import { useState } from 'react';
import { Link } from 'react-router';
import { useLeaderboard } from '../lib/queries';
import { Absent, Chip, Lbl, lblStyle, Pending, rowStyle, SectionHead, Unavailable } from '../components/ui';

/**
 * Leaderboards (docs/design/12 row 3) — legacy leaderboard.js carried over:
 * one table, a stat picker and a period picker. Kept verbatim: the nine
 * stats, the four periods, limit 50, client-side value formatting per stat.
 * Not carried: min_games (the legacy FE never sent it and the backend
 * ignores it), and the duplicated column when the picked stat equals a
 * fixed column — the fixed column simply highlights instead.
 */

const STATS: { key: string; label: string }[] = [
  { key: 'dpm', label: 'DPM' },
  { key: 'kills', label: 'Kills' },
  { key: 'kd', label: 'K/D' },
  { key: 'damage', label: 'Damage' },
  { key: 'headshots', label: 'Headshots' },
  { key: 'accuracy', label: 'Accuracy (%)' },
  { key: 'revives', label: 'Revives' },
  { key: 'gibs', label: 'Gibs' },
  { key: 'games', label: 'Rounds' },
];

const PERIODS: { key: string; label: string }[] = [
  { key: '7d', label: '7 days' },
  { key: '30d', label: '30 days' },
  { key: 'season', label: 'Season' },
  { key: 'all', label: 'All time' },
];

/** Legacy's client-side formatting, per stat. */
function formatValue(stat: string, value: number): string {
  if (stat === 'accuracy') return `${value.toFixed(1)}%`;
  if (stat === 'dpm') return value.toFixed(1);
  if (stat === 'kd') return value.toFixed(2);
  return value.toLocaleString('en-US');
}


export function Leaderboards() {
  // Legacy defaults: stat=games ("Rounds"), period=season.
  const [stat, setStat] = useState('games');
  const [period, setPeriod] = useState('season');
  const board = useLeaderboard(stat, period);
  const data = board.isError ? undefined : board.data;
  const statLabel = STATS.find((s) => s.key === stat)?.label ?? stat.toUpperCase();
  // The picked stat already renders in the value column — repeating it in
  // its fixed column showed the same number twice on the DEFAULT view
  // (Codex on #813, wave 2). The fixed column hides instead.
  const cols = `34px minmax(0,1fr) auto${stat === 'games' ? '' : ' auto'}${stat === 'kills' ? '' : ' auto'}${stat === 'kd' ? '' : ' auto'}`;
  return (
    <div style={{ paddingTop: 'var(--space-7)', paddingBottom: 'var(--space-7)', maxWidth: 860 }}>
      <Lbl>leaderboards · top players by performance</Lbl>
      <h1 style={{ fontSize: 'var(--fs-title)', letterSpacing: '0.03em', textTransform: 'uppercase', margin: 'var(--space-3) 0 0', fontWeight: 500 }}>
        Who leads, and by how much.
      </h1>

      <div data-parity="leaderboards.filters" style={{ marginTop: 'var(--space-5)' }}>
        <div style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
          {STATS.map((s) => (
            <Chip key={s.key} active={stat === s.key} label={s.label} onClick={() => { setStat(s.key); }} />
          ))}
        </div>
        <div style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap', marginTop: 'var(--space-2)' }}>
          {PERIODS.map((p) => (
            <Chip key={p.key} active={period === p.key} label={p.label} onClick={() => { setPeriod(p.key); }} />
          ))}
        </div>
      </div>

      <div data-parity="leaderboards.table" style={{ marginTop: 'var(--space-5)' }}>
        <SectionHead label={`${statLabel.toLowerCase()} · ${PERIODS.find((p) => p.key === period)?.label.toLowerCase()}`} />
        <div className="lb-table" style={{ marginTop: 'var(--space-2)' }}>
          <div className="lb-row" style={{ ...rowStyle, display: 'grid', gridTemplateColumns: cols, gap: 'var(--space-4)', padding: 'var(--space-2) 0' }}>
            <Lbl style={{ fontSize: 'var(--fs-caption)' }}>#</Lbl>
            <Lbl style={{ fontSize: 'var(--fs-caption)' }}>player</Lbl>
            <Lbl style={{ fontSize: 'var(--fs-caption)', textAlign: 'right' }}>{statLabel}</Lbl>
            {stat !== 'games' && <span className="lb-aux"><Lbl style={{ fontSize: 'var(--fs-caption)', textAlign: 'right' }}>rounds</Lbl></span>}
            {stat !== 'kills' && <span className="lb-aux"><Lbl style={{ fontSize: 'var(--fs-caption)', textAlign: 'right' }}>kills</Lbl></span>}
            {stat !== 'kd' && <span className="lb-aux"><Lbl style={{ fontSize: 'var(--fs-caption)', textAlign: 'right' }}>k/d</Lbl></span>}
          </div>
          {board.isPending && <div style={{ padding: 'var(--space-2) 0' }}><Pending label="leaderboard" /></div>}
          {board.isError && <div style={{ padding: 'var(--space-2) 0' }}><Unavailable what="leaderboard" /></div>}
          {data?.length === 0 && (
            <Absent block style={{ padding: 'var(--space-2) 0' }} reason="no data found for this period" />
          )}
          {data?.map((row) => (
            <Link
              key={row.guid}
              to={`/profile/${row.guid}`}
              className="lb-row"
              style={{ ...rowStyle, display: 'grid', gridTemplateColumns: cols, gap: 'var(--space-4)', alignItems: 'baseline', padding: 'var(--space-2) 0', textDecoration: 'none', color: 'var(--color-text-100)' }}
            >
              <span className="m" style={{ ...lblStyle, fontSize: 'var(--fs-label)' }}>{String(row.rank).padStart(2, '0')}</span>
              <span className="m" style={{ fontSize: 'var(--fs-value)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{row.name}</span>
              <span className="m" style={{ fontSize: 'var(--fs-value)', textAlign: 'right', color: 'var(--color-text-100)' }}>{formatValue(stat, row.value)}</span>
              {stat !== 'games' && <span className="m lb-aux" style={{ fontSize: 'var(--fs-small)', textAlign: 'right', color: 'var(--color-text-400)' }}>{row.rounds}</span>}
              {stat !== 'kills' && <span className="m lb-aux" style={{ fontSize: 'var(--fs-small)', textAlign: 'right', color: 'var(--color-text-400)' }}>{row.kills ?? '—'}</span>}
              {stat !== 'kd' && <span className="m lb-aux" style={{ fontSize: 'var(--fs-small)', textAlign: 'right', color: 'var(--color-text-400)' }}>{row.kd.toFixed(2)}</span>}
            </Link>
          ))}
        </div>
        {/* Measured against players_router:1132 — the 50-bullet/rate-cap
          * claim belonged to the RECORDS endpoint, not this one (Codex on
          * #813; my own confident-half). */}
        <Lbl style={{ fontSize: 'var(--fs-caption)', marginTop: 'var(--space-2)' }}>
          bots excluded · halves only (r1+r2) · accuracy needs 100+ bullets
        </Lbl>
      </div>
    </div>
  );
}
