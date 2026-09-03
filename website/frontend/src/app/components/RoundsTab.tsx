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
import { Lbl, SectionHead } from './ui';
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
      />
      <Lbl style={{ fontSize: 'var(--fs-caption)' }}>
        every recorded round, the ones that do not count marked, not hidden
      </Lbl>
    </Stack>
  );
}
