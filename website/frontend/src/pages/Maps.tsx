import { useState } from 'react';
import { Map, Users, Clock, Skull, Crosshair } from 'lucide-react';
import { useMapStats } from '../api/hooks';
import type { MapStats } from '../api/types';
import { DataTable, type Column } from '../components/DataTable';
import { PageHeader } from '../components/PageHeader';
import { Skeleton } from '../components/Skeleton';
import { GlassCard } from '../components/GlassCard';
import { cn } from '../lib/cn';
import { formatNumber } from '../lib/format';
import { mapLevelshot } from '../lib/game-assets';

function formatDuration(seconds: number): string {
  if (!seconds) return '-';
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

function mapLabel(name: string): string {
  return name.replace(/^maps[\\/]/, '').replace(/\.(bsp|pk3|arena)$/i, '').replace(/_/g, ' ');
}

function WinRateBar({ allies, axis }: { allies: number; axis: number }) {
  return (
    <div className="flex items-center gap-2 min-w-[120px]">
      <span className="text-xs text-blue-400 font-mono w-10 text-right">{allies}%</span>
      <div className="flex-1 h-2 rounded-full bg-slate-700 overflow-hidden flex">
        <div className="bg-blue-500 h-full" style={{ width: `${allies}%` }} />
        <div className="bg-rose-500 h-full" style={{ width: `${axis}%` }} />
      </div>
      <span className="text-xs text-rose-400 font-mono w-10">{axis}%</span>
    </div>
  );
}

const columns: Column<MapStats>[] = [
  {
    key: 'name',
    label: 'Map',
    render: (row) => (
      <div className="flex items-center gap-3">
        <img
          src={mapLevelshot(row.name)}
          alt={mapLabel(row.name)}
          className="w-8 h-8 rounded-lg object-cover bg-slate-800"
          onError={(e) => { e.currentTarget.style.display = 'none'; }}
        />
        <span className="font-semibold text-white">{mapLabel(row.name)}</span>
      </div>
    ),
  },
  {
    key: 'matches_played',
    label: 'Matches',
    sortable: true,
    sortValue: (row) => row.matches_played,
    className: 'font-mono text-brand-cyan',
  },
  {
    key: 'win_rate',
    label: 'Win Rate (A/X)',
    render: (row) => <WinRateBar allies={row.allies_win_rate} axis={row.axis_win_rate} />,
  },
  {
    key: 'avg_duration',
    label: 'Avg Duration',
    sortable: true,
    sortValue: (row) => row.avg_duration,
    className: 'font-mono text-slate-300',
    render: (row) => formatDuration(row.avg_duration),
  },
  {
    key: 'unique_players',
    label: 'Players',
    sortable: true,
    sortValue: (row) => row.unique_players,
    className: 'text-slate-400',
  },
  {
    key: 'avg_dpm',
    label: 'Avg DPM',
    sortable: true,
    sortValue: (row) => row.avg_dpm,
    className: 'font-mono text-slate-300',
    render: (row) => row.avg_dpm.toFixed(1),
  },
  {
    key: 'total_kills',
    label: 'Total Kills',
    sortable: true,
    sortValue: (row) => row.total_kills,
    className: 'text-slate-400',
    render: (row) => formatNumber(row.total_kills),
  },
  {
    key: 'last_played',
    label: 'Last Played',
    sortable: true,
    className: 'text-slate-500 text-xs',
  },
];

export default function MapsPage() {
  const { data: maps, isLoading, isError } = useMapStats();
  const [view, setView] = useState<'table' | 'cards'>('table');

  if (isLoading) {
    return (
      <div className="page-shell">
        <PageHeader title="Maps" subtitle="Historical map context once the main session and player questions are already answered." eyebrow="More" />
        <Skeleton variant="table" count={8} />
      </div>
    );
  }

  if (isError || !maps) {
    return (
      <div className="page-shell">
        <PageHeader title="Maps" subtitle="Map statistics and analytics" eyebrow="More" />
        <div className="text-center text-red-400 py-12">Failed to load map data.</div>
      </div>
    );
  }

  const totalMatches = maps.reduce((s, m) => s + m.matches_played, 0);
  const totalPlayers = new Set(maps.map((m) => m.unique_players)).size;

  return (
    <div className="page-shell">
      <PageHeader title="Maps" subtitle={`${maps.length} maps tracked across the archive.`} eyebrow="More">
        <div className="flex gap-1 bg-slate-800 rounded-lg p-0.5">
          <button
            onClick={() => setView('table')}
            className={cn('px-3 py-1.5 rounded-md text-xs font-bold transition',
              view === 'table' ? 'bg-blue-500/20 text-blue-400' : 'text-slate-400 hover:text-white')}
          >
            Table
          </button>
          <button
            onClick={() => setView('cards')}
            className={cn('px-3 py-1.5 rounded-md text-xs font-bold transition',
              view === 'cards' ? 'bg-blue-500/20 text-blue-400' : 'text-slate-400 hover:text-white')}
          >
            Cards
          </button>
        </div>
      </PageHeader>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div className="glass-card rounded-xl p-4">
          <div className="text-xs text-slate-500 uppercase font-bold">Maps</div>
          <div className="text-2xl font-black text-white mt-1">{maps.length}</div>
        </div>
        <div className="glass-card rounded-xl p-4">
          <div className="text-xs text-slate-500 uppercase font-bold">Total Matches</div>
          <div className="text-2xl font-black text-brand-cyan mt-1">{formatNumber(totalMatches)}</div>
        </div>
        <div className="glass-card rounded-xl p-4">
          <div className="text-xs text-slate-500 uppercase font-bold">Most Played</div>
          <div className="text-sm font-black text-brand-purple mt-1 truncate">{mapLabel(maps[0]?.name ?? '-')}</div>
          <div className="text-[11px] text-slate-500">{maps[0]?.matches_played ?? 0} matches</div>
        </div>
        <div className="glass-card rounded-xl p-4">
          <div className="text-xs text-slate-500 uppercase font-bold">Unique Players</div>
          <div className="text-2xl font-black text-brand-emerald mt-1">{totalPlayers}</div>
        </div>
      </div>

      {view === 'table' ? (
        <DataTable
          columns={columns}
          data={maps}
          keyFn={(row) => row.name}
          defaultSort={{ key: 'matches_played', dir: 'desc' }}
          stickyHeader
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {maps.map((m) => (
            <GlassCard key={m.name} className="relative overflow-hidden">
              <div className="relative -mx-5 -mt-5 mb-4 h-28 overflow-hidden rounded-t-xl bg-slate-800">
                <img
                  src={mapLevelshot(m.name)}
                  alt={mapLabel(m.name)}
                  className="w-full h-full object-cover opacity-70"
                  onError={(e) => { e.currentTarget.style.display = 'none'; }}
                />
                <div className="absolute inset-0 bg-gradient-to-t from-slate-900 via-slate-900/40 to-transparent" />
                <div className="absolute bottom-3 left-4">
                  <div className="font-bold text-white text-lg drop-shadow-lg">{mapLabel(m.name)}</div>
                  <div className="text-xs text-slate-300">{m.matches_played} matches</div>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3 mb-3 text-center">
                <div>
                  <Users className="w-3.5 h-3.5 mx-auto text-slate-500 mb-1" />
                  <div className="text-sm font-bold text-white">{m.unique_players}</div>
                  <div className="text-[10px] text-slate-500">Players</div>
                </div>
                <div>
                  <Clock className="w-3.5 h-3.5 mx-auto text-slate-500 mb-1" />
                  <div className="text-sm font-bold text-white">{formatDuration(m.avg_duration)}</div>
                  <div className="text-[10px] text-slate-500">Avg Time</div>
                </div>
                <div>
                  <Skull className="w-3.5 h-3.5 mx-auto text-slate-500 mb-1" />
                  <div className="text-sm font-bold text-white">{formatNumber(m.total_kills)}</div>
                  <div className="text-[10px] text-slate-500">Kills</div>
                </div>
              </div>
              <WinRateBar allies={m.allies_win_rate} axis={m.axis_win_rate} />
              <div className="flex items-center justify-between mt-3 pt-3 border-t border-white/5">
                <div className="flex items-center gap-1 text-xs text-slate-500">
                  <Crosshair className="w-3 h-3" />
                  <span>{m.avg_dpm.toFixed(1)} DPM</span>
                </div>
                <span className="text-[10px] text-slate-500">{m.last_played}</span>
              </div>
            </GlassCard>
          ))}
        </div>
      )}
    </div>
  );
}
