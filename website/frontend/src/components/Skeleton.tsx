import { cn } from '../lib/cn';

interface SkeletonProps {
  variant?: 'card' | 'table' | 'line';
  count?: number;
  className?: string;
}

function SkeletonCard() {
  return (
    <div className="glass-card rounded-xl p-6 border border-white/5 animate-pulse">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-10 h-10 rounded-lg bg-slate-700/50" />
        <div className="h-4 w-24 rounded bg-slate-700/50" />
      </div>
      <div className="h-10 w-32 rounded bg-slate-700/50 mb-3" />
      <div className="h-3 w-20 rounded bg-slate-700/50" />
      <div className="mt-4 pt-4 border-t border-white/5 flex justify-between">
        <div className="h-4 w-28 rounded bg-slate-700/50" />
        <div className="h-4 w-16 rounded bg-slate-700/50" />
      </div>
    </div>
  );
}

export function Skeleton({ variant = 'card', count = 1, className }: SkeletonProps) {
  const items = Array.from({ length: count }, (_, i) => i);

  if (variant === 'card') {
    return (
      <div className={cn('grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4', className)}>
        {items.map((i) => <SkeletonCard key={i} />)}
      </div>
    );
  }

  return (
    <div className={cn('space-y-3', className)}>
      {items.map((i) => (
        <div key={i} className="h-4 rounded bg-slate-700/50 animate-pulse" style={{ width: `${60 + Math.random() * 30}%` }} />
      ))}
    </div>
  );
}
