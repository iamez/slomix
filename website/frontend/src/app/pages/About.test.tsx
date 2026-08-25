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
});
