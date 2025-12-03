from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from ..models import Trader
from ..models.metrics import SmartTraderUniverse
from ..schemas import SmartTraderOut
from .metrics_service import compute_metrics_for_trader


def refresh_smart_universe(
    db: Session,
    window_days: int = 30,
    top_n: int = 20,
) -> dict:
    """
    Recompute metrics and selection for all traders and refresh the smart universe.

    Steps:
    1. Load all traders from `traders` table.
    2. For each trader, call `metrics_service.compute_metrics_for_trader`, which:
       - Computes all performance metrics.
       - Calls `selection_service.evaluate_trader_profile` to get eligible/score.
       - Updates the `smart_trader_universe` row for (trader_id, window_days).
    3. After the loop, query `smart_trader_universe` for:
       - matching window_days
       - eligible = True
       ordered by score descending, limited to `top_n`.
    4. Return a summary dict of this refresh run.
    """
    # 1) Fetch all traders.
    traders = list(db.scalars(select(Trader)).all())
    total_traders = len(traders)

    # 2) Recompute metrics for each trader.
    for trader in traders:
        compute_metrics_for_trader(db=db, trader_id=trader.id, window_days=window_days)

    # 3) Query eligible traders count.
    eligible_count = db.scalar(
        select(func.count())
        .select_from(SmartTraderUniverse)
        .where(
            SmartTraderUniverse.window_days == window_days,
            SmartTraderUniverse.eligible.is_(True),
        )
    ) or 0

    # 4) Fetch top-N eligible traders with their addresses and key metrics.
    stu_alias = aliased(SmartTraderUniverse)
    trader_alias = aliased(Trader)
    top_stmt = (
        select(stu_alias, trader_alias.address)
        .join(trader_alias, trader_alias.id == stu_alias.trader_id)
        .where(
            stu_alias.window_days == window_days,
            stu_alias.eligible.is_(True),
        )
        .order_by(stu_alias.score.desc())
        .limit(top_n)
    )

    rows = db.execute(top_stmt).all()
    top_traders: list[dict] = []
    for stu, address in rows:
        top_traders.append(
            {
                "trader_id": stu.trader_id,
                "address": address,
                "score": stu.score,
                "win_rate": stu.win_rate_window,
                "payoff_ratio": stu.payoff_ratio,
                "expectancy": stu.expectancy,
                "trades_per_day": stu.trades_per_day,
            }
        )

    return {
        "window_days": window_days,
        "total_traders": total_traders,
        "eligible_traders": eligible_count,
        "top_traders": top_traders,
    }


def list_smart_traders(
    db: Session,
    window_days: int = 30,
    min_score: Optional[float] = None,
    min_payoff_ratio: Optional[float] = None,
    min_trades_per_day: Optional[float] = None,
) -> list[SmartTraderOut]:
    """
    List smart traders from the universe with optional additional filters.

    We join `smart_trader_universe` with `traders` to obtain the human-readable
    address, filter on:
      - window_days
      - eligible = True
      - min_score / min_payoff_ratio / min_trades_per_day (if provided)
    and order by score descending.
    """
    stu_alias = aliased(SmartTraderUniverse)
    trader_alias = aliased(Trader)

    stmt = (
        select(stu_alias, trader_alias.address)
        .join(trader_alias, trader_alias.id == stu_alias.trader_id)
        .where(
            stu_alias.window_days == window_days,
            stu_alias.eligible.is_(True),
        )
    )

    if min_score is not None:
        stmt = stmt.where(stu_alias.score >= min_score)

    if min_payoff_ratio is not None:
        stmt = stmt.where(stu_alias.payoff_ratio >= min_payoff_ratio)

    if min_trades_per_day is not None:
        stmt = stmt.where(stu_alias.trades_per_day >= min_trades_per_day)

    stmt = stmt.order_by(stu_alias.score.desc())

    rows = db.execute(stmt).all()
    results: list[SmartTraderOut] = []
    for stu, address in rows:
        results.append(
            SmartTraderOut(
                trader_id=stu.trader_id,
                address=address,
                window_days=stu.window_days,
                score=stu.score,
                win_rate_window=stu.win_rate_window,
                pnl_window=stu.pnl_window,
                volatility_window=stu.volatility_window,
                max_drawdown_window=stu.max_drawdown_window,
                payoff_ratio=stu.payoff_ratio,
                expectancy=stu.expectancy,
                trades_per_day=stu.trades_per_day,
            )
        )

    return results


