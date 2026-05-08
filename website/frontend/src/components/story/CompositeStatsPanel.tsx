import { useState } from 'react';
import type { CompositeStatsResponse, CompositeStatsPlayer } from '../../api/types';

// Composite advanced stats panel — Team Impact Rating, Clutch Index,
// Kill Permanence Index, Spawn Denial Score, Combat Presence.
//
// Pairs with InvisibleValuePanel: that one shows the proximity-driven
// "invisible value" axes (gravity/space/enabler/lurker), this one shows
// the PCS-driven "performance fingerprint" — the numerical companion to
// the storytelling narrative ("stories WITH numbers").

type Metric = 'tir' | 'ci' | 'kpi' | 'sds' | 'cp';

interface MetricDef {
  key: Metric;
  label: string;
  short: string;
  color: string;
  activeBg: string;
  description: string;
  // Returns the value rendered as a 0-100 score with formatting tweaks
  format: (p: CompositeStatsPlayer) => string;
}

const METRICS: MetricDef[] = [
  {
    key: 'tir',
    label: 'TEAM IMPACT',
    short: 'TIR',
    color: 'text-emerald-400',
    activeBg: 'bg-emerald-500/20 border-emerald-400/40',
    description: 'Crossfire + trade coordination',
    format: (p) => p.tir.toFixed(0),
  },
  {
    key: 'ci',
    label: 'CLUTCH',
    short: 'CI',
    color: 'text-amber-400',
    activeBg: 'bg-amber-500/20 border-amber-400/40',
    description: 'Low-HP / outnumbered kill rate',
    format: (p) => p.ci.toFixed(0),
  },
  {
    key: 'kpi',
    label: 'PERMANENCE',
    short: 'KPI',
    color: 'text-rose-400',
    activeBg: 'bg-rose-500/20 border-rose-400/40',
    description: 'Gib rate (kills that stay)',
    format: (p) => p.kpi.toFixed(0),
  },
  {
    key: 'sds',
    label: 'SPAWN DENIAL',
    short: 'SDS',
    color: 'text-blue-400',
    activeBg: 'bg-blue-500/20 border-blue-400/40',
    description: 'Spawn timing + denied playtime',
    format: (p) => p.sds.toFixed(0),
  },
  {
    key: 'cp',
    label: 'PRESENCE',
    short: 'CP',
    color: 'text-purple-400',
    activeBg: 'bg-purple-500/20 border-purple-400/40',
    description: 'Survival + focus escape',
    format: (p) => p.cp.toFixed(0),
  },
];

function StatCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-white/[0.03] px-2 py-1.5">
      <div className="text-[10px] text-slate-500 uppercase tracking-wider">{label}</div>
      <div className="text-sm font-bold tabular-nums text-white">{value}</div>
    </div>
  );
}

interface Props {
  composite: CompositeStatsResponse | undefined;
}

export function CompositeStatsPanel({ composite }: Props) {
  const [active, setActive] = useState<Metric>('tir');

  const players = composite?.players ?? [];
  if (players.length === 0) return null;

  const activeMetric = METRICS.find((m) => m.key === active)!;

  // Sort by the active metric (descending). Fall back to kills for stable
  // tie-breaking so the order doesn't jitter on toggle.
  // Use an explicit accessor switch instead of `a[active]` dynamic indexing —
  // the dynamic form is type-safe under TS but trips "object injection" rules
  // in some static analyzers because `active` is tab-state user-controlled.
  const sortedPlayers = [...players].sort((a, b) => {
    const av = metricValue(a, active);
    const bv = metricValue(b, active);
    if (bv !== av) return bv - av;
    return b.kills - a.kills;
  });

  return (
    <div>
      <div className="flex items-center gap-3 mb-3">
        <h3 className="text-xs text-slate-500 uppercase tracking-wider font-bold">Performance Fingerprint</h3>
        <span className={`rounded-full border px-2.5 py-0.5 text-[10px] font-bold ${activeMetric.activeBg} ${activeMetric.color}`}>
          {activeMetric.short}
        </span>
        <span className="text-[10px] text-slate-500 italic">{activeMetric.description}</span>
      </div>

      <div className="flex flex-wrap gap-1.5 mb-4">
        {METRICS.map((m) => (
          <button
            key={m.key}
            onClick={() => setActive(m.key)}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wider transition-all
              ${active === m.key
                ? `${m.activeBg} ${m.color} border`
                : 'text-slate-500 hover:text-slate-300 bg-white/[0.02] border border-transparent hover:border-white/8'
              }`}
            title={m.description}
          >
            {m.short}
          </button>
        ))}
      </div>

      <div className="glass-card rounded-[24px] p-5 border border-white/8">
        <div className="space-y-2">
          {sortedPlayers.map((p, i) => {
            const score = activeMetric.format(p);
            const detailCells = renderDetailCells(active, p);
            return (
              <div
                key={p.player_guid}
                className="flex items-center gap-3 rounded-xl bg-white/[0.02] px-3 py-2.5 hover:bg-white/[0.04] transition-colors"
                style={{ animation: `fadeUp 0.3s ease-out ${i * 0.04}s both` }}
              >
                <span className={`${activeMetric.color} font-bold text-lg tabular-nums w-12`}>{score}</span>
                <span className="text-sm text-white font-medium flex-1 truncate">{p.player_name}</span>
                <div className="flex gap-2">{detailCells}</div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function metricValue(p: CompositeStatsPlayer, m: Metric): number {
  switch (m) {
    case 'tir': return p.tir;
    case 'ci':  return p.ci;
    case 'kpi': return p.kpi;
    case 'sds': return p.sds;
    case 'cp':  return p.cp;
    default: {
      const _exhaustive: never = m;
      void _exhaustive;
      return 0;
    }
  }
}

function renderDetailCells(metric: Metric, p: CompositeStatsPlayer) {
  // Defensive `|| {}` because some upstream rows may have a missing `details`
  // bag if the underlying SQL CTEs don't have the matching scope (e.g. a player
  // appears in PCS but has no proximity_kill_outcome rows). Default to 0/-
  // rather than crashing on `undefined.crossfire_kills`.
  const d = p.details ?? {
    crossfire_kills: 0,
    trade_kills: 0,
    clutch_kills: 0,
    gibbed_count: 0,
    total_outcomes: 0,
    avg_spawn_score: 0,
    focus_escapes: 0,
    times_focused: 0,
  };
  switch (metric) {
    case 'tir':
      return (
        <>
          <StatCell label="CROSSFIRE" value={String(d.crossfire_kills)} />
          <StatCell label="TRADES" value={String(d.trade_kills)} />
          <StatCell label="KILLS" value={String(p.kills)} />
        </>
      );
    case 'ci':
      return (
        <>
          <StatCell label="CLUTCH" value={String(d.clutch_kills)} />
          <StatCell label="KILLS" value={String(p.kills)} />
        </>
      );
    case 'kpi':
      return (
        <>
          <StatCell label="GIBBED" value={String(d.gibbed_count)} />
          <StatCell label="OUTCOMES" value={String(d.total_outcomes)} />
        </>
      );
    case 'sds':
      return (
        <>
          <StatCell label="AVG SCORE" value={d.avg_spawn_score.toFixed(2)} />
          <StatCell label="KILLS" value={String(p.kills)} />
        </>
      );
    case 'cp':
      return (
        <>
          <StatCell label="ESCAPES" value={String(d.focus_escapes)} />
          <StatCell label="FOCUSED" value={String(d.times_focused)} />
        </>
      );
    default: {
      // Exhaustiveness check — TypeScript will narrow `metric` to `never`
      // here; if a new tab key is added without a case, this assignment
      // produces a compile error and a runtime fallback.
      const _exhaustive: never = metric;
      void _exhaustive;
      return null;
    }
  }
}
