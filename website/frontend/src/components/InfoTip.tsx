import { useState, useRef, useEffect, type ReactNode } from 'react';
import { HelpCircle } from 'lucide-react';

interface InfoTipProps {
  /** Short heading shown in bold at the top of the popover */
  label?: string;
  /** Popover body content */
  children: ReactNode;
  /** Optional extra class on the trigger button */
  className?: string;
}

export function InfoTip({ label, children, className }: InfoTipProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, [open]);

  return (
    <div ref={ref} className={`relative inline-flex items-center ${className ?? ''}`}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="text-slate-500 hover:text-cyan-400 transition-colors focus:outline-none"
        aria-label={label ? `Info: ${label}` : 'More info'}
      >
        <HelpCircle className="w-3.5 h-3.5" />
      </button>
      {open && (
        <div className="absolute z-50 left-0 top-full mt-1.5 w-72 rounded-xl border border-white/10 bg-slate-800/95 backdrop-blur-lg p-3.5 shadow-xl shadow-black/40 text-xs text-slate-300 leading-relaxed">
          {label && <div className="font-bold text-white text-[11px] mb-1.5">{label}</div>}
          {children}
        </div>
      )}
    </div>
  );
}
