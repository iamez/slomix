import { cn } from '../lib/cn';

interface EmptyStateProps {
  message?: string;
  className?: string;
}

export function EmptyState({ message = 'No data available.', className }: EmptyStateProps) {
  return (
    <div className={cn('text-center py-16', className)}>
      <div className="text-4xl mb-4">📭</div>
      <p className="text-slate-400 text-lg">{message}</p>
    </div>
  );
}
