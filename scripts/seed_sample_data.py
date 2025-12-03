from __future__ import annotations

"""
Seed the local SQLite database with sample traders and trades.

This is purely for development / demo purposes so that you can:
- Have a few example "smart money" addresses in the DB.
- See realistic metrics and selection results when calling the APIs.

Usage (from the project root directory):

    python -m scripts.seed_sample_data
"""

from datetime import datetime, timedelta
import random
from typing import Iterable

from sqlalchemy import func, select

from backend.app.db import Base, engine, SessionLocal
from backend.app.models import Trader, Trade  # noqa: F401  # ensure models are imported


def ensure_schema() -> None:
    """
    Make sure all tables exist.

    This calls Base.metadata.create_all(bind=engine), which is safe to run
    multiple times; it will only create missing tables and leave existing
    tables/data intact.
    """
    Base.metadata.create_all(bind=engine)


def create_sample_traders_if_missing() -> list[Trader]:
    """
    Create a few sample traders if none exist yet.

    Returns the list of all traders after seeding.
    """
    with SessionLocal() as db:
        count = db.scalar(select(func.count()).select_from(Trader)) or 0
        if count == 0:
            print("[seed] No traders found, creating sample traders...")
            traders: list[Trader] = [
                Trader(address="trader_A_demo"),
                Trader(address="trader_B_demo"),
                Trader(address="trader_C_demo"),
            ]
            db.add_all(traders)
            db.commit()
        else:
            print(f"[seed] Found {count} existing traders, not creating new ones.")

        all_traders = list(db.scalars(select(Trader)).all())
        return all_traders


def _generate_trades_for_trader_a(trader_id: int, num_trades: int) -> Iterable[Trade]:
    """
    Trader A: high win rate, but per-trade R is relatively small.

    We model this as:
    - Win rate ~ 75%
    - Winners: r in [0.3, 0.8]
    - Losers: r in [-0.5, -0.1]
    """
    return _generate_trades_for_pattern(
        trader_id=trader_id,
        num_trades=num_trades,
        win_rate=0.75,
        win_r_range=(0.3, 0.8),
        loss_r_range=(-0.5, -0.1),
    )


def _generate_trades_for_trader_b(trader_id: int, num_trades: int) -> Iterable[Trade]:
    """
    Trader B: moderate win rate, but large winners and small losers.

    This matches the "smart money" profile you prefer:
    - Win rate ~ 55%
    - Winners: r in [1.5, 3.0]
    - Losers: r in [-0.6, -0.2]
    """
    return _generate_trades_for_pattern(
        trader_id=trader_id,
        num_trades=num_trades,
        win_rate=0.55,
        win_r_range=(1.5, 3.0),
        loss_r_range=(-0.6, -0.2),
    )


def _generate_trades_for_pattern(
    *,
    trader_id: int,
    num_trades: int,
    win_rate: float,
    win_r_range: tuple[float, float],
    loss_r_range: tuple[float, float],
) -> Iterable[Trade]:
    """
    Generic trade generator for a given R-distribution pattern.

    本地 demo 环境中，我们为每笔交易随机生成一个相对收益 r，
    确保所有 trade 都“真的有盈亏”，方便回测看到非 0 的曲线。

    注意：
    - 这些随机 r 仅用于 demo/回测场景；
    - 真正接入 Hyperliquid 历史数据时，请用真实的 entry/exit 来计算 r。
    """
    now = datetime.utcnow()
    symbols = ["BTC", "ETH", "SOL", "DOGE"]
    sides = ["long", "short"]

    for i in range(num_trades):
        # Random open time within the last 30 days.
        days_ago = random.uniform(0, 30)
        open_time = now - timedelta(days=days_ago, hours=random.uniform(0, 23))
        # Close sometime after open, but still before "now".
        close_time = min(
            open_time + timedelta(hours=random.uniform(1, 48)),
            now,
        )

        symbol = random.choice(symbols)
        side = random.choice(sides)

        # Simple price / size model.
        entry_price = random.uniform(100.0, 110.0)
        size = random.uniform(0.5, 2.0)

        # Decide whether this trade is a "win" according to the requested win_rate.
        # 然后从一个对称区间中采样 r，保证 [-5%, +10%] 之间都有可能出现。
        is_win = random.random() < win_rate
        if is_win:
            # Winners: 0% ~ +10%
            r = random.uniform(0.0, 0.10)
        else:
            # Losers: -5% ~ 0%
            r = random.uniform(-0.05, 0.0)

        notional = entry_price * size
        # Back out realized_pnl and exit_price from r so that
        # r = realized_pnl / (entry_price * size) holds exactly.
        realized_pnl = r * notional

        # 对多头：r = (exit - entry) / entry => exit = entry * (1 + r)
        # 对空头：r = (entry - exit) / entry => exit = entry * (1 - r)
        if side == "long":
            exit_price = entry_price * (1 + r)
        else:
            exit_price = entry_price * (1 - r)

        yield Trade(
            trader_id=trader_id,
            symbol=symbol,
            side=side,
            size=size,
            entry_price=entry_price,
            exit_price=exit_price,
            realized_pnl=realized_pnl,
            opened_at=open_time,
            closed_at=close_time,
            raw_data={
                "note": "seeded sample trade (demo-only random r)",
                "pattern": "A" if win_rate > 0.6 else "B",
                "r": r,
            },
        )


def seed_trades_for_sample_traders(traders: list[Trader]) -> None:
    """
    Seed trades for at least two traders:
    - Trader A (first): high win rate, small R per trade.
    - Trader B (second): moderate win rate, large winners, small losers.
    """
    if not traders:
        print("[seed] No traders available to seed trades.")
        return

    with SessionLocal() as db:
        # Refresh from DB to get IDs (in case we were passed detached objects).
        db_traders = list(db.scalars(select(Trader)).all())
        if len(db_traders) < 2:
            print("[seed] Need at least 2 traders in DB to seed sample trades.")
            return

        trader_a = db_traders[0]
        trader_b = db_traders[1]

        print(f"[seed] Seeding trades for Trader A ({trader_a.address})...")
        trades_a = list(_generate_trades_for_trader_a(trader_a.id, num_trades=80))

        print(f"[seed] Seeding trades for Trader B ({trader_b.address})...")
        trades_b = list(_generate_trades_for_trader_b(trader_b.id, num_trades=80))

        db.add_all(trades_a + trades_b)
        db.commit()

        print(
            f"[seed] Inserted {len(trades_a)} trades for Trader A and "
            f"{len(trades_b)} trades for Trader B."
        )


def main() -> None:
    """
    Entry point for the seed script.

    Steps:
    1. Ensure DB schema exists.
    2. Create sample traders if needed.
    3. Seed realistic trade histories for at least two traders.
    """
    print("[seed] Ensuring database schema...")
    ensure_schema()

    print("[seed] Creating sample traders (if missing)...")
    traders = create_sample_traders_if_missing()

    print("[seed] Seeding trades for sample traders...")
    seed_trades_for_sample_traders(traders)

    print("[seed] Done.")


if __name__ == "__main__":
    main()


