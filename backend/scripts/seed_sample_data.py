from __future__ import annotations

"""
Seed the local database with a small amount of demo data.

This script is intentionally simple and focuses on generating:
- 2 demo traders (if the table is currently empty)
- 50–100 synthetic trades for each trader over the last 30 days

Usage (from the `backend` directory):

    cd backend
    python -m scripts.seed_sample_data
"""

from datetime import datetime, timedelta
import random

from sqlalchemy import func, select

from app.db import Base, engine, SessionLocal
from app.models import Trader, Trade  # type: ignore


# Ensure all tables exist before inserting data.
Base.metadata.create_all(bind=engine)


def seed() -> None:
    """
    Seed traders and trades if the database is currently empty.

    The generated trades roughly follow your specification:
    - symbol: "BTC"
    - side: random choice of "long" / "short"
    - entry_price: uniform in [90000, 95000]
    - size: uniform in [0.01, 0.1]
    - realized_pnl:
        * winners: +1% to +5% of entry_price * size
        * losers:  -0.5% to -2% of entry_price * size
    - opened_at: random timestamp in the last 30 days
    - closed_at: opened_at + a few minutes
    """
    with SessionLocal() as db:
        trader_count = db.scalar(select(func.count()).select_from(Trader)) or 0

        if trader_count == 0:
            print("[seed] traders table is empty, creating demo traders...")
            trader_a = Trader(address="demo_trader_A")
            trader_b = Trader(address="demo_trader_B")
            db.add_all([trader_a, trader_b])
            db.commit()
            db.refresh(trader_a)
            db.refresh(trader_b)
            traders = [trader_a, trader_b]
        else:
            print(f"[seed] Found {trader_count} traders, will not create new ones.")
            traders = list(db.scalars(select(Trader)).all())

        if not traders:
            print("[seed] No traders found; aborting trade generation.")
            return

        now = datetime.utcnow()

        for trader in traders[:2]:
            # For each of the first two traders, generate between 50 and 100 trades.
            num_trades = random.randint(50, 100)
            print(f"[seed] Generating {num_trades} trades for {trader.address}...")

            for _ in range(num_trades):
                # Random time within the last 30 days.
                days_ago = random.uniform(0, 30)
                opened_at = now - timedelta(
                    days=days_ago,
                    minutes=random.uniform(0, 60 * 24),
                )
                # Closed a few minutes after open.
                closed_at = opened_at + timedelta(minutes=random.uniform(5, 240))

                symbol = "BTC"
                side = random.choice(["long", "short"])
                entry_price = random.uniform(90000, 95000)
                size = random.uniform(0.01, 0.1)
                notional = entry_price * size

                # Randomly decide win or loss.
                is_win = random.random() < 0.6  # roughly 60% win rate
                if is_win:
                    pnl_pct = random.uniform(0.01, 0.05)  # +1% to +5%
                else:
                    pnl_pct = random.uniform(-0.02, -0.005)  # -2% to -0.5%

                realized_pnl = notional * pnl_pct

                trade = Trade(
                    trader_id=trader.id,
                    symbol=symbol,
                    side=side,
                    size=size,
                    entry_price=entry_price,
                    exit_price=entry_price,  # simple placeholder; backtest uses realized_pnl anyway
                    realized_pnl=realized_pnl,
                    opened_at=opened_at,
                    closed_at=closed_at,
                    raw_data={"note": "backend/scripts.seed_sample_data demo trade"},
                )
                db.add(trade)

        db.commit()
        print("[seed] Done seeding demo traders and trades.")


if __name__ == "__main__":
    seed()


