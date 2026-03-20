import type { ReactNode } from 'react';
import { cn } from '../lib/cn';

export interface FilterOption {
  value: string;
  label: string;
}

interface SelectFilterProps {
  label?: string;
  value: string;
  options: FilterOption[];
  onChange: (value: string) => void;
  allLabel?: string;
  className?: string;
}

export function SelectFilter({ label, value, options, onChange, allLabel = 'All', className }: SelectFilterProps) {
  return (
    <label className={cn('flex items-center gap-2', className)}>
      {label && <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">{label}</span>}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-xl border border-white/10 bg-slate-900/85 px-3 py-2 text-sm text-slate-200 focus:border-cyan-400/40 focus:outline-none"
      >
        <option value="">{allLabel}</option>
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </label>
  );
}

interface FilterBarProps {
  children: ReactNode;
  className?: string;
}

export function FilterBar({ children, className }: FilterBarProps) {
  return (
    <div className={cn('glass-panel flex flex-wrap items-center gap-3 rounded-[24px] p-3 md:p-4 mb-6', className)}>
      {children}
    </div>
  );
}
