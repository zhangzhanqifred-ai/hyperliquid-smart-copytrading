from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base


class FollowerTrade(Base):
    """
    Records our own follow-trade executions (simulated execution layer).

    One Signal can correspond to zero or many FollowerTrade rows.
    For now we only model simple one-leg open/close positions.
    """

    __tablename__ = "follower_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    signal_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("signals.id"), nullable=True, index=True
    )

    symbol: Mapped[str] = mapped_column(String, index=True, nullable=False)
    side: Mapped[str] = mapped_column(String, nullable=False)  # "long" / "short"

    # Position size (contract size or coin amount, depending on the venue).
    size: Mapped[float] = mapped_column(Float, nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)

    realized_pnl: Mapped[float | None] = mapped_column(Float, nullable=True)

    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    is_open: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    # To support partial exits based on specific smart trader moves
    source_signal_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_trader_address: Mapped[str | None] = mapped_column(String, nullable=True)

    signal: Mapped["Signal"] = relationship("Signal", back_populates="follower_trades")


