import { useState, useMemo } from 'react';
import { useRecentRounds, useRoundViz } from '../api/hooks';
import type { RoundVizData, VizPlayer } from '../api/types';
import { ChartCanvas } from '../components/Chart';
import { PageHeader } from '../components/PageHeader';
import { Skeleton } from '../components/Skeleton';
import { EmptyState } from '../components/EmptyState';
import { DataTable, type Column } from '../components/DataTable';
import { cn } from '../lib/cn';
import { formatNumber } from '../lib/format';
import { navigateToPlayer } from '../lib/navigation';
import { mapLevelshot } from '../lib/game-assets';

const CHART_COLORS = [
  'rgba(59, 130, 246, 0.7)',
  'rgba(244, 63, 94, 0.7)',
  'rgba(16, 185, 129, 0.7)',
  'rgba(245, 158, 11, 0.7)',
  'rgba(168, 85, 247, 0.7)',
];

function roundLabel(n: number): string {
  if (n === 0) return 'R0 (summary)';
  return `R${n}`;
}

// --- Match Summary Panel ---
function MatchSummary({ data }: { data: RoundVizData }) {
  const h = data.highlights;
  const winnerLabel = data.winner_team === 1 ? 'Axis' : data.winner_team === 2 ? 'Allies' : 'Tied';
  const winnerColor = data.winner_team === 1 ? 'text-rose-400' : data.winner_team === 2 ? 'text-blue-400' : 'text-slate-400';
  const durationStr = data.duration_seconds ? `${Math.round(data.duration_seconds / 60)}m` : '--';

  return (
    <div className="glass-card rounded-xl p-5">
      <h3 className="text-sm font-bold text-white mb-4">Match Summary</h3>
      <div className="grid grid-cols-2 gap-3 text-sm">
        <div className="glass-panel rounded-lg p-3 flex items-center gap-2">
          <img src={mapLevelshot(data.map_name || '')} alt="" className="w-8 h-8 rounded object-cover bg-slate-700" onError={(e) => { e.currentTarget.style.display = 'none'; }} />
          <div>
            <div className="text-[11px] text-slate-500">Map</div>
            <div className="font-bold text-white">{data.map_name || 'Unknown'}</div>
          </div>
        </div>
        <Stat label="Round" value={data.round_label || roundLabel(data.round_number)} />
        <Stat label="Date" value={data.round_date || '--'} />
        <Stat label="Duration" value={durationStr} />
        <Stat label="Players" value={String(data.player_count)} />
        <div className="glass-panel rounded-lg p-3">
          <div className="text-[11px] text-slate-500">Winner</div>
          <div className={cn('font-bold', winnerColor)}>{winnerLabel}</div>
        </div>
      </div>
      {(h.mvp || h.most_kills || h.most_damage) && (
        <div className="mt-4 grid grid-cols-3 gap-2">
          {h.mvp && (
            <MiniHighlight label="MVP (DPM)" name={h.mvp.name} value={Math.round(h.mvp.dpm)} color="text-yellow-500" />
          )}
          {h.most_kills && (
            <MiniHighlight label="Most Kills" name={h.most_kills.name} value={h.most_kills.kills} color="text-rose-400" />
          )}
          {h.most_damage && (
            <MiniHighlight label="Most Damage" name={h.most_damage.name} value={formatNumber(h.most_damage.damage_given)} color="text-orange-400" />
          )}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="glass-panel rounded-lg p-3">
      <div className="text-[11px] text-slate-500">{label}</div>
      <div className="text-white font-bold">{value}</div>
    </div>
  );
}

function MiniHighlight({ label, name, value, color }: { label: string; name: string; value: string | number; color: string }) {
  return (
    <div className="glass-panel rounded-lg p-2 text-center">
      <div className={cn('text-[10px]', color)}>{label}</div>
      <div className="text-xs text-white font-bold truncate">{name}</div>
      <div className="text-[10px] text-slate-400">{value}</div>
    </div>
  );
}

// --- Combat Radar ---
function CombatRadar({ players }: { players: VizPlayer[] }) {
  const top5 = useMemo(() =>
    [...players].sort((a, b) => b.dpm - a.dpm).slice(0, 5),
    [players],
  );

  const chartData = useMemo(() => {
    if (top5.length === 0) return null;
    const maxK = Math.max(...top5.map((p) => p.kills), 1);
    const maxD = Math.max(...top5.map((p) => p.deaths), 1);
    const maxDpm = Math.max(...top5.map((p) => p.dpm), 1);
    const maxDmg = Math.max(...top5.map((p) => p.damage_given), 1);
    const maxG = Math.max(...top5.map((p) => p.gibs), 1);

    return {
      labels: ['Kills', 'Deaths(inv)', 'DPM', 'Damage', 'Efficiency', 'Gibs'],
      datasets: top5.map((p, i) => ({
        label: p.name,
        data: [
          Math.round((p.kills / maxK) * 100),
          Math.round((1 - p.deaths / maxD) * 100),
          Math.round((p.dpm / maxDpm) * 100),
          Math.round((p.damage_given / maxDmg) * 100),
          Math.round(p.efficiency),
          Math.round((p.gibs / maxG) * 100),
        ],
        backgroundColor: CHART_COLORS[i % CHART_COLORS.length],
        borderColor: CHART_COLORS[i % CHART_COLORS.length],
        borderWidth: 2,
      })),
    };
  }, [top5]);

  if (!chartData) return null;

  return (
    <div className="glass-card rounded-xl p-5">
      <h3 className="text-sm font-bold text-white mb-4">Combat Overview</h3>
      <ChartCanvas
        type="radar"
        data={chartData}
        height={320}
        options={{
          plugins: { legend: { position: 'bottom', labels: { color: '#94a3b8', font: { size: 10 } } } },
          scales: {
            r: {
              angleLines: { color: 'rgba(148,163,184,0.2)' },
              grid: { color: 'rgba(148,163,184,0.2)' },
              pointLabels: { color: '#94a3b8', font: { size: 10 } },
              ticks: { display: false },
              min: 0,
              max: 100,
            },
          },
        }}
      />
    </div>
  );
}

// --- Top Fraggers Bar ---
function TopFraggers({ players }: { players: VizPlayer[] }) {
  const sorted = useMemo(() => [...players].sort((a, b) => b.kills - a.kills), [players]);

  const chartData = useMemo(() => ({
    labels: sorted.map((p) => p.name),
    datasets: [
      {
        label: 'Kills',
        data: sorted.map((p) => p.kills),
        backgroundColor: 'rgba(59, 130, 246, 0.7)',
      },
      {
        label: 'Deaths',
        data: sorted.map((p) => p.deaths),
        backgroundColor: 'rgba(244, 63, 94, 0.5)',
      },
    ],
  }), [sorted]);

  return (
    <div className="glass-card rounded-xl p-5">
      <h3 className="text-sm font-bold text-white mb-4">Top Fraggers</h3>
      <ChartCanvas
        type="bar"
        data={chartData}
        height={Math.max(200, players.length * 32)}
        options={{
          indexAxis: 'y',
          plugins: { legend: { labels: { color: '#94a3b8', font: { size: 10 } } } },
          scales: {
            x: { grid: { color: 'rgba(148,163,184,0.1)' }, ticks: { color: '#94a3b8' } },
            y: { grid: { display: false }, ticks: { color: '#e2e8f0', font: { size: 11 } } },
          },
        }}
      />
    </div>
  );
}

// --- Support Performance ---
function SupportPerformance({ players }: { players: VizPlayer[] }) {
  const sorted = useMemo(() =>
    [...players].sort((a, b) => b.revives_given - a.revives_given),
    [players],
  );

  const chartData = useMemo(() => ({
    labels: sorted.map((p) => p.name),
    datasets: [
      {
        label: 'Revives',
        data: sorted.map((p) => p.revives_given),
        backgroundColor: 'rgba(16, 185, 129, 0.7)',
      },
      {
        label: 'Gibs',
        data: sorted.map((p) => p.gibs),
        backgroundColor: 'rgba(168, 85, 247, 0.5)',
      },
      {
        label: 'Self Kills',
        data: sorted.map((p) => p.self_kills),
        backgroundColor: 'rgba(245, 158, 11, 0.5)',
      },
    ],
  }), [sorted]);

  return (
    <div className="glass-card rounded-xl p-5">
      <h3 className="text-sm font-bold text-white mb-4">Support Performance</h3>
      <ChartCanvas
        type="bar"
        data={chartData}
        height={Math.max(200, players.length * 36)}
        options={{
          indexAxis: 'y',
          plugins: { legend: { labels: { color: '#94a3b8', font: { size: 10 } } } },
          scales: {
            x: { stacked: true, grid: { color: 'rgba(148,163,184,0.1)' }, ticks: { color: '#94a3b8' } },
            y: { stacked: true, grid: { display: false }, ticks: { color: '#e2e8f0', font: { size: 11 } } },
          },
        }}
      />
    </div>
  );
}

// --- Time Distribution ---
function TimeDistribution({ players }: { players: VizPlayer[] }) {
  const sorted = useMemo(() =>
    [...players].sort((a, b) => b.time_played_seconds - a.time_played_seconds),
    [players],
  );

  const chartData = useMemo(() => ({
    labels: sorted.map((p) => p.name),
    datasets: [
      {
        label: 'Alive (s)',
        data: sorted.map((p) => Math.max(0, p.time_played_seconds - p.time_dead_seconds)),
        backgroundColor: 'rgba(34, 197, 94, 0.7)',
      },
      {
        label: 'Dead (s)',
        data: sorted.map((p) => p.time_dead_seconds),
        backgroundColor: 'rgba(100, 116, 139, 0.5)',
      },
    ],
  }), [sorted]);

  return (
    <div className="glass-card rounded-xl p-5">
      <h3 className="text-sm font-bold text-white mb-4">Time Distribution</h3>
      <ChartCanvas
        type="bar"
        data={chartData}
        height={Math.max(200, players.length * 32)}
        options={{
          indexAxis: 'y',
          plugins: { legend: { labels: { color: '#94a3b8', font: { size: 10 } } } },
          scales: {
            x: { stacked: true, grid: { color: 'rgba(148,163,184,0.1)' }, ticks: { color: '#94a3b8' } },
            y: { stacked: true, grid: { display: false }, ticks: { color: '#e2e8f0', font: { size: 11 } } },
          },
        }}
      />
    </div>
  );
}

// --- Damage Breakdown Table ---
const dmgColumns: Column<VizPlayer>[] = [
  {
    key: 'name',
    label: 'Player',
    render: (row) => (
      <button onClick={() => navigateToPlayer(row.name)} className="text-blue-400 hover:text-blue-300 font-semibold text-left">
        {row.name}
      </button>
    ),
  },
  { key: 'damage_given', label: 'Dmg Given', sortable: true, sortValue: (r) => r.damage_given, className: 'font-mono text-white', render: (r) => formatNumber(r.damage_given) },
  { key: 'damage_received', label: 'Dmg Recv', sortable: true, sortValue: (r) => r.damage_received, className: 'font-mono text-slate-400', render: (r) => formatNumber(r.damage_received) },
  { key: 'team_damage_given', label: 'Team Dmg', sortable: true, sortValue: (r) => r.team_damage_given, className: 'font-mono text-amber-400', render: (r) => formatNumber(r.team_damage_given) },
  { key: 'dpm', label: 'DPM', sortable: true, sortValue: (r) => r.dpm, className: 'font-mono text-cyan-400', render: (r) => r.dpm.toFixed(1) },
  { key: 'efficiency', label: 'Eff%', sortable: true, sortValue: (r) => r.efficiency, className: 'font-mono text-emerald-400', render: (r) => `${r.efficiency.toFixed(0)}%` },
];

function DamageBreakdown({ players }: { players: VizPlayer[] }) {
  return (
    <div className="glass-card rounded-xl p-5">
      <h3 className="text-sm font-bold text-white mb-4">Damage Breakdown</h3>
      <div className="overflow-x-auto">
        <DataTable
          columns={dmgColumns}
          data={players}
          keyFn={(r) => r.guid}
          defaultSort={{ key: 'damage_given', dir: 'desc' }}
        />
      </div>
    </div>
  );
}

// --- Main Page ---
export default function RetroViz() {
  const { data: rounds, isLoading: roundsLoading } = useRecentRounds(50);
  const [selectedRoundId, setSelectedRoundId] = useState<number | null>(null);

  // Auto-select first round
  const activeRoundId = selectedRoundId ?? (rounds?.[0]?.id ?? null);
  const { data: vizData, isLoading: vizLoading } = useRoundViz(activeRoundId);

  if (roundsLoading) {
    return (
      <div className="mt-6">
        <PageHeader title="Round Visualizer" subtitle="Interactive round-by-round combat analytics" />
        <Skeleton variant="card" count={4} />
      </div>
    );
  }

  const selectableRounds = (rounds ?? []).filter((r) => r.round_number > 0);

  if (selectableRounds.length === 0) {
    return (
      <div className="mt-6">
        <PageHeader title="Round Visualizer" subtitle="Interactive round-by-round combat analytics" />
        <EmptyState message="No round data found. Play some rounds first!" />
      </div>
    );
  }

  return (
    <div className="mt-6">
      <PageHeader title="Round Visualizer" subtitle="Interactive round-by-round combat analytics">
        <select
          value={activeRoundId ?? ''}
          onChange={(e) => setSelectedRoundId(Number(e.target.value))}
          className="bg-slate-800 border border-white/10 text-slate-200 rounded-lg px-3 py-2 text-sm
                     focus:outline-none focus:border-cyan-500/50 min-w-[320px]"
        >
          {selectableRounds.map((r) => {
            const dateStr = r.round_date
              ? new Date(r.round_date + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
              : '';
            return (
              <option key={r.id} value={r.id}>
                {r.map_name || 'Unknown'} {r.round_label || roundLabel(r.round_number)} — {dateStr} ({r.player_count} players)
              </option>
            );
          })}
        </select>
      </PageHeader>

      {vizLoading ? (
        <Skeleton variant="card" count={6} className="grid-cols-2" />
      ) : !vizData || vizData.players.length === 0 ? (
        <EmptyState message="No player data for this round." />
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <MatchSummary data={vizData} />
            <CombatRadar players={vizData.players} />
          </div>
          <TopFraggers players={vizData.players} />
          <DamageBreakdown players={vizData.players} />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <SupportPerformance players={vizData.players} />
            <TimeDistribution players={vizData.players} />
          </div>
        </div>
      )}
    </div>
  );
}
