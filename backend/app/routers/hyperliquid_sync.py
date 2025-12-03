# app/routers/hyperliquid_sync.py

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.trader import Trader
from app.models.trade import Trade
from app.models.metrics import SmartTraderUniverse
from app.services.hyperliquid_client import HyperliquidClient
from app.services.metrics_service import compute_metrics_for_trader


router = APIRouter(prefix="/hyperliquid", tags=["hyperliquid"])


class HyperliquidSyncRequest(BaseModel):
    """
    请求体：
    - window_days: 从现在往前看多少天（用于 metrics 计算的窗口）
    - min_trades / limit: 预留给 list_active_traders，用不到可以先忽略
    - addresses: 如果提供，就按这些地址同步；否则才调用 client.list_active_traders()
    """
    window_days: int = 30
    min_trades: int = 0
    limit: int = 50
    addresses: Optional[List[str]] = None


class HyperliquidSyncResult(BaseModel):
    traders_synced: int
    trades_inserted: int


@router.post("/sync-traders", response_model=HyperliquidSyncResult)
def sync_traders_from_hyperliquid(
    payload: HyperliquidSyncRequest,
    db: Session = Depends(get_db),
) -> HyperliquidSyncResult:
    """
    从 Hyperliquid 拉取指定地址的成交，并写入本地 Trade 表，然后为每个 trader 计算一次指标。
    """

    client = HyperliquidClient()

    now = datetime.now(timezone.utc)
    start_time = now - timedelta(days=payload.window_days)

    # 优先使用请求中显式给出的地址
    if payload.addresses:
        candidates: List[dict[str, Any]] = [{"address": addr} for addr in payload.addresses]
    else:
        # 自动发现模式：从 leaderboard 或其他来源获取候选地址
        candidates = client.list_active_traders(
            window_days=payload.window_days,
            min_trades=payload.min_trades,
            limit=payload.limit,
        )
        print(f"[sync-traders] discovered {len(candidates)} candidate traders")

        if not candidates:
            print("[sync-traders] leaderboard returned no candidates, falling back to local DB")

            # 挑选最近 window_days 内 score 高的 trader
            # 这里的子查询用于找出符合窗口的 smart universe 记录，并按 score 排序
            subq = (
                db.query(SmartTraderUniverse)
                .filter(SmartTraderUniverse.window_days == payload.window_days)
                .order_by(SmartTraderUniverse.score.desc())
                .limit(payload.limit)
                .subquery()
            )

            # Join Trader 表获取地址
            rows = (
                db.query(Trader)
                .join(subq, Trader.id == subq.c.trader_id)
                .all()
            )

            candidates = [{"address": t.address} for t in rows]
            print(f"[sync-traders] local DB fallback -> {len(candidates)} traders")

    traders_synced = 0
    trades_inserted = 0

    for c in candidates:
        address = c["address"]

        # 1. 确保 Trader 记录存在
        trader = (
            db.query(Trader)
            .filter(Trader.address == address)
            .one_or_none()
        )
        if trader is None:
            trader = Trader(address=address)
            db.add(trader)
            db.commit()
            db.refresh(trader)

        # 2. 拉取成交
        fills = client.fetch_trades_for_trader(
            address=address,
            start_time=start_time,
            end_time=now,
        )

        print(f"[sync-traders] trader {address} got {len(fills)} normalized fills")

        # 3. 导入 Trade 表
        for i, f in enumerate(fills):
            # 从 fill 中获取 PnL，用于 metrics 计算 R
            closed_pnl = f.get("closed_pnl", 0.0)
            price = f["price"]
            size = f["size"]
            
            # 计算 notional 和近似 R
            # notional = abs(price * size)
            # 如果 notional > 0: r = closed_pnl / notional
            # 否则 r = 0.0
            # 我们这里主要确保 realized_pnl 被正确传递
            
            # 日志采样 (前5条)
            if i < 5:
                notional = abs(price * size)
                r_approx = closed_pnl / notional if notional > 0 else 0.0
                print(f"[hyperliquid_sync] sample trade r={r_approx}, closed_pnl={closed_pnl}, notional={notional}")

            trade = Trade(
                trader_id=trader.id,
                symbol=f["symbol"],
                side=f["side"],
                entry_price=price,
                size=size,
                opened_at=f["timestamp"],
                closed_at=f["timestamp"], # fills 视为瞬间完成
                
                # 核心：realized_pnl 必须非 None，metrics 才会统计
                realized_pnl=closed_pnl,
                
                raw_data={"note": "imported from hyperliquid fill", "fill_type": "raw", "closed_pnl": closed_pnl}
            )
            db.add(trade)
            trades_inserted += 1

        db.commit()

        # 4. 为这个 trader 计算一次指标
        compute_metrics_for_trader(
            db=db,
            trader_id=trader.id,
            window_days=payload.window_days,
        )

        traders_synced += 1

    return HyperliquidSyncResult(
        traders_synced=traders_synced,
        trades_inserted=trades_inserted,
    )
