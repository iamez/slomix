/**
 * The player × map matrix of an evening — every player's line, one cell per
 * map, with a metric switch (dpm / k/d / damage). The old React had it
 * (`src/pages` PlayerMatchMatrix); the new page drew the team totals only
 * while `/detail` carried the whole matrix (ledger 2026-09-08).
 *
 * Columns are DATA: one `DataColumn` per map from `matrix.maps`, so a
 * seventh map is a seventh column and no layout knows the number.
 */
import { useEffect, useState } from 'react';

import { DataTable, type DataColumn } from './DataTable';
import { Cluster, Stack } from './layout';
import { Absent, Chip, Lbl, Meta, SectionHead, Unavailable, figure } from './ui';
import { mapLabel } from '../lib/maps';
import type { SessionMatrixCell, SessionMatrixPlayer, SessionTeamMatrix } from '../lib/types';

export type MatrixMetric = 'dpm' | 'kd' | 'damage';
const METRICS: { key: MatrixMetric; label: string; title: string }[] = [
  { key: 'dpm', label: 'dpm', title: 'damage per minute played on that map' },
  { key: 'kd', label: 'k/d', title: 'kills over deaths on that map' },
  { key: 'damage', label: 'damage', title: 'damage given on that map' },
];
const STORAGE_KEY = 'spa.session.matrix.metric';
const ABSENT_REASON: Record<string, string> = {
  no_teams: 'no lua team rosters for this session, so no matrix',
  no_rounds: 'no counted rounds in this session',
};

function readStoredMetric(): MatrixMetric {
  try {
    const v = window.localStorage.getItem(STORAGE_KEY);
    return v === 'kd' || v === 'damage' || v === 'dpm' ? v : 'dpm';
  } catch {
    return 'dpm';
  }
}

function cellText(c: Pick<SessionMatrixCell, 'dpm' | 'kd' | 'damage'>, metric: MatrixMetric): string {
  return metric === 'damage' ? figure(c.damage) : metric === 'kd' ? figure(c.kd) : figure(c.dpm);
}

function columnsFor(maps: NonNullable<SessionTeamMatrix['maps']>, metric: MatrixMetric): DataColumn<SessionMatrixPlayer>[] {
  const perMap: DataColumn<SessionMatrixPlayer>[] = maps.map((m) => ({
    key: `map-${String(m.map_index)}`,
    // A null score is an absent stopwatch result, shown as a dash, never as 'null'.
    label: <span title={`${mapLabel(m.map_name)} · ${m.team_a_score == null ? '—' : figure(m.team_a_score)}–${m.team_b_score == null ? '—' : figure(m.team_b_score)}`}>{mapLabel(m.map_name)}</span>,
    align: 'right',
    format: (p) => {
      const cell = p.cells.find((c) => c.map_index === m.map_index);
      // Not played is not a zero: the cell is absent, the figure would lie.
      return cell?.played ? cellText(cell, metric) : <Meta>—</Meta>;
    },
    sortValue: (p) => {
      const cell = p.cells.find((c) => c.map_index === m.map_index);
      return cell?.played ? cell[metric] : null;
    },
  }));
  return [
    { key: 'player', label: 'player', width: 160, align: 'left', sortValue: (p) => p.player_name },
    ...perMap,
    { key: 'total', label: 'session', align: 'right', title: 'the whole evening', format: (p) => cellText(p.totals, metric), sortValue: (p) => p.totals[metric] },
  ];
}

export function PlayerMapMatrix({ matrix }: { matrix: SessionTeamMatrix }) {
  const [metric, setMetric] = useState<MatrixMetric>(readStoredMetric);
  useEffect(() => {
    try { window.localStorage.setItem(STORAGE_KEY, metric); } catch { /* private mode: the choice lives for the page */ }
  }, [metric]);

  const maps = matrix.maps ?? [];
  const rosters = matrix.rosters;
  return (
    <Stack gap={3} parity="session.matrix">
      <SectionHead
        label="player × map"
        aside={(
          <Cluster gap={2}>
            {METRICS.map((m) => (
              <Chip key={m.key} active={metric === m.key} label={m.label} title={m.title} onClick={() => { setMetric(m.key); }} />
            ))}
          </Cluster>
        )}
      />
      {!matrix.available && (matrix.reason === 'error' || matrix.reason === 'side_mapping_failed') ? (
        // The instrument failed; that is not an empty result (Codex on #989).
        <Unavailable what="player × map matrix" />
      ) : !matrix.available || !rosters || maps.length === 0 ? (
        <Absent reason={ABSENT_REASON[matrix.reason ?? ''] ?? 'no matrix without the team rosters — this session has none'} />
      ) : (
        <Stack gap={4}>
          {([['team_a', matrix.team_a_name ?? 'Team A'], ['team_b', matrix.team_b_name ?? 'Team B']] as const).map(([key, name]) => (
            <Stack key={key} gap={1}>
              <Lbl style={{ fontSize: 'var(--fs-caption)' }}>{name}</Lbl>
              <DataTable<SessionMatrixPlayer>
                parity={key === 'team_a' ? 'session.matrix.team-a' : 'session.matrix.team-b'}
                label={`${name} by map`}
                columns={columnsFor(maps, metric)}
                rows={rosters[key]}
                rowKey={(p) => p.player_guid}
                defaultSort={{ key: 'total', dir: 'desc' }}
                minWidth={160 + 90 * (maps.length + 1)}
              />
            </Stack>
          ))}
          <Meta>a dash is a map the player did not play — not a zero</Meta>
        </Stack>
      )}
    </Stack>
  );
}
