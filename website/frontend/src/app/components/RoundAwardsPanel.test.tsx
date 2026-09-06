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

  it('reports a failed request as unavailable, not as empty', async () => {
    renderPanel(() => Promise.resolve({ ok: false, status: 500 } as Response));
    await waitFor(() => {
      expect(screen.getByText(/awards: unavailable/i)).toBeTruthy();
    });
    expect(screen.queryByText(/no awards recorded/i)).toBeNull();
  });
});
