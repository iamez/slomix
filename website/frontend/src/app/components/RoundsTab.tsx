/**
 * The session page's Rounds tab (stats 2.0 R4, docs/design/18 §C plast 2):
 * the RoundsTable the retired /rounds page hosted, minus the session picker
 * the page needed and the session page does not — it already knows which
 * session it is on.
 *
 * The two views are the same data seen from two ends — `round` for "how did
 * that round go", `player` for "how am I doing" — the split the owner asked
 * for on the old page, kept here.
 */
import { useMemo, useState } from 'react';

import { Cluster, Stack } from './layout';
import { RoundsTable, type EmptyReason } from './RoundsTable';
import { Absent, Lbl, Pending, SectionHead, Unavailable } from './ui';
import { useRoundAwards } from '../lib/queries';
import type { SessionRounds } from '../lib/types';

/** ⛔ A DISABLED QUERY IS PENDING FOREVER IN REACT QUERY v5 — but on the
 *  session page the id is in the URL, so the query is never disabled and the
 *  three states are the whole story. */
export function roundsReason(rounds: { isPending: boolean; isError: boolean }): EmptyReason {
  if (rounds.isError) return 'unavailable';
  if (rounds.isPending) return 'loading';
  return 'no_data';
}

export function RoundsTab({ rounds, reason }: { rounds: SessionRounds | undefined; reason: EmptyReason }) {
  const [mode, setMode] = useState<'round' | 'player'>('round');
  const [guid, setGuid] = useState<string>('');
  // Which round's awards are open. The table has carried an `onSelectRound`
  // prop since it was written and nothing ever passed one — clicking a round
  // did nothing at all. This is that prop's first consumer.
  const [openRound, setOpenRound] = useState<number | null>(null);

  // Players present in this session, for the "one player" view.
  const players = useMemo(() => {
    const seen = new Map<string, string>();
    for (const round of rounds?.rounds ?? []) {
      for (const p of round.players) seen.set(p.player_guid, p.player_name);
    }
    return [...seen.entries()].sort((a, b) => a[1].localeCompare(b[1]));
  }, [rounds]);

  // ⛔ A saved selection must be re-checked against the roster. Keeping a
  // guid the roster does not contain leaves the selector showing a value no
  // option holds, while the table filters every row and reports "no rounds
  // match" for a session that is full of rounds.
  const knownGuid = players.some(([g]) => g === guid);
  const effectiveGuid = (knownGuid ? guid : players.at(0)?.[0]) ?? '';

  return (
    <Stack gap={3} parity="session.rounds">
      <SectionHead
        label="rounds"
        aside={rounds ? (
          <span className="lbl">
            {rounds.counted_rounds} of {rounds.total_rounds} count toward totals
          </span>
        ) : undefined}
      />

      <Cluster gap={3} align="baseline">
        <Lbl style={{ fontSize: 'var(--fs-caption)' }}>view</Lbl>
        <Cluster gap={2}>
          {(['round', 'player'] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => { setMode(m); }}
              aria-pressed={mode === m}
              style={{ all: 'unset', cursor: 'pointer',
                       fontSize: 'var(--fs-small)',
                       textTransform: 'uppercase', letterSpacing: '0.08em',
                       color: mode === m ? 'var(--color-text-100)'
                                         : 'var(--color-text-500)' }}
            >
              {m === 'round' ? 'by round' : 'one player'}
            </button>
          ))}
        </Cluster>

        {mode === 'player' && players.length > 0 ? (
          <select
            value={effectiveGuid}
            onChange={(e) => { setGuid(e.target.value); }}
            aria-label="player"
            style={{ background: 'transparent', color: 'var(--color-text-100)',
                     border: '1px solid var(--color-rule-900)',
                     padding: 'var(--space-2)', fontSize: 'var(--fs-small)' }}
          >
            {players.map(([g, name]) => (
              <option key={g} value={g}>{name}</option>
            ))}
          </select>
        ) : null}
      </Cluster>

      <RoundsTable
        rounds={rounds?.rounds ?? []}
        mode={mode}
        playerGuid={mode === 'player' ? effectiveGuid : undefined}
        emptyReason={reason}
        onSelectRound={(id) => { setOpenRound((cur) => (cur === id ? null : id)); }}
      />
      {openRound != null ? <RoundAwardsPanel roundId={openRound} /> : null}
      <Lbl style={{ fontSize: 'var(--fs-caption)' }}>
        every recorded round, the ones that do not count marked, not hidden
      </Lbl>
    </Stack>
  );
}

/**
 * Awards for one round, the breakdown behind the session's award summary.
 *
 * ⛔ THE EMPTY ANSWER IS THE COMMON ONE. Only 1016 of 3243 rounds carry any
 * award at all, so "this round has none" is what two visitors in three will
 * see. It is `Absent` with a reason, not a blank space — a page that shows
 * nothing without saying why reads as broken.
 *
 * ⚠️ `numeric` is deliberately not rendered. It exists for sorting and is
 * null whenever the figure is a rendered string; `value` is the display form
 * and is never null.
 */
export function RoundAwardsPanel({ roundId }: { roundId: number }) {
  const awards = useRoundAwards(roundId);
  const categories = Object.entries(awards.data?.categories ?? {});

  return (
    <Stack gap={2} parity="session.rounds.awards">
      <SectionHead label={`awards · round ${String(roundId)}`} />
      {awards.isPending ? <Pending label="awards" /> : null}
      {awards.isError ? <Unavailable what="awards" /> : null}
      {!awards.isPending && !awards.isError && categories.length === 0
        ? <Absent reason="no awards recorded for this round" />
        : null}
      {categories.map(([key, cat]) => (
        <Stack key={key} gap={1}>
          <Lbl style={{ fontSize: 'var(--fs-caption)' }}>
            {cat.emoji} {cat.name}
          </Lbl>
          {cat.awards.map((a, i) => (
            <Cluster key={`${a.award}-${String(i)}`} gap={2} align="baseline">
              <span style={{ fontSize: 'var(--fs-small)', color: 'var(--color-text-500)' }}>
                {a.award}
              </span>
              <span style={{ fontSize: 'var(--fs-small)', color: 'var(--color-text-100)' }}>
                {a.player}
              </span>
              <span style={{ fontSize: 'var(--fs-small)', color: 'var(--color-text-500)' }}>
                {a.value}
              </span>
            </Cluster>
          ))}
        </Stack>
      ))}
    </Stack>
  );
}
