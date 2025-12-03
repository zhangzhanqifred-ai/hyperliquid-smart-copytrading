from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base


class TraderMetricsDaily(Base):
    """
    Daily aggregated performance metrics for a trader.
    """

    __tablename__ = "trader_metrics_daily"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    trader_id: Mapped[int] = mapped_column(ForeignKey("traders.id"), index=True, nullable=False)

    date: Mapped[date] = mapped_column(Date, nullable=False)

    pnl: Mapped[float] = mapped_column(Float, nullable=False)
    roi: Mapped[float] = mapped_column(Float, nullable=False)
    win_rate: Mapped[float] = mapped_column(Float, nullable=False)
    volatility: Mapped[float] = mapped_column(Float, nullable=False)
    max_drawdown: Mapped[float] = mapped_column(Float, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    trader: Mapped["Trader"] = relationship("Trader", back_populates="metrics_daily")


class SmartTraderUniverse(Base):
    """
    Smart trader universe table describing which traders currently pass filters.
    """

    __tablename__ = "smart_trader_universe"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    trader_id: Mapped[int] = mapped_column(ForeignKey("traders.id"), index=True, nullable=False)

    window_days: Mapped[int] = mapped_column(Integer, nullable=False)

    pnl_window: Mapped[float] = mapped_column(Float, nullable=False)
    win_rate_window: Mapped[float] = mapped_column(Float, nullable=False)
    volatility_window: Mapped[float] = mapped_column(Float, nullable=False)
    max_drawdown_window: Mapped[float] = mapped_column(Float, nullable=False)
    sharpe_window: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Additional behavioral / quality metrics for the trader within the window.
    num_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trades_per_day: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_win_r: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_loss_r: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    payoff_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    expectancy: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    min_trade_r: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_drawdown_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    filters_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    trader: Mapped["Trader"] = relationship("Trader", back_populates="smart_universe_entries")


