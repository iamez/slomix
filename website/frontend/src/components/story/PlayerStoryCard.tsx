import type { KillImpactEntry } from '../../api/types';
import { ArchetypeBadge, type PlayerArchetype } from './ArchetypeBadge';
import { cn } from '../../lib/cn';
import { navigateToPlayer } from '../../lib/navigation';

interface PlayerStoryCardProps {
  entry: KillImpactEntry;
  rank: number;
  archetype: PlayerArchetype;
  className?: string;
}

function kisGradientClass(kis: number): string {
  if (kis >= 40) return 'border-amber-500/40 shadow-lg shadow-amber-500/10';
  if (kis >= 25) return 'border-cyan-500/30 shadow-lg shadow-cyan-500/8';
  if (kis >= 15) return 'border-white/10';
  return 'border-slate-700/50';
}

function kisBadgeStyle(kis: number): string {
  if (kis >= 40) return 'bg-gradient-to-r from-amber-500/20 to-rose-500/20 text-amber-300 border-amber-500/30';
  if (kis >= 25) return 'bg-gradient-to-r from-cyan-500/20 to-emerald-500/20 text-cyan-300 border-cyan-500/30';
  if (kis >= 15) return 'bg-white/8 text-white border-white/10';
  return 'bg-slate-800/50 text-slate-400 border-slate-700/50';
}

function stripColors(name: string): string {
  return name.replace(/\^[0-9a-zA-Z]/g, '');
}

export function PlayerStoryCard({ entry, rank, archetype, className }: PlayerStoryCardProps) {
  const name = stripColors(entry.name);
  const total = entry.carrier_kills + entry.push_kills + entry.crossfire_kills;
  const baseKills = entry.kills - total;

  // Segment widths (percentage of total kills)
  const pctBase = entry.kills > 0 ? (baseKills / entry.kills) * 100 : 100;
  const pctCarrier = entry.kills > 0 ? (entry.carrier_kills / entry.kills) * 100 : 0;
  const pctPush = entry.kills > 0 ? (entry.push_kills / entry.kills) * 100 : 0;
  const pctXfire = entry.kills > 0 ? (entry.crossfire_kills / entry.kills) * 100 : 0;

  return (
    <div
      className={cn(
        'glass-card rounded-[20px] p-5 border transition-all hover:-translate-y-0.5',
        kisGradientClass(entry.total_kis),
        className,
      )}
      style={{ animation: `fadeUp 0.5s ease-out ${rank * 0.06}s both` }}
    >
      {/* Archetype */}
      <div className="mb-3">
        <ArchetypeBadge archetype={archetype} size="sm" />
      </div>

      {/* Player name */}
      <button
        onClick={() => { navigateToPlayer(name); }}
        className="text-lg font-bold text-white hover:text-cyan-300 transition-colors truncate block w-full text-left"
      >
        {name}
      </button>

      {/* KIS score */}
      <div className="mt-3 flex items-baseline gap-3">
        <span className={cn(
          'inline-flex items-center rounded-xl border px-4 py-1.5 text-2xl font-black tabular-nums',
          kisBadgeStyle(entry.total_kis),
        )}>
          {entry.total_kis.toFixed(1)}
        </span>
        <span className="text-xs text-slate-500 uppercase tracking-wider">KIS</span>
      </div>

      {/* Stat grid */}
      <div className="mt-4 grid grid-cols-3 gap-2 text-center">
        <StatCell label="Kills" value={entry.kills} />
        <StatCell label="Avg" value={entry.avg_impact.toFixed(2)} />
        <StatCell label="Carrier" value={entry.carrier_kills} highlight={entry.carrier_kills > 0} color="text-rose-400" />
      </div>
      <div className="mt-2 grid grid-cols-2 gap-2 text-center">
        <StatCell label="Push" value={entry.push_kills} highlight={entry.push_kills > 0} color="text-violet-400" />
        <StatCell label="Crossfire" value={entry.crossfire_kills} highlight={entry.crossfire_kills > 0} color="text-cyan-400" />
      </div>

      {/* KIS breakdown bar */}
      <div className="mt-4">
        <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-1">Kill Breakdown</div>
        <div className="flex h-2 rounded-full overflow-hidden bg-slate-800/50">
          {pctBase > 0 && (
            <div className="bg-slate-500/60" style={{ width: `${pctBase}%` }} title={`Base: ${baseKills}`} />
          )}
          {pctCarrier > 0 && (
            <div className="bg-rose-500/70" style={{ width: `${pctCarrier}%` }} title={`Carrier: ${entry.carrier_kills}`} />
          )}
          {pctPush > 0 && (
            <div className="bg-violet-500/70" style={{ width: `${pctPush}%` }} title={`Push: ${entry.push_kills}`} />
          )}
          {pctXfire > 0 && (
            <div className="bg-cyan-500/70" style={{ width: `${pctXfire}%` }} title={`Crossfire: ${entry.crossfire_kills}`} />
          )}
        </div>
        {/* Legend */}
        <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 text-[9px] text-slate-500">
          <span className="flex items-center gap-1"><span className="inline-block w-2 h-2 rounded-full bg-slate-500/60" />Base</span>
          {pctCarrier > 0 && <span className="flex items-center gap-1"><span className="inline-block w-2 h-2 rounded-full bg-rose-500/70" />Carrier</span>}
          {pctPush > 0 && <span className="flex items-center gap-1"><span className="inline-block w-2 h-2 rounded-full bg-violet-500/70" />Push</span>}
          {pctXfire > 0 && <span className="flex items-center gap-1"><span className="inline-block w-2 h-2 rounded-full bg-cyan-500/70" />Crossfire</span>}
        </div>
      </div>
    </div>
  );
}

function StatCell({ label, value, highlight, color }: {
  label: string;
  value: number | string;
  highlight?: boolean;
  color?: string;
}) {
  return (
    <div className="rounded-lg bg-white/[0.03] px-2 py-1.5">
      <div className="text-[10px] text-slate-500 uppercase tracking-wider">{label}</div>
      <div className={cn(
        'text-sm font-bold tabular-nums',
        highlight && color ? color : 'text-white',
      )}>
        {value}
      </div>
    </div>
  );
}
