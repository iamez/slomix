/**
 * Phase 7 — head to head (route `compare`).
 *
 * Legacy opens this as a modal with two text inputs (compare.js:11-33), fills
 * the first from the profile you came from, and renders six rows with a trophy
 * on the better side. Here it is a PAGE, the same convention docs/design/12
 * applies to the story details modal and to upload-detail.
 *
 * ⭐ The two names live in the URL (`?a=&b=`), which is the thing a modal
 * could not do: a comparison becomes a link you can paste. Legacy's state
 * died with the overlay.
 */
import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { Cluster, Stack } from '../components/layout';
import { Absent, Lbl, Meta, Pending, SectionHead, Unavailable, figure } from '../components/ui';
import { usePlayerIdentity } from '../lib/queries';
import type { PlayerIdentity } from '../lib/types';

type Stats = PlayerIdentity['stats'];

/** The six rows legacy compares (compare.js:63-70), in its order.
 *
 * ⛔ ONE DELIBERATE DIVERGENCE, and it is a defect fix, not a redesign.
 * Legacy gives Playtime `higherIsBetter: false`, so the trophy goes to
 * whoever played LESS — displayed identically to K/D, where the trophy means
 * "better". As shown, that is a false claim: 205h next to 40h with the badge
 * on 40h reads as "40 hours is the better number", which nobody means. Hours
 * played is context for every row above it, not a contest of its own, so it
 * keeps its place and loses its trophy. Flagged to the owner rather than
 * silently mirrored OR silently dropped.
 */
const ROWS: {
  label: string;
  pick: (s: Stats) => number;
  fmt?: (v: number) => string;
  contest: boolean;
}[] = [
  { label: 'K/D ratio', pick: (s) => s.kd, fmt: (v) => v.toFixed(2), contest: true },
  { label: 'DPM', pick: (s) => s.dpm, contest: true },
  { label: 'total kills', pick: (s) => s.kills, contest: true },
  { label: 'win rate', pick: (s) => s.win_rate, fmt: (v) => `${v}%`, contest: true },
  { label: 'games played', pick: (s) => s.games, contest: true },
  { label: 'playtime', pick: (s) => s.playtime_hours, fmt: (v) => `${v}h`, contest: false },
];

// The house input, copied from AvailabilityPage rather than invented: the
// same border token, the same scale. My first draft used `--color-rule-1`,
// which does not exist (the scale is 400-900), and a raw `2px 0` padding that
// pushed the hand-typed-size ratchet from 26 to 27. Both were caught by
// tokens.test.ts, which is what it is for.
const inputStyle = {
  background: 'transparent', border: '1px solid var(--color-rule-700)', color: 'var(--color-text-100)',
  fontSize: 'var(--fs-row)', padding: '0 var(--space-1)', width: 160,
} as const;
const actionStyle = {
  all: 'unset' as const, cursor: 'pointer', fontSize: 'var(--fs-caption)',
  letterSpacing: '0.06em', textTransform: 'uppercase' as const, color: 'var(--color-accent)',
};

function Side({ name, q }: { name: string; q: ReturnType<typeof usePlayerIdentity> }) {
  if (q.isPending) return <Pending label={name} />;
  // ⛔ A name nobody has is a 404 here, and a 404 is a STATE: "no player by
  // that name" is what the reader needs, not "unavailable".
  if (q.isError) return <Absent reason={`no player called "${name}"`} />;
  return <Meta>{q.data?.name ?? name} · {figure(q.data?.stats.games ?? 0)} games</Meta>;
}

export function ComparePage() {
  const [params, setParams] = useSearchParams();
  const a = params.get('a') ?? '';
  const b = params.get('b') ?? '';
  const [draftA, setDraftA] = useState(a);
  const [draftB, setDraftB] = useState(b);
  // The URL is the source of truth: a pasted link, or the browser's back
  // button, must move the fields too.
  useEffect(() => { setDraftA(a); setDraftB(b); }, [a, b]);

  const qa = usePlayerIdentity(a || null);
  const qb = usePlayerIdentity(b || null);
  const sa = qa.data?.stats;
  const sb = qb.data?.stats;
  const both = sa != null && sb != null;

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const next = new URLSearchParams();
    if (draftA.trim()) next.set('a', draftA.trim());
    if (draftB.trim()) next.set('b', draftB.trim());
    setParams(next);
  };

  return (
    <Stack gap={6} style={{ paddingTop: 'var(--space-7)' }}>
      <Stack gap={2}>
        <Lbl>compare · head to head</Lbl>
        <h1 style={{ fontSize: 'var(--fs-title)', letterSpacing: 'var(--track-title)', textTransform: 'uppercase', margin: 'var(--space-3) 0 0', fontWeight: 500 }}>
          two players, one column each
        </h1>
      </Stack>

      <form onSubmit={submit} data-parity="compare.form">
        <Cluster gap={4} align="baseline" style={{ flexWrap: 'wrap' }}>
          <input aria-label="first player" value={draftA} style={inputStyle}
            onChange={(e) => setDraftA(e.target.value)} placeholder="player" />
          <Lbl>vs</Lbl>
          <input aria-label="second player" value={draftB} style={inputStyle}
            onChange={(e) => setDraftB(e.target.value)} placeholder="player" />
          <button type="submit" style={actionStyle}>compare →</button>
        </Cluster>
      </form>

      {(a === '' || b === '') && (
        <Absent block reason="name two players — the comparison lives in the URL, so you can paste the link" />
      )}

      {a !== '' && b !== '' && (
        <div data-parity="compare.results">
          <SectionHead label={`${a} vs ${b}`} />
          <Cluster gap={5} justify="between" align="baseline" style={{ marginTop: 'var(--space-2)', flexWrap: 'wrap' }}>
            <Side name={a} q={qa} />
            <Side name={b} q={qb} />
          </Cluster>

          {(qa.isError || qb.isError) && !both && (
            <div style={{ marginTop: 'var(--space-3)' }}>
              <Absent reason="both names have to resolve before there is anything to compare" />
            </div>
          )}
          {(qa.isPending || qb.isPending) && <Pending label="the comparison" />}

          {both && (
            <Stack gap={1} className="rows" style={{ marginTop: 'var(--space-3)' }}>
              {ROWS.map((r) => {
                const va = r.pick(sa);
                const vb = r.pick(sb);
                const fmt = r.fmt ?? ((v: number) => figure(v));
                const winA = r.contest && va > vb;
                const winB = r.contest && vb > va;
                const strong = { color: 'var(--color-pos)' };
                return (
                  <Cluster key={r.label} gap={4} justify="between" align="baseline" className="row" style={{ padding: 'var(--space-2) 0' }}>
                    <span className="m" style={{ fontSize: 'var(--fs-row)', ...(winA ? strong : {}) }}>
                      {fmt(va)}{winA && ' ◂'}
                    </span>
                    <Lbl>{r.label}</Lbl>
                    <span className="m" style={{ fontSize: 'var(--fs-row)', ...(winB ? strong : {}) }}>
                      {winB && '▸ '}{fmt(vb)}
                    </span>
                  </Cluster>
                );
              })}
            </Stack>
          )}
          {both && <Meta>playtime is context, not a contest — it carries no marker</Meta>}
          {both && (
            <Cluster gap={4} style={{ marginTop: 'var(--space-3)' }}>
              <Link to={`/profile/${qa.data?.guid ?? ''}`} style={actionStyle}>{a}&rsquo;s profile →</Link>
              <Link to={`/profile/${qb.data?.guid ?? ''}`} style={actionStyle}>{b}&rsquo;s profile →</Link>
            </Cluster>
          )}
        </div>
      )}
      {qa.isError && qb.isError && <Unavailable what="both players" />}
    </Stack>
  );
}
