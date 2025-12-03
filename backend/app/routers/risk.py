from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import RiskStatusResponse
from ..services.execution_service import close_all_positions
from ..services.risk_engine import check_and_enforce_risk_limits

router = APIRouter()

DbDep = Annotated[Session, Depends(get_db)]


@router.get("/status", response_model=RiskStatusResponse)
def get_risk_status(db: DbDep) -> RiskStatusResponse:
    """
    Compute and return the current risk status, including drawdown metrics.
    """
    # check_and_enforce_risk_limits returns a dict that matches the
    # RiskStatusResponse schema (config, equity, drawdown, last_event, etc.).
    return check_and_enforce_risk_limits(db)


@router.post("/force-liquidate")
def force_liquidate_all(db: DbDep) -> dict:
    """
    Manually close all open simulated follower positions.

    This is mainly intended for testing the risk pipeline and execution
    integration; it does not interact with any real exchanges.
    """
    closed_trades = close_all_positions(db)
    return {"closed_trades_count": len(closed_trades)}

