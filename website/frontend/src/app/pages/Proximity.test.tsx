import { render, screen, waitFor } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { Proximity } from './Proximity';
import type { ProximityLeaderboard } from '../lib/types';
import boardJson from './__fixtures__/api_proximity_leaderboards.json';
import scopes from './__fixtures__/api_proximity_scopes.json';
import quality from './__fixtures__/api_proximity_quality.json';
import spawnTiming from './__fixtures__/api_proximity_spawn_timing.json';
import aimLock from './__fixtures__/api_proximity_aim_lock.json';
import cohesion from './__fixtures__/api_proximity_cohesion.json';
import crossfireAngles from './__fixtures__/api_proximity_crossfire_angles.json';
import pushes from './__fixtures__/api_proximity_pushes.json';
import luaTrades from './__fixtures__/api_proximity_lua_trades.json';
import revives from './__fixtures__/api_proximity_revives.json';
import focusFire from './__fixtures__/api_proximity_focus_fire.json';
import supportSummary from './__fixtures__/api_proximity_support_summary.json';
import combatPositions from './__fixtures__/api_proximity_combat_position_stats.json';
import classes from './__fixtures__/api_proximity_classes.json';
import reactions from './__fixtures__/api_proximity_reactions.json';

const INSTRUMENTS = new Map<string, unknown>([
  ['/api/proximity/scopes', scopes],
  ['/api/proximity/quality', quality],
  ['/api/proximity/spawn-timing', spawnTiming],
  ['/api/proximity/aim-lock', aimLock],
  ['/api/proximity/cohesion', cohesion],
  ['/api/proximity/crossfire-angles', crossfireAngles],
  ['/api/proximity/pushes', pushes],
  ['/api/proximity/lua-trades', luaTrades],
  ['/api/proximity/revives', revives],
  ['/api/proximity/focus-fire', focusFire],
  ['/api/proximity/support-summary', supportSummary],
  ['/api/proximity/combat-position-stats', combatPositions],
  ['/api/proximity/classes', classes],
  ['/api/proximity/reactions', reactions],
]);

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
    const body = bodyByPath.get(pathname) ?? INSTRUMENTS.get(pathname);
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

  it('renders the instruments against the recorded scope, quality band first', async () => {
    vi.stubGlobal('fetch', vi.fn(fetchFor(new Map([['/api/proximity/leaderboards', board]]))));
    renderPage();
    // The data-completeness band is the truth strip the design asks for —
    // it must render the per-source chips, correlation completeness, and
    // the recorded scope's numbers, not a generic 'ok'.
    await waitFor(() => expect(screen.getByText(/correlation 99\.1%/)).toBeInTheDocument());
    // One leader from each of two instruments, colour codes stripped —
    // both values the backend really said.
    const spawnLeader = (spawnTiming as { leaders: { name: string }[] }).leaders[0];
    await waitFor(() =>
      expect(screen.getAllByText(spawnLeader.name.replace(/\^[0-9A-Za-z]/g, '')).length).toBeGreaterThan(0),
    );
    // Crossfire duos carry partner_name HERE (the field legacy tried to
    // read off the leaderboards endpoint, which never sent it).
    expect(screen.getByText(/kanii \+ bronze/)).toBeInTheDocument();
  });

  it('scopes the instruments to the newest CAPTURE date by default', async () => {
    const fetchSpy = vi.fn(fetchFor(new Map([['/api/proximity/leaderboards', board]])));
    vi.stubGlobal('fetch', fetchSpy);
    renderPage();
    await waitFor(() => expect(screen.getByText(/correlation/)).toBeInTheDocument());
    const newest = (scopes as { sessions: { session_date: string }[] }).sessions[0].session_date;
    const instrumentCalls = fetchSpy.mock.calls
      .map((c) => String(c[0]))
      .filter((u) => u.includes('/api/proximity/') && !u.includes('leaderboards') && !u.includes('scopes'));
    expect(instrumentCalls.length).toBeGreaterThan(0);
    for (const u of instrumentCalls) {
      // ⛔ Unscoped instruments measured up to 1.9 s cold — the first
      // paint must NEVER be the unbounded window.
      expect(u, `unscoped instrument call: ${u}`).toContain(`session_date=${newest}`);
    }
  });

  it('mounts nothing unscoped when the scope lookup fails', async () => {
    // Three reviewers independently: a failed /proximity/scopes must not
    // fall through into thirteen unbounded instrument queries.
    const fetchSpy = vi.fn((input: RequestInfo | URL) => {
      const pathname = String(input).split('?')[0];
      if (pathname === '/api/proximity/scopes') {
        return Promise.resolve({ ok: false, status: 503, json: () => Promise.resolve({}) } as Response);
      }
      const body = new Map([['/api/proximity/leaderboards', board as unknown]]).get(pathname) ?? INSTRUMENTS.get(pathname);
      if (body === undefined) return Promise.reject(new Error(`unexpected: ${pathname}`));
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);
    });
    vi.stubGlobal('fetch', fetchSpy);
    renderPage();
    await waitFor(() => expect(screen.getByText(/capture dates: unavailable/)).toBeInTheDocument());
    const instrumentCalls = fetchSpy.mock.calls
      .map((c) => String(c[0]))
      .filter((u) => u.includes('/api/proximity/') && !u.includes('leaderboards') && !u.includes('scopes'));
    expect(instrumentCalls).toEqual([]);
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
