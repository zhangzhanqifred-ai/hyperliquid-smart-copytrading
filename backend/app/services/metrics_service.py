from datetime import datetime, timedelta
import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import SmartTraderUniverse, Trade
from ..schemas import TraderMetricsResult
from .selection_service import DEFAULT_CONFIG, evaluate_trader_profile


def compute_metrics_for_trader(
    db: Session,
    trader_id: int,
    window_days: int,
) -> TraderMetricsResult:
    """
    Compute performance metrics for a trader over a given lookback window,
    and write summary fields into `smart_trader_universe`.
    
    CRITICAL FIELD DEPENDENCIES:
    - This function relies on `trade.realized_pnl` being non-None to consider a trade "valid" for metrics.
    - It also relies on `trade.entry_price * trade.size` (notional) being non-zero.
    - `num_trades` counts only these valid trades.
    - `win_rate`, `expectancy`, `payoff_ratio` etc. all derive from `realized_pnl`.
    - The core metric R (Risk Multiple) is calculated as:
      R = realized_pnl / (entry_price * size)
    - If `realized_pnl` is None (e.g. raw fills without PnL), metrics will be all zeros.
    """
    now = datetime.utcnow()
    window_start = now - timedelta(days=window_days)

    # Pull all trades in the window for this trader.
    trades: list[Trade] = list(
        db.scalars(
            select(Trade)
            .where(
                Trade.trader_id == trader_id,
                Trade.opened_at >= window_start,
            )
            .order_by(Trade.opened_at.asc())
        ).all()
    )

    if not trades:
        # No trades in window: run selection on an "empty" metrics profile so
        # that filters and score still behave consistently.
        metrics_profile = TraderMetricsResult(
            pnl=0.0,
            win_rate=0.0,
            volatility=0.0,
            max_drawdown=0.0,
            num_trades=0,
            active_days=0,
            trades_per_day=0.0,
            avg_win_r=0.0,
            avg_loss_r=0.0,
            payoff_ratio=0.0,
            expectancy=0.0,
            min_trade_r=0.0,
            max_drawdown_pct=0.0,
        )
        selection = evaluate_trader_profile(metrics_profile, DEFAULT_CONFIG)
        _update_smart_universe_row(
            db=db,
            trader_id=trader_id,
            window_days=window_days,
            pnl_window=0.0,
            win_rate_window=0.0,
            volatility_window=0.0,
            max_drawdown_window=0.0,
            sharpe_window=None,
            num_trades=0,
            active_days=0,
            trades_per_day=0.0,
            avg_win_r=0.0,
            avg_loss_r=0.0,
            payoff_ratio=0.0,
            expectancy=0.0,
            min_trade_r=0.0,
            max_drawdown_pct=0.0,
            eligible=selection.eligible,
            score=selection.score,
            filters_snapshot=DEFAULT_CONFIG.model_dump(),
        )
        # Return the metrics together with eligibility and score.
        return metrics_profile.model_copy(
            update={"eligible": selection.eligible, "score": selection.score}
        )

    # --- Per-trade R-multiples and basic aggregates ---
    rs: list[float] = []
    win_rs: list[float] = []
    loss_rs: list[float] = []
    total_pnl = 0.0
    active_dates: set[datetime.date] = set()

    for t in trades:
        # Track active days from both open and close timestamps.
        if t.opened_at is not None:
            active_dates.add(t.opened_at.date())
        if t.closed_at is not None:
            active_dates.add(t.closed_at.date())

        # For R-multiple we only use trades with a realized PnL and non-zero
        # notional (entry_price * size). Open trades without realized PnL are
        # ignored for now, but you could extend this to use mark-to-market PnL.
        if t.realized_pnl is None:
            continue

        notional = t.entry_price * t.size
        if notional == 0:
            continue

        r = t.realized_pnl / notional
        rs.append(r)
        total_pnl += t.realized_pnl

        if r > 0:
            win_rs.append(r)
        elif r < 0:
            loss_rs.append(r)

    num_trades = len(rs)
    active_days = len(active_dates)

    if num_trades == 0:
        # All trades had missing/invalid PnL; treat as no data but still run selection.
        metrics_profile = TraderMetricsResult(
            pnl=0.0,
            win_rate=0.0,
            volatility=0.0,
            max_drawdown=0.0,
            num_trades=0,
            active_days=active_days,
            trades_per_day=0.0,
            avg_win_r=0.0,
            avg_loss_r=0.0,
            payoff_ratio=0.0,
            expectancy=0.0,
            min_trade_r=0.0,
            max_drawdown_pct=0.0,
        )
        selection = evaluate_trader_profile(metrics_profile, DEFAULT_CONFIG)
        _update_smart_universe_row(
            db=db,
            trader_id=trader_id,
            window_days=window_days,
            pnl_window=0.0,
            win_rate_window=0.0,
            volatility_window=0.0,
            max_drawdown_window=0.0,
            sharpe_window=None,
            num_trades=0,
            active_days=active_days,
            trades_per_day=0.0,
            avg_win_r=0.0,
            avg_loss_r=0.0,
            payoff_ratio=0.0,
            expectancy=0.0,
            min_trade_r=0.0,
            max_drawdown_pct=0.0,
            eligible=selection.eligible,
            score=selection.score,
            filters_snapshot=DEFAULT_CONFIG.model_dump(),
        )
        return metrics_profile.model_copy(
            update={"eligible": selection.eligible, "score": selection.score}
        )

    # Win rate: fraction of trades with r_i > 0.
    # Modified: exclude flat trades (r=0) from denominator to focus on directionality
    # Or keep them if you consider flat as "not winning". 
    # User request: "不把 flat 算进分母"
    # Also ensure we handle "true losses" (r < 0) correctly.
    
    count_directional = len(win_rs) + len(loss_rs)
    win_rate = len(win_rs) / count_directional if count_directional > 0 else 0.0

    # Average win R (0 if there are no winning trades).
    avg_win_r = sum(win_rs) / len(win_rs) if win_rs else 0.0

    # Average loss R, expressed as a positive number (0 if no losing trades).
    # User request: "如果没有亏损 trade，可以用一个轻微的负值占位，避免 payoff_ratio = 0/0"
    if loss_rs:
        avg_loss_r = sum(abs(x) for x in loss_rs) / len(loss_rs)
    else:
        # Avoid div by zero later if used blindly, though here we usually keep it 0.0 
        # and handle payoff ratio logic below.
        # User hint suggests maybe using a small placeholder if needed for ratio,
        # but standard practice is to handle it in the ratio calc.
        avg_loss_r = 0.0 

    # Payoff ratio = average win size / average loss size.
    if avg_loss_r > 0:
        payoff_ratio = avg_win_r / avg_loss_r
    else:
        # If never lost, payoff is infinite? Or 0?
        # If we have wins but no losses, ratio is technically infinite.
        # We cap it or treat as high value if wins exist.
        payoff_ratio = 0.0 if avg_win_r == 0 else 10.0 # Arbitrary cap for "perfect" trader

    # Expectancy = average R per trade.
    mean_r = sum(rs) / num_trades
    expectancy = mean_r

    # Minimum (worst) trade R.
    min_trade_r = min(rs) if rs else 0.0

    # Volatility: standard deviation of R-multiples.
    if num_trades > 1:
        variance = sum((r - mean_r) ** 2 for r in rs) / num_trades
        volatility = math.sqrt(variance)
    else:
        volatility = 0.0

    # --- Equity curve and drawdown calculations ---
    equity = 1.0
    peak_equity = 1.0
    max_drawdown_abs = 0.0  # in synthetic equity units
    max_drawdown_pct = 0.0  # normalized by peak_equity (0.3 == 30%)

    for r in rs:
        equity *= 1.0 + r
        if equity > peak_equity:
            peak_equity = equity
        drawdown_abs = peak_equity - equity
        # Drawdown pct relative to the running peak
        drawdown_pct = drawdown_abs / peak_equity if peak_equity > 0 else 0.0

        if drawdown_abs > max_drawdown_abs:
            max_drawdown_abs = drawdown_abs
        if drawdown_pct > max_drawdown_pct:
            max_drawdown_pct = drawdown_pct

    # For now we do not compute Sharpe; you can fill this in later.
    sharpe_window = None

    trades_per_day = num_trades / active_days if active_days > 0 else 0.0

    # Build a detailed metrics profile and run selection/scoring.
    metrics_profile = TraderMetricsResult(
        pnl=total_pnl,
        win_rate=win_rate,
        volatility=volatility,
        max_drawdown=max_drawdown_abs,
        num_trades=num_trades,
        active_days=active_days,
        trades_per_day=trades_per_day,
        avg_win_r=avg_win_r,
        avg_loss_r=avg_loss_r,
        payoff_ratio=payoff_ratio,
        expectancy=expectancy,
        min_trade_r=min_trade_r,
        max_drawdown_pct=max_drawdown_pct,
    )
    selection = evaluate_trader_profile(metrics_profile, DEFAULT_CONFIG)

    # Persist summary statistics into the smart_trader_universe table so you
    # can easily filter addresses based on these metrics.
    _update_smart_universe_row(
        db=db,
        trader_id=trader_id,
        window_days=window_days,
        pnl_window=total_pnl,
        win_rate_window=win_rate,
        volatility_window=volatility,
        max_drawdown_window=max_drawdown_abs,
        sharpe_window=sharpe_window,
        num_trades=num_trades,
        active_days=active_days,
        trades_per_day=trades_per_day,
        avg_win_r=avg_win_r,
        avg_loss_r=avg_loss_r,
        payoff_ratio=payoff_ratio,
        expectancy=expectancy,
        min_trade_r=min_trade_r,
        max_drawdown_pct=max_drawdown_pct,
        eligible=selection.eligible,
        score=selection.score,
        filters_snapshot=DEFAULT_CONFIG.model_dump(),
    )

    # Return full metrics profile including eligibility and score.
    return metrics_profile.model_copy(
        update={"eligible": selection.eligible, "score": selection.score}
    )


def _update_smart_universe_row(
    db: Session,
    *,
    trader_id: int,
    window_days: int,
    pnl_window: float,
    win_rate_window: float,
    volatility_window: float,
    max_drawdown_window: float,
    sharpe_window: float | None,
    num_trades: int,
    active_days: int,
    trades_per_day: float,
    avg_win_r: float,
    avg_loss_r: float,
    payoff_ratio: float,
    expectancy: float,
    min_trade_r: float,
    max_drawdown_pct: float,
    score: float,
    eligible: bool,
    filters_snapshot: dict,
) -> None:
    """
    Helper to insert or update the `smart_trader_universe` row for a trader.

    `eligible` and `score` are computed by `evaluate_trader_profile` in
    `selection_service`. `filters_snapshot` should contain the configuration
    that was used for this evaluation so that you can later reconstruct or
    debug the selection logic.
    """
    existing = db.scalar(
        select(SmartTraderUniverse).where(
            SmartTraderUniverse.trader_id == trader_id,
            SmartTraderUniverse.window_days == window_days,
        )
    )

    if existing is None:
        existing = SmartTraderUniverse(
            trader_id=trader_id,
            window_days=window_days,
            filters_snapshot=filters_snapshot,
            eligible=eligible,
            pnl_window=pnl_window,
            win_rate_window=win_rate_window,
            volatility_window=volatility_window,
            max_drawdown_window=max_drawdown_window,
            sharpe_window=sharpe_window,
            num_trades=num_trades,
            active_days=active_days,
            trades_per_day=trades_per_day,
            avg_win_r=avg_win_r,
            avg_loss_r=avg_loss_r,
            payoff_ratio=payoff_ratio,
            expectancy=expectancy,
            min_trade_r=min_trade_r,
            max_drawdown_pct=max_drawdown_pct,
            score=score,
        )
        db.add(existing)
    else:
        existing.pnl_window = pnl_window
        existing.win_rate_window = win_rate_window
        existing.volatility_window = volatility_window
        existing.max_drawdown_window = max_drawdown_window
        existing.sharpe_window = sharpe_window
        existing.num_trades = num_trades
        existing.active_days = active_days
        existing.trades_per_day = trades_per_day
        existing.avg_win_r = avg_win_r
        existing.avg_loss_r = avg_loss_r
        existing.payoff_ratio = payoff_ratio
        existing.expectancy = expectancy
        existing.min_trade_r = min_trade_r
        existing.max_drawdown_pct = max_drawdown_pct
        existing.score = score
        existing.eligible = eligible
        existing.filters_snapshot = filters_snapshot

    db.commit()
