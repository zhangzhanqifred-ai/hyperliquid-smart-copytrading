from datetime import datetime

from pydantic import BaseModel


class SignalOut(BaseModel):
    """
    Public representation of a trading signal returned by the API.

    Mirrors the main fields of the `Signal` ORM model.
    """

    id: int
    created_at: datetime
    symbol: str
    side: str
    price_range_min: float
    price_range_max: float
    smart_trader_count: int
    trader_addresses: list[str]
    signal_strength: float | None
    executed: bool
    executed_at: datetime | None

    class Config:
        from_attributes = True


