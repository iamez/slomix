import { useState, useMemo, type ReactNode } from 'react';
import { ChevronUp, ChevronDown } from 'lucide-react';
import { cn } from '../lib/cn';

export interface Column<T> {
  key: string;
  label: string;
  render?: (row: T, index: number) => ReactNode;
  sortable?: boolean;
  sortValue?: (row: T) => number | string;
  className?: string;
  headerClassName?: string;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  keyFn: (row: T, index: number) => string;
  onRowClick?: (row: T) => void;
  rowClassName?: (row: T, index: number) => string | undefined;
  emptyMessage?: string;
  className?: string;
  defaultSort?: { key: string; dir: 'asc' | 'desc' };
  stickyHeader?: boolean;
}

export function DataTable<T>({
  columns,
  data,
  keyFn,
  onRowClick,
  rowClassName,
  emptyMessage = 'No data available.',
  className,
  defaultSort,
  stickyHeader,
}: DataTableProps<T>) {
  const [sort, setSort] = useState(defaultSort ?? null);

  const sorted = useMemo(() => {
    if (!sort) return data;
    const col = columns.find((c) => c.key === sort.key);
    if (!col?.sortable) return data;
    const getValue = col.sortValue ?? ((row: T) => (row as Record<string, unknown>)[sort.key]);
    return [...data].sort((a, b) => {
      const va = getValue(a);
      const vb = getValue(b);
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      const cmp = typeof va === 'number' && typeof vb === 'number' ? va - vb : String(va).localeCompare(String(vb));
      return sort.dir === 'asc' ? cmp : -cmp;
    });
  }, [data, sort, columns]);

  function toggleSort(key: string) {
    setSort((prev) => {
      if (prev?.key === key) {
        return prev.dir === 'desc' ? { key, dir: 'asc' } : null;
      }
      return { key, dir: 'desc' };
    });
  }

  if (data.length === 0) {
    return <div className="glass-panel rounded-[24px] py-12 text-center text-slate-400">{emptyMessage}</div>;
  }

  return (
    <div className={cn('table-shell overflow-x-auto rounded-[24px]', className)}>
      <table className="min-w-[720px] w-full text-left">
        <thead>
          <tr className={cn('border-b border-white/10', stickyHeader && 'sticky top-0 bg-slate-900/95 backdrop-blur-sm z-10')}>
            {columns.map((col) => (
              <th
                key={col.key}
                className={cn(
                  'px-4 py-3 text-xs font-bold text-slate-400 uppercase tracking-wider',
                  col.sortable && 'cursor-pointer select-none hover:text-slate-200 transition',
                  col.headerClassName,
                )}
                onClick={col.sortable ? () => toggleSort(col.key) : undefined}
                aria-sort={col.sortable && sort?.key === col.key ? (sort.dir === 'asc' ? 'ascending' : 'descending') : undefined}
                role={col.sortable ? 'columnheader button' : 'columnheader'}
              >
                <span className="inline-flex items-center gap-1">
                  {col.label}
                  {col.sortable && sort?.key === col.key && (
                    sort.dir === 'desc' ? <ChevronDown className="w-3 h-3" /> : <ChevronUp className="w-3 h-3" />
                  )}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, i) => (
            <tr
              key={keyFn(row, i)}
              className={cn(
                'border-b border-white/5 transition',
                onRowClick && 'cursor-pointer hover:bg-white/[0.03]',
                i % 2 === 0 ? 'bg-transparent' : 'bg-white/[0.015]',
                rowClassName?.(row, i),
              )}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
            >
              {columns.map((col) => (
                <td key={col.key} className={cn('px-4 py-3 text-sm text-slate-200', col.className)}>
                  {col.render ? col.render(row, i) : String((row as Record<string, unknown>)[col.key] ?? '')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
