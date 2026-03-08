import { useState, useMemo } from 'react';
import { ArrowLeft, Users, Map, Gamepad2, Clock, Trophy, Skull, Crosshair, Heart, Shield } from 'lucide-react';
import { useSessionDetail, useSessionByDate } from '../api/hooks';
import type { SessionDetailResponse, SessionMatch, SessionRound, SessionPlayer } from '../api/types';
import { DataTable, type Column } from '../components/DataTable';
import { GlassCard } from '../components/GlassCard';
import { PageHeader } from '../components/PageHeader';
import { Skeleton } from '../components/Skeleton';
import { cn } from '../lib/cn';
import { formatNumber } from '../lib/format';
import { navigateTo, navigateToPlayer } from '../lib/navigation';
import { mapLevelshot } from '../lib/game-assets';

type Tab = 'overview' | 'players' | 'rounds';

function formatDuration(seconds: number | null): string {
  const total = Number(seconds || 0);
  if (!total || total < 0) return '0:00';
  const mins = Math.floor(total / 60);
  const secs = Math.floor(total % 60);
  return `${mins}:${String(secs).padStart(2, '0')}`;
}

function mapLabel(name: string): string {
  return (name || 'Unknown').replace(/^maps[\\/]/, '').replace(/\.(bsp|pk3|arena)$/i, '').replace(/_/g, ' ');
}

function winnerLabel(team: number | null): string {
  if (team === 1) return 'Axis';
  if (team === 2) return 'Allies';
  return 'Tied';
}

function winnerColor(team: number | null): string {
  if (team === 1) return 'text-rose-400';
  if (team === 2) return 'text-blue-400';
  return 'text-slate-400';
}

// --- Tab Buttons ---
function TabBar({ active, onChange }: { active: Tab; onChange: (t: Tab) => void }) {
  const tabs: { key: Tab; label: string }[] = [
    { key: 'overview', label: 'Overview' },
    { key: 'players', label: 'Players' },
    { key: 'rounds', label: 'Rounds' },
  ];
  return (
    <div className="flex gap-1 bg-slate-800/80 rounded-lg p-0.5 mb-6">
      {tabs.map((t) => (
        <button
          key={t.key}
          onClick={() => onChange(t.key)}
          className={cn('px-4 py-2 rounded-md text-sm font-bold transition',
            active === t.key ? 'bg-blue-500/20 text-blue-400' : 'text-slate-400 hover:text-white')}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

// --- KPI Row ---
function KpiRow({ data }: { data: SessionDetailResponse }) {
  const totalDuration = data.matches.reduce((s, m) =>
    s + m.rounds.reduce((rs, r) => rs + (r.duration_seconds ?? 0), 0), 0);
  const totalKills = data.players.reduce((s, p) => s + p.kills, 0);
  const mapCount = data.matches.length;

  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
      <KpiCard icon={Gamepad2} label="Rounds" value={data.round_count} color="text-brand-cyan" />
      <KpiCard icon={Map} label="Maps" value={mapCount} color="text-brand-purple" />
      <KpiCard icon={Users} label="Players" value={data.player_count} color="text-brand-amber" />
      <KpiCard icon={Skull} label="Total Kills" value={formatNumber(totalKills)} color="text-brand-rose" />
      <KpiCard icon={Clock} label="Duration" value={formatDuration(totalDuration)} color="text-slate-300" />
    </div>
  );
}

function KpiCard({ icon: Icon, label, value, color }: {
  icon: typeof Users; label: string; value: string | number; color: string;
}) {
  return (
    <div className="glass-card rounded-xl p-4 text-center">
      <Icon className={cn('w-5 h-5 mx-auto mb-2', color)} />
      <div className={cn('text-xl font-black', color)}>{value}</div>
      <div className="text-[10px] text-slate-500 uppercase">{label}</div>
    </div>
  );
}

// --- Overview: Map Strip ---
function MapStrip({ matches, scoring }: { matches: SessionMatch[]; scoring: SessionDetailResponse['scoring'] }) {
  const scoringMaps = scoring?.maps ?? [];
  return (
    <div className="flex flex-wrap gap-3 mb-6">
      {matches.map((match, idx) => {
        const sm = scoringMaps[idx];
        const alliesScore = sm?.team_a_points ?? sm?.allies_score;
        const axisScore = sm?.team_b_points ?? sm?.axis_score;
        const hasScore = alliesScore != null && axisScore != null;
        return (
          <div key={`${match.map_name}-${idx}`}
               className="glass-card rounded-xl overflow-hidden min-w-[180px] border border-white/10">
            <div className="relative h-16 bg-slate-800">
              <img src={mapLevelshot(match.map_name)} alt="" className="w-full h-full object-cover opacity-60" onError={(e) => { e.currentTarget.style.display = 'none'; }} />
              <div className="absolute inset-0 bg-gradient-to-t from-slate-900 to-transparent" />
              <div className="absolute bottom-1.5 left-3 text-sm font-bold text-white drop-shadow-lg">{mapLabel(match.map_name)}</div>
            </div>
            <div className="p-4">
            <div className="text-[10px] text-slate-500 uppercase mb-1">{match.rounds.length} rounds</div>
            {hasScore && (
              <div className="flex items-center gap-2 text-xs">
                <span className="text-blue-400 font-bold">{alliesScore}</span>
                <span className="text-slate-600">—</span>
                <span className="text-rose-400 font-bold">{axisScore}</span>
              </div>
            )}
            <div className="mt-2 space-y-1">
              {match.rounds.map((r) => (
                <div key={r.round_id} className="flex items-center justify-between text-[11px]">
                  <span className="text-slate-400">R{r.round_number}</span>
                  <span className={winnerColor(r.winner_team)}>{winnerLabel(r.winner_team)}</span>
                  <span className="text-slate-500 font-mono">{formatDuration(r.duration_seconds)}</span>
                </div>
              ))}
            </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// --- Overview: Scoring Banner ---
function ScoringBanner({ scoring }: { scoring: SessionDetailResponse['scoring'] }) {
  if (!scoring?.available || scoring.team_a_total == null) return null;
  const alliesLead = (scoring.team_a_total ?? 0) > (scoring.team_b_total ?? 0);
  const tied = scoring.team_a_total === scoring.team_b_total;
  return (
    <div className="glass-card rounded-xl p-5 mb-6 flex items-center justify-center gap-6">
      <div className="text-center">
        <div className="text-[10px] text-slate-500 uppercase mb-1">Allies</div>
        <div className={cn('text-3xl font-black', alliesLead && !tied ? 'text-blue-400' : 'text-slate-300')}>
          {scoring.team_a_total}
        </div>
      </div>
      <div className="text-slate-600 text-2xl font-bold">vs</div>
      <div className="text-center">
        <div className="text-[10px] text-slate-500 uppercase mb-1">Axis</div>
        <div className={cn('text-3xl font-black', !alliesLead && !tied ? 'text-rose-400' : 'text-slate-300')}>
          {scoring.team_b_total}
        </div>
      </div>
    </div>
  );
}

// --- Players Tab ---
const playerColumns: Column<SessionPlayer>[] = [
  {
    key: 'player_name',
    label: 'Player',
    render: (row) => (
      <button onClick={() => navigateToPlayer(row.player_name)}
              className="text-blue-400 hover:text-blue-300 font-semibold text-left">
        {row.player_name}
      </button>
    ),
  },
  { key: 'kills', label: 'Kills', sortable: true, sortValue: (r) => r.kills, className: 'font-mono text-white' },
  { key: 'deaths', label: 'Deaths', sortable: true, sortValue: (r) => r.deaths, className: 'font-mono text-slate-400' },
  { key: 'kd', label: 'K/D', sortable: true, sortValue: (r) => r.kd, className: 'font-mono text-emerald-400', render: (r) => r.kd.toFixed(2) },
  { key: 'dpm', label: 'DPM', sortable: true, sortValue: (r) => r.dpm, className: 'font-mono text-cyan-400', render: (r) => r.dpm.toFixed(1) },
  { key: 'damage_given', label: 'Damage', sortable: true, sortValue: (r) => r.damage_given, className: 'font-mono text-white', render: (r) => formatNumber(r.damage_given) },
  { key: 'headshot_kills', label: 'HS', sortable: true, sortValue: (r) => r.headshot_kills, className: 'font-mono text-amber-400' },
  { key: 'revives_given', label: 'Revives', sortable: true, sortValue: (r) => r.revives_given, className: 'font-mono text-green-400' },
  { key: 'gibs', label: 'Gibs', sortable: true, sortValue: (r) => r.gibs, className: 'font-mono text-purple-400' },
  { key: 'kill_assists', label: 'Assists', sortable: true, sortValue: (r) => r.kill_assists, className: 'font-mono text-slate-400' },
];

function PlayersTab({ players }: { players: SessionPlayer[] }) {
  return (
    <div className="glass-panel rounded-xl p-0 overflow-hidden">
      <DataTable
        columns={playerColumns}
        data={players}
        keyFn={(r) => r.player_guid}
        defaultSort={{ key: 'dpm', dir: 'desc' }}
        stickyHeader
        onRowClick={(row) => navigateToPlayer(row.player_name)}
      />
    </div>
  );
}

// --- Rounds Tab ---
function RoundsTab({ matches }: { matches: SessionMatch[] }) {
  const allRounds = matches.flatMap((m) =>
    m.rounds.map((r) => ({ ...r, match_map: m.map_name })),
  );

  const roundColumns: Column<SessionRound & { match_map: string }>[] = [
    { key: 'round_id', label: 'ID', className: 'text-slate-500 font-mono text-xs' },
    { key: 'match_map', label: 'Map', render: (r) => (
      <span className="text-white font-semibold inline-flex items-center gap-2">
        <img src={mapLevelshot(r.match_map)} alt="" className="w-5 h-5 rounded-sm object-cover bg-slate-700" onError={(e) => { e.currentTarget.style.display = 'none'; }} />
        {mapLabel(r.match_map)}
      </span>
    ) },
    { key: 'round_number', label: 'Round', render: (r) => <span className="text-slate-300">R{r.round_number}</span> },
    {
      key: 'winner_team',
      label: 'Winner',
      render: (r) => <span className={winnerColor(r.winner_team)}>{winnerLabel(r.winner_team)}</span>,
    },
    {
      key: 'score',
      label: 'Score',
      render: (r) => (
        r.allies_score != null ? (
          <span>
            <span className="text-blue-400">{r.allies_score}</span>
            <span className="text-slate-600"> — </span>
            <span className="text-rose-400">{r.axis_score}</span>
          </span>
        ) : <span className="text-slate-600">—</span>
      ),
    },
    {
      key: 'duration_seconds',
      label: 'Duration',
      sortable: true,
      sortValue: (r) => r.duration_seconds ?? 0,
      className: 'font-mono text-slate-300',
      render: (r) => formatDuration(r.duration_seconds),
    },
    { key: 'round_date', label: 'Date', className: 'text-slate-500 text-xs' },
    { key: 'round_time', label: 'Time', className: 'text-slate-500 text-xs' },
  ];

  return (
    <div className="glass-panel rounded-xl p-0 overflow-hidden">
      <DataTable
        columns={roundColumns}
        data={allRounds}
        keyFn={(r) => String(r.round_id)}
        stickyHeader
      />
    </div>
  );
}

// --- Main Page ---
export default function SessionDetail({ params }: { params?: Record<string, string> }) {
  const [tab, setTab] = useState<Tab>('overview');

  const sessionId = params?.sessionId ? Number(params.sessionId) : null;
  const sessionDate = params?.sessionDate ?? null;

  const { data: byId, isLoading: idLoading, isError: idError } = useSessionDetail(sessionId);
  const { data: byDate, isLoading: dateLoading, isError: dateError } = useSessionByDate(
    !sessionId ? sessionDate : null,
  );

  const data = byId ?? byDate;
  const isLoading = (sessionId ? idLoading : dateLoading);
  const isError = (sessionId ? idError : dateError);

  if (isLoading) {
    return (
      <div className="mt-6">
        <PageHeader title="Session Detail" subtitle="Loading..." />
        <Skeleton variant="card" count={4} />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="mt-6">
        <PageHeader title="Session Detail" subtitle="Session not found" />
        <div className="text-center py-12">
          <div className="text-red-400 text-lg mb-4">Session not found</div>
          <button onClick={() => navigateTo('#/sessions2')}
                  className="px-4 py-2 rounded-lg bg-blue-500/20 text-blue-400 font-bold text-sm hover:bg-blue-500/30 transition">
            Back to Sessions
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="mt-6">
      <PageHeader
        title={`Session ${data.session_id ?? ''}`}
        subtitle={data.date ? `${data.date} · ${data.round_count} rounds · ${data.player_count} players` : `${data.round_count} rounds`}
      >
        <button onClick={() => navigateTo('#/sessions2')}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 text-slate-300 text-sm font-bold hover:text-white transition">
          <ArrowLeft className="w-4 h-4" />
          Back
        </button>
      </PageHeader>

      <KpiRow data={data} />
      <TabBar active={tab} onChange={setTab} />

      {tab === 'overview' && (
        <>
          <ScoringBanner scoring={data.scoring} />
          <MapStrip matches={data.matches} scoring={data.scoring} />

          {/* Top performers */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <TopPerformer
              label="MVP (DPM)"
              color="text-yellow-500"
              icon={Trophy}
              players={data.players}
              getValue={(p) => p.dpm}
              formatValue={(v) => v.toFixed(1)}
            />
            <TopPerformer
              label="Most Kills"
              color="text-rose-400"
              icon={Skull}
              players={data.players}
              getValue={(p) => p.kills}
              formatValue={(v) => String(v)}
            />
            <TopPerformer
              label="Most Revives"
              color="text-emerald-400"
              icon={Heart}
              players={data.players}
              getValue={(p) => p.revives_given}
              formatValue={(v) => String(v)}
            />
          </div>

          {/* Quick players table */}
          <h3 className="text-sm font-bold text-slate-500 uppercase tracking-wider mb-3">All Players</h3>
          <PlayersTab players={data.players} />
        </>
      )}

      {tab === 'players' && <PlayersTab players={data.players} />}

      {tab === 'rounds' && <RoundsTab matches={data.matches} />}
    </div>
  );
}

function TopPerformer({ label, color, icon: Icon, players, getValue, formatValue }: {
  label: string;
  color: string;
  icon: typeof Trophy;
  players: SessionPlayer[];
  getValue: (p: SessionPlayer) => number;
  formatValue: (v: number) => string;
}) {
  if (players.length === 0) return null;
  const top = players.reduce((best, p) => getValue(p) > getValue(best) ? p : best, players[0]);
  return (
    <GlassCard onClick={() => navigateToPlayer(top.player_name)}>
      <div className="flex items-center gap-3">
        <Icon className={cn('w-6 h-6', color)} />
        <div>
          <div className="text-[10px] text-slate-500 uppercase">{label}</div>
          <div className="text-lg font-black text-white">{top.player_name}</div>
          <div className={cn('text-sm font-bold', color)}>{formatValue(getValue(top))}</div>
        </div>
      </div>
    </GlassCard>
  );
}
