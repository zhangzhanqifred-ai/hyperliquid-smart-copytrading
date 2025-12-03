from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SignalRead(BaseModel):
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


class TradeEvent(BaseModel):
    """
    A single fill / trade event from a smart-money or normal address,
    used as input to the strategy engine.

    In the future this can be constructed from WebSocket / REST feeds,
    and is also convenient for offline backtesting / debugging.
    """

    trader_address: str = Field(..., description="交易地址（钱包地址或唯一标识）")
    symbol: str = Field(..., description="交易标的，例如 BTC-PERP 或 BTC")
    side: Literal["long", "short"] = Field(..., description="多头或空头方向")
    price: float = Field(..., gt=0, description="成交价格")
    size: float = Field(..., gt=0, description="成交数量或合约张数")
    timestamp: datetime = Field(..., description="事件发生时间（成交时间）")


class StrategyConfig(BaseModel):
    """
    Strategy parameters for aggregating smart-money trades into signals.

    默认参数针对日内短线策略做了一个相对保守的设定，你可以在 API 层或配置中
    调整这些值来适配不同的品种和周期。
    """

    # Time window in which we aggregate trade events (in seconds).
    time_window_seconds: int = 300

    # Price band configuration: you can use either percentage or absolute width.
    # If both are provided, percentage (pct) will normally take precedence.
    # Here we use a wider 1% band by default to make testing easier.
    price_range_width_pct: float | None = 0.01  # 1% 价格带，便于测试
    price_range_width_abs: float | None = None  # 绝对价格带，例如 50 USDT

    # Minimum number of distinct smart traders required to trigger a signal.
    # During early testing we set this to 1 so that a single smart address can
    # already generate signals and help validate the engine.
    min_smart_traders: int = 1

    # Debounce configuration to avoid repeated signals for the same pattern
    # in a very short time window. Also relaxed for testing.
    min_signal_interval_seconds: int = 1

