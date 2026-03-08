import type { ReactNode, MouseEventHandler } from 'react';
import { cn } from '../lib/cn';

interface GlassCardProps {
  children: ReactNode;
  className?: string;
  onClick?: MouseEventHandler<HTMLDivElement>;
}

export function GlassCard({ children, className, onClick }: GlassCardProps) {
  return (
    <div
      className={cn(
        'glass-card rounded-xl p-6 border border-white/5 hover:border-white/10 hover:bg-white/[0.03] transition-all cursor-pointer',
        className,
      )}
      onClick={onClick}
    >
      {children}
    </div>
  );
}
