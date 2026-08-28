/**
 * ⛔ THE TABLE'S JOB IS TO SHOW WHAT THE ROUND RECORDED — INCLUDING THAT A
 * ROUND DOES NOT COUNT.
 *
 * `/stats/session/{id}/detail` filters cancelled rounds out and says nothing,
 * so the player who played one has nowhere to learn why it is missing. This
 * component must not repeat that: it shows the round AND marks it.
 */
import { render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { RoundsTable, mmss } from './RoundsTable';
import type { RoundPlayerRow, SessionRound } from '../lib/types';

function player(over: Partial<RoundPlayerRow> = {}): RoundPlayerRow {
  return {
    player_guid: 'AAA', player_name: 'one', team: 1,
    time_played_seconds: 222, gibs: 3, damage_received: 1204,
    damage_given: 1510, kills: 8, deaths: 3, headshots: 12,
    headshot_kills: 2, revives_given: 1, times_revived: 0, xp: 55,
    ...over,
  };
}

function round(over: Partial<SessionRound> = {}): SessionRound {
  return {
    round_id: 1, map_name: 'supply', round_number: 1,
    played_at: '2026-08-26 21:09:58', duration_seconds: 454,
    end_reason: 'SURRENDER', round_status: 'completed',
    counts_toward_totals: true, match_id: 'm1',
    players: [player()],
    ...over,
  };
}

describe('the three fields nothing else surfaces per round', () => {
  it('shows time played, gibs and damage taken by default', () => {
    render(<RoundsTable rounds={[round()]} mode="round" />);
    expect(screen.getByText('played')).toBeTruthy();
    expect(screen.getByText('gibs')).toBeTruthy();
    expect(screen.getByText('taken')).toBeTruthy();
    // and their values, not just the headers
    expect(screen.getByText('3:42')).toBeTruthy();       // 222 s
    expect(screen.getByText('1,204')).toBeTruthy();      // damage taken
  });

  it('does not put them behind a toggle', () => {
    const { container } = render(<RoundsTable rounds={[round()]} mode="round" />);
    expect(container.querySelectorAll('button[aria-expanded]').length).toBe(0);
  });
});

describe('a round that does not count', () => {
  const excluded = round({ counts_toward_totals: false, round_status: 'cancelled' });

  it('is still rendered', () => {
    const { container } = render(<RoundsTable rounds={[excluded]} mode="round" />);
    expect(container.querySelector('[data-round-id="1"]')).toBeTruthy();
    expect(screen.getByText('one')).toBeTruthy();
  });

  it('is marked, so the reader is not left to guess', () => {
    const { container } = render(<RoundsTable rounds={[excluded]} mode="round" />);
    expect(container.querySelector('[data-excluded]')).toBeTruthy();
    expect(screen.getByText(/not counted/i)).toBeTruthy();
  });

  it('is not marked when it does count', () => {
    const { container } = render(<RoundsTable rounds={[round()]} mode="round" />);
    expect(container.querySelector('[data-excluded]')).toBeNull();
  });
});

describe('emptiness has a reason', () => {
  it.each([
    ['no_data', /no rounds recorded/i],
    ['unavailable', /could not load/i],
    ['loading', /loading/i],
    ['filtered', /no rounds match/i],
  ] as const)('%s reads differently', (reason, pattern) => {
    render(<RoundsTable rounds={[]} mode="round" emptyReason={reason} />);
    expect(screen.getByText(pattern)).toBeTruthy();
  });

  it('never renders an empty table that looks like zero rounds', () => {
    const { container } = render(<RoundsTable rounds={[]} mode="round" />);
    expect(container.querySelector('table')).toBeNull();
  });
});

describe('player mode', () => {
  const two = [
    round({ round_id: 1, players: [player(), player({ player_guid: 'BBB', player_name: 'two' })] }),
    round({ round_id: 2, map_name: 'brewdog',
            players: [player({ player_guid: 'BBB', player_name: 'two', gibs: 9 })] }),
  ];

  it('keeps only the chosen player and every round they played', () => {
    render(<RoundsTable rounds={two} mode="player" playerGuid="BBB" />);
    expect(screen.getByText(/supply R1/)).toBeTruthy();
    expect(screen.getByText(/brewdog R1/)).toBeTruthy();
    expect(screen.getByText('9')).toBeTruthy();
    expect(screen.queryByText('one')).toBeNull();
  });

  it('says the filter emptied it rather than claiming no data', () => {
    render(<RoundsTable rounds={two} mode="player" playerGuid="NOBODY" />);
    expect(screen.getByText(/no rounds match/i)).toBeTruthy();
  });

  it('calls back with the round id when a round is chosen', () => {
    const onSelect = vi.fn();
    render(<RoundsTable rounds={two} mode="player" playerGuid="BBB"
                        onSelectRound={onSelect} />);
    screen.getByText(/brewdog R1/).click();
    expect(onSelect).toHaveBeenCalledWith(2);
  });
});

describe('columns', () => {
  it('narrows to the requested set', () => {
    const { container } = render(
      <RoundsTable rounds={[round()]} mode="round" columns={['gibs', 'kills']} />,
    );
    const thead = container.querySelector('thead');
    expect(thead).not.toBeNull();
    const head = within(thead as HTMLElement);
    expect(head.getByText('gibs')).toBeTruthy();
    expect(head.queryByText('taken')).toBeNull();
  });
});

describe('it owns look, not placement', () => {
  it('writes no margin of its own', () => {
    // The owner reworks layout repeatedly; a component that sets its own outer
    // spacing has to be hunted through on every pass.
    const { container } = render(<RoundsTable rounds={[round()]} mode="round" />);
    const withMargin = [...container.querySelectorAll<HTMLElement>('*')].filter(
      (el) => el.style.margin || el.style.marginTop || el.style.marginBottom,
    );
    expect(withMargin.map((e) => e.tagName)).toEqual([]);
  });

  it('spaces from the scale, never a raw pixel literal', () => {
    const { container } = render(<RoundsTable rounds={[round()]} mode="round" />);
    const gaps = [...container.querySelectorAll<HTMLElement>('*')]
      .map((el) => el.style.gap)
      .filter(Boolean);
    expect(gaps.length).toBeGreaterThan(0);
    expect(gaps.every((g) => g.startsWith('var(--space-'))).toBe(true);
  });
});

describe('mmss', () => {
  it('formats seconds as a clock', () => {
    expect(mmss(0)).toBe('0:00');
    expect(mmss(59)).toBe('0:59');
    expect(mmss(222)).toBe('3:42');
    expect(mmss(647)).toBe('10:47');
  });

  it('does not invent a time for a non-number', () => {
    expect(mmss(Number.NaN)).toBe('—');
  });
});


describe('the review round', () => {
  it('a stale player selection does not survive a session change', () => {
    // Selecting someone in session A and switching to session B, where that
    // guid is absent, used to leave the table filtering every row and
    // reporting "no rounds match" for a session full of rounds.
    const sessionB = [round({ players: [player({ player_guid: 'ONLY_HERE' })] })];
    render(<RoundsTable rounds={sessionB} mode="player" playerGuid="FROM_SESSION_A" />);
    expect(screen.getByText(/no rounds match/i)).toBeTruthy();
    // …which is why the PAGE must re-resolve the guid; the table's job is only
    // to say that the filter, not the data, is what emptied it.
  });

  it('reports the filter, never "no data", when rounds exist', () => {
    const { container } = render(
      <RoundsTable rounds={[round()]} mode="player" playerGuid="NOBODY" />,
    );
    expect(container.querySelector('[data-empty="filtered"]')).toBeTruthy();
    expect(container.querySelector('[data-empty="no_data"]')).toBeNull();
  });
});
