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
const FIXTURES = new Map<string, unknown>([
  ['/api/live/state', liveState],
  ['/api/voice-activity/current', voice],
  ['/api/stats/overview', overview],
  ['/api/stats/quick-leaders', leaders],
  ['/api/sessions', sessions],
]);

function fixtureFetch(input: RequestInfo | URL): Promise<Response> {
  const pathname = String(input).split('?')[0];
  const body = FIXTURES.get(pathname);
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
    // The recording's last event is ~5 days old — while idle the retained
    // map is a memory and carries its age (Codex wave 5).
    expect(screen.getByText('supply · 5 d ago')).toBeInTheDocument();
    expect(screen.getByText('No one in voice')).toBeInTheDocument();

    // Standing figures straight from /api/stats/overview.
    await waitFor(() => expect(screen.getByText('122,999')).toBeInTheDocument());
    expect(screen.getByText('rounds kept')).toBeInTheDocument();

    // Last night = first /api/sessions row: 7 / 3 on 2026-08-23. The label
    // is honest about age (the recording is days old by the time any test
    // runs) and the score is a BOX score, not maps won.
    expect(await screen.findByText('7')).toBeInTheDocument();
    expect(screen.getAllByText(/10 rd/).length).toBeGreaterThan(0);
    // Recency comes from the API's own classification: the recording says
    // time_ago 'Yesterday', so the panel says last night — regardless of
    // how many browser-local days have elapsed since the fixture was cut.
    expect(screen.getByText('last night')).toBeInTheDocument();
    expect(screen.getByText(/See last night/)).toBeInTheDocument();
    expect(screen.getByText(/box score/)).toBeInTheDocument();

    // Session links carry the stable session_id — a date URL would merge
    // two same-day sessions into one page (Codex on #806).
    const evening = screen.getByRole('link', { name: /open the evening/i });
    expect(evening.getAttribute('href')).toBe('/session-detail/152');

    // Quick leaders from the recording.
    expect(await screen.findByText('vid')).toBeInTheDocument();
  });

  it('renders a session without team attribution instead of crashing on null', async () => {
    const first = (sessions as Array<Record<string, unknown>>)[0];
    const unattributed = [{
      ...first, team_1_name: null, team_2_name: null, team_1_score: null, team_2_score: null,
    }];
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const pathname = String(input).split('?')[0];
        if (pathname === '/api/sessions') {
          return Promise.resolve({ ok: true, json: () => Promise.resolve(unattributed) } as Response);
        }
        return fixtureFetch(input);
      }),
    );
    renderLanding();
    await waitFor(() => expect(screen.getByText(/score not attributed/)).toBeInTheDocument());
    expect(screen.getByText('—')).toBeInTheDocument();
    expect(screen.queryByText(/box score/)).not.toBeInTheDocument();
  });

  it('keeps the voice row alive when the live-state query fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const pathname = String(input).split('?')[0];
        if (pathname === '/api/live/state') {
          return Promise.resolve({ ok: false, status: 502 } as Response);
        }
        return fixtureFetch(input);
      }),
    );
    renderLanding();
    await waitFor(() => expect(screen.getByText(/game server: unavailable/)).toBeInTheDocument());
    expect(await screen.findByText('No one in voice')).toBeInTheDocument();
  });

  it('treats an all-zero overview as unavailable, not as the record', async () => {
    // The endpoint substitutes 0 per failed aggregate and still answers 200.
    const zeroed = { ...(overview as Record<string, unknown>), rounds: 0, total_kills: 0, sessions: 0, players_all_time: 0 };
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const pathname = String(input).split('?')[0];
        if (pathname === '/api/stats/overview') {
          return Promise.resolve({ ok: true, json: () => Promise.resolve(zeroed) } as Response);
        }
        return fixtureFetch(input);
      }),
    );
    renderLanding();
    await waitFor(() => expect(screen.getByText(/figures: unavailable/)).toBeInTheDocument());
  });

  it('attributes a board failure to the board that failed, not its neighbour', async () => {
    // The backend's error tokens are per board — exactly 'xp_query_failed' /
    // 'dpm_query_failed' (players_router). Here xp is legitimately empty
    // while dpm failed: only the dpm board may say unavailable.
    const broken = { ...(leaders as Record<string, unknown>), xp: [], dpm_sessions: [], errors: ['dpm_query_failed'] };
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const pathname = String(input).split('?')[0];
        if (pathname === '/api/stats/quick-leaders') {
          return Promise.resolve({ ok: true, json: () => Promise.resolve(broken) } as Response);
        }
        return fixtureFetch(input);
      }),
    );
    renderLanding();
    await waitFor(() => expect(screen.getAllByText(/board: unavailable/).length).toBe(1));
    expect(screen.getByText(/no data in this window/)).toBeInTheDocument();
  });

  it('qualifies an aged roster count instead of presenting it as current', async () => {
    // The reducer keeps the lineup up to 600 s after is_live flips off and
    // exposes roster_age_seconds for exactly this (Codex wave 4).
    const aged = {
      ...(liveState as Record<string, unknown>),
      roster: { axis: [], allies: [], spectators: [], player_count: 5, roster_age_seconds: 240, has_bots: false },
    };
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const pathname = String(input).split('?')[0];
        if (pathname === '/api/live/state') {
          return Promise.resolve({ ok: true, json: () => Promise.resolve(aged) } as Response);
        }
        return fixtureFetch(input);
      }),
    );
    renderLanding();
    await waitFor(() => expect(screen.getByText(/5 players · seen 4 min ago/)).toBeInTheDocument());
  });

  it('qualifies the map the moment is_live is false — no second threshold', async () => {
    // The backend flips is_live at 180 s; a frontend threshold beside it
    // left a window showing SERVER IDLE next to a bare map.
    const justIdle = { ...(liveState as Record<string, unknown>), is_live: false, last_event_age_seconds: 200 };
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const pathname = String(input).split('?')[0];
        if (pathname === '/api/live/state') {
          return Promise.resolve({ ok: true, json: () => Promise.resolve(justIdle) } as Response);
        }
        return fixtureFetch(input);
      }),
    );
    renderLanding();
    await waitFor(() => expect(screen.getByText('supply · 3 min ago')).toBeInTheDocument());
  });

  it('marks an unconfirmed map as a guess even while live (#808 fields)', async () => {
    const unconfirmed = { ...(liveState as Record<string, unknown>), is_live: true, map_confirmed: false, map_age_seconds: null };
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const pathname = String(input).split('?')[0];
        if (pathname === '/api/live/state') {
          return Promise.resolve({ ok: true, json: () => Promise.resolve(unconfirmed) } as Response);
        }
        return fixtureFetch(input);
      }),
    );
    renderLanding();
    await waitFor(() => expect(screen.getByText('supply · unconfirmed')).toBeInTheDocument());
  });

  it('treats an in-band voice failure as unavailable, not as an empty room (#808)', async () => {
    const broken = { status: 'unavailable', reason: 'malformed status_data', total_count: 0, members: [] };
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const pathname = String(input).split('?')[0];
        if (pathname === '/api/voice-activity/current') {
          return Promise.resolve({ ok: true, json: () => Promise.resolve(broken) } as Response);
        }
        return fixtureFetch(input);
      }),
    );
    renderLanding();
    await waitFor(() => expect(screen.getByText(/voice: unavailable/)).toBeInTheDocument());
    expect(screen.queryByText('No one in voice')).not.toBeInTheDocument();
  });

  it('relays the backend staleness verdict on a voice snapshot (#808)', async () => {
    // The endpoint does not expose these fields TODAY — this asserts the
    // defensive path is live the moment the backend starts sending them.
    // The verdict and the age are both the SERVER's; nothing here reads
    // the client clock.
    const stale = {
      ...(voice as Record<string, unknown>),
      status: 'stale',
      age_seconds: 3600,
    };
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const pathname = String(input).split('?')[0];
        if (pathname === '/api/voice-activity/current') {
          return Promise.resolve({ ok: true, json: () => Promise.resolve(stale) } as Response);
        }
        return fixtureFetch(input);
      }),
    );
    renderLanding();
    await waitFor(() => expect(screen.getByText(/No one in voice · as of 60 min ago/)).toBeInTheDocument());
  });

  it('labels a session dated today as tonight, not last night', async () => {
    const first = (sessions as Array<Record<string, unknown>>)[0];
    const today = new Date();
    const iso = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
    const fresh = [{ ...first, date: iso, time_ago: 'Today' }];
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const pathname = String(input).split('?')[0];
        if (pathname === '/api/sessions') {
          return Promise.resolve({ ok: true, json: () => Promise.resolve(fresh) } as Response);
        }
        return fixtureFetch(input);
      }),
    );
    renderLanding();
    await waitFor(() => expect(screen.getByText('tonight')).toBeInTheDocument());
    expect(screen.getByText(/See tonight/)).toBeInTheDocument();
    expect(screen.queryByText('last night')).not.toBeInTheDocument();
  });

  it('says so when no sessions exist at all — in both places, without a false error', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const pathname = String(input).split('?')[0];
        if (pathname === '/api/sessions') {
          return Promise.resolve({ ok: true, json: () => Promise.resolve([]) } as Response);
        }
        return fixtureFetch(input);
      }),
    );
    renderLanding();
    // A successful [] is an empty state in the hero panel AND the list —
    // never "unavailable", the endpoint answered fine (Codex wave 3).
    await waitFor(() => expect(screen.getAllByText(/no sessions recorded yet/).length).toBe(2));
    expect(screen.queryByText(/last session: unavailable/)).not.toBeInTheDocument();
    // The heading stays neutral — "last night" would assert a session that
    // never happened (wave 7).
    expect(screen.getByText('latest session')).toBeInTheDocument();
    expect(screen.queryByText('last night')).not.toBeInTheDocument();
  });

  it('renders a dash for a single zeroed overview metric instead of claiming 0 kills', async () => {
    // _safe_val substitutes 0 PER METRIC — one failed aggregate must not
    // publish "0 kills recorded" next to real figures (Codex wave 3).
    const partial = { ...(overview as Record<string, unknown>), total_kills: 0 };
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const pathname = String(input).split('?')[0];
        if (pathname === '/api/stats/overview') {
          return Promise.resolve({ ok: true, json: () => Promise.resolve(partial) } as Response);
        }
        return fixtureFetch(input);
      }),
    );
    renderLanding();
    await waitFor(() => expect(screen.getByText('1,948')).toBeInTheDocument());
    expect(screen.queryByText('122,999')).not.toBeInTheDocument();
    expect(screen.getAllByText('—').length).toBeGreaterThan(0);
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
