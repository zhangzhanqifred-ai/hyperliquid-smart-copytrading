from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Dict

import requests
from hyperliquid.info import Info
from hyperliquid.utils import constants


class HyperliquidClient:
    """
    Thin wrapper around the official hyperliquid-python-sdk Info client.

    目前先只用来拉取某个地址在时间区间内的成交明细（user_fills_by_time），
    后续再扩展成 leaderboard / 账户状态等。
    """

    def __init__(self, use_testnet: bool = False) -> None:
        self.base_url = constants.TESTNET_API_URL if use_testnet else constants.MAINNET_API_URL
        # 关闭 websocket，只用 HTTP
        self.info = Info(self.base_url, skip_ws=True)

    def list_active_traders(
        self,
        *,
        window_days: int,
        min_trades: int,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        返回一批“候选聪明钱”地址。
        """
        url = self.base_url + "/info"

        # 这里是示例结构，真实字段名请根据 Hyperliquid 文档 / SDK 源码调整
        payload = {
            "type": "leaderboard",
            "window": "30d", # 尝试匹配 30 天窗口
            # "n": limit, # API 可能不支持 n/limit 参数，或者名字不同
        }

        try:
            # Timeout 设短一点，避免阻塞
            resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
            
            print(f"[HyperliquidClient] leaderboard status={resp.status_code}")
            # 关键：一定要打印 resp.text，不要只打印“Failed to deserialize”
            # 这样才能看到 Hyperliquid 真正返回的错误提示
            if resp.status_code != 200:
                print(f"[HyperliquidClient] leaderboard raw body={resp.text}")
            
            resp.raise_for_status()
            data = resp.json()
            
            candidates: list[dict[str, Any]] = []
            
            # 假设 data 是 list 或者是 {"leaderboardRows": [...]} 结构
            rows = data.get("leaderboardRows", []) if isinstance(data, dict) else data
            
            if isinstance(rows, list):
                for row in rows:
                    # 尝试适配不同的字段名
                    addr = row.get("user") or row.get("address") or row.get("ethAddress")
                    if not addr:
                        continue
                    
                    candidates.append({
                        "address": addr,
                        "approx_pnl": float(row.get("pnl", 0.0)),
                        "approx_num_trades": int(row.get("numTrades", 0)),
                    })

            print(f"[HyperliquidClient] leaderboard returned {len(candidates)} leaders")
            return candidates[:limit]

        except Exception as e:
            print(f"[HyperliquidClient] leaderboard REST call failed: {e}")
            # 暂时先返回空，后面用 DB 降级方案补上
            return []

    def fetch_trades_for_trader(
        self,
        *,
        address: str,
        start_time: datetime,
        end_time: datetime,
    ) -> List[Dict[str, Any]]:
        """
        极简版本：从官方 SDK 拉 fills，只要基础字段齐全就返回，不做任何基于 PnL 的过滤。
        """

        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)

        start_ms = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)

        try:
            fills = self.info.user_fills_by_time(address, start_ms, end_ms)
        except Exception as e:
            print(f"[HyperliquidClient] user_fills_by_time error for {address}: {e}")
            return []

        if not fills:
            print(f"[HyperliquidClient] no fills for {address} between {start_ms} and {end_ms}")
            return []

        result: List[Dict[str, Any]] = []
        print(f"[HyperliquidClient] fetched {len(fills)} raw fills for {address}")

        for f in fills:
            try:
                symbol = f.get("coin")
                price_str = f.get("px")
                size_str = f.get("sz")
                ts_ms = f.get("time")

                # side: 部分环境是 "B"/"S"，也有可能是通过 dir 表示方向
                side_raw = f.get("side") or f.get("dir")

                # 只有在缺少“绝对必要字段”时才跳过
                if symbol is None or price_str is None or size_str is None or ts_ms is None:
                    print(f"[HyperliquidClient] skip fill with missing core fields: {f}")
                    continue

                price = float(price_str)
                size = float(size_str)
                ts_dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)

                if side_raw in ("B", "Buy", "Open Long", "Close Short"):
                    side = "long"
                elif side_raw in ("S", "Sell", "Open Short", "Close Long"):
                    side = "short"
                else:
                    # 如果拿不到方向，就默认当作 long，后面有需要再细化
                    side = "long"
                
                # 尝试获取 closedPnl，没有则为 0.0
                closed_pnl_str = f.get("closedPnl")
                closed_pnl = float(closed_pnl_str) if closed_pnl_str is not None else 0.0

                result.append(
                    {
                        "symbol": symbol,
                        "side": side,
                        "price": price,
                        "size": size,
                        "timestamp": ts_dt,
                        "closed_pnl": closed_pnl,
                    }
                )
            except Exception as parse_err:
                print(f"[HyperliquidClient] parse fill error for {address}: {parse_err} | raw={f}")
                continue

        print(f"[HyperliquidClient] normalized {len(result)} fills for {address}")
        return result
