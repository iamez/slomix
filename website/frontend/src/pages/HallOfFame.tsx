import { useState } from 'react';
import {
  Trophy, Skull, Zap, Heart, Star, Target, Swords,
  Gamepad2, ShieldAlert, Bomb, Crown, Timer,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { useHallOfFame } from '../api/hooks';
import type { HallOfFameEntry } from '../api/types';
import { GlassCard } from '../components/GlassCard';
import { PageHeader } from '../components/PageHeader';
import { SelectFilter } from '../components/FilterBar';
import { Skeleton } from '../components/Skeleton';
import { cn } from '../lib/cn';
import { formatNumber } from '../lib/format';
import { navigateToPlayer } from '../lib/navigation';

const CATEGORY_META: Record<string, { label: string; icon: LucideIcon; color: string; bg: string }> = {
  most_active: { label: 'Most Active', icon: Gamepad2, color: 'text-blue-400', bg: 'bg-blue-400/10' },
  most_damage: { label: 'Most Damage', icon: Zap, color: 'text-amber-400', bg: 'bg-amber-400/10' },
  most_kills: { label: 'Most Kills', icon: Skull, color: 'text-rose-500', bg: 'bg-rose-500/10' },
  most_revives: { label: 'Most Revives', icon: Heart, color: 'text-cyan-500', bg: 'bg-cyan-500/10' },
  most_xp: { label: 'Most XP', icon: Star, color: 'text-amber-300', bg: 'bg-amber-300/10' },
  most_assists: { label: 'Most Assists', icon: Swords, color: 'text-purple-400', bg: 'bg-purple-400/10' },
  most_deaths: { label: 'Most Deaths', icon: ShieldAlert, color: 'text-slate-400', bg: 'bg-slate-500/10' },
  most_selfkills: { label: 'Most Selfkills', icon: Bomb, color: 'text-orange-400', bg: 'bg-orange-400/10' },
  most_full_selfkills: { label: 'Full Selfkills', icon: Bomb, color: 'text-red-400', bg: 'bg-red-400/10' },
  most_wins: { label: 'Most Wins', icon: Crown, color: 'text-emerald-400', bg: 'bg-emerald-400/10' },
  most_dpm: { label: 'Best DPM', icon: Target, color: 'text-indigo-400', bg: 'bg-indigo-400/10' },
  most_consecutive_games: { label: 'Longest Streak', icon: Timer, color: 'text-brand-cyan', bg: 'bg-brand-cyan/10' },
};

const PERIODS = [
  { value: 'all_time', label: 'All Time' },
  { value: '7d', label: 'Last 7 Days' },
  { value: '14d', label: 'Last 14 Days' },
  { value: '30d', label: 'Last 30 Days' },
  { value: '90d', label: 'Last 90 Days' },
  { value: 'season', label: 'Current Season' },
];

function PodiumCard({ category, entries }: { category: string; entries: HallOfFameEntry[] }) {
  const meta = CATEGORY_META[category] ?? { label: category, icon: Trophy, color: 'text-slate-400', bg: 'bg-slate-700/50' };
  const Icon = meta.icon;
  if (!entries?.length) return null;

  const top = entries[0];

  return (
    <GlassCard className="relative overflow-hidden group">
      <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
        <Icon className={cn('w-16 h-16', meta.color)} />
      </div>

      <div className="flex items-center gap-3 mb-4">
        <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center', meta.bg)}>
          <Icon className={cn('w-5 h-5', meta.color)} />
        </div>
        <div className="text-sm font-bold text-slate-400 uppercase tracking-wider">
          {meta.label}
        </div>
      </div>

      <div className="mb-4">
        <div className="text-3xl font-black text-white tracking-tight">
          {formatNumber(top.value)}
        </div>
        <div className="text-xs text-slate-500">{top.unit}</div>
      </div>

      <div className="space-y-1.5 mb-3">
        {entries.slice(0, 5).map((entry, i) => (
          <div key={entry.player_guid} className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2 min-w-0">
              <span className={cn('font-mono text-xs w-5',
                i === 0 ? 'text-amber-400' : i === 1 ? 'text-slate-300' : i === 2 ? 'text-amber-600' : 'text-slate-500',
              )}>
                {i + 1}
              </span>
              <button
                className="text-white hover:text-blue-400 transition truncate font-medium"
                onClick={(e) => { e.stopPropagation(); navigateToPlayer(entry.player_name); }}
              >
                {entry.player_name}
              </button>
            </div>
            <span className={cn('font-mono text-xs', i === 0 ? meta.color : 'text-slate-400')}>
              {formatNumber(entry.value)}
            </span>
          </div>
        ))}
      </div>
    </GlassCard>
  );
}

export default function HallOfFame() {
  const [period, setPeriod] = useState('all_time');
  const { data, isLoading, isError } = useHallOfFame(period);

  if (isLoading) {
    return (
      <div className="mt-6">
        <PageHeader title="Hall of Fame" subtitle="Top players across all categories" />
        <Skeleton variant="card" count={8} />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="mt-6">
        <PageHeader title="Hall of Fame" subtitle="Top players across all categories" />
        <div className="text-center text-red-400 py-12">Failed to load hall of fame.</div>
      </div>
    );
  }

  const cats = data?.categories ?? {};
  const categoryKeys = Object.keys(cats);

  return (
    <div className="mt-6">
      <PageHeader title="Hall of Fame" subtitle="Top players across all categories">
        <SelectFilter
          label="Period"
          value={period}
          onChange={setPeriod}
          options={PERIODS}
          allLabel="All Time"
        />
      </PageHeader>

      {categoryKeys.length === 0 ? (
        <div className="text-center text-slate-400 py-12">No hall of fame data available.</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {categoryKeys.map((cat) => (
            <PodiumCard key={cat} category={cat} entries={cats[cat]} />
          ))}
        </div>
      )}
    </div>
  );
}
