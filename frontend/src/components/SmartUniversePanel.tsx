import { useEffect, useState, useMemo } from 'react';
import { fetchSmartUniverse, SmartTrader } from '../api/smartUniverse';

export function SmartUniversePanel() {
  const [traders, setTraders] = useState<SmartTrader[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [minScore, setMinScore] = useState<number>(0);
  const [minTradesPerDay, setMinTradesPerDay] = useState<number>(0);
  
  const [sortField, setSortField] = useState<keyof SmartTrader>('score');
  const [sortDesc, setSortDesc] = useState(true);
  const [selectedTrader, setSelectedTrader] = useState<SmartTrader | null>(null);

  useEffect(() => {
    loadTraders();
  }, []);

  const loadTraders = async () => {
    setLoading(true);
    setError(null);
    try {
      // Fetch with broad params, then filter locally for responsiveness 
      // or fetch with specific params if backend supports it well.
      // Here we use the params we just defined in api
      const data = await fetchSmartUniverse({
        min_score: minScore,
        min_trades_per_day: minTradesPerDay
      });
      setTraders(data);
    } catch (e) {
      setError('加载聪明钱列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleSort = (field: keyof SmartTrader) => {
    if (sortField === field) {
      setSortDesc(!sortDesc);
    } else {
      setSortField(field);
      setSortDesc(true);
    }
  };

  const sortedTraders = useMemo(() => {
    return [...traders].sort((a, b) => {
      const valA = Number(a[sortField] || 0);
      const valB = Number(b[sortField] || 0);
      if (valA === valB) return 0;
      return sortDesc ? valB - valA : valA - valB;
    });
  }, [traders, sortField, sortDesc]);

  const formatPercent = (val: number) => `${(val * 100).toFixed(1)}%`;
  const formatNum = (val: number) => val.toFixed(2);

  const thClass = "px-3 py-2 text-left text-xs font-semibold text-slate-500 cursor-pointer hover:text-slate-700 select-none";
  const tdClass = "px-3 py-2 text-sm text-slate-700";

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
      <div className="space-y-4">
        {/* Filters */}
        <div className="flex flex-wrap items-end gap-4 rounded-lg bg-white p-4 shadow-sm">
          <label className="text-sm text-slate-600">
            <div className="mb-1 text-xs font-semibold">Min Score</div>
            <input 
              type="number" 
              step="0.1"
              className="rounded border border-slate-300 px-2 py-1 text-sm"
              value={minScore}
              onChange={e => setMinScore(Number(e.target.value))}
            />
          </label>
          <label className="text-sm text-slate-600">
            <div className="mb-1 text-xs font-semibold">Min Trades/Day</div>
            <input 
              type="number" 
              step="0.1"
              className="rounded border border-slate-300 px-2 py-1 text-sm"
              value={minTradesPerDay}
              onChange={e => setMinTradesPerDay(Number(e.target.value))}
            />
          </label>
          <button 
            onClick={loadTraders}
            disabled={loading}
            className="rounded bg-slate-900 px-4 py-1.5 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-60"
          >
            {loading ? 'Loading...' : 'Filter'}
          </button>
        </div>

        {/* Table */}
        <div className="overflow-hidden rounded-lg bg-white shadow-sm">
          {error ? (
            <div className="p-8 text-center text-sm text-red-500">{error}</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200">
                <thead className="bg-slate-50">
                  <tr>
                    <th className={thClass}>Address</th>
                    <th className={thClass} onClick={() => handleSort('score')}>Score {sortField === 'score' && (sortDesc ? '↓' : '↑')}</th>
                    <th className={thClass} onClick={() => handleSort('pnl_window')}>PnL {sortField === 'pnl_window' && (sortDesc ? '↓' : '↑')}</th>
                    <th className={thClass} onClick={() => handleSort('win_rate_window')}>WinRate {sortField === 'win_rate_window' && (sortDesc ? '↓' : '↑')}</th>
                    <th className={thClass} onClick={() => handleSort('trades_per_day')}>Freq {sortField === 'trades_per_day' && (sortDesc ? '↓' : '↑')}</th>
                    <th className={thClass}>Expectancy</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {sortedTraders.map((t) => {
                    const isSelected = selectedTrader?.trader_id === t.trader_id;
                    return (
                      <tr 
                        key={t.trader_id}
                        onClick={() => setSelectedTrader(t)}
                        className={`cursor-pointer transition-colors hover:bg-slate-50 ${isSelected ? 'bg-slate-50 ring-1 ring-inset ring-slate-200' : ''}`}
                      >
                        <td className={tdClass}>
                          <div className="w-24 truncate font-mono text-xs" title={t.address}>{t.address}</div>
                        </td>
                        <td className={`${tdClass} font-semibold`}>{formatNum(t.score)}</td>
                        <td className={tdClass}>{formatNum(t.pnl_window)}</td>
                        <td className={tdClass}>{formatPercent(t.win_rate_window)}</td>
                        <td className={tdClass}>{formatNum(t.trades_per_day)}</td>
                        <td className={tdClass}>{formatNum(t.expectancy)}</td>
                      </tr>
                    );
                  })}
                  {sortedTraders.length === 0 && !loading && (
                    <tr>
                      <td colSpan={6} className="p-8 text-center text-sm text-slate-500">
                        暂无符合条件的数据
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Detail Card */}
      <div className="space-y-4">
        {selectedTrader ? (
          <div className="sticky top-4 space-y-4 rounded-lg bg-white p-6 shadow-sm">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">Trader Overview</h3>
              <p className="break-all font-mono text-xs text-slate-500">{selectedTrader.address}</p>
            </div>
            
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <div className="text-xs text-slate-500">Score</div>
                <div className="font-semibold">{formatNum(selectedTrader.score)}</div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Window Days</div>
                <div className="font-semibold">{selectedTrader.window_days}</div>
              </div>
              <div>
                <div className="text-xs text-slate-500">PnL (Window)</div>
                <div className={`font-semibold ${selectedTrader.pnl_window >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                  {formatNum(selectedTrader.pnl_window)}
                </div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Max Drawdown</div>
                <div className="font-semibold">{formatPercent(selectedTrader.max_drawdown_window)}</div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Payoff Ratio</div>
                <div className="font-semibold">{formatNum(selectedTrader.payoff_ratio)}</div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Volatility</div>
                <div className="font-semibold">{formatNum(selectedTrader.volatility_window)}</div>
              </div>
            </div>
          </div>
        ) : (
          <div className="sticky top-4 rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">
            点击左侧表格行<br/>查看 Trader 详情
          </div>
        )}
      </div>
    </div>
  );
}

