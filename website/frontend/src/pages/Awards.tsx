import { useState } from 'react';
import { useAwardsLeaderboard, useAwards } from '../api/hooks';
import type { AwardLeaderboardEntry, RoundAward } from '../api/types';
import { DataTable, type Column } from '../components/DataTable';
import { PageHeader } from '../components/PageHeader';
import { SelectFilter, FilterBar } from '../components/FilterBar';
import { Skeleton } from '../components/Skeleton';
import { cn } from '../lib/cn';
import { formatNumber } from '../lib/format';
import { navigateToPlayer } from '../lib/navigation';
import { mapLevelshot, medalIcon, weaponIcon } from '../lib/game-assets';

const AWARD_STYLES: Record<string, { emoji: string; medal?: string; color: string; bg: string }> = {
  combat: { emoji: '⚔️', medal: 'accuracy', color: 'text-rose-400', bg: 'bg-rose-500/10' },
  deaths: { emoji: '💀', color: 'text-slate-400', bg: 'bg-slate-700/50' },
  skills: { emoji: '🎯', medal: 'light_weapons', color: 'text-purple-400', bg: 'bg-purple-500/10' },
  weapons: { emoji: '🔫', color: 'text-blue-400', bg: 'bg-blue-500/10' },
  teamwork: { emoji: '🤝', medal: 'first_aid', color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
  objectives: { emoji: '🚩', medal: 'engineer', color: 'text-amber-400', bg: 'bg-amber-400/10' },
  timing: { emoji: '⏱️', color: 'text-cyan-400', bg: 'bg-cyan-500/10' },
};

/** Try to resolve a weapon icon from the award name (e.g. "Most SMG Kills" → mp40 icon) */
function awardWeaponIcon(awardName: string): string | null {
  const n = awardName.toLowerCase();
  const weaponKeywords: Record<string, string> = {
    smg: 'mp40', thompson: 'thompson', mp40: 'mp40', sten: 'sten',
    rifle: 'kar98', garand: 'garand', fg42: 'fg42', k43: 'k43',
    pistol: 'luger', grenade: 'grenade', knife: 'knife',
    panzer: 'panzerfaust', mortar: 'mortar', mg42: 'mg42',
    flamethrower: 'flamethrower', sniper: 'mauser', landmine: 'landmine',
    dynamite: 'dynamite', syringe: 'syringe',
  };
  for (const [keyword, weapon] of Object.entries(weaponKeywords)) {
    if (n.includes(keyword)) return weaponIcon(weapon);
  }
  return null;
}

function getCategoryKey(name: string): string {
  const n = name.toLowerCase();
  if (n.includes('damage') || n.includes('k/d') || n.includes('kill')) return 'combat';
  if (n.includes('death') || n.includes('selfkill') || n.includes('gib')) return 'deaths';
  if (n.includes('headshot') || n.includes('accuracy') || n.includes('first blood')) return 'skills';
  if (n.includes('smg') || n.includes('rifle') || n.includes('pistol') || n.includes('grenade') || n.includes('knife')) return 'weapons';
  if (n.includes('revive') || n.includes('heal') || n.includes('ammo') || n.includes('assist')) return 'teamwork';
  if (n.includes('dynamite') || n.includes('objective') || n.includes('planted') || n.includes('defused') || n.includes('stolen')) return 'objectives';
  if (n.includes('time') || n.includes('playtime') || n.includes('respawn')) return 'timing';
  return 'combat';
}

const TIME_OPTIONS = [
  { value: '', label: 'All Time' },
  { value: '7', label: 'Last 7 Days' },
  { value: '30', label: 'Last 30 Days' },
  { value: '90', label: 'Last 90 Days' },
];

const PAGE_SIZE = 24;

function rankBadge(rank: number) {
  if (rank === 1) return '🥇';
  if (rank === 2) return '🥈';
  if (rank === 3) return '🥉';
  return `#${rank}`;
}

const leaderColumns: Column<AwardLeaderboardEntry>[] = [
  {
    key: 'rank',
    label: 'Rank',
    className: 'w-16',
    render: (_row, i) => (
      <span className={cn(
        'font-mono font-bold',
        i === 0 ? 'text-amber-400' : i === 1 ? 'text-slate-300' : i === 2 ? 'text-amber-600' : 'text-slate-500',
      )}>
        {rankBadge(i + 1)}
      </span>
    ),
  },
  {
    key: 'player',
    label: 'Player',
    render: (row) => (
      <button
        className="font-semibold text-white hover:text-blue-400 transition"
        onClick={(e) => { e.stopPropagation(); navigateToPlayer(row.player); }}
      >
        {row.player}
      </button>
    ),
  },
  {
    key: 'award_count',
    label: 'Awards',
    sortable: true,
    sortValue: (row) => row.award_count,
    className: 'font-mono text-brand-cyan font-bold text-right',
    render: (row) => formatNumber(row.award_count),
  },
  {
    key: 'top_award',
    label: 'Most Won',
    className: 'text-slate-300',
    render: (row) => (
      <span>
        {row.top_award || '-'}
        {row.top_award_count ? <span className="text-xs text-slate-500 ml-1">({row.top_award_count}x)</span> : null}
      </span>
    ),
  },
];

function AwardExplorer({ awards }: { awards: RoundAward[] }) {
  if (!awards.length) {
    return <div className="text-center text-slate-500 py-10">No awards found for this filter.</div>;
  }

  const groups = new Map<string, { round_id: number; date: string; map: string; round_number: number; awards: RoundAward[] }>();
  for (const award of awards) {
    const key = `${award.round_id}:${award.date}:${award.map}:${award.round_number}`;
    if (!groups.has(key)) {
      groups.set(key, { round_id: award.round_id, date: award.date, map: award.map, round_number: award.round_number, awards: [] });
    }
    groups.get(key)!.awards.push(award);
  }

  return (
    <div className="space-y-4">
      {Array.from(groups.values()).map((round) => {
        const dateLabel = round.date
          ? new Date(round.date).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
          : '';
        return (
          <div key={`${round.round_id}-${round.date}`} className="glass-card rounded-xl overflow-hidden">
            <div className="px-5 py-3 bg-slate-800/50 border-b border-white/5 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <img src={mapLevelshot(round.map || '')} alt="" className="w-8 h-8 rounded object-cover bg-slate-700" onError={(e) => { e.currentTarget.style.display = 'none'; }} />
                <div>
                  <div className="font-bold text-white">{round.map || 'Unknown Map'}</div>
                  <div className="text-xs text-slate-500">Round {round.round_number} · {dateLabel}</div>
                </div>
              </div>
              <span className="text-xs px-2 py-1 rounded-full bg-blue-500/20 text-blue-400">
                {round.awards.length} awards
              </span>
            </div>
            <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-3">
              {round.awards.map((a, i) => {
                const cat = getCategoryKey(a.award);
                const style = AWARD_STYLES[cat] ?? AWARD_STYLES.combat;
                const wIcon = cat === 'weapons' ? awardWeaponIcon(a.award) : null;
                const mIcon = !wIcon && style.medal ? medalIcon(style.medal) : null;
                return (
                  <div key={`${a.award}-${a.player}-${i}`} className={cn('flex items-center gap-3 p-3 rounded-lg border border-white/5', style.bg)}>
                    {wIcon ? (
                      <img src={wIcon} alt="" className="w-7 h-5 object-contain opacity-80 shrink-0" style={{ filter: 'brightness(1.6)' }} />
                    ) : mIcon ? (
                      <img src={mIcon} alt="" className="w-6 h-6 object-contain shrink-0" />
                    ) : (
                      <span className="text-lg">{style.emoji}</span>
                    )}
                    <div className="min-w-0 flex-1">
                      <div className="text-xs text-slate-400 truncate">{a.award}</div>
                      <button
                        className="font-semibold text-white hover:text-blue-400 transition truncate block text-left w-full"
                        onClick={() => navigateToPlayer(a.player)}
                      >
                        {a.player}
                      </button>
                    </div>
                    <div className={cn('text-sm font-mono', style.color)}>{String(a.value ?? '-')}</div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function Awards() {
  const [days, setDays] = useState('');
  const [page, setPage] = useState(0);

  const { data: lbData, isLoading: lbLoading } = useAwardsLeaderboard({ days: days || undefined, limit: 20 });
  const { data: awardsData, isLoading: awardsLoading } = useAwards({ days: days || undefined, limit: PAGE_SIZE, offset: page * PAGE_SIZE });

  const isLoading = lbLoading || awardsLoading;
  const leaderboard = lbData?.leaderboard ?? [];
  const awards = awardsData?.awards ?? [];
  const total = awardsData?.total ?? 0;
  const totalPages = Math.ceil(total / PAGE_SIZE);

  if (isLoading) {
    return (
      <div className="mt-6">
        <PageHeader title="Awards" subtitle="Achievement tracking and explorer" />
        <Skeleton variant="card" count={6} />
      </div>
    );
  }

  return (
    <div className="mt-6">
      <PageHeader title="Awards" subtitle="Achievement tracking and explorer" />

      <FilterBar>
        <SelectFilter label="Time" value={days} onChange={(v) => { setDays(v); setPage(0); }} options={TIME_OPTIONS} allLabel="All Time" />
      </FilterBar>

      {/* KPI Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div className="glass-card rounded-xl p-4">
          <div className="text-xs text-slate-500 uppercase font-bold">Total Awards</div>
          <div className="text-2xl font-black text-brand-cyan mt-1">{formatNumber(total)}</div>
        </div>
        <div className="glass-card rounded-xl p-4">
          <div className="text-xs text-slate-500 uppercase font-bold">Unique Winners</div>
          <div className="text-2xl font-black text-brand-purple mt-1">{leaderboard.length}</div>
        </div>
        <div className="glass-card rounded-xl p-4">
          <div className="text-xs text-slate-500 uppercase font-bold">Top Winner</div>
          <div className="text-sm font-black text-brand-gold mt-1 truncate">{leaderboard[0]?.player ?? '-'}</div>
          <div className="text-[11px] text-slate-500">{leaderboard[0] ? `${formatNumber(leaderboard[0].award_count)} awards` : ''}</div>
        </div>
        <div className="glass-card rounded-xl p-4">
          <div className="text-xs text-slate-500 uppercase font-bold">Period</div>
          <div className="text-sm font-black text-white mt-1">{days ? `Last ${days} days` : 'All Time'}</div>
        </div>
      </div>

      {/* Leaderboard */}
      <div className="glass-panel rounded-xl p-5 mb-6">
        <h3 className="text-lg font-black text-white mb-4">Awards Leaderboard</h3>
        <DataTable
          columns={leaderColumns}
          data={leaderboard}
          keyFn={(row) => row.guid}
          onRowClick={(row) => navigateToPlayer(row.player)}
        />
      </div>

      {/* Explorer */}
      <div className="glass-panel rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-black text-white">Award Explorer</h3>
          <span className="text-xs text-slate-500">Grouped by round</span>
        </div>
        <AwardExplorer awards={awards} />

        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-2 mt-6">
            {page > 0 && (
              <button onClick={() => setPage(page - 1)} className="px-3 py-2 rounded-lg bg-slate-700 text-white hover:bg-slate-600 transition text-sm">
                Prev
              </button>
            )}
            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
              const p = Math.max(0, Math.min(page - 2, totalPages - 5)) + i;
              if (p >= totalPages) return null;
              return (
                <button
                  key={p}
                  onClick={() => setPage(p)}
                  className={cn('px-3 py-2 rounded-lg text-sm font-bold transition',
                    p === page ? 'bg-blue-500 text-white' : 'bg-slate-700 text-slate-300 hover:bg-slate-600')}
                >
                  {p + 1}
                </button>
              );
            })}
            {page < totalPages - 1 && (
              <button onClick={() => setPage(page + 1)} className="px-3 py-2 rounded-lg bg-slate-700 text-white hover:bg-slate-600 transition text-sm">
                Next
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
