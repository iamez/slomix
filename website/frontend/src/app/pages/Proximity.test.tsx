import { render, screen, waitFor } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { Proximity } from './Proximity';
import type { ProximityLeaderboard } from '../lib/types';
import boardJson from './__fixtures__/api_proximity_leaderboards.json';

// `satisfies` makes the compiler hold the RECORDED fixture against the
// declared wire type — this is what caught attribution.mode being a string
// while the type only allowed numeric extensions (CodeRabbit on #856).
const board = boardJson satisfies ProximityLeaderboard;

/** Rendered against the RECORDED power board (10 entries, attribution
 * block, formula_version) — every asserted string is something the backend
 * really said on 31. 8. */

function fetchFor(bodyByPath: Map<string, unknown>) {
  return (input: RequestInfo | URL): Promise<Response> => {
    const pathname = String(input).split('?')[0];
    const body = bodyByPath.get(pathname);
    if (body === undefined) {
      return Promise.reject(new Error(`Proximity called an unexpected endpoint: ${pathname}`));
    }
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);
  };
}

function renderPage() {
  const client = makeQueryClient();
  client.setDefaultOptions({ queries: { retry: false } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Proximity />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('Proximity', () => {
  it('opens on the power board with the attribution the wire sent', async () => {
    vi.stubGlobal('fetch', vi.fn(fetchFor(new Map([['/api/proximity/leaderboards', board]]))));
    renderPage();
    const first = (board as { entries: { name: string }[] }).entries[0];
    // The recorded first entry, colour codes stripped.
    await waitFor(() =>
      expect(screen.getByText(first.name.replace(/\^[0-9A-Za-z]/g, ''))).toBeInTheDocument(),
    );
    // The attribution block is the board's own honesty statement — it must
    // survive the render, not just the wire.
    expect(screen.getByText(/source rows linkable/)).toBeInTheDocument();
  });

  it('names all ten boards, so none can be lost at build time', () => {
    vi.stubGlobal('fetch', vi.fn(fetchFor(new Map([['/api/proximity/leaderboards', board]]))));
    renderPage();
    for (const label of [
      'power rating', 'spawn timing', 'crossfire', 'trade kills', 'reactions',
      'survivors', 'movement', 'focus fire', 'krogt', 'comp skill',
    ]) {
      expect(screen.getByRole('tab', { name: label })).toBeInTheDocument();
    }
  });

  it('renders an empty window as a reasoned absence, not a blank board', async () => {
    vi.stubGlobal('fetch', vi.fn(fetchFor(new Map([
      ['/api/proximity/leaderboards', { status: 'ok', category: 'power', entries: [] }],
    ]))));
    renderPage();
    await waitFor(() =>
      expect(screen.getByText(/proximity capture only covers sessions where the tracker ran/)).toBeInTheDocument(),
    );
  });

  it('treats a 200 with status:error as a failure, not as data', async () => {
    // The endpoint's own answer for an unknown category — recorded live:
    // {"status":"error","detail":"Unknown category: …"} with HTTP 200.
    vi.stubGlobal('fetch', vi.fn(fetchFor(new Map([
      ['/api/proximity/leaderboards', { status: 'error', detail: 'Unknown category: nonsense', entries: [] }],
    ]))));
    renderPage();
    await waitFor(() => expect(screen.getByText(/leaderboard: unavailable/)).toBeInTheDocument());
  });
});
