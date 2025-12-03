from dataclasses import dataclass

from pydantic import BaseModel

from ..schemas import TraderMetricsResult


class SmartSelectionConfig(BaseModel):
    """
    Configuration for hard filters and scoring of smart traders.

    你可以在这里调整你对“聪明钱”的画像要求：
    - min_trades / min_active_days: 至少要有多少样本和活跃天数；
    - min_payoff_ratio: 平均盈利单 / 平均亏损单 的最小倍数；
    - min_expectancy: 每笔交易期望 R 值的下限；
    - max_drawdown_pct: 接受的最大回撤（0.35 表示 35%）；
    - min_trades_per_day: 交易频率过低的地址会被过滤掉；
    - max_single_loss_r: 单笔最大可接受亏损的 R；
    - target_*: 用于把指标归一化为 [0,1] 的目标值，方便打分。
    """

    window_days: int = 30
    min_trades: int = 200
    min_active_days: int = 5
    min_trades_per_day: float = 5.0
    min_expectancy: float = 0.01
    min_payoff_ratio: float = 1.5
    max_drawdown_pct: float = 0.3
    min_score: float = 0.7
    max_single_loss_r: float = 2.0  # Relaxed check

    target_expectancy: float = 0.02
    target_payoff: float = 2.5
    target_trades_per_day: float = 10.0


@dataclass
class TraderSelectionResult:
    """Result of applying selection rules to a trader profile."""

    eligible: bool
    score: float


DEFAULT_CONFIG = SmartSelectionConfig()


def clamp(value: float, minimum: float, maximum: float) -> float:
    """
    Clamp a value into [minimum, maximum].

    This is used to make sure each component stays within [0, 1] before
    we combine them into a final score.
    """
    if value < minimum:
        return minimum
    if value > maximum:
        return maximum
    return value


def evaluate_trader_profile(
    metrics: TraderMetricsResult,
    config: SmartSelectionConfig = DEFAULT_CONFIG,
) -> TraderSelectionResult:
    """
    Evaluate whether a trader passes selection rules and compute a score.

    逻辑：
    1. 硬过滤（hard filters）：
       - num_trades >= min_trades
       - active_days >= min_active_days
       - payoff_ratio >= min_payoff_ratio
       - expectancy > min_expectancy
       - max_drawdown_pct <= max_drawdown_pct
       - trades_per_day >= min_trades_per_day
       - min_trade_r >= -max_single_loss_r
       任意条件不满足 => eligible = False, score = 0.

    2. 打分（score），在通过硬过滤的前提下：
         E_component = clamp(expectancy / target_expectancy, 0, 1)
         P_component = clamp(payoff_ratio / target_payoff, 0, 1)
         F_component = clamp(trades_per_day / target_trades_per_day, 0, 1)
         D_component = clamp(1 - max_drawdown_pct / config.max_drawdown_pct, 0, 1)

       最终：
         score = 0.4 * E_component
               + 0.3 * P_component
               + 0.2 * F_component
               + 0.1 * D_component
    """

    # --- Hard filters ---
    if metrics.num_trades < config.min_trades:
        return TraderSelectionResult(eligible=False, score=0.0)

    if metrics.active_days < config.min_active_days:
        return TraderSelectionResult(eligible=False, score=0.0)

    if metrics.payoff_ratio < config.min_payoff_ratio:
        return TraderSelectionResult(eligible=False, score=0.0)

    if metrics.expectancy <= config.min_expectancy:
        return TraderSelectionResult(eligible=False, score=0.0)

    if metrics.max_drawdown_pct > config.max_drawdown_pct:
        return TraderSelectionResult(eligible=False, score=0.0)

    if metrics.trades_per_day < config.min_trades_per_day:
        return TraderSelectionResult(eligible=False, score=0.0)

    # Relaxed check: min_trade_r is negative for loss, so we check if it's worse than -max_loss
    if metrics.min_trade_r < -config.max_single_loss_r:
        return TraderSelectionResult(eligible=False, score=0.0)

    # --- Scoring components ---
    # Expectancy component.
    if config.target_expectancy > 0:
        e_raw = metrics.expectancy / config.target_expectancy
    else:
        e_raw = 0.0
    e_component = clamp(e_raw, 0.0, 1.0)

    # Payoff ratio component.
    if config.target_payoff > 0:
        p_raw = metrics.payoff_ratio / config.target_payoff
    else:
        p_raw = 0.0
    p_component = clamp(p_raw, 0.0, 1.0)

    # Trading frequency component.
    if config.target_trades_per_day > 0:
        f_raw = metrics.trades_per_day / config.target_trades_per_day
    else:
        f_raw = 0.0
    f_component = clamp(f_raw, 0.0, 1.0)

    # Drawdown component (the smaller the drawdown, the closer to 1.0).
    if config.max_drawdown_pct > 0:
        d_raw = 1.0 - (metrics.max_drawdown_pct / config.max_drawdown_pct)
    else:
        d_raw = 1.0
    d_component = clamp(d_raw, 0.0, 1.0)

    score = (
        0.4 * e_component
        + 0.3 * p_component
        + 0.2 * f_component
        + 0.1 * d_component
    )

    return TraderSelectionResult(eligible=True, score=score)
