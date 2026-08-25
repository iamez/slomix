import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { SmartStatsDiag } from './SmartStatsDiag';
import diag from './__fixtures__/api_diagnostics_storytelling_completeness.json';
import sessions from './__fixtures__/api_sessions.json';

/** Rendered against RECORDED responses. The default date comes from
 * /api/sessions (the endpoint 422s without a scope — measured live), so the
 * fetch stub asserts the diagnostics call actually carries session_date. */

function fixtureFetch(input: RequestInfo | URL): Promise<Response> {
  const url = String(input);
  const pathname = url.split('?')[0];
  if (pathname === '/api/sessions') {
    return Promise.resolve({ ok: true, json: () => Promise.resolve(sessions) } as Response);
  }
  if (pathname === '/api/diagnostics/storytelling-completeness') {
    if (!url.includes('session_date=')) {
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

  it('renders the three boards, thresholds and known issues from recorded data', async () => {
    vi.stubGlobal('fetch', vi.fn(fixtureFetch));
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
