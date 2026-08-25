import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { Landing } from './Landing';
import liveState from './__fixtures__/api_live_state.json';
import voice from './__fixtures__/api_voice_activity_current.json';
import overview from './__fixtures__/api_stats_overview.json';
import leaders from './__fixtures__/api_stats_quick_leaders.json';
import sessions from './__fixtures__/api_sessions.json';

/**
 * Rendered against RECORDED responses (docs/design/09 §H4) — the fixtures
 * are corpus files, so every asserted string is something the live backend
 * really said. Fetch is routed by pathname; an unexpected call fails loudly
 * instead of resolving to something invented.
 */
const FIXTURES: Record<string, unknown> = {
  '/api/live/state': liveState,
  '/api/voice-activity/current': voice,
  '/api/stats/overview': overview,
  '/api/stats/quick-leaders': leaders,
  '/api/sessions': sessions,
};

function fixtureFetch(input: RequestInfo | URL): Promise<Response> {
  const pathname = String(input).split('?')[0];
  const body = FIXTURES[pathname];
  if (body === undefined) {
    return Promise.reject(new Error(`Landing called an unexpected endpoint: ${pathname}`));
  }
  return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response);
}

function testClient(): QueryClient {
  // Production client retries once; a test asserting the error state would
  // only be waiting out the retry backoff.
  const client = makeQueryClient();
  client.setDefaultOptions({ queries: { retry: false } });
  return client;
}

function renderLanding() {
  return render(
    <QueryClientProvider client={testClient()}>
      <MemoryRouter>
        <Landing />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('Landing', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders the hero, live panel, figures, evenings and leaders from recorded data', async () => {
    vi.stubGlobal('fetch', vi.fn(fixtureFetch));
    renderLanding();

    expect(screen.getByRole('heading', { level: 1 }).textContent).toMatch(/every round we play/i);

    // Live panel: the recording says idle, 0 players, supply, nobody in voice.
    await waitFor(() => expect(screen.getByText('SERVER IDLE')).toBeInTheDocument());
    expect(screen.getByText('supply')).toBeInTheDocument();
    expect(screen.getByText('No one in voice')).toBeInTheDocument();

    // Standing figures straight from /api/stats/overview.
    await waitFor(() => expect(screen.getByText('122,999')).toBeInTheDocument());
    expect(screen.getByText('rounds kept')).toBeInTheDocument();

    // Last night = first /api/sessions row: 7 / 3 on 2026-08-23.
    expect(await screen.findByText('7')).toBeInTheDocument();
    expect(screen.getAllByText(/10 rd/).length).toBeGreaterThan(0);

    // Quick leaders from the recording.
    expect(await screen.findByText('vid')).toBeInTheDocument();
  });

  it('says unavailable instead of rendering empty boxes when an endpoint fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const pathname = String(input).split('?')[0];
        if (pathname === '/api/stats/overview') {
          return Promise.resolve({ ok: false, status: 503 } as Response);
        }
        return fixtureFetch(input);
      }),
    );
    renderLanding();
    await waitFor(() => expect(screen.getByText(/figures: unavailable/)).toBeInTheDocument());
  });
});
