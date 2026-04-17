import { useEffect, useMemo, useState } from 'react';
import type {
  SessionTeamMatrix,
  SessionTeamMatrixCell,
  SessionTeamMatrixPlayer,
} from '../api/types';
import { cn } from '../lib/cn';

type MetricMode = 'dpm' | 'kd' | 'damage';

const METRIC_LABELS: Record<MetricMode, string> = {
  dpm: 'DPM',
  kd: 'K/D',
  damage: 'Damage',
};

const STORAGE_KEY = 'session-matrix-metric';

function formatCell(cell: SessionTeamMatrixCell | undefined, metric: MetricMode): string {
  if (!cell || !cell.played) return '—';
  switch (metric) {
    case 'dpm':
      return cell.dpm.toFixed(0);
    case 'kd':
      return `${cell.kills}/${cell.deaths}`;
    case 'damage':
      return cell.damage >= 1000 ? `${(cell.damage / 1000).toFixed(1)}k` : String(cell.damage);
  }
}

function formatTotals(player: SessionTeamMatrixPlayer, metric: MetricMode): string {
  const t = player.totals;
  switch (metric) {
    case 'dpm':
      return t.dpm.toFixed(0);
    case 'kd':
      return `${t.kills}/${t.deaths}`;
    case 'damage':
      return t.damage >= 1000 ? `${(t.damage / 1000).toFixed(1)}k` : String(t.damage);
  }
}

function cellSecondaryLine(cell: SessionTeamMatrixCell | undefined, metric: MetricMode): string {
  if (!cell || !cell.played) return '';
  if (metric === 'dpm') return `${cell.kills}/${cell.deaths}`;
  if (metric === 'kd') return `${cell.dpm.toFixed(0)} dpm`;
  return `${cell.kills}/${cell.deaths}`;
}

function formatMapName(name: string): string {
  return name
    .replace(/^etl_/i, '')
    .replace(/_final.*$/i, '')
    .replace(/_/g, ' ');
}

function TeamBadge({ label, colorClass }: { label: 'A' | 'B'; colorClass: string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center justify-center w-6 h-5 text-[10px] font-black rounded border',
        colorClass,
      )}
    >
      {label}
    </span>
  );
}

interface Props {
  matrix: SessionTeamMatrix;
  activePlayerGuid?: string | null;
  onMapClick?: (mapIndex: number) => void;
  onPlayerClick?: (playerGuid: string) => void;
}

export function PlayerMatchMatrix({
  matrix,
  activePlayerGuid,
  onMapClick,
  onPlayerClick,
}: Props) {
  const [metric, setMetric] = useState<MetricMode>(() => {
    if (typeof window === 'undefined') return 'dpm';
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return (stored === 'kd' || stored === 'damage' || stored === 'dpm') ? stored : 'dpm';
  });

  useEffect(() => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(STORAGE_KEY, metric);
    }
  }, [metric]);

  const sortedRosters = useMemo(() => {
    const teamA = [...(matrix.rosters?.team_a ?? [])];
    const teamB = [...(matrix.rosters?.team_b ?? [])];
    const sortFn = (a: SessionTeamMatrixPlayer, b: SessionTeamMatrixPlayer) => {
      if (metric === 'kd') return b.totals.kd - a.totals.kd;
      if (metric === 'damage') return b.totals.damage - a.totals.damage;
      return b.totals.dpm - a.totals.dpm;
    };
    teamA.sort(sortFn);
    teamB.sort(sortFn);
    return { teamA, teamB };
  }, [matrix.rosters, metric]);

  if (!matrix.available || !matrix.rosters || !matrix.maps || matrix.maps.length === 0) {
    return null;
  }

  const teamAName = matrix.team_a_name ?? 'Team A';
  const teamBName = matrix.team_b_name ?? 'Team B';
  const maps = matrix.maps;

  const renderRow = (player: SessionTeamMatrixPlayer, team: 'A' | 'B') => {
    const isActive = activePlayerGuid === player.player_guid;
    const badgeColor = team === 'A'
      ? 'border-blue-400/40 text-blue-300 bg-blue-500/10'
      : 'border-rose-400/40 text-rose-300 bg-rose-500/10';
    return (
      <tr
        key={`${team}-${player.player_guid}`}
        className={cn(
          'border-t border-white/5 hover:bg-white/5 transition',
          isActive && 'bg-cyan-500/10',
        )}
      >
        <td className="sticky left-0 z-10 bg-slate-900/80 backdrop-blur px-3 py-2">
          <button
            type="button"
            onClick={() => onPlayerClick?.(player.player_guid)}
            className="flex items-center gap-2 text-left group"
          >
            <TeamBadge label={team} colorClass={badgeColor} />
            <span className="text-white font-semibold text-sm group-hover:text-cyan-300">
              {player.player_name}
            </span>
          </button>
        </td>
        {maps.map((_, mapIdx) => {
          const cell = player.cells[mapIdx];
          const primary = formatCell(cell, metric);
          const secondary = cellSecondaryLine(cell, metric);
          const played = cell?.played;
          return (
            <td
              key={mapIdx}
              className={cn(
                'px-3 py-2 text-center tabular-nums',
                played ? 'text-slate-200' : 'text-slate-600',
              )}
              title={played && cell
                ? `kills ${cell.kills} · deaths ${cell.deaths} · dmg ${cell.damage} · dpm ${cell.dpm.toFixed(1)}`
                : 'did not play'}
            >
              <div className="font-semibold text-sm">{primary}</div>
              {secondary && <div className="text-[10px] text-slate-500">{secondary}</div>}
            </td>
          );
        })}
        <td className="px-3 py-2 text-center font-bold text-white tabular-nums bg-white/5">
          {formatTotals(player, metric)}
        </td>
      </tr>
    );
  };

  return (
    <div className="glass-card rounded-xl p-5 mb-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="text-sm font-bold text-white">Player × Map Matrix</div>
          <div className="text-[11px] text-slate-500">
            Stats split per round by team. Substitutes appear in both rosters.
          </div>
        </div>
        <div className="inline-flex rounded-lg border border-white/10 overflow-hidden text-xs">
          {(Object.keys(METRIC_LABELS) as MetricMode[]).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMetric(m)}
              className={cn(
                'px-3 py-1.5 transition',
                metric === m
                  ? 'bg-cyan-500/20 text-cyan-200 font-semibold'
                  : 'text-slate-400 hover:text-white hover:bg-white/5',
              )}
            >
              {METRIC_LABELS[m]}
            </button>
          ))}
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="text-[11px] uppercase text-slate-400">
              <th className="sticky left-0 z-10 bg-slate-900/80 backdrop-blur px-3 py-2 text-left">
                Player
              </th>
              {maps.map((map, mapIdx) => (
                <th
                  key={`${map.map_name}-${mapIdx}`}
                  className="px-3 py-2 text-center cursor-pointer hover:text-cyan-300"
                  onClick={() => onMapClick?.(mapIdx)}
                >
                  {formatMapName(map.map_name)}
                </th>
              ))}
              <th className="px-3 py-2 text-center bg-white/5">Total</th>
            </tr>
          </thead>
          <tbody>
            {sortedRosters.teamA.length > 0 && (
              <>
                <tr className="bg-blue-500/5">
                  <td
                    colSpan={maps.length + 2}
                    className="sticky left-0 bg-blue-500/10 px-3 py-1.5 text-[11px] uppercase font-bold text-blue-300"
                  >
                    {teamAName}
                  </td>
                </tr>
                {sortedRosters.teamA.map((p) => renderRow(p, 'A'))}
              </>
            )}
            {sortedRosters.teamB.length > 0 && (
              <>
                <tr className="bg-rose-500/5">
                  <td
                    colSpan={maps.length + 2}
                    className="sticky left-0 bg-rose-500/10 px-3 py-1.5 text-[11px] uppercase font-bold text-rose-300"
                  >
                    {teamBName}
                  </td>
                </tr>
                {sortedRosters.teamB.map((p) => renderRow(p, 'B'))}
              </>
            )}
            <tr className="border-t-2 border-white/10">
              <td className="sticky left-0 bg-slate-900/80 backdrop-blur px-3 py-2 text-[11px] uppercase text-slate-400">
                Map score
              </td>
              {maps.map((map, mapIdx) => {
                const a = map.team_a_score ?? 0;
                const b = map.team_b_score ?? 0;
                const aWon = a > b;
                const bWon = b > a;
                return (
                  <td key={mapIdx} className="px-3 py-2 text-center text-xs tabular-nums">
                    <span className={aWon ? 'text-blue-400 font-bold' : 'text-slate-400'}>{a}</span>
                    <span className="text-slate-600 mx-1">–</span>
                    <span className={bWon ? 'text-rose-400 font-bold' : 'text-slate-400'}>{b}</span>
                  </td>
                );
              })}
              <td className="px-3 py-2 bg-white/5" />
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
