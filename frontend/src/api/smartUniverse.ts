import { api } from "./client";

export interface SmartTrader {
  trader_id: number;
  address: string;
  window_days: number;
  
  score: number;
  win_rate_window: number;
  pnl_window: number;
  volatility_window: number;
  max_drawdown_window: number;
  payoff_ratio: number;
  expectancy: number;
  trades_per_day: number;
}

export interface FetchSmartUniverseParams {
  window_days?: number;
  min_score?: number;
  min_trades_per_day?: number;
}

export async function fetchSmartUniverse(params?: FetchSmartUniverseParams): Promise<SmartTrader[]> {
  const res = await api.get<SmartTrader[]>("/smart-universe", { params });
  return res.data;
}

