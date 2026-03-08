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
        className="bg-slate-800 border border-white/10 text-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500/50"
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
    <div className={cn('flex flex-wrap items-center gap-3 mb-6', className)}>
      {children}
    </div>
  );
}
