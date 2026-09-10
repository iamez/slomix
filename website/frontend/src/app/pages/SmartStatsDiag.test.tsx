import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { SmartStatsDiag } from './SmartStatsDiag';
import diag from './__fixtures__/api_diagnostics_storytelling_completeness.json';
import sessions from './__fixtures__/api_sessions.json';

/** Rendered against RECORDED responses. The default scope comes from
 * /api/sessions as a gaming_session_id — session_date is date-wide on the
 * backend and merges same-day sessions (Codex on #809); the endpoint 422s
 * with no scope at all (measured live), and the stub keeps both truths. */

function fixtureFetch(input: RequestInfo | URL): Promise<Response> {
  const url = String(input);
  const pathname = url.split('?')[0];
  if (pathname === '/api/sessions') {
    return Promise.resolve({ ok: true, json: () => Promise.resolve(sessions) } as Response);
  }
  if (pathname === '/api/diagnostics/storytelling-completeness') {
    if (!url.includes('session_date=') && !url.includes('gaming_session_id=')) {
      // The real backend answers 422 here; resolving anyway would hide a
      // regression to the no-scope call.
      return Promise.resolve({ ok: false, status: 422 } as Response);
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve(diag) } as Response);
  }
  return Promise.reject(new Error(`SmartStatsDiag called an unexpected endpoint: ${pathname}`));
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
        <SmartStatsDiag />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('SmartStatsDiag', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders the three boards from recorded data, scoped by session ID', async () => {
    const fetchSpy = vi.fn(fixtureFetch);
    vi.stubGlobal('fetch', fetchSpy);
    renderPage();

    // Boards: 1370/1370 kills, 21/21 rounds — all at 100.0% in the recording.
    await waitFor(() => expect(screen.getAllByText('1,370').length).toBeGreaterThan(0));
    expect(screen.getAllByText('100.0%').length).toBe(3);
    expect(screen.getByText(/kis coverage/)).toBeInTheDocument();
    expect(screen.getByText(/round linkage/)).toBeInTheDocument();
    expect(screen.getByText(/r1\+r2 correlation/)).toBeInTheDocument();

    // The recording has no warnings and the session crosses midnight.
    expect(screen.getByText(/No warnings/)).toBeInTheDocument();
    expect(screen.getByText(/gaming_session_id 150/)).toBeInTheDocument();
    expect(screen.getByText(/crosses midnight/)).toBeInTheDocument();

    // Systemic known issues render with their titles.
    expect(screen.getByText('time_played_seconds ni per-player')).toBeInTheDocument();
    expect(screen.getByText('Distance multiplier hardcoded na 1.0')).toBeInTheDocument();

    // The DEFAULT scope is the latest session's ID (152), never its date —
    // session_date merges same-day sessions on the backend.
    const diagCall = fetchSpy.mock.calls
      .map((c) => String(c[0]))
      .find((u) => u.includes('storytelling-completeness'));
    expect(diagCall).toContain('gaming_session_id=152');
    expect(diagCall).not.toContain('session_date=');
  });

  it('renders no_data as an empty state, not three red boards', async () => {
    const empty = { ...(diag as Record<string, unknown>), status: 'no_data', kills_total: 0, kis_rows: 0, completeness_ratio: 0.0, linkage_ratio: 0.0, correlation_ratio: 0.0 };
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('storytelling-completeness')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(empty) } as Response);
      }
      return fixtureFetch(input);
    }));
    renderPage();
    await waitFor(() => expect(screen.getByText(/nothing to diagnose/i)).toBeInTheDocument());
    expect(screen.queryByText(/kis coverage/)).not.toBeInTheDocument();
  });

  it('says so when no sessions exist instead of pending forever', async () => {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const pathname = String(input).split('?')[0];
      if (pathname === '/api/sessions') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) } as Response);
      }
      return fixtureFetch(input);
    }));
    renderPage();
    await waitFor(() => expect(screen.getByText(/no sessions recorded yet/)).toBeInTheDocument());
    expect(screen.queryByText(/diagnostics…/)).not.toBeInTheDocument();
  });

  it('says unavailable when the diagnostics endpoint fails', async () => {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const pathname = String(input).split('?')[0];
      if (pathname === '/api/diagnostics/storytelling-completeness') {
        return Promise.resolve({ ok: false, status: 503 } as Response);
      }
      return fixtureFetch(input);
    }));
    renderPage();
    await waitFor(() => expect(screen.getByText(/diagnostics: unavailable/)).toBeInTheDocument());
  });

  it('reports when even the default date cannot be found', async () => {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const pathname = String(input).split('?')[0];
      if (pathname === '/api/sessions') {
        return Promise.resolve({ ok: false, status: 503 } as Response);
      }
      return fixtureFetch(input);
    }));
    renderPage();
    await waitFor(() =>
      expect(screen.getByText(/latest session date: unavailable/)).toBeInTheDocument(),
    );
  });
});
