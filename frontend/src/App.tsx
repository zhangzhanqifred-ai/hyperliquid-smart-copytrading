import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer
} from 'recharts';
import {
  BacktestRequestBody,
  BacktestRun,
  RiskStatus,
  BUILTIN_PRESETS
} from './types';
import { BacktestForm } from './components/BacktestForm';
import { ResultCard } from './components/ResultCard';
import { BacktestTable } from './components/BacktestTable';
import { RiskStatusCard } from './components/RiskStatusCard';
import { SmartUniversePanel } from './components/SmartUniversePanel';
import {
  createBacktest,
  fetchBacktests,
  fetchBacktestDetail,
  fetchRiskStatus
} from './api';

const today = () => new Date().toISOString().slice(0, 10);

const defaultFormState: BacktestRequestBody = {
  start_date: '2025-11-01',
  end_date: today(),
  params: {
    window_days: 30,
    min_score: 0,
    min_trades_per_day: 0,
    strategy: {
      time_window_seconds: 60,
      price_range_width_pct: 0.001,
      min_smart_traders: 1
    },
    execution: {
      notional_per_signal: 100,
      initial_equity: 10000,
      fee_rate_bps: 5
    }
  }
};

function EquityCurveChart({ run }: { run: BacktestRun | null }) {
  if (!run || !run.equity_curve || run.equity_curve.length === 0) {
    return (
      <div className="flex h-64 w-full items-center justify-center rounded-lg bg-white shadow-sm">
        <p className="text-sm text-slate-400">暂无权益曲线</p>
      </div>
    );
  }

  return (
    <div className="h-64 w-full rounded-lg bg-white p-4 shadow-sm">
      <p className="mb-4 text-sm font-semibold text-slate-700">权益曲线</p>
      <ResponsiveContainer width="100%" height="85%">
        <LineChart data={run.equity_curve}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            dataKey="step"
            tick={{ fontSize: 12, fill: '#64748b' }}
            tickLine={false}
          />
          <YAxis
            domain={['auto', 'auto']}
            tick={{ fontSize: 12, fill: '#64748b' }}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#fff',
              border: '1px solid #e2e8f0',
              borderRadius: '0.375rem',
              fontSize: '12px'
            }}
          />
          <Line
            type="monotone"
            dataKey="equity"
            stroke="#0f172a"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, strokeWidth: 0 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function RiskStatusBar() {
  const [status, setStatus] = useState<RiskStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchRiskStatus()
      .then(setStatus)
      .catch((e) => {
        console.error("Failed to fetch risk status", e);
        setError("无法获取风控状态");
      });
  }, []);

  if (error) {
    return (
      <div className="mb-4 rounded bg-red-50 px-3 py-2 text-sm text-red-600">
        {error}
      </div>
    );
  }

  if (!status) {
    return (
      <div className="mb-4 rounded bg-gray-50 px-3 py-2 text-sm text-gray-500">
        正在加载风控状态…
      </div>
    );
  }

  const maxDdPct = (status.config.max_drawdown_pct * 100).toFixed(1);
  const curDdPct = (status.max_drawdown_pct * 100).toFixed(2);

  return (
    <div className="mb-4 flex items-center justify-between rounded bg-slate-900 px-4 py-3 text-sm text-slate-50">
      <div>
        <div>当前权益: <span className="font-semibold">{status.current_equity.toFixed(2)}</span></div>
        <div className="text-xs text-slate-300">
          最大回撤阈值: {maxDdPct}% | 当前回撤: {curDdPct}%
        </div>
      </div>
      <div>
        {status.risk_triggered ? (
          <span className="rounded bg-red-500 px-2 py-1 text-xs font-semibold">RISK TRIGGERED</span>
        ) : (
          <span className="rounded bg-emerald-500 px-2 py-1 text-xs font-semibold">RISK OK</span>
        )}
      </div>
    </div>
  );
}

function App() {
  const [riskStatus, setRiskStatus] = useState<RiskStatus | null>(null);
  const [backtests, setBacktests] = useState<BacktestRun[]>([]);
  const [latestRun, setLatestRun] = useState<BacktestRun | null>(null);
  const [selectedRun, setSelectedRun] = useState<BacktestRun | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'backtest' | 'universe'>('backtest');

  const handleRiskFetch = useCallback(async () => {
    try {
      const data = await fetchRiskStatus();
      setRiskStatus(data);
    } catch (err) {
      setError('获取风险状态失败，请稍后重试。');
    }
  }, []);

  const handleBacktestsFetch = useCallback(async () => {
    try {
      const data = await fetchBacktests();
      const normalizedData = Array.isArray(data) ? data : [];
      setBacktests(normalizedData);
      if (normalizedData.length > 0 && !latestRun) {
        // Don't auto-select if we already have one selected
        // But if it's initial load, maybe? 
        // Let's leave auto-select logic to user interaction mostly, 
        // but for initial load it's fine.
        if (!selectedRun) {
           // handleSelectRun(normalizedData[0]); // Avoid double fetch
        }
      }
    } catch (err) {
      setError('获取历史回测失败，请检查后端服务。');
    }
  }, [latestRun, selectedRun]);

  useEffect(() => {
    handleRiskFetch();
    handleBacktestsFetch();
  }, [handleRiskFetch, handleBacktestsFetch]);

  const handleSelectRun = async (run: BacktestRun) => {
    try {
      setLatestRun(run);
      setSelectedRun(run);
      
      const detail = await fetchBacktestDetail(run.id);
      
      // Preserve frontend-only fields if they exist on the original item but not on detail
      const decoratedDetail = {
        ...detail,
        strategy_name: run.strategy_name ?? detail.strategy_name,
        preset_id: run.preset_id ?? detail.preset_id
      };

      setLatestRun(decoratedDetail);
      setSelectedRun(decoratedDetail);
      
      setBacktests((prev) => 
        prev.map((item) => (item.id === detail.id ? decoratedDetail : item))
      );
    } catch (err) {
      console.error('Failed to fetch backtest details', err);
    }
  };

  const handleRunBacktest = async (values: BacktestRequestBody & { presetId?: string }) => {
    try {
      setIsRunning(true);
      setError(null);
      
      // Separate presetId from the payload
      const { presetId, ...payload } = values;
      
      const run = await createBacktest(payload);
      
      // Decorate result
      const preset = BUILTIN_PRESETS.find(p => p.id === presetId);
      const decorated: BacktestRun = {
        ...run,
        preset_id: presetId,
        strategy_name: preset?.name
      };

      try {
        const detail = await fetchBacktestDetail(run.id);
        const decoratedDetail = {
          ...detail,
          preset_id: presetId,
          strategy_name: preset?.name
        };
        setLatestRun(decoratedDetail);
        setSelectedRun(decoratedDetail);
        setBacktests((prev) => {
          const safePrev = Array.isArray(prev) ? prev : [];
          return [decoratedDetail, ...safePrev];
        });
      } catch (e) {
        setLatestRun(decorated);
        setSelectedRun(decorated);
        setBacktests((prev) => {
          const safePrev = Array.isArray(prev) ? prev : [];
          return [decorated, ...safePrev];
        });
      }
    } catch (e) {
      console.error('Failed to run backtest', e);
      setError('回测失败，请检查后端服务或参数配置');
    } finally {
      setIsRunning(false);
    }
  };

  const summaryByPreset = useMemo(() => {
    const map = new Map<string, { name: string; count: number; avgReturn: number; avgMaxDd: number }>();
    backtests.forEach(run => {
      const key = run.preset_id ?? "custom";
      const name = run.strategy_name ?? "自定义";
      const item = map.get(key) ?? { name, count: 0, avgReturn: 0, avgMaxDd: 0 };
      item.count += 1;
      item.avgReturn += run.total_return_pct;
      item.avgMaxDd += run.max_drawdown_pct;
      map.set(key, item);
    });
    return Array.from(map.values()).map(item => ({
      ...item,
      avgReturn: item.count > 0 ? item.avgReturn / item.count : 0,
      avgMaxDd: item.count > 0 ? item.avgMaxDd / item.count : 0
    }));
  }, [backtests]);

  const activeRun = useMemo(() => selectedRun || latestRun, [selectedRun, latestRun]);

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="mx-auto flex max-w-6xl flex-col gap-6">
        <header className="space-y-3">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">
              Hyperliquid 聪明钱策略控制台
            </h1>
            <p className="text-sm text-slate-500">
              Tailwind + React + Axios 的最小可用控制台
            </p>
          </div>
          <RiskStatusBar />
        </header>

        {error && (
          <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-4 border-b border-slate-200">
          <button
            className={`px-4 py-2 text-sm font-semibold ${activeTab === 'backtest' ? 'border-b-2 border-slate-900 text-slate-900' : 'text-slate-500 hover:text-slate-700'}`}
            onClick={() => setActiveTab('backtest')}
          >
            回测控制台
          </button>
          <button
            className={`px-4 py-2 text-sm font-semibold ${activeTab === 'universe' ? 'border-b-2 border-slate-900 text-slate-900' : 'text-slate-500 hover:text-slate-700'}`}
            onClick={() => setActiveTab('universe')}
          >
            聪明钱池 (Smart Universe)
          </button>
        </div>

        {activeTab === 'backtest' ? (
          <>
            <main className="grid gap-6 md:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
              <section>
                <BacktestForm
                  initialValues={defaultFormState}
                  onSubmit={handleRunBacktest}
                  loading={isRunning}
                />
              </section>
              <aside className="space-y-6">
                <ResultCard run={activeRun} />
                <EquityCurveChart run={activeRun} />
              </aside>
            </main>

            <section className="space-y-3 pb-12">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-slate-900">
                  策略对比汇总
                </h2>
              </div>
              
              {/* Summary Cards */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {summaryByPreset.map((item) => (
                  <div key={item.name} className="rounded-lg bg-white p-4 shadow-sm">
                    <div className="text-sm font-medium text-slate-500">{item.name}</div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className={`text-xl font-semibold ${item.avgReturn >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                            {(item.avgReturn * 100).toFixed(2)}%
                        </span>
                        <span className="text-xs text-slate-400">Avg Return</span>
                    </div>
                    <div className="mt-1 text-xs text-slate-500">
                        Avg Max DD: {(item.avgMaxDd * 100).toFixed(2)}%
                    </div>
                    <div className="mt-1 text-xs text-slate-400">
                        Samples: {item.count}
                    </div>
                  </div>
                ))}
              </div>

              <div className="flex items-center justify-between pt-6">
                <h2 className="text-lg font-semibold text-slate-900">
                  历史回测记录
                </h2>
                <button
                  type="button"
                  onClick={handleBacktestsFetch}
                  className="text-xs font-semibold text-slate-500 underline"
                >
                  Refresh
                </button>
              </div>
              <BacktestTable
                items={backtests}
                onSelect={handleSelectRun}
                selectedId={activeRun?.id}
              />
            </section>
          </>
        ) : (
          <SmartUniversePanel />
        )}
      </div>
    </div>
  );
}

export default App;
