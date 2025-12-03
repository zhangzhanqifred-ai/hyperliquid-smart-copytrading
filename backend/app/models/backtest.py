from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class BacktestRun(Base):
    """
    Represents a single backtest run with parameters and aggregated results.
    """

    __tablename__ = "backtest_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True
    )

    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Free-form params JSON containing strategy / universe / execution configs.
    params: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Optional human-friendly metadata.
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Aggregated summary metrics for quick listing / filtering.
    total_pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_drawdown: Mapped[float | None] = mapped_column(Float, nullable=True)
    win_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    sharpe: Mapped[float | None] = mapped_column(Float, nullable=True)

    # More detailed summary payload, including equity curve and per-trade stats.
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)

