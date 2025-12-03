import sys
import os
from pathlib import Path

# Add backend directory to sys.path so we can import 'app'
backend_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(backend_dir))

from app.db import SessionLocal
from app.services.backtest_service import run_backtest
from app.schemas import BacktestRunCreate
from datetime import date
import traceback

try:
    db = SessionLocal()
    payload = BacktestRunCreate(
        start_date=date(2025, 11, 1),
        end_date=date(2025, 12, 2),
        params={
            'window_days': 30,
            'min_score': 0.0,
            'min_trades_per_day': 0.0,
            'strategy': {
                'time_window_seconds': 60,
                'price_range_width_pct': 0.01,
                'min_smart_traders': 1
            },
            'execution': {
                'notional_per_signal': 100,
                'initial_equity': 10000,
                'fee_rate_bps': 5
            }
        }
    )
    print("Running backtest...")
    run_backtest(db, payload)
    print("Success")
except Exception:
    traceback.print_exc()

