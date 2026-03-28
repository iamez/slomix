import type { MatchMoment } from '../../api/types';
import { cn } from '../../lib/cn';

const MOMENT_CONFIG: Record<string, { icon: string; color: string; bg: string }> = {
  kill_streak:    { icon: '\u{1F525}', color: 'text-orange-400', bg: 'from-orange-500/15 to-red-500/15' },
  carrier_chain:  { icon: '\u{1F3AF}', color: 'text-rose-400',   bg: 'from-rose-500/15 to-pink-500/15' },
  focus_survival: { icon: '\u{1F6E1}\uFE0F', color: 'text-emerald-400', bg: 'from-emerald-500/15 to-teal-500/15' },
  push_success:   { icon: '\u26A1',    color: 'text-violet-400', bg: 'from-violet-500/15 to-purple-500/15' },
  trade_chain:    { icon: '\u2694\uFE0F', color: 'text-cyan-400',   bg: 'from-cyan-500/15 to-blue-500/15' },
};

const TYPE_LABELS: Record<string, string> = {
  kill_streak: 'Kill Streak',
  carrier_chain: 'Carrier Chain',
  focus_survival: 'Focus Survival',
  push_success: 'Team Push',
  trade_chain: 'Trade Kill',
};

function Stars({ count }: { count: number }) {
  return (
    <span className="text-amber-400 text-xs tracking-tight">
      {'\u2605'.repeat(count)}
      <span className="text-slate-600">{'\u2605'.repeat(5 - count)}</span>
    </span>
  );
}

interface MomentCardProps {
  moment: MatchMoment;
  index: number;
}

export function MomentCard({ moment, index }: MomentCardProps) {
  const cfg = MOMENT_CONFIG[moment.type] ?? MOMENT_CONFIG.kill_streak;
  const label = TYPE_LABELS[moment.type] ?? moment.type;

  return (
    <div
      className={cn(
        'flex-shrink-0 w-72 rounded-2xl border border-white/8 p-4',
        'bg-gradient-to-br', cfg.bg,
        'backdrop-blur-sm transition-transform hover:scale-[1.02]',
      )}
      style={{ animation: `fadeUp 0.4s ease-out ${index * 0.08}s both` }}
    >
      {/* Header: icon + type + stars */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-xl">{cfg.icon}</span>
          <span className={cn('text-xs font-bold uppercase tracking-wider', cfg.color)}>
            {label}
          </span>
        </div>
        <Stars count={moment.impact_stars} />
      </div>

      {/* Player + map */}
      <div className="flex items-baseline justify-between mb-2">
        <span className="text-sm font-bold text-white truncate max-w-[60%]">
          {moment.player}
        </span>
        <span className="text-[10px] text-slate-500 uppercase tracking-wider">
          R{moment.round_number} {moment.map_name}
        </span>
      </div>

      {/* Narrative */}
      <p className="text-xs text-slate-300 leading-relaxed">
        {moment.narrative}
      </p>
    </div>
  );
}
