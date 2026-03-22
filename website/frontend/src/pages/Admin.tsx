import { useState, useMemo, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { PageHeader } from '../components/PageHeader';
import { GlassPanel } from '../components/GlassPanel';
import { GlassCard } from '../components/GlassCard';
import { formatSec } from '../lib/format';
import { Skeleton } from '../components/Skeleton';
import { useAuthMe, useLiveStatus } from '../api/hooks';

const API_BASE = '/api';

// ── Types ────────────────────────────────────────────────────────────────────

interface DiagnosticsResponse {
  status: string;
  timestamp: string;
  database: { status: string; error?: string };
  tables: Array<{ name: string; status: string; row_count?: number; error?: string; required: boolean }>;
  issues: string[];
  warnings: string[];
  time: {
    raw_dead_seconds?: number;
    agg_dead_seconds?: number;
    cap_seconds?: number;
    cap_hits?: number;
    raw_denied_seconds?: number;
  };
  monitoring: Record<string, { count: number; last_recorded_at: string | null; error?: string }>;
}

interface StatusResponse {
  status: string;
  service: string;
  database: string;
}

type StatusColor = 'green' | 'red' | 'blue' | 'amber';

// ── Helpers ──────────────────────────────────────────────────────────────────

function statusColor(s: string): StatusColor {
  if (s === 'connected' || s === 'ok' || s === 'online' || s === 'green') return 'green';
  if (s === 'error' || s === 'not_found' || s === 'red') return 'red';
  if (s === 'warning' || s === 'degraded' || s === 'amber') return 'amber';
  return 'blue';
}

const DOT_CLS: Record<StatusColor, string> = {
  green: 'bg-emerald-500 shadow-emerald-500/50',
  red:   'bg-rose-500 shadow-rose-500/50',
  amber: 'bg-amber-500 shadow-amber-500/50',
  blue:  'bg-blue-500 shadow-blue-500/50',
};

function StatusDot({ color, pulse }: { color: StatusColor; pulse?: boolean }) {
  return (
    <span className="relative flex h-2.5 w-2.5">
      {pulse && <span className={`absolute inline-flex h-full w-full rounded-full opacity-60 animate-ping ${DOT_CLS[color]}`} />}
      <span className={`relative inline-flex rounded-full h-2.5 w-2.5 shadow-[0_0_6px] ${DOT_CLS[color]}`} />
    </span>
  );
}


function fmtNum(v: number | undefined | null): string {
  if (v == null) return '--';
  return v.toLocaleString();
}

function timeAgo(iso: string | null | undefined): string {
  if (!iso) return 'never';
  const d = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(d / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

// ── Version & Config ─────────────────────────────────────────────────────────

const SYSTEM_VERSION = '1.0.8';
const SCHEMA_VERSION = '2.0';

// ── Architecture Data ────────────────────────────────────────────────────────

interface PipelineNode {
  id: string;
  label: string;
  desc: string;
  icon: string;
  layer: 'server' | 'lua' | 'transport' | 'pipeline' | 'storage' | 'output';
}

const PIPELINE: PipelineNode[] = [
  { id: 'et',         label: 'ET:Legacy',              desc: 'Game server running matches',                 icon: '\u{1F3AE}', layer: 'server' },
  { id: 'c0rn',       label: 'c0rnp0rn7.lua',          desc: 'Writes gamestats/*.txt after each round',     icon: '\u{1F4DD}', layer: 'lua' },
  { id: 'endstats',   label: 'endstats.lua',            desc: 'Writes endstats awards files',                icon: '\u{1F3C6}', layer: 'lua' },
  { id: 'webhook',    label: 'stats_webhook.lua',       desc: 'Real-time round start/end notifications',     icon: '\u{1F4E1}', layer: 'lua' },
  { id: 'proximity',  label: 'proximity_tracker.lua',   desc: 'Tracks player positions & engagements',       icon: '\u{1F4CD}', layer: 'lua' },
  { id: 'ssh',        label: 'SSH Monitor',             desc: 'Downloads new files every 60s',               icon: '\u{1F50D}', layer: 'transport' },
  { id: 'filetrack',  label: 'File Tracker',            desc: '5-layer dedup with SHA256 integrity',         icon: '\u{1F4C1}', layer: 'transport' },
  { id: 'webhookrx',  label: 'Webhook Receiver',        desc: 'Catches Lua timing pings via HTTP',           icon: '\u{1F4E5}', layer: 'transport' },
  { id: 'parser',     label: 'Stats Parser',            desc: 'Parses 56 fields, R2 differential calc',      icon: '\u{2699}\u{FE0F}',  layer: 'pipeline' },
  { id: 'validate',   label: 'Validation & Caps',       desc: 'Prevents impossible values, caps outliers',   icon: '\u{1F6E1}\u{FE0F}', layer: 'pipeline' },
  { id: 'session',    label: 'Session Aggregator',      desc: 'Groups rounds into sessions (60-min gap)',    icon: '\u{1F4CA}', layer: 'pipeline' },
  { id: 'correlate',  label: 'Round Correlation',       desc: 'Tracks R1+R2 data completeness',              icon: '\u{1F517}', layer: 'pipeline' },
  { id: 'postgres',   label: 'PostgreSQL',              desc: '68 tables, 56+ columns in player stats',     icon: '\u{1F5C4}\u{FE0F}', layer: 'storage' },
  { id: 'redis',      label: 'Redis',                   desc: 'Cache layer, session data',                   icon: '\u{26A1}',  layer: 'storage' },
  { id: 'bot',        label: 'Discord Bot',             desc: '80+ commands across 18 Cogs',                 icon: '\u{1F916}', layer: 'output' },
  { id: 'website',    label: 'Website API',             desc: 'FastAPI backend, 88 endpoints',               icon: '\u{1F310}', layer: 'output' },
];

const LAYER_META: Record<string, { label: string; color: string; border: string }> = {
  server:    { label: 'Game Server',    color: 'text-rose-400',    border: 'border-rose-500/30' },
  lua:       { label: 'Lua Scripts',    color: 'text-amber-400',   border: 'border-amber-500/30' },
  transport: { label: 'Transport',      color: 'text-cyan-400',    border: 'border-cyan-500/30' },
  pipeline:  { label: 'Processing',     color: 'text-emerald-400', border: 'border-emerald-500/30' },
  storage:   { label: 'Storage',        color: 'text-purple-400',  border: 'border-purple-500/30' },
  output:    { label: 'Output',         color: 'text-blue-400',    border: 'border-blue-500/30' },
};

const LAYER_ORDER = ['server', 'lua', 'transport', 'pipeline', 'storage', 'output'] as const;

const FLOW_ARROWS: Array<[string, string, string]> = [
  ['ET:Legacy',             'Lua Scripts',    'game events'],
  ['Lua Scripts',           'Transport',      'files + HTTP'],
  ['Transport',             'Processing',     'parse queue'],
  ['Processing',            'Storage',        'write rows'],
  ['Storage',               'Output',         'query + post'],
];

// ── Table categories ─────────────────────────────────────────────────────────

const TABLE_CATEGORIES: Record<string, string[]> = {
  'Core Stats':   ['rounds', 'player_comprehensive_stats', 'weapon_comprehensive_stats', 'player_links'],
  'Sessions':     ['sessions', 'session_teams', 'gaming_sessions'],
  'Lua & Timing': ['lua_round_teams', 'lua_spawn_stats', 'round_correlations'],
  'Proximity':    ['proximity_engagements', 'proximity_spawn_timing', 'proximity_team_cohesion', 'proximity_crossfire_opportunity', 'proximity_team_push', 'proximity_lua_trade_kill'],
  'Monitoring':   ['server_status_history', 'voice_status_history', 'processed_files'],
  'Users':        ['discord_users', 'players'],
};

// ── Service Status Card ──────────────────────────────────────────────────────

function ServiceCard({ title, status, detail, pulse }: { title: string; status: StatusColor; detail: string; pulse?: boolean }) {
  return (
    <div className="rounded-xl border border-white/10 bg-slate-950/40 p-4 hover:border-white/20 transition">
      <div className="flex items-center gap-2.5 mb-1.5">
        <StatusDot color={status} pulse={pulse} />
        <span className="text-sm font-bold text-white">{title}</span>
      </div>
      <div className="text-xs text-slate-400 pl-5">{detail}</div>
    </div>
  );
}

// ── Health Banner ────────────────────────────────────────────────────────────

function HealthBanner({ diag, apiStatus }: { diag: DiagnosticsResponse | undefined; apiStatus: StatusResponse | undefined }) {
  const { data: live } = useLiveStatus();

  const dbColor = statusColor(diag?.database?.status ?? 'unknown');
  const apiColor = statusColor(apiStatus?.status ?? 'unknown');
  const gameOnline = live?.game_server?.online ?? false;
  const gameColor: StatusColor = gameOnline ? 'green' : 'red';
  const voiceCount = live?.voice_channel?.count ?? 0;
  const overallColor: StatusColor = diag?.issues?.length ? 'red' : diag?.warnings?.length ? 'amber' : 'green';

  const playerCountText = gameOnline
    ? `${live?.game_server?.player_count ?? 0}/${live?.game_server?.max_players ?? 20} players`
    : 'offline';

  return (
    <GlassPanel>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5">
        <div className="flex items-center gap-3">
          <StatusDot color={overallColor} pulse={overallColor !== 'green'} />
          <div>
            <span className="text-sm font-bold text-white">System {diag?.status?.toUpperCase() ?? 'CHECKING'}</span>
            <span className="text-xs text-slate-500 ml-2">v{SYSTEM_VERSION} / schema {SCHEMA_VERSION}</span>
          </div>
        </div>
        <div className="text-[11px] text-slate-500 tabular-nums">
          {diag?.timestamp ? new Date(diag.timestamp).toLocaleString() : '--'}
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <ServiceCard title="Database"    status={dbColor}   detail={diag?.database?.status ?? 'unknown'} />
        <ServiceCard title="API"         status={apiColor}  detail={apiStatus?.database ?? 'unknown'} />
        <ServiceCard title="Game Server" status={gameColor} detail={playerCountText} pulse={gameOnline} />
        <ServiceCard title="Voice"       status={voiceCount > 0 ? 'green' : 'blue'} detail={`${voiceCount} in channel`} pulse={voiceCount > 0} />
      </div>
    </GlassPanel>
  );
}

// ── Architecture Pipeline ────────────────────────────────────────────────────

function ArchitecturePipeline() {
  const [expanded, setExpanded] = useState<string | null>(null);

  const layers = useMemo(() => {
    return LAYER_ORDER.map((layer) => ({
      ...LAYER_META[layer],
      id: layer,
      nodes: PIPELINE.filter((n) => n.layer === layer),
    }));
  }, []);

  return (
    <GlassPanel>
      <div className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-4">Data Pipeline Architecture</div>

      {/* Flow arrows between layers */}
      <div className="hidden lg:flex items-center justify-center gap-0 mb-6 px-4">
        {FLOW_ARROWS.map(([from, to, label], i) => (
          <div key={i} className="flex items-center">
            {i > 0 && <div className="w-px h-4 bg-slate-700 mx-1" />}
            <div className="flex flex-col items-center px-2">
              <span className="text-[10px] text-cyan-400 font-mono whitespace-nowrap">{from}</span>
              <div className="flex items-center gap-1 my-0.5">
                <div className="w-8 h-px bg-gradient-to-r from-cyan-500/50 to-emerald-500/50" />
                <span className="text-[9px] text-slate-500">{label}</span>
                <div className="w-8 h-px bg-gradient-to-r from-emerald-500/50 to-cyan-500/50" />
              </div>
              <span className="text-[10px] text-emerald-400 font-mono whitespace-nowrap">{to}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Layer groups */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
        {layers.map((layer) => (
          <div key={layer.id} className={`rounded-xl border ${layer.border} bg-slate-950/30 p-3`}>
            <div className={`text-[10px] font-bold uppercase tracking-wider ${layer.color} mb-2`}>
              {layer.label}
            </div>
            <div className="space-y-1">
              {layer.nodes.map((node) => (
                <button
                  key={node.id}
                  onClick={() => setExpanded(expanded === node.id ? null : node.id)}
                  className="w-full text-left rounded-lg border border-white/5 bg-slate-950/40 px-3 py-2 hover:border-white/15 transition"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-sm">{node.icon}</span>
                    <span className="text-xs font-semibold text-white">{node.label}</span>
                  </div>
                  {expanded === node.id && (
                    <div className="mt-1.5 text-[11px] text-slate-400 pl-6">{node.desc}</div>
                  )}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </GlassPanel>
  );
}

// ── Quick Stats Bar ──────────────────────────────────────────────────────────

function QuickStats({ tables }: { tables: DiagnosticsResponse['tables'] }) {
  const get = (name: string) => tables.find((t) => t.name === name)?.row_count;

  const stats = [
    { label: 'Rounds',       value: fmtNum(get('rounds')),                        icon: '\u{1F3AF}' },
    { label: 'Player Stats', value: fmtNum(get('player_comprehensive_stats')),     icon: '\u{1F4CA}' },
    { label: 'Players',      value: fmtNum(get('players')),                        icon: '\u{1F465}' },
    { label: 'Linked Users', value: fmtNum(get('discord_users')),                  icon: '\u{1F517}' },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {stats.map(({ label, value, icon }) => (
        <GlassCard key={label}>
          <div className="flex items-center gap-3">
            <span className="text-2xl">{icon}</span>
            <div>
              <div className="text-lg font-bold text-white tabular-nums">{value}</div>
              <div className="text-[10px] text-slate-500 uppercase tracking-wider">{label}</div>
            </div>
          </div>
        </GlassCard>
      ))}
    </div>
  );
}

// ── Alerts Panel ─────────────────────────────────────────────────────────────

function AlertsPanel({ issues, warnings }: { issues: string[]; warnings: string[] }) {
  if (!issues.length && !warnings.length) {
    return (
      <GlassCard>
        <div className="flex items-center gap-2">
          <StatusDot color="green" />
          <span className="text-xs text-slate-300">All systems operational. No alerts.</span>
        </div>
      </GlassCard>
    );
  }
  return (
    <GlassCard>
      <div className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-3">Alerts</div>
      <div className="space-y-2">
        {issues.map((msg, i) => (
          <div key={`i${i}`} className="flex items-start gap-2 rounded-lg bg-rose-500/5 border border-rose-500/20 px-3 py-2">
            <StatusDot color="red" /><span className="text-xs text-rose-300">{msg}</span>
          </div>
        ))}
        {warnings.map((msg, i) => (
          <div key={`w${i}`} className="flex items-start gap-2 rounded-lg bg-amber-500/5 border border-amber-500/20 px-3 py-2">
            <StatusDot color="amber" /><span className="text-xs text-amber-300">{msg}</span>
          </div>
        ))}
      </div>
    </GlassCard>
  );
}

// ── Tables Overview ──────────────────────────────────────────────────────────

function TablesOverview({ tables }: { tables: DiagnosticsResponse['tables'] }) {
  const [openCat, setOpenCat] = useState<string | null>('Core Stats');

  if (!tables.length) return null;

  // Group known tables into categories, put unknowns in "Other"
  const categorized = useMemo(() => {
    const known = new Set(Object.values(TABLE_CATEGORIES).flat());
    const other = tables.filter((t) => !known.has(t.name));
    return { ...TABLE_CATEGORIES, ...(other.length ? { Other: other.map((t) => t.name) } : {}) };
  }, [tables]);

  const tableMap = useMemo(() => {
    const m: Record<string, (typeof tables)[0]> = {};
    for (const t of tables) m[t.name] = t;
    return m;
  }, [tables]);

  return (
    <GlassPanel>
      <div className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-3">
        Database Tables ({tables.length})
      </div>
      <div className="space-y-2">
        {Object.entries(categorized).map(([cat, names]) => {
          const catTables = names.map((n) => tableMap[n]).filter(Boolean);
          const total = catTables.reduce((s, t) => s + (t.row_count ?? 0), 0);
          const hasError = catTables.some((t) => t.status !== 'ok');
          const isOpen = openCat === cat;

          return (
            <div key={cat} className="rounded-xl border border-white/10 bg-slate-950/30 overflow-hidden">
              <button
                onClick={() => setOpenCat(isOpen ? null : cat)}
                className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-white/5 transition"
              >
                <div className="flex items-center gap-2">
                  <StatusDot color={hasError ? 'amber' : 'green'} />
                  <span className="text-xs font-bold text-white">{cat}</span>
                  <span className="text-[10px] text-slate-500">{catTables.length} tables</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-[11px] text-slate-400 tabular-nums">{fmtNum(total)} rows</span>
                  <span className="text-slate-500 text-[11px]">{isOpen ? '\u25B2' : '\u25BC'}</span>
                </div>
              </button>

              {isOpen && (
                <div className="border-t border-white/5 px-4 py-2 space-y-1">
                  {catTables.map((t) => (
                    <div key={t.name} className="flex items-center justify-between py-1">
                      <div className="flex items-center gap-2">
                        <StatusDot color={statusColor(t.status)} />
                        <span className="text-[11px] text-white font-mono">{t.name}</span>
                        {t.required && <span className="text-[9px] text-amber-400 font-bold ml-1">REQ</span>}
                      </div>
                      <span className="text-[11px] text-slate-400 tabular-nums">
                        {t.status === 'ok' ? fmtNum(t.row_count) : t.status}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </GlassPanel>
  );
}

// ── Time Metrics ─────────────────────────────────────────────────────────────

function TimeMetrics({ time }: { time: DiagnosticsResponse['time'] }) {
  const metrics = [
    { label: 'Raw Dead Time',    value: formatSec(time.raw_dead_seconds),    sub: 'Total across all players' },
    { label: 'Capped Dead Time', value: formatSec(time.agg_dead_seconds),    sub: 'After per-round capping' },
    { label: 'Time Removed',     value: formatSec(time.cap_seconds),         sub: 'Saved by capping' },
    { label: 'Cap Triggers',     value: fmtNum(time.cap_hits),               sub: 'Rows where cap applied' },
    { label: 'Denied Time',      value: formatSec(time.raw_denied_seconds),  sub: 'Total denied playtime' },
  ];

  return (
    <GlassCard>
      <div className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-3">Timing Audit</div>
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
        {metrics.map(({ label, value, sub }) => (
          <div key={label} className="text-center">
            <div className="text-[10px] text-slate-500 uppercase mb-0.5">{label}</div>
            <div className="text-base font-bold text-white font-mono tabular-nums">{value}</div>
            <div className="text-[9px] text-slate-600 mt-0.5">{sub}</div>
          </div>
        ))}
      </div>
    </GlassCard>
  );
}

// ── Monitoring Panel ─────────────────────────────────────────────────────────

function MonitoringPanel({ monitoring }: { monitoring: DiagnosticsResponse['monitoring'] }) {
  const entries = Object.entries(monitoring);
  if (!entries.length) return null;
  return (
    <GlassCard>
      <div className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-3">Monitoring History</div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {entries.map(([key, info]) => (
          <div key={key} className="rounded-lg border border-white/10 bg-slate-950/30 p-3">
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2">
                <StatusDot color={info.error ? 'amber' : info.count > 0 ? 'green' : 'blue'} />
                <span className="text-xs font-bold text-white capitalize">{key}</span>
              </div>
              <span className="text-[10px] text-slate-500">{timeAgo(info.last_recorded_at)}</span>
            </div>
            <div className="text-[11px] text-slate-400 pl-5">{fmtNum(info.count)} records</div>
          </div>
        ))}
      </div>
    </GlassCard>
  );
}

// ── Main Page ────────────────────────────────────────────────────────────────

export default function Admin() {
  const { data: auth } = useAuthMe();
  const [refreshKey, setRefreshKey] = useState(0);

  const { data: diag, isLoading: diagLoading } = useQuery<DiagnosticsResponse>({
    queryKey: ['diagnostics', refreshKey],
    queryFn: () => fetch(`${API_BASE}/diagnostics`).then((r) => r.json()),
    staleTime: 10_000,
    refetchInterval: 15_000,
  });

  const { data: apiStatus } = useQuery<StatusResponse>({
    queryKey: ['api-status', refreshKey],
    queryFn: () => fetch(`${API_BASE}/status`).then((r) => r.json()),
    staleTime: 10_000,
    refetchInterval: 15_000,
  });

  const handleRefresh = useCallback(() => setRefreshKey((k) => k + 1), []);

  if (!auth) {
    return (
      <div className="page-shell">
        <PageHeader title="System Overview" subtitle="Operational diagnostics and architecture." eyebrow="Admin" />
        <div className="text-center py-16">
          <div className="text-4xl mb-4">{'\u{1F512}'}</div>
          <p className="text-slate-400 text-lg mb-4">Admin access requires authentication.</p>
          <a href="/auth/discord" className="inline-block px-6 py-2 rounded-xl bg-indigo-600 text-white font-bold text-sm hover:bg-indigo-500 transition">
            Login with Discord
          </a>
        </div>
      </div>
    );
  }

  if (diagLoading) return <Skeleton variant="card" count={4} />;

  return (
    <div className="page-shell">
      <PageHeader title="System Overview" subtitle="Real-time diagnostics, architecture, and operational health." eyebrow="Admin" />

      {/* Refresh button */}
      <div className="flex items-center justify-end mb-4">
        <button
          onClick={handleRefresh}
          className="px-3 py-1.5 rounded-lg text-xs font-bold border border-white/10 text-slate-300 hover:border-cyan-500/40 hover:text-white transition"
        >
          Refresh
        </button>
      </div>

      {/* Health Banner */}
      <HealthBanner diag={diag} apiStatus={apiStatus} />

      {/* Alerts */}
      <div className="mt-4">
        <AlertsPanel issues={diag?.issues ?? []} warnings={diag?.warnings ?? []} />
      </div>

      {/* Quick Stats */}
      <div className="mt-4">
        <QuickStats tables={diag?.tables ?? []} />
      </div>

      {/* Architecture Pipeline */}
      <div className="mt-4">
        <ArchitecturePipeline />
      </div>

      {/* Time Metrics + Monitoring */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4">
        <TimeMetrics time={diag?.time ?? {}} />
        <MonitoringPanel monitoring={diag?.monitoring ?? {}} />
      </div>

      {/* Database Tables */}
      <div className="mt-4">
        <TablesOverview tables={diag?.tables ?? []} />
      </div>
    </div>
  );
}
