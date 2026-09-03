import { useMemo, useState } from 'react';
import { Link } from 'react-router';
import { useSessionLineups, useSessions } from '../lib/queries';
import { mapImageFor, mapLabel } from '../lib/maps';
import type { LineupChange, LineupPlayer, SessionSummary } from '../lib/types';
import { Absent, Lbl, lblStyle, Meta, Pending, rowStyle, SectionHead, Unavailable, figure } from '../components/ui';

/**
 * The evenings — ONE archive (stats 2.0, docs/design/18 §B). Until #8xx this
 * component served two routes with a boolean (/sessions plain, /sessions2
 * with the BOX columns); the owner wanted one list, so the BOX view is the
 * view and /sessions2 redirects here.
 *
 * Each row is what an ET player reads first: a levelshot of one of the
 * evening's maps (the API lists them alphabetically — the map played first
 * is R2 work, see BACKLOG), the date and the session id (two evenings on one date are two
 * rows, and the id is how they differ), the BOX score, the maps, rounds and
 * players, and a flag when a round is missing (an odd count means a map has
 * one half). Rows are sorted by date, then id, newest first — the API already
 * does that, and the sort here keeps the promise if it ever stops.
 */

const TEAM_COLOR: Record<string, string> = { a: 'var(--color-team-a)', b: 'var(--color-team-b)' };

const names = (ps: LineupPlayer[]) => ps.map((p) => p.name).join(' · ');

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
        out.push({ key: `${c.round_id}:${s.out.guid || s.out.name}`, label: where, text: `${s.out.name} → ${s.incoming.name}` });
        consumed.add(s.out.guid);
        consumed.add(s.incoming.guid);
      }
    }
    for (const c of group) {
      const sibling = group.find((o) => o.team !== c.team);
      for (const p of c.joined) {
        if (consumed.has(p.guid)) continue;
        if (sibling?.left.some((l) => l.guid === p.guid)) {
          out.push({ key: `${c.round_id}:sw:${p.guid || p.name}`, label: where, text: `${p.name} ⇄ switched to team ${c.team}` });
          consumed.add(p.guid);
        }
      }
    }
    for (const c of group) {
      for (const p of c.joined) {
        if (!consumed.has(p.guid)) out.push({ key: `${c.round_id}:+${p.guid || p.name}`, label: where, text: `+ ${p.name} (team ${c.team})` });
      }
      for (const p of c.left) {
        if (!consumed.has(p.guid)) out.push({ key: `${c.round_id}:-${p.guid || p.name}`, label: where, text: `− ${p.name} (team ${c.team})` });
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
    <div data-parity="sessions.lineups" style={{ padding: '2px 0 12px' }}>
      {lineups.isPending && <Pending label="lineups" />}
      {lineups.isError && <Unavailable what="lineups" />}
      {data && data.teams.length === 0 && (
        <Absent reason="no roster capture for this evening" />
      )}
      {data && data.teams.length > 0 && (
        <>
          <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'baseline', flexWrap: 'wrap' }}>
            {data.teams.map((t, i) => (
              <span key={t.key} style={{ display: 'inline-flex', gap: 'var(--space-2)', alignItems: 'baseline' }}>
                {i > 0 && <span className="m" style={{ fontSize: 'var(--fs-body)', color: 'var(--color-text-500)' }}>/</span>}
                <span style={{ fontSize: 'var(--fs-value)', letterSpacing: '0.05em', textTransform: 'uppercase', color: TEAM_COLOR[t.key] ?? 'var(--color-text-200)' }}>
                  {names(t.players)}
                </span>
              </span>
            ))}
          </div>
          {events.length > 0 && (
            <div style={{ marginTop: 'var(--space-2)' }}>
              {events.map((e) => (
                <div key={e.key} className="m" style={{ ...rowStyle, fontSize: 'var(--fs-label)', color: 'var(--color-text-400)', padding: '3px 0', display: 'flex', gap: 'var(--space-3)' }}>
                  <span style={{ ...lblStyle, fontSize: 'var(--fs-caption)' }}>{e.label}</span>
                  <span>{e.text}</span>
                </div>
              ))}
            </div>
          )}
          {data.rounds_without_roster > 0 && (
            <Lbl style={{ fontSize: 'var(--fs-caption)', marginTop: 'var(--space-2)' }}>
              {data.rounds_without_roster} round(s) without roster capture — changes there are unmeasured
            </Lbl>
          )}
        </>
      )}
    </div>
  );
}

const PAGE = 200;

/** Newest first: date, then id — two evenings on one date keep their order
 *  by id, which is the only thing that tells them apart. */
export function sortNewestFirst(rows: readonly SessionSummary[]): SessionSummary[] {
  return [...rows].sort((a, b) => (a.date === b.date ? b.session_id - a.session_id : (a.date < b.date ? 1 : -1)));
}

/** 0/0 with an aggregate row present means NO map was attributed — a dash,
 *  not a claimed tie (Codex wave 2). */
function boxScore(row: SessionSummary): string {
  return row.team_1_score != null && row.team_2_score != null && row.team_1_score + row.team_2_score > 0
    ? `${row.team_1_score} / ${row.team_2_score}`
    : '—';
}

/** The day of the week the API's formatted date starts with ("Sunday, …"),
 *  kept short; the ISO date carries the rest. */
function weekday(row: SessionSummary): string {
  const first = row.formatted_date.split(',')[0]?.trim() ?? '';
  return first.length > 3 && !/\d/.test(first) ? first.slice(0, 3).toLowerCase() : '';
}

const thumbStyle = {
  width: 72, height: 40, objectFit: 'cover', display: 'block',
  filter: 'grayscale(1) contrast(1.1) brightness(0.6)', background: 'var(--color-ink-800)',
} as const;

export function SessionsList() {
  // The archive must never silently truncate: when a full page comes back,
  // a 'show older' control raises the limit (the endpoint supports
  // limit/offset; one growing limit keeps a single cache entry and no
  // stitching) — Codex on #811.
  const [limit, setLimit] = useState(PAGE);
  // One lineup strip open at a time — the strip is an instrument readout,
  // not an accordion wall.
  const [openLineup, setOpenLineup] = useState<number | null>(null);
  const sessions = useSessions(limit);
  const raw = sessions.isError ? undefined : sessions.data;
  const data = useMemo(() => (raw ? sortNewestFirst(raw) : undefined), [raw]);
  const maybeMore = data != null && data.length >= limit;
  const grid = '72px minmax(0,1fr) auto auto auto auto';
  return (
    <div style={{ paddingTop: 'var(--space-7)', paddingBottom: 'var(--space-7)', maxWidth: 960 }}>
      <Lbl>the evenings</Lbl>
      <h1 style={{ fontSize: 'var(--fs-title)', letterSpacing: '0.03em', textTransform: 'uppercase', margin: 'var(--space-3) 0 0', fontWeight: 500 }}>
        Every evening we played.
      </h1>
      <div data-parity="sessions.table" style={{ marginTop: 'var(--space-5)' }}>
        <SectionHead
          label={`newest first · ${data?.length ?? '…'} evenings`}
          aside={<span className="lbl">date · id</span>}
        />
        <div style={{ marginTop: 'var(--space-2)' }}>
          <div style={{ ...rowStyle, display: 'grid', gridTemplateColumns: grid, gap: 'var(--space-4)', padding: 'var(--space-2) 0' }}>
            <Lbl style={{ fontSize: 'var(--fs-caption)' }}>map</Lbl>
            <Lbl style={{ fontSize: 'var(--fs-caption)' }}>evening</Lbl>
            <Lbl style={{ fontSize: 'var(--fs-caption)' }}>rd</Lbl>
            <Lbl style={{ fontSize: 'var(--fs-caption)' }}>pl</Lbl>
            <Lbl style={{ fontSize: 'var(--fs-caption)' }}>kills</Lbl>
            <Lbl style={{ fontSize: 'var(--fs-caption)', textAlign: 'right' }}>box</Lbl>
          </div>
          {sessions.isPending && <div style={{ padding: 'var(--space-2) 0' }}><Pending label="sessions" /></div>}
          {sessions.isError && <div style={{ padding: 'var(--space-2) 0' }}><Unavailable what="sessions" /></div>}
          {data?.length === 0 && (
            <Absent block style={{ padding: 'var(--space-2) 0' }} reason="no sessions recorded yet" />
          )}
          {data?.map((row) => {
            const firstMap = row.maps_played[0] ?? null;
            const oddRounds = row.rounds % 2 === 1;
            return (
              <div key={row.session_id}>
                <Link
                  to={`/session-detail/${row.session_id}`}
                  style={{ ...rowStyle, display: 'grid', gridTemplateColumns: grid, gap: 'var(--space-4)', alignItems: 'center', padding: 'var(--space-2) 0', textDecoration: 'none', color: 'var(--color-text-100)' }}
                >
                  {firstMap
                    ? <img src={mapImageFor(firstMap)} alt={`${mapLabel(firstMap)} levelshot`} style={thumbStyle} loading="lazy" />
                    : <span role="img" style={{ ...thumbStyle, display: 'block' }} aria-label="no map recorded" />}
                  <span style={{ minWidth: 0, display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
                    <span style={{ fontSize: 'var(--fs-row)', letterSpacing: '0.04em', textTransform: 'uppercase', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      <span className="m">{row.date}</span>{weekday(row) && <> · {weekday(row)}</>} · <span className="m">#{row.session_id}</span>
                    </span>
                    <Meta>
                      {row.maps_played.length > 0 ? row.maps_played.map(mapLabel).join(' · ') : 'no maps recorded'}
                      {oddRounds && <> · <span style={{ color: 'var(--color-accent-warm)' }}>one half missing</span></>}
                    </Meta>
                  </span>
                  <span className="m" style={{ fontSize: 'var(--fs-small)', color: 'var(--color-text-400)' }}>{row.rounds}</span>
                  <span className="m" style={{ fontSize: 'var(--fs-small)', color: 'var(--color-text-400)' }}>{row.players}</span>
                  <span className="m" style={{ fontSize: 'var(--fs-small)', color: 'var(--color-text-400)' }}>{figure(row.total_kills)}</span>
                  <span className="m" style={{ fontSize: 'var(--fs-body)', minWidth: 58, textAlign: 'right' }}>{boxScore(row)}</span>
                </Link>
                <button
                  type="button"
                  onClick={() => { setOpenLineup((cur) => (cur === row.session_id ? null : row.session_id)); }}
                  style={{ ...lblStyle, fontSize: 'var(--fs-caption)', background: 'none', border: 'none', cursor: 'pointer', padding: '2px 0 6px', color: openLineup === row.session_id ? 'var(--color-text-200)' : 'var(--color-text-500)' }}
                >
                  lineup {openLineup === row.session_id ? '▴' : '▾'}
                </button>
                <LineupStrip sessionId={row.session_id} open={openLineup === row.session_id} />
              </div>
            );
          })}
        </div>
        {maybeMore && (
          <button
            type="button"
            onClick={() => setLimit((l) => l + PAGE)}
            style={{
              marginTop: 'var(--space-4)', fontSize: 'var(--fs-small)', letterSpacing: '0.08em', textTransform: 'uppercase',
              border: '1px solid var(--color-rule-700)', background: 'transparent',
              color: 'var(--color-text-300)', padding: 'var(--space-2) var(--space-3)', cursor: 'pointer',
            }}
          >
            show older evenings →
          </button>
        )}
        <Lbl style={{ fontSize: 'var(--fs-caption)', marginTop: 'var(--space-2)' }}>
          box = 2 points per map won, 1–1 on a draw · sides swap every map · one half missing = an odd round count
        </Lbl>
      </div>
    </div>
  );
}
