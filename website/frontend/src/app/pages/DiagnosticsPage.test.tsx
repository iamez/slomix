import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { DiagnosticsPage } from './DiagnosticsPage';
import healthy from './__fixtures__/api_diagnostics.json';
import degraded from './__fixtures__/api_diagnostics_degraded.json';

/**
 * Two fixtures on purpose. `api_diagnostics.json` is RECORDED from the live
 * backend, so every number in the happy path is something the server really
 * said. `api_diagnostics_degraded.json` is CONSTRUCTED from the handler's
 * branches and says so in its own `_note`, because a healthy database cannot
 * produce a permission-denied table or an empty time block — and a fixture
 * cannot fail on a value it does not contain.
 */

function testClient(): QueryClient {
  const client = makeQueryClient();
  client.setDefaultOptions({ queries: { retry: false } });
  return client;
}

function renderPage() {
  return render(
    <QueryClientProvider client={testClient()}>
      <MemoryRouter>
        <DiagnosticsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function stubJson(body: unknown) {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const pathname = String(input).split('?')[0];
    if (pathname !== '/api/diagnostics') {
      return Promise.reject(new Error(`DiagnosticsPage called an unexpected endpoint: ${pathname}`));
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response);
  }));
}

function stubStatus(status: number, detail: string) {
  vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({
    ok: false,
    status,
    json: () => Promise.resolve({ detail }),
  } as Response)));
}

describe('DiagnosticsPage', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders the recorded healthy report', async () => {
    stubJson(healthy);
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('The API can read everything it needs')).toBeTruthy();
    });
    // Recorded counts, not invented ones.
    expect(screen.getByText('player_comprehensive_stats')).toBeTruthy();
    expect(screen.getByText('20,977 rows')).toBeTruthy();
    expect(screen.getByText('nothing the API needs is missing')).toBeTruthy();
  });

  it('says why a table has no count instead of printing zero', async () => {
    stubJson(degraded);
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Something the API needs is missing')).toBeTruthy();
    });
    expect(screen.getByText('permission denied for table player_comprehensive_stats')).toBeTruthy();
    expect(screen.getByText('relation "processed_files" does not exist')).toBeTruthy();
    // A table that really has zero rows still shows the zero — absence and
    // emptiness must not collapse into one another in either direction.
    expect(screen.getByText('0 rows')).toBeTruthy();
  });

  it('reports an empty time block as a query that did not run', async () => {
    stubJson(degraded);
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/timing query did not run/)).toBeTruthy();
    });
    // and never as zeroes
    expect(screen.queryByText('dead time, as stored')).toBeNull();
  });

  it('shows a monitoring table that failed as unavailable, not as zero rows', async () => {
    stubJson(degraded);
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('query failed: unavailable')).toBeTruthy();
    });
  });

  it('tells an anonymous visitor to sign in', async () => {
    stubStatus(401, 'Authentication required');
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/you are not signed in/i)).toBeTruthy();
    });
  });

  it('tells a signed-in non-admin that the page is admin-only, not that it failed', async () => {
    stubStatus(403, 'Admin privileges required');
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/for admins only/i)).toBeTruthy();
    });
    // ⛔ The failure this test exists for: rendering a 403 as a broken page
    // tells a signed-in player to sign in again, forever.
    expect(screen.queryByText(/not signed in/i)).toBeNull();
    expect(screen.queryByText(/unavailable/i)).toBeNull();
  });

  it('still reports a real failure as a failure', async () => {
    stubStatus(500, 'boom');
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('diagnostics: unavailable')).toBeTruthy();
    });
  });
});
