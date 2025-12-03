from datetime import datetime

from pydantic import BaseModel


class TraderMetricsResult(BaseModel):
    """
    Aggregated metrics for a trader over a given lookback window.

    字段含义与 selection_service.TraderMetricsResult 中的 dataclass 对应，
    方便前端或命令行直接查看某个地址的完整画像。
    """

    pnl: float
    win_rate: float
    volatility: float
    max_drawdown: float

    num_trades: int
    active_days: int
    trades_per_day: float

    avg_win_r: float
    avg_loss_r: float
    payoff_ratio: float
    expectancy: float

    min_trade_r: float
    max_drawdown_pct: float
    # Whether this trader currently passes the smart selection filters for
    # the given window. This is computed in metrics_service / selection_service.
    eligible: bool = False
    # Composite score combining expectancy, payoff ratio, trading frequency,
    # and drawdown. Higher is better. None means score was not computed.
    score: float | None = None


class SmartTraderUniverseRead(BaseModel):
    id: int
    trader_id: int
    address: str
    window_days: int
    pnl_window: float
    win_rate_window: float
    volatility_window: float
    max_drawdown_window: float
    sharpe_window: float | None
    num_trades: int
    active_days: int
    trades_per_day: float
    avg_win_r: float
    avg_loss_r: float
    payoff_ratio: float
    expectancy: float
    min_trade_r: float
    max_drawdown_pct: float
    score: float
    eligible: bool
    filters_snapshot: dict
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SmartTraderUniverseListResponse(BaseModel):
    total: int
    items: list[SmartTraderUniverseRead]


class SmartTraderUniverseTopTrader(BaseModel):
    """
    Lightweight summary used when returning top-ranked smart traders.
    """

    trader_id: int
    address: str
    score: float


class SmartTraderUniverseRefreshResponse(BaseModel):
    """
    Response from /smart-universe/refresh endpoint.

    It tells you how many traders are currently eligible and returns the
    top-N addresses with the highest score so that you can quickly inspect
    the smart money pool.
    """

    window_days: int
    eligible_count: int
    top: list[SmartTraderUniverseTopTrader]
