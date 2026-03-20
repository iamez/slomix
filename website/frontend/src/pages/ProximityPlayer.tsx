import { useQuery } from '@tanstack/react-query';
import { PageHeader } from '../components/PageHeader';
import { GlassPanel } from '../components/GlassPanel';
import { GlassCard } from '../components/GlassCard';
import { Skeleton } from '../components/Skeleton';
import { navigateTo } from '../lib/navigation';

const API = '/api';

// ── Types ────────────────────────────────────────────────────────────────────

interface ProfileData {
  player_name: string;
  guid: string;
  total_engagements: number;
  escapes: number;
  deaths: number;
  escape_rate: number;
  avg_duration_ms: number;
  total_kills: number;
  crossfire_count: number;
  avg_speed: number;
  sprint_pct: number;
  avg_distance_per_life: number;
  avg_return_fire_ms: number;
  avg_dodge_ms: number;
  avg_support_reaction_ms: number;
  spawn_avg_score: number;
  timed_kills: number;
  avg_denial_ms: number;
  trades_made: number;
}

interface RadarData {
  axes: { label: string; value: number }[];
  composite: number;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function fmtNum(v: number | null | undefined) {
  return v != null ? v.toLocaleString() : '--';
}
function fmtMs(v: number | null | undefined) {
  return v != null ? `${Math.round(v)}ms` : '--';
}
function fmtPct(v: number | null | undefined) {
  return v != null ? `${v.toFixed(1)}%` : '--';
}

// ── Radar Chart ──────────────────────────────────────────────────────────────

const RADAR_SIZE = 300;
const CX = RADAR_SIZE / 2;
const CY = RADAR_SIZE / 2;
const R = 120;

function polarToXY(angle: number, radius: number): [number, number] {
  // Start from top (-90deg), go clockwise
  const rad = ((angle - 90) * Math.PI) / 180;
  return [CX + radius * Math.cos(rad), CY + radius * Math.sin(rad)];
}

function pentagonPoints(radius: number): string {
  return Array.from({ length: 5 }, (_, i) => {
    const [x, y] = polarToXY((360 / 5) * i, radius);
    return `${x},${y}`;
  }).join(' ');
}

function RadarChart({ axes, composite }: { axes: { label: string; value: number }[]; composite: number }) {
  if (axes.length !== 5) return null;

  const dataPoints = axes.map((a, i) => {
    const frac = Math.min(a.value, 100) / 100;
    return polarToXY((360 / 5) * i, R * frac);
  });
  const dataPath = dataPoints.map(([x, y]) => `${x},${y}`).join(' ');

  // Label positions pushed slightly further out
  const labelPositions = axes.map((_, i) => polarToXY((360 / 5) * i, R + 28));

  return (
    <svg viewBox={`0 0 ${RADAR_SIZE} ${RADAR_SIZE}`} className="w-full max-w-[320px] mx-auto">
      {/* Grid pentagons */}
      {[0.33, 0.66, 1].map((scale) => (
        <polygon
          key={scale}
          points={pentagonPoints(R * scale)}
          fill="none"
          stroke="rgba(148,163,184,0.15)"
          strokeWidth="1"
        />
      ))}

      {/* Axis lines */}
      {axes.map((_, i) => {
        const [x, y] = polarToXY((360 / 5) * i, R);
        return <line key={i} x1={CX} y1={CY} x2={x} y2={y} stroke="rgba(148,163,184,0.1)" strokeWidth="1" />;
      })}

      {/* Data shape */}
      <polygon
        points={dataPath}
        fill="rgba(56,189,248,0.2)"
        stroke="rgba(56,189,248,0.8)"
        strokeWidth="2"
      />

      {/* Data points */}
      {dataPoints.map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r="4" fill="rgb(56,189,248)" stroke="rgb(15,23,42)" strokeWidth="2" />
      ))}

      {/* Axis labels */}
      {axes.map((a, i) => {
        const [lx, ly] = labelPositions[i];
        return (
          <g key={i}>
            <text
              x={lx}
              y={ly - 6}
              textAnchor="middle"
              dominantBaseline="middle"
              className="fill-slate-400 text-[10px] font-bold"
            >
              {a.label}
            </text>
            <text
              x={lx}
              y={ly + 7}
              textAnchor="middle"
              dominantBaseline="middle"
              className="fill-cyan-400 text-[10px] font-mono"
            >
              {Math.round(a.value)}
            </text>
          </g>
        );
      })}

      {/* Composite score in center */}
      <text x={CX} y={CY - 6} textAnchor="middle" dominantBaseline="middle" className="fill-white text-2xl font-black">
        {Math.round(composite)}
      </text>
      <text x={CX} y={CY + 12} textAnchor="middle" dominantBaseline="middle" className="fill-slate-500 text-[9px] font-bold uppercase">
        Composite
      </text>
    </svg>
  );
}

// ── Stat Tile ────────────────────────────────────────────────────────────────

function StatTile({ label, value, color = 'text-white' }: { label: string; value: string | number; color?: string }) {
  return (
    <div>
      <div className="text-[10px] text-slate-500 uppercase font-bold">{label}</div>
      <div className={`text-lg font-bold ${color}`}>{value}</div>
    </div>
  );
}

// ── Gauge ────────────────────────────────────────────────────────────────────

function ScoreGauge({ score, label }: { score: number; label: string }) {
  const pct = Math.min(Math.max(score, 0), 100);
  const color = pct >= 70 ? 'bg-emerald-500' : pct >= 40 ? 'bg-amber-500' : 'bg-rose-500';
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] text-slate-500 uppercase font-bold">{label}</span>
        <span className="text-sm font-bold text-white">{score.toFixed(1)}</span>
      </div>
      <div className="h-2 rounded-full bg-slate-700 overflow-hidden">
        <div className={`h-full rounded-full ${color} transition-all`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

// ── Main Page ────────────────────────────────────────────────────────────────

export default function ProximityPlayer({ params }: { params?: Record<string, string> }) {
  const guid = params?.guid ?? '';

  const { data: profile, isLoading: profileLoading, isError: profileError } = useQuery<ProfileData>({
    queryKey: ['proximity-player-profile', guid],
    queryFn: async () => {
      const r = await fetch(`${API}/proximity/player/${encodeURIComponent(guid)}/profile`);
      return r.json();
    },
    enabled: !!guid,
    staleTime: 60_000,
  });

  const { data: radar } = useQuery<RadarData>({
    queryKey: ['proximity-player-radar', guid],
    queryFn: async () => {
      const r = await fetch(`${API}/proximity/player/${encodeURIComponent(guid)}/radar`);
      return r.json();
    },
    enabled: !!guid,
    staleTime: 60_000,
  });

  if (!guid) {
    return (
      <div className="mt-6 text-center text-slate-400 py-12">
        No player GUID provided. Navigate here from the Proximity page.
      </div>
    );
  }

  if (profileLoading) {
    return (
      <div className="mt-6">
        <PageHeader title="Loading..." subtitle={guid} />
        <Skeleton variant="card" count={6} />
      </div>
    );
  }

  if (profileError || !profile) {
    return (
      <div className="mt-6">
        <PageHeader title="Proximity Profile" subtitle={guid} />
        <div className="text-center text-red-400 py-12">
          Player not found or failed to load proximity data.
        </div>
      </div>
    );
  }

  return (
    <div className="mt-6">
      {/* Back link */}
      <button
        onClick={() => navigateTo('#/proximity')}
        className="text-xs text-cyan-400 hover:text-cyan-300 transition mb-4 inline-block"
      >
        &larr; Back to Proximity Analytics
      </button>

      {/* Header */}
      <PageHeader title={profile.player_name} subtitle={`GUID: ${profile.guid}`} />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Radar Chart */}
        <GlassPanel className="lg:col-span-1 flex flex-col items-center justify-center">
          <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-4 self-start">
            Player Radar
          </h3>
          {radar?.axes?.length === 5 ? (
            <RadarChart axes={radar.axes} composite={radar.composite} />
          ) : (
            <div className="text-sm text-slate-500 py-8">Radar data not available</div>
          )}
        </GlassPanel>

        {/* Stats Overview */}
        <div className="lg:col-span-2 space-y-4">
          {/* Engagement Stats */}
          <GlassPanel>
            <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-4">
              Engagement Stats
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-4">
              <StatTile label="Engagements" value={fmtNum(profile.total_engagements)} color="text-cyan-400" />
              <StatTile label="Escapes" value={fmtNum(profile.escapes)} color="text-emerald-400" />
              <StatTile label="Deaths" value={fmtNum(profile.deaths)} color="text-rose-400" />
              <StatTile label="Escape Rate" value={fmtPct(profile.escape_rate)} color="text-emerald-400" />
              <StatTile label="Avg Duration" value={fmtMs(profile.avg_duration_ms)} color="text-amber-400" />
            </div>
          </GlassPanel>

          {/* Kill Stats */}
          <GlassPanel>
            <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-4">
              Kill Stats
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
              <StatTile label="Total Kills" value={fmtNum(profile.total_kills)} color="text-rose-400" />
              <StatTile label="Crossfire Kills" value={fmtNum(profile.crossfire_count)} color="text-purple-400" />
            </div>
          </GlassPanel>

          {/* Movement */}
          <GlassPanel>
            <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-4">
              Movement
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
              <StatTile label="Avg Speed" value={profile.avg_speed != null ? `${Math.round(profile.avg_speed)}u/s` : '--'} color="text-cyan-400" />
              <StatTile label="Sprint %" value={fmtPct(profile.sprint_pct)} color="text-blue-400" />
              <StatTile label="Dist/Life" value={profile.avg_distance_per_life != null ? `${Math.round(profile.avg_distance_per_life)}u` : '--'} color="text-indigo-400" />
            </div>
          </GlassPanel>
        </div>
      </div>

      {/* Reaction Times */}
      <GlassPanel className="mt-6">
        <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-4">
          Reaction Times
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
          <GlassCard>
            <div className="text-[10px] text-slate-500 uppercase font-bold mb-1">Return Fire</div>
            <div className="text-2xl font-bold text-amber-400">{fmtMs(profile.avg_return_fire_ms)}</div>
          </GlassCard>
          <GlassCard>
            <div className="text-[10px] text-slate-500 uppercase font-bold mb-1">Dodge</div>
            <div className="text-2xl font-bold text-emerald-400">{fmtMs(profile.avg_dodge_ms)}</div>
          </GlassCard>
          <GlassCard>
            <div className="text-[10px] text-slate-500 uppercase font-bold mb-1">Support Reaction</div>
            <div className="text-2xl font-bold text-blue-400">{fmtMs(profile.avg_support_reaction_ms)}</div>
          </GlassCard>
        </div>
      </GlassPanel>

      {/* Spawn Timing & Trade Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
        <GlassPanel>
          <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-4">
            Spawn Timing
          </h3>
          <ScoreGauge score={profile.spawn_avg_score ?? 0} label="Avg Score" />
          <div className="grid grid-cols-2 gap-4 mt-4">
            <StatTile label="Timed Kills" value={fmtNum(profile.timed_kills)} color="text-emerald-400" />
            <StatTile label="Avg Denial" value={fmtMs(profile.avg_denial_ms)} color="text-amber-400" />
          </div>
        </GlassPanel>

        <GlassPanel>
          <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-4">
            Trade Stats
          </h3>
          <div className="flex items-center justify-center py-4">
            <div className="text-center">
              <div className="text-4xl font-black text-cyan-400">{fmtNum(profile.trades_made)}</div>
              <div className="text-[10px] text-slate-500 uppercase font-bold mt-1">Trades Made</div>
            </div>
          </div>
        </GlassPanel>
      </div>
    </div>
  );
}
