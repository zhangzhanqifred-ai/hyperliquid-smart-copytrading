from datetime import date, datetime

from pydantic import BaseModel, Field


class BacktestRunCreate(BaseModel):
    """
    Configuration for launching a new backtest.

    For flexibility we keep most knobs inside the `params` dict, but you can
    add top-level fields here if you prefer stronger typing later.
    """

    start_date: date
    end_date: date
    params: dict = Field(
        default_factory=dict,
        description="Free-form strategy / universe / execution config for this backtest run.",
    )


class BacktestRunOut(BaseModel):
    """
    Public representation of a backtest run with key summary metrics.
    """

    id: int
    created_at: datetime
    start_date: date
    end_date: date

    name: str | None = None
    description: str | None = None

    initial_equity: float
    final_equity: float
    total_return_pct: float
    max_drawdown_pct: float

    total_trades: int
    win_rate: float


class BacktestRunDetail(BacktestRunOut):
    """
    Detailed view of a backtest run, including equity curve and full parameter snapshot.
    """

    equity_curve: list[dict] = Field(
        default_factory=list,
        description="Array of {step, equity} objects representing the equity curve.",
    )
    params_snapshot: dict = Field(
        default_factory=dict,
        description="Snapshot of the parameters used for this backtest.",
    )
    trades_summary: list[dict] = Field(
        default_factory=list,
        description="Simplified list of simulated trades: [{symbol, side, r, realized_pnl}, ...]",
    )


class BacktestRunListResponse(BaseModel):
    total: int
    items: list[BacktestRunOut]

