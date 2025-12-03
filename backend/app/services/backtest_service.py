from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, time, timedelta
import math
from typing import Any, Deque, Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from ..models import BacktestRun, Trader
from ..models.metrics import SmartTraderUniverse
from ..models.trade import Trade
from ..schemas import BacktestRunCreate
from ..schemas.signal import StrategyConfig
from .execution_service import DEFAULT_NOTIONAL_PER_SIGNAL
from .execution_client import SimulatedExecutionClient

DEFAULT_INITIAL_EQUITY: float = 10000.0


@dataclass
class BacktestTradeEvent:
    trader_address: str
    symbol: str
    side: str  # 'long' or 'short'
    price: float
    size: float
    timestamp: datetime
    exit_price: float | None
    realized_pnl: float | None
    closed_at: datetime | None


@dataclass
class BacktestEngineContext:
    event_buffers: Dict[tuple[str, str], Deque[BacktestTradeEvent]]
    last_signal_ts: Dict[tuple[str, str], datetime]


def _bt_get_price_range(event: BacktestTradeEvent, config: StrategyConfig) -> tuple[float, float]:
    """
    Compute price band [price_min, price_max] around the event price for backtesting.
    """
    if config.price_range_width_pct is not None:
        half_width = event.price * (config.price_range_width_pct / 2.0)
        price_min = event.price - half_width
        price_max = event.price + half_width
    elif config.price_range_width_abs is not None:
        half_width = config.price_range_width_abs / 2.0
        price_min = event.price - half_width
        price_max = event.price + half_width
    else:
        price_min = price_max = event.price

    return price_min, price_max


def _bt_process_trade_event(
    ctx: BacktestEngineContext,
    event: BacktestTradeEvent,
    config: StrategyConfig,
) -> Optional[dict[str, Any]]:
    """
    Backtest version of the strategy engine's process_trade_event.

    It operates purely in memory and does NOT touch the database.
    Returns a lightweight signal dict when a signal is generated, otherwise None.
    """
    key = (event.symbol, event.side)
    buf = ctx.event_buffers[key]

    buf.append(event)

    cutoff = event.timestamp - timedelta(seconds=config.time_window_seconds)
    while buf and buf[0].timestamp < cutoff:
        buf.popleft()

    price_min, price_max = _bt_get_price_range(event, config)

    smart_addresses: set[str] = set()
    for e in buf:
        if price_min <= e.price <= price_max and e.symbol == event.symbol and e.side == event.side:
            smart_addresses.add(e.trader_address)

    smart_count = len(smart_addresses)
    if smart_count < config.min_smart_traders:
        return None

    last_ts = ctx.last_signal_ts.get(key)
    if last_ts is not None:
        delta = (event.timestamp - last_ts).total_seconds()
        if delta < config.min_signal_interval_seconds:
            return None

    ctx.last_signal_ts[key] = event.timestamp

    return {
        "symbol": event.symbol,
        "side": event.side,
        "price_min": price_min,
        "price_max": price_max,
        "timestamp": event.timestamp,
        "smart_trader_count": smart_count,
        "addresses": list(smart_addresses),
        "event": event,
    }


def _compute_drawdown_from_equity(equity_curve: list[float], initial_equity: float) -> tuple[float, float]:
    """
    Given an equity curve, compute max drawdown (abs and pct).
    """
    peak = initial_equity
    max_dd_abs = 0.0

    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = peak - eq
        if dd > max_dd_abs:
            max_dd_abs = dd

    max_dd_pct = max_dd_abs / initial_equity if initial_equity > 0 else 0.0
    return max_dd_abs, max_dd_pct


def run_backtest(db: Session, payload: BacktestRunCreate) -> BacktestRun:
    """
    Run a backtest over historical trades and smart trader universe.

    This function:
    - Determines the time range from `start_date`/`end_date`.
    - Selects eligible smart traders from `smart_trader_universe` for a given
      `window_days` and optional score / activity filters.
    - Reads historical trades for those traders from `trades`.
    - Feeds them into an in-memory strategy engine that mirrors the realtime
      logic (time window + price band + min_smart_traders).
    - For each generated signal, simulates a single-position trade whose PnL
      scales with the underlying trader's realized PnL.
    - Builds an equity curve, computes drawdown and summary stats.
    - Persists a `BacktestRun` row with params + summary JSON and returns it.
    """
    params: dict[str, Any] = payload.params or {}

    # Universe configuration.
    window_days: int = int(params.get("window_days", 30))
    min_score: float | None = params.get("min_score")
    min_trades_per_day: float | None = params.get("min_trades_per_day")

    # Strategy parameters (mirrors StrategyConfig fields).
    strategy_params = params.get("strategy", {}) or {}
    if strategy_params is None:
        strategy_params = {}
        
    strategy_cfg = StrategyConfig(
        time_window_seconds=int(strategy_params.get("time_window_seconds", params.get("time_window_seconds", 300))),
        price_range_width_pct=float(strategy_params.get("price_range_width_pct", params.get("price_range_width_pct", 0.01))),
        price_range_width_abs=float(strategy_params.get("price_range_width_abs")) if strategy_params.get("price_range_width_abs") else None,
        min_smart_traders=int(strategy_params.get("min_smart_traders", params.get("min_smart_traders", 1))),
        min_signal_interval_seconds=int(strategy_params.get("min_signal_interval_seconds", params.get("min_signal_interval_seconds", 1))),
    )

    # Execution parameters: prefer nested params["execution"], with a fallback
    # to top-level keys for backwards compatibility.
    exec_params: dict[str, Any] = params.get("execution", {}) or {}
    if exec_params is None:
        exec_params = {}

    initial_equity: float = float(
        exec_params.get("initial_equity", params.get("initial_equity", DEFAULT_INITIAL_EQUITY))
    )
    notional_per_signal: float = float(
        exec_params.get(
            "notional_per_signal",
            params.get("notional_per_signal", DEFAULT_NOTIONAL_PER_SIGNAL),
        )
    )
    fee_rate_bps: float = float(exec_params.get("fee_rate_bps", params.get("fee_rate_bps", 5.0)))

    # Initialize Execution Client for recording trades (optional usage in loop)
    execution_client = SimulatedExecutionClient(db)

    # 1) Determine time range.
    start_dt = datetime.combine(payload.start_date, time.min)
    end_dt = datetime.combine(payload.end_date, time.max)

    # 2) Select eligible smart traders for the chosen window.
    stu_alias = aliased(SmartTraderUniverse)
    trader_alias = aliased(Trader)

    stu_stmt = (
        select(stu_alias, trader_alias)
        .join(trader_alias, trader_alias.id == stu_alias.trader_id)
        .where(
            stu_alias.window_days == window_days,
            # stu_alias.eligible.is_(True), # Removed hard filter on eligible
        )
    )

    if min_score is not None:
        stu_stmt = stu_stmt.where(stu_alias.score >= float(min_score))
    if min_trades_per_day is not None:
        stu_stmt = stu_stmt.where(stu_alias.trades_per_day >= float(min_trades_per_day))

    stu_rows = db.execute(stu_stmt).all()
    
    # LOG 2: 选出的聪明钱数量
    import logging
    logger = logging.getLogger("uvicorn")
    logger.info(f"[backtest] window={window_days}, min_score={min_score} -> {len(stu_rows)} smart traders selected")
    if stu_rows:
        sample = stu_rows[:3]
        logger.info(f"[backtest] sample traders: {[(r[0].trader_id, r[0].score, r[0].trades_per_day) for r in sample]}")

    if not stu_rows:
        run = BacktestRun(
            start_date=payload.start_date,
            end_date=payload.end_date,
            params=params,
            name=params.get("name"),
            description=params.get("description"),
            total_pnl=0.0,
            max_drawdown=0.0,
            win_rate=0.0,
            sharpe=0.0,
            summary={
                "initial_equity": initial_equity,
                "final_equity": initial_equity,
                "total_return_pct": 0.0,
                "max_drawdown_abs": 0.0,
                "max_drawdown_pct": 0.0,
                "total_trades": 0,
                "win_rate": 0.0,
                "equity_curve": [],
            },
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    trader_ids: set[int] = set()
    address_by_id: dict[int, str] = {}
    for stu, trader in stu_rows:
        trader_ids.add(stu.trader_id)
        address_by_id[trader.id] = trader.address

    # 3) Load trades for these traders within the time range.
    trades_stmt = (
        select(Trade)
        .where(
            Trade.trader_id.in_(trader_ids),
            Trade.opened_at >= start_dt,
            Trade.opened_at <= end_dt,
        )
        .order_by(Trade.opened_at.asc())
    )
    trades: list[Trade] = list(db.scalars(trades_stmt).all())
    
    # LOG 3: 选出的交易数量
    logger.info(f"[backtest] collected {len(trades)} raw trades for candidates within {start_dt} to {end_dt}")

    events: list[BacktestTradeEvent] = []
    for t in trades:
        addr = address_by_id.get(t.trader_id)
        if addr is None:
            continue

        events.append(
            BacktestTradeEvent(
                trader_address=addr,
                symbol=t.symbol,
                side=t.side,
                price=t.entry_price,
                size=t.size,
                timestamp=t.opened_at,
                exit_price=t.exit_price,
                realized_pnl=t.realized_pnl,
                closed_at=t.closed_at,
            )
        )

    events.sort(key=lambda e: e.timestamp)

    # 4) Run the in-memory strategy engine and simulate execution.
    ctx = BacktestEngineContext(
        event_buffers=defaultdict(deque),
        last_signal_ts={},
    )

    # In backtests, we typically keep everything in memory for speed.
    # However, per requirements, we use the execution_client to record "simulated" trades to DB.
    # This will be slower but creates a persistent record of backtest executions.
    virtual_pnls: list[float] = []
    virtual_trades: list[dict[str, Any]] = []
    win_count = 0
    loss_count = 0
    total_signals = 0

    # Build a quick lookup for smart trader exit events: (address, symbol, side) -> sorted list of (exit_time, exit_price)
    # We can optimize this by only querying "exit" trades or using the event list we already have.
    # Since 'events' contains all trades for the selected smart traders in the window, we can index them.
    # Note: The 'BacktestTradeEvent' already has exit_price/closed_at if it was a closed trade.
    # We can use that directly if the signal is formed by an OPEN trade.
    # However, our logic below iterates through events which ARE trades.
    # If `ev` is an entry, we can use `ev.exit_price` and `ev.closed_at` if available.
    
    # But wait, the requirement says: "When *some* smart trader Ai closes their position".
    # If the signal was formed by [A, B], and later A closes, we close A's leg.
    # If B closes later, we close B's leg.
    # The `BacktestTradeEvent` structure seems to represent a single round-trip trade (entry+exit).
    # If so, `ev` already contains the exit info for that specific trader's trade.
    # So for a signal generated at `ev.timestamp` involving trader `ev.trader_address`,
    # this specific trader's exit is simply `ev.closed_at`.
    
    # However, a signal aggregates MULTIPLE traders.
    # `_bt_process_trade_event` returns a signal dict with `addresses`.
    # We need to find the corresponding exit for EACH address in that list.
    # Since `events` list has all the trades, we can search in `events` for the trades that contributed to the signal.
    # Optimally, we index `events` by (address, symbol, side) to quickly find the trade that happened around signal time.

    # Index events for fast lookup of exits
    # Key: (address, symbol, side) -> List of events sorted by time
    events_by_trader: Dict[tuple[str, str, str], list[BacktestTradeEvent]] = defaultdict(list)
    for e in events:
        events_by_trader[(e.trader_address, e.symbol, e.side)].append(e)

    # We need to track open legs to handle risk (max drawdown).
    # List of active legs: { 'exit_time': datetime, 'pnl': float, 'open_time': datetime, 'equity_curve_impact': ... }
    # Actually, simpler: calculate PnL for all legs, collect them, then sort by exit time to build equity curve.
    # Risk check (drawdown > 30%) needs to happen chronologically.
    
    # Let's collect all "Leg Executions" first.
    # Each leg has: open_time, close_time, pnl, notional
    all_legs: list[dict[str, Any]] = []

    for ev in events:
        sig = _bt_process_trade_event(ctx, ev, strategy_cfg)
        if sig is None:
            continue

        total_signals += 1
        
        # LOG 4: 生成信号数量 (Sample)
        if total_signals % 100 == 0 or total_signals < 5:
             logger.info(f"[backtest] Signal {total_signals}: {ev.symbol} {ev.side} @ {ev.timestamp}")

        # Signal data
        addresses = sig.get("addresses", [])
        if not addresses:
            continue
            
        n_traders = len(addresses)
        leg_notional = notional_per_signal / n_traders
        
        # For each trader in the signal, find their specific trade exit
        for addr in addresses:
            # Find the trade for this address that overlaps with signal time
            # We look for a trade where opened_at <= signal_time <= closed_at?
            # Or simply the trade that started at or slightly before this signal?
            # In our simplified `_bt_process_trade_event`, the signal is triggered by `ev`.
            # But other traders might have opened earlier within `time_window_seconds`.
            
            # Strategy: Look for the first trade for `addr` that opened within [signal_time - window, signal_time + window]
            # Or simply the trade that is "active" or "just opened".
            # Since we are iterating chronologically, and the buffer has recent trades.
            
            candidate_trades = events_by_trader.get((addr, sig["symbol"], sig["side"]), [])
            
            # Find the trade that likely contributed to this signal
            # It should be the one in the buffer. The buffer logic keeps trades within `time_window_seconds`.
            # So we look for a trade where `timestamp` is close to `sig['timestamp']`.
            
            matched_trade = None
            for t in candidate_trades:
                # allow a small epsilon or check if it matches the buffer window logic
                # buffer logic: t.timestamp >= sig['timestamp'] - time_window
                # and t.timestamp <= sig['timestamp']
                if (sig["timestamp"] - timedelta(seconds=strategy_cfg.time_window_seconds) 
                    <= t.timestamp <= sig["timestamp"]):
                    # Check price constraint if needed, though buffer already filtered it
                    # We take the most recent one or just the first one found? 
                    # Usually the signal is triggered by the LATEST one (`ev`), but includes others.
                    # We match the specific trade instance.
                    matched_trade = t
                    # If multiple trades match (e.g. trader opened twice quickly), 
                    # we might pick the one closest to signal time or just the first one. 
                    # Let's pick the one closest to signal timestamp to be safe, or just the last one.
                    # Actually, any trade in the window contributes. 
                    # Let's just take the LAST one in the window for that trader to simplify,
                    # or ideally we map them 1-to-1 if we tracked IDs.
                    # For now: take the one with closest timestamp.
            
            if matched_trade and matched_trade.exit_price is not None:
                # Found a valid closed trade for this leg
                # Calculate PnL for this leg
                if matched_trade.side == "long":
                    r = (matched_trade.exit_price - matched_trade.entry_price) / matched_trade.entry_price
                else:
                    r = (matched_trade.entry_price - matched_trade.exit_price) / matched_trade.entry_price
                
                gross_pnl = leg_notional * r
                fee = leg_notional * fee_rate_bps / 10000.0
                net_pnl = gross_pnl - fee
                
                close_ts = matched_trade.closed_at or matched_trade.timestamp
                
                all_legs.append({
                    "open_time": sig["timestamp"],
                    "close_time": close_ts,
                    "pnl": net_pnl,
                    "r": r,
                    "symbol": sig["symbol"],
                    "side": sig["side"],
                    "trader": addr,
                    "notional": leg_notional
                })
            else:
                # Trader holds until end of backtest or data missing
                # Force close at end of period
                # For simplicity in this iteration, if no exit info, we treat as 0 PnL or ignore
                # Or we can mark it as open.
                pass

    # 5) Chronological Replay for Risk Management
    # We have a list of legs with known open/close times and PnL.
    # We need to simulate equity curve and check for max drawdown > 30%.
    # Events: OPEN (deduct fee?), CLOSE (add PnL).
    # Actually, for simple backtest, we usually mark PnL at CLOSE time.
    
    # Sort all lifecycle events: (time, type, amount)
    # type: 0=OPEN (fee?), 1=CLOSE (pnl)
    # To verify drawdown, we strictly need mark-to-market. 
    # But "Force Liquidate at 30% DD" implies we check equity often.
    # Approximation: Check equity at every CLOSE event.
    
    all_legs.sort(key=lambda x: x["close_time"])
    
    equity = initial_equity
    peak_equity = initial_equity
    
    equity_curve: list[dict[str, Any]] = [{"step": 0, "equity": equity, "time": start_dt.isoformat()}]
    
    virtual_trades = []
    active_drawdown_triggered = False
    
    step_counter = 0
    for leg in all_legs:
        if active_drawdown_triggered:
            # If already liquidated, subsequent trades are cancelled or result in 0?
            # Simplification: Stop trading after liquidation.
            break
            
        # Update equity
        equity += leg["pnl"]
        step_counter += 1
        
        # Check DD
        if equity > peak_equity:
            peak_equity = equity
        
        dd_abs = peak_equity - equity
        dd_pct = dd_abs / peak_equity if peak_equity > 0 else 0.0
        
        if dd_pct >= 0.3:
            # Trigger Risk!
            active_drawdown_triggered = True
            # Technically we should find the EXACT moment it crossed 30%.
            # Here we just stop and accept this loss (or cap it at -30% exactly?).
            # Let's accept the loss that triggered it.
            logger.info(f"[backtest] Risk triggered! DD={dd_pct:.2%}")
        
        equity_curve.append({
            "step": step_counter, 
            "equity": equity, 
            "time": leg["close_time"].isoformat()
        })
        
        virtual_trades.append({
            "symbol": leg["symbol"],
            "side": leg["side"],
            "entry_time": leg["open_time"].isoformat(),
            "exit_time": leg["close_time"].isoformat(),
            "r": leg["r"],
            "realized_pnl": leg["pnl"],
            "source_trader": leg["trader"]
        })
        
        if leg["pnl"] > 0:
            win_count += 1
        elif leg["pnl"] < 0:
            loss_count += 1

    virtual_pnls = [t["realized_pnl"] for t in virtual_trades]
    total_trades = len(virtual_pnls)
    
    # LOG 4/5 Summary
    logger.info(f"[backtest] generated {total_signals} signals total")
    logger.info(f"[backtest] executed {total_trades} follower legs; final_equity={equity}")

    # Build equity curve based on virtual follower trades. We assume trades are
    # closed at their "exit_time" ordering; here we simply apply them in the
    # order we recorded them.
    equity = initial_equity
    equity_curve: list[dict[str, Any]] = [{"step": 0, "equity": equity}]
    step_counter = 0

    for pnl_bt in virtual_pnls:
        step_counter += 1
        equity += pnl_bt
        equity_curve.append({"step": step_counter, "equity": equity})


    total_pnl = equity - initial_equity
    total_return_pct = total_pnl / initial_equity if initial_equity > 0 else 0.0

    win_rate = win_count / total_trades if total_trades > 0 else 0.0

    wins = [p for p in virtual_pnls if p > 0]
    losses = [p for p in virtual_pnls if p < 0]

    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = -sum(losses) / len(losses) if losses else 0.0
    payoff_ratio = avg_win / avg_loss if avg_win > 0.0 and avg_loss > 0.0 else 0.0

    expectancy = sum(virtual_pnls) / total_trades if total_trades > 0 else 0.0

    if total_trades > 1:
        mean_pnl = expectancy
        variance = sum((p - mean_pnl) ** 2 for p in virtual_pnls) / total_trades
        std_dev = math.sqrt(variance)
        sharpe = (expectancy / std_dev) if std_dev > 0 else 0.0
    else:
        sharpe = 0.0

    max_dd_abs, max_dd_pct = _compute_drawdown_from_equity([e["equity"] for e in equity_curve], initial_equity)

    # Truncate equity curve to avoid huge payloads.
    max_points = 500
    if len(equity_curve) > max_points:
        step = max(1, len(equity_curve) // max_points)
        eq_samples = [equity_curve[i] for i in range(0, len(equity_curve), step)]
    else:
        eq_samples = equity_curve

    summary = {
        "initial_equity": initial_equity,
        "final_equity": equity,
        "total_pnl": total_pnl,
        "total_return_pct": total_return_pct,
        "max_drawdown_abs": max_dd_abs,
        "max_drawdown_pct": max_dd_pct,
        "total_signals": total_signals,
        "total_trades": total_trades,
        "win_rate": win_rate,
        "payoff_ratio": payoff_ratio,
        "expectancy": expectancy,
        "sharpe": sharpe,
        "equity_curve": eq_samples,
        "virtual_trades": virtual_trades,
        "params_snapshot": params,
    }


    run = BacktestRun(
        start_date=payload.start_date,
        end_date=payload.end_date,
        params=params,
        name=params.get("name"),
        description=params.get("description"),
        total_pnl=total_pnl,
        max_drawdown=max_dd_abs,
        win_rate=win_rate,
        sharpe=sharpe,
        summary=summary,
    )

    db.add(run)
    db.commit()
    db.refresh(run)

    return run
