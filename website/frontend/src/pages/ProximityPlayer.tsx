import { useQuery } from '@tanstack/react-query';
import { PageHeader } from '../components/PageHeader';
import { GlassPanel } from '../components/GlassPanel';
import { GlassCard } from '../components/GlassCard';
import { Skeleton } from '../components/Skeleton';
import { navigateTo } from '../lib/navigation';
import { useProximityKillOutcomePlayerStats, useProximityHitRegions, useProximityHitRegionsByWeapon, useMovementStats, useProxScores } from '../api/hooks';

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
function stripColors(name: string): string { return name.replace(/\^[0-9a-zA-Z]/g, ''); }

const REGION_NAMES = ['Head', 'Arms', 'Body', 'Legs'] as const;
const REGION_COLORS = ['#ef4444', '#60a5fa', '#22c55e', '#f59e0b'];
const WEAPON_NAMES: Record<number, string> = {
  3: 'Knife', 8: 'MP40', 9: 'Thompson', 10: 'Sten',
  15: 'Panzerfaust', 19: 'FG42', 23: 'Garand', 28: 'K43',
  32: 'Colt', 33: 'Luger', 35: 'Grenade', 36: 'Grenade',
  44: 'Landmine', 47: 'Mortar', 50: 'Dynamite', 57: 'MG42',
};

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

      {/* Proximity Composite Score */}
      <PlayerProxScoreSection guid={guid} />

      {/* v5.2 sections */}
      <PlayerKillOutcomesSection guid={guid} />
      <PlayerHitRegionsSection guid={guid} />
      <PlayerMovementSection guid={guid} />
    </div>
  );
}

// ── Proximity Composite Score per player ────────────────────────────────────

const SCORE_COLORS: Record<string, string> = {
  prox_combat: '#ef4444', prox_team: '#60a5fa', prox_gamesense: '#f59e0b', prox_overall: '#22c55e',
};

function PlayerProxScoreSection({ guid }: { guid: string }) {
  const { data } = useProxScores(30, guid, 1);
  const player = data?.players[0];
  if (!player) return null;

  return (
    <GlassPanel className="mt-6">
      <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-4">
        Proximity Score
      </h3>
      {/* Score tiles */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-4">
        <div className="text-center">
          <div className="text-[10px] text-slate-500">Combat</div>
          <div className="text-2xl font-black" style={{ color: SCORE_COLORS.prox_combat }}>{player.prox_combat.toFixed(1)}</div>
        </div>
        <div className="text-center">
          <div className="text-[10px] text-slate-500">Team</div>
          <div className="text-2xl font-black" style={{ color: SCORE_COLORS.prox_team }}>{player.prox_team.toFixed(1)}</div>
        </div>
        <div className="text-center">
          <div className="text-[10px] text-slate-500">Game Sense</div>
          <div className="text-2xl font-black" style={{ color: SCORE_COLORS.prox_gamesense }}>{player.prox_gamesense.toFixed(1)}</div>
        </div>
        <div className="text-center">
          <div className="text-[10px] text-slate-500">Overall</div>
          <div className="text-3xl font-black" style={{ color: SCORE_COLORS.prox_overall }}>{player.prox_overall.toFixed(1)}</div>
        </div>
      </div>

      {/* Radar values */}
      <div className="flex gap-3 justify-center mb-4">
        {player.prox_radar.map((axis, i) => (
          <div key={i} className="text-center px-2">
            <div className="text-[10px] text-slate-500">{axis.label}</div>
            <div className="text-sm font-bold text-white">{axis.value.toFixed(0)}</div>
          </div>
        ))}
      </div>

      {/* Per-metric breakdown */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {Object.entries(player.breakdown).map(([catKey, metrics]) => (
          <div key={catKey}>
            {/* eslint-disable-next-line security/detect-object-injection */}
            <div className="text-[10px] font-bold uppercase mb-1.5" style={{ color: SCORE_COLORS[catKey] ?? '#94a3b8' }}>
              {catKey.replace('prox_', '')}
            </div>
            {Object.entries(metrics).map(([mk, m]) => (
              <div key={mk} className="flex items-center gap-1 text-[10px] mb-0.5">
                <span className="text-slate-500 w-24 truncate">{m.label}</span>
                <div className="flex-1 h-1.5 rounded-full bg-slate-700 overflow-hidden">
                  <div className="h-full rounded-full bg-cyan-500/60" style={{ width: `${m.percentile * 100}%` }} />
                </div>
                <span className="text-slate-400 font-mono w-8 text-right">{(m.percentile * 100).toFixed(0)}</span>
              </div>
            ))}
          </div>
        ))}
      </div>
      <div className="text-[10px] text-slate-600 mt-2 text-center">Rank #{player.rank} &middot; {player.engagements} engagements &middot; Last 30 days</div>
    </GlassPanel>
  );
}

// ── Kill Outcomes per player ────────────────────────────────────────────────

function PlayerKillOutcomesSection({ guid }: { guid: string }) {
  const { data: stats } = useProximityKillOutcomePlayerStats(90, guid);

  const kprEntry = stats?.kill_permanence_leaders.find(p => p.guid === guid);
  const revEntry = stats?.revive_rate_leaders.find(p => p.guid === guid);

  if (!kprEntry && !revEntry) return null;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
      {kprEntry && (
        <GlassPanel>
          <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-4">
            Kill Permanence (as Killer)
          </h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <StatTile label="KPR" value={`${(kprEntry.kpr * 100).toFixed(1)}%`} color="text-cyan-400" />
            <StatTile label="Gibs" value={fmtNum(kprEntry.gibs)} color="text-red-400" />
            <StatTile label="Revived Against" value={fmtNum(kprEntry.revives_against)} color="text-emerald-400" />
            <StatTile label="Tapouts" value={fmtNum(kprEntry.tapouts)} color="text-amber-400" />
          </div>
          {kprEntry.avg_denied_ms > 0 && (
            <div className="mt-3 text-[10px] text-slate-500">
              Avg time denied to victims: <span className="text-purple-400 font-mono">{(kprEntry.avg_denied_ms / 1000).toFixed(1)}s</span>
            </div>
          )}
        </GlassPanel>
      )}
      {revEntry && (
        <GlassPanel>
          <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-4">
            Survivability (as Victim)
          </h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <StatTile label="Revive Rate" value={`${(revEntry.revive_rate * 100).toFixed(1)}%`} color="text-emerald-400" />
            <StatTile label="Times Killed" value={fmtNum(revEntry.times_killed)} color="text-rose-400" />
            <StatTile label="Times Revived" value={fmtNum(revEntry.times_revived)} color="text-emerald-400" />
            <StatTile label="Times Gibbed" value={fmtNum(revEntry.times_gibbed)} color="text-red-400" />
          </div>
          {revEntry.avg_wait_ms > 0 && (
            <div className="mt-3 text-[10px] text-slate-500">
              Avg wait for revive: <span className="text-amber-400 font-mono">{(revEntry.avg_wait_ms / 1000).toFixed(1)}s</span>
            </div>
          )}
        </GlassPanel>
      )}
    </div>
  );
}

// ── Hit Regions per player ──────────────────────────────────────────────────

function PlayerHitRegionsSection({ guid }: { guid: string }) {
  const { data: hitData } = useProximityHitRegions({ range_days: 90 });
  const { data: weaponData } = useProximityHitRegionsByWeapon(guid, 90);

  const player = hitData?.players.find(p => p.guid === guid);
  const weapons = weaponData?.weapons ?? [];

  if (!player && weapons.length === 0) return null;

  const regionCounts = player ? [player.head, player.arms, player.body, player.legs] : [];
  const total = regionCounts.reduce((a, b) => a + b, 0);
  const maxCount = Math.max(...regionCounts, 1);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
      {player && total > 0 && (
        <GlassPanel>
          <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-4">
            Hit Region Profile
          </h3>
          <div className="flex items-end gap-2 h-24 mb-3 justify-center">
            {REGION_NAMES.map((name, i) => {
              // eslint-disable-next-line security/detect-object-injection
              const count = regionCounts[i];
              const pct = total > 0 ? (count / total) * 100 : 0;
              return (
                <div key={name} className="flex flex-col items-center gap-1 flex-1 max-w-20">
                  <span className="text-[10px] font-mono text-slate-300">{pct.toFixed(1)}%</span>
                  <div className="w-full rounded-t" style={{
                    height: `${Math.max((count / maxCount) * 100, 4)}%`,
                    // eslint-disable-next-line security/detect-object-injection
                    backgroundColor: REGION_COLORS[i],
                    opacity: 0.85,
                  }} />
                  <span className="text-[10px] text-slate-400">{name}</span>
                  <span className="text-[10px] text-slate-600">{count}</span>
                </div>
              );
            })}
          </div>
          <div className="text-center text-[10px] text-slate-500">
            {total.toLocaleString()} hits &middot; {player.total_damage.toLocaleString()} damage &middot; {player.head_pct.toFixed(1)}% headshot
          </div>
        </GlassPanel>
      )}
      {weapons.length > 0 && (
        <GlassPanel>
          <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-4">
            Per-Weapon Accuracy
          </h3>
          <div className="space-y-1.5">
            {weapons.sort((a, b) => b.total - a.total).slice(0, 8).map(w => {
              const wTotal = w.total || 1;
              return (
                <div key={w.weapon_id} className="flex items-center gap-2 text-xs">
                  <span className="w-20 truncate text-slate-300">{WEAPON_NAMES[w.weapon_id] ?? `W#${w.weapon_id}`}</span>
                  <div className="flex-1 flex h-3 rounded-full overflow-hidden bg-slate-800">
                    <div style={{ width: `${(w.head / wTotal) * 100}%`, backgroundColor: REGION_COLORS[0] }} />
                    <div style={{ width: `${(w.arms / wTotal) * 100}%`, backgroundColor: REGION_COLORS[1] }} />
                    <div style={{ width: `${(w.body / wTotal) * 100}%`, backgroundColor: REGION_COLORS[2] }} />
                    <div style={{ width: `${(w.legs / wTotal) * 100}%`, backgroundColor: REGION_COLORS[3] }} />
                  </div>
                  <span className="text-red-400 font-mono w-12 text-right text-[10px]">{w.headshot_pct.toFixed(0)}% HS</span>
                  <span className="text-slate-500 text-[10px] w-10 text-right">{w.total}</span>
                </div>
              );
            })}
          </div>
          <div className="flex gap-3 mt-2 text-[10px] text-slate-500 justify-center">
            <span><span className="inline-block w-2 h-2 rounded-full mr-1" style={{ backgroundColor: REGION_COLORS[0] }} />Head</span>
            <span><span className="inline-block w-2 h-2 rounded-full mr-1" style={{ backgroundColor: REGION_COLORS[1] }} />Arms</span>
            <span><span className="inline-block w-2 h-2 rounded-full mr-1" style={{ backgroundColor: REGION_COLORS[2] }} />Body</span>
            <span><span className="inline-block w-2 h-2 rounded-full mr-1" style={{ backgroundColor: REGION_COLORS[3] }} />Legs</span>
          </div>
        </GlassPanel>
      )}
    </div>
  );
}

// ── Movement per player ─────────────────────────────────────────────────────

function PlayerMovementSection({ guid }: { guid: string }) {
  const { data } = useMovementStats(90, guid);

  const player = data?.players.find(p => p.guid === guid);
  if (!player) return null;

  const totalStance = player.standing_sec + player.crouching_sec + player.prone_sec;

  return (
    <GlassPanel className="mt-6">
      <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-4">
        Movement Profile
      </h3>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-4 mb-4">
        <StatTile label="Avg Speed" value={`${player.avg_speed.toFixed(0)} u/s`} color="text-cyan-400" />
        <StatTile label="Peak Speed" value={`${player.max_peak_speed.toFixed(0)} u/s`} color="text-orange-400" />
        <StatTile label="Total Distance" value={`${(player.total_distance / 1000).toFixed(1)}K u`} color="text-white" />
        <StatTile label="Sprint %" value={`${player.avg_sprint_pct.toFixed(1)}%`} color="text-emerald-400" />
        <StatTile label="Post-Spawn Rush" value={`${player.avg_post_spawn_dist.toFixed(0)} u`} color="text-purple-400" />
        <StatTile label="Tracks" value={player.tracks} color="text-slate-400" />
      </div>
      {totalStance > 0 && (
        <div>
          <div className="text-[10px] text-slate-500 mb-1">Stance Distribution</div>
          <div className="h-4 rounded-full overflow-hidden flex">
            <div style={{ width: `${(player.standing_sec / totalStance) * 100}%`, backgroundColor: '#60a5fa' }} title={`Standing ${player.standing_pct.toFixed(1)}%`} />
            <div style={{ width: `${(player.crouching_sec / totalStance) * 100}%`, backgroundColor: '#f59e0b' }} title={`Crouching ${player.crouching_pct.toFixed(1)}%`} />
            <div style={{ width: `${(player.prone_sec / totalStance) * 100}%`, backgroundColor: '#ef4444' }} title={`Prone ${player.prone_pct.toFixed(1)}%`} />
          </div>
          <div className="flex justify-between text-[10px] mt-1">
            <span className="text-blue-400">Standing {player.standing_pct.toFixed(0)}% ({player.standing_sec.toFixed(0)}s)</span>
            <span className="text-amber-400">Crouch {player.crouching_pct.toFixed(0)}% ({player.crouching_sec.toFixed(0)}s)</span>
            <span className="text-red-400">Prone {player.prone_pct.toFixed(0)}% ({player.prone_sec.toFixed(0)}s)</span>
          </div>
        </div>
      )}
    </GlassPanel>
  );
}
