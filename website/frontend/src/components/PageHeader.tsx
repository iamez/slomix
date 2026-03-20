import type { ReactNode } from 'react';
import { cn } from '../lib/cn';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  children?: ReactNode;
  className?: string;
  eyebrow?: string;
  badge?: string;
}

export function PageHeader({ title, subtitle, children, className, eyebrow, badge }: PageHeaderProps) {
  return (
    <div className={cn('glass-panel relative overflow-hidden rounded-[30px] p-6 md:p-7 mb-8', className)}>
      <div className="absolute inset-y-0 right-0 w-48 bg-[radial-gradient(circle_at_top_right,rgba(56,189,248,0.15),transparent_60%)]" />
      <div className="relative flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-3xl">
          {(eyebrow || badge) && (
            <div className="mb-3 flex flex-wrap items-center gap-2">
              {eyebrow && <div className="section-kicker">{eyebrow}</div>}
              {badge && (
                <span className="rounded-full border border-cyan-400/25 bg-cyan-400/12 px-3 py-1 text-[11px] font-bold text-cyan-200">
                  {badge}
                </span>
              )}
            </div>
          )}
          <h1 className="text-3xl font-black tracking-tight text-white md:text-4xl">{title}</h1>
          {subtitle && <p className="mt-2 max-w-2xl text-sm text-slate-400 md:text-base">{subtitle}</p>}
        </div>
        {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
      </div>
    </div>
  );
}
