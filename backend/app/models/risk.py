from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class RiskConfig(Base):
    """
    Current risk configuration for the strategy.
    """

    __tablename__ = "risk_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    max_drawdown_pct: Mapped[float] = mapped_column(Float, nullable=False)
    max_leverage_per_symbol: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_position_size_per_symbol: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class RiskEvent(Base):
    """
    Logged risk events, such as hitting maximum drawdown.
    """

    __tablename__ = "risk_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)


