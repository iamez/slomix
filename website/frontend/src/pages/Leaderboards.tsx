import { useState } from 'react';
import { Trophy, Skull, Crosshair, Heart, Target, Bomb, Zap, Gamepad2 } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { useLeaderboard } from '../api/hooks';
import type { LeaderboardEntry } from '../api/types';
import { DataTable, type Column } from '../components/DataTable';
import { PageHeader } from '../components/PageHeader';
import { SelectFilter, FilterBar } from '../components/FilterBar';
import { Skeleton } from '../components/Skeleton';
import { cn } from '../lib/cn';
import { formatNumber } from '../lib/format';
import { navigateToPlayer } from '../lib/navigation';
import { rankIcon } from '../lib/game-assets';

interface StatDef {
  key: string;
  label: string;
  icon: LucideIcon;
  color: string;
  valueLabel: string;
}

const STATS: StatDef[] = [
  { key: 'dpm', label: 'DPM', icon: Zap, color: 'text-blue-500', valueLabel: 'DPM' },
  { key: 'kills', label: 'Kills', icon: Skull, color: 'text-rose-500', valueLabel: 'Kills' },
  { key: 'kd', label: 'K/D Ratio', icon: Crosshair, color: 'text-purple-500', valueLabel: 'K/D' },
  { key: 'damage', label: 'Damage', icon: Zap, color: 'text-amber-400', valueLabel: 'Damage' },
  { key: 'headshots', label: 'Headshots', icon: Target, color: 'text-emerald-500', valueLabel: 'Headshots' },
  { key: 'revives', label: 'Revives', icon: Heart, color: 'text-cyan-500', valueLabel: 'Revives' },
  { key: 'accuracy', label: 'Accuracy', icon: Target, color: 'text-green-400', valueLabel: 'Accuracy' },
  { key: 'gibs', label: 'Gibs', icon: Bomb, color: 'text-orange-500', valueLabel: 'Gibs' },
  { key: 'games', label: 'Games Played', icon: Gamepad2, color: 'text-indigo-400', valueLabel: 'Rounds' },
];

const PERIODS = [
  { value: '7d', label: 'Last 7 days' },
  { value: '30d', label: 'Last 30 days' },
  { value: 'season', label: 'Season' },
  { value: 'all', label: 'All time' },
];

function rankBadge(rank: number) {
  if (rank === 1) return <span className="text-amber-400 font-black">🥇 1</span>;
  if (rank === 2) return <span className="text-slate-300 font-black">🥈 2</span>;
  if (rank === 3) return <span className="text-amber-600 font-black">🥉 3</span>;
  if (rank <= 11) {
    return (
      <span className="inline-flex items-center gap-1.5 text-slate-400 font-mono">
        <img src={rankIcon(rank)} alt="" className="w-4 h-4 object-contain" />
        #{rank}
      </span>
    );
  }
  return <span className="text-slate-500 font-mono">#{rank}</span>;
}

const columns: Column<LeaderboardEntry>[] = [
  {
    key: 'rank',
    label: 'Rank',
    className: 'w-16',
    render: (row) => rankBadge(row.rank),
  },
  {
    key: 'name',
    label: 'Player',
    render: (row) => (
      <button
        className="font-semibold text-white hover:text-blue-400 transition"
        onClick={(e) => { e.stopPropagation(); navigateToPlayer(row.name); }}
      >
        {row.name}
      </button>
    ),
  },
  {
    key: 'value',
    label: 'Value',
    sortable: true,
    sortValue: (row) => row.value,
    className: 'font-mono text-brand-cyan font-bold',
    render: (row) => formatNumber(row.value),
  },
  {
    key: 'rounds',
    label: 'Rounds',
    sortable: true,
    sortValue: (row) => row.rounds,
    className: 'text-slate-400',
    render: (row) => formatNumber(row.rounds),
  },
  {
    key: 'kd',
    label: 'K/D',
    sortable: true,
    sortValue: (row) => row.kd,
    className: 'text-slate-400 font-mono',
    render: (row) => row.kd.toFixed(2),
  },
  {
    key: 'kills',
    label: 'Kills',
    sortable: true,
    sortValue: (row) => row.kills,
    className: 'text-slate-400',
    render: (row) => formatNumber(row.kills),
  },
  {
    key: 'deaths',
    label: 'Deaths',
    sortable: true,
    sortValue: (row) => row.deaths,
    className: 'text-slate-400',
    render: (row) => formatNumber(row.deaths),
  },
];

export default function Leaderboards() {
  const [stat, setStat] = useState('dpm');
  const [period, setPeriod] = useState('30d');
  const { data, isLoading, isError } = useLeaderboard(stat, period);

  const activeDef = STATS.find((s) => s.key === stat);
  const Icon = activeDef?.icon ?? Trophy;

  if (isLoading) {
    return (
      <div className="mt-6">
        <PageHeader title="Leaderboards" subtitle="Top players by stat" />
        <Skeleton variant="table" count={10} />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="mt-6">
        <PageHeader title="Leaderboards" subtitle="Top players by stat" />
        <div className="text-center text-red-400 py-12">Failed to load leaderboard.</div>
      </div>
    );
  }

  return (
    <div className="mt-6">
      <PageHeader title="Leaderboards" subtitle="Top players by stat">
        <div className="flex items-center gap-2">
          <Icon className={cn('w-5 h-5', activeDef?.color)} />
          <span className="text-sm font-bold text-white">{activeDef?.valueLabel}</span>
        </div>
      </PageHeader>

      <FilterBar>
        <div className="flex flex-wrap gap-2">
          {STATS.map((s) => {
            const SI = s.icon;
            return (
              <button
                key={s.key}
                onClick={() => setStat(s.key)}
                className={cn(
                  'px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5',
                  stat === s.key
                    ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                    : 'bg-slate-800 text-slate-400 border border-white/5 hover:bg-slate-700',
                )}
              >
                <SI className="w-3.5 h-3.5" />
                {s.label}
              </button>
            );
          })}
        </div>
        <label className="flex items-center gap-2">
          <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Period</span>
          <select
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            className="bg-slate-800 border border-white/10 text-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500/50"
          >
            {PERIODS.map((p) => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </select>
        </label>
      </FilterBar>

      <div className="glass-panel rounded-xl p-0 overflow-hidden">
        <DataTable
          columns={columns}
          data={data ?? []}
          keyFn={(row) => row.guid}
          onRowClick={(row) => navigateToPlayer(row.name)}
          defaultSort={{ key: 'value', dir: 'desc' }}
        />
      </div>
    </div>
  );
}
