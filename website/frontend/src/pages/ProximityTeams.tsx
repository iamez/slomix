import { useQuery } from '@tanstack/react-query';
import { PageHeader } from '../components/PageHeader';
import { GlassPanel } from '../components/GlassPanel';
import { GlassCard } from '../components/GlassCard';
import { Skeleton } from '../components/Skeleton';

const API = '/api';

// ── Types ────────────────────────────────────────────────────────────────────

interface TeamCohesion {
  avg_dispersion: number | null;
  avg_max_spread: number | null;
  avg_stragglers: number | null;
  samples: number | null;
}

interface TeamPush {
  push_count: number | null;
  avg_quality: number | null;
  avg_alignment: number | null;
}

interface CrossfireTarget {
  target_team: string;
  total_opportunities: number | null;
  executed: number | null;
  execution_rate: number | null;
}

interface TeamComparisonData {
  cohesion?: { axis: TeamCohesion; allies: TeamCohesion };
  pushes?: { axis: TeamPush; allies: TeamPush };
  crossfire?: CrossfireTarget[];
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function fmtNum(v: number | null | undefined) { return v != null ? v.toLocaleString() : '--'; }
function fmtDec(v: number | null | undefined, d = 1) { return v != null ? v.toFixed(d) : '--'; }
function fmtPct(v: number | null | undefined) { return v != null ? `${v.toFixed(1)}%` : '--'; }

function ComparisonBar({ axisVal, alliesVal, label }: { axisVal: number | null; alliesVal: number | null; label: string }) {
  const a = axisVal ?? 0;
  const b = alliesVal ?? 0;
  const max = Math.max(a, b, 1);
  const aPct = Math.round((a / max) * 100);
  const bPct = Math.round((b / max) * 100);

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-[10px] text-slate-500 uppercase tracking-wider">
        <span>{label}</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-xs text-red-400 font-mono w-14 text-right">{fmtDec(axisVal)}</span>
        <div className="flex-1 flex items-center gap-1 h-4">
          <div className="flex-1 flex justify-end">
            <div
              className="h-full rounded-l bg-red-500/70 transition-all duration-500"
              style={{ width: `${aPct}%` }}
            />
          </div>
          <div className="w-px h-full bg-slate-600" />
          <div className="flex-1">
            <div
              className="h-full rounded-r bg-blue-500/70 transition-all duration-500"
              style={{ width: `${bPct}%` }}
            />
          </div>
        </div>
        <span className="text-xs text-blue-400 font-mono w-14">{fmtDec(alliesVal)}</span>
      </div>
    </div>
  );
}

// ── Main Page ────────────────────────────────────────────────────────────────

export default function ProximityTeams({ params }: { params?: Record<string, string> }) {
  const roundId = params?.roundId ?? '';

  const { data, isLoading, error } = useQuery<TeamComparisonData>({
    queryKey: ['proximity-team-comparison', roundId],
    queryFn: () => fetch(`${API}/proximity/round/${roundId}/team-comparison`).then((r) => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    }),
    enabled: !!roundId,
    staleTime: 60_000,
  });

  if (!roundId) {
    return (
      <>
        <PageHeader title="Team Comparison" subtitle="No round specified" />
        <GlassPanel>
          <div className="text-sm text-slate-400">Please select a round from the proximity analytics page.</div>
        </GlassPanel>
      </>
    );
  }

  if (isLoading) return <Skeleton variant="card" count={4} />;

  if (error) {
    return (
      <>
        <PageHeader title={`Team Comparison - Round #${roundId}`} />
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          Failed to load team comparison data. {(error as Error).message}
        </div>
      </>
    );
  }

  const cohesion = data?.cohesion;
  const pushes = data?.pushes;
  const crossfire = data?.crossfire ?? [];

  return (
    <>
      {/* Header */}
      <PageHeader title={`Team Comparison - Round #${roundId}`} subtitle="Side-by-side team performance analysis">
        <a
          href="#/proximity"
          className="px-3 py-1.5 rounded-lg text-xs font-bold border border-white/10 text-slate-300 hover:border-cyan-500/40 transition"
        >
          Back to Proximity
        </a>
      </PageHeader>

      {/* Team Legend */}
      <div className="flex items-center gap-6 mb-6 text-xs">
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-red-500" />
          <span className="text-slate-300 font-medium">Axis</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-blue-500" />
          <span className="text-slate-300 font-medium">Allies</span>
        </div>
      </div>

      {/* Cohesion Comparison */}
      {cohesion && (
        <GlassPanel className="mb-6">
          <div className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-4">Cohesion Comparison</div>
          <div className="space-y-4">
            <ComparisonBar label="Avg Dispersion" axisVal={cohesion.axis.avg_dispersion} alliesVal={cohesion.allies.avg_dispersion} />
            <ComparisonBar label="Avg Max Spread" axisVal={cohesion.axis.avg_max_spread} alliesVal={cohesion.allies.avg_max_spread} />
            <ComparisonBar label="Avg Stragglers" axisVal={cohesion.axis.avg_stragglers} alliesVal={cohesion.allies.avg_stragglers} />
            <ComparisonBar label="Samples" axisVal={cohesion.axis.samples} alliesVal={cohesion.allies.samples} />
          </div>
        </GlassPanel>
      )}

      {/* Push Quality */}
      {pushes && (
        <GlassPanel className="mb-6">
          <div className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-4">Push Quality</div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-5">
            {(['push_count', 'avg_quality', 'avg_alignment'] as const).map((key) => {
              const labels: Record<string, string> = { push_count: 'Push Count', avg_quality: 'Avg Quality', avg_alignment: 'Avg Alignment' };
              return (
                <GlassCard key={key} className="!cursor-default">
                  <div className="text-[10px] text-slate-500 uppercase mb-2">{labels[key]}</div>
                  <div className="flex items-end justify-between">
                    <div className="text-center flex-1">
                      <div className="text-lg font-bold text-red-400">{fmtDec(pushes.axis[key])}</div>
                      <div className="text-[10px] text-slate-500">Axis</div>
                    </div>
                    <div className="text-slate-600 text-xs px-2">vs</div>
                    <div className="text-center flex-1">
                      <div className="text-lg font-bold text-blue-400">{fmtDec(pushes.allies[key])}</div>
                      <div className="text-[10px] text-slate-500">Allies</div>
                    </div>
                  </div>
                </GlassCard>
              );
            })}
          </div>
          <div className="space-y-4">
            <ComparisonBar label="Push Count" axisVal={pushes.axis.push_count} alliesVal={pushes.allies.push_count} />
            <ComparisonBar label="Quality" axisVal={pushes.axis.avg_quality} alliesVal={pushes.allies.avg_quality} />
            <ComparisonBar label="Alignment" axisVal={pushes.axis.avg_alignment} alliesVal={pushes.allies.avg_alignment} />
          </div>
        </GlassPanel>
      )}

      {/* Crossfire Execution */}
      {crossfire.length > 0 && (
        <GlassPanel className="mb-6">
          <div className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-4">Crossfire Execution</div>
          <div className="space-y-5">
            {crossfire.map((cf) => {
              const rate = cf.execution_rate ?? 0;
              const isAxis = cf.target_team.toUpperCase() === 'AXIS';
              const barColor = isAxis ? 'bg-red-500/70' : 'bg-blue-500/70';
              const textColor = isAxis ? 'text-red-400' : 'text-blue-400';

              return (
                <div key={cf.target_team}>
                  <div className="flex items-center justify-between mb-2">
                    <span className={`text-sm font-medium ${textColor}`}>
                      vs {cf.target_team}
                    </span>
                    <span className="text-xs text-slate-400">
                      {fmtNum(cf.executed)} / {fmtNum(cf.total_opportunities)} opportunities
                    </span>
                  </div>
                  <div className="w-full h-5 rounded-full bg-slate-800/80 overflow-hidden">
                    <div
                      className={`h-full rounded-full ${barColor} transition-all duration-700 flex items-center justify-end pr-2`}
                      style={{ width: `${Math.max(rate, 2)}%` }}
                    >
                      {rate >= 15 && (
                        <span className="text-[10px] font-bold text-white">{fmtPct(cf.execution_rate)}</span>
                      )}
                    </div>
                  </div>
                  {rate < 15 && (
                    <div className="text-right mt-0.5">
                      <span className="text-[10px] font-bold text-slate-400">{fmtPct(cf.execution_rate)}</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </GlassPanel>
      )}

      {/* Empty state */}
      {!cohesion && !pushes && crossfire.length === 0 && (
        <GlassPanel>
          <div className="text-center py-8">
            <div className="text-slate-500 text-sm">No team comparison data available for this round.</div>
            <div className="text-slate-600 text-xs mt-1">This round may not have proximity teamplay data recorded.</div>
          </div>
        </GlassPanel>
      )}
    </>
  );
}
