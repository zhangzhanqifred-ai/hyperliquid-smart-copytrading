import { RiskStatus } from '../types';

interface RiskStatusCardProps {
  data?: RiskStatus | null;
}

export function RiskStatusCard({ data }: RiskStatusCardProps) {
  if (!data) {
    return (
      <div className="rounded-lg border border-dashed border-slate-300 p-4 text-sm text-slate-500">
        正在读取风险状态...
      </div>
    );
  }

  const badgeClass = data.risk_triggered
    ? 'bg-red-100 text-red-700'
    : 'bg-emerald-100 text-emerald-700';

  const badgeLabel = data.risk_triggered ? 'Triggered' : 'OK';

  return (
    <div className="rounded-lg bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold text-slate-700">Risk Status</p>
          <p className="text-xs text-slate-500">来自 /risk/status 接口</p>
        </div>
        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${badgeClass}`}>
          {badgeLabel}
        </span>
      </div>
      <div className="mt-4 grid grid-cols-3 gap-4 text-sm">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">
            Current Equity
          </p>
          <p className="text-lg font-semibold text-slate-900">
            {data.current_equity.toFixed(2)}
          </p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">
            Max Drawdown
          </p>
          <p className="text-lg font-semibold text-slate-900">
            {(data.max_drawdown_pct * 100).toFixed(2)}%
          </p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">
            Risk Flag
          </p>
          <p className="text-lg font-semibold text-slate-900">{badgeLabel}</p>
        </div>
      </div>
    </div>
  );
}

