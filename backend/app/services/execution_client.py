from abc import ABC, abstractmethod
from typing import Protocol, Literal, List, Dict, Optional
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.follower import FollowerTrade

Side = Literal["long", "short"]

class ExecutionClient(ABC):
    """
    Unified execution client interface.
    Future implementations:
      - Simulated Execution (Write to DB)
      - Hyperliquid Real Trading
      - Binance Real Trading
    """

    @abstractmethod
    def open_position(
        self,
        *,
        symbol: str,
        side: Side,
        notional: float,
        price: float | None = None,
        signal_id: int | None = None,
        timestamp: datetime | None = None,
    ) -> int:
        """
        Open a position, return internal follower_trade_id (or external order_id).
        """
        raise NotImplementedError

    @abstractmethod
    def close_position(
        self,
        *,
        follower_trade_id: int,
        price: float | None = None,
        timestamp: datetime | None = None,
    ) -> None:
        """
        Close an existing position.
        """
        raise NotImplementedError

    @abstractmethod
    def get_open_positions(self) -> list[dict]:
        """
        Return all currently open positions.
        """
        raise NotImplementedError


class SimulatedExecutionClient(ExecutionClient):
    def __init__(self, db: Session):
        self.db = db

    def open_position(
        self,
        *,
        symbol: str,
        side: Side,
        notional: float,
        price: float | None = None,
        signal_id: int | None = None,
        timestamp: datetime | None = None,
    ) -> int:
        # Determine opened_at: use provided timestamp or current UTC time
        opened_at = timestamp if timestamp else datetime.now(timezone.utc)
        
        # Simplified: use notional as size directly for now
        trade = FollowerTrade(
            symbol=symbol,
            side=side,
            size=notional, # Mapping notional to size as per request/logic
            entry_price=price if price is not None else 0.0, # execution_service uses (min+max)/2, here we expect caller to provide price
            opened_at=opened_at,
            is_open=True, # Using is_open based on FollowerTrade model
            signal_id=signal_id,
            realized_pnl=0.0
        )
        # Note: FollowerTrade model has 'size', 'entry_price', 'is_open' (boolean)
        # User prompt used 'notional', 'status'. I adapted to actual model:
        # size=notional, is_open=True.
        
        self.db.add(trade)
        self.db.commit()
        self.db.refresh(trade)
        return trade.id

    def close_position(
        self,
        *,
        follower_trade_id: int,
        price: float | None = None,
        timestamp: datetime | None = None,
    ) -> None:
        trade = self.db.get(FollowerTrade, follower_trade_id)
        if not trade or not trade.is_open:
            return

        closed_at = timestamp if timestamp else datetime.now(timezone.utc)
        exit_price = price or trade.entry_price
        
        realized_pnl = 0.0
        if exit_price and trade.entry_price:
            if trade.side == "long":
                realized_pnl = (exit_price - trade.entry_price) * trade.size
            else:
                realized_pnl = (trade.entry_price - exit_price) * trade.size
        
        # Adjust for fee? The user prompt didn't include fee in the snippet, 
        # but backtest_service does. I'll stick to the snippet for now.

        trade.exit_price = exit_price
        trade.closed_at = closed_at
        trade.realized_pnl = realized_pnl
        trade.is_open = False

        self.db.add(trade)
        self.db.commit()

    def get_open_positions(self) -> list[dict]:
        q = (
            self.db.query(FollowerTrade)
            .filter(FollowerTrade.is_open.is_(True))
            .all()
        )
        return [
            {
                "id": t.id,
                "symbol": t.symbol,
                "side": t.side,
                "entry_price": t.entry_price,
                "notional": t.size,
                "opened_at": t.opened_at,
            }
            for t in q
        ]


class HyperliquidExecutionClient(ExecutionClient):
    """
    Reserved for future Hyperliquid real trading implementation.
    """

    def __init__(self, api_key: str, api_secret: str, base_url: str = "TODO"):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url

    def open_position(
        self,
        *,
        symbol: str,
        side: Side,
        notional: float,
        price: float | None = None,
        signal_id: int | None = None,
        timestamp: datetime | None = None,
    ) -> int:
        raise NotImplementedError

    def close_position(
        self,
        *,
        follower_trade_id: int,
        price: float | None = None,
        timestamp: datetime | None = None,
    ) -> None:
        raise NotImplementedError

    def get_open_positions(self) -> list[dict]:
        raise NotImplementedError

