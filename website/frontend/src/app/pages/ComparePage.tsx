import { Link, useNavigate, useParams } from 'react-router';
import { Cluster, Stack } from '../components/layout';
import { PickPlayer } from '../components/PickPlayer';
import { Absent, Lbl, Pending, SectionHead, Unavailable, figure } from '../components/ui';
import { usePlayerProfile } from '../lib/queries';
import type { PlayerProfile } from '../lib/types';

/**
 * Compare two players (phase 7; legacy compare.js). The legacy was a modal
 * fed by name through /api/stats/player/<name>; this is a ROUTE with two
 * guids — shareable, and a guid is not ambiguous the way an alias is. The
 * numbers come from the same profile endpoint the profile page reads, so
 * the two never disagree.
 *
 * The six rows are the legacy six. Colour marks the better side and
 * nothing else (docs/design/03): green on the number that wins; playtime
 * reads "lower is better" like the legacy did — it is the price paid for
 * the other five, not a score.
 */
type Row = { label: string; value: (p: PlayerProfile) => number | null; format: (v: number) => string; higherIsBetter: boolean };

function dpmOf(p: PlayerProfile): number | null {
  const l = p.lifetime;
  if (!l.available || l.time_played_seconds <= 0) return null;
  return l.damage_given / (l.time_played_seconds / 60);
}

export const COMPARE_ROWS: Row[] = [
  { label: 'k:d', value: (p) => (p.lifetime.available ? p.lifetime.kd : null), format: (v) => v.toFixed(2), higherIsBetter: true },
  { label: 'dpm', value: dpmOf, format: (v) => v.toFixed(0), higherIsBetter: true },
  { label: 'kills', value: (p) => (p.lifetime.available ? p.lifetime.kills : null), format: figure, higherIsBetter: true },
  { label: 'win rate', value: (p) => (p.lifetime.available ? p.lifetime.win_rate : null), format: (v) => `${v.toFixed(1)}%`, higherIsBetter: true },
  { label: 'rounds', value: (p) => (p.lifetime.available ? p.lifetime.rounds : null), format: figure, higherIsBetter: true },
  // Legacy compare.js:69 scored playtime the other way (fewer hours won) and
  // painted it like k:d, so the table claimed the player who played LESS was
  // better. Owner, 2026-09-06: more time played wins; the direction flag stays
  // so a genuinely lower-is-better row can still be expressed.
  { label: 'played', value: (p) => (p.lifetime.available ? p.lifetime.time_played_seconds / 3600 : null), format: (v) => `${v.toFixed(1)} h`, higherIsBetter: true },
];

/** Which side wins a row: 'a', 'b', or null for a tie / missing value. */
export function winner(row: Row, a: number | null, b: number | null): 'a' | 'b' | null {
  if (a == null || b == null || a === b) return null;
  const aWins = row.higherIsBetter ? a > b : a < b;
  return aWins ? 'a' : 'b';
}

function nameOf(p: PlayerProfile | undefined, guid: string): string {
  return p?.identity.available && p.identity.name ? p.identity.name : guid;
}

function Side({ guid, p, align }: { guid: string; p: PlayerProfile | undefined; align: 'left' | 'right' }) {
  return (
    <div style={{ textAlign: align, minWidth: 0 }}>
      <Lbl>{align === 'left' ? 'a' : 'b'} · {guid}</Lbl>
      <Link to={`/profile/${encodeURIComponent(guid)}`} style={{ display: 'block', fontSize: 'var(--fs-title)', textTransform: 'uppercase', letterSpacing: '0.03em', color: 'var(--color-text-100)', textDecoration: 'none', marginTop: 'var(--space-1)' }}>
        {nameOf(p, guid)}
      </Link>
    </div>
  );
}

export function ComparePage() {
  const { a = '', b = '' } = useParams();
  const navigate = useNavigate();
  const pa = usePlayerProfile(a);
  const pb = usePlayerProfile(b);
  const both = a.length > 0 && b.length > 0;
  const go = (x: string, y: string) => { void navigate(`/compare/${encodeURIComponent(x)}${y ? `/${encodeURIComponent(y)}` : ''}`); };

  return (
    <Stack gap={5} style={{ paddingTop: 'var(--space-6)' }}>
      <SectionHead label="compare" aside={<span className="lbl">two players · lifetime · same source as the profile</span>} />
      <Cluster gap={6} align="start" parity="compare.pick" style={{ flexWrap: 'wrap' }}>
        {!a && <PickPlayer label="player a" parity="compare.pick-a" onPick={(g) => { go(g, b); }} />}
        {a && !b && <PickPlayer label="player b" parity="compare.pick-b" onPick={(g) => { go(a, g); }} />}
        {both && (
          <Lbl>
            <Link to={`/compare/${encodeURIComponent(a)}`} style={{ color: 'inherit' }}>change b</Link>
            {' · '}
            <Link to="/compare" style={{ color: 'inherit' }}>start over</Link>
          </Lbl>
        )}
      </Cluster>
      {!both && (
        <Absent block reason={a ? 'pick the second player' : 'pick two players to compare'} />
      )}
      {both && (
        <div data-parity="compare.table">
          <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', gap: 'var(--space-4)', alignItems: 'end', paddingBottom: 'var(--space-3)', borderBottom: '1px solid var(--color-rule-700)' }}>
            <Side guid={a} p={pa.data} align="left" />
            <Lbl>vs</Lbl>
            <Side guid={b} p={pb.data} align="right" />
          </div>
          {(pa.isPending || pb.isPending) && <Pending label="profiles" />}
          {(pa.isError || pb.isError) && <Unavailable what="profiles" />}
          {pa.data && pb.data && (
            !pa.data.lifetime.available || !pb.data.lifetime.available ? (
              <Absent block reason={`no lifetime figures for ${!pa.data.lifetime.available ? nameOf(pa.data, a) : nameOf(pb.data, b)}`} />
            ) : (
              <Stack gap={1} className="rows">
                {COMPARE_ROWS.map((row) => {
                  const va = row.value(pa.data);
                  const vb = row.value(pb.data);
                  const w = winner(row, va, vb);
                  const cell = (v: number | null, side: 'a' | 'b') => (
                    <span
                      className="m"
                      data-wins={w === side ? 'true' : undefined}
                      style={{ fontSize: 'var(--fs-row-lg)', color: w === side ? 'var(--color-pos)' : 'var(--color-text-100)' }}
                    >
                      {v == null ? '—' : row.format(v)}
                    </span>
                  );
                  return (
                    <div key={row.label} className="row" style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', gap: 'var(--space-4)', alignItems: 'baseline', padding: 'var(--space-2) 0', borderBottom: '1px solid var(--color-rule-800)' }}>
                      <div style={{ textAlign: 'left' }}>{cell(va, 'a')}</div>
                      <Lbl style={{ textAlign: 'center' }}>{row.label}{row.higherIsBetter ? '' : ' · lower wins'}</Lbl>
                      <div style={{ textAlign: 'right' }}>{cell(vb, 'b')}</div>
                    </div>
                  );
                })}
              </Stack>
            )
          )}
        </div>
      )}
    </Stack>
  );
}
