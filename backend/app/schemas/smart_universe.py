from pydantic import BaseModel


class SmartTraderOut(BaseModel):
    """
    Public representation of a smart trader entry used by universe-related APIs.

    Most fields come directly from `smart_trader_universe`, combined with the
    human-readable `address` from the `traders` table.
    """

    trader_id: int
    address: str
    window_days: int

    score: float
    win_rate_window: float
    pnl_window: float
    volatility_window: float
    max_drawdown_window: float
    payoff_ratio: float
    expectancy: float
    trades_per_day: float


