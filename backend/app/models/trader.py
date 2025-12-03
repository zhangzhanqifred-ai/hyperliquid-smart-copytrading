from datetime import datetime

from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base


class Trader(Base):
    """
    Represents a single trader address on Hyperliquid (or other exchanges).
    """

    __tablename__ = "traders"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    address: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    trades: Mapped[list["Trade"]] = relationship(
        "Trade", back_populates="trader", cascade="all, delete-orphan"
    )
    metrics_daily: Mapped[list["TraderMetricsDaily"]] = relationship(
        "TraderMetricsDaily", back_populates="trader", cascade="all, delete-orphan"
    )
    smart_universe_entries: Mapped[list["SmartTraderUniverse"]] = relationship(
        "SmartTraderUniverse", back_populates="trader", cascade="all, delete-orphan"
    )


