import { useState, useMemo, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { PageHeader } from '../components/PageHeader';
import { GlassPanel } from '../components/GlassPanel';
import { GlassCard } from '../components/GlassCard';
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

// ── Node Data ────────────────────────────────────────────────────────────────

interface NodeInfo {
  title: string;
  eli5: string;
  group: string;
  files?: string;
}

const NODES: Record<string, NodeInfo> = {
  core_game_server:     { title: 'puran.hehe.si (Game Server)',  eli5: 'The live game server where matches are played.',       group: 'infrastructure' },
  core_postgres:        { title: 'PostgreSQL (Central DB)',      eli5: 'The vault that stores every stat safely.',             group: 'infrastructure' },
  core_bot_web:         { title: 'Bot + Website Host',           eli5: 'Runs the Discord bot, API backend, and website.',     group: 'infrastructure' },
  et_server:            { title: 'ET:Legacy Runtime',            eli5: 'The game itself running on the server.',              group: 'game-server' },
  lua_modules:          { title: 'Lua Modules',                  eli5: 'Scripts that watch the game and write stats files.',  group: 'game-server' },
  lua_c0rnp0rn7:        { title: 'c0rnp0rn7.lua',               eli5: 'Writes the main stats file after each round.',       group: 'lua', files: 'c0rnp0rn7.lua' },
  lua_endstats:         { title: 'endstats.lua',                 eli5: 'Writes the awards file when a round ends.',          group: 'lua', files: 'endstats.lua' },
  lua_webhook:          { title: 'stats_discord_webhook.lua',    eli5: 'Sends a quick ping when rounds start/end.',          group: 'lua', files: 'vps_scripts/stats_discord_webhook.lua' },
  lua_proximity:        { title: 'proximity_tracker.lua',        eli5: 'Logs how close players are.',                        group: 'lua', files: 'proximity/lua/proximity_tracker.lua' },
  stats_parser:         { title: 'Stats Parser',                 eli5: 'Turns raw text into clean numbers.',                  group: 'pipeline', files: 'bot/community_stats_parser.py' },
  differential_calc:    { title: 'R1/R2 Differential',           eli5: 'Computes Round 2 by subtracting Round 1.',           group: 'pipeline', files: 'bot/community_stats_parser.py' },
  validation_caps:      { title: 'Validation & Caps',            eli5: 'Stops impossible numbers from sneaking in.',         group: 'pipeline', files: 'postgresql_database_manager.py' },
  ssh_monitor:          { title: 'SSH Monitor',                  eli5: 'Downloads new stats files from the game server.',    group: 'pipeline', files: 'bot/services/automation/ssh_monitor.py' },
  file_tracker:         { title: 'File Tracker',                 eli5: 'Keeps track of which files are new.',                group: 'pipeline', files: 'bot/automation/file_tracker.py' },
  webhook_receiver:     { title: 'Webhook Receiver',             eli5: 'Catches Lua timing pings.',                          group: 'pipeline', files: 'bot/ultimate_bot.py' },
  session_aggregator:   { title: 'Session Aggregator',           eli5: 'Groups rounds into gaming sessions.',                group: 'pipeline', files: 'bot/services/' },
  discord_bot:          { title: 'Discord Bot',                  eli5: 'Posts stats and handles commands.',                   group: 'output', files: 'bot/ultimate_bot.py' },
  website_api:          { title: 'Website API',                  eli5: 'Serves stats to the website.',                       group: 'output', files: 'website/backend/main.py' },
  proximity_parser:     { title: 'Proximity Parser',             eli5: 'Parses proximity engagement logs.',                  group: 'pipeline', files: 'proximity/parser/parser.py' },
  endstats_parser:      { title: 'Endstats Parser',              eli5: 'Turns awards files into award rows.',                group: 'pipeline', files: 'bot/endstats_parser.py' },
};

const GROUPS: Record<string, { label: string; color: string }> = {
  infrastructure: { label: 'Infrastructure', color: 'text-purple-400' },
  'game-server':  { label: 'Game Server',    color: 'text-cyan-400' },
  lua:            { label: 'Lua Modules',    color: 'text-amber-400' },
  pipeline:       { label: 'Data Pipeline',  color: 'text-emerald-400' },
  output:         { label: 'Output',         color: 'text-blue-400' },
};

const FLOW_STEPS = [
  { from: 'ET:Legacy Runtime', to: 'Lua Modules',        label: 'Game events' },
  { from: 'c0rnp0rn7.lua',    to: 'gamestats/*.txt',     label: 'Stats files' },
  { from: 'endstats.lua',     to: 'endstats/*.txt',      label: 'Award files' },
  { from: 'Lua Webhook',      to: 'Webhook Receiver',    label: 'HTTP POST' },
  { from: 'SSH Monitor',      to: 'File Tracker',        label: 'Sync files' },
  { from: 'File Tracker',     to: 'Stats Parser',        label: 'Parse queue' },
  { from: 'Stats Parser',     to: 'R1/R2 Differential',  label: 'R2 split' },
  { from: 'R1/R2 Differential', to: 'Validation & Caps', label: 'Validate' },
  { from: 'Validation & Caps',to: 'PostgreSQL',          label: 'Write rows' },
  { from: 'PostgreSQL',       to: 'Session Aggregator',  label: 'Session totals' },
  { from: 'Session Aggregator', to: 'Discord Bot',       label: 'Post embeds' },
  { from: 'PostgreSQL',       to: 'Website API',         label: 'Query data' },
];

// ── Helpers ──────────────────────────────────────────────────────────────────

function statusColor(s: string): StatusColor {
  if (s === 'connected' || s === 'ok' || s === 'online' || s === 'green') return 'green';
  if (s === 'error' || s === 'not_found' || s === 'red') return 'red';
  if (s === 'warning' || s === 'degraded' || s === 'amber') return 'amber';
  return 'blue';
}

function StatusDot({ color }: { color: StatusColor }) {
  const cls = {
    green: 'bg-emerald-500 shadow-emerald-500/50',
    red: 'bg-rose-500 shadow-rose-500/50',
    amber: 'bg-amber-500 shadow-amber-500/50',
    blue: 'bg-blue-500 shadow-blue-500/50',
  }[color];
  return <span className={`inline-block w-2.5 h-2.5 rounded-full shadow-[0_0_6px] ${cls}`} />;
}

function formatSec(v: number | undefined | null): string {
  if (v == null || !Number.isFinite(v)) return '--';
  const neg = v < 0 ? '-' : '';
  let s = Math.floor(Math.abs(v));
  const h = Math.floor(s / 3600); s -= h * 3600;
  const m = Math.floor(s / 60); s = s % 60;
  if (h > 0) return `${neg}${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  return `${neg}${m}:${String(s).padStart(2, '0')}`;
}

function fmtNum(v: number | undefined | null): string {
  if (v == null) return '--';
  return v.toLocaleString();
}

// ── Health Dashboard ─────────────────────────────────────────────────────────

function HealthDashboard({ diag, apiStatus }: { diag: DiagnosticsResponse | undefined; apiStatus: StatusResponse | undefined }) {
  const { data: live } = useLiveStatus();

  const dbColor = statusColor(diag?.database?.status ?? 'unknown');
  const apiColor = statusColor(apiStatus?.status ?? 'unknown');
  const gameColor = live?.game_server?.online ? 'green' as StatusColor : 'red' as StatusColor;
  const overallColor = diag?.issues?.length ? 'red' as StatusColor : diag?.warnings?.length ? 'amber' as StatusColor : 'green' as StatusColor;

  return (
    <GlassPanel>
      <div className="flex items-center justify-between mb-4">
        <div className="text-xs font-bold uppercase tracking-widest text-slate-400">System Health</div>
        <div className="flex items-center gap-2">
          <StatusDot color={overallColor} />
          <span className="text-xs text-slate-300">{diag?.status?.toUpperCase() ?? 'CHECKING'}</span>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3">
          <div className="flex items-center gap-2 mb-1"><StatusDot color={dbColor} /><span className="text-xs font-bold text-white">Database</span></div>
          <div className="text-[11px] text-slate-400">{diag?.database?.status ?? 'unknown'}</div>
        </div>
        <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3">
          <div className="flex items-center gap-2 mb-1"><StatusDot color={apiColor} /><span className="text-xs font-bold text-white">API</span></div>
          <div className="text-[11px] text-slate-400">{apiStatus?.status ?? 'unknown'}</div>
        </div>
        <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3">
          <div className="flex items-center gap-2 mb-1"><StatusDot color={gameColor} /><span className="text-xs font-bold text-white">Game Server</span></div>
          <div className="text-[11px] text-slate-400">
            {live?.game_server?.online
              ? `${live.game_server.player_count}/${live.game_server.max_players} players`
              : 'offline'}
          </div>
        </div>
        <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3">
          <div className="flex items-center gap-2 mb-1"><StatusDot color={live?.voice_channel?.count ? 'green' : 'blue'} /><span className="text-xs font-bold text-white">Voice</span></div>
          <div className="text-[11px] text-slate-400">{live?.voice_channel?.count ?? 0} in voice</div>
        </div>
      </div>
    </GlassPanel>
  );
}

// ── Tables Status ────────────────────────────────────────────────────────────

function TablesStatus({ tables }: { tables: DiagnosticsResponse['tables'] }) {
  if (!tables.length) return null;
  return (
    <GlassCard>
      <div className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-3">Database Tables</div>
      <div className="space-y-1.5">
        {tables.map((t) => (
          <div key={t.name} className="flex items-center justify-between rounded-lg border border-white/10 bg-slate-950/30 px-3 py-2">
            <div className="flex items-center gap-2">
              <StatusDot color={statusColor(t.status)} />
              <span className="text-xs text-white font-mono">{t.name}</span>
              {t.required && <span className="text-[9px] text-amber-400 font-bold">REQ</span>}
            </div>
            <div className="text-[11px] text-slate-400">
              {t.status === 'ok' ? `${fmtNum(t.row_count)} rows` : t.status}
            </div>
          </div>
        ))}
      </div>
    </GlassCard>
  );
}

// ── Warnings Panel ───────────────────────────────────────────────────────────

function WarningsPanel({ issues, warnings }: { issues: string[]; warnings: string[] }) {
  if (!issues.length && !warnings.length) {
    return (
      <GlassCard>
        <div className="flex items-center gap-2">
          <StatusDot color="green" />
          <span className="text-xs text-slate-300">Diagnostics clean. No critical warnings detected.</span>
        </div>
      </GlassCard>
    );
  }
  return (
    <GlassCard>
      <div className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-3">Alerts</div>
      <div className="space-y-2">
        {issues.map((msg, i) => (
          <div key={`i${i}`} className="flex items-start gap-2">
            <StatusDot color="red" /><span className="text-xs text-rose-400">{msg}</span>
          </div>
        ))}
        {warnings.map((msg, i) => (
          <div key={`w${i}`} className="flex items-start gap-2">
            <StatusDot color="blue" /><span className="text-xs text-blue-400">{msg}</span>
          </div>
        ))}
      </div>
    </GlassCard>
  );
}

// ── Time Metrics ─────────────────────────────────────────────────────────────

function TimeMetrics({ time }: { time: DiagnosticsResponse['time'] }) {
  return (
    <GlassCard>
      <div className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-3">Timing Metrics</div>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {[
          { label: 'Raw Dead', value: formatSec(time.raw_dead_seconds) },
          { label: 'Capped Dead', value: formatSec(time.agg_dead_seconds) },
          { label: 'Raw Denied', value: formatSec(time.raw_denied_seconds) },
          { label: 'Cap Hits', value: fmtNum(time.cap_hits) },
          { label: 'Cap Seconds', value: formatSec(time.cap_seconds) },
        ].map(({ label, value }) => (
          <div key={label} className="text-center">
            <div className="text-[10px] text-slate-500 uppercase">{label}</div>
            <div className="text-sm font-bold text-white font-mono">{value}</div>
          </div>
        ))}
      </div>
    </GlassCard>
  );
}

// ── Monitoring ───────────────────────────────────────────────────────────────

function MonitoringPanel({ monitoring }: { monitoring: DiagnosticsResponse['monitoring'] }) {
  const entries = Object.entries(monitoring);
  if (!entries.length) return null;
  return (
    <GlassCard>
      <div className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-3">Monitoring History</div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {entries.map(([key, info]) => (
          <div key={key} className="rounded-lg border border-white/10 bg-slate-950/30 p-3">
            <div className="flex items-center gap-2 mb-1">
              <StatusDot color={info.error ? 'amber' : info.count > 0 ? 'green' : 'blue'} />
              <span className="text-xs font-bold text-white capitalize">{key}</span>
            </div>
            <div className="text-[11px] text-slate-400">
              {fmtNum(info.count)} records
              {info.last_recorded_at && <> &middot; Last: {new Date(info.last_recorded_at).toLocaleString()}</>}
            </div>
          </div>
        ))}
      </div>
    </GlassCard>
  );
}

// ── Data Flow ────────────────────────────────────────────────────────────────

function DataFlowPanel() {
  return (
    <GlassCard>
      <div className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-3">Data Flow Pipeline</div>
      <div className="space-y-1">
        {FLOW_STEPS.map((step, i) => (
          <div key={i} className="flex items-center gap-2 text-xs">
            <span className="text-cyan-400 font-mono min-w-[140px] text-right">{step.from}</span>
            <span className="text-slate-600">{'\u2192'}</span>
            <span className="text-emerald-400 font-mono min-w-[140px]">{step.to}</span>
            <span className="text-slate-500 text-[11px]">{step.label}</span>
          </div>
        ))}
      </div>
    </GlassCard>
  );
}

// ── Node Explorer ────────────────────────────────────────────────────────────

function NodeExplorer() {
  const [search, setSearch] = useState('');
  const [selectedGroup, setSelectedGroup] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return Object.entries(NODES).filter(([_, n]) => {
      if (selectedGroup && n.group !== selectedGroup) return false;
      if (q && !n.title.toLowerCase().includes(q) && !n.eli5.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [search, selectedGroup]);

  return (
    <GlassPanel>
      <div className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-3">System Components ({Object.keys(NODES).length})</div>

      <div className="flex flex-wrap gap-2 mb-3">
        <button
          onClick={() => setSelectedGroup(null)}
          className={`px-2.5 py-1 rounded-lg text-[11px] font-bold border transition ${!selectedGroup ? 'border-cyan-500/50 text-cyan-400 bg-cyan-500/10' : 'border-white/15 text-slate-400 hover:text-white'}`}
        >
          All
        </button>
        {Object.entries(GROUPS).map(([key, g]) => (
          <button
            key={key}
            onClick={() => setSelectedGroup(selectedGroup === key ? null : key)}
            className={`px-2.5 py-1 rounded-lg text-[11px] font-bold border transition ${selectedGroup === key ? 'border-cyan-500/50 text-cyan-400 bg-cyan-500/10' : 'border-white/15 text-slate-400 hover:text-white'}`}
          >
            {g.label}
          </button>
        ))}
      </div>

      <input
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search components..."
        className="w-full rounded-lg border border-white/10 bg-slate-950/50 px-3 py-2 text-xs text-white placeholder-slate-500 outline-none focus:border-cyan-500/50 mb-3"
      />

      <div className="space-y-1.5 max-h-[500px] overflow-y-auto">
        {filtered.map(([id, node]) => (
          <button
            key={id}
            onClick={() => setExpanded(expanded === id ? null : id)}
            className="w-full text-left rounded-lg border border-white/10 bg-slate-950/30 px-3 py-2 hover:border-cyan-500/30 transition"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className={`text-[10px] font-bold ${GROUPS[node.group]?.color ?? 'text-slate-500'}`}>
                  {GROUPS[node.group]?.label ?? node.group}
                </span>
                <span className="text-xs font-semibold text-white">{node.title}</span>
              </div>
              <span className="text-[11px] text-slate-500">{expanded === id ? '\u25B2' : '\u25BC'}</span>
            </div>
            {expanded === id && (
              <div className="mt-2 space-y-1 text-[11px]">
                <div className="text-slate-300">{node.eli5}</div>
                {node.files && <div className="text-slate-500 font-mono">{node.files}</div>}
              </div>
            )}
          </button>
        ))}
        {filtered.length === 0 && <div className="text-xs text-slate-500 text-center py-4">No matching components.</div>}
      </div>
    </GlassPanel>
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
        <PageHeader title="Admin Panel" subtitle="Operational diagnostics and architecture." eyebrow="Advanced" />
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
      <PageHeader title="Admin Panel" subtitle="System diagnostics and operational overview." eyebrow="Advanced" />

      <div className="flex items-center justify-between mb-4">
        <div className="text-[11px] text-slate-500">
          Last refresh: {diag?.timestamp ? new Date(diag.timestamp).toLocaleTimeString() : '--'}
        </div>
        <button
          onClick={handleRefresh}
          className="px-3 py-1.5 rounded-lg text-xs font-bold border border-white/10 text-slate-300 hover:border-cyan-500/40 hover:text-white transition"
        >
          Refresh Now
        </button>
      </div>

      {/* Health Dashboard */}
      <HealthDashboard diag={diag} apiStatus={apiStatus} />

      {/* Warnings */}
      <div className="mt-4">
        <WarningsPanel issues={diag?.issues ?? []} warnings={diag?.warnings ?? []} />
      </div>

      {/* Time Metrics + Monitoring */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4">
        <TimeMetrics time={diag?.time ?? {}} />
        <MonitoringPanel monitoring={diag?.monitoring ?? {}} />
      </div>

      {/* Tables + Data Flow */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4">
        <TablesStatus tables={diag?.tables ?? []} />
        <DataFlowPanel />
      </div>

      {/* Node Explorer */}
      <div className="mt-4">
        <NodeExplorer />
      </div>
    </div>
  );
}
