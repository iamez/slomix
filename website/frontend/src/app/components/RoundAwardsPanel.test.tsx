/**
 * Awards for one round — the breakdown behind the session award summary.
 *
 * ⛔ THE EMPTY ANSWER IS THE COMMON ONE. Measured on the dev database: only
 * 1016 of 3243 rounds carry any award at all. So "this round has none" is
 * what two visitors in three will see, and it is the state this file tests
 * first — a panel that renders nothing without saying why reads as broken.
 */
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { RoundAwardsPanel } from './RoundsTab';
import { makeQueryClient } from '../lib/queries';
import type { RoundAwards } from '../lib/types';
import recorded from '../pages/__fixtures__/api_rounds_round_id_awards.json';

// ⛔ THE HAND-WRITTEN TYPE IS CHECKED AGAINST A LIVE ANSWER, not only against
// fixtures I invented. A type built from a sample sees only the branches that
// sample happened to take; one built from a schema can be wrong in the other
// direction. This line makes a real recorded response the arbiter of the
// interface — 7 categories, 58 awards, taken from round 9831.
//
// ⚠️ It does NOT cover the nullable fields: this recording contains no null
// `guid` and no null `numeric`, because that round has none. A fixture cannot
// fail on a value it does not contain, which is why the constructed cases
// below carry both — and why they are not redundant with this one.
const live = recorded satisfies RoundAwards;

const withAwards: RoundAwards = {
  round_id: 4242,
  map_name: 'supply',
  round_number: 2,
  round_date: '2026-09-01T20:00:00',
  categories: {
    combat: {
      name: 'Combat', emoji: '💥',
      awards: [
        { award: 'Most Kills', player: 'someone', guid: 'AAAA1111', value: '31', numeric: 31 },
        // ⚠️ Both nullable fields at once: an award that never resolved to a
        // player AND whose figure is a rendered string. Typing `numeric` as
        // `number` once turned 3 rounds out of 40 into a 500.
        { award: 'Best Streak', player: 'nameless', guid: null, value: '7 in a row', numeric: null },
      ],
    },
  },
};

const noAwards: RoundAwards = {
  round_id: 77, map_name: null, round_number: null, round_date: null, categories: {},
};

function renderPanel(reply: () => Promise<Response>) {
  vi.spyOn(globalThis, 'fetch').mockImplementation(reply);
  const client = makeQueryClient();
  client.setDefaultOptions({ queries: { retry: false } });
  return render(
    <QueryClientProvider client={client}>
      <RoundAwardsPanel roundId={4242} />
    </QueryClientProvider>,
  );
}

const ok = (body: unknown) => () =>
  Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response);

describe('RoundAwardsPanel', () => {
  afterEach(() => { vi.restoreAllMocks(); });

  it('says why it is empty instead of showing a blank space', async () => {
    renderPanel(ok(noAwards));
    expect(await screen.findByText(/no awards recorded for this round/i)).toBeTruthy();
  });

  it('renders each category with its awards', async () => {
    renderPanel(ok(withAwards));
    expect(await screen.findByText(/Most Kills/)).toBeTruthy();
    expect(screen.getByText('someone')).toBeTruthy();
    expect(screen.getByText('31')).toBeTruthy();
  });

  it('renders an award with no guid and no numeric figure', async () => {
    renderPanel(ok(withAwards));
    // ⛔ The value, not the numeric: `value` is the display form and is never
    // null, while `numeric` exists for sorting and is frequently absent.
    expect(await screen.findByText('7 in a row')).toBeTruthy();
    expect(screen.getByText('nameless')).toBeTruthy();
  });

  it('renders a recorded live response end to end', async () => {
    renderPanel(ok(live));
    // 7 categories on round 9831; combat is the one every round has.
    expect(await screen.findByText(/Combat/)).toBeTruthy();
    // ⚠️ getAllByText, not getByText — and the reason is a data fact, not a
    // test convenience. Round 9831 carries TWO "Most damage given" awards
    // naming different players with different figures (bronze 4953,
    // SuperBoyy 3910), written eleven minutes apart by two separate imports.
    // 282 such groups exist. The panel shows both because both are in the
    // table; deciding which is right is not a rendering question.
    expect(screen.getAllByText('Most damage given').length).toBeGreaterThan(0);
  });

  it('reports a failed request as unavailable, not as empty', async () => {
    renderPanel(() => Promise.resolve({ ok: false, status: 500 } as Response));
    await waitFor(() => {
      expect(screen.getByText(/awards: unavailable/i)).toBeTruthy();
    });
    expect(screen.queryByText(/no awards recorded/i)).toBeNull();
  });
});
