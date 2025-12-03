from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Signal
from ..schemas.signal import TradeEvent, StrategyConfig
from ..schemas import SignalOut, FollowerTradeOut
from ..services.strategy_engine import process_trade_event
from ..services.execution_service import execute_signal
from ..services.execution_client import SimulatedExecutionClient

router = APIRouter(prefix="/signals", tags=["signals"])

DbDep = Annotated[Session, Depends(get_db)]


@router.post("/debug/trade-event", response_model=Optional[SignalOut])
def debug_trade_event(
    event: TradeEvent,
    db: DbDep,
) -> Optional[SignalOut]:
    """
    Debug endpoint: feed a single TradeEvent into the strategy engine.

    If a Signal is generated, return it; otherwise return null.
    """
    config = StrategyConfig()  # Later this can be loaded from a config table.
    signal = process_trade_event(db=db, event=event, config=config)
    return signal


@router.get("/recent", response_model=List[SignalOut])
def get_recent_signals(
    db: DbDep,
    limit: int = Query(50, ge=1, le=200, description="Number of most recent signals to return"),
) -> list[SignalOut]:
    """
    Return the most recent N signals ordered by creation time (descending).
    """
    stmt = select(Signal).order_by(Signal.created_at.desc()).limit(limit)
    return list(db.scalars(stmt).all())


@router.post("/{signal_id}/execute", response_model=FollowerTradeOut)
def execute_signal_endpoint(
    signal_id: int,
    db: DbDep,
) -> FollowerTradeOut:
    """
    Execute a simulated follow-trade for the specified signal_id.

    Uses the default notional per signal defined in the execution service.
    """
    execution_client = SimulatedExecutionClient(db)
    trade = execute_signal(db=db, signal_id=signal_id, execution_client=execution_client)
    return trade
