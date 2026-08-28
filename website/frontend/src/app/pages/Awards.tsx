import { useState } from 'react';
import { Link } from 'react-router';
import { useAwards, useAwardsLeaderboard } from '../lib/queries';
import type { AwardRow } from '../lib/types';
import { Chip, Lbl, lblStyle, Pending, rowStyle, SectionHead, Unavailable } from '../components/ui';

/**
 * Awards (docs/design/12 row 11) — legacy awards.js carried over: two tabs
 * (by round / by player), an award-type filter and a days filter, round
 * cards grouped client-side, leaderboard table.
 *
 * Legacy bugs deliberately NOT carried: the dead /api/awards?limit=1 init
 * call; the favorite_award/top_award mismatch that left the dropdown with
 * only its hardcoded list (here the type list comes from the leaderboard's
 * real top_award values, plus the legacy twelve as the floor); rank is the
 * API's own, not index+1.
 *
 * Grouping stays by (date, map, round_number) — the legacy key — because
 * award rows can carry a null round_id; the crack (a midnight-crossing
 * round split by date) is inherited and documented rather than hidden.
 */

const LEGACY_TYPES = [
  'Best K/D ratio', 'Best accuracy', 'First blood', 'Most damage given',
  'Most deaths', 'Most dynamite defused', 'Most dynamite planted',
  'Most gibs', 'Most headshots', 'Most kills', 'Most revives', 'Most selfkills',
];

const DAY_CHOICES: { key: number | null; label: string }[] = [
  { key: 7, label: '7 days' },
  { key: 30, label: '30 days' },
  { key: 90, label: '90 days' },
  { key: null, label: 'All time' },
];


function roundKey(a: AwardRow): string {
  return `${a.date}-${a.map}-${a.round_number}`;
}

function ByRound({ days, awardType }: { days: number | null; awardType: string | null }) {
  const [page, setPage] = useState(0);
  const awards = useAwards(page, days, awardType);
  const data = awards.isError ? undefined : awards.data;
  const groups = new Map<string, AwardRow[]>();
  for (const row of data?.awards ?? []) {
    const key = roundKey(row);
    const list = groups.get(key);
    if (list) list.push(row);
    else groups.set(key, [row]);
  }
  const pages = data ? Math.ceil(data.total / data.limit) : 0;
  return (
    <div data-parity="awards.by-round">
      <SectionHead
        label={`${data?.total?.toLocaleString('en-US') ?? '…'} awards`}
        aside={pages > 1
          ? <span className="m" style={{ ...lblStyle, fontSize: 9 }}>page {page + 1} / {pages}</span>
          : undefined}
      />
      {awards.isPending && <div style={{ marginTop: 12 }}><Pending label="awards" /></div>}
      {awards.isError && <div style={{ marginTop: 12 }}><Unavailable what="awards" /></div>}
      {data?.awards.length === 0 && (
        <div className="m" style={{ fontSize: 11, color: 'var(--color-text-500)', marginTop: 12 }}>
          no awards found for this selection
        </div>
      )}
      {[...groups.entries()].map(([key, rows]) => (
        <div key={key} style={{ marginTop: 16, border: '1px solid var(--color-rule-700)', background: 'var(--color-ink-800)', padding: 14 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 15, letterSpacing: '0.04em', textTransform: 'uppercase' }}>{rows[0].map}</span>
            {/* The endpoint paginates ROWS, so a big round can straddle
              * pages — the caption counts what is SHOWN, never claims the
              * round's total (Codex on #813). */}
            <span className="m" style={{ ...lblStyle, fontSize: 9 }}>
              round {rows[0].round_number} · {rows[0].date} · {rows.length} shown
            </span>
          </div>
          <div className="home-cols3" style={{ gap: 10, marginTop: 10 }}>
            {rows.map((a, i) => (
              <div key={`${a.award}-${i}`} style={{ ...rowStyle, padding: '6px 0' }}>
                <Lbl style={{ fontSize: 9 }}>{a.award.toLowerCase()}</Lbl>
                <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 10 }}>
                  <span className="m" style={{ fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.player}</span>
                  <span className="m" style={{ fontSize: 11, color: 'var(--color-text-400)', flex: 'none' }}>{a.value}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
      {pages > 1 && (
        <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
          {/* Boundary controls disable instead of silently clamping. */}
          <button
            type="button"
            disabled={page === 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            style={{ fontSize: 12, letterSpacing: '0.08em', textTransform: 'uppercase', border: '1px solid var(--color-rule-700)', background: 'transparent', color: page === 0 ? '#454340' : 'var(--color-text-400)', padding: '4px 9px', cursor: page === 0 ? 'default' : 'pointer' }}
          >
            ← newer
          </button>
          <button
            type="button"
            disabled={page >= pages - 1}
            onClick={() => setPage((p) => Math.min(pages - 1, p + 1))}
            style={{ fontSize: 12, letterSpacing: '0.08em', textTransform: 'uppercase', border: '1px solid var(--color-rule-700)', background: 'transparent', color: page >= pages - 1 ? '#454340' : 'var(--color-text-400)', padding: '4px 9px', cursor: page >= pages - 1 ? 'default' : 'pointer' }}
          >
            older →
          </button>
        </div>
      )}
    </div>
  );
}

function ByPlayer({ days, awardType }: { days: number | null; awardType: string | null }) {
  const board = useAwardsLeaderboard(days, awardType);
  const data = board.isError ? undefined : board.data;
  return (
    <div data-parity="awards.by-player">
      <SectionHead label={`${data?.leaderboard.length ?? '…'} players`} />
      <div style={{ marginTop: 8 }}>
        <div style={{ ...rowStyle, display: 'grid', gridTemplateColumns: '34px minmax(0,1fr) auto minmax(0,1fr)', gap: 14, padding: '6px 0' }}>
          <Lbl style={{ fontSize: 9 }}>#</Lbl>
          <Lbl style={{ fontSize: 9 }}>player</Lbl>
          <Lbl style={{ fontSize: 9, textAlign: 'right' }}>awards</Lbl>
          <Lbl style={{ fontSize: 9 }}>most won</Lbl>
        </div>
        {board.isPending && <div style={{ padding: '10px 0' }}><Pending label="leaderboard" /></div>}
        {board.isError && <div style={{ padding: '10px 0' }}><Unavailable what="leaderboard" /></div>}
        {data?.leaderboard.length === 0 && (
          <div className="m" style={{ fontSize: 11, color: 'var(--color-text-500)', padding: '10px 0' }}>
            no player awards found for this selection
          </div>
        )}
        {data?.leaderboard.map((row) => {
          const inner = (<>
            <span className="m" style={{ ...lblStyle, fontSize: 10 }}>{String(row.rank).padStart(2, '0')}</span>
            <span className="m" style={{ fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{row.player}</span>
            <span className="m" style={{ fontSize: 13, textAlign: 'right' }}>{row.award_count.toLocaleString('en-US')}</span>
            <span className="m" style={{ fontSize: 11, color: 'var(--color-text-400)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {row.top_award.toLowerCase()} ({row.top_award_count}×)
            </span>
          </>);
          const style = { ...rowStyle, display: 'grid', gridTemplateColumns: '34px minmax(0,1fr) auto minmax(0,1fr)', gap: 14, alignItems: 'baseline', padding: '9px 0', textDecoration: 'none', color: 'var(--color-text-100)' } as const;
          // A null guid is a historical winner neither alias map resolves —
          // a row, not a /profile/null link (Codex on #813).
          return row.guid
            ? <Link key={row.guid} to={`/profile/${row.guid}`} style={style}>{inner}</Link>
            : <div key={`${row.rank}-${row.player}`} style={style}>{inner}</div>;
        })}
      </div>
    </div>
  );
}

export function Awards() {
  const [tab, setTab] = useState<'round' | 'player'>('round');
  // Legacy default: last 30 days.
  const [days, setDays] = useState<number | null>(30);
  const [awardType, setAwardType] = useState<string | null>(null);
  // The dropdown lists REAL award names from every source this page has:
  // the legacy twelve as the floor, the leaderboard's top_award values, and
  // the award names on the first unfiltered awards page — top_award alone
  // cannot enumerate types nobody tops (Codex on #813). Full enumeration
  // needs a backend types endpoint; noted for the response_model batch.
  const allBoard = useAwardsLeaderboard(null, null);
  const firstPage = useAwards(0, null, null);
  const types = [...new Set([
    ...LEGACY_TYPES,
    ...(allBoard.data?.leaderboard.map((r) => r.top_award) ?? []),
    ...(firstPage.data?.awards.map((a) => a.award) ?? []),
  ])].sort();
  return (
    <div style={{ paddingTop: 44, paddingBottom: 40, maxWidth: 980 }}>
      <Lbl>awards · round awards from endgame stats</Lbl>
      <h1 style={{ fontSize: 34, letterSpacing: '0.03em', textTransform: 'uppercase', margin: '12px 0 0', fontWeight: 500 }}>
        Who took what home.
      </h1>
      <div style={{ display: 'flex', gap: 8, marginTop: 18, flexWrap: 'wrap' }}>
        <Chip active={tab === 'round'} label="By round" onClick={() => setTab('round')} />
        <Chip active={tab === 'player'} label="By player" onClick={() => setTab('player')} />
        <span style={{ width: 12 }} />
        {DAY_CHOICES.map((d) => (
          <Chip key={String(d.key)} active={days === d.key} label={d.label} onClick={() => setDays(d.key)} />
        ))}
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, marginTop: 10 }}>
        <Lbl style={{ fontSize: 9 }}>award</Lbl>
        <select
          value={awardType ?? ''}
          onChange={(e) => setAwardType(e.target.value || null)}
          aria-label="Award type"
          className="m"
          style={{ background: 'var(--color-ink-800)', color: 'var(--color-text-100)', border: '1px solid var(--color-rule-700)', fontSize: 13, padding: '6px 10px', maxWidth: 320 }}
        >
          <option value="">all awards</option>
          {types.map((name) => <option key={name} value={name}>{name}</option>)}
        </select>
      </div>
      <div style={{ marginTop: 20 }}>
        {/* key remounts ByRound when filters change, so its page state
          * resets — a narrower result must never inherit an out-of-range
          * offset (Codex on #813). */}
        {tab === 'round'
          ? <ByRound key={`${days ?? 'all'}:${awardType ?? 'all'}`} days={days} awardType={awardType} />
          : <ByPlayer days={days} awardType={awardType} />}
      </div>
    </div>
  );
}
