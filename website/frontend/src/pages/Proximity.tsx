import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { PageHeader } from '../components/PageHeader';
import { GlassPanel } from '../components/GlassPanel';
import { GlassCard } from '../components/GlassCard';
import { Skeleton } from '../components/Skeleton';
import { DataTable, type Column } from '../components/DataTable';
import { InfoTip } from '../components/InfoTip';
import { ProximityIntro } from '../components/ProximityIntro';
import { useProximityLeaderboards, useProximitySessionScores } from '../api/hooks';
import type { ProximityLeaderboardEntry, SessionScoreEntry } from '../api/types';
import { METRICS, LEADERBOARD_HELP } from './proximity-glossary';

const API = '/api';
const GRID = 512;

// ── Leaderboard Types & Config ──────────────────────────────────────────────

const LEADERBOARD_TABS = [
  { key: 'power', label: 'Power Rating', unit: 'pts', desc: 'Composite 5-axis combat score' },
  { key: 'spawn', label: 'Spawn Timing', unit: 'score 0\u20131', desc: 'Kill efficiency vs respawn waves' },
  { key: 'crossfire', label: 'Crossfire', unit: 'kills', desc: 'Top crossfire duos (45\u00b0+ angle)' },
  { key: 'trades', label: 'Trade Kills', unit: 'trades', desc: 'Revenge kills within 3 seconds' },
  { key: 'reactions', label: 'Reactions', unit: 'ms', desc: 'Fastest return fire after being hit' },
  { key: 'survivors', label: 'Survivors', unit: '%', desc: 'Escape rate from engagements' },
  { key: 'movement', label: 'Movement', unit: 'u/s', desc: 'Speed & distance (\u2248300u = 5m)' },
  { key: 'focus_fire', label: 'Focus Fire', unit: 'score 0\u20131', desc: 'Coordinated multi-attacker bursts' },
] as const;

function formatLeaderValue(category: string, entry: ProximityLeaderboardEntry): string {
  switch (category) {
    case 'power': return `${entry.value}`;
    case 'spawn': return `${entry.value.toFixed(3)}`;
    case 'crossfire': return `${entry.value} kills`;
    case 'trades': return `${entry.value} trades`;
    case 'reactions': return `${entry.value}ms`;
    case 'survivors': return `${entry.value}%`;
    case 'movement': return `${entry.value} u/s`;
    case 'focus_fire': return `${entry.value.toFixed(3)}`;
    default: return String(entry.value);
  }
}

function formatLeaderDetail(category: string, entry: ProximityLeaderboardEntry): string {
  switch (category) {
    case 'power': {
      const axes = entry.axes as Record<string, number> | undefined;
      if (!axes) return '';
      return `A:${axes.aggression} W:${axes.awareness} T:${axes.teamplay} Ti:${axes.timing} M:${axes.mechanical}`;
    }
    case 'spawn': return `${entry.timed_kills ?? 0} kills, ${entry.avg_denial_ms ?? 0}ms denial`;
    case 'crossfire': return `${entry.total ?? 0} opportunities, ${entry.avg_delay_ms ?? 0}ms avg delay`;
    case 'trades': return `avg ${entry.avg_trade_ms ?? 0}ms`;
    case 'reactions': return `dodge ${entry.avg_dodge_ms ?? 0}ms, support ${entry.avg_support_ms ?? 0}ms`;
    case 'survivors': return `${entry.escapes ?? 0}/${entry.total ?? 0} engagements`;
    case 'movement': return `sprint ${entry.sprint_pct ?? 0}%, ${((entry.total_distance as number) ?? 0).toLocaleString()}u total`;
    case 'focus_fire': return `${entry.times_focused ?? 0}x focused, avg ${entry.avg_attackers ?? 0} attackers, ${entry.avg_damage ?? 0} dmg`;
    default: return '';
  }
}

// ── Types ────────────────────────────────────────────────────────────────────

interface ScopeSession { session_date: string; maps: Array<{ map_name: string; rounds: Array<{ round_number: number; round_start_unix: number }> }> }
interface ScopeData { sessions: ScopeSession[]; scope?: { session_date: string } }
interface SummaryData { ready: boolean; status?: string; message?: string; total_engagements?: number; sample_rounds?: number; avg_distance?: number; avg_reaction_ms?: number }
interface HotzonePoint { x: number; y: number; count: number; team?: string }
interface HotzoneData { hotzones: HotzonePoint[]; map_name?: string; image_path?: string }
interface EventItem { id: number; target_name: string; attacker_name: string; target_team: string; attacker_team: string; distance: number; reaction_ms: number; weapon?: string; timestamp_ms?: number }
interface EventsData { events: EventItem[] }
interface LeaderRow { name: string; [key: string]: unknown }
interface TradesSummary { total_trades?: number; avg_trade_distance?: number; win_rate_pct?: number }
interface TradeEvent { id?: number; killer: string; victim: string; weapon?: string; distance?: number; trade_ms?: number }

// ── Helpers ──────────────────────────────────────────────────────────────────

function fmtNum(v: number | null | undefined) { return v != null ? v.toLocaleString() : '--'; }
function fmtMs(v: number | null | undefined) { return v != null ? `${v.toFixed(0)}ms` : '--'; }
function fmtDist(v: number | null | undefined) { return v != null ? `${Math.round(v)}u` : '--'; }
function fmtPct(v: number | null | undefined) { return v != null ? `${v.toFixed(1)}%` : '--'; }

function buildParams(state: { sessionDate: string | null; mapName: string | null; roundNumber: number | null; roundStartUnix: number | null }) {
  const p = new URLSearchParams();
  if (state.sessionDate) p.set('session_date', state.sessionDate);
  if (state.mapName) p.set('map_name', state.mapName);
  if (state.roundNumber != null) p.set('round_number', String(state.roundNumber));
  if (state.roundStartUnix) p.set('round_start_unix', String(state.roundStartUnix));
  return p.toString();
}

// ── Heatmap Canvas ───────────────────────────────────────────────────────────

function HeatmapCanvas({ hotzones, mapImage, intensity = 1.0 }: { hotzones: HotzonePoint[]; mapImage: string | null; intensity: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);

  useEffect(() => {
    if (!mapImage) { imgRef.current = null; return; }
    const img = new Image();
    img.onload = () => { imgRef.current = img; draw(); };
    img.onerror = () => { imgRef.current = null; draw(); };
    img.src = mapImage;
  }, [mapImage]);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const w = canvas.width;
    const h = canvas.height;

    ctx.clearRect(0, 0, w, h);

    // Background
    if (imgRef.current) {
      ctx.drawImage(imgRef.current, 0, 0, w, h);
    } else {
      ctx.fillStyle = 'rgba(15, 23, 42, 0.9)';
      ctx.fillRect(0, 0, w, h);
    }

    if (!hotzones.length) return;

    const maxCount = Math.max(...hotzones.map((p) => p.count), 1);
    for (const p of hotzones) {
      const nx = (p.x / GRID) * w;
      const ny = (1 - p.y / GRID) * h;
      const alpha = Math.min(1, (p.count / maxCount) * intensity * 0.8 + 0.1);
      const r = Math.max(4, (p.count / maxCount) * 12);

      const team = String(p.team ?? '').toUpperCase();
      if (team === 'AXIS' || team === '1') {
        ctx.fillStyle = `rgba(239, 68, 68, ${alpha})`;
      } else if (team === 'ALLIES' || team === '2') {
        ctx.fillStyle = `rgba(59, 130, 246, ${alpha})`;
      } else {
        ctx.fillStyle = `rgba(56, 189, 248, ${alpha})`;
      }

      ctx.beginPath();
      ctx.arc(nx, ny, r, 0, Math.PI * 2);
      ctx.fill();
    }
  }, [hotzones, intensity]);

  useEffect(() => { draw(); }, [draw]);

  return (
    <canvas
      ref={canvasRef}
      width={GRID}
      height={GRID}
      className="w-full max-w-[512px] aspect-square rounded-xl border border-white/10"
    />
  );
}

// ── Leader List ──────────────────────────────────────────────────────────────

function LeaderList({ title, rows, format, tip }: { title: string; rows: LeaderRow[]; format: (r: LeaderRow) => string; tip?: string }) {
  return (
    <GlassCard>
      <div className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2">
        {title}
        {tip && <InfoTip>{tip}</InfoTip>}
      </div>
      {!rows.length ? (
        <div className="text-xs text-slate-500">No data yet</div>
      ) : (
        <div className="space-y-1">
          {rows.map((r, i) => (
            <div key={i} className="flex items-center justify-between text-xs">
              <span className="text-slate-200 truncate">{r.name}</span>
              <span className="text-cyan-400 font-mono text-[11px]">{format(r)}</span>
            </div>
          ))}
        </div>
      )}
    </GlassCard>
  );
}

// ── Event List ───────────────────────────────────────────────────────────────

function EventList({ events }: { events: EventItem[] }) {
  if (!events.length) return null;
  return (
    <GlassCard>
      <div className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2">
        Recent Engagements
        <InfoTip label="Engagement Events">
          <p>Individual combat encounters. Each row shows attacker → target with distance (game units, ~300u = 5m) and fight duration (ms).</p>
        </InfoTip>
      </div>
      <div className="space-y-1 max-h-[300px] overflow-y-auto">
        {events.map((e, i) => (
          <div key={e.id ?? i} className="flex items-center justify-between text-xs rounded-lg border border-white/5 bg-slate-950/30 px-2.5 py-1.5">
            <div className="flex items-center gap-1.5 min-w-0">
              <span className="text-blue-400 truncate">{e.attacker_name}</span>
              <span className="text-slate-600">{'\u2192'}</span>
              <span className="text-rose-400 truncate">{e.target_name}</span>
            </div>
            <div className="flex items-center gap-3 text-[11px] text-slate-400 shrink-0">
              <span title="Distance (game units)">{fmtDist(e.distance)}</span>
              <span title="Fight duration (ms)">{fmtMs(e.reaction_ms)}</span>
              {e.weapon && <span className="text-slate-500">{e.weapon}</span>}
            </div>
          </div>
        ))}
      </div>
    </GlassCard>
  );
}

// ── Trades Panel ─────────────────────────────────────────────────────────────

function TradesPanel({ summary, events }: { summary: TradesSummary | null; events: TradeEvent[] }) {
  return (
    <GlassCard>
      <div className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2">
        Trade Kills
        <InfoTip label={METRICS.trade_kill.label}>
          <p>{METRICS.trade_kill.oneLiner}</p>
          <p className="mt-1.5 text-slate-400">{METRICS.trade_kill.detail}</p>
        </InfoTip>
      </div>
      {summary && (
        <div className="grid grid-cols-3 gap-3 mb-3">
          <div className="text-center"><div className="text-[10px] text-slate-500">Total</div><div className="text-lg font-bold text-white">{fmtNum(summary.total_trades)}</div></div>
          <div className="text-center"><div className="text-[10px] text-slate-500">Avg Dist <span className="text-slate-600">(u)</span></div><div className="text-lg font-bold text-cyan-400">{fmtDist(summary.avg_trade_distance)}</div></div>
          <div className="text-center"><div className="text-[10px] text-slate-500">Win Rate</div><div className="text-lg font-bold text-emerald-400">{fmtPct(summary.win_rate_pct)}</div></div>
        </div>
      )}
      {events.length > 0 && (
        <div className="space-y-1">
          {events.slice(0, 8).map((e, i) => (
            <div key={e.id ?? i} className="flex items-center justify-between text-xs">
              <span className="text-slate-200">{e.killer} {'\u2192'} {e.victim}</span>
              <span className="text-slate-400">{fmtDist(e.distance)} {e.trade_ms != null ? `${e.trade_ms}ms` : ''}</span>
            </div>
          ))}
        </div>
      )}
      {!summary && !events.length && <div className="text-xs text-slate-500">No trade data in this scope.</div>}
    </GlassCard>
  );
}

// ── Session Score ────────────────────────────────────────────────────────────

function SessionScorePanel({ sessionDate }: { sessionDate: string | null }) {
  const { data, isLoading } = useProximitySessionScores(sessionDate ?? undefined);

  if (isLoading) return <Skeleton variant="card" count={1} />;
  if (!data?.players?.length) return null;

  const cats = ['kill_timing', 'crossfire', 'focus_fire', 'trades', 'survivability', 'movement', 'reactions'] as const;
  const catLabels: Record<string, string> = {
    kill_timing: 'Timing', crossfire: 'XFire', focus_fire: 'Focus',
    trades: 'Trade', survivability: 'Survive', movement: 'Move', reactions: 'React',
  };

  return (
    <div className="mt-8">
      <GlassPanel>
        <div className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1">
          Session Combat Score
        </div>
        <div className="text-[10px] text-slate-500 mb-4">
          Composite score (0-100) from 7 proximity categories for {data.session_date}
        </div>
        <div className="space-y-2">
          {data.players.map((p, i) => {
            const pct = Math.min(p.total_score, 100);
            return (
              <div key={p.guid} className="bg-slate-900/50 rounded-lg p-3 border border-white/5">
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2">
                    <span className={`font-bold text-sm ${i < 3 ? 'text-amber-400' : 'text-slate-500'}`}>
                      #{i + 1}
                    </span>
                    <span className="text-white font-medium text-sm truncate">{p.name}</span>
                    <span className="text-slate-600 text-[10px]">{p.engagement_count} eng</span>
                  </div>
                  <span className="text-cyan-400 font-mono font-bold text-lg">{p.total_score.toFixed(1)}</span>
                </div>
                <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden mb-1.5">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-teal-400"
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-slate-500">
                  {cats.map((c) => (
                    <span key={c} title={p.categories[c]?.detail ?? ''}>
                      {catLabels[c]}: <span className="text-slate-400">{(p.categories[c]?.weighted ?? 0).toFixed(0)}</span>
                    </span>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </GlassPanel>
    </div>
  );
}

// ── Leaderboard Tabs ─────────────────────────────────────────────────────────

function LeaderboardTabs() {
  const [activeTab, setActiveTab] = useState('power');
  const [rangeDays, setRangeDays] = useState(30);

  const { data, isLoading } = useProximityLeaderboards(activeTab, rangeDays, 10);

  const tabInfo = LEADERBOARD_TABS.find((t) => t.key === activeTab);

  const columns = useMemo((): Column<ProximityLeaderboardEntry>[] => [
    {
      key: 'rank',
      label: '#',
      className: 'w-12 text-center',
      render: (_row, i) => (
        <span className={`font-bold ${i < 3 ? 'text-amber-400' : 'text-slate-500'}`}>#{i + 1}</span>
      ),
    },
    {
      key: 'name',
      label: 'Player',
      render: (row) => (
        <span className="text-slate-200 font-medium truncate">
          {activeTab === 'crossfire' ? `${row.name} + ${row.partner_name ?? '?'}` : row.name}
        </span>
      ),
    },
    {
      key: 'value',
      label: tabInfo?.label ?? 'Value',
      sortable: true,
      sortValue: (row) => row.value,
      className: 'text-right',
      headerClassName: 'text-right',
      render: (row) => (
        <span className="text-cyan-400 font-mono font-bold">{formatLeaderValue(activeTab, row)}</span>
      ),
    },
    {
      key: 'detail',
      label: 'Detail',
      className: 'hidden md:table-cell text-slate-500 text-[11px] max-w-[280px]',
      headerClassName: 'hidden md:table-cell',
      render: (row) => (
        <span className="truncate block">{formatLeaderDetail(activeTab, row)}</span>
      ),
    },
  ], [activeTab, tabInfo]);

  return (
    <div className="mt-8">
      <GlassPanel>
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="text-xs font-bold uppercase tracking-widest text-slate-400">Proximity Leaderboards</div>
            <div className="text-[10px] text-slate-500 mt-0.5">{tabInfo?.desc ?? ''}</div>
          </div>
          <select
            value={rangeDays}
            onChange={(e) => setRangeDays(parseInt(e.target.value, 10))}
            className="rounded-lg border border-white/10 bg-slate-950/70 px-2 py-1 text-xs text-white outline-none focus:border-cyan-500/50"
          >
            <option value={7}>7 days</option>
            <option value={30}>30 days</option>
            <option value={90}>90 days</option>
            <option value={365}>All time</option>
          </select>
        </div>

        {/* Tab buttons */}
        <div className="flex flex-wrap gap-1.5 mb-2">
          {LEADERBOARD_TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold border transition ${
                activeTab === tab.key
                  ? 'border-cyan-500/50 bg-cyan-500/10 text-cyan-400'
                  : 'border-white/10 text-slate-400 hover:border-white/20 hover:text-slate-300'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        {LEADERBOARD_HELP[activeTab] && (
          <div className="text-[10px] text-slate-500 leading-relaxed mb-4 max-w-2xl">
            {LEADERBOARD_HELP[activeTab]}
          </div>
        )}

        {/* Results */}
        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-10 rounded-lg bg-slate-800/50 animate-pulse" />
            ))}
          </div>
        ) : (
          <DataTable
            columns={columns}
            data={data?.entries ?? []}
            keyFn={(row) => row.guid + (row.partner_guid ?? '')}
            defaultSort={{ key: 'value', dir: 'desc' }}
            emptyMessage="No data for this category in the selected time range."
          />
        )}
      </GlassPanel>
    </div>
  );
}

// ── Main Page ────────────────────────────────────────────────────────────────

export default function Proximity() {
  const [sessionDate, setSessionDate] = useState<string | null>(null);
  const [mapName, setMapName] = useState<string | null>(null);
  const [roundNumber, setRoundNumber] = useState<number | null>(null);
  const [roundStartUnix, setRoundStartUnix] = useState<number | null>(null);
  const [heatIntensity, setHeatIntensity] = useState(1.0);

  const scope = useMemo(() => ({ sessionDate, mapName, roundNumber, roundStartUnix }), [sessionDate, mapName, roundNumber, roundStartUnix]);
  const scopeParams = useMemo(() => buildParams(scope), [scope]);

  // Scopes
  const { data: scopes, isLoading: scopesLoading } = useQuery<ScopeData>({
    queryKey: ['proximity-scopes'],
    queryFn: () => fetch(`${API}/proximity/scopes?range_days=365`).then((r) => r.json()),
    staleTime: 60_000,
  });

  // Auto-select first session
  useEffect(() => {
    if (!sessionDate && scopes?.sessions?.length) {
      setSessionDate(scopes.scope?.session_date ?? scopes.sessions[0].session_date);
    }
  }, [scopes, sessionDate]);

  const selectedSession = scopes?.sessions?.find((s) => s.session_date === sessionDate);
  const availableMaps = selectedSession?.maps ?? [];
  const selectedMap = availableMaps.find((m) => m.map_name === mapName);
  const availableRounds = selectedMap?.rounds ?? [];

  // Data queries
  const { data: summary } = useQuery<SummaryData>({
    queryKey: ['proximity-summary', scopeParams],
    queryFn: () => fetch(`${API}/proximity/summary?${scopeParams}`).then((r) => r.json()),
    enabled: !!sessionDate,
    staleTime: 30_000,
  });

  const ready = summary?.ready === true || summary?.status === 'ok' || summary?.status === 'ready';

  const { data: hotzones } = useQuery<HotzoneData>({
    queryKey: ['proximity-hotzones', scopeParams],
    queryFn: () => fetch(`${API}/proximity/hotzones?${scopeParams}`).then((r) => r.json()),
    enabled: !!sessionDate && ready,
    staleTime: 30_000,
  });

  const { data: events } = useQuery<EventsData>({
    queryKey: ['proximity-events', scopeParams],
    queryFn: () => fetch(`${API}/proximity/events?${scopeParams}&limit=20`).then((r) => r.json()),
    enabled: !!sessionDate && ready,
    staleTime: 30_000,
  });

  const { data: movers } = useQuery<Record<string, LeaderRow[]>>({
    queryKey: ['proximity-movers', scopeParams],
    queryFn: () => fetch(`${API}/proximity/movers?${scopeParams}&limit=50`).then((r) => r.json()),
    enabled: !!sessionDate && ready,
    staleTime: 30_000,
  });

  const { data: teamplay } = useQuery<Record<string, LeaderRow[]>>({
    queryKey: ['proximity-teamplay', scopeParams],
    queryFn: () => fetch(`${API}/proximity/teamplay?${scopeParams}&limit=50`).then((r) => r.json()),
    enabled: !!sessionDate && ready,
    staleTime: 30_000,
  });

  const { data: tradesSummary } = useQuery<TradesSummary>({
    queryKey: ['proximity-trades-summary', scopeParams],
    queryFn: () => fetch(`${API}/proximity/trades/summary?${scopeParams}`).then((r) => r.json()),
    enabled: !!sessionDate && ready,
    staleTime: 30_000,
  });

  const { data: tradesEvents } = useQuery<{ events: TradeEvent[] }>({
    queryKey: ['proximity-trades-events', scopeParams],
    queryFn: () => fetch(`${API}/proximity/trades/events?${scopeParams}&limit=10`).then((r) => r.json()),
    enabled: !!sessionDate && ready,
    staleTime: 30_000,
  });

  // Scope handlers
  const handleSessionChange = useCallback((v: string) => {
    setSessionDate(v || null);
    setMapName(null);
    setRoundNumber(null);
    setRoundStartUnix(null);
  }, []);

  const handleMapChange = useCallback((v: string) => {
    setMapName(v || null);
    setRoundNumber(null);
    setRoundStartUnix(null);
  }, []);

  const handleRoundChange = useCallback((v: string) => {
    if (!v) { setRoundNumber(null); setRoundStartUnix(null); return; }
    const [rn, rs] = v.split('|');
    setRoundNumber(parseInt(rn, 10) || null);
    setRoundStartUnix(parseInt(rs || '0', 10) || null);
  }, []);

  const handleReset = useCallback(() => {
    setSessionDate(scopes?.sessions?.[0]?.session_date ?? null);
    setMapName(null);
    setRoundNumber(null);
    setRoundStartUnix(null);
  }, [scopes]);

  if (scopesLoading) return <Skeleton variant="card" count={3} />;

  return (
    <div className="page-shell">
      <PageHeader
        title="Proximity Analytics"
        subtitle="Real-time combat telemetry from the game server — every fight, trade, and team play measured automatically."
        eyebrow="Advanced"
      />

      <ProximityIntro />

      {/* Scope Selectors */}
      <GlassPanel>
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="text-[10px] text-slate-500 uppercase block mb-1">Session</label>
            <select
              value={sessionDate ?? ''}
              onChange={(e) => handleSessionChange(e.target.value)}
              className="rounded-lg border border-white/10 bg-slate-950/70 px-3 py-1.5 text-xs text-white outline-none focus:border-cyan-500/50"
            >
              {(scopes?.sessions ?? []).map((s) => (
                <option key={s.session_date} value={s.session_date}>{s.session_date}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-[10px] text-slate-500 uppercase block mb-1">Map</label>
            <select
              value={mapName ?? ''}
              onChange={(e) => handleMapChange(e.target.value)}
              className="rounded-lg border border-white/10 bg-slate-950/70 px-3 py-1.5 text-xs text-white outline-none focus:border-cyan-500/50"
            >
              <option value="">All Maps</option>
              {availableMaps.map((m) => (
                <option key={m.map_name} value={m.map_name}>{m.map_name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-[10px] text-slate-500 uppercase block mb-1">Round</label>
            <select
              value={roundNumber != null ? `${roundNumber}|${roundStartUnix ?? 0}` : ''}
              onChange={(e) => handleRoundChange(e.target.value)}
              className="rounded-lg border border-white/10 bg-slate-950/70 px-3 py-1.5 text-xs text-white outline-none focus:border-cyan-500/50"
            >
              <option value="">All Rounds</option>
              {availableRounds.map((r) => (
                <option key={`${r.round_number}-${r.round_start_unix}`} value={`${r.round_number}|${r.round_start_unix}`}>
                  Round {r.round_number}
                </option>
              ))}
            </select>
          </div>
          <button
            onClick={handleReset}
            className="px-3 py-1.5 rounded-lg text-xs font-bold border border-white/10 text-slate-300 hover:border-cyan-500/40 transition"
          >
            Reset
          </button>
        </div>
        <div className="text-[10px] text-slate-500 mt-2">
          Filter by gaming session, map, or individual round. Each session is one continuous play period (60-minute gap = new session).
        </div>
      </GlassPanel>

      {/* Summary Stats */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">
          <GlassCard>
            <div className="text-[10px] text-slate-500 uppercase">Status</div>
            <div className={`text-sm font-bold ${ready ? 'text-emerald-400' : 'text-amber-400'}`}>
              {ready ? 'Live' : 'Prototype'}
            </div>
          </GlassCard>
          <GlassCard>
            <div className="flex items-center gap-1 text-[10px] text-slate-500 uppercase">
              Engagements
              <InfoTip label={METRICS.engagement.label}>
                <p>{METRICS.engagement.oneLiner}</p>
                <p className="mt-1.5 text-slate-400">{METRICS.engagement.detail}</p>
                {METRICS.engagement.howMeasured && <p className="mt-1.5 text-slate-500 text-[10px]">{METRICS.engagement.howMeasured}</p>}
              </InfoTip>
            </div>
            <div className="text-lg font-bold text-white">{fmtNum(summary.total_engagements)}</div>
          </GlassCard>
          <GlassCard>
            <div className="flex items-center gap-1 text-[10px] text-slate-500 uppercase">
              Avg Distance <span className="normal-case text-slate-600">(u)</span>
              <InfoTip label={METRICS.distance.label}>
                <p>{METRICS.distance.oneLiner}</p>
                <p className="mt-1.5 text-slate-400">{METRICS.distance.detail}</p>
              </InfoTip>
            </div>
            <div className="text-lg font-bold text-cyan-400">{fmtDist(summary.avg_distance)}</div>
          </GlassCard>
          <GlassCard>
            <div className="flex items-center gap-1 text-[10px] text-slate-500 uppercase">
              Avg Fight Duration <span className="normal-case text-slate-600">(ms)</span>
              <InfoTip label={METRICS.avg_duration.label}>
                <p>{METRICS.avg_duration.oneLiner}</p>
                <p className="mt-1.5 text-slate-400">{METRICS.avg_duration.detail}</p>
                {METRICS.avg_duration.howMeasured && <p className="mt-1.5 text-slate-500 text-[10px]">{METRICS.avg_duration.howMeasured}</p>}
              </InfoTip>
            </div>
            <div className="text-lg font-bold text-amber-400">{fmtMs(summary.avg_reaction_ms)}</div>
          </GlassCard>
        </div>
      )}

      {!ready && summary?.message && (
        <div className="mt-4 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-400">
          {summary.message}
        </div>
      )}

      {ready && (
        <div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Heatmap */}
          <div>
            <GlassPanel>
              <div className="flex items-center justify-between mb-3">
                <div className="text-xs font-bold uppercase tracking-widest text-slate-400">Engagement Heatmap</div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-slate-500">Intensity</span>
                  <input
                    type="range"
                    min="0.6"
                    max="1.8"
                    step="0.1"
                    value={heatIntensity}
                    onChange={(e) => setHeatIntensity(parseFloat(e.target.value))}
                    className="w-20 accent-cyan-500"
                  />
                  <span className="text-[10px] text-cyan-400 w-8">{heatIntensity.toFixed(1)}x</span>
                </div>
              </div>
              <HeatmapCanvas
                hotzones={hotzones?.hotzones ?? []}
                mapImage={hotzones?.image_path ?? null}
                intensity={heatIntensity}
              />
              <div className="flex items-center gap-4 mt-2 text-[10px]">
                <div className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-blue-500" />Allies</div>
                <div className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-rose-500" />Axis</div>
              </div>
            </GlassPanel>
          </div>

          {/* Right side panels */}
          <div className="space-y-4">
            {/* Leaderboards */}
            <div className="grid grid-cols-2 gap-3">
              <LeaderList
                title="Distance Leaders"
                rows={movers?.distance ?? []}
                format={(r) => fmtDist(r.total_distance as number)}
                tip="Total distance covered in game units (~300u = 5m). More distance = more active map movement."
              />
              <LeaderList
                title="Sprint Leaders"
                rows={movers?.sprint ?? []}
                format={(r) => fmtPct(r.sprint_pct as number)}
                tip="Percentage of time spent sprinting (~300 u/s). Higher sprint % = more aggressive positioning."
              />
              <LeaderList
                title="Return Fire Leaders"
                rows={movers?.reaction ?? []}
                format={(r) => fmtMs(r.reaction_ms as number)}
                tip="Fastest return fire — time (ms) to shoot back after being hit. Lower = faster reflexes."
              />
              <LeaderList
                title="Survival Leaders"
                rows={movers?.survival ?? []}
                format={(r) => r.duration_ms != null ? `${((r.duration_ms as number) / 1000).toFixed(1)}s` : '--'}
                tip="Players who survived longest in engagements. Escape = moved 300+ units from attacker for 5 seconds."
              />
            </div>

            {/* Teamplay */}
            <div className="grid grid-cols-2 gap-3">
              <LeaderList
                title="Crossfire Kills"
                rows={teamplay?.crossfire_kills ?? []}
                format={(r) => `${fmtNum(r.crossfire_kills as number)} (${fmtPct(r.kill_rate_pct as number)})`}
                tip="Kills involving crossfire — 2+ teammates attacking the same enemy from 45°+ angular separation within 2000 units."
              />
              <LeaderList
                title="Team Sync"
                rows={teamplay?.sync ?? []}
                format={(r) => fmtMs(r.avg_delay_ms as number)}
                tip="Average delay (ms) between teammates engaging the same target. Lower = more synchronized attacks."
              />
            </div>
          </div>
        </div>
      )}

      {ready && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
          <EventList events={events?.events ?? []} />
          <TradesPanel summary={tradesSummary ?? null} events={tradesEvents?.events ?? []} />
        </div>
      )}

      {/* Session Combat Scores */}
      <SessionScorePanel sessionDate={sessionDate} />

      {/* Proximity Leaderboards */}
      <LeaderboardTabs />
    </div>
  );
}
