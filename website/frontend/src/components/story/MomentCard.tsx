import type { MatchMoment, MatchMomentType } from '../../api/types';
import { cn } from '../../lib/cn';

// Palette mirrors legacy website/js/story.js:618 so React + legacy
// render identically (moments detector in moments.py emits 11 types).
// Previously only the first 5 were covered here, which silently fell
// every other moment back to the `kill_streak` config and mislabelled
// ~55% of cards.
const MOMENT_CONFIG: Record<MatchMomentType, { icon: string; color: string; bg: string }> = {
  kill_streak:       { icon: '\u{1F480}',        color: 'text-rose-400',    bg: 'from-rose-500/15 to-pink-500/15' },
  carrier_chain:     { icon: '\u{1F3AF}',        color: 'text-emerald-400', bg: 'from-emerald-500/15 to-teal-500/15' },
  focus_survival:    { icon: '\u{1F48E}',        color: 'text-purple-400',  bg: 'from-purple-500/15 to-violet-500/15' },
  push_success:      { icon: '\u{1F6E1}\uFE0F',  color: 'text-amber-400',   bg: 'from-amber-500/15 to-orange-500/15' },
  trade_chain:       { icon: '\u26A1',           color: 'text-cyan-400',    bg: 'from-cyan-500/15 to-blue-500/15' },
  objective_secured: { icon: '\u{1F3C6}',        color: 'text-yellow-400',  bg: 'from-yellow-500/15 to-amber-500/15' },
  objective_run:     { icon: '\u{1F527}',        color: 'text-blue-400',    bg: 'from-blue-500/15 to-sky-500/15' },
  objective_denied:  { icon: '\u{1F6AB}',        color: 'text-red-400',     bg: 'from-red-500/15 to-rose-500/15' },
  multi_revive:      { icon: '\u{1F489}',        color: 'text-emerald-400', bg: 'from-emerald-500/15 to-green-500/15' },
  team_wipe:         { icon: '\u{1F480}',        color: 'text-rose-400',    bg: 'from-rose-500/15 to-red-500/15' },
  multikill:         { icon: '\u{1F525}',        color: 'text-amber-400',   bg: 'from-amber-500/15 to-orange-500/15' },
};

const TYPE_LABELS: Record<MatchMomentType, string> = {
  kill_streak:       'Kill Streak',
  carrier_chain:     'Carrier Chain',
  focus_survival:    'Focus Survival',
  push_success:      'Team Push',
  trade_chain:       'Trade Kill',
  objective_secured: 'Objective Secured',
  objective_run:     'Objective Run',
  objective_denied:  'Objective Denied',
  multi_revive:      'Multi-Revive',
  team_wipe:         'Team Wipe',
  multikill:         'Multikill',
};

const FALLBACK = MOMENT_CONFIG.kill_streak;

function Stars({ count }: { count: number }) {
  const n = Math.min(Math.max(Math.round(count || 0), 0), 5);
  return (
    <span className="text-amber-400 text-xs tracking-tight">
      {'\u2605'.repeat(n)}
      <span className="text-slate-600">{'\u2605'.repeat(5 - n)}</span>
    </span>
  );
}

interface MomentCardProps {
  moment: MatchMoment;
  index: number;
}

export function MomentCard({ moment, index }: MomentCardProps) {
  const cfg = MOMENT_CONFIG[moment.type] ?? FALLBACK;
  const label = TYPE_LABELS[moment.type] ?? moment.type;
  const hasKills = Array.isArray(moment.kills) && moment.kills.length > 0;

  return (
    <div
      className={cn(
        'flex-shrink-0 rounded-2xl border border-white/8 p-4',
        hasKills ? 'w-72' : 'w-56',
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
        <div className="flex items-center gap-2">
          {moment.time_formatted && (
            <span className="text-[10px] text-slate-500 font-mono">
              {moment.time_formatted}
            </span>
          )}
          <Stars count={moment.impact_stars} />
        </div>
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

      {/* Per-kill breakdown (multikill / team_wipe emit this payload) */}
      {hasKills && (
        <div className="mt-2 pt-2 border-t border-white/5 space-y-0.5 text-[10px]">
          {moment.kills!.map((k, i) => (
            <div key={i} className="flex items-center gap-1">
              <span className="text-white">{k.killer}</span>
              <span className="text-slate-600">{'\u2192'}</span>
              <span className="text-red-400">{k.victim}</span>
              {k.weapon && <span className="text-slate-600 ml-auto">{k.weapon}</span>}
              {k.time_formatted && (
                <span className="text-slate-700 w-8 text-right">{k.time_formatted}</span>
              )}
            </div>
          ))}
          {moment.duration_ms != null && (
            <div className="text-slate-600 mt-1">
              Duration: {(moment.duration_ms / 1000).toFixed(1)}s
            </div>
          )}
        </div>
      )}
    </div>
  );
}
