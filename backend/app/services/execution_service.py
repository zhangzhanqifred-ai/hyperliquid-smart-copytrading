from datetime import datetime
from typing import Any, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Signal
from ..models.follower import FollowerTrade
from .execution_client import ExecutionClient, SimulatedExecutionClient


# Default notional size used when no explicit notional is provided.
# For example, use a 0.01 BTC-equivalent notional per signal.
DEFAULT_NOTIONAL_PER_SIGNAL: float = 0.01


def execute_signal(
    db: Session,
    signal_id: int,
    notional: float | None = None,
    execution_client: ExecutionClient | None = None,
) -> FollowerTrade:
    """
    Execute a trading signal using the provided ExecutionClient.

    - Look up the `Signal` by id.
    - Validates signal state.
    - Uses execution_client.open_position() to execute.
    - Marks signal as executed.
    - Returns the persisted FollowerTrade.
    """
    if execution_client is None:
        execution_client = SimulatedExecutionClient(db)

    signal = db.get(Signal, signal_id)
    if signal is None:
        raise ValueError(f"Signal {signal_id} not found")

    if signal.executed:
        raise ValueError(f"Signal {signal_id} has already been executed")

    now = datetime.utcnow()

    entry_price = (signal.price_range_min + signal.price_range_max) / 2.0
    if entry_price <= 0:
        raise ValueError(f"Invalid entry price computed for signal {signal_id}")

    effective_notional = notional if notional is not None else DEFAULT_NOTIONAL_PER_SIGNAL
    if effective_notional <= 0:
        raise ValueError("Notional must be positive")

    # Execute via client
    # Note: this might commit the trade to DB (for Simulated) or send API request (for Real)
    trade_id = execution_client.open_position(
        symbol=signal.symbol,
        side=signal.side,  # type: ignore
        notional=effective_notional,
        price=entry_price,
        signal_id=signal.id,
    )

    # Mark the signal as executed locally
    signal.executed = True
    signal.executed_at = now
    
    db.add(signal)
    db.commit()
    db.refresh(signal)

    print(
        f"[ExecutionService] Executed signal {signal_id} on {signal.symbol} "
        f"side={signal.side} size={effective_notional:.6f} entry_price={entry_price:.2f}"
    )

    # Return the trade object. For Simulated execution, it's in the DB.
    # For real execution, we might need to fetch or construct it.
    # Here we assume we can fetch it from DB because SimulatedExecutionClient writes it.
    # If using a real client, we might need a local representation.
    # Assuming for now we are using SimulatedExecutionClient or compatible local storage.
    trade = db.get(FollowerTrade, trade_id)
    if not trade:
        # Fallback if not found (should not happen with SimulatedExecutionClient)
        raise RuntimeError(f"Trade {trade_id} created but not found in DB")
        
    return trade


def close_all_positions(
    db: Session,
    exit_price_map: dict[str, float] | None = None,
    reason: str | None = None,
    execution_client: ExecutionClient | None = None,
) -> list[FollowerTrade]:
    """
    Close all open positions using the ExecutionClient.
    """
    if execution_client is None:
        execution_client = SimulatedExecutionClient(db)

    if exit_price_map is None:
        exit_price_map = {}

    now = datetime.utcnow()

    # Get open positions from client
    # returns List[dict]
    open_trades_data = execution_client.get_open_positions()
    
    if not open_trades_data:
        return []

    # If no explicit exit prices are provided, we synthesize a simple PnL
    # pattern so that the risk engine sees non-zero equity and drawdown.
    if not exit_price_map:
        # Sort by opened_at to have a deterministic ordering.
        # Ensure opened_at is datetime
        open_trades_sorted = sorted(
            open_trades_data,
            key=lambda t: t.get("opened_at") or now,
        )
        count = len(open_trades_sorted)
        n = max(1, count // 4) if count > 0 else 0

        winner_ids = {t["id"] for t in open_trades_sorted[:n]}
        loser_ids = {t["id"] for t in open_trades_sorted[-n:]} if n > 0 else set()
    else:
        winner_ids = set()
        loser_ids = set()

    closed_ids = []

    for trade_data in open_trades_data:
        t_id = trade_data["id"]
        t_symbol = trade_data["symbol"]
        t_entry = trade_data["entry_price"]
        
        if exit_price_map:
            exit_price = exit_price_map.get(t_symbol, t_entry)
        else:
            if t_id in winner_ids:
                exit_price = t_entry * 1.05  # +5%
            elif t_id in loser_ids:
                exit_price = t_entry * 0.7  # -30%
            else:
                exit_price = t_entry

        if exit_price is None or exit_price <= 0:
            exit_price = t_entry

        execution_client.close_position(
            follower_trade_id=t_id,
            price=exit_price,
        )
        closed_ids.append(t_id)

        print(
            f"[ExecutionService] Closed position {t_id} on {t_symbol} "
            f"exit={exit_price:.2f} reason={reason or 'N/A'}"
        )

    # Return list of FollowerTrade objects
    if not closed_ids:
        return []
        
    stmt = select(FollowerTrade).where(FollowerTrade.id.in_(closed_ids))
    return list(db.scalars(stmt).all())
