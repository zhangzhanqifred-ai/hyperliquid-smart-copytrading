from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import SmartTraderOut
from ..services.universe_service import refresh_smart_universe, list_smart_traders

router = APIRouter(prefix="/smart-universe", tags=["smart-universe"])

DbDep = Annotated[Session, Depends(get_db)]


@router.post("/refresh")
def refresh_smart_universe_endpoint(
    db: DbDep,
    window_days: int = Query(30, ge=1, description="Lookback window in days"),
) -> dict:
    """
    Recompute metrics and update the smart trader universe for all traders.

    This endpoint is typically called manually (e.g. via CLI or admin UI) when
    you want to refresh the \"smart money\" pool in bulk.
    """
    return refresh_smart_universe(db=db, window_days=window_days)


@router.get("", response_model=list[SmartTraderOut])
def list_smart_universe_endpoint(
    db: DbDep,
    window_days: int = Query(30, ge=1, description="Lookback window in days"),
    min_score: float | None = Query(
        None,
        description="Minimum composite score required to include a trader.",
    ),
    min_payoff_ratio: float | None = Query(
        None,
        description="Minimum payoff ratio required to include a trader.",
    ),
    min_trades_per_day: float | None = Query(
        None,
        description="Minimum trades per day required to include a trader.",
    ),
) -> list[SmartTraderOut]:
    """
    List smart traders from the current universe for a given window.

    You can optionally filter by minimum score, payoff ratio, and trading
    frequency. Results are ordered by score descending.
    """
    return list_smart_traders(
        db=db,
        window_days=window_days,
        min_score=min_score,
        min_payoff_ratio=min_payoff_ratio,
        min_trades_per_day=min_trades_per_day,
    )
