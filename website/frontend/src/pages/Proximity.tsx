import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { PageHeader } from '../components/PageHeader';
import { GlassPanel } from '../components/GlassPanel';
import { GlassCard } from '../components/GlassCard';
import { Skeleton } from '../components/Skeleton';
import { DataTable, type Column } from '../components/DataTable';
import { InfoTip } from '../components/InfoTip';
import { ProximityIntro } from '../components/ProximityIntro';
import { useProximityLeaderboards, useProximitySessionScores, useProximityKillOutcomes, useProximityKillOutcomePlayerStats, useProximityHitRegions, useProximityHeadshotRates, useCombatHeatmap, useKillLines, useDangerZones, useMovementStats, useProxScores, useProxFormula } from '../api/hooks';
import type { ProximityLeaderboardEntry, SessionScoreEntry, HitRegionPlayer, HeadshotRateEntry, MovementStatsPlayer, ProxScorePlayer } from '../api/types';
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

/** Strip ET:Legacy color codes (^0-^9, ^a-^z, ^A-^Z) from player names */
function stripColors(name: string): string { return name.replace(/\^[0-9a-zA-Z]/g, ''); }

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
              <span className="text-slate-200 truncate">{stripColors(String(r.name))}</span>
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
              <span className="text-blue-400 truncate">{stripColors(e.attacker_name)}</span>
              <span className="text-slate-600">{'\u2192'}</span>
              <span className="text-rose-400 truncate">{stripColors(e.target_name)}</span>
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
              <span className="text-slate-200">{stripColors(e.killer)} {'\u2192'} {stripColors(e.victim)}</span>
              <span className="text-slate-400">{fmtDist(e.distance)} {e.trade_ms != null ? `${e.trade_ms}ms` : ''}</span>
            </div>
          ))}
        </div>
      )}
      {!summary && !events.length && <div className="text-xs text-slate-500">No trade data in this scope.</div>}
    </GlassCard>
  );
}

// ── Proximity Composite Scores ───────────────────────────────────────────────

const SCORE_COLORS = {
  prox_combat: '#ef4444',
  prox_team: '#60a5fa',
  prox_gamesense: '#f59e0b',
  prox_overall: '#22c55e',
};

function ProxScoresPanel() {
  const [rangeDays, setRangeDays] = useState(30);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [showFormula, setShowFormula] = useState(false);
  const { data, isLoading } = useProxScores(rangeDays, undefined, 30);
  const { data: formula } = useProxFormula();

  if (isLoading) return <Skeleton variant="card" count={1} />;

  const players = data?.players ?? [];
  if (players.length === 0) return null;

  return (
    <div className="mt-6">
      <GlassPanel>
        <div className="flex items-center justify-between mb-3">
          <div>
            <div className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1">
              Proximity Score
            </div>
            <div className="text-[10px] text-slate-500">
              Composite rating from {Object.keys(formula?.categories ?? {}).length || 3} categories, {
                Object.values(formula?.categories ?? {}).reduce((a, c) => a + Object.keys(c.metrics).length, 0) || 18
              } metrics — v{data?.version ?? '1.0'}
            </div>
          </div>
          <div className="flex gap-2 items-center">
            <button
              className={`px-2 py-0.5 rounded text-[10px] font-medium ${showFormula ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40' : 'bg-slate-800 text-slate-500 border border-slate-700'}`}
              onClick={() => { setShowFormula(!showFormula); }}
            >Formula</button>
            <div className="flex gap-1">
              {[14, 30, 90].map(d => (
                <button
                  key={d}
                  className={`px-2 py-0.5 rounded text-[10px] font-medium ${rangeDays === d ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/40' : 'bg-slate-800 text-slate-500 border border-slate-700'}`}
                  onClick={() => { setRangeDays(d); }}
                >{d}d</button>
              ))}
            </div>
          </div>
        </div>

        {/* Formula transparency panel */}
        {showFormula && formula && (
          <div className="mb-4 p-3 rounded-lg bg-slate-800/40 border border-slate-700/40">
            <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-2">
              Scoring Formula v{data?.version ?? '1.0'}
            </div>
            <div className="text-[10px] text-slate-500 mb-3">
              Each metric is ranked as a percentile (0-100) across all players with {formula.min_engagements}+ engagements, then weighted within its category.
              Overall = {Object.entries(formula.category_weights).map(([k, w]) => {
                const cat = formula.categories[k as keyof typeof formula.categories];
                return cat ? `${cat.label} ${((w as number) * 100).toFixed(0)}%` : '';
              }).filter(Boolean).join(' + ')}.
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {Object.entries(formula.categories).map(([catKey, cat]) => (
                <div key={catKey}>
                  {/* eslint-disable-next-line security/detect-object-injection */}
                  <div className="text-xs font-bold mb-1" style={{ color: SCORE_COLORS[catKey as keyof typeof SCORE_COLORS] }}>
                    {cat.label} <span className="font-normal text-slate-500">({((formula.category_weights[catKey as keyof typeof formula.category_weights] as number) * 100).toFixed(0)}%)</span>
                  </div>
                  <div className="text-[10px] text-slate-500 mb-1.5">{cat.description}</div>
                  <div className="space-y-0.5">
                    {Object.entries(cat.metrics).map(([mk, m]) => (
                      <div key={mk} className="flex items-center justify-between text-[10px]">
                        <span className="text-slate-400">{m.label}{m.invert ? ' *' : ''}</span>
                        <span className="text-slate-600 font-mono">{((m.weight as number) * 100).toFixed(0)}%</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            <div className="text-[9px] text-slate-600 mt-2">* Inverted metrics: lower = better (e.g., faster reaction time scores higher)</div>
          </div>
        )}

        {/* Header row */}
        <div className="grid grid-cols-[2rem_1fr_4rem_4rem_4rem_4.5rem] gap-1 text-[10px] text-slate-500 font-bold uppercase mb-1 px-1">
          <span>#</span>
          <span>Player</span>
          <span className="text-right" style={{ color: SCORE_COLORS.prox_combat }}>Combat</span>
          <span className="text-right" style={{ color: SCORE_COLORS.prox_team }}>Team</span>
          <span className="text-right" style={{ color: SCORE_COLORS.prox_gamesense }}>Sense</span>
          <span className="text-right" style={{ color: SCORE_COLORS.prox_overall }}>Overall</span>
        </div>

        <div className="space-y-0.5">
          {players.map(p => (
            <div key={p.guid}>
              <button
                className="w-full grid grid-cols-[2rem_1fr_4rem_4rem_4rem_4.5rem] gap-1 items-center text-xs px-1 py-1 rounded hover:bg-slate-800/50 transition-colors"
                onClick={() => { setExpanded(expanded === p.guid ? null : p.guid); }}
              >
                <span className="text-slate-600 font-mono text-right">{p.rank}</span>
                <span className="truncate text-slate-200 text-left">{stripColors(p.name)}</span>
                <span className="font-mono font-bold text-right" style={{ color: SCORE_COLORS.prox_combat }}>{p.prox_combat.toFixed(1)}</span>
                <span className="font-mono font-bold text-right" style={{ color: SCORE_COLORS.prox_team }}>{p.prox_team.toFixed(1)}</span>
                <span className="font-mono font-bold text-right" style={{ color: SCORE_COLORS.prox_gamesense }}>{p.prox_gamesense.toFixed(1)}</span>
                <span className="font-mono font-black text-right" style={{ color: SCORE_COLORS.prox_overall }}>{p.prox_overall.toFixed(1)}</span>
              </button>

              {/* Expanded breakdown */}
              {expanded === p.guid && (
                <div className="ml-8 mb-2 p-2 rounded bg-slate-800/30 border border-slate-700/30">
                  {/* Mini radar */}
                  <div className="flex gap-4 mb-2">
                    {p.prox_radar.map((axis, i) => (
                      <div key={i} className="text-center">
                        <div className="text-[10px] text-slate-500">{axis.label}</div>
                        <div className="text-sm font-bold text-white">{axis.value.toFixed(0)}</div>
                      </div>
                    ))}
                  </div>
                  {/* Per-category metric breakdown */}
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    {Object.entries(p.breakdown).map(([catKey, metrics]) => (
                      <div key={catKey}>
                        {/* eslint-disable-next-line security/detect-object-injection */}
                        <div className="text-[10px] font-bold uppercase mb-1" style={{ color: SCORE_COLORS[catKey as keyof typeof SCORE_COLORS] }}>
                          {/* eslint-disable-next-line security/detect-object-injection */}
                          {formula?.categories[catKey]?.label ?? catKey}
                        </div>
                        {Object.entries(metrics).map(([mk, m]) => (
                          <div key={mk} className="flex items-center gap-1 text-[10px]">
                            <span className="text-slate-500 w-20 truncate">{m.label}</span>
                            <div className="flex-1 h-1.5 rounded-full bg-slate-700 overflow-hidden">
                              <div className="h-full rounded-full bg-cyan-500/60" style={{ width: `${m.percentile * 100}%` }} />
                            </div>
                            <span className="text-slate-400 font-mono w-8 text-right">{(m.percentile * 100).toFixed(0)}</span>
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                  <div className="text-[10px] text-slate-600 mt-1">{p.engagements} engagements, {p.tracks} tracks</div>
                </div>
              )}
            </div>
          ))}
        </div>
      </GlassPanel>
    </div>
  );
}

// ── Kill Outcomes (v5.2) ─────────────────────────────────────────────────────

const OUTCOME_COLORS: Record<string, string> = {
  gibbed: '#ef4444',     // red
  revived: '#22c55e',    // green
  tapped_out: '#f59e0b', // amber
  expired: '#64748b',    // slate
  round_end: '#6366f1',  // indigo
};

function KillOutcomesPanel() {
  const { data: outcomes, isLoading: outcomesLoading } = useProximityKillOutcomes();
  const { data: playerStats, isLoading: statsLoading } = useProximityKillOutcomePlayerStats(30);

  if (outcomesLoading && statsLoading) return <Skeleton variant="card" count={1} />;

  const s = outcomes?.summary;
  if (!s || s.total_kills === 0) return null;

  // Simple bar visualization for outcome distribution
  const bars = [
    { key: 'gibbed', label: 'Gibbed', count: s.gibbed, color: OUTCOME_COLORS.gibbed },
    { key: 'revived', label: 'Revived', count: s.revived, color: OUTCOME_COLORS.revived },
    { key: 'tapped_out', label: 'Tapped Out', count: s.tapped_out, color: OUTCOME_COLORS.tapped_out },
    { key: 'expired', label: 'Expired', count: s.expired, color: OUTCOME_COLORS.expired },
    { key: 'round_end', label: 'Round End', count: s.round_end, color: OUTCOME_COLORS.round_end },
  ].filter(b => b.count > 0);
  const maxCount = Math.max(...bars.map(b => b.count), 1);

  return (
    <div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Outcome Distribution */}
      <GlassPanel>
        <div className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1">
          Kill Outcomes
        </div>
        <div className="text-[10px] text-slate-500 mb-4">
          What happens after each kill — gibbed, revived by medic, or tapped out
        </div>
        <div className="grid grid-cols-3 sm:grid-cols-5 gap-3 mb-4">
          <div className="text-center">
            <div className="text-[10px] text-slate-500">Total Kills</div>
            <div className="text-lg font-bold text-white">{s.total_kills}</div>
          </div>
          <div className="text-center">
            <div className="text-[10px] text-slate-500">Gib Rate</div>
            <div className="text-lg font-bold text-red-400">{s.gib_rate}%</div>
          </div>
          <div className="text-center">
            <div className="text-[10px] text-slate-500">Revive Rate</div>
            <div className="text-lg font-bold text-emerald-400">{s.revive_rate}%</div>
          </div>
          <div className="text-center">
            <div className="text-[10px] text-slate-500">Avg Outcome</div>
            <div className="text-lg font-bold text-amber-400">{s.avg_delta_ms ? `${(s.avg_delta_ms / 1000).toFixed(1)}s` : '--'}</div>
          </div>
          <div className="text-center">
            <div className="text-[10px] text-slate-500">Avg Denied</div>
            <div className="text-lg font-bold text-purple-400">{s.avg_denied_ms ? `${(s.avg_denied_ms / 1000).toFixed(1)}s` : '--'}</div>
          </div>
        </div>
        <div className="space-y-2">
          {bars.map(b => (
            <div key={b.key}>
              <div className="flex justify-between text-[10px] mb-0.5">
                <span className="text-slate-300">{b.label}</span>
                <span className="text-slate-400">{b.count} ({s.total_kills > 0 ? ((b.count / s.total_kills) * 100).toFixed(1) : 0}%)</span>
              </div>
              <div className="h-2 rounded-full bg-slate-800 overflow-hidden">
                <div
                  className="h-full rounded-full transition-all"
                  style={{ width: `${(b.count / maxCount) * 100}%`, backgroundColor: b.color }}
                />
              </div>
            </div>
          ))}
        </div>
      </GlassPanel>

      {/* Kill Permanence Leaderboard */}
      <GlassPanel>
        <div className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1">
          Kill Permanence Rate (KPR)
        </div>
        <div className="text-[10px] text-slate-500 mb-4">
          Gibs / (Gibs + Revives) — who makes their kills stick
        </div>
        {playerStats?.kill_permanence_leaders && playerStats.kill_permanence_leaders.length > 0 ? (
          <div className="space-y-1.5">
            {playerStats.kill_permanence_leaders.slice(0, 10).map((p, i) => (
              <div key={p.guid} className="flex items-center gap-2 text-xs">
                <span className="w-4 text-right text-slate-600 font-mono">{i + 1}</span>
                <span className="flex-1 truncate text-slate-200">{stripColors(p.name)}</span>
                <span className="text-cyan-400 font-mono font-bold w-14 text-right">{(p.kpr * 100).toFixed(1)}%</span>
                <span className="text-slate-500 text-[10px] w-28 text-right">{p.gibs}G/{p.revives_against}R/{p.tapouts}T {p.avg_denied_ms ? `${(p.avg_denied_ms / 1000).toFixed(1)}s` : ''}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-xs text-slate-500">No kill outcome data yet.</div>
        )}
        {playerStats?.revive_rate_leaders && playerStats.revive_rate_leaders.length > 0 && (
          <>
            <div className="text-xs font-bold uppercase tracking-widest text-slate-400 mt-4 mb-1">
              Most Revived
            </div>
            <div className="text-[10px] text-slate-500 mb-2">
              Players who get revived most often — medic magnet indicator
            </div>
            <div className="space-y-1.5">
              {playerStats.revive_rate_leaders.slice(0, 5).map((p, i) => (
                <div key={p.guid} className="flex items-center gap-2 text-xs">
                  <span className="w-4 text-right text-slate-600 font-mono">{i + 1}</span>
                  <span className="flex-1 truncate text-slate-200">{stripColors(p.name)}</span>
                  <span className="text-emerald-400 font-mono font-bold w-14 text-right">{(p.revive_rate * 100).toFixed(1)}%</span>
                  <span className="text-slate-500 text-[10px] w-28 text-right">{p.times_revived}R/{p.times_killed}D {p.avg_wait_ms ? `${(p.avg_wait_ms / 1000).toFixed(1)}s wait` : ''}</span>
                </div>
              ))}
            </div>
          </>
        )}
      </GlassPanel>
    </div>
  );
}

// ── Hit Regions (v5.2) ──────────────────────────────────────────────────────

const REGION_NAMES = ['Head', 'Arms', 'Body', 'Legs'] as const;
const REGION_COLORS = ['#ef4444', '#60a5fa', '#22c55e', '#f59e0b']; // red, blue, green, amber

function HitRegionsPanel() {
  const { data: hitData, isLoading: hitLoading } = useProximityHitRegions();
  const { data: hsData, isLoading: hsLoading } = useProximityHeadshotRates(30);

  if (hitLoading && hsLoading) return <Skeleton variant="card" count={1} />;

  const players = hitData?.players ?? [];
  const hsLeaders = hsData?.leaders ?? [];

  if (players.length === 0 && hsLeaders.length === 0) return null;

  // Aggregate totals across all players for the distribution chart
  const totals = players.reduce(
    (acc, p) => ({ head: acc.head + p.head, arms: acc.arms + p.arms, body: acc.body + p.body, legs: acc.legs + p.legs }),
    { head: 0, arms: 0, body: 0, legs: 0 },
  );
  const totalHits = totals.head + totals.arms + totals.body + totals.legs;

  const regionBars = [
    { label: 'Head', count: totals.head, color: REGION_COLORS[0] },
    { label: 'Arms', count: totals.arms, color: REGION_COLORS[1] },
    { label: 'Body', count: totals.body, color: REGION_COLORS[2] },
    { label: 'Legs', count: totals.legs, color: REGION_COLORS[3] },
  ];
  const maxRegionCount = Math.max(...regionBars.map(b => b.count), 1);

  return (
    <div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Hit Region Distribution */}
      <GlassPanel>
        <div className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1">
          Hit Region Distribution
        </div>
        <div className="text-[10px] text-slate-500 mb-4">
          Where shots land — head, arms, body, or legs (last 30 days)
        </div>

        {/* Visual body diagram - simplified horizontal bars */}
        {totalHits > 0 && (
          <>
            <div className="flex items-end gap-1 h-28 mb-3 justify-center">
              {regionBars.map((b, i) => {
                const pct = totalHits > 0 ? (b.count / totalHits) * 100 : 0;
                return (
                  <div key={i} className="flex flex-col items-center gap-1 flex-1 max-w-16">
                    <span className="text-[10px] font-mono text-slate-300">{pct.toFixed(1)}%</span>
                    <div className="w-full rounded-t" style={{
                      height: `${Math.max((b.count / maxRegionCount) * 100, 4)}%`,
                      backgroundColor: b.color,
                      opacity: 0.85,
                    }} />
                    <span className="text-[10px] text-slate-400">{b.label}</span>
                  </div>
                );
              })}
            </div>
            <div className="text-center text-[10px] text-slate-500 mb-3">
              {totalHits.toLocaleString()} hits &middot; {players.reduce((a, p) => a + p.total_damage, 0).toLocaleString()} damage tracked
            </div>
          </>
        )}

        <div className="space-y-2">
          {regionBars.map(b => (
            <div key={b.label}>
              <div className="flex justify-between text-[10px] mb-0.5">
                <span className="text-slate-300">{b.label}</span>
                <span className="text-slate-400">{b.count.toLocaleString()} ({totalHits > 0 ? ((b.count / totalHits) * 100).toFixed(1) : 0}%)</span>
              </div>
              <div className="h-2 rounded-full bg-slate-800 overflow-hidden">
                <div
                  className="h-full rounded-full transition-all"
                  style={{ width: `${(b.count / maxRegionCount) * 100}%`, backgroundColor: b.color }}
                />
              </div>
            </div>
          ))}
        </div>
      </GlassPanel>

      {/* Headshot Rate Leaderboard */}
      <GlassPanel>
        <div className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1">
          Best Aimers — Headshot %
        </div>
        <div className="text-[10px] text-slate-500 mb-4">
          Highest headshot percentage (min 50 hits, last 30 days)
        </div>
        {hsLeaders.length > 0 ? (
          <div className="space-y-1.5">
            {hsLeaders.slice(0, 15).map((p, i) => (
              <div key={p.guid} className="flex items-center gap-2 text-xs">
                <span className="w-4 text-right text-slate-600 font-mono">{i + 1}</span>
                <span className="flex-1 truncate text-slate-200">{stripColors(p.name)}</span>
                <span className="text-red-400 font-mono font-bold w-14 text-right">{p.headshot_pct.toFixed(1)}%</span>
                <span className="text-slate-500 text-[10px] w-24 text-right">{p.head_hits}H / {p.total_hits} total</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-xs text-slate-500">No hit region data yet.</div>
        )}

        {/* Top players by total hits */}
        {players.length > 0 && (
          <>
            <div className="text-xs font-bold uppercase tracking-widest text-slate-400 mt-4 mb-1">
              Most Active Shooters
            </div>
            <div className="text-[10px] text-slate-500 mb-2">
              Players with the most total hits tracked
            </div>
            <div className="space-y-1.5">
              {[...players].sort((a, b) => b.total_hits - a.total_hits).slice(0, 5).map((p, i) => (
                <div key={p.guid} className="flex items-center gap-2 text-xs">
                  <span className="w-4 text-right text-slate-600 font-mono">{i + 1}</span>
                  <span className="flex-1 truncate text-slate-200">{stripColors(p.name)}</span>
                  <span className="text-cyan-400 font-mono font-bold w-14 text-right">{p.total_hits.toLocaleString()}</span>
                  <span className="text-slate-500 text-[10px] w-24 text-right">
                    H:{p.head} A:{p.arms} B:{p.body} L:{p.legs}
                  </span>
                </div>
              ))}
            </div>
          </>
        )}
      </GlassPanel>
    </div>
  );
}

// ── Movement Analytics (Phase A) ────────────────────────────────────────────

const STANCE_COLORS = { standing: '#60a5fa', crouching: '#f59e0b', prone: '#ef4444' };

function MovementStatsPanel() {
  const { data, isLoading } = useMovementStats(30);

  if (isLoading) return <Skeleton variant="card" count={1} />;

  const players = data?.players ?? [];
  if (players.length === 0) return null;

  // Aggregate for overview stats
  const totals = players.reduce(
    (acc, p) => ({
      distance: acc.distance + p.total_distance,
      alive: acc.alive + p.alive_sec,
      sprint: acc.sprint + p.sprint_sec,
      standing: acc.standing + p.standing_sec,
      crouching: acc.crouching + p.crouching_sec,
      prone: acc.prone + p.prone_sec,
    }),
    { distance: 0, alive: 0, sprint: 0, standing: 0, crouching: 0, prone: 0 },
  );
  const totalStance = totals.standing + totals.crouching + totals.prone;

  return (
    <div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Movement Overview */}
      <GlassPanel>
        <div className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1">
          Movement Analytics
        </div>
        <div className="text-[10px] text-slate-500 mb-4">
          Stance, speed, and distance from path samples (last 30 days)
        </div>

        {/* Stance distribution bar */}
        {totalStance > 0 && (
          <div className="mb-4">
            <div className="text-[10px] text-slate-500 mb-1">Stance Distribution</div>
            <div className="h-4 rounded-full overflow-hidden flex">
              <div style={{ width: `${(totals.standing / totalStance) * 100}%`, backgroundColor: STANCE_COLORS.standing }} title={`Standing ${((totals.standing / totalStance) * 100).toFixed(1)}%`} />
              <div style={{ width: `${(totals.crouching / totalStance) * 100}%`, backgroundColor: STANCE_COLORS.crouching }} title={`Crouching ${((totals.crouching / totalStance) * 100).toFixed(1)}%`} />
              <div style={{ width: `${(totals.prone / totalStance) * 100}%`, backgroundColor: STANCE_COLORS.prone }} title={`Prone ${((totals.prone / totalStance) * 100).toFixed(1)}%`} />
            </div>
            <div className="flex justify-between text-[10px] mt-1">
              <span className="text-blue-400">Standing {((totals.standing / totalStance) * 100).toFixed(0)}%</span>
              <span className="text-amber-400">Crouch {((totals.crouching / totalStance) * 100).toFixed(0)}%</span>
              <span className="text-red-400">Prone {((totals.prone / totalStance) * 100).toFixed(0)}%</span>
            </div>
          </div>
        )}

        <div className="grid grid-cols-3 gap-3 mb-3">
          <div className="text-center">
            <div className="text-[10px] text-slate-500">Total Distance</div>
            <div className="text-sm font-bold text-white">{(totals.distance / 1000).toFixed(0)}K u</div>
          </div>
          <div className="text-center">
            <div className="text-[10px] text-slate-500">Alive Time</div>
            <div className="text-sm font-bold text-white">{(totals.alive / 60).toFixed(0)}m</div>
          </div>
          <div className="text-center">
            <div className="text-[10px] text-slate-500">Sprint Time</div>
            <div className="text-sm font-bold text-cyan-400">{(totals.sprint / 60).toFixed(1)}m</div>
          </div>
        </div>

        {/* Top movers */}
        <div className="text-[10px] text-slate-500 mb-1 mt-2">Biggest Movers (total distance)</div>
        <div className="space-y-1.5">
          {[...players].sort((a, b) => b.total_distance - a.total_distance).slice(0, 8).map((p, i) => (
            <div key={p.guid} className="flex items-center gap-2 text-xs">
              <span className="w-4 text-right text-slate-600 font-mono">{i + 1}</span>
              <span className="flex-1 truncate text-slate-200">{stripColors(p.name)}</span>
              <span className="text-cyan-400 font-mono font-bold w-16 text-right">{(p.total_distance / 1000).toFixed(1)}K</span>
              <span className="text-slate-500 text-[10px] w-16 text-right">{p.avg_speed.toFixed(0)} u/s</span>
            </div>
          ))}
        </div>
      </GlassPanel>

      {/* Speed + Sprint leaderboard */}
      <GlassPanel>
        <div className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1">
          Speed & Sprint Leaders
        </div>
        <div className="text-[10px] text-slate-500 mb-4">
          Peak speed and sprint usage (last 30 days, min 3 lives)
        </div>

        {/* Fastest players */}
        <div className="text-[10px] text-slate-500 mb-1">Fastest Peak Speed</div>
        <div className="space-y-1.5 mb-4">
          {[...players].sort((a, b) => b.max_peak_speed - a.max_peak_speed).slice(0, 8).map((p, i) => (
            <div key={p.guid} className="flex items-center gap-2 text-xs">
              <span className="w-4 text-right text-slate-600 font-mono">{i + 1}</span>
              <span className="flex-1 truncate text-slate-200">{stripColors(p.name)}</span>
              <span className="text-orange-400 font-mono font-bold w-16 text-right">{p.max_peak_speed.toFixed(0)} u/s</span>
              <span className="text-slate-500 text-[10px] w-16 text-right">avg {p.avg_peak_speed.toFixed(0)}</span>
            </div>
          ))}
        </div>

        {/* Sprint leaders */}
        <div className="text-[10px] text-slate-500 mb-1">Most Sprint Time</div>
        <div className="space-y-1.5 mb-4">
          {[...players].sort((a, b) => b.avg_sprint_pct - a.avg_sprint_pct).slice(0, 8).map((p, i) => (
            <div key={p.guid} className="flex items-center gap-2 text-xs">
              <span className="w-4 text-right text-slate-600 font-mono">{i + 1}</span>
              <span className="flex-1 truncate text-slate-200">{stripColors(p.name)}</span>
              <span className="text-emerald-400 font-mono font-bold w-14 text-right">{p.avg_sprint_pct.toFixed(1)}%</span>
              <span className="text-slate-500 text-[10px] w-20 text-right">{p.sprint_sec.toFixed(0)}s total</span>
            </div>
          ))}
        </div>

        {/* Post-spawn aggression */}
        <div className="text-[10px] text-slate-500 mb-1">Post-Spawn Rush (3s distance)</div>
        <div className="space-y-1.5">
          {[...players].sort((a, b) => b.avg_post_spawn_dist - a.avg_post_spawn_dist).slice(0, 5).map((p, i) => (
            <div key={p.guid} className="flex items-center gap-2 text-xs">
              <span className="w-4 text-right text-slate-600 font-mono">{i + 1}</span>
              <span className="flex-1 truncate text-slate-200">{stripColors(p.name)}</span>
              <span className="text-purple-400 font-mono font-bold w-16 text-right">{p.avg_post_spawn_dist.toFixed(0)} u</span>
            </div>
          ))}
        </div>
      </GlassPanel>
    </div>
  );
}

// ── Danger Zones (v5.2) ─────────────────────────────────────────────────────

const CLASS_COLORS: Record<string, string> = {
  SOLDIER: '#ef4444', MEDIC: '#22c55e', ENGINEER: '#f59e0b', FIELDOPS: '#60a5fa', COVERTOPS: '#a855f7',
};

function DangerZonesPanel() {
  const [mapName, setMapName] = useState('');
  const [classFilter, setClassFilter] = useState<string | undefined>(undefined);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const { data, isLoading } = useDangerZones(mapName, { victimClass: classFilter, rangeDays: 30 });
  const zones = data?.zones ?? [];
  const gridSize = data?.grid_size ?? 512;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !mapName) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const W = canvas.width;
    const H = canvas.height;
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = '#0f172a';
    ctx.fillRect(0, 0, W, H);

    if (zones.length === 0) {
      ctx.fillStyle = '#64748b';
      ctx.font = '12px monospace';
      ctx.textAlign = 'center';
      ctx.fillText('No danger zone data for this map', W / 2, H / 2);
      return;
    }

    const maxDeaths = Math.max(...zones.map(z => z.deaths), 1);
    for (const zone of zones) {
      const nx = (zone.x / gridSize) * W;
      const ny = (zone.y / gridSize) * H;
      const intensity = zone.deaths / maxDeaths;
      const radius = 6 + intensity * 18;

      // Color by dominant class
      const classes = zone.classes;
      const dominant = Object.entries(classes).sort((a, b) => b[1] - a[1])[0];
      // eslint-disable-next-line security/detect-object-injection
      const baseColor = CLASS_COLORS[dominant[0]] ?? '#64748b';
      const alpha = 0.25 + intensity * 0.55;

      ctx.beginPath();
      ctx.arc(nx, ny, radius, 0, Math.PI * 2);
      // Convert hex to rgba
      const r = parseInt(baseColor.slice(1, 3), 16);
      const g = parseInt(baseColor.slice(3, 5), 16);
      const b = parseInt(baseColor.slice(5, 7), 16);
      ctx.fillStyle = `rgba(${r},${g},${b},${alpha})`;
      ctx.fill();

      // Death count label for large zones
      if (intensity > 0.3) {
        ctx.fillStyle = 'rgba(255,255,255,0.7)';
        ctx.font = '9px monospace';
        ctx.textAlign = 'center';
        ctx.fillText(String(zone.deaths), nx, ny + 3);
      }
    }
  }, [zones, mapName, gridSize]);

  const totalDeaths = zones.reduce((a, z) => a + z.deaths, 0);
  // Aggregate class breakdown across all zones
  const classBreakdown: Record<string, number> = {};
  for (const zone of zones) {
    for (const [cls, count] of Object.entries(zone.classes)) {
      // eslint-disable-next-line security/detect-object-injection
      classBreakdown[cls] = (classBreakdown[cls] ?? 0) + count;
    }
  }
  const classSorted = Object.entries(classBreakdown).sort((a, b) => b[1] - a[1]);

  return (
    <div className="mt-6">
      <GlassPanel>
        <div className="flex items-center justify-between mb-3">
          <div>
            <div className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1">
              Danger Zones
            </div>
            <div className="text-[10px] text-slate-500">
              Death hotspots colored by class — where do players die most? (last 30 days)
            </div>
          </div>
          <div className="flex gap-2 items-center">
            <input
              type="text"
              placeholder="Map name..."
              value={mapName}
              onChange={e => { setMapName(e.target.value); }}
              className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-xs text-slate-200 w-32 focus:outline-none focus:border-cyan-500"
            />
          </div>
        </div>

        {/* Class filter buttons */}
        <div className="flex gap-1 mb-3 flex-wrap">
          <button
            className={`px-2 py-0.5 rounded text-[10px] font-medium transition-colors ${!classFilter ? 'bg-slate-600 text-white' : 'bg-slate-800 text-slate-500 border border-slate-700'}`}
            onClick={() => { setClassFilter(undefined); }}
          >All</button>
          {Object.entries(CLASS_COLORS).map(([cls, color]) => (
            <button
              key={cls}
              className={`px-2 py-0.5 rounded text-[10px] font-medium transition-colors border ${classFilter === cls ? 'border-current' : 'border-slate-700 bg-slate-800'}`}
              style={{ color: classFilter === cls ? color : undefined }}
              onClick={() => { setClassFilter(classFilter === cls ? undefined : cls); }}
            >{cls}</button>
          ))}
        </div>

        {!mapName ? (
          <div className="flex items-center justify-center h-48 text-xs text-slate-500">
            Enter a map name to view danger zones
          </div>
        ) : isLoading ? (
          <Skeleton variant="card" count={1} />
        ) : (
          <div className="flex gap-4">
            <canvas ref={canvasRef} width={512} height={512} className="rounded-lg border border-slate-700/50 flex-shrink-0" />
            {/* Class breakdown sidebar */}
            <div className="flex-1 min-w-0">
              <div className="text-[10px] text-slate-500 mb-2">{totalDeaths} deaths in {zones.length} zones</div>
              {classSorted.length > 0 && (
                <div className="space-y-1.5">
                  {classSorted.map(([cls, count]) => (
                    <div key={cls} className="flex items-center gap-2 text-xs">
                      {/* eslint-disable-next-line security/detect-object-injection */}
                      <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: CLASS_COLORS[cls] ?? '#64748b' }} />
                      <span className="text-slate-300 w-20">{cls}</span>
                      <div className="flex-1 h-2 rounded-full bg-slate-800 overflow-hidden">
                        <div className="h-full rounded-full" style={{
                          width: `${totalDeaths > 0 ? (count / totalDeaths) * 100 : 0}%`,
                          // eslint-disable-next-line security/detect-object-injection
                          backgroundColor: CLASS_COLORS[cls] ?? '#64748b',
                        }} />
                      </div>
                      <span className="text-slate-400 font-mono text-[10px] w-12 text-right">
                        {totalDeaths > 0 ? ((count / totalDeaths) * 100).toFixed(0) : 0}%
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </GlassPanel>
    </div>
  );
}

// ── Combat Heatmap (v5.2) ───────────────────────────────────────────────────

function CombatHeatmapPanel() {
  const [mapName, setMapName] = useState('');
  const [perspective, setPerspective] = useState<'kills' | 'deaths'>('kills');
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const { data: heatmapData, isLoading: heatLoading } = useCombatHeatmap(mapName, { perspective, rangeDays: 30 });
  const { data: killLinesData } = useKillLines(mapName, { rangeDays: 30, limit: 200 });

  // Don't render until we have a map name set — will be populated by user or from data
  const hotzones = heatmapData?.hotzones ?? [];
  const killLines = killLinesData?.lines ?? [];
  const gridSize = heatmapData?.grid_size ?? 512;

  // Draw heatmap + kill lines on canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !mapName) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const W = canvas.width;
    const H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    // Background
    ctx.fillStyle = '#0f172a';
    ctx.fillRect(0, 0, W, H);

    if (hotzones.length === 0 && killLines.length === 0) {
      ctx.fillStyle = '#64748b';
      ctx.font = '12px monospace';
      ctx.textAlign = 'center';
      ctx.fillText('No combat data for this map yet', W / 2, H / 2);
      return;
    }

    // Heatmap circles
    const maxCount = Math.max(...hotzones.map(h => h.count), 1);
    for (const hz of hotzones) {
      const nx = (hz.x / gridSize) * W;
      const ny = (hz.y / gridSize) * H;
      const intensity = hz.count / maxCount;
      const radius = 4 + intensity * 16;
      const alpha = 0.2 + intensity * 0.6;

      const color = perspective === 'kills'
        ? `rgba(239, 68, 68, ${alpha})`   // red for kills
        : `rgba(96, 165, 250, ${alpha})`;  // blue for deaths

      ctx.beginPath();
      ctx.arc(nx, ny, radius, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
    }

    // Kill lines (arrows from killer to victim)
    for (const line of killLines) {
      const ax = (line.ax / gridSize) * W;
      const ay = (line.ay / gridSize) * H;
      const vx = (line.vx / gridSize) * W;
      const vy = (line.vy / gridSize) * H;
      const teamColor = line.attacker_team === 'AXIS'
        ? 'rgba(239, 68, 68, 0.15)'
        : 'rgba(96, 165, 250, 0.15)';

      ctx.beginPath();
      ctx.moveTo(ax, ay);
      ctx.lineTo(vx, vy);
      ctx.strokeStyle = teamColor;
      ctx.lineWidth = 1;
      ctx.stroke();
    }
  }, [hotzones, killLines, mapName, perspective, gridSize]);

  return (
    <div className="mt-6">
      <GlassPanel>
        <div className="flex items-center justify-between mb-3">
          <div>
            <div className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1">
              Combat Heatmap
            </div>
            <div className="text-[10px] text-slate-500">
              Kill/death hotspots on the map (last 30 days)
            </div>
          </div>
          <div className="flex gap-2 items-center">
            <input
              type="text"
              placeholder="Map name..."
              value={mapName}
              onChange={e => { setMapName(e.target.value); }}
              className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-xs text-slate-200 w-32 focus:outline-none focus:border-cyan-500"
            />
            <div className="flex gap-1">
              <button
                className={`px-2 py-1 rounded text-[10px] font-medium transition-colors ${perspective === 'kills' ? 'bg-red-500/20 text-red-400 border border-red-500/40' : 'bg-slate-800 text-slate-500 border border-slate-700'}`}
                onClick={() => { setPerspective('kills'); }}
              >
                Kills
              </button>
              <button
                className={`px-2 py-1 rounded text-[10px] font-medium transition-colors ${perspective === 'deaths' ? 'bg-blue-500/20 text-blue-400 border border-blue-500/40' : 'bg-slate-800 text-slate-500 border border-slate-700'}`}
                onClick={() => { setPerspective('deaths'); }}
              >
                Deaths
              </button>
            </div>
          </div>
        </div>

        {!mapName ? (
          <div className="flex items-center justify-center h-64 text-xs text-slate-500">
            Enter a map name to view combat positions
          </div>
        ) : heatLoading ? (
          <Skeleton variant="card" count={1} />
        ) : (
          <div className="flex justify-center">
            <canvas
              ref={canvasRef}
              width={512}
              height={512}
              className="rounded-lg border border-slate-700/50"
            />
          </div>
        )}

        {killLines.length > 0 && (
          <div className="mt-2 text-[10px] text-slate-500 text-center">
            {hotzones.length} hotspots · {killLines.length} kill lines · {perspective === 'kills' ? 'Red' : 'Blue'} = {perspective}
          </div>
        )}
      </GlassPanel>
    </div>
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
                    <span className="text-white font-medium text-sm truncate">{stripColors(p.name)}</span>
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
          {activeTab === 'crossfire' ? `${stripColors(row.name)} + ${stripColors(row.partner_name ?? '?')}` : stripColors(row.name)}
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

      {/* Proximity Composite Scores — the main rating */}
      <ProxScoresPanel />

      {/* Kill Outcomes — global data, always visible */}
      <KillOutcomesPanel />

      {/* Hit Regions — global data, always visible */}
      <HitRegionsPanel />

      {/* Movement Analytics */}
      <MovementStatsPanel />

      {/* Danger Zones — class-specific death hotspots */}
      <DangerZonesPanel />

      {/* Combat Heatmap — global data, always visible */}
      <CombatHeatmapPanel />

      {/* Session Combat Scores */}
      <SessionScorePanel sessionDate={sessionDate} />

      {/* Proximity Leaderboards */}
      <LeaderboardTabs />
    </div>
  );
}
