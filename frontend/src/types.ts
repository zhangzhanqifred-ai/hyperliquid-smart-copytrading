export interface StrategyParams {
  time_window_seconds: number;
  price_range_width_pct: number;
  min_smart_traders: number;
}

export interface ExecutionParams {
  notional_per_signal: number;
  initial_equity: number;
  fee_rate_bps: number;
}

export interface BacktestParams {
  window_days: number;
  min_score: number;
  min_trades_per_day: number;
  strategy: StrategyParams;
  execution: ExecutionParams;
}

export interface BacktestRequest {
  start_date: string;  // ISO Date
  end_date: string;    // ISO Date
  params: BacktestParams;
}

// Alias for compatibility if needed, or replace usages
export type BacktestRequestBody = BacktestRequest;

export interface EquityPoint {
  step: number;
  equity: number;
}

export interface BacktestRun {
  id: string | number;
  created_at?: string;
  start_date: string;
  end_date: string;
  initial_equity: number;
  final_equity: number;
  total_return_pct: number;
  max_drawdown_pct: number;
  total_trades: number;
  win_rate: number;
  equity_curve?: EquityPoint[];
  params_snapshot?: BacktestParams | null;
  strategy_name?: string | null; // Preset name
  preset_id?: string | null;
}

export interface RiskStatus {
  current_equity: number;
  max_drawdown_pct: number;
  risk_triggered: boolean;
  config: {
    max_drawdown_pct: number;
  };
}

export interface StrategyPreset {
  id: string;
  name: string;
  description: string;
  params: BacktestParams;
}

export const BUILTIN_PRESETS: StrategyPreset[] = [
  {
    id: "conservative",
    name: "保守策略",
    description: "高分聪明钱 + 相对宽价格区间，仓位较小，控制回撤优先。",
    params: {
      window_days: 30,
      min_score: 0.7,
      min_trades_per_day: 3,
      strategy: {
        time_window_seconds: 60,
        price_range_width_pct: 0.0015,
        min_smart_traders: 2
      },
      execution: {
        notional_per_signal: 0.005,
        initial_equity: 10000,
        fee_rate_bps: 5
      }
    }
  },
  {
    id: "balanced",
    name: "中性策略",
    description: "中高分聪明钱 + 中等频率，适中仓位，收益与回撤平衡。",
    params: {
      window_days: 30,
      min_score: 0.6,
      min_trades_per_day: 2,
      strategy: {
        time_window_seconds: 60,
        price_range_width_pct: 0.001,
        min_smart_traders: 2
      },
      execution: {
        notional_per_signal: 0.01,
        initial_equity: 10000,
        fee_rate_bps: 5
      }
    }
  },
  {
    id: "aggressive",
    name: "激进策略",
    description: "分数阈值略低，但要求高频交易和多地址共振，单笔仓位稍大。",
    params: {
      window_days: 30,
      min_score: 0.5,
      min_trades_per_day: 5,
      strategy: {
        time_window_seconds: 45,
        price_range_width_pct: 0.0008,
        min_smart_traders: 3
      },
      execution: {
        notional_per_signal: 0.015,
        initial_equity: 10000,
        fee_rate_bps: 5
      }
    }
  }
];

export type BacktestFieldPath =
  | 'start_date'
  | 'end_date'
  | 'params.window_days'
  | 'params.min_score'
  | 'params.min_trades_per_day'
  | 'params.strategy.time_window_seconds'
  | 'params.strategy.price_range_width_pct'
  | 'params.strategy.min_smart_traders'
  | 'params.execution.notional_per_signal'
  | 'params.execution.initial_equity'
  | 'params.execution.fee_rate_bps';
