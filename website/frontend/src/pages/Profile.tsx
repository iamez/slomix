import { useMemo } from 'react';
import { AreaChart, Clock3, Crosshair, Link2, Shield, Skull, Star, Trophy, Zap } from 'lucide-react';
import { usePlayerForm, usePlayerProfile, usePlayerRounds } from '../api/hooks';
import type { PlayerProfileResponse, PlayerRound } from '../api/types';
import { ChartCanvas } from '../components/Chart';
import { DataTable, type Column } from '../components/DataTable';
import { GlassPanel } from '../components/GlassPanel';
import { PageHeader } from '../components/PageHeader';
import { PlayerLookup } from '../components/PlayerLookup';
import { Skeleton } from '../components/Skeleton';
import { cn } from '../lib/cn';
import { formatDate, formatNumber } from '../lib/format';
import { mapLevelshot, weaponIcon } from '../lib/game-assets';
import { navigateTo } from '../lib/navigation';

const roundColumns: Column<PlayerRound>[] = [
  {
    key: 'round_date',
    label: 'Date',
    render: (row) => formatDate(row.round_date),
    className: 'text-slate-400',
  },
  {
    key: 'map_name',
    label: 'Map',
    render: (row) => (
      <div className="flex items-center gap-3">
        <img
          src={mapLevelshot(row.map_name)}
          alt={row.map_name}
          className="h-9 w-9 rounded-2xl object-cover bg-slate-900/80"
          onError={(event) => { event.currentTarget.style.display = 'none'; }}
        />
        <div>
          <div className="font-semibold text-white">{row.map_name}</div>
          <div className="text-xs text-slate-500">Round {row.round_number}</div>
        </div>
      </div>
    ),
  },
  {
    key: 'kills',
    label: 'Kills',
    sortable: true,
    sortValue: (row) => row.kills,
    className: 'text-emerald-300 font-mono',
  },
  {
    key: 'deaths',
    label: 'Deaths',
    sortable: true,
    sortValue: (row) => row.deaths,
    className: 'text-rose-300 font-mono',
  },
  {
    key: 'dpm',
    label: 'DPM',
    sortable: true,
    sortValue: (row) => row.dpm,
    className: 'text-cyan-300 font-mono',
    render: (row) => row.dpm?.toFixed(1) ?? '--',
  },
  {
    key: 'result',
    label: 'Result',
    render: (row) => {
      const won = row.team === row.winner_team && row.winner_team !== 0;
      const lost = row.team !== row.winner_team && row.winner_team !== 0;
      if (won) return <span className="text-xs font-bold text-emerald-300">WIN</span>;
      if (lost) return <span className="text-xs font-bold text-rose-300">LOSS</span>;
      return <span className="text-xs text-slate-500">-</span>;
    },
  },
];

function getPlayerNameFromHash(): string {
  const queryString = window.location.hash.split('?')[1] ?? '';
  return new URLSearchParams(queryString).get('name') ?? '';
}

function KpiTile({
  label,
  value,
  icon: Icon,
  accent,
}: {
  label: string;
  value: string;
  icon: typeof Skull;
  accent: string;
}) {
  return (
    <div className="rounded-[22px] border border-white/8 bg-white/[0.03] p-4">
      <div className="flex items-center gap-2">
        <Icon className={`h-4 w-4 ${accent}`} />
        <span className="text-[11px] font-bold uppercase tracking-[0.2em] text-slate-500">{label}</span>
      </div>
      <div className={`mt-3 text-2xl font-black ${accent}`}>{value}</div>
    </div>
  );
}

function AchievementBadge({ achievement }: { achievement: PlayerProfileResponse['achievements'][0] }) {
  return (
    <div
      className={cn(
        'rounded-[22px] border p-4 transition',
        achievement.unlocked
          ? 'border-amber-300/20 bg-amber-300/8'
          : 'border-white/8 bg-white/[0.02] opacity-70',
      )}
    >
      <div className="text-2xl">{achievement.icon}</div>
      <div className={cn('mt-3 text-sm font-bold', achievement.unlocked ? 'text-white' : 'text-slate-500')}>
        {achievement.name}
      </div>
      <div className="mt-1 text-xs text-slate-500">{achievement.description}</div>
    </div>
  );
}

export default function Profile({ params }: { params?: Record<string, string> }) {
  const playerName = params?.name || getPlayerNameFromHash();
  const { data: profile, isLoading, isError } = usePlayerProfile(playerName);
  const { data: rounds } = usePlayerRounds(playerName);
  const { data: form } = usePlayerForm(playerName);

  const formChart = useMemo(() => {
    if (!form?.length) return null;
    return {
      labels: form.map((entry) => formatDate(entry.date)),
      datasets: [
        {
          data: form.map((entry) => entry.dpm),
          borderColor: '#22d3ee',
          backgroundColor: 'rgba(34,211,238,0.08)',
          fill: true,
          tension: 0.35,
          borderWidth: 2,
          pointRadius: 2,
        },
      ],
    };
  }, [form]);

  if (!playerName) {
    return (
      <div className="page-shell">
        <PageHeader
          title="Find a Player"
          subtitle="Profile is now the direct lookup surface when you already know the player you want."
          eyebrow="Players"
        />
        <PlayerLookup title="Search a player" subtitle="Type at least two characters to open a full player profile." />
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="page-shell">
        <PageHeader title={playerName} subtitle="Loading player profile..." eyebrow="Players" />
        <Skeleton variant="card" count={5} />
      </div>
    );
  }

  if (isError || !profile) {
    return (
      <div className="page-shell">
        <PageHeader title={playerName} subtitle="Player profile could not be loaded." eyebrow="Players" />
        <div className="text-center text-red-400 py-12">Player not found or failed to load.</div>
      </div>
    );
  }

  const stats = profile.stats;
  const latestRound = rounds?.[0] ?? null;
  const latestSessionHash = latestRound ? `#/session-detail/date/${encodeURIComponent(latestRound.round_date)}` : null;
  const initials = profile.name.slice(0, 2).toUpperCase();
  const unlockedCount = profile.achievements.filter((achievement) => achievement.unlocked).length;

  return (
    <div className="page-shell">
      <PageHeader
        title={profile.name}
        subtitle="Personal performance, recent form, and a direct path back into the latest session context."
        eyebrow="Players"
        badge={profile.discord_linked ? 'Discord linked' : 'Website profile'}
      >
        <button
          type="button"
          onClick={() => navigateTo('#/sessions2')}
          className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-xs font-bold text-slate-300 transition hover:text-white"
        >
          Back to Sessions
        </button>
      </PageHeader>

      <GlassPanel className="p-0 overflow-hidden">
        <div className="grid gap-0 lg:grid-cols-[0.85fr_1.15fr]">
          <div className="border-b border-white/8 p-6 md:p-7 lg:border-b-0 lg:border-r">
            <div className="flex items-start gap-4">
              <div className="flex h-18 w-18 items-center justify-center rounded-[26px] bg-gradient-to-br from-cyan-400 to-purple-500 text-2xl font-black text-slate-950">
                {initials}
              </div>
              <div className="min-w-0">
                <div className="section-kicker mb-2">Player Summary</div>
                <div className="text-3xl font-black text-white">{profile.name}</div>
                <div className="mt-2 flex flex-wrap gap-2">
                  {profile.aliases.slice(0, 3).map((alias) => (
                    <span key={alias} className="rounded-full border border-white/10 bg-white/6 px-3 py-1 text-xs font-bold text-slate-300">
                      {alias}
                    </span>
                  ))}
                </div>
                <div className="mt-4 text-sm text-slate-400">
                  Last seen {stats.last_seen ? formatDate(stats.last_seen) : 'unknown'}.
                </div>
              </div>
            </div>

            <div className="mt-6 grid gap-3 sm:grid-cols-2">
              <KpiTile label="Kills" value={formatNumber(stats.kills)} icon={Skull} accent="text-white" />
              <KpiTile label="DPM" value={formatNumber(stats.dpm)} icon={Zap} accent="text-cyan-300" />
              <KpiTile label="K/D" value={stats.kd.toFixed(2)} icon={Crosshair} accent="text-amber-300" />
              <KpiTile label="Win Rate" value={`${stats.win_rate}%`} icon={Trophy} accent="text-emerald-300" />
            </div>

            <div className="surface-divider mt-6 space-y-3">
              {latestSessionHash && (
                <button
                  type="button"
                  onClick={() => latestSessionHash && navigateTo(latestSessionHash)}
                  className="flex w-full items-center justify-between rounded-[20px] border border-white/8 bg-white/[0.03] px-4 py-3 text-left transition hover:bg-white/[0.06]"
                >
                  <div>
                    <div className="text-sm font-bold text-white">Latest played session</div>
                    <div className="text-xs text-slate-500">{latestRound ? formatDate(latestRound.round_date) : 'Unknown date'}</div>
                  </div>
                  <Link2 className="h-4 w-4 text-slate-500" />
                </button>
              )}

              <PlayerLookup compact placeholder="Search another player..." title="Search another player" subtitle="" />
            </div>
          </div>

          <div className="p-6 md:p-7">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <KpiTile label="Rounds" value={formatNumber(stats.games)} icon={Star} accent="text-purple-300" />
              <KpiTile label="Playtime" value={`${stats.playtime_hours}h`} icon={Clock3} accent="text-slate-200" />
              <KpiTile label="Damage" value={formatNumber(stats.damage)} icon={Shield} accent="text-rose-300" />
              <KpiTile label="XP" value={formatNumber(stats.total_xp)} icon={AreaChart} accent="text-cyan-300" />
            </div>

            <div className="mt-6 grid gap-4 xl:grid-cols-[1fr_0.9fr]">
              <div className="rounded-[22px] border border-white/8 bg-white/[0.03] p-5">
                <div className="section-kicker mb-2">Recent Form</div>
                <div className="text-xl font-black text-white">DPM over recent sessions</div>
                <div className="mt-4">
                  {formChart ? (
                    <ChartCanvas
                      type="line"
                      data={formChart}
                      height="220px"
                      options={{
                        plugins: { legend: { display: false } },
                        scales: {
                          x: { ticks: { color: '#64748b' }, grid: { color: 'rgba(255,255,255,0.04)' } },
                          y: { ticks: { color: '#64748b' }, grid: { color: 'rgba(255,255,255,0.04)' }, beginAtZero: true },
                        },
                      }}
                    />
                  ) : (
                    <div className="py-16 text-center text-sm text-slate-500">Recent form data unavailable.</div>
                  )}
                </div>
              </div>

              <div className="rounded-[22px] border border-white/8 bg-white/[0.03] p-5">
                <div className="section-kicker mb-2">Personal Taste</div>
                <div className="text-xl font-black text-white">Preferred loadout</div>
                <div className="mt-5 space-y-4">
                  <div className="rounded-[20px] border border-white/8 bg-slate-900/70 p-4">
                    <div className="text-[11px] font-bold uppercase tracking-[0.2em] text-slate-500">Favorite weapon</div>
                    <div className="mt-3 flex items-center gap-3">
                      {stats.favorite_weapon && weaponIcon(stats.favorite_weapon) ? (
                        <img src={weaponIcon(stats.favorite_weapon)!} alt="" className="h-7 object-contain opacity-80" style={{ filter: 'brightness(1.7)' }} />
                      ) : (
                        <Crosshair className="h-5 w-5 text-cyan-300" />
                      )}
                      <div className="text-lg font-black text-white">{stats.favorite_weapon || 'Unknown'}</div>
                    </div>
                  </div>

                  <div className="rounded-[20px] border border-white/8 bg-slate-900/70 p-4">
                    <div className="text-[11px] font-bold uppercase tracking-[0.2em] text-slate-500">Favorite map</div>
                    <div className="mt-3 flex items-center gap-3">
                      {stats.favorite_map ? (
                        <img
                          src={mapLevelshot(stats.favorite_map)}
                          alt={stats.favorite_map}
                          className="h-12 w-12 rounded-2xl object-cover bg-slate-950"
                          onError={(event) => { event.currentTarget.style.display = 'none'; }}
                        />
                      ) : (
                        <div className="h-12 w-12 rounded-2xl bg-slate-950" />
                      )}
                      <div className="text-lg font-black text-white">{stats.favorite_map || 'Unknown'}</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </GlassPanel>

      {profile.achievements.length > 0 && (
        <GlassPanel className="p-6">
          <div className="mb-4 flex items-end justify-between gap-4">
            <div>
              <div className="section-kicker mb-2">Achievements</div>
              <div className="text-2xl font-black text-white">Unlocked {unlockedCount} of {profile.achievements.length}</div>
            </div>
          </div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {profile.achievements.map((achievement) => (
              <AchievementBadge key={achievement.name} achievement={achievement} />
            ))}
          </div>
        </GlassPanel>
      )}

      {rounds && rounds.length > 0 && (
        <div>
          <div className="mb-4">
            <div className="section-kicker mb-2">Recent rounds</div>
            <div className="text-2xl font-black text-white">What the player has been doing lately</div>
          </div>
          <DataTable
            columns={roundColumns}
            data={rounds}
            keyFn={(row) => String(row.round_id)}
            defaultSort={{ key: 'round_date', dir: 'desc' }}
          />
        </div>
      )}
    </div>
  );
}
