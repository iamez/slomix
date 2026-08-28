/**
 * Rounds — one session, round by round, with the numbers a player asks about.
 *
 * ⛔ WHY A ROUTE OF ITS OWN. The natural homes for this are the profile (phase
 * 3) and session-detail (phase 4), both still stubs in another workstream.
 * Waiting for them would leave the data unreachable in a browser for weeks;
 * building them here would collide. So the page is thin and the table is a
 * component: when those phases land, they mount `RoundsTable` and this route
 * can go.
 *
 * The two views are the same data seen from two ends — `round` for "how did
 * that round go", `player` for "how am I doing" — which is the split the owner
 * asked for.
 */
import { useMemo, useState } from 'react';

import { RoundsTable, type EmptyReason } from '../components/RoundsTable';
import { Lbl, SectionHead } from '../components/ui';
import { useSessionRounds, useSessions } from '../lib/queries';

const SPACE = {
  2: 'var(--space-2, 8px)',
  3: 'var(--space-3, 12px)',
  5: 'var(--space-5, 22px)',
  7: 'var(--space-7, 40px)',
} as const;

/** ⛔ A DISABLED QUERY IS PENDING FOREVER IN REACT QUERY v5.
 *
 * `useSessionRounds(null)` never runs, so `isPending` stays true — and reading
 * only the rounds query would render "Loading rounds…" indefinitely when the
 * real story is that the session LIST failed, or that there are no sessions at
 * all. The upstream state has to be part of the answer.
 */
function reasonFor(
  rounds: { isPending: boolean; isError: boolean },
  sessions: { isPending: boolean; isError: boolean },
  haveSession: boolean,
): EmptyReason {
  if (sessions.isError) return 'unavailable';
  if (sessions.isPending) return 'loading';
  if (!haveSession) return 'no_data';
  if (rounds.isError) return 'unavailable';
  if (rounds.isPending) return 'loading';
  return 'no_data';
}

export function RoundsPage() {
  const sessions = useSessions(30);
  const [picked, setPicked] = useState<number | null>(null);
  const [mode, setMode] = useState<'round' | 'player'>('round');
  const [guid, setGuid] = useState<string>('');

  const sessionList = sessions.data ?? [];
  const sessionId = picked ?? sessionList.at(0)?.session_id ?? null;
  const rounds = useSessionRounds(sessionId);
  const data = rounds.isError ? undefined : rounds.data;

  // Players present in this session, for the "one player" view.
  const players = useMemo(() => {
    const seen = new Map<string, string>();
    for (const round of data?.rounds ?? []) {
      for (const p of round.players) seen.set(p.player_guid, p.player_name);
    }
    return [...seen.entries()].sort((a, b) => a[1].localeCompare(b[1]));
  }, [data]);

  // ⛔ A saved selection must be re-checked against the NEW session. Keeping
  // a guid that this session's roster does not contain leaves the selector
  // showing a value no option holds, while the table filters every row and
  // reports "no rounds match" for a session that is full of rounds.
  const knownGuid = players.some(([g]) => g === guid);
  const effectiveGuid = (knownGuid ? guid : players.at(0)?.[0]) ?? '';

  return (
    <div style={{ paddingTop: SPACE[7], paddingBottom: SPACE[7], maxWidth: 1100 }}>
      <Lbl>rounds · one session, half by half</Lbl>
      <h1 style={{ fontSize: 'var(--fs-9, 34px)', letterSpacing: '0.03em',
                   textTransform: 'uppercase', marginBlock: `${SPACE[3]} 0`, fontWeight: 500 }}>
        Every round, not just the totals.
      </h1>
      <p style={{ color: 'var(--color-text-400)', maxWidth: '46em',
                  fontSize: 'var(--fs-4, 13px)' }}>
        Time played, gibs and damage taken per round — the three the rest of the
        site reports only as session totals. Rounds that do not count toward
        those totals are shown here and marked, not hidden.
      </p>

      <div style={{ display: 'flex', alignItems: 'baseline', gap: SPACE[3],
                    flexWrap: 'wrap', marginTop: SPACE[5] }}>
        <Lbl style={{ fontSize: 'var(--fs-1, 9px)' }}>session</Lbl>
        <select
          value={sessionId ?? ''}
          onChange={(e) => { setPicked(Number(e.target.value)); setGuid(''); }}
          aria-label="session"
          style={{ background: 'transparent', color: 'var(--color-text-100)',
                   border: '1px solid var(--color-rule-900, #1b1b1b)',
                   padding: SPACE[2], fontSize: 'var(--fs-3, 12px)' }}
        >
          {sessionList.map((s) => (
            <option key={s.session_id} value={s.session_id}>
              {s.date} · {s.rounds} rounds
            </option>
          ))}
        </select>

        <Lbl style={{ fontSize: 'var(--fs-1, 9px)' }}>view</Lbl>
        <div style={{ display: 'flex', gap: SPACE[2] }}>
          {(['round', 'player'] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => { setMode(m); }}
              aria-pressed={mode === m}
              style={{ all: 'unset', cursor: 'pointer',
                       fontSize: 'var(--fs-3, 12px)',
                       textTransform: 'uppercase', letterSpacing: '0.08em',
                       color: mode === m ? 'var(--color-text-100)'
                                         : 'var(--color-text-500)' }}
            >
              {m === 'round' ? 'by round' : 'one player'}
            </button>
          ))}
        </div>

        {mode === 'player' && players.length > 0 ? (
          <select
            value={effectiveGuid}
            onChange={(e) => { setGuid(e.target.value); }}
            aria-label="player"
            style={{ background: 'transparent', color: 'var(--color-text-100)',
                     border: '1px solid var(--color-rule-900, #1b1b1b)',
                     padding: SPACE[2], fontSize: 'var(--fs-3, 12px)' }}
          >
            {players.map(([g, name]) => (
              <option key={g} value={g}>{name}</option>
            ))}
          </select>
        ) : null}
      </div>

      {data ? (
        <p style={{ color: 'var(--color-text-400)', fontSize: 'var(--fs-3, 12px)',
                    marginTop: SPACE[3] }}>
          {data.counted_rounds === data.total_rounds
            ? `${data.total_rounds} rounds`
            : `${data.counted_rounds} counted of ${data.total_rounds} recorded`}
          {data.session_date ? ` · ${data.session_date}` : ''}
        </p>
      ) : null}

      <div style={{ marginTop: SPACE[5] }}>
        <SectionHead label={mode === 'round' ? 'by round' : 'one player'} />
        <div style={{ marginTop: SPACE[3] }}>
          <RoundsTable
            rounds={data?.rounds ?? []}
            mode={mode}
            playerGuid={mode === 'player' ? effectiveGuid : undefined}
            emptyReason={reasonFor(rounds, sessions, sessionId != null)}
          />
        </div>
      </div>
    </div>
  );
}
