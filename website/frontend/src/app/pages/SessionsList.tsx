import { useState } from 'react';
import { Link } from 'react-router';
import { useSessions } from '../lib/queries';
import { Lbl, Pending, SectionHead, Unavailable, lblStyle, rowStyle } from '../components/ui';

/**
 * The evenings (docs/design/12 rows 2 and 30) — one table, two routes:
 * /sessions is the plain archive, /sessions2 adds the BOX columns the
 * legacy sessions2 view earned in #757 (allies/axis map wins and draws are
 * already on every /api/sessions row). Rows link by session_id — the date
 * route merges same-day sessions (the #806 lesson, kept).
 */

const PAGE = 200;

export function SessionsList({ box }: { box: boolean }) {
  // The archive must never silently truncate: when a full page comes back,
  // a 'show older' control raises the limit (the endpoint supports
  // limit/offset; one growing limit keeps a single cache entry and no
  // stitching) — Codex on #811.
  const [limit, setLimit] = useState(PAGE);
  const sessions = useSessions(limit);
  const data = sessions.isError ? undefined : sessions.data;
  const maybeMore = data != null && data.length >= limit;
  return (
    <div style={{ paddingTop: 44, paddingBottom: 40, maxWidth: box ? 900 : 760 }}>
      <Lbl>{box ? 'the evenings · box score' : 'the evenings'}</Lbl>
      <h1 style={{ fontSize: 34, letterSpacing: '0.03em', textTransform: 'uppercase', margin: '12px 0 0', fontWeight: 500 }}>
        Every evening we played.
      </h1>
      <div data-parity={box ? 'sessions2.table' : 'sessions.table'} style={{ marginTop: 24 }}>
        <SectionHead
          label={`newest first · ${data?.length ?? '…'} evenings`}
          aside={box
            ? <Link to="/sessions" style={{ ...lblStyle, fontSize: 9, textDecoration: 'none' }}>plain view →</Link>
            : <Link to="/sessions2" style={{ ...lblStyle, fontSize: 9, textDecoration: 'none' }}>box view →</Link>}
        />
        <div style={{ marginTop: 10 }}>
          <div style={{ ...rowStyle, display: 'grid', gridTemplateColumns: box ? 'minmax(0,1fr) auto auto auto auto auto auto' : 'minmax(0,1fr) auto auto auto auto', gap: 14, padding: '6px 0' }}>
            <Lbl style={{ fontSize: 9 }}>evening</Lbl>
            <Lbl style={{ fontSize: 9 }}>rd</Lbl>
            <Lbl style={{ fontSize: 9 }}>pl</Lbl>
            <Lbl style={{ fontSize: 9 }}>kills</Lbl>
            {box && <Lbl style={{ fontSize: 9 }}>allies</Lbl>}
            {box && <Lbl style={{ fontSize: 9 }}>axis</Lbl>}
            <Lbl style={{ fontSize: 9, textAlign: 'right' }}>box</Lbl>
          </div>
          {sessions.isPending && <div style={{ padding: '10px 0' }}><Pending label="sessions" /></div>}
          {sessions.isError && <div style={{ padding: '10px 0' }}><Unavailable what="sessions" /></div>}
          {data?.length === 0 && (
            <div className="m" style={{ fontSize: 11, color: 'var(--color-text-500)', padding: '10px 0' }}>
              no sessions recorded yet
            </div>
          )}
          {data?.map((row) => (
            <Link
              key={row.session_id}
              to={`/session-detail/${row.session_id}`}
              style={{ ...rowStyle, display: 'grid', gridTemplateColumns: box ? 'minmax(0,1fr) auto auto auto auto auto auto' : 'minmax(0,1fr) auto auto auto auto', gap: 14, alignItems: 'baseline', padding: '10px 0', textDecoration: 'none', color: 'var(--color-text-100)' }}
            >
              <span style={{ fontSize: 15, letterSpacing: '0.04em', textTransform: 'uppercase', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {row.formatted_date}
              </span>
              <span className="m" style={{ fontSize: 12, color: 'var(--color-text-400)' }}>{row.rounds}</span>
              <span className="m" style={{ fontSize: 12, color: 'var(--color-text-400)' }}>{row.players}</span>
              <span className="m" style={{ fontSize: 12, color: 'var(--color-text-400)' }}>{row.total_kills.toLocaleString('en-US')}</span>
              {box && <span className="m" style={{ fontSize: 12, color: 'var(--color-accent)' }}>{row.allies_wins}</span>}
              {box && <span className="m" style={{ fontSize: 12, color: 'var(--color-accent-warm)' }}>{row.axis_wins}</span>}
              <span className="m" style={{ fontSize: 14, minWidth: 58, textAlign: 'right' }}>
                {row.team_1_score != null && row.team_2_score != null
                  ? `${row.team_1_score} / ${row.team_2_score}`
                  : '—'}
              </span>
            </Link>
          ))}
        </div>
        {maybeMore && (
          <button
            type="button"
            onClick={() => setLimit((l) => l + PAGE)}
            style={{
              marginTop: 14, fontSize: 12, letterSpacing: '0.08em', textTransform: 'uppercase',
              border: '1px solid var(--color-rule-700)', background: 'transparent',
              color: 'var(--color-text-300)', padding: '6px 12px', cursor: 'pointer',
            }}
          >
            show older evenings →
          </button>
        )}
        {box && (
          <Lbl style={{ fontSize: 9, marginTop: 10 }}>
            box = 2 points per map won, 1–1 on a draw · allies/axis = map wins by the side, sides swap every map
          </Lbl>
        )}
      </div>
    </div>
  );
}
