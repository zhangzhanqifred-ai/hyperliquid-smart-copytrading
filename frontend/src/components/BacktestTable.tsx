import { BacktestRun } from '../types';

interface BacktestTableProps {
  items: BacktestRun[];
  onSelect: (run: BacktestRun) => void;
  selectedId?: string | number | null;
}

const headerClass = 'px-3 py-2 text-left text-xs font-semibold text-slate-500';
const cellClass = 'px-3 py-2 text-sm text-slate-700';

const formatPercent = (value: number) => `${(value * 100).toFixed(2)}%`;

export function BacktestTable({ items, onSelect, selectedId }: BacktestTableProps) {
  if (!items.length) {
    return (
      <div className="rounded-lg border border-dashed border-slate-300 p-4 text-sm text-slate-500">
        暂无历史回测记录
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg bg-white shadow-sm">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50">
          <tr>
            <th className={headerClass}>ID</th>
            <th className={headerClass}>Strategy</th>
            <th className={headerClass}>Created</th>
            <th className={headerClass}>Return</th>
            <th className={headerClass}>Max DD</th>
            <th className={headerClass}>Trades</th>
            <th className={headerClass}>Win Rate</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {items.map((run) => {
            const isSelected = selectedId === run.id;
            return (
              <tr
                key={String(run.id)}
                onClick={() => onSelect(run)}
                className={`cursor-pointer transition-colors hover:bg-slate-50 ${
                  isSelected ? 'bg-slate-50 ring-1 ring-inset ring-slate-200' : 'bg-white'
                }`}
              >
                <td className={cellClass}>
                  <span className="font-mono text-xs">{String(run.id)}</span>
                </td>
                <td className={cellClass}>
                  {run.strategy_name ?? run.preset_id ?? '自定义'}
                </td>
                <td className={cellClass}>
                  {run.created_at
                    ? new Date(run.created_at).toLocaleString()
                    : '—'}
                </td>
                <td className={cellClass}>{formatPercent(run.total_return_pct)}</td>
                <td className={cellClass}>
                  {formatPercent(run.max_drawdown_pct)}
                </td>
                <td className={cellClass}>{run.total_trades}</td>
                <td className={cellClass}>{formatPercent(run.win_rate)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
