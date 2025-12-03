from datetime import datetime

from pydantic import BaseModel


class RiskConfigRead(BaseModel):
    id: int
    max_drawdown_pct: float
    max_leverage_per_symbol: float | None
    max_position_size_per_symbol: float | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RiskEventRead(BaseModel):
    id: int
    created_at: datetime
    event_type: str
    details: dict | None

    class Config:
        from_attributes = True


class RiskStatusResponse(BaseModel):
    """
    Aggregated view of the current risk configuration and drawdown state.
    """

    config: RiskConfigRead
    current_equity: float
    max_drawdown_abs: float
    max_drawdown_pct: float
    risk_triggered: bool
    last_event: RiskEventRead | None

