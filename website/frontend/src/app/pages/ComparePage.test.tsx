import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { COMPARE_ROWS, ComparePage, winner } from './ComparePage';
import profile from './__fixtures__/api_players_identifier_profile.json';
import type { PlayerProfile } from '../lib/types';

/** Two players out of one recording: B is A with a different guid and a
 *  lifetime scaled so every row has a definite winner. */
const A = profile as PlayerProfile;
const B: PlayerProfile = {
  ...A,
  guid: 'B0B0B0B0',
  identity: { ...A.identity, guid: 'B0B0B0B0', name: 'bee' },
  lifetime: {
    ...A.lifetime,
    kd: A.lifetime.kd * 0.5,
    kills: A.lifetime.kills + 100,
    win_rate: A.lifetime.win_rate + 5,
    rounds: A.lifetime.rounds - 1,
    time_played_seconds: A.lifetime.time_played_seconds * 2,   // played more: WINS the playtime row
    damage_given: A.lifetime.damage_given * 2,                 // …but with the same dpm → tie
  },
};

function fixtureFetch(input: RequestInfo | URL): Promise<Response> {
  const pathname = String(input).split('?')[0];
  const m = /\/api\/players\/([^/]+)\/profile$/.exec(pathname);
  if (m) {
    const body = m[1] === 'B0B0B0B0' ? B : A;
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);
  }
  return Promise.reject(new Error(`unexpected endpoint: ${pathname}`));
}

function testClient(): QueryClient {
  const client = makeQueryClient();
  client.setDefaultOptions({ queries: { retry: false } });
  return client;
}

function renderAt(url: string) {
  vi.stubGlobal('fetch', vi.fn(fixtureFetch));
  return render(
    <QueryClientProvider client={testClient()}>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/compare/:a?/:b?" element={<ComparePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('ComparePage', () => {
  afterEach(() => { vi.restoreAllMocks(); });

  it('asks for two players before it compares anything, and does not fetch', async () => {
    renderAt('/compare');
    expect(screen.getByText(/pick two players to compare/)).toBeInTheDocument();
    expect(screen.getByLabelText('player a')).toBeInTheDocument();
    renderAt(`/compare/${A.guid}`);
    expect(await screen.findByText(/pick the second player/)).toBeInTheDocument();
    expect(screen.getByLabelText('player b')).toBeInTheDocument();
  });

  it('renders the legacy six rows and colours the better side per row, more playtime wins', async () => {
    renderAt(`/compare/${A.guid}/B0B0B0B0`);
    await waitFor(() => expect(screen.getByText('bee')).toBeInTheDocument());
    const table = document.querySelector('[data-parity="compare.table"]')!;
    const rows = table.querySelectorAll('.row');
    expect(rows).toHaveLength(6);
    expect(COMPARE_ROWS.map((r) => r.label)).toEqual(['k:d', 'dpm', 'kills', 'win rate', 'rounds', 'played']);
    const winnersBySide = (row: Element) => Array.from(row.querySelectorAll('[data-wins="true"]')).length;
    // k:d — A (twice B's); dpm — tie (no winner); kills — B; win rate — B; rounds — A; played — B (more hours)
    expect(Array.from(rows).map(winnersBySide)).toEqual([1, 0, 1, 1, 1, 1]);
    // Owner, 2026-09-06: playtime is no longer scored lower-wins (legacy compare.js:69 had it
    // backwards), so no row carries the 'lower wins' note and the played winner is B.
    expect(rows[5].textContent).not.toMatch(/lower wins/);
    expect(rows[5].querySelector('[data-wins="true"]')?.textContent).toMatch(/h$/);
    expect(COMPARE_ROWS.every((r) => r.higherIsBetter)).toBe(true);
    expect(rows[1].querySelectorAll('[data-wins="true"]')).toHaveLength(0);
  });

  it('winner() reads the direction', () => {
    const higher = COMPARE_ROWS[0];
    const lower = { ...COMPARE_ROWS[5], higherIsBetter: false };
    expect(winner(higher, 2, 1)).toBe('a');
    expect(winner(higher, 1, 2)).toBe('b');
    expect(winner(lower, 2, 1)).toBe('b');
    expect(winner(higher, 1, 1)).toBeNull();
    expect(winner(higher, null, 1)).toBeNull();
  });

  it('says which player has no lifetime figures instead of showing zeros', async () => {
    const noLifetime = { ...B, lifetime: { ...B.lifetime, available: false } };
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const pathname = String(input).split('?')[0];
      if (pathname.endsWith('/B0B0B0B0/profile')) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(noLifetime) } as Response);
      }
      return fixtureFetch(input);
    }));
    render(
      <QueryClientProvider client={testClient()}>
        <MemoryRouter initialEntries={[`/compare/${A.guid}/B0B0B0B0`]}>
          <Routes><Route path="/compare/:a?/:b?" element={<ComparePage />} /></Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(await screen.findByText(/no lifetime figures for bee/)).toBeInTheDocument();
    expect(document.querySelectorAll('[data-parity="compare.table"] .row')).toHaveLength(0);
  });
});
