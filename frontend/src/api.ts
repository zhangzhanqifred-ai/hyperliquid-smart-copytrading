import axios from 'axios';
import type {
  BacktestRequestBody,
  BacktestRun,
  RiskStatus
} from './types';

/**
 * Update baseURL or define VITE_API_BASE_URL to match your FastAPI endpoint.
 */
export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000',
  timeout: 15000
});

export async function fetchRiskStatus(): Promise<RiskStatus> {
  const { data } = await apiClient.get<RiskStatus>('/risk/status');
  return data;
}

export async function fetchBacktests(): Promise<BacktestRun[]> {
  const { data } = await apiClient.get<BacktestRun[]>('/backtests');
  return data;
}

export async function fetchBacktestDetail(id: string | number): Promise<BacktestRun> {
  const { data } = await apiClient.get<BacktestRun>(`/backtests/${id}`);
  return data;
}

export async function createBacktest(
  payload: BacktestRequestBody
): Promise<BacktestRun> {
  const { data } = await apiClient.post<BacktestRun>('/backtests', payload);
  return data;
}

