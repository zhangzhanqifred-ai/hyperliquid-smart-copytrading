from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import BacktestRun
from ..schemas import BacktestRunCreate, BacktestRunListResponse, BacktestRunOut, BacktestRunDetail
from ..services.backtest_service import run_backtest, DEFAULT_INITIAL_EQUITY

router = APIRouter()

DbDep = Annotated[Session, Depends(get_db)]


def _to_backtest_out(run: BacktestRun) -> BacktestRunOut:
    """
    Helper to map a BacktestRun ORM object plus its summary JSON into the
    public BacktestRunOut schema.
    """
    summary = run.summary or {}
    params = run.params or {}

    initial_equity = float(summary.get("initial_equity", DEFAULT_INITIAL_EQUITY))
    final_equity = float(summary.get("final_equity", initial_equity))
    total_return_pct = float(summary.get("total_return_pct", 0.0))
    max_drawdown_pct = float(summary.get("max_drawdown_pct", 0.0))
    total_trades = int(summary.get("total_trades", 0))
    win_rate = float(summary.get("win_rate", 0.0))

    return BacktestRunOut(
        id=run.id,
        created_at=run.created_at,
        start_date=run.start_date,
        end_date=run.end_date,
        name=params.get("name"),
        description=params.get("description"),
        initial_equity=initial_equity,
        final_equity=final_equity,
        total_return_pct=total_return_pct,
        max_drawdown_pct=max_drawdown_pct,
        total_trades=total_trades,
        win_rate=win_rate,
    )


def _to_backtest_detail(run: BacktestRun) -> BacktestRunDetail:
    """
    Helper to map a BacktestRun ORM object into the detailed view.
    """
    base = _to_backtest_out(run)
    summary = run.summary or {}
    
    # Extract the detailed fields from the summary JSON
    equity_curve = summary.get("equity_curve", [])
    virtual_trades = summary.get("virtual_trades", [])
    params_snapshot = summary.get("params_snapshot", run.params or {})

    return BacktestRunDetail(
        **base.model_dump(),
        equity_curve=equity_curve,
        trades_summary=virtual_trades,
        params_snapshot=params_snapshot,
    )


@router.get("", response_model=BacktestRunListResponse)
def list_backtests(
    db: DbDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> BacktestRunListResponse:
    """
    List recent backtest runs (most recent first).
    """
    total = db.scalar(select(func.count()).select_from(BacktestRun)) or 0
    runs = db.scalars(
        select(BacktestRun).order_by(BacktestRun.created_at.desc()).offset(skip).limit(limit)
    ).all()

    items = [_to_backtest_out(run) for run in runs]
    return BacktestRunListResponse(total=total, items=items)


@router.get("/{backtest_id}", response_model=BacktestRunDetail)
def get_backtest_detail(
    backtest_id: int,
    db: DbDep,
) -> BacktestRunDetail:
    """
    Get full details of a specific backtest run, including equity curve and trade list.
    """
    run = db.get(BacktestRun, backtest_id)
    if not run:
        raise HTTPException(status_code=404, detail="Backtest not found")
    
    return _to_backtest_detail(run)


@router.post("", response_model=BacktestRunOut)
def create_backtest(
    payload: BacktestRunCreate,
    db: DbDep,
) -> BacktestRunOut:
    """
    Launch a new backtest run and return its summary.
    """
    run = run_backtest(db=db, payload=payload)
    return _to_backtest_out(run)
