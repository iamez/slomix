import { useMemo, useState } from 'react';
import {
  ArrowLeft,
  Clock,
  Crosshair,
  Gamepad2,
  Map,
  Radar,
  Shield,
  Skull,
  Swords,
  Target,
  Trophy,
  Users,
  Zap,
} from 'lucide-react';
import {
  useSessionByDate,
  useSessionDetail,
  useSessionGraphs,
  useRoundPlayerDetails,
  useRoundViz,
  useWeaponsByPlayer,
  useProximityTradeSummary,
  useProximityTradeEvents,
  useProximityDuos,
  useProximityTeamplay,
  useProximityMovers,
  usePlayerVsStats,
} from '../api/hooks';
import type {
  ProximityMoverEntry,
  ProximityScope,
  ProximityTeamplayEntry,
  RoundPlayerDetailResponse,
  RoundVizData,
  SessionDetailResponse,
  SessionGraphsResponse,
  SessionMatch,
  SessionPlayer,
  SessionRound,
  VizPlayer,
  VsStatsEntry,
  WeaponPlayerStat,
} from '../api/types';
import { ChartCanvas } from '../components/Chart';
import { DataTable, type Column } from '../components/DataTable';
import { EmptyState } from '../components/EmptyState';
import { GlassCard } from '../components/GlassCard';
import { GlassPanel } from '../components/GlassPanel';
import { PageHeader } from '../components/PageHeader';
import { Skeleton } from '../components/Skeleton';
import { cn } from '../lib/cn';
import { formatNumber, formatDurationMS as formatDuration } from '../lib/format';
import { mapLevelshot } from '../lib/game-assets';
import { navigateTo, navigateToPlayer } from '../lib/navigation';

type Tab = 'summary' | 'players' | 'teamplay' | 'charts';

type PlayerListRow = {
  guid: string;
  name: string;
  kills: number;
  deaths: number;
  dpm: number;
  damageGiven: number;
  damageReceived: number;
  selfKills: number;
  deniedSeconds: number;
  timeDeadSeconds: number;
  alivePct: number | null;
  playedPct: number | null;
  revives: number;
  assists: number;
  gibs: number;
  accuracy: number | null;
  source: 'session' | 'round';
  sessionPlayer?: SessionPlayer;
  roundPlayer?: VizPlayer;
};

const CHART_COLORS = [
  'rgba(59, 130, 246, 0.7)',
  'rgba(244, 63, 94, 0.7)',
  'rgba(16, 185, 129, 0.7)',
  'rgba(245, 158, 11, 0.7)',
  'rgba(168, 85, 247, 0.7)',
  'rgba(20, 184, 166, 0.7)',
  'rgba(251, 113, 133, 0.7)',
  'rgba(132, 204, 22, 0.7)',
];


function formatDenied(seconds: number | null | undefined): string {
  const total = Math.max(0, Math.round(Number(seconds || 0)));
  const mins = Math.floor(total / 60);
  const secs = total % 60;
  return `${mins}:${String(secs).padStart(2, '0')}`;
}

function formatPct(value: number | null | undefined): string {
  return value == null || !Number.isFinite(value) ? '--' : `${value.toFixed(1)}%`;
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

function buildScopeParams(sessionDate: string | null, round: SessionRound | null): ProximityScope | undefined {
  if (!sessionDate) return undefined;
  return {
    session_date: sessionDate,
    round_start_unix: round?.round_start_unix ?? undefined,
  };
}

function ScopePill({
  activeRound,
  expandedMap,
  onClear,
}: {
  activeRound: SessionRound | null;
  expandedMap: string | null;
  onClear: () => void;
}) {
  if (activeRound) {
    return (
      <div className="glass-panel rounded-xl px-4 py-3 mb-6 flex items-center gap-3">
        <Target className="w-4 h-4 text-cyan-400" />
        <div className="text-sm text-slate-300">
          Scoped to <strong className="text-white">{mapLabel(activeRound.map_name)} R{activeRound.round_number}</strong>
        </div>
        <button
          onClick={onClear}
          className="ml-auto text-xs font-bold text-slate-400 hover:text-white transition"
        >
          Clear Scope
        </button>
      </div>
    );
  }

  if (expandedMap) {
    return (
      <div className="glass-panel rounded-xl px-4 py-3 mb-6 flex items-center gap-3">
        <Map className="w-4 h-4 text-violet-400" />
        <div className="text-sm text-slate-300">
          Viewing <strong className="text-white">{mapLabel(expandedMap)}</strong> — full session stats
        </div>
        <button
          onClick={onClear}
          className="ml-auto text-xs font-bold text-slate-400 hover:text-white transition"
        >
          Clear
        </button>
      </div>
    );
  }

  return (
    <div className="glass-panel rounded-xl px-4 py-3 text-sm text-slate-300 mb-6">
      Scope: <strong className="text-white">Full session</strong>
    </div>
  );
}

function TabBar({ active, onChange }: { active: Tab; onChange: (t: Tab) => void }) {
  const tabs: Array<{ key: Tab; label: string }> = [
    { key: 'summary', label: 'Summary' },
    { key: 'players', label: 'Player Stats' },
    { key: 'teamplay', label: 'Teamplay' },
    { key: 'charts', label: 'Charts' },
  ];

  return (
    <div className="flex flex-wrap gap-1 bg-slate-800/80 rounded-lg p-1 mb-6">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          onClick={() => onChange(tab.key)}
          className={cn(
            'px-4 py-2 rounded-md text-sm font-bold transition',
            active === tab.key ? 'bg-blue-500/20 text-blue-400' : 'text-slate-400 hover:text-white',
          )}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

function KpiRow({ data, activeRound }: { data: SessionDetailResponse; activeRound: SessionRound | null }) {
  const totalDuration = activeRound
    ? activeRound.duration_seconds ?? 0
    : data.matches.reduce((sum, match) => (
      sum + match.rounds.reduce((roundSum, round) => roundSum + (round.duration_seconds ?? 0), 0)
    ), 0);
  const totalKills = activeRound
    ? 0
    : data.players.reduce((sum, player) => sum + player.kills, 0);
  const mapCount = activeRound ? 1 : data.matches.length;
  const playerCount = data.player_count;

  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
      <KpiCard icon={Gamepad2} label={activeRound ? 'Round' : 'Rounds'} value={activeRound ? `R${activeRound.round_number}` : data.round_count} color="text-cyan-400" />
      <KpiCard icon={Map} label="Maps" value={mapCount} color="text-violet-400" />
      <KpiCard icon={Users} label="Players" value={playerCount} color="text-amber-400" />
      <KpiCard icon={Skull} label={activeRound ? 'Round Kills' : 'Session Kills'} value={activeRound ? '--' : formatNumber(totalKills)} color="text-rose-400" />
      <KpiCard icon={Clock} label="Duration" value={formatDuration(totalDuration)} color="text-slate-200" />
    </div>
  );
}

function KpiCard({ icon: Icon, label, value, color }: { icon: typeof Users; label: string; value: string | number; color: string }) {
  return (
    <GlassCard className="!cursor-default">
      <Icon className={cn('w-5 h-5 mx-auto mb-2', color)} />
      <div className={cn('text-xl font-black', color)}>{value}</div>
      <div className="text-[10px] text-slate-500 uppercase">{label}</div>
    </GlassCard>
  );
}

function ScoringBanner({ scoring }: { scoring: SessionDetailResponse['scoring'] }) {
  if (!scoring?.available || scoring.team_a_total == null || scoring.team_b_total == null) return null;
  const alliesLead = scoring.team_a_total > scoring.team_b_total;
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

function MapStrip({
  matches,
  activeRoundId,
  expandedMapIndex,
  onSelectMap,
  onSelectRound,
  onClearRound,
}: {
  matches: SessionMatch[];
  activeRoundId: number | null;
  expandedMapIndex: number | null;
  onSelectMap: (index: number) => void;
  onSelectRound: (roundId: number) => void;
  onClearRound: () => void;
}) {
  const expanded = expandedMapIndex !== null ? matches[expandedMapIndex] : null;

  return (
    <div className="mb-6">
      {/* Thumbnail row */}
      <div className="flex flex-wrap gap-3 mb-3">
        {matches.map((match, idx) => {
          const isExpanded = expandedMapIndex === idx;
          const hasActiveRound = isExpanded && activeRoundId !== null;
          return (
            <button
              key={`${match.map_name}-${idx}`}
              onClick={() => onSelectMap(idx)}
              className={cn(
                'relative rounded-xl overflow-hidden border transition group',
                isExpanded
                  ? 'border-cyan-400/60 ring-1 ring-cyan-400/30'
                  : 'border-white/10 hover:border-white/25',
              )}
              style={{ width: 160, height: 80 }}
            >
              <img
                src={mapLevelshot(match.map_name)}
                alt={match.map_name || 'Map'}
                className="w-full h-full object-cover opacity-60 group-hover:opacity-75 transition"
                onError={(e) => { e.currentTarget.style.display = 'none'; }}
              />
              <div className="absolute inset-0 bg-gradient-to-t from-slate-900/90 via-slate-900/30 to-transparent" />
              {/* Round count badge */}
              <div className="absolute top-2 right-2 bg-slate-900/80 text-[10px] text-slate-400 rounded px-1.5 py-0.5">
                {match.rounds.length}R
              </div>
              {/* Map name */}
              <div className="absolute bottom-2 left-2.5 text-xs font-bold text-white drop-shadow-lg leading-tight">
                {mapLabel(match.map_name)}
              </div>
              {/* Active indicator */}
              {hasActiveRound && (
                <div className="absolute top-2 left-2 w-1.5 h-1.5 rounded-full bg-cyan-400" />
              )}
            </button>
          );
        })}
      </div>

      {/* Round timeline — only for expanded map */}
      {expanded && (
        <div className="glass-panel rounded-xl px-4 py-3 flex flex-wrap items-center gap-2">
          <span className="text-xs text-slate-500 uppercase tracking-wider mr-1">
            {mapLabel(expanded.map_name)}
          </span>
          {expanded.rounds.map((round) => (
            <button
              key={round.round_id}
              onClick={() => onSelectRound(round.round_id)}
              className={cn(
                'flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-bold transition',
                activeRoundId === round.round_id
                  ? 'border-cyan-400/60 bg-cyan-500/10 text-cyan-300'
                  : 'border-white/10 bg-slate-900/40 text-slate-300 hover:border-white/20 hover:text-white',
              )}
            >
              <span>R{round.round_number}</span>
              <span className={cn('text-[10px]', winnerColor(round.winner_team))}>
                {winnerLabel(round.winner_team)}
              </span>
              {round.duration_seconds ? (
                <span className="text-slate-500 font-mono">{formatDuration(round.duration_seconds)}</span>
              ) : null}
            </button>
          ))}
          <button
            onClick={onClearRound}
            className={cn(
              'rounded-lg border px-3 py-1.5 text-xs font-bold transition',
              activeRoundId === null
                ? 'border-violet-400/60 bg-violet-500/10 text-violet-300'
                : 'border-white/10 bg-slate-900/40 text-slate-400 hover:text-white hover:border-white/20',
            )}
          >
            Full Map
          </button>
        </div>
      )}
    </div>
  );
}

function TopPerformer({
  label,
  color,
  icon: Icon,
  players,
  getValue,
  formatValue,
}: {
  label: string;
  color: string;
  icon: typeof Trophy;
  players: SessionPlayer[];
  getValue: (p: SessionPlayer) => number;
  formatValue: (v: number) => string;
}) {
  if (players.length === 0) return null;
  const top = players.reduce((best, player) => (getValue(player) > getValue(best) ? player : best), players[0]);

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

function SummaryTab({
  data,
  activeRoundId,
  expandedMapIndex,
  onSelectMap,
  onSelectRound,
  onClearRound,
}: {
  data: SessionDetailResponse;
  activeRoundId: number | null;
  expandedMapIndex: number | null;
  onSelectMap: (index: number) => void;
  onSelectRound: (roundId: number) => void;
  onClearRound: () => void;
}) {
  return (
    <>
      <ScoringBanner scoring={data.scoring} />
      <MapStrip
        matches={data.matches}
        activeRoundId={activeRoundId}
        expandedMapIndex={expandedMapIndex}
        onSelectMap={onSelectMap}
        onSelectRound={onSelectRound}
        onClearRound={onClearRound}
      />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <TopPerformer label="MVP (DPM)" color="text-yellow-500" icon={Trophy} players={data.players} getValue={(p) => p.dpm} formatValue={(value) => value.toFixed(1)} />
        <TopPerformer label="Most Kills" color="text-rose-400" icon={Skull} players={data.players} getValue={(p) => p.kills} formatValue={(value) => String(value)} />
        <TopPerformer label="Most Revives" color="text-emerald-400" icon={Shield} players={data.players} getValue={(p) => p.revives_given} formatValue={(value) => String(value)} />
      </div>
      <div className="glass-card rounded-xl p-5 mb-6">
        <div className="text-sm font-bold text-white mb-3">Session Pulse</div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 text-sm">
          <ScopeMetric icon={Zap} label="Top DPM" value={data.players[0] ? `${data.players[0].player_name} · ${data.players[0].dpm.toFixed(1)}` : '--'} />
          <ScopeMetric icon={Swords} label="Best K/D" value={data.players[0] ? `${[...data.players].sort((a, b) => b.kd - a.kd)[0].kd.toFixed(2)}` : '--'} />
          <ScopeMetric icon={Crosshair} label="Most Gibs" value={String(Math.max(...data.players.map((player) => player.gibs), 0))} />
          <ScopeMetric icon={Clock} label="Most Denied" value={formatDenied(Math.max(...data.players.map((player) => player.denied_playtime ?? 0), 0))} />
        </div>
      </div>
      {/* Rounds table */}
      <RoundsTable matches={data.matches} activeRoundId={activeRoundId} onSelectRound={onSelectRound} />
    </>
  );
}

function ScopeMetric({ icon: Icon, label, value }: { icon: typeof Zap; label: string; value: string }) {
  return (
    <div className="glass-panel rounded-lg p-3">
      <div className="flex items-center gap-2 text-slate-500 text-[11px] uppercase">
        <Icon className="w-4 h-4 text-cyan-400" />
        {label}
      </div>
      <div className="mt-2 text-white font-bold">{value}</div>
    </div>
  );
}

function RoundsTable({
  matches,
  activeRoundId,
  onSelectRound,
}: {
  matches: SessionMatch[];
  activeRoundId: number | null;
  onSelectRound: (roundId: number) => void;
}) {
  const allRounds = matches.flatMap((match) => match.rounds.map((round) => ({ ...round, match_map: match.map_name })));

  if (allRounds.length === 0) {
    return <EmptyState message="No rounds found for this session." />;
  }

  return (
    <div className="glass-panel rounded-xl overflow-hidden">
      <table className="w-full text-left">
        <thead>
          <tr className="border-b border-white/10 bg-white/5 text-xs uppercase text-slate-500">
            <th className="px-4 py-3">Map</th>
            <th className="px-4 py-3">Round</th>
            <th className="px-4 py-3">Winner</th>
            <th className="px-4 py-3">Score</th>
            <th className="px-4 py-3">Duration</th>
            <th className="px-4 py-3">Date</th>
            <th className="px-4 py-3 text-right">Scope</th>
          </tr>
        </thead>
        <tbody>
          {allRounds.map((round) => (
            <tr key={round.round_id} className="border-b border-white/5 hover:bg-white/5">
              <td className="px-4 py-3 text-white font-semibold">{mapLabel(round.match_map)}</td>
              <td className="px-4 py-3 text-slate-300">R{round.round_number}</td>
              <td className={cn('px-4 py-3', winnerColor(round.winner_team))}>{winnerLabel(round.winner_team)}</td>
              <td className="px-4 py-3 text-slate-300">
                {round.allies_score != null ? (
                  <>
                    <span className="text-blue-400">{round.allies_score}</span>
                    <span className="text-slate-600"> — </span>
                    <span className="text-rose-400">{round.axis_score}</span>
                  </>
                ) : '—'}
              </td>
              <td className="px-4 py-3 text-slate-400 font-mono">{formatDuration(round.duration_seconds)}</td>
              <td className="px-4 py-3 text-slate-500 text-xs">
                {[round.round_date, round.round_time].filter(Boolean).join(' · ') || '--'}
              </td>
              <td className="px-4 py-3 text-right">
                <button
                  onClick={() => onSelectRound(round.round_id)}
                  className={cn(
                    'px-3 py-1.5 rounded-lg text-xs font-bold transition',
                    activeRoundId === round.round_id
                      ? 'bg-cyan-500/20 text-cyan-300'
                      : 'bg-slate-800 text-slate-300 hover:text-white',
                  )}
                >
                  {activeRoundId === round.round_id ? 'Scoped' : 'Scope'}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const playerColumns: Column<PlayerListRow>[] = [
  {
    key: 'name',
    label: 'Player',
    render: (row) => (
      <button onClick={() => navigateToPlayer(row.name)} className="text-blue-400 hover:text-blue-300 font-semibold text-left">
        {row.name}
      </button>
    ),
  },
  { key: 'kills', label: 'Kills', sortable: true, sortValue: (row) => row.kills, className: 'font-mono text-white' },
  { key: 'deaths', label: 'Deaths', sortable: true, sortValue: (row) => row.deaths, className: 'font-mono text-slate-400' },
  { key: 'dpm', label: 'DPM', sortable: true, sortValue: (row) => row.dpm, className: 'font-mono text-cyan-400', render: (row) => row.dpm.toFixed(1) },
  { key: 'damage', label: 'Dmg', sortable: true, sortValue: (row) => row.damageGiven, className: 'font-mono text-white', render: (row) => formatNumber(row.damageGiven) },
  { key: 'selfKills', label: 'Self', sortable: true, sortValue: (row) => row.selfKills, className: 'font-mono text-amber-400' },
  { key: 'deniedSeconds', label: 'Denied', sortable: true, sortValue: (row) => row.deniedSeconds, className: 'font-mono text-rose-300', render: (row) => formatDenied(row.deniedSeconds) },
  { key: 'alivePct', label: 'Alive%', sortable: true, sortValue: (row) => row.alivePct ?? -1, className: 'font-mono text-emerald-300', render: (row) => formatPct(row.alivePct) },
  { key: 'playedPct', label: 'Played%', sortable: true, sortValue: (row) => row.playedPct ?? -1, className: 'font-mono text-violet-300', render: (row) => formatPct(row.playedPct) },
];

function VsStatsPanel({
  preys,
  enemies,
  loading,
}: {
  preys: VsStatsEntry[];
  enemies: VsStatsEntry[];
  loading: boolean;
}) {
  if (loading) return <Skeleton variant="card" count={1} />;
  if (!preys.length && !enemies.length) return null;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4">
      <div className="glass-panel rounded-xl p-4">
        <div className="flex items-center gap-2 mb-3">
          <Crosshair className="w-4 h-4 text-emerald-400" />
          <div className="text-sm font-bold text-white">Easiest Preys</div>
        </div>
        {preys.length ? (
          <div className="space-y-2">
            {preys.map((entry, i) => (
              <div key={entry.opponent_guid ?? entry.opponent_name} className="flex items-center justify-between rounded-lg bg-slate-900/50 px-3 py-2 text-sm">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-slate-600 text-xs font-mono w-4">{i + 1}</span>
                  <button
                    onClick={() => navigateToPlayer(entry.opponent_name)}
                    className="text-white font-semibold truncate hover:text-cyan-400 transition"
                  >
                    {entry.opponent_name}
                  </button>
                </div>
                <div className="flex items-center gap-3 text-xs shrink-0">
                  <span className="text-emerald-400 font-mono">{entry.kills}K</span>
                  <span className="text-rose-400 font-mono">{entry.deaths}D</span>
                  <span className="text-slate-400 font-mono">{entry.kd.toFixed(1)}</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-xs text-slate-500 py-2">No prey data</div>
        )}
      </div>
      <div className="glass-panel rounded-xl p-4">
        <div className="flex items-center gap-2 mb-3">
          <Skull className="w-4 h-4 text-rose-400" />
          <div className="text-sm font-bold text-white">Worst Enemies</div>
        </div>
        {enemies.length ? (
          <div className="space-y-2">
            {enemies.map((entry, i) => (
              <div key={entry.opponent_guid ?? entry.opponent_name} className="flex items-center justify-between rounded-lg bg-slate-900/50 px-3 py-2 text-sm">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-slate-600 text-xs font-mono w-4">{i + 1}</span>
                  <button
                    onClick={() => navigateToPlayer(entry.opponent_name)}
                    className="text-white font-semibold truncate hover:text-cyan-400 transition"
                  >
                    {entry.opponent_name}
                  </button>
                </div>
                <div className="flex items-center gap-3 text-xs shrink-0">
                  <span className="text-emerald-400 font-mono">{entry.kills}K</span>
                  <span className="text-rose-400 font-mono">{entry.deaths}D</span>
                  <span className="text-slate-400 font-mono">{entry.kd.toFixed(1)}</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-xs text-slate-500 py-2">No enemy data</div>
        )}
      </div>
    </div>
  );
}

function SessionPlayerDetail({
  row,
  weaponMastery,
  loading,
  vsPreys,
  vsEnemies,
  vsLoading,
}: {
  row: PlayerListRow | null;
  weaponMastery: WeaponPlayerStat | null;
  loading: boolean;
  vsPreys: VsStatsEntry[];
  vsEnemies: VsStatsEntry[];
  vsLoading: boolean;
}) {
  if (!row) return null;

  return (
    <div className="glass-card rounded-xl p-5 mt-6">
      <div className="flex items-center justify-between gap-3 mb-4">
        <div>
          <div className="text-xs uppercase tracking-wider text-slate-500">Player Focus</div>
          <div className="text-xl font-black text-white">{row.name}</div>
        </div>
        <button onClick={() => navigateToPlayer(row.name)} className="text-sm text-cyan-400 hover:text-white transition">
          Open Profile
        </button>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <DetailMetric label="Kills" value={String(row.kills)} />
        <DetailMetric label="DPM" value={row.dpm.toFixed(1)} />
        <DetailMetric label="Self Kills" value={String(row.selfKills)} />
        <DetailMetric label="Time Denied" value={formatDenied(row.deniedSeconds)} />
      </div>
      {loading ? (
        <Skeleton variant="card" count={1} />
      ) : (
        <div className="glass-panel rounded-xl p-4">
          <div className="text-sm font-bold text-white mb-3">Weapon Mastery</div>
          {weaponMastery?.weapons?.length ? (
            <div className="space-y-2">
              {weaponMastery.weapons.map((weapon) => (
                <div key={weapon.weapon_key} className="flex items-center justify-between rounded-lg bg-slate-900/50 px-3 py-2 text-sm">
                  <div>
                    <div className="font-semibold text-white">{weapon.name}</div>
                    <div className="text-xs text-slate-500">
                      {weapon.kills > 0 ? `${weapon.kills} kills · ` : ''}{weapon.accuracy.toFixed(1)}% acc
                    </div>
                  </div>
                  <div className="text-right text-xs">
                    {weapon.headshots > 0 && (
                      <div className="text-cyan-300">{weapon.headshots} HS</div>
                    )}
                    <div className="text-slate-500">{weapon.hits}/{weapon.shots}</div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState message="No weapon mastery data for this player." className="!py-6" />
          )}
        </div>
      )}
      <VsStatsPanel preys={vsPreys} enemies={vsEnemies} loading={vsLoading} />
    </div>
  );
}

function RoundPlayerDetail({ detail, loading, vsPreys, vsEnemies, vsLoading }: { detail: RoundPlayerDetailResponse | null | undefined; loading: boolean; vsPreys: VsStatsEntry[]; vsEnemies: VsStatsEntry[]; vsLoading: boolean }) {
  if (loading) return <Skeleton variant="card" count={2} />;
  if (!detail) return <EmptyState message="Round drilldown is not available for this player." className="!py-6" />;

  return (
    <div className="glass-card rounded-xl p-5 mt-6">
      <div className="flex items-center gap-3 mb-4">
        <Radar className="w-5 h-5 text-cyan-400" />
        <div>
          <div className="text-xs uppercase tracking-wider text-slate-500">Round Drilldown</div>
          <div className="text-xl font-black text-white">{detail.player_name}</div>
        </div>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <DetailMetric label="Kills" value={String(detail.combat.kills)} />
        <DetailMetric label="Damage" value={formatNumber(detail.combat.damage_given)} />
        <DetailMetric label="Self Kills" value={String(detail.misc.self_kills)} />
        <DetailMetric label="Time Denied" value={formatDenied(detail.time.denied_playtime)} />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <GlassPanel className="!p-4">
          <div className="text-sm font-bold text-white mb-3">Combat</div>
          <DetailList
            items={[
              ['Deaths', String(detail.combat.deaths)],
              ['Headshots', String(detail.combat.headshots)],
              ['Gibs', String(detail.combat.gibs)],
              ['Accuracy', `${detail.combat.accuracy.toFixed(1)}%`],
              ['Revives Given', String(detail.support.revives_given)],
              ['Times Revived', String(detail.support.times_revived)],
            ]}
          />
        </GlassPanel>
        <GlassPanel className="!p-4">
          <div className="text-sm font-bold text-white mb-3">Objectives & Time</div>
          <DetailList
            items={[
              ['Objective Steals', String(detail.objectives.stolen)],
              ['Objective Returns', String(detail.objectives.returned)],
              ['Dynos Planted', String(detail.objectives.dynamites_planted)],
              ['Dynos Defused', String(detail.objectives.dynamites_defused)],
              ['Dead Minutes', detail.time.dead_minutes.toFixed(1)],
              ['Played Seconds', String(detail.time.played_seconds)],
            ]}
          />
        </GlassPanel>
      </div>
      <div className="glass-panel rounded-xl p-4 mt-4">
        <div className="text-sm font-bold text-white mb-3">Weapons</div>
        {detail.weapons.length ? (
          <div className="space-y-2">
            {detail.weapons.map((weapon) => (
              <div key={weapon.name} className="flex items-center justify-between rounded-lg bg-slate-900/50 px-3 py-2 text-sm">
                <div className="font-semibold text-white">{weapon.name}</div>
                <div className="text-right text-xs text-slate-400">
                  {weapon.kills}K / {weapon.deaths}D · {weapon.accuracy.toFixed(1)}%
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState message="No weapon detail found for this round." className="!py-6" />
        )}
      </div>
      <VsStatsPanel preys={vsPreys} enemies={vsEnemies} loading={vsLoading} />
    </div>
  );
}

function DetailMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="glass-panel rounded-lg p-3">
      <div className="text-[11px] text-slate-500 uppercase">{label}</div>
      <div className="text-white font-bold mt-1">{value}</div>
    </div>
  );
}

function DetailList({ items }: { items: Array<[string, string]> }) {
  return (
    <div className="space-y-2 text-sm">
      {items.map(([label, value]) => (
        <div key={label} className="flex items-center justify-between border-b border-white/5 pb-2 last:border-0 last:pb-0">
          <span className="text-slate-400">{label}</span>
          <span className="text-white font-semibold">{value}</span>
        </div>
      ))}
    </div>
  );
}

function PlayersTab({
  rows,
  selectedGuid,
  onSelectPlayer,
}: {
  rows: PlayerListRow[];
  selectedGuid: string | null;
  onSelectPlayer: (guid: string) => void;
}) {
  if (!rows.length) return <EmptyState message="No player data for this scope." />;

  return (
    <div className="glass-panel rounded-xl p-0 overflow-hidden">
      <DataTable
        columns={playerColumns}
        data={rows}
        keyFn={(row) => row.guid}
        defaultSort={{ key: 'dpm', dir: 'desc' }}
        stickyHeader
        onRowClick={(row) => onSelectPlayer(row.guid)}
        rowClassName={(row) => cn(selectedGuid === row.guid && 'bg-cyan-500/10')}
      />
    </div>
  );
}

function SignalsTab({
  loading,
  summary,
  events,
  duos,
  teamplay,
  movers,
}: {
  loading: boolean;
  summary: ReturnType<typeof useProximityTradeSummary>['data'];
  events: ReturnType<typeof useProximityTradeEvents>['data'];
  duos: ReturnType<typeof useProximityDuos>['data'];
  teamplay: ReturnType<typeof useProximityTeamplay>['data'];
  movers: ReturnType<typeof useProximityMovers>['data'];
}) {
  if (loading) return <Skeleton variant="card" count={4} />;

  const hasContent = Boolean(
    summary?.ready
      || events?.events?.length
      || duos?.duos?.length
      || teamplay?.crossfire_kills?.length
      || teamplay?.sync?.length
      || teamplay?.focus_survival?.length
      || movers?.distance?.length
      || movers?.sprint?.length
      || movers?.reaction?.length
      || movers?.survival?.length,
  );

  if (!hasContent) {
    return <EmptyState message="No proximity signal data is available for this scope yet." />;
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <DetailMetric label="Trade Opps" value={String(summary?.trade_opportunities ?? 0)} />
        <DetailMetric label="Trade Success" value={String(summary?.trade_success ?? 0)} />
        <DetailMetric label="Missed Trades" value={String(summary?.missed_trade_candidates ?? 0)} />
        <DetailMetric label="Isolation Deaths" value={String(summary?.isolation_deaths ?? 0)} />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <GlassPanel className="!p-5">
          <div className="text-sm font-bold text-white mb-4">Recent Trade Events</div>
          {events?.events?.length ? (
            <div className="space-y-2">
              {events.events.slice(0, 10).map((event, index) => (
                <div key={`${event.round_id ?? event.date}-${index}`} className="rounded-lg bg-slate-900/50 px-3 py-2 text-sm">
                  <div className="font-semibold text-white">{event.victim} vs {event.killer}</div>
                  <div className="text-xs text-slate-400">
                    {event.map} R{event.round} · success {event.success} · attempts {event.attempts} · missed {event.missed}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState message="No trade events for this scope." className="!py-6" />
          )}
        </GlassPanel>

        <GlassPanel className="!p-5">
          <div className="text-sm font-bold text-white mb-4">Top Synergy Duos</div>
          {duos?.duos?.length ? (
            <div className="space-y-2">
              {duos.duos.map((duo, index) => (
                <div key={`${duo.player1_name ?? duo.player1}-${duo.player2_name ?? duo.player2}-${index}`} className="rounded-lg bg-slate-900/50 px-3 py-2 text-sm">
                  <div className="font-semibold text-white">
                    {duo.player1_name || duo.player1} + {duo.player2_name || duo.player2}
                  </div>
                  <div className="text-xs text-slate-400">
                    {duo.crossfire_kills ?? duo.crossfires ?? 0} crossfires · {Math.round(duo.avg_delay_ms ?? 0)}ms avg delay
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState message="No duo signal data for this scope." className="!py-6" />
          )}
        </GlassPanel>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <SignalList title="Crossfire Kills" rows={teamplay?.crossfire_kills ?? []} valueLabel="crossfire_kills" formatValue={(row) => String(row.crossfire_kills ?? row.count ?? 0)} />
        <SignalList title="Team Sync" rows={teamplay?.sync ?? []} valueLabel="sync" formatValue={(row) => String(row.crossfire_participations ?? row.count ?? 0)} />
        <SignalList title="Focus Survival" rows={teamplay?.focus_survival ?? []} valueLabel="survival" formatValue={(row) => formatPct(row.survival_rate_pct)} />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <MoverList title="Distance Leaders" rows={movers?.distance ?? []} formatValue={(row) => `${(row.total_distance ?? 0).toFixed(1)}u`} />
        <MoverList title="Sprint Leaders" rows={movers?.sprint ?? []} formatValue={(row) => formatPct(row.sprint_pct)} />
        <MoverList title="Reaction Leaders" rows={movers?.reaction ?? []} formatValue={(row) => row.reaction_ms != null ? `${Math.round(row.reaction_ms)}ms` : '--'} />
        <MoverList title="Survival Leaders" rows={movers?.survival ?? []} formatValue={(row) => row.duration_ms != null ? formatDuration(row.duration_ms / 1000) : '--'} />
      </div>
    </div>
  );
}

function SignalList({
  title,
  rows,
  valueLabel: _valueLabel,
  formatValue,
}: {
  title: string;
  rows: ProximityTeamplayEntry[];
  valueLabel?: string;
  formatValue: (row: ProximityTeamplayEntry) => string;
}) {
  return (
    <GlassPanel className="!p-5">
      <div className="text-sm font-bold text-white mb-4">{title}</div>
      {rows.length ? (
        <div className="space-y-2">
          {rows.map((row, index) => (
            <div key={`${row.name}-${index}`} className="flex items-center justify-between rounded-lg bg-slate-900/50 px-3 py-2 text-sm">
              <span className="font-semibold text-white">{row.name}</span>
              <span className="text-cyan-300 font-mono">{formatValue(row)}</span>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState message="No data in this signal set." className="!py-6" />
      )}
    </GlassPanel>
  );
}

function MoverList({
  title,
  rows,
  formatValue,
}: {
  title: string;
  rows: ProximityMoverEntry[];
  formatValue: (row: ProximityMoverEntry) => string;
}) {
  return (
    <GlassPanel className="!p-5">
      <div className="text-sm font-bold text-white mb-4">{title}</div>
      {rows.length ? (
        <div className="space-y-2">
          {rows.map((row, index) => (
            <div key={`${row.name}-${index}`} className="flex items-center justify-between rounded-lg bg-slate-900/50 px-3 py-2 text-sm">
              <span className="font-semibold text-white">{row.name}</span>
              <span className="text-violet-300 font-mono">{formatValue(row)}</span>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState message="No mover data in this scope." className="!py-6" />
      )}
    </GlassPanel>
  );
}

function SessionViz({ data }: { data: SessionGraphsResponse }) {
  const topPlayers = data.players.slice(0, 8);
  const labels = topPlayers[0]?.dpm_timeline?.map((point) => point.label) ?? [];
  const timelineData = {
    labels,
    datasets: topPlayers.map((player, index) => ({
      label: player.name,
      data: player.dpm_timeline.map((point) => point.dpm),
      borderColor: CHART_COLORS[index % CHART_COLORS.length],
      backgroundColor: CHART_COLORS[index % CHART_COLORS.length],
      borderWidth: 2,
      tension: 0.3,
    })),
  };

  const aggressionData = {
    labels: topPlayers.map((player) => player.name),
    datasets: [
      {
        label: 'Aggression',
        data: topPlayers.map((player) => player.playstyle.aggression),
        backgroundColor: 'rgba(59, 130, 246, 0.7)',
      },
      {
        label: 'Discipline',
        data: topPlayers.map((player) => 100 - player.advanced_metrics.damage_efficiency),
        backgroundColor: 'rgba(16, 185, 129, 0.6)',
      },
    ],
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <GlassCard className="!cursor-default">
          <div className="text-sm font-bold text-white mb-4">DPM Timeline</div>
          {labels.length ? (
            <ChartCanvas
              type="line"
              data={timelineData}
              height={320}
              options={{
                plugins: { legend: { labels: { color: '#94a3b8', font: { size: 10 } } } },
                scales: {
                  x: { ticks: { color: '#94a3b8', font: { size: 10 } }, grid: { color: 'rgba(148,163,184,0.1)' } },
                  y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,0.1)' } },
                },
              }}
            />
          ) : (
            <EmptyState message="No timeline points are available for this session." className="!py-6" />
          )}
        </GlassCard>
        <GlassCard className="!cursor-default">
          <div className="text-sm font-bold text-white mb-4">Aggression vs Discipline</div>
          <ChartCanvas
            type="bar"
            data={aggressionData}
            height={320}
            options={{
              indexAxis: 'y',
              plugins: { legend: { labels: { color: '#94a3b8', font: { size: 10 } } } },
              scales: {
                x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,0.1)' } },
                y: { ticks: { color: '#e2e8f0', font: { size: 11 } }, grid: { display: false } },
              },
            }}
          />
        </GlassCard>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {data.players.slice(0, 6).map((player) => (
          <GlassCard key={player.name} onClick={() => navigateToPlayer(player.name)}>
            <div className="text-lg font-black text-white">{player.name}</div>
            <div className="grid grid-cols-2 gap-2 mt-4 text-sm">
              <DetailMetric label="Survival" value={formatPct(player.advanced_metrics.survival_rate)} />
              <DetailMetric label="Dmg Efficiency" value={player.advanced_metrics.damage_efficiency.toFixed(1)} />
              <DetailMetric label="Time Denied" value={formatDenied(player.advanced_metrics.time_denied_raw_seconds)} />
              <DetailMetric label="Self Kills" value={String(player.combat_defense.self_kills)} />
            </div>
          </GlassCard>
        ))}
      </div>
    </div>
  );
}

function MatchSummary({ data }: { data: RoundVizData }) {
  const winner = winnerLabel(data.winner_team);
  return (
    <GlassCard className="!cursor-default">
      <div className="text-sm font-bold text-white mb-4">Round Summary</div>
      <div className="grid grid-cols-2 gap-3 text-sm">
        <DetailMetric label="Map" value={mapLabel(data.map_name || 'Unknown')} />
        <DetailMetric label="Round" value={data.round_label || `R${data.round_number}`} />
        <DetailMetric label="Date" value={data.round_date || '--'} />
        <DetailMetric label="Duration" value={formatDuration(data.duration_seconds)} />
        <DetailMetric label="Players" value={String(data.player_count)} />
        <DetailMetric label="Winner" value={winner} />
      </div>
    </GlassCard>
  );
}

function CombatRadar({ players }: { players: VizPlayer[] }) {
  const topPlayers = [...players].sort((a, b) => b.dpm - a.dpm).slice(0, 5);
  const maxKills = Math.max(...topPlayers.map((player) => player.kills), 1);
  const maxDeaths = Math.max(...topPlayers.map((player) => player.deaths), 1);
  const maxDpm = Math.max(...topPlayers.map((player) => player.dpm), 1);
  const maxDamage = Math.max(...topPlayers.map((player) => player.damage_given), 1);
  const maxGibs = Math.max(...topPlayers.map((player) => player.gibs), 1);

  const data = {
    labels: ['Kills', 'Deaths(inv)', 'DPM', 'Damage', 'Efficiency', 'Gibs'],
    datasets: topPlayers.map((player, index) => ({
      label: player.name,
      data: [
        Math.round((player.kills / maxKills) * 100),
        Math.round((1 - player.deaths / maxDeaths) * 100),
        Math.round((player.dpm / maxDpm) * 100),
        Math.round((player.damage_given / maxDamage) * 100),
        Math.round(player.efficiency),
        Math.round((player.gibs / maxGibs) * 100),
      ],
      backgroundColor: CHART_COLORS[index % CHART_COLORS.length],
      borderColor: CHART_COLORS[index % CHART_COLORS.length],
      borderWidth: 2,
    })),
  };

  return (
    <GlassCard className="!cursor-default">
      <div className="text-sm font-bold text-white mb-4">Combat Radar</div>
      <ChartCanvas
        type="radar"
        data={data}
        height={320}
        options={{
          plugins: { legend: { position: 'bottom', labels: { color: '#94a3b8', font: { size: 10 } } } },
          scales: {
            r: {
              min: 0,
              max: 100,
              ticks: { display: false },
              angleLines: { color: 'rgba(148,163,184,0.2)' },
              grid: { color: 'rgba(148,163,184,0.2)' },
              pointLabels: { color: '#94a3b8', font: { size: 10 } },
            },
          },
        }}
      />
    </GlassCard>
  );
}

function RoundFraggers({ players }: { players: VizPlayer[] }) {
  const sorted = [...players].sort((a, b) => b.kills - a.kills);
  return (
    <GlassCard className="!cursor-default">
      <div className="text-sm font-bold text-white mb-4">Top Fraggers</div>
      <ChartCanvas
        type="bar"
        data={{
          labels: sorted.map((player) => player.name),
          datasets: [
            { label: 'Kills', data: sorted.map((player) => player.kills), backgroundColor: 'rgba(59, 130, 246, 0.7)' },
            { label: 'Deaths', data: sorted.map((player) => player.deaths), backgroundColor: 'rgba(244, 63, 94, 0.5)' },
          ],
        }}
        height={Math.max(220, sorted.length * 34)}
        options={{
          indexAxis: 'y',
          plugins: { legend: { labels: { color: '#94a3b8', font: { size: 10 } } } },
          scales: {
            x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,0.1)' } },
            y: { ticks: { color: '#e2e8f0', font: { size: 11 } }, grid: { display: false } },
          },
        }}
      />
    </GlassCard>
  );
}

function DamageBreakdown({ players }: { players: VizPlayer[] }) {
  const columns: Column<VizPlayer>[] = [
    {
      key: 'name',
      label: 'Player',
      render: (row) => (
        <button onClick={() => navigateToPlayer(row.name)} className="text-blue-400 hover:text-blue-300 font-semibold text-left">
          {row.name}
        </button>
      ),
    },
    { key: 'damage_given', label: 'Dmg Given', sortable: true, sortValue: (row) => row.damage_given, className: 'font-mono text-white', render: (row) => formatNumber(row.damage_given) },
    { key: 'damage_received', label: 'Dmg Recv', sortable: true, sortValue: (row) => row.damage_received, className: 'font-mono text-slate-400', render: (row) => formatNumber(row.damage_received) },
    { key: 'team_damage_given', label: 'Team Dmg', sortable: true, sortValue: (row) => row.team_damage_given, className: 'font-mono text-amber-400', render: (row) => formatNumber(row.team_damage_given) },
    { key: 'dpm', label: 'DPM', sortable: true, sortValue: (row) => row.dpm, className: 'font-mono text-cyan-400', render: (row) => row.dpm.toFixed(1) },
  ];

  return (
    <GlassCard className="!cursor-default">
      <div className="text-sm font-bold text-white mb-4">Damage Breakdown</div>
      <DataTable columns={columns} data={players} keyFn={(row) => row.guid} defaultSort={{ key: 'damage_given', dir: 'desc' }} />
    </GlassCard>
  );
}

function RoundSupport({ players }: { players: VizPlayer[] }) {
  const sorted = [...players].sort((a, b) => b.revives_given - a.revives_given);
  return (
    <GlassCard className="!cursor-default">
      <div className="text-sm font-bold text-white mb-4">Support Performance</div>
      <ChartCanvas
        type="bar"
        data={{
          labels: sorted.map((player) => player.name),
          datasets: [
            { label: 'Revives', data: sorted.map((player) => player.revives_given), backgroundColor: 'rgba(16, 185, 129, 0.7)' },
            { label: 'Gibs', data: sorted.map((player) => player.gibs), backgroundColor: 'rgba(168, 85, 247, 0.5)' },
            { label: 'Self Kills', data: sorted.map((player) => player.self_kills), backgroundColor: 'rgba(245, 158, 11, 0.5)' },
          ],
        }}
        height={Math.max(220, sorted.length * 36)}
        options={{
          indexAxis: 'y',
          plugins: { legend: { labels: { color: '#94a3b8', font: { size: 10 } } } },
          scales: {
            x: { stacked: true, ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,0.1)' } },
            y: { stacked: true, ticks: { color: '#e2e8f0', font: { size: 11 } }, grid: { display: false } },
          },
        }}
      />
    </GlassCard>
  );
}

function RoundTime({ players }: { players: VizPlayer[] }) {
  const sorted = [...players].sort((a, b) => b.time_played_seconds - a.time_played_seconds);
  return (
    <GlassCard className="!cursor-default">
      <div className="text-sm font-bold text-white mb-4">Time Distribution</div>
      <ChartCanvas
        type="bar"
        data={{
          labels: sorted.map((player) => player.name),
          datasets: [
            {
              label: 'Alive (s)',
              data: sorted.map((player) => Math.max(0, player.time_played_seconds - player.time_dead_seconds)),
              backgroundColor: 'rgba(34, 197, 94, 0.7)',
            },
            {
              label: 'Dead (s)',
              data: sorted.map((player) => player.time_dead_seconds),
              backgroundColor: 'rgba(100, 116, 139, 0.5)',
            },
          ],
        }}
        height={Math.max(220, sorted.length * 34)}
        options={{
          indexAxis: 'y',
          plugins: { legend: { labels: { color: '#94a3b8', font: { size: 10 } } } },
          scales: {
            x: { stacked: true, ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,0.1)' } },
            y: { stacked: true, ticks: { color: '#e2e8f0', font: { size: 11 } }, grid: { display: false } },
          },
        }}
      />
    </GlassCard>
  );
}

function RoundViz({ data }: { data: RoundVizData }) {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <MatchSummary data={data} />
        <CombatRadar players={data.players} />
      </div>
      <RoundFraggers players={data.players} />
      <DamageBreakdown players={data.players} />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <RoundSupport players={data.players} />
        <RoundTime players={data.players} />
      </div>
    </div>
  );
}

export default function SessionDetail({ params }: { params?: Record<string, string> }) {
  const [tab, setTab] = useState<Tab>('summary');
  const [activeRoundId, setActiveRoundId] = useState<number | null>(null);
  const [expandedMapIndex, setExpandedMapIndex] = useState<number | null>(null);
  const [selectedPlayerGuid, setSelectedPlayerGuid] = useState<string | null>(null);

  const sessionId = params?.sessionId ? Number(params.sessionId) : null;
  const sessionDate = params?.sessionDate ?? null;

  const { data: byId, isLoading: idLoading, isError: idError } = useSessionDetail(sessionId);
  const { data: byDate, isLoading: dateLoading, isError: dateError } = useSessionByDate(!sessionId ? sessionDate : null);

  const data = byId ?? byDate;
  const isLoading = sessionId ? idLoading : dateLoading;
  const isError = sessionId ? idError : dateError;

  const allRounds = useMemo(() => (
    data?.matches.flatMap((match) => match.rounds) ?? []
  ), [data]);
  const activeRound = useMemo(() => (
    allRounds.find((round) => round.round_id === activeRoundId) ?? null
  ), [allRounds, activeRoundId]);

  const scopeParams = useMemo(() => buildScopeParams(data?.date ?? null, activeRound), [data?.date, activeRound]);

  const { data: roundVizData, isLoading: roundVizLoading } = useRoundViz(activeRoundId);
  const { data: sessionGraphs, isLoading: sessionGraphsLoading } = useSessionGraphs(
    data?.date ?? null,
    data?.session_id ?? null,
    tab === 'charts' && !activeRoundId && !!data?.date,
  );

  const playerRows = useMemo<PlayerListRow[]>(() => {
    if (activeRound && roundVizData?.players?.length) {
      return roundVizData.players.map((player) => ({
        guid: player.guid,
        name: player.name,
        kills: player.kills,
        deaths: player.deaths,
        dpm: player.dpm,
        damageGiven: player.damage_given,
        damageReceived: player.damage_received,
        selfKills: player.self_kills,
        deniedSeconds: player.denied_playtime,
        timeDeadSeconds: player.time_dead_seconds,
        alivePct: player.time_played_seconds > 0
          ? ((player.time_played_seconds - player.time_dead_seconds) / player.time_played_seconds) * 100
          : null,
        playedPct: null,
        revives: player.revives_given,
        assists: player.kill_assists,
        gibs: player.gibs,
        accuracy: null,
        source: 'round',
        roundPlayer: player,
      }));
    }

    return (data?.players ?? []).map((player) => ({
      guid: player.player_guid,
      name: player.player_name,
      kills: player.kills,
      deaths: player.deaths,
      dpm: player.dpm,
      damageGiven: player.damage_given,
      damageReceived: player.damage_received,
      selfKills: player.self_kills,
      deniedSeconds: player.denied_playtime ?? player.time_denied_seconds ?? 0,
      timeDeadSeconds: Math.round((player.time_dead_minutes ?? 0) * 60),
      alivePct: player.alive_pct ?? player.alive_percent ?? null,
      playedPct: player.played_pct ?? player.played_percent ?? null,
      revives: player.revives_given,
      assists: player.kill_assists,
      gibs: player.gibs,
      accuracy: player.accuracy ?? null,
      source: 'session',
      sessionPlayer: player,
    }));
  }, [activeRound, roundVizData, data]);

  const effectivePlayerGuid = useMemo(() => {
    if (!playerRows.length) return null;
    return playerRows.some((row) => row.guid === selectedPlayerGuid)
      ? selectedPlayerGuid
      : playerRows[0].guid;
  }, [playerRows, selectedPlayerGuid]);

  const selectedPlayerRow = useMemo(() => (
    playerRows.find((row) => row.guid === effectivePlayerGuid) ?? null
  ), [playerRows, effectivePlayerGuid]);

  const { data: roundPlayerDetail, isLoading: roundPlayerDetailLoading } = useRoundPlayerDetails(
    activeRoundId,
    activeRoundId ? effectivePlayerGuid : null,
    tab === 'players' && !!activeRoundId && !!effectivePlayerGuid,
  );

  const { data: weaponMastery, isLoading: weaponMasteryLoading } = useWeaponsByPlayer(
    'session',
    !activeRoundId ? effectivePlayerGuid : null,
    1,
    50,
    tab === 'players' && !activeRoundId && !!effectivePlayerGuid,
    data?.session_id ?? undefined,
  );

  const { data: vsStats, isLoading: vsStatsLoading } = usePlayerVsStats(
    effectivePlayerGuid,
    activeRoundId ? 'round' : 'session',
    !activeRoundId ? (data?.session_id ?? undefined) : undefined,
    activeRoundId ?? undefined,
    tab === 'players' && !!effectivePlayerGuid,
  );

  const { data: tradeSummary, isLoading: tradeSummaryLoading } = useProximityTradeSummary(scopeParams, tab === 'teamplay' && !!scopeParams);
  const { data: tradeEvents, isLoading: tradeEventsLoading } = useProximityTradeEvents(scopeParams, 250, tab === 'teamplay' && !!scopeParams);
  const { data: duos, isLoading: duosLoading } = useProximityDuos(scopeParams, 8, tab === 'teamplay' && !!scopeParams);
  const { data: teamplay, isLoading: teamplayLoading } = useProximityTeamplay(scopeParams, tab === 'teamplay' && !!scopeParams);
  const { data: movers, isLoading: moversLoading } = useProximityMovers(scopeParams, 5, tab === 'teamplay' && !!scopeParams);

  if (isLoading) {
    return (
      <div className="page-shell">
        <PageHeader title="Session Detail" subtitle="Loading..." eyebrow="Deep Session Detail" />
        <Skeleton variant="card" count={4} />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="page-shell">
        <PageHeader title="Session Detail" subtitle="Session not found" eyebrow="Deep Session Detail" />
        <div className="text-center py-12">
          <div className="text-red-400 text-lg mb-4">Session not found</div>
          <button
            onClick={() => navigateTo('#/sessions2')}
            className="px-4 py-2 rounded-lg bg-blue-500/20 text-blue-400 font-bold text-sm hover:bg-blue-500/30 transition"
          >
            Back to Sessions
          </button>
        </div>
      </div>
    );
  }

  const teamplayLoading2 = tradeSummaryLoading || tradeEventsLoading || duosLoading || teamplayLoading || moversLoading;

  // Find which map index contains the active round (for auto-expanding)
  const activeRoundMapIndex = useMemo(() => {
    if (!activeRoundId || !data) return null;
    return data.matches.findIndex((match) =>
      match.rounds.some((round) => round.round_id === activeRoundId)
    );
  }, [activeRoundId, data]);

  const effectiveExpandedMapIndex = activeRoundMapIndex !== null && activeRoundMapIndex >= 0
    ? activeRoundMapIndex
    : expandedMapIndex;

  const expandedMapName = effectiveExpandedMapIndex !== null && data
    ? data.matches[effectiveExpandedMapIndex]?.map_name ?? null
    : null;

  function handleSelectMap(index: number) {
    setExpandedMapIndex(index);
    setActiveRoundId(null);
  }

  function handleSelectRound(roundId: number) {
    setActiveRoundId(roundId);
  }

  function handleClearScope() {
    setActiveRoundId(null);
    setExpandedMapIndex(null);
  }

  return (
    <div className="page-shell">
      <PageHeader
        title={`Session ${data.session_id ?? ''}`}
        subtitle={data.date ? `${data.date} · ${data.round_count} rounds · ${data.player_count} players` : `${data.round_count} rounds`}
        eyebrow="Deep Session Detail"
      >
        <button
          onClick={() => setTab('players')}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/6 border border-white/10 text-slate-300 text-sm font-bold hover:text-white transition"
        >
          Player Stats
        </button>
        <button
          onClick={() => navigateTo('#/sessions2')}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 text-slate-300 text-sm font-bold hover:text-white transition"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </button>
      </PageHeader>

      <KpiRow data={data} activeRound={activeRound} />
      <TabBar active={tab} onChange={setTab} />
      <ScopePill
        activeRound={activeRound}
        expandedMap={expandedMapName}
        onClear={handleClearScope}
      />

      {tab === 'summary' && (
        <SummaryTab
          data={data}
          activeRoundId={activeRoundId}
          expandedMapIndex={effectiveExpandedMapIndex}
          onSelectMap={handleSelectMap}
          onSelectRound={handleSelectRound}
          onClearRound={() => setActiveRoundId(null)}
        />
      )}

      {tab === 'players' && (
        <>
          <PlayersTab rows={playerRows} selectedGuid={effectivePlayerGuid} onSelectPlayer={setSelectedPlayerGuid} />
          {activeRoundId ? (
            <RoundPlayerDetail
              detail={roundPlayerDetail}
              loading={roundPlayerDetailLoading}
              vsPreys={vsStats?.easiest_preys ?? []}
              vsEnemies={vsStats?.worst_enemies ?? []}
              vsLoading={vsStatsLoading}
            />
          ) : (
            <SessionPlayerDetail
              row={selectedPlayerRow}
              weaponMastery={weaponMastery?.players?.[0] ?? null}
              loading={weaponMasteryLoading}
              vsPreys={vsStats?.easiest_preys ?? []}
              vsEnemies={vsStats?.worst_enemies ?? []}
              vsLoading={vsStatsLoading}
            />
          )}
        </>
      )}

      {tab === 'teamplay' && (
        <SignalsTab
          loading={teamplayLoading2}
          summary={tradeSummary}
          events={tradeEvents}
          duos={duos}
          teamplay={teamplay}
          movers={movers}
        />
      )}

      {tab === 'charts' && (
        roundVizLoading && activeRoundId ? (
          <Skeleton variant="card" count={4} />
        ) : activeRoundId ? (
          roundVizData ? <RoundViz data={roundVizData} /> : <EmptyState message="No round viz data is available for this scope." />
        ) : sessionGraphsLoading ? (
          <Skeleton variant="card" count={4} />
        ) : sessionGraphs ? (
          <SessionViz data={sessionGraphs} />
        ) : (
          <EmptyState message="No session graph data is available for this session." />
        )
      )}
    </div>
  );
}
