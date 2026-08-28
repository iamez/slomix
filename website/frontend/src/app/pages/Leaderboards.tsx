import { useState } from 'react';
import { Link } from 'react-router';
import { useLeaderboard } from '../lib/queries';
import { Chip, Lbl, lblStyle, Pending, rowStyle, SectionHead, Unavailable } from '../components/ui';

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
    <div style={{ paddingTop: 44, paddingBottom: 40, maxWidth: 860 }}>
      <Lbl>leaderboards · top players by performance</Lbl>
      <h1 style={{ fontSize: 34, letterSpacing: '0.03em', textTransform: 'uppercase', margin: '12px 0 0', fontWeight: 500 }}>
        Who leads, and by how much.
      </h1>

      <div data-parity="leaderboards.filters" style={{ marginTop: 22 }}>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {STATS.map((s) => (
            <Chip key={s.key} active={stat === s.key} label={s.label} onClick={() => setStat(s.key)} />
          ))}
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
          {PERIODS.map((p) => (
            <Chip key={p.key} active={period === p.key} label={p.label} onClick={() => setPeriod(p.key)} />
          ))}
        </div>
      </div>

      <div data-parity="leaderboards.table" style={{ marginTop: 22 }}>
        <SectionHead label={`${statLabel.toLowerCase()} · ${PERIODS.find((p) => p.key === period)?.label.toLowerCase()}`} />
        <div className="lb-table" style={{ marginTop: 8 }}>
          <div className="lb-row" style={{ ...rowStyle, display: 'grid', gridTemplateColumns: cols, gap: 14, padding: '6px 0' }}>
            <Lbl style={{ fontSize: 9 }}>#</Lbl>
            <Lbl style={{ fontSize: 9 }}>player</Lbl>
            <Lbl style={{ fontSize: 9, textAlign: 'right' }}>{statLabel}</Lbl>
            {stat !== 'games' && <span className="lb-aux"><Lbl style={{ fontSize: 9, textAlign: 'right' }}>rounds</Lbl></span>}
            {stat !== 'kills' && <span className="lb-aux"><Lbl style={{ fontSize: 9, textAlign: 'right' }}>kills</Lbl></span>}
            {stat !== 'kd' && <span className="lb-aux"><Lbl style={{ fontSize: 9, textAlign: 'right' }}>k/d</Lbl></span>}
          </div>
          {board.isPending && <div style={{ padding: '10px 0' }}><Pending label="leaderboard" /></div>}
          {board.isError && <div style={{ padding: '10px 0' }}><Unavailable what="leaderboard" /></div>}
          {data?.length === 0 && (
            <div className="m" style={{ fontSize: 11, color: 'var(--color-text-500)', padding: '10px 0' }}>
              no data found for this period
            </div>
          )}
          {data?.map((row) => (
            <Link
              key={row.guid}
              to={`/profile/${row.guid}`}
              className="lb-row"
              style={{ ...rowStyle, display: 'grid', gridTemplateColumns: cols, gap: 14, alignItems: 'baseline', padding: '9px 0', textDecoration: 'none', color: 'var(--color-text-100)' }}
            >
              <span className="m" style={{ ...lblStyle, fontSize: 10 }}>{String(row.rank).padStart(2, '0')}</span>
              <span className="m" style={{ fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{row.name}</span>
              <span className="m" style={{ fontSize: 13, textAlign: 'right', color: 'var(--color-text-100)' }}>{formatValue(stat, row.value)}</span>
              {stat !== 'games' && <span className="m lb-aux" style={{ fontSize: 12, textAlign: 'right', color: 'var(--color-text-400)' }}>{row.rounds}</span>}
              {stat !== 'kills' && <span className="m lb-aux" style={{ fontSize: 12, textAlign: 'right', color: 'var(--color-text-400)' }}>{row.kills}</span>}
              {stat !== 'kd' && <span className="m lb-aux" style={{ fontSize: 12, textAlign: 'right', color: 'var(--color-text-400)' }}>{row.kd.toFixed(2)}</span>}
            </Link>
          ))}
        </div>
        {/* Measured against players_router:1132 — the 50-bullet/rate-cap
          * claim belonged to the RECORDS endpoint, not this one (Codex on
          * #813; my own confident-half). */}
        <Lbl style={{ fontSize: 9, marginTop: 10 }}>
          bots excluded · halves only (r1+r2) · accuracy needs 100+ bullets
        </Lbl>
      </div>
    </div>
  );
}
