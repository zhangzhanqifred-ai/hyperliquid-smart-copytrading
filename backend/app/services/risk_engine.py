from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.follower import FollowerTrade
from ..models import RiskConfig, RiskEvent

DEFAULT_INITIAL_EQUITY: float = 10000.0
DEFAULT_MAX_DRAWDOWN_PCT: float = 0.3


def _get_or_create_risk_config(db: Session) -> RiskConfig:
    """
    从数据库读取唯一一条 RiskConfig，如果不存在则创建一条默认配置。
    """
    config = db.scalar(select(RiskConfig).order_by(RiskConfig.created_at.desc()))
    if config is not None:
        return config

    config = RiskConfig(
        max_drawdown_pct=DEFAULT_MAX_DRAWDOWN_PCT,
        max_leverage_per_symbol=None,
        max_position_size_per_symbol=None,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


def compute_equity_and_drawdown(
    trades: list[FollowerTrade],
    initial_equity: float,
) -> tuple[float, float, float]:
    """
    根据 follower_trades 历史计算当前权益和最大回撤。

    简化逻辑：
    - 只看已经平仓且 realized_pnl 不为 None 的交易；
    - 按 closed_at 升序排序；
    - 从 initial_equity 开始累加 realized_pnl 得到 equity 序列；
    - 遍历 equity 序列，维护 peak（迄今为止最高权益），
      drawdown = peak - equity[i]，记录最大 drawdown；
    - max_drawdown_pct = max_drawdown_abs / initial_equity。
    """
    closed_trades = sorted(
        (t for t in trades if t.realized_pnl is not None and t.closed_at is not None),
        key=lambda t: t.closed_at or datetime.utcnow(),
    )

    equity = initial_equity
    peak_equity = initial_equity
    max_drawdown_abs = 0.0

    for trade in closed_trades:
        equity += trade.realized_pnl or 0.0
        if equity > peak_equity:
            peak_equity = equity

        drawdown = peak_equity - equity
        if drawdown > max_drawdown_abs:
            max_drawdown_abs = drawdown

    max_drawdown_pct = max_drawdown_abs / initial_equity if initial_equity > 0 else 0.0

    return equity, max_drawdown_abs, max_drawdown_pct


def check_and_enforce_risk_limits(db: Session) -> dict:
    """
    读取当前风控配置和交易历史，计算最大回撤并判断是否触发风控。

    行为：
    - 调用 `_get_or_create_risk_config` 读取/创建 RiskConfig；
    - 查询所有 FollowerTrade：
        * 已平仓的用于计算历史回撤；
        * 未平仓的当前版本忽略（未来可扩展为按 entry_price 估值）；
    - 使用 `compute_equity_and_drawdown` 得到 current_equity、max_drawdown_abs、max_drawdown_pct；
    - 判断 `risk_triggered = max_drawdown_pct >= config.max_drawdown_pct`；
    - 如果触发风控，则写入一条 RiskEvent(event_type='MAX_DRAWDOWN_HIT')；
    - 返回一个 dict，总结当前状态和最近一次 RiskEvent。
    """
    config = _get_or_create_risk_config(db)

    trades: list[FollowerTrade] = list(db.scalars(select(FollowerTrade)).all())

    current_equity, max_dd_abs, max_dd_pct = compute_equity_and_drawdown(
        trades=trades,
        initial_equity=DEFAULT_INITIAL_EQUITY,
    )

    risk_triggered = max_dd_pct >= config.max_drawdown_pct

    if risk_triggered:
        event = RiskEvent(
            event_type="MAX_DRAWDOWN_HIT",
            details={
                "current_equity": current_equity,
                "max_drawdown_abs": max_dd_abs,
                "max_drawdown_pct": max_dd_pct,
                "threshold": config.max_drawdown_pct,
            },
        )
        db.add(event)
        db.commit()

    last_event = db.scalar(select(RiskEvent).order_by(RiskEvent.created_at.desc()))

    return {
        "config": config,
        "current_equity": current_equity,
        "max_drawdown_abs": max_dd_abs,
        "max_drawdown_pct": max_dd_pct,
        "risk_triggered": risk_triggered,
        "last_event": last_event,
    }


