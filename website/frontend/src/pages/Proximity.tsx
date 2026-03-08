import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { PageHeader } from '../components/PageHeader';
import { GlassPanel } from '../components/GlassPanel';
import { GlassCard } from '../components/GlassCard';
import { Skeleton } from '../components/Skeleton';

const API = '/api';
const GRID = 512;

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

function LeaderList({ title, rows, format }: { title: string; rows: LeaderRow[]; format: (r: LeaderRow) => string }) {
  return (
    <GlassCard>
      <div className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2">{title}</div>
      {!rows.length ? (
        <div className="text-xs text-slate-500">No data yet</div>
      ) : (
        <div className="space-y-1">
          {rows.slice(0, 6).map((r, i) => (
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
      <div className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2">Recent Engagements</div>
      <div className="space-y-1 max-h-[300px] overflow-y-auto">
        {events.map((e, i) => (
          <div key={e.id ?? i} className="flex items-center justify-between text-xs rounded-lg border border-white/5 bg-slate-950/30 px-2.5 py-1.5">
            <div className="flex items-center gap-1.5 min-w-0">
              <span className="text-blue-400 truncate">{e.attacker_name}</span>
              <span className="text-slate-600">{'\u2192'}</span>
              <span className="text-rose-400 truncate">{e.target_name}</span>
            </div>
            <div className="flex items-center gap-3 text-[11px] text-slate-400 shrink-0">
              <span>{fmtDist(e.distance)}</span>
              <span>{fmtMs(e.reaction_ms)}</span>
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
      <div className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2">Trade Kills</div>
      {summary && (
        <div className="grid grid-cols-3 gap-3 mb-3">
          <div className="text-center"><div className="text-[10px] text-slate-500">Total</div><div className="text-lg font-bold text-white">{fmtNum(summary.total_trades)}</div></div>
          <div className="text-center"><div className="text-[10px] text-slate-500">Avg Dist</div><div className="text-lg font-bold text-cyan-400">{fmtDist(summary.avg_trade_distance)}</div></div>
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
    queryFn: () => fetch(`${API}/proximity/movers?${scopeParams}`).then((r) => r.json()),
    enabled: !!sessionDate && ready,
    staleTime: 30_000,
  });

  const { data: teamplay } = useQuery<Record<string, LeaderRow[]>>({
    queryKey: ['proximity-teamplay', scopeParams],
    queryFn: () => fetch(`${API}/proximity/teamplay?${scopeParams}&limit=6`).then((r) => r.json()),
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
    <>
      <PageHeader title="Proximity Analytics" subtitle="Combat engagement heatmaps and player movement analysis" />

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
            <div className="text-[10px] text-slate-500 uppercase">Engagements</div>
            <div className="text-lg font-bold text-white">{fmtNum(summary.total_engagements)}</div>
          </GlassCard>
          <GlassCard>
            <div className="text-[10px] text-slate-500 uppercase">Avg Distance</div>
            <div className="text-lg font-bold text-cyan-400">{fmtDist(summary.avg_distance)}</div>
          </GlassCard>
          <GlassCard>
            <div className="text-[10px] text-slate-500 uppercase">Avg Reaction</div>
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
              />
              <LeaderList
                title="Sprint Leaders"
                rows={movers?.sprint ?? []}
                format={(r) => fmtPct(r.sprint_pct as number)}
              />
              <LeaderList
                title="Reaction Leaders"
                rows={movers?.reaction ?? []}
                format={(r) => fmtMs(r.reaction_ms as number)}
              />
              <LeaderList
                title="Survival Leaders"
                rows={movers?.survival ?? []}
                format={(r) => r.duration_ms != null ? `${((r.duration_ms as number) / 1000).toFixed(1)}s` : '--'}
              />
            </div>

            {/* Teamplay */}
            <div className="grid grid-cols-2 gap-3">
              <LeaderList
                title="Crossfire Kills"
                rows={teamplay?.crossfire_kills ?? []}
                format={(r) => `${fmtNum(r.crossfire_kills as number)} (${fmtPct(r.kill_rate_pct as number)})`}
              />
              <LeaderList
                title="Team Sync"
                rows={teamplay?.sync ?? []}
                format={(r) => fmtMs(r.avg_delay_ms as number)}
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
    </>
  );
}
