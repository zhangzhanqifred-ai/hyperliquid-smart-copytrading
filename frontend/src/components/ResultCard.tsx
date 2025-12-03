import { BacktestRun } from '../types';

interface ResultCardProps {
  run?: BacktestRun | null;
}

const valueClass = 'text-lg font-semibold text-slate-900';
const labelClass = 'text-xs uppercase tracking-wide text-slate-500';

function formatPercent(value?: number) {
  if (value === undefined || value === null) return '—';
  return `${(value * 100).toFixed(2)}%`;
}

export function ResultCard({ run }: ResultCardProps) {
  if (!run) {
    return (
      <div className="rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">
        尚未运行回测
      </div>
    );
  }

  return (
    <div className="space-y-4 rounded-lg bg-white p-6 shadow-sm">
      <div>
        <p className="text-sm font-semibold text-slate-700">最近回测</p>
        <p className="text-sm text-slate-500">
          {run.start_date} ~ {run.end_date}
        </p>
      </div>
      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <p className={labelClass}>Initial Equity</p>
          <p className={valueClass}>{run.initial_equity.toFixed(2)}</p>
        </div>
        <div>
          <p className={labelClass}>Final Equity</p>
          <p className={valueClass}>{run.final_equity.toFixed(2)}</p>
        </div>
        <div>
          <p className={labelClass}>Total Return</p>
          <p className={valueClass}>{formatPercent(run.total_return_pct)}</p>
        </div>
        <div>
          <p className={labelClass}>Max Drawdown</p>
          <p className={valueClass}>{formatPercent(run.max_drawdown_pct)}</p>
        </div>
        <div>
          <p className={labelClass}>Total Trades</p>
          <p className={valueClass}>{run.total_trades}</p>
        </div>
        <div>
          <p className={labelClass}>Win Rate</p>
          <p className={valueClass}>{formatPercent(run.win_rate)}</p>
        </div>
      </div>
    </div>
  );
}

