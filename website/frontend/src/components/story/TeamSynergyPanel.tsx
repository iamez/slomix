import type { SynergyResponse, SynergyGroup } from '../../api/types';

const METRIC_LABELS: { key: keyof Omit<SynergyGroup, 'players' | 'composite'>; label: string; color: string }[] = [
  { key: 'crossfire', label: 'Crossfire', color: 'bg-rose-400' },
  { key: 'trade', label: 'Trade', color: 'bg-amber-400' },
  { key: 'cohesion', label: 'Cohesion', color: 'bg-cyan-400' },
  { key: 'push', label: 'Push', color: 'bg-violet-400' },
  { key: 'medic', label: 'Medic', color: 'bg-emerald-400' },
];

function GroupCard({ group, label, isWinner }: { group: SynergyGroup; label: string; isWinner: boolean }) {
  return (
    <div className={`glass-card rounded-[20px] p-5 border ${isWinner ? 'border-amber-400/25' : 'border-white/8'}`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <span className="text-xs text-slate-500 uppercase tracking-wider font-bold">{label}</span>
        <span className={`text-2xl font-bold tabular-nums ${isWinner ? 'text-amber-400' : 'text-slate-300'}`}>
          {group.composite.toFixed(0)}
        </span>
      </div>

      {/* Metric bars */}
      <div className="space-y-2.5">
        {METRIC_LABELS.map(({ key, label: metricLabel, color }) => {
          const val = group[key] as number;
          return (
            <div key={key}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] text-slate-500 uppercase tracking-wider">{metricLabel}</span>
                <span className="text-xs text-slate-300 font-bold tabular-nums">{val.toFixed(0)}</span>
              </div>
              <div className="h-1.5 rounded-full bg-white/5 overflow-hidden">
                <div
                  className={`h-full rounded-full ${color} opacity-75 transition-all duration-500`}
                  style={{ width: `${Math.min(val, 100)}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* Player list */}
      <div className="mt-4 flex flex-wrap gap-1.5">
        {group.players.map((name) => (
          <span key={name} className="rounded-md bg-white/5 px-2 py-0.5 text-[10px] text-slate-400">{name}</span>
        ))}
      </div>
    </div>
  );
}

interface Props {
  data: SynergyResponse;
}

function InsufficientDataBadge({ reason }: { reason?: string }) {
  return (
    <div className="glass-card rounded-[20px] p-5 border border-amber-500/25 text-center">
      <div className="text-amber-400 text-xs uppercase tracking-wider font-bold mb-2">
        Insufficient data
      </div>
      <p className="text-xs text-slate-400">
        {reason === 'no_r1_data'
          ? 'Round 1 stats are missing for this session — team synergy needs R1 to establish groups.'
          : 'Not enough data to compute team synergy for this session.'}
      </p>
    </div>
  );
}

export function TeamSynergyPanel({ data }: Props) {
  // F9 (2026-04-21): backend may return `status: "partial_data"` when
  // the session has rows but no R1 data — render a badge instead of
  // forcing zero-bars that mislead the user into thinking the team
  // played badly.
  if (data.status === 'partial_data') {
    return (
      <div>
        <h3 className="text-xs text-slate-500 uppercase tracking-wider font-bold mb-3">Team Coordination</h3>
        <InsufficientDataBadge reason={data.reason} />
      </div>
    );
  }

  const groups = data.groups as { group_a?: SynergyGroup; group_b?: SynergyGroup };
  if (!groups.group_a || !groups.group_b) return null;

  const { group_a, group_b } = groups;
  const aWins = group_a.composite >= group_b.composite;
  const defaulted = data.defaulted_players_count ?? 0;

  return (
    <div>
      <h3 className="text-xs text-slate-500 uppercase tracking-wider font-bold mb-3">Team Coordination</h3>
      {defaulted > 0 && (
        <div className="mb-3 text-[10px] text-amber-400/80 uppercase tracking-wider">
          {defaulted} player{defaulted === 1 ? '' : 's'} had incomplete stopwatch correlation — results may be skewed
        </div>
      )}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <GroupCard group={group_a} label={group_a.players.slice(0, 2).join(' & ') + (group_a.players.length > 2 ? ' +' : '')} isWinner={aWins} />
        <GroupCard group={group_b} label={group_b.players.slice(0, 2).join(' & ') + (group_b.players.length > 2 ? ' +' : '')} isWinner={!aWins} />
      </div>
    </div>
  );
}
