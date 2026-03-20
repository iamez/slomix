import { useMemo } from 'react';
import { ArrowRight, CalendarDays, ChevronRight, Radar, Search, Trophy, Users, Zap } from 'lucide-react';
import { ChartCanvas } from '../components/Chart';
import { GlassCard } from '../components/GlassCard';
import { GlassPanel } from '../components/GlassPanel';
import { PlayerLookup } from '../components/PlayerLookup';
import { Skeleton } from '../components/Skeleton';
import { useLatestSession, useLiveStatus, useOverview, useQuickLeaders, useSeason, useTrends } from '../api/hooks';
import { mapLevelshot } from '../lib/game-assets';
import { formatNumber } from '../lib/format';
import { navigateTo, navigateToPlayer } from '../lib/navigation';

function mapLabel(name: string): string {
  return (name || 'Unknown').replace(/^maps[\\/]/, '').replace(/\.(bsp|pk3|arena)$/i, '').replace(/_/g, ' ');
}

function formatDuration(seconds: number): string {
  if (!seconds || seconds <= 0) return '--';
  const mins = Math.floor(seconds / 60);
  const hrs = Math.floor(mins / 60);
  const remMins = mins % 60;
  return hrs > 0 ? `${hrs}h ${remMins}m` : `${mins}m`;
}

function winnerTone(alliesWins: number, axisWins: number) {
  if (alliesWins > axisWins) return 'Allies edge';
  if (axisWins > alliesWins) return 'Axis edge';
  return 'Dead even';
}

function latestSessionHash(latest?: {
  session_id: number | null;
  date: string;
}) {
  if (!latest) return '#/sessions2';
  return latest.session_id
    ? `#/session-detail/${latest.session_id}`
    : `#/session-detail/date/${encodeURIComponent(latest.date)}`;
}

function HeroCard() {
  const { data: latest, isLoading } = useLatestSession();
  const { data: season } = useSeason();

  if (isLoading) {
    return <Skeleton variant="card" count={1} className="grid-cols-1" />;
  }

  if (!latest) {
    return (
      <GlassPanel className="p-8 md:p-10">
        <div className="section-kicker mb-2">Tonight / Start Here</div>
        <div className="text-4xl font-black text-white">No session available yet</div>
        <p className="mt-3 max-w-2xl text-slate-400">
          The session-first shell is ready. Once the next gaming session lands, this page becomes the fastest route into stats.
        </p>
      </GlassPanel>
    );
  }

  const topMap = latest.maps_played[0] || '';
  const scoreLabel = `${latest.allies_wins ?? 0} : ${latest.axis_wins ?? 0}`;

  return (
    <GlassPanel className="overflow-hidden p-0">
      <div className="grid gap-0 lg:grid-cols-[1.45fr_0.95fr]">
        <div className="relative overflow-hidden p-7 md:p-8">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(56,189,248,0.16),transparent_36%),radial-gradient(circle_at_bottom_left,rgba(168,85,247,0.14),transparent_28%)]" />
          <div className="relative">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <span className="rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 text-[11px] font-bold uppercase tracking-[0.2em] text-cyan-200">
                Tonight / Start Here
              </span>
              {season && (
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] font-bold text-slate-300">
                  {season.name}
                </span>
              )}
            </div>

            <div className="max-w-3xl">
              <h1 className="text-4xl font-black tracking-tight text-white md:text-6xl">
                Latest session, first.
              </h1>
              <p className="mt-4 text-base leading-7 text-slate-300 md:text-lg">
                Most visitors arrive to check what just happened. Put the last session, tonight&apos;s roster, and personal lookup in front of everything else.
              </p>
            </div>

            <div className="mt-6 flex flex-wrap items-center gap-2">
              <span className="metric-chip">{latest.formatted_date || latest.date}</span>
              <span className="metric-chip">{scoreLabel} score</span>
              <span className="metric-chip">{latest.round_count} rounds</span>
              <span className="metric-chip">{latest.player_count} players</span>
              {topMap && <span className="metric-chip">{mapLabel(topMap)}</span>}
            </div>

            <div className="mt-7 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => navigateTo(latestSessionHash(latest))}
                className="inline-flex items-center gap-2 rounded-2xl bg-cyan-400 px-5 py-3 text-sm font-black text-slate-950 transition hover:bg-cyan-300"
              >
                Open Last Session
                <ArrowRight className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={() => navigateTo('#/profile')}
                className="inline-flex items-center gap-2 rounded-2xl border border-white/10 bg-white/6 px-5 py-3 text-sm font-bold text-white transition hover:border-cyan-400/25 hover:bg-white/10"
              >
                Find My Stats
                <Users className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>

        <div className="border-t border-white/8 p-7 md:p-8 lg:border-l lg:border-t-0">
          <div className="section-kicker mb-2">Session Snapshot</div>
          <div className="text-3xl font-black text-white">{winnerTone(latest.allies_wins ?? 0, latest.axis_wins ?? 0)}</div>
          <p className="mt-2 text-sm text-slate-400">
            {latest.time_ago || 'Most recent tracked session'} {latest.start_time && latest.end_time ? `· ${latest.start_time} to ${latest.end_time}` : ''}
          </p>

          <div className="mt-5 grid grid-cols-2 gap-3">
            <Snapshot label="Duration" value={formatDuration(latest.duration_seconds)} />
            <Snapshot label="Kills" value={formatNumber(latest.total_kills || 0)} />
            <Snapshot label="Maps" value={formatNumber(latest.maps_played.length || latest.maps || 0)} />
            <Snapshot label="Roster" value={formatNumber(latest.player_names.length || latest.player_count)} />
          </div>

          <div className="surface-divider mt-6">
            <div className="text-sm font-bold text-white">Fast next steps</div>
            <div className="mt-3 space-y-2">
              <QuickLink title="Last session" subtitle="Open the newest session detail immediately" onClick={() => navigateTo(latestSessionHash(latest))} />
              <QuickLink title="Find my stats" subtitle="Jump straight into a player profile" onClick={() => navigateTo('#/profile')} />
              <QuickLink title="Browse archive" subtitle="Open sessions history and drill deeper" onClick={() => navigateTo('#/sessions2')} />
            </div>
          </div>
        </div>
      </div>
    </GlassPanel>
  );
}

function Snapshot({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[22px] border border-white/8 bg-white/[0.04] p-4">
      <div className="text-[11px] font-bold uppercase tracking-[0.22em] text-slate-500">{label}</div>
      <div className="mt-2 text-2xl font-black text-white">{value}</div>
    </div>
  );
}

function QuickLink({
  title,
  subtitle,
  onClick,
}: {
  title: string;
  subtitle: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center justify-between rounded-[20px] border border-white/8 bg-white/[0.03] px-4 py-3 text-left transition hover:border-cyan-400/20 hover:bg-white/[0.06]"
    >
      <div>
        <div className="text-sm font-bold text-white">{title}</div>
        <div className="text-xs text-slate-500">{subtitle}</div>
      </div>
      <ChevronRight className="h-4 w-4 text-slate-500" />
    </button>
  );
}

function ActionRail() {
  const { data: latest } = useLatestSession();

  return (
    <div className="grid gap-4 md:grid-cols-3">
      <ActionCard
        kicker="Fast Action"
        title="Last Session"
        body="Open tonight's session without sifting through archive density."
        onClick={() => navigateTo(latestSessionHash(latest))}
      />
      <ActionCard
        kicker="Fast Action"
        title="Find My Stats"
        body="Use player lookup when you already know who you want."
        onClick={() => navigateTo('#/profile')}
      />
      <ActionCard
        kicker="Fast Action"
        title="Session Archive"
        body="Browse older sessions only after the newest-session path is obvious."
        onClick={() => navigateTo('#/sessions2')}
      />
    </div>
  );
}

function ActionCard({
  kicker,
  title,
  body,
  onClick,
}: {
  kicker: string;
  title: string;
  body: string;
  onClick: () => void;
}) {
  return (
    <GlassCard onClick={onClick} className="p-5">
      <div className="section-kicker mb-2">{kicker}</div>
      <div className="text-2xl font-black text-white">{title}</div>
      <p className="mt-3 text-sm leading-6 text-slate-400">{body}</p>
      <div className="mt-6 inline-flex items-center gap-2 text-sm font-bold text-cyan-300">
        Open
        <ArrowRight className="h-4 w-4" />
      </div>
    </GlassCard>
  );
}

function TonightAtAGlance() {
  const { data: latest } = useLatestSession();
  const { data: overview } = useOverview();
  const { data: live } = useLiveStatus();

  const liveMap = live?.game_server.map ? mapLabel(live.game_server.map) : 'Offline';
  const livePlayers = live?.game_server.online ? `${live.game_server.player_count}/${live.game_server.max_players}` : '0';

  return (
    <section className="space-y-4">
      <div className="flex items-end justify-between gap-4">
        <div>
          <div className="section-kicker">Tonight At A Glance</div>
          <h2 className="mt-2 text-3xl font-black text-white">One quick scan, then move.</h2>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <CompactStat label="Rounds tonight" value={formatNumber(latest?.round_count || 0)} accent="text-cyan-300" />
        <CompactStat label="Players tonight" value={formatNumber(latest?.player_count || 0)} accent="text-white" />
        <CompactStat label="Top map" value={latest?.maps_played[0] ? mapLabel(latest.maps_played[0]) : '--'} accent="text-amber-300" />
        <CompactStat label="Total kills" value={formatNumber(latest?.total_kills || overview?.total_kills_14d || 0)} accent="text-rose-300" />
        <CompactStat label="Live server" value={liveMap} secondary={`${livePlayers} live`} accent={live?.game_server.online ? 'text-emerald-300' : 'text-slate-300'} />
      </div>
    </section>
  );
}

function CompactStat({
  label,
  value,
  secondary,
  accent,
}: {
  label: string;
  value: string;
  secondary?: string;
  accent: string;
}) {
  return (
    <GlassPanel className="p-5">
      <div className="text-[11px] font-bold uppercase tracking-[0.24em] text-slate-500">{label}</div>
      <div className={`mt-3 text-2xl font-black ${accent}`}>{value}</div>
      {secondary && <div className="mt-2 text-xs text-slate-500">{secondary}</div>}
    </GlassPanel>
  );
}

function InsightPreview() {
  const { data: trends, isLoading: trendsLoading } = useTrends(14);
  const { data: leaders } = useQuickLeaders();

  const trendData = useMemo(() => {
    if (!trends?.dates?.length) return null;
    return {
      labels: trends.dates.map((date) => new Date(`${date}T00:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })),
      datasets: [
        {
          data: trends.rounds,
          borderColor: '#22d3ee',
          backgroundColor: 'rgba(34,211,238,0.08)',
          fill: true,
          borderWidth: 2,
          tension: 0.35,
          pointRadius: 0,
        },
      ],
    };
  }, [trends]);

  const mapData = useMemo(() => {
    if (!trends?.map_distribution || typeof trends.map_distribution !== 'object') return null;
    const entries = Object.entries(trends.map_distribution)
      .map(([name, count]) => [mapLabel(name), Number(count)] as const)
      .filter(([, count]) => count > 0)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8);
    if (!entries.length) return null;
    const palette = ['#22d3ee', '#a78bfa', '#f472b6', '#fbbf24', '#34d399', '#fb923c', '#60a5fa', '#e879f9'];
    return {
      labels: entries.map(([name]) => name),
      datasets: [{
        data: entries.map(([, count]) => count),
        backgroundColor: entries.map((_, i) => `${palette[i % palette.length]}cc`),
        borderColor: entries.map((_, i) => palette[i % palette.length]),
        borderWidth: 1,
        borderRadius: 4,
      }],
    };
  }, [trends]);

  return (
    <section className="grid gap-4 xl:grid-cols-3">
      <GlassPanel className="p-6">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <div className="section-kicker">Preview</div>
            <h2 className="mt-2 text-2xl font-black text-white">Community rhythm</h2>
          </div>
          <button
            type="button"
            onClick={() => navigateTo('#/leaderboards')}
            className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-bold text-slate-300 transition hover:text-white"
          >
            More depth
          </button>
        </div>

        {trendsLoading ? (
          <Skeleton variant="card" count={1} className="grid-cols-1" />
        ) : trendData ? (
          <ChartCanvas
            type="line"
            data={trendData}
            height="240px"
            options={{
              plugins: { legend: { display: false } },
              scales: {
                x: { ticks: { color: '#64748b' }, grid: { color: 'rgba(255,255,255,0.04)' } },
                y: { ticks: { color: '#64748b' }, grid: { color: 'rgba(255,255,255,0.04)' }, beginAtZero: true },
              },
            }}
          />
        ) : (
          <div className="py-16 text-center text-sm text-slate-500">Trend preview unavailable.</div>
        )}
      </GlassPanel>

      <GlassPanel className="p-6">
        <div className="section-kicker">Preview</div>
        <h2 className="mt-2 text-2xl font-black text-white">Map distribution</h2>
        <p className="mt-1 text-xs text-slate-500">Most played maps (14 days)</p>
        <div className="mt-4">
          {trendsLoading ? (
            <Skeleton variant="card" count={1} className="grid-cols-1" />
          ) : mapData ? (
            <ChartCanvas
              type="bar"
              data={mapData}
              height="220px"
              options={{
                indexAxis: 'y' as const,
                plugins: { legend: { display: false } },
                scales: {
                  x: { ticks: { color: '#64748b' }, grid: { color: 'rgba(255,255,255,0.04)' }, beginAtZero: true },
                  y: { ticks: { color: '#cbd5e1', font: { size: 11 } }, grid: { display: false } },
                },
              }}
            />
          ) : (
            <div className="py-16 text-center text-sm text-slate-500">No map data available.</div>
          )}
        </div>
      </GlassPanel>

      <GlassPanel className="p-6">
        <div className="section-kicker">Preview</div>
        <h2 className="mt-2 text-2xl font-black text-white">Leaderboard snapshot</h2>
        <div className="mt-5 space-y-3">
          {(leaders?.dpm_sessions || []).slice(0, 5).map((entry) => (
            <button
              key={`${entry.guid}-${entry.rank}`}
              type="button"
              onClick={() => navigateToPlayer(entry.name)}
              className="flex w-full items-center justify-between rounded-[20px] border border-white/8 bg-white/[0.03] px-4 py-3 text-left transition hover:bg-white/[0.06]"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-cyan-400/10 text-cyan-300">
                  {entry.rank}
                </div>
                <div>
                  <div className="text-sm font-bold text-white">{entry.name}</div>
                  <div className="text-xs text-slate-500">DPM sessions</div>
                </div>
              </div>
              <div className="text-right">
                <div className="text-sm font-black text-white">{formatNumber(entry.value)}</div>
                <div className="text-xs text-slate-500">{entry.sessions || 0} sessions</div>
              </div>
            </button>
          ))}
        </div>
      </GlassPanel>
    </section>
  );
}

function DiscoveryStrip() {
  return (
    <section className="grid gap-4 xl:grid-cols-[1fr_1fr_1fr]">
      <GlassCard onClick={() => navigateTo('#/sessions2')} className="p-5">
        <div className="section-kicker mb-2">Browse</div>
        <div className="flex items-center gap-3">
          <CalendarDays className="h-5 w-5 text-cyan-300" />
          <div className="text-xl font-black text-white">Sessions archive</div>
        </div>
        <p className="mt-3 text-sm text-slate-400">
          Clean session history for when the latest session is not enough.
        </p>
      </GlassCard>

      <GlassCard onClick={() => navigateTo('#/profile')} className="p-5">
        <div className="section-kicker mb-2">People</div>
        <div className="flex items-center gap-3">
          <Users className="h-5 w-5 text-amber-300" />
          <div className="text-xl font-black text-white">Player profiles</div>
        </div>
        <p className="mt-3 text-sm text-slate-400">
          Search a player quickly when you already know whose stats you want.
        </p>
      </GlassCard>

      <GlassCard onClick={() => navigateTo('#/proximity')} className="p-5">
        <div className="section-kicker mb-2">Deep Analysis</div>
        <div className="flex items-center gap-3">
          <Radar className="h-5 w-5 text-purple-300" />
          <div className="text-xl font-black text-white">Advanced tools</div>
        </div>
        <p className="mt-3 text-sm text-slate-400">
          Proximity, viz, uploads, admin, and other specialist surfaces now live behind the main journey.
        </p>
      </GlassCard>
    </section>
  );
}

export default function Home() {
  return (
    <div className="page-shell">
      <HeroCard />
      <ActionRail />

      <section className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <TonightAtAGlance />
        <PlayerLookup
          title="Find My Stats"
          subtitle="Search a player immediately when you want your personal flow instead of the archive."
        />
      </section>

      <InsightPreview />
      <DiscoveryStrip />
    </div>
  );
}
