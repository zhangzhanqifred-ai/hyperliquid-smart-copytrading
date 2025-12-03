import { api } from "./client";

export interface RiskConfig {
  id: number;
  max_drawdown_pct: number;
  max_leverage_per_symbol: number | null;
  max_position_size_per_symbol: number | null;
  created_at: string;
  updated_at: string;
}

export interface RiskStatus {
  config: RiskConfig;
  current_equity: number;
  max_drawdown_abs: number;
  max_drawdown_pct: number;
  risk_triggered: boolean;
  last_event: any | null;
}

export async function fetchRiskStatus(): Promise<RiskStatus> {
  const res = await api.get<RiskStatus>("/risk/status");
  return res.data;
}

