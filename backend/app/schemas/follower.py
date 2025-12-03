from datetime import datetime

from pydantic import BaseModel


class FollowerTradeOut(BaseModel):
    """
    Public representation of a follower trade (simulated execution).

    Mirrors the main fields of the `FollowerTrade` ORM model so that you can
    inspect simulated positions via the API.
    """

    id: int
    signal_id: int | None

    symbol: str
    side: str

    size: float
    entry_price: float
    exit_price: float | None

    realized_pnl: float | None

    opened_at: datetime
    closed_at: datetime | None

    is_open: bool

    class Config:
        from_attributes = True


