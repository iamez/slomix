import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { API_PROBES } from '../lib/probes';
import { About } from './About';
import overview from './__fixtures__/api_stats_overview.json';
import build from './__fixtures__/api_build.json';
import systemOverview from './__fixtures__/api_system_overview.json';
import access from './__fixtures__/api_availability_access.json';
import diagnostics from './__fixtures__/api_diagnostics.json';

/**
 * Rendered against RECORDED responses. The About page is the widest consumer
 * on the site — figures, build identity, health AND twelve probes — so the
 * fetch stub whitelists exactly those endpoints and fails loudly on any
 * other call.
 */

const DATA = new Map<string, unknown>([
  ['/api/stats/overview', overview],
  ['/api/build', build],
  ['/api/system/overview', systemOverview],
  // Anonymous access: the diagnostics panel must not even ask.
  ['/api/availability/access', access],
]);
const PROBE_PATHS = new Set(API_PROBES.map((p) => p.endpoint.split('?')[0]));

function fixtureFetch(input: RequestInfo | URL): Promise<Response> {
  const pathname = String(input).split('?')[0];
  const body = DATA.get(pathname);
  if (body !== undefined) {
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);
  }
  if (PROBE_PATHS.has(pathname)) {
    // Probes only read ok/status — an empty body is faithful enough.
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) } as Response);
  }
  return Promise.reject(new Error(`About called an unexpected endpoint: ${pathname}`));
}

function testClient(): QueryClient {
  const client = makeQueryClient();
  client.setDefaultOptions({ queries: { retry: false } });
  return client;
}

function renderPage() {
  return render(
    <QueryClientProvider client={testClient()}>
      <MemoryRouter>
        <About />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('About', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders the prose with LIVE figures, build identity, health and probes', async () => {
    vi.stubGlobal('fetch', vi.fn(fixtureFetch));
    renderPage();

    expect(screen.getByRole('heading', { level: 1 }).textContent).toMatch(/keeps the record/i);

    // O6: headline figures come from /api/stats/overview, never the README —
    // 1,948 rounds and 67 players are the RECORDED truth (the prototype
    // hardcoded 2,987, which counts R0 summary rows).
    await waitFor(() => expect(screen.getAllByText('1,948').length).toBeGreaterThan(0));
    // 67 appears in both the headline grid and the counted grid.
    expect(screen.getAllByText('67').length).toBeGreaterThan(0);
    expect(screen.queryByText('2,987')).not.toBeInTheDocument();

    // The four stopwatch problems and the pipeline, verbatim from the prototype.
    expect(screen.getByText('Round 2 is cumulative — but not entirely')).toBeInTheDocument();
    expect(screen.getByText('A session is not a date')).toBeInTheDocument();
    expect(screen.getAllByText(/six checks/i).length).toBeGreaterThan(0);

    // This build — live from /api/build (recorded by hand, not in the corpus).
    expect(await screen.findByText('0f1a48e2')).toBeInTheDocument();
    expect(screen.getByText('077_player_aim_summary')).toBeInTheDocument();

    // Health rows reuse the system overview stages.
    expect(await screen.findByText('Lua capture')).toBeInTheDocument();

    // Probes: every row fires a real GET; the stub answers 200.
    expect(screen.getByText('Recent Matches')).toBeInTheDocument();
    await waitFor(() => expect(screen.getAllByText(/200 · \d+ ms/).length).toBe(API_PROBES.length));
  });

  it('marks failed probes without taking the page down', async () => {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const pathname = String(input).split('?')[0];
      if (pathname === '/api/stats/records') {
        return Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) } as Response);
      }
      return fixtureFetch(input);
    }));
    renderPage();
    await waitFor(() => expect(screen.getAllByText(/200 · \d+ ms/).length).toBe(API_PROBES.length - 1));
    expect(screen.getByText('500')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
  });

  it('says unavailable for figures and build when those endpoints fail', async () => {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const pathname = String(input).split('?')[0];
      if (pathname === '/api/stats/overview' || pathname === '/api/build') {
        return Promise.resolve({ ok: false, status: 503, json: () => Promise.resolve({}) } as Response);
      }
      return fixtureFetch(input);
    }));
    renderPage();
    await waitFor(() => expect(screen.getByText(/figures: unavailable/)).toBeInTheDocument());
    expect(await screen.findByText(/build info: unavailable/)).toBeInTheDocument();
  });

  it('shows the backend diagnostics only to an admin, and asks for them only then', async () => {
    const calls: string[] = [];
    const adminFetch = (input: RequestInfo | URL): Promise<Response> => {
      const pathname = String(input).split('?')[0];
      calls.push(pathname);
      if (pathname === '/api/availability/access') {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ ...access, authenticated: true, is_admin: true }) } as Response);
      }
      if (pathname === '/api/diagnostics') {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(diagnostics) } as Response);
      }
      return fixtureFetch(input);
    };
    vi.stubGlobal('fetch', vi.fn(adminFetch));
    renderPage();
    // The recording: eight tables, none missing, no issues.
    await waitFor(() => expect(screen.getByText('player_comprehensive_stats')).toBeInTheDocument());
    expect(screen.getByText('lua_round_teams')).toBeInTheDocument();
    expect(screen.getByText(/all systems go/)).toBeInTheDocument();
    expect(screen.getByText(/database connected/)).toBeInTheDocument();
    expect(calls.filter((c) => c === '/api/diagnostics')).toHaveLength(1);
  });

  it('does not request diagnostics for an anonymous visitor', async () => {
    const calls: string[] = [];
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      calls.push(String(input).split('?')[0]);
      return fixtureFetch(input);
    }));
    renderPage();
    await waitFor(() => expect(calls).toContain('/api/availability/access'));
    await new Promise((r) => setTimeout(r, 50));
    expect(calls).not.toContain('/api/diagnostics');
    expect(screen.queryByText(/backend diagnostics/)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// The degraded report (carried over from the closed #911, 2026-09-06). The
// fixture is CONSTRUCTED from the handler's branches and says so in its own
// `_note`: a healthy database cannot produce a permission-denied table or an
// empty time block, and a fixture cannot fail on a value it does not contain.

import degraded from './__fixtures__/api_diagnostics_degraded.json';

function adminFetchWith(diagBody: unknown, diagStatus = 200) {
  return (input: RequestInfo | URL): Promise<Response> => {
    const pathname = String(input).split('?')[0];
    if (pathname === '/api/availability/access') {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ ...access, authenticated: true, is_admin: true }) } as Response);
    }
    if (pathname === '/api/diagnostics') {
      return Promise.resolve({ ok: diagStatus < 400, status: diagStatus, json: () => Promise.resolve(diagBody) } as Response);
    }
    return fixtureFetch(input);
  };
}

describe('About — diagnostics panel, degraded states', () => {
  afterEach(() => { vi.restoreAllMocks(); });

  it('says why a table has no count instead of printing zero, and keeps a real zero', async () => {
    vi.stubGlobal('fetch', vi.fn(adminFetchWith(degraded)));
    renderPage();
    await waitFor(() => expect(screen.getByText('player_comprehensive_stats')).toBeInTheDocument());
    // once as the table's reason, once inside the handler's own time warning
    expect(screen.getAllByText(/permission denied for table player_comprehensive_stats/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/relation "processed_files" does not exist/)).toBeInTheDocument();
    // the table's reason and the handler's own issue line both carry it
    expect(screen.getAllByText(/connection to server was lost/).length).toBeGreaterThanOrEqual(1);
    // gaming_sessions really has 0 rows — that is a count, not an absence
    expect(screen.getByText('0 rows')).toBeInTheDocument();
    expect(screen.getByText(/2 issues/)).toBeInTheDocument();
  });

  it('reports an empty time block as a query that did not run', async () => {
    vi.stubGlobal('fetch', vi.fn(adminFetchWith(degraded)));
    renderPage();
    await waitFor(() => expect(screen.getByText(/the timing query did not run/)).toBeInTheDocument());
    expect(screen.queryByText('dead time, as stored')).toBeNull();
  });

  it('shows a monitoring table that failed as unavailable, not as zero rows', async () => {
    vi.stubGlobal('fetch', vi.fn(adminFetchWith(degraded)));
    renderPage();
    await waitFor(() => expect(screen.getByText(/query failed: unavailable/)).toBeInTheDocument());
    // the payload literally carries count: 0 for voice; the panel must not say so
    expect(screen.queryByText(/voice 0 rows/)).toBeNull();
    expect(screen.getByText(/8,831 rows/)).toBeInTheDocument();
    expect(screen.getByText(/adapter has no pool_stats/)).toBeInTheDocument();
  });

  it('renders the recorded healthy report with the time and pool sections', async () => {
    vi.stubGlobal('fetch', vi.fn(adminFetchWith(diagnostics)));
    renderPage();
    await waitFor(() => expect(screen.getByText('dead time, as stored')).toBeInTheDocument());
    expect(screen.getByText(/all systems go/)).toBeInTheDocument();
    expect(screen.getByText(/in use, .* idle of/)).toBeInTheDocument();
  });

  it('tells an admin whose session ended to sign in again, and a 403 that the endpoint disagrees', async () => {
    vi.stubGlobal('fetch', vi.fn(adminFetchWith({ detail: 'Authentication required' }, 401)));
    renderPage();
    await waitFor(() => expect(screen.getByText(/the session ended between the access check/)).toBeInTheDocument());
    expect(screen.queryByText(/diagnostics: unavailable/)).toBeNull();
    vi.restoreAllMocks();
    vi.stubGlobal('fetch', vi.fn(adminFetchWith({ detail: 'Admin privileges required' }, 403)));
    renderPage();
    await waitFor(() => expect(screen.getByText(/does not count this account as an admin/)).toBeInTheDocument());
  });

  it('still reports a real failure as a failure', async () => {
    vi.stubGlobal('fetch', vi.fn(adminFetchWith({ detail: 'boom' }, 500)));
    renderPage();
    await waitFor(() => expect(screen.getByText(/diagnostics: unavailable/)).toBeInTheDocument());
  });
});
