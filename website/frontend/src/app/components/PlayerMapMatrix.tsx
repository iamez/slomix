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
import { Absent, Lbl, Meta, SectionHead, figure } from './ui';
import { mapLabel } from '../lib/maps';
import type { SessionMatrixCell, SessionMatrixPlayer, SessionTeamMatrix } from '../lib/types';

export type MatrixMetric = 'dpm' | 'kd' | 'damage';
const METRICS: { key: MatrixMetric; label: string; title: string }[] = [
  { key: 'dpm', label: 'dpm', title: 'damage per minute played on that map' },
  { key: 'kd', label: 'k/d', title: 'kills over deaths on that map' },
  { key: 'damage', label: 'damage', title: 'damage given on that map' },
];
const STORAGE_KEY = 'spa.session.matrix.metric';

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
    label: <span title={`${mapLabel(m.map_name)} · ${String(m.team_a_score)}–${String(m.team_b_score)}`}>{mapLabel(m.map_name)}</span>,
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
    { key: 'player', label: 'player', sortValue: (p) => p.player_name },
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
              <button
                key={m.key}
                type="button"
                title={m.title}
                aria-pressed={metric === m.key}
                onClick={() => { setMetric(m.key); }}
                style={{ all: 'unset', cursor: 'pointer', fontSize: 'var(--fs-caption)', letterSpacing: '0.08em', textTransform: 'uppercase',
                         color: metric === m.key ? 'var(--color-text-100)' : 'var(--color-text-500)' }}
              >
                {m.label}
              </button>
            ))}
          </Cluster>
        )}
      />
      {!matrix.available || !rosters || maps.length === 0 ? (
        <Absent reason="no matrix without the team rosters — this session has none" />
      ) : (
        <Stack gap={4}>
          {([['team_a', matrix.team_a_name ?? 'Team A'], ['team_b', matrix.team_b_name ?? 'Team B']] as const).map(([key, name]) => (
            <Stack key={key} gap={1}>
              <Lbl style={{ fontSize: 'var(--fs-caption)' }}>{name}</Lbl>
              <DataTable<SessionMatrixPlayer>
                parity={`session.matrix.${key}`}
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
