from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Deque, Dict, Optional, Set, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Signal, Trader
from ..models.metrics import SmartTraderUniverse
from ..schemas.signal import StrategyConfig, TradeEvent


# In-memory event buffers keyed by (symbol, side) -> deque of recent TradeEvent
_EVENT_BUFFERS: Dict[Tuple[str, str], Deque[TradeEvent]] = defaultdict(deque)

# Last signal timestamp per (symbol, side) key for debouncing.
_LAST_SIGNAL_TS: Dict[Tuple[str, str], datetime] = {}


def _get_price_range(event: TradeEvent, config: StrategyConfig) -> tuple[float, float]:
    """
    Compute the price band [price_min, price_max] around the event price.

    Priority:
    - If `price_range_width_pct` is set: use percentage band around price.
    - Else if `price_range_width_abs` is set: use absolute band.
    - Else: fall back to a zero-width band (exact price match).
    """
    if config.price_range_width_pct is not None:
        half_width = event.price * (config.price_range_width_pct / 2.0)
        price_min = event.price - half_width
        price_max = event.price + half_width
    elif config.price_range_width_abs is not None:
        half_width = config.price_range_width_abs / 2.0
        price_min = event.price - half_width
        price_max = event.price + half_width
    else:
        price_min = price_max = event.price

    return price_min, price_max


def process_trade_event(
    db: Session,
    event: TradeEvent,
    config: StrategyConfig,
) -> Optional[Signal]:
    """
    Process a single trade event and optionally generate a follow-trade signal.

    High-level flow:
    1. Check whether the trader address is currently in the smart universe
       (eligible == True). If not, ignore the event.
    2. Append the event to the in-memory buffer for (symbol, side) and evict
       any events older than `time_window_seconds`.
    3. Within the current buffer, count distinct smart trader addresses whose
       trades lie inside the dynamic price band around the current event.
    4. If the count >= `min_smart_traders` and we are past the debounce window,
       create and persist a new `Signal` ORM object and return it.
    """
    # --- Step 1: Check if the address is currently a smart trader ---
    smart_row = db.scalar(
        select(SmartTraderUniverse)
        .join(Trader, Trader.id == SmartTraderUniverse.trader_id)
        .where(
            Trader.address == event.trader_address,
            SmartTraderUniverse.eligible.is_(True),
        )
    )

    if smart_row is None:
        # Not in the current smart trader universe; ignore this event.
        return None

    # --- Step 2: Update buffer for (symbol, side) ---
    key = (event.symbol, event.side)
    buf = _EVENT_BUFFERS[key]

    buf.append(event)

    cutoff = event.timestamp - timedelta(seconds=config.time_window_seconds)
    while buf and buf[0].timestamp < cutoff:
        buf.popleft()

    # --- Step 3: Count distinct smart trader addresses within price band ---
    price_min, price_max = _get_price_range(event, config)

    smart_addresses: Set[str] = set()
    for e in buf:
        # We only ever insert events from smart addresses into the buffer,
        # so here we just need to check price band and direction.
        if price_min <= e.price <= price_max and e.symbol == event.symbol and e.side == event.side:
            smart_addresses.add(e.trader_address)

    smart_count = len(smart_addresses)

    # --- Step 4: Check threshold and debounce ---
    if smart_count < config.min_smart_traders:
        return None

    last_ts = _LAST_SIGNAL_TS.get(key)
    if last_ts is not None:
        delta = (event.timestamp - last_ts).total_seconds()
        if delta < config.min_signal_interval_seconds:
            # Too soon since last signal for this (symbol, side); debounce.
            return None

    # --- Step 5: Create and persist Signal ---
    signal = Signal(
        symbol=event.symbol,
        side=event.side,
        price_range_min=price_min,
        price_range_max=price_max,
        smart_trader_count=smart_count,
        trader_addresses=list(smart_addresses),
        signal_strength=float(smart_count),
        executed=False,
        created_at=event.timestamp,
    )

    db.add(signal)
    db.commit()
    db.refresh(signal)

    _LAST_SIGNAL_TS[key] = event.timestamp

    return signal
