import { render, screen, waitFor } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { RoundsPage } from './RoundsPage';
import sessions from './__fixtures__/api_sessions.json';
import rounds from './__fixtures__/api_stats_session_gaming_session_id_rounds.json';

/** The one page of phases 1-4 without its own test (plan §2c) — until now it
 * was covered only through SessionDetail's use of RoundsTable, which says
 * nothing about THIS page's wiring: the session picker defaulting to the
 * newest session, the counted-of-recorded line, and the upstream-aware empty
 * reason. Rendered against recorded fixtures, the same discipline as every
 * other page test here. */

const FIXTURES = new Map<string, unknown>([
  ['/api/sessions', sessions],
  [
    `/api/stats/session/${(sessions as { session_id: number }[])[0].session_id}/rounds`,
    rounds,
  ],
]);

function fixtureFetch(input: RequestInfo | URL): Promise<Response> {
  const pathname = String(input).split('?')[0];
  const body = FIXTURES.get(pathname);
  if (body === undefined) {
    return Promise.reject(new Error(`RoundsPage called an unexpected endpoint: ${pathname}`));
  }
  return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);
}

function renderPage() {
  const client = makeQueryClient();
  client.setDefaultOptions({ queries: { retry: false } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <RoundsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('RoundsPage', () => {
  it('defaults to the newest session and reports counted-of-recorded honestly', async () => {
    vi.stubGlobal('fetch', vi.fn(fixtureFetch));
    renderPage();
    // The fixture has 17 counted of 18 recorded — the page must SAY the gap,
    // not silently render seventeen rows under an "18 rounds" claim.
    await waitFor(() =>
      expect(screen.getByText(/17 counted of 18 recorded/)).toBeInTheDocument(),
    );
    const picker = screen.getByLabelText('session') as HTMLSelectElement;
    expect(Number(picker.value)).toBe((sessions as { session_id: number }[])[0].session_id);
  });

  it('says the session LIST failed rather than loading rounds forever', async () => {
    // A disabled query is pending forever in React Query v5 — with no
    // session id, the rounds query never runs, and the page must attribute
    // the emptiness to the sessions list, not hang on "loading".
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve({
          ok: false,
          status: 503,
          json: () => Promise.resolve({}),
        } as Response),
      ),
    );
    renderPage();
    await waitFor(() => expect(screen.getByText('Could not load rounds.')).toBeInTheDocument());
  });

  it('renders an empty database as no sessions, not as a failure', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const pathname = String(input).split('?')[0];
        if (pathname === '/api/sessions') {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: () => Promise.resolve([]),
          } as Response);
        }
        return Promise.reject(new Error(`unexpected endpoint: ${pathname}`));
      }),
    );
    renderPage();
    // With zero sessions the rounds query must never fire (the fetch stub
    // rejects anything else), and the table has to say "no rounds", the
    // no_data reason — outage-reads-as-empty is the class this guards.
    await waitFor(() => expect(screen.getByText('No rounds recorded.')).toBeInTheDocument());
  });
});
