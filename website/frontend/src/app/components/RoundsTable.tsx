/**
 * One round's stats, laid out so a person can read them.
 *
 * ⛔ WHAT THIS EXISTS FOR. A round row carries 39 populated numeric fields, and
 * until now the site showed 13 of them per round — omitting exactly the three
 * a player asks about first: time played, gibs, and damage TAKEN. Those were
 * answerable nowhere in a browser. They are in the default column set here,
 * not behind a toggle.
 *
 * ⛔ NO MARGIN, NO RAW NUMBERS. The owner intends to rework layout and buttons
 * repeatedly, so this component owns its LOOK and nothing about its PLACEMENT:
 * spacing to whatever sits next to it is the parent's business. Sizes come
 * from the `--space-*` / `--fs-*` scale rather than literals, which is also
 * what the ratchet in `tokens.test.ts` enforces.
 *
 * The `var(--space-N, fallback)` form is deliberate: the scale lands in a
 * separate PR, and a CSS variable that does not exist yet resolves to nothing
 * — which is how `--color-ink-800` painted 22 boxes transparent. A fallback
 * makes this correct before AND after that PR merges.
 */
import type { ReactNode } from 'react';

import type { RoundPlayerRow, SessionRound } from '../lib/types';

const SPACE = {
  1: 'var(--space-1, 4px)',
  2: 'var(--space-2, 8px)',
  3: 'var(--space-3, 12px)',
  4: 'var(--space-4, 16px)',
  5: 'var(--space-5, 22px)',
} as const;

const FS = {
  micro: 'var(--fs-1, 9px)',
  small: 'var(--fs-3, 12px)',
  body: 'var(--fs-4, 13px)',
} as const;

/** Columns, in the order they read. `key` doubles as the field name. */
export const ROUND_COLUMNS = [
  { key: 'time_played_seconds', label: 'played', format: mmss },
  { key: 'gibs', label: 'gibs' },
  { key: 'damage_received', label: 'taken' },
  { key: 'damage_given', label: 'given' },
  { key: 'kills', label: 'k' },
  { key: 'deaths', label: 'd' },
  { key: 'headshot_kills', label: 'hs' },
  { key: 'revives_given', label: 'rev' },
] as const satisfies readonly {
  key: keyof RoundPlayerRow;
  label: string;
  format?: (value: number) => string;
}[];

export type RoundColumnKey = (typeof ROUND_COLUMNS)[number]['key'];

export function mmss(seconds: number): string {
  if (!Number.isFinite(seconds)) return '—';
  const whole = Math.round(seconds);
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, '0')}`;
}

/** Why a table is empty. ⛔ An empty list and an unanswered question have the
 *  same shape; the reader must be able to tell them apart. */
export type EmptyReason = 'no_data' | 'unavailable' | 'loading' | 'filtered';

/** ⛔ A Map, not an object index. `Record<K, V>` types the lookup as always
 *  present, so `EMPTY_TEXT[reason]` reads as `string` even for a key that is
 *  not there — the same shape that lets a bad key reach the DOM as
 *  `undefined`. A Map makes the miss visible to the type system. */
const EMPTY_TEXT = new Map<EmptyReason, string>([
  ['no_data', 'No rounds recorded.'],
  ['unavailable', 'Could not load rounds.'],
  ['loading', 'Loading rounds…'],
  ['filtered', 'No rounds match this filter.'],
]);

function Cell({ children, muted }: { children: ReactNode; muted?: boolean }) {
  return (
    <td
      style={{
        padding: `${SPACE[1]} ${SPACE[2]}`,
        textAlign: 'right',
        fontVariantNumeric: 'tabular-nums',
        color: muted ? 'var(--color-text-400)' : 'var(--color-text-100)',
        fontSize: FS.body,
      }}
    >
      {children}
    </td>
  );
}

function HeadRow({ columns }: { columns: readonly typeof ROUND_COLUMNS[number][] }) {
  return (
    <tr>
      <th style={{ textAlign: 'left', padding: `${SPACE[1]} ${SPACE[2]}`,
                   fontSize: FS.micro, letterSpacing: '0.08em',
                   textTransform: 'uppercase', color: 'var(--color-text-500)',
                   fontWeight: 400 }}>
        player
      </th>
      {columns.map((c) => (
        <th
          key={c.key}
          style={{ textAlign: 'right', padding: `${SPACE[1]} ${SPACE[2]}`,
                   fontSize: FS.micro, letterSpacing: '0.08em',
                   textTransform: 'uppercase', color: 'var(--color-text-500)',
                   fontWeight: 400 }}
        >
          {c.label}
        </th>
      ))}
    </tr>
  );
}

function PlayerRows({
  players,
  columns,
  highlightGuid,
}: {
  players: readonly RoundPlayerRow[];
  columns: readonly typeof ROUND_COLUMNS[number][];
  highlightGuid?: string;
}) {
  return (
    <>
      {players.map((p) => {
        const mine = highlightGuid != null && p.player_guid === highlightGuid;
        return (
          <tr
            key={p.player_guid}
            data-highlighted={mine || undefined}
            style={{ borderTop: '1px solid var(--color-rule-900, #1b1b1b)' }}
          >
            <td style={{ padding: `${SPACE[1]} ${SPACE[2]}`, fontSize: FS.body,
                         color: mine ? 'var(--color-accent, #d8a657)'
                                     : 'var(--color-text-100)' }}>
              {p.player_name}
            </td>
            {columns.map((c) => {
              const raw = p[c.key];
              const value = typeof raw === 'number' ? raw : 0;
              return (
                <Cell key={c.key}>
                  {'format' in c ? c.format(value) : value.toLocaleString()}
                </Cell>
              );
            })}
          </tr>
        );
      })}
    </>
  );
}

function RoundHeading({ round }: { round: SessionRound }) {
  const excluded = !round.counts_toward_totals;
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', gap: SPACE[2],
                  flexWrap: 'wrap' }}>
      <span style={{ fontSize: FS.body, color: 'var(--color-text-100)' }}>
        {round.map_name}
      </span>
      <span style={{ fontSize: FS.micro, letterSpacing: '0.08em',
                     textTransform: 'uppercase', color: 'var(--color-text-500)' }}>
        R{round.round_number}
      </span>
      <span style={{ fontSize: FS.small, color: 'var(--color-text-400)',
                     fontVariantNumeric: 'tabular-nums' }}>
        {round.duration_seconds == null ? 'duration unknown' : mmss(round.duration_seconds)}
      </span>
      {round.end_reason ? (
        <span style={{ fontSize: FS.micro, color: 'var(--color-text-500)',
                       textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          {round.end_reason}
        </span>
      ) : null}
      {excluded ? (
        // ⛔ Say it, do not hide the round. The session endpoint drops these
        // silently, which leaves the player who played one with no way to
        // learn why it is missing.
        <span
          data-excluded="true"
          style={{ fontSize: FS.micro, letterSpacing: '0.08em',
                   textTransform: 'uppercase',
                   color: 'var(--color-accent-warm, #c98a4b)' }}
        >
          {round.round_status ?? 'excluded'} · not counted
        </span>
      ) : null}
    </div>
  );
}

export interface RoundsTableProps {
  rounds: readonly SessionRound[];
  /** `round` groups by round and lists players; `player` lists one player's
   *  rounds as rows. */
  mode: 'round' | 'player';
  /** Required in `player` mode: whose rounds these are. */
  playerGuid?: string;
  /** Shown instead of the table when `rounds` is empty. Absence of data and a
   *  failure to fetch it must not look alike. */
  emptyReason?: EmptyReason;
  /** Narrow the default set; order follows ROUND_COLUMNS regardless. */
  columns?: readonly RoundColumnKey[];
  onSelectRound?: (roundId: number) => void;
}

export function RoundsTable({
  rounds,
  mode,
  playerGuid,
  emptyReason = 'no_data',
  columns,
  onSelectRound,
}: RoundsTableProps) {
  const cols = columns
    ? ROUND_COLUMNS.filter((c) => columns.includes(c.key))
    : ROUND_COLUMNS;

  if (rounds.length === 0) {
    return (
      <p data-empty={emptyReason}
         style={{ fontSize: FS.small, color: 'var(--color-text-400)' }}>
        {EMPTY_TEXT.get(emptyReason)}
      </p>
    );
  }

  if (mode === 'player') {
    const rows = rounds
      .map((r) => ({ round: r, row: r.players.find((p) => p.player_guid === playerGuid) }))
      .filter((x): x is { round: SessionRound; row: RoundPlayerRow } => x.row != null);

    if (rows.length === 0) {
      return (
        <p data-empty="filtered"
           style={{ fontSize: FS.small, color: 'var(--color-text-400)' }}>
          {EMPTY_TEXT.get('filtered')}
        </p>
      );
    }

    return (
      <div style={{ overflowX: 'auto' }}>
        <table style={{ borderCollapse: 'collapse', width: '100%' }}>
          <thead>
            <tr>
              <th style={{ textAlign: 'left', padding: `${SPACE[1]} ${SPACE[2]}`,
                           fontSize: FS.micro, letterSpacing: '0.08em',
                           textTransform: 'uppercase',
                           color: 'var(--color-text-500)', fontWeight: 400 }}>
                round
              </th>
              {cols.map((c) => (
                <th key={c.key}
                    style={{ textAlign: 'right', padding: `${SPACE[1]} ${SPACE[2]}`,
                             fontSize: FS.micro, letterSpacing: '0.08em',
                             textTransform: 'uppercase',
                             color: 'var(--color-text-500)', fontWeight: 400 }}>
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(({ round, row }) => (
              <tr key={round.round_id}
                  data-excluded={!round.counts_toward_totals || undefined}
                  style={{ borderTop: '1px solid var(--color-rule-900, #1b1b1b)' }}>
                <td style={{ padding: `${SPACE[1]} ${SPACE[2]}`, fontSize: FS.body }}>
                  <button
                    type="button"
                    onClick={onSelectRound ? () => { onSelectRound(round.round_id); } : undefined}
                    disabled={!onSelectRound}
                    style={{ all: 'unset', cursor: onSelectRound ? 'pointer' : 'default',
                             color: 'var(--color-text-100)' }}
                  >
                    {round.map_name} R{round.round_number}
                  </button>
                  {!round.counts_toward_totals ? (
                    <span style={{ fontSize: FS.micro, marginInlineStart: SPACE[2],
                                   textTransform: 'uppercase', letterSpacing: '0.08em',
                                   color: 'var(--color-accent-warm, #c98a4b)' }}>
                      not counted
                    </span>
                  ) : null}
                </td>
                {cols.map((c) => {
                  const raw = row[c.key];
                  const value = typeof raw === 'number' ? raw : 0;
                  return (
                    <Cell key={c.key} muted={!round.counts_toward_totals}>
                      {'format' in c ? c.format(value) : value.toLocaleString()}
                    </Cell>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <div style={{ display: 'grid', gap: SPACE[5] }}>
      {rounds.map((round) => (
        <section key={round.round_id} data-round-id={round.round_id}
                 data-excluded={!round.counts_toward_totals || undefined}>
          <div style={{ display: 'grid', gap: SPACE[2] }}>
            <RoundHeading round={round} />
            <div style={{ overflowX: 'auto' }}>
              <table style={{ borderCollapse: 'collapse', width: '100%' }}>
                <thead>
                  <HeadRow columns={cols} />
                </thead>
                <tbody>
                  <PlayerRows players={round.players} columns={cols}
                              highlightGuid={playerGuid} />
                </tbody>
              </table>
            </div>
          </div>
        </section>
      ))}
    </div>
  );
}
