import { useState } from 'react';
import { Link } from 'react-router';
import { useSessionLineups, useSessions } from '../lib/queries';
import type { LineupChange, LineupPlayer } from '../lib/types';
import { Lbl, Pending, SectionHead, Unavailable, lblStyle, rowStyle } from '../components/ui';

/**
 * The evenings (docs/design/12 rows 2 and 30) — one table, two routes:
 * /sessions is the plain archive, /sessions2 adds the BOX columns the
 * legacy sessions2 view earned in #757 (allies/axis map wins and draws are
 * already on every /api/sessions row). Rows link by session_id — the date
 * route merges same-day sessions (the #806 lesson, kept).
 */


const TEAM_COLOR: Record<string, string> = { a: 'var(--color-team-a)', b: 'var(--color-team-b)' };

const names = (ps: LineupPlayer[]) => ps.map((p) => p.name).join(' \u00b7 ');

/** Mirror pairs — a player joined one team and left the other in the same
 * round — are one EVENT (they switched teams), not four list entries. */
function foldChanges(changes: LineupChange[]) {
  const byRound = new Map<number, LineupChange[]>();
  for (const c of changes) {
    byRound.set(c.round_id, [...(byRound.get(c.round_id) ?? []), c]);
  }
  const out: { key: string; label: string; text: string }[] = [];
  for (const group of byRound.values()) {
    const where = `${group[0].map_name} R${group[0].round_number}`;
    const consumed = new Set<string>();
    for (const c of group) {
      for (const s of c.swaps) {
        out.push({ key: `${c.round_id}:${s.out.guid || s.out.name}`, label: where, text: `${s.out.name} \u2192 ${s.incoming.name}` });
        consumed.add(s.out.guid);
        consumed.add(s.incoming.guid);
      }
    }
    for (const c of group) {
      const sibling = group.find((o) => o.team !== c.team);
      for (const p of c.joined) {
        if (consumed.has(p.guid)) continue;
        if (sibling?.left.some((l) => l.guid === p.guid)) {
          out.push({ key: `${c.round_id}:sw:${p.guid || p.name}`, label: where, text: `${p.name} \u21c4 switched to team ${c.team}` });
          consumed.add(p.guid);
        }
      }
    }
    for (const c of group) {
      for (const p of c.joined) {
        if (!consumed.has(p.guid)) out.push({ key: `${c.round_id}:+${p.guid || p.name}`, label: where, text: `+ ${p.name} (team ${c.team})` });
      }
      for (const p of c.left) {
        if (!consumed.has(p.guid)) out.push({ key: `${c.round_id}:-${p.guid || p.name}`, label: where, text: `\u2212 ${p.name} (team ${c.team})` });
      }
    }
  }
  return out;
}

function LineupStrip({ sessionId, open }: { sessionId: number; open: boolean }) {
  const lineups = useSessionLineups(sessionId, open);
  if (!open) return null;
  const data = lineups.isError ? undefined : lineups.data;
  const events = data ? foldChanges(data.changes) : [];
  return (
    <div data-parity="sessions2.lineups" style={{ padding: '2px 0 12px' }}>
      {lineups.isPending && <Pending label="lineups" />}
      {lineups.isError && <Unavailable what="lineups" />}
      {data && data.teams.length === 0 && (
        <span className="m" style={{ fontSize: 11, color: 'var(--color-text-500)' }}>
          no roster capture for this evening
        </span>
      )}
      {data && data.teams.length > 0 && (
        <>
          <div style={{ display: 'flex', gap: 10, alignItems: 'baseline', flexWrap: 'wrap' }}>
            {data.teams.map((t, i) => (
              <span key={t.key} style={{ display: 'inline-flex', gap: 10, alignItems: 'baseline' }}>
                {i > 0 && <span className="m" style={{ fontSize: 14, color: 'var(--color-text-500)' }}>/</span>}
                <span style={{ fontSize: 13, letterSpacing: '0.05em', textTransform: 'uppercase', color: TEAM_COLOR[t.key] ?? 'var(--color-text-200)' }}>
                  {names(t.players)}
                </span>
              </span>
            ))}
          </div>
          {events.length > 0 && (
            <div style={{ marginTop: 6 }}>
              {events.map((e) => (
                <div key={e.key} className="m" style={{ ...rowStyle, fontSize: 10, color: 'var(--color-text-400)', padding: '3px 0', display: 'flex', gap: 12 }}>
                  <span style={{ ...lblStyle, fontSize: 9 }}>{e.label}</span>
                  <span>{e.text}</span>
                </div>
              ))}
            </div>
          )}
          {data.rounds_without_roster > 0 && (
            <Lbl style={{ fontSize: 9, marginTop: 6 }}>
              {data.rounds_without_roster} round(s) without roster capture \u2014 changes there are unmeasured
            </Lbl>
          )}
        </>
      )}
    </div>
  );
}

const PAGE = 200;

export function SessionsList({ box }: { box: boolean }) {
  // The archive must never silently truncate: when a full page comes back,
  // a 'show older' control raises the limit (the endpoint supports
  // limit/offset; one growing limit keeps a single cache entry and no
  // stitching) — Codex on #811.
  const [limit, setLimit] = useState(PAGE);
  // One lineup strip open at a time — the strip is an instrument readout,
  // not an accordion wall.
  const [openLineup, setOpenLineup] = useState<number | null>(null);
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
          <div style={{ ...rowStyle, display: 'grid', gridTemplateColumns: box ? 'minmax(0,1fr) auto auto auto auto auto auto auto' : 'minmax(0,1fr) auto auto auto auto', gap: 14, padding: '6px 0' }}>
            <Lbl style={{ fontSize: 9 }}>evening</Lbl>
            <Lbl style={{ fontSize: 9 }}>rd</Lbl>
            <Lbl style={{ fontSize: 9 }}>pl</Lbl>
            <Lbl style={{ fontSize: 9 }}>kills</Lbl>
            {box && <Lbl style={{ fontSize: 9 }}>allies</Lbl>}
            {box && <Lbl style={{ fontSize: 9 }}>axis</Lbl>}
            {box && <Lbl style={{ fontSize: 9 }}>draw</Lbl>}
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
            <div key={row.session_id}>
            <Link
              to={`/session-detail/${row.session_id}`}
              style={{ ...rowStyle, display: 'grid', gridTemplateColumns: box ? 'minmax(0,1fr) auto auto auto auto auto auto auto' : 'minmax(0,1fr) auto auto auto auto', gap: 14, alignItems: 'baseline', padding: '10px 0', textDecoration: 'none', color: 'var(--color-text-100)' }}
            >
              <span style={{ fontSize: 15, letterSpacing: '0.04em', textTransform: 'uppercase', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {row.formatted_date}
              </span>
              <span className="m" style={{ fontSize: 12, color: 'var(--color-text-400)' }}>{row.rounds}</span>
              <span className="m" style={{ fontSize: 12, color: 'var(--color-text-400)' }}>{row.players}</span>
              <span className="m" style={{ fontSize: 12, color: 'var(--color-text-400)' }}>{row.total_kills.toLocaleString('en-US')}</span>
              {box && <span className="m" style={{ fontSize: 12, color: 'var(--color-accent)' }}>{row.allies_wins}</span>}
              {box && <span className="m" style={{ fontSize: 12, color: 'var(--color-accent-warm)' }}>{row.axis_wins}</span>}
              {box && <span className="m" style={{ fontSize: 12, color: 'var(--color-text-400)' }}>{row.draws}</span>}
              <span className="m" style={{ fontSize: 14, minWidth: 58, textAlign: 'right' }}>
                {/* 0/0 with an aggregate row present means NO map was
                  * attributed — a dash, not a claimed tie (Codex wave 2). */}
                {row.team_1_score != null && row.team_2_score != null && row.team_1_score + row.team_2_score > 0
                  ? `${row.team_1_score} / ${row.team_2_score}`
                  : '—'}
              </span>
            </Link>
            {box && (
              <button
                type="button"
                onClick={() => { setOpenLineup((cur) => (cur === row.session_id ? null : row.session_id)); }}
                style={{ ...lblStyle, fontSize: 9, background: 'none', border: 'none', cursor: 'pointer', padding: '2px 0 6px', color: openLineup === row.session_id ? 'var(--color-text-200)' : 'var(--color-text-500)' }}
              >
                lineup {openLineup === row.session_id ? '\u25b4' : '\u25be'}
              </button>
            )}
            {box && <LineupStrip sessionId={row.session_id} open={openLineup === row.session_id} />}
            </div>
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
