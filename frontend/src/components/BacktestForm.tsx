import { useState } from 'react';
import {
  BacktestFieldPath,
  BacktestRequestBody,
  BUILTIN_PRESETS
} from '../types';

interface BacktestFormProps {
  initialValues: BacktestRequestBody;
  onSubmit: (
    values: BacktestRequestBody & { presetId?: string }
  ) => void;
  loading: boolean;
}

const inputClass =
  'w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200';

const labelClass = 'text-xs font-semibold text-slate-600';

const sectionClass = 'space-y-3 rounded-lg bg-white p-4 shadow-sm';

export function BacktestForm({
  initialValues,
  onSubmit,
  loading
}: BacktestFormProps) {
  const [values, setValues] = useState<BacktestRequestBody>(initialValues);
  const [selectedPresetId, setSelectedPresetId] = useState<string>('balanced');

  // Initialize with balanced preset if present, or just keep initialValues
  // Actually, let's respect the logic:
  // When preset changes, update values.params
  
  const handlePresetChange = (id: string) => {
    setSelectedPresetId(id);
    const preset = BUILTIN_PRESETS.find((p) => p.id === id);
    if (preset) {
      setValues((prev) => ({
        ...prev,
        params: preset.params
      }));
    }
  };

  const handleChange = (field: BacktestFieldPath, value: string | number) => {
    setValues((prev) => {
      const newParams = { ...prev.params };
      const newStrategy = { ...newParams.strategy };
      const newExecution = { ...newParams.execution };

      if (field === 'start_date' || field === 'end_date') {
        return { ...prev, [field]: value as string };
      } else if (field.startsWith('params.strategy.')) {
        const key = field.split('.').pop() as keyof typeof newStrategy;
        // @ts-ignore
        newStrategy[key] = Number(value);
        newParams.strategy = newStrategy;
      } else if (field.startsWith('params.execution.')) {
        const key = field.split('.').pop() as keyof typeof newExecution;
        // @ts-ignore
        newExecution[key] = Number(value);
        newParams.execution = newExecution;
      } else if (field.startsWith('params.')) {
        const key = field.split('.').pop() as keyof typeof newParams;
        // @ts-ignore
        newParams[key] = Number(value);
      }

      // If user manually edits, maybe we should clear preset selection?
      // Or keep it as "Modified"? For now, let's keep the selection but allow edits.
      // Or better: set preset to empty/custom if params change? 
      // The user didn't specify, so let's keep it simple.
      
      return { ...prev, params: newParams };
    });
  };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onSubmit({
      ...values,
      presetId: selectedPresetId
    });
  };

  const numberInput = (
    field: BacktestFieldPath,
    value: number,
    label: string,
    step = 'any',
    min?: number
  ) => (
    <label className="space-y-1">
      <span className={labelClass}>{label}</span>
      <input
        type="number"
        step={step}
        min={min}
        className={inputClass}
        value={value}
        onChange={(e) => handleChange(field, Number(e.target.value))}
      />
    </label>
  );

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Preset Selection */}
      <div className={sectionClass}>
        <h3 className="text-sm font-semibold text-slate-700">策略预设</h3>
        <div className="space-y-2">
          <select
            className={inputClass}
            value={selectedPresetId}
            onChange={(e) => handlePresetChange(e.target.value)}
          >
            <option value="custom">自定义</option>
            {BUILTIN_PRESETS.map((preset) => (
              <option key={preset.id} value={preset.id}>
                {preset.name}
              </option>
            ))}
          </select>
          {selectedPresetId && selectedPresetId !== 'custom' && (
            <p className="text-xs text-slate-500">
              {BUILTIN_PRESETS.find((p) => p.id === selectedPresetId)?.description}
            </p>
          )}
        </div>
      </div>

      <div className={sectionClass}>
        <h3 className="text-sm font-semibold text-slate-700">回测区间</h3>
        <div className="grid grid-cols-1 gap-3">
          <label className="space-y-1">
            <span className={labelClass}>Start Date</span>
            <input
              type="date"
              className={inputClass}
              value={values.start_date}
              onChange={(e) => handleChange('start_date', e.target.value)}
            />
          </label>
          <label className="space-y-1">
            <span className={labelClass}>End Date</span>
            <input
              type="date"
              className={inputClass}
              value={values.end_date}
              onChange={(e) => handleChange('end_date', e.target.value)}
            />
          </label>
        </div>
      </div>

      <div className={sectionClass}>
        <h3 className="text-sm font-semibold text-slate-700">筛选参数</h3>
        <div className="grid grid-cols-1 gap-3">
          {numberInput(
            'params.window_days',
            values.params.window_days,
            'Window Days',
            '1',
            1
          )}
          {numberInput(
            'params.min_score',
            values.params.min_score,
            'Min Score'
          )}
          {numberInput(
            'params.min_trades_per_day',
            values.params.min_trades_per_day,
            'Min Trades / Day'
          )}
        </div>
      </div>

      <div className={sectionClass}>
        <h3 className="text-sm font-semibold text-slate-700">策略参数</h3>
        <div className="grid grid-cols-1 gap-3">
          {numberInput(
            'params.strategy.time_window_seconds',
            values.params.strategy.time_window_seconds,
            'Time Window (s)',
            '1',
            1
          )}
          {numberInput(
            'params.strategy.price_range_width_pct',
            values.params.strategy.price_range_width_pct,
            'Price Range Width (%)',
            '0.0001'
          )}
          {numberInput(
            'params.strategy.min_smart_traders',
            values.params.strategy.min_smart_traders,
            'Min Smart Traders',
            '1',
            1
          )}
        </div>
      </div>

      <div className={sectionClass}>
        <h3 className="text-sm font-semibold text-slate-700">执行参数</h3>
        <div className="grid grid-cols-1 gap-3">
          {numberInput(
            'params.execution.notional_per_signal',
            values.params.execution.notional_per_signal,
            'Notional / Signal'
          )}
          {numberInput(
            'params.execution.initial_equity',
            values.params.execution.initial_equity,
            'Initial Equity'
          )}
          {numberInput(
            'params.execution.fee_rate_bps',
            values.params.execution.fee_rate_bps,
            'Fee Rate (bps)',
            '1',
            0
          )}
        </div>
      </div>

      <button
        type="submit"
        className="w-full rounded-md bg-slate-900 py-2 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
        disabled={loading}
      >
        {loading ? 'Running...' : 'Run Backtest'}
      </button>
    </form>
  );
}
