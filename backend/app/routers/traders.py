from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Trader
from ..models.metrics import SmartTraderUniverse, TraderMetricsDaily
from ..schemas import (
    TraderCreate,
    TraderRead,
    TraderListResponse,
    TraderMetricsResult,
)
from ..services.metrics_service import compute_metrics_for_trader

router = APIRouter()

DbDep = Annotated[Session, Depends(get_db)]


@router.post("", response_model=TraderRead)
def create_or_update_trader(payload: TraderCreate, db: DbDep) -> Trader:
    """
    Create a new trader by address or return the existing one.

    Later you might extend this to update additional metadata about the trader.
    """
    stmt = select(Trader).where(Trader.address == payload.address)
    trader = db.scalar(stmt)
    if trader is None:
        trader = Trader(address=payload.address)
        db.add(trader)
        db.commit()
        db.refresh(trader)
    return trader


@router.get("", response_model=TraderListResponse)
def list_traders(
    db: DbDep,
    skip: int = Query(0, ge=0, description="Number of records to skip (for pagination)"),
    limit: int = Query(50, ge=1, le=200, description="Max records to return"),
) -> TraderListResponse:
    """
    List traders with simple offset-based pagination.
    """
    total = db.scalar(select(func.count()).select_from(Trader)) or 0
    items = db.scalars(select(Trader).offset(skip).limit(limit)).all()
    return TraderListResponse(total=total, items=items)


@router.post(
    "/{trader_id}/compute-metrics",
    response_model=TraderMetricsResult,
    summary="Recompute metrics for a trader over a given window",
)
def compute_metrics_for_trader_endpoint(
    trader_id: int,
    db: DbDep,
    window_days: int = Query(30, ge=1, description="Lookback window in days"),
) -> TraderMetricsResult:
    """
    Trigger a recomputation of metrics for a single trader.

    Internally this calls `metrics_service.compute_metrics_for_trader`, which
    also updates the `smart_trader_universe` row for (trader_id, window_days).
    We then read back the latest universe entry and expose a friendly
    `TraderMetricsResult` JSON for inspection.
    """
    trader = db.get(Trader, trader_id)
    if trader is None:
        raise HTTPException(status_code=404, detail="Trader not found")

    # Compute metrics, refresh smart_trader_universe and return the full profile,
    # including `eligible` and `score` from the selection engine.
    return compute_metrics_for_trader(db=db, trader_id=trader_id, window_days=window_days)


@router.get(
    "/{trader_id}/metrics",
    response_model=TraderMetricsResult,
    summary="Get latest metrics snapshot for a trader",
)
def get_trader_metrics(
    trader_id: int,
    db: DbDep,
    window_days: int = Query(30, ge=1, description="Lookback window in days"),
) -> TraderMetricsResult:
    """
    Get the latest metrics snapshot for a trader over a given window.

    We read:
    - The most recent `smart_trader_universe` entry for (trader_id, window_days),
      which contains the aggregated metrics and selection results for that
      window.
    - The most recent `trader_metrics_daily` entry for this trader. Right now
      we only load it for potential future use (e.g. exposing daily stats), but
      the response is fully derived from `smart_trader_universe` so that the
      schema stays simple.
    """
    trader = db.get(Trader, trader_id)
    if trader is None:
        raise HTTPException(status_code=404, detail="Trader not found")

    stu = db.scalar(
        select(SmartTraderUniverse)
        .where(
            SmartTraderUniverse.trader_id == trader_id,
            SmartTraderUniverse.window_days == window_days,
        )
        .order_by(SmartTraderUniverse.updated_at.desc())
    )
    if stu is None:
        raise HTTPException(
            status_code=404,
            detail="No metrics found for this trader and window_days. "
            "Try calling /traders/{trader_id}/compute-metrics first.",
        )

    # Optional: load most recent daily metrics; currently not used in the
    # response but may be helpful for future extensions.
    _latest_daily = db.scalar(
        select(TraderMetricsDaily)
        .where(TraderMetricsDaily.trader_id == trader_id)
        .order_by(TraderMetricsDaily.date.desc())
    )

    return TraderMetricsResult(
        pnl=stu.pnl_window,
        win_rate=stu.win_rate_window,
        volatility=stu.volatility_window,
        max_drawdown=stu.max_drawdown_window,
        num_trades=stu.num_trades,
        active_days=stu.active_days,
        trades_per_day=stu.trades_per_day,
        avg_win_r=stu.avg_win_r,
        avg_loss_r=stu.avg_loss_r,
        payoff_ratio=stu.payoff_ratio,
        expectancy=stu.expectancy,
        min_trade_r=stu.min_trade_r,
        max_drawdown_pct=stu.max_drawdown_pct,
        eligible=stu.eligible,
        score=stu.score,
    )
