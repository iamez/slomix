import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { Home } from './Home';
import liveStatus from './__fixtures__/api_live_status.json';
import lastSession from './__fixtures__/api_stats_last_session.json';
import trends from './__fixtures__/api_stats_trends.json';
import matches from './__fixtures__/api_stats_matches.json';
import seasonCurrent from './__fixtures__/api_seasons_current.json';
import seasonLeaders from './__fixtures__/api_seasons_current_leaders.json';
import seasonSummary from './__fixtures__/api_seasons_current_summary.json';
import availability from './__fixtures__/api_availability.json';
import movers from './__fixtures__/api_skill_movers.json';
import challenge from './__fixtures__/api_challenges_current.json';
import tonight from './__fixtures__/api_stats_tonight.json';
import calendar from './__fixtures__/api_stats_activity_calendar.json';
import overview from './__fixtures__/api_stats_overview.json';
import quickLeaders from './__fixtures__/api_stats_quick_leaders.json';
import sessions from './__fixtures__/api_sessions.json';
import search from './__fixtures__/auth_players_search.json';

/** Rendered against RECORDED responses — every asserted string is something
 * the backend really said (api_live_status recorded FRESH on 25. 8.; the
 * corpus copy held a different shape — see the LiveStatus type note). */
const FIXTURES = new Map<string, unknown>([
  ['/api/live-status', liveStatus],
  ['/api/stats/last-session', lastSession],
  ['/api/stats/trends', trends],
  ['/api/stats/matches', matches],
  ['/api/seasons/current', seasonCurrent],
  ['/api/seasons/current/leaders', seasonLeaders],
  ['/api/seasons/current/summary', seasonSummary],
  ['/api/availability', availability],
  ['/api/skill/movers', movers],
  ['/api/challenges/current', challenge],
  ['/api/stats/tonight', tonight],
  ['/api/stats/activity-calendar', calendar],
  ['/api/stats/overview', overview],
  ['/api/stats/quick-leaders', quickLeaders],
  ['/api/sessions', sessions],
  ['/auth/players/search', search],
]);

function fixtureFetch(input: RequestInfo | URL): Promise<Response> {
  const pathname = String(input).split('?')[0];
  const body = FIXTURES.get(pathname);
  if (body === undefined) {
    return Promise.reject(new Error(`Home called an unexpected endpoint: ${pathname}`));
  }
  return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);
}

function testClient(): QueryClient {
  const client = makeQueryClient();
  client.setDefaultOptions({ queries: { retry: false } });
  return client;
}

function renderHome() {
  return render(
    <QueryClientProvider client={testClient()}>
      <MemoryRouter>
        <Home />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('Home', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders every section from recorded data', async () => {
    vi.stubGlobal('fetch', vi.fn(fixtureFetch));
    renderHome();

    // Top band from the fresh live-status recording.
    await waitFor(() => expect(screen.getByText('#purans.only')).toBeInTheDocument());
    expect(screen.getByText('0 / 16 players')).toBeInTheDocument();

    // Hero: session 152, BOX 7 / 3, linked by gaming_session_id.
    await waitFor(() => expect(screen.getByText(/session 152/)).toBeInTheDocument());
    expect(screen.getByText('7')).toBeInTheDocument();
    const open = screen.getByRole('link', { name: /open the evening/i });
    expect(open.getAttribute('href')).toBe('/session-detail/152');

    // Evening figures are SUMS of the session's own player rows — recompute
    // from the fixture rather than hard-coding, so the fixture stays the
    // single source.
    const fixture = lastSession as {
      teams: { players: { kills: number }[] }[];
      unassigned_players?: { kills: number }[];
    };
    const players = [...fixture.teams.flatMap((t) => t.players), ...(fixture.unassigned_players ?? [])];
    const kills = players.reduce((a, p) => a + p.kills, 0);
    expect(screen.getByText(kills.toLocaleString('en-US'))).toBeInTheDocument();

    // Insights from trends: recorded peak rounds/day is 22.
    expect(await screen.findByText(/peak 22/)).toBeInTheDocument();
    expect(screen.getAllByText('te_escape2').length).toBeGreaterThan(0);

    // Season block.
    expect(await screen.findByText('2026 Fall (Q3)')).toBeInTheDocument();
    expect(screen.getByText('37 days left')).toBeInTheDocument();

    // Latest games row from the matches recording (players joined with ·).
    expect((await screen.findAllByText(/SuperBoyy · carniee/)).length).toBeGreaterThan(0);

    // Quick leaders (vid appears in xp board and possibly movers).
    expect((await screen.findAllByText('vid')).length).toBeGreaterThan(0);

    // Movers: recorded top mover with +36.4%.
    expect((await screen.findAllByText('#smetarski.proner')).length).toBeGreaterThan(0);
    expect(screen.getByText('+36.4%')).toBeInTheDocument();

    // Challenge is null this week — said, not blank.
    expect(await screen.findByText(/no challenge this week/)).toBeInTheDocument();

    // Tonight: recording is inactive and voice empty.
    expect(screen.getByText('Nobody in voice')).toBeInTheDocument();

    // Standing figures LIVE from overview.
    expect(screen.getByText('122,999')).toBeInTheDocument();

    // The kpm trace absence is named, never an invented line.
    expect(screen.getByText(/no per-minute series is recorded/)).toBeInTheDocument();
  });

  it('says unavailable per section when an endpoint fails, without taking the page down', async () => {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const pathname = String(input).split('?')[0];
      if (pathname === '/api/seasons/current' || pathname === '/api/stats/trends') {
        return Promise.resolve({ ok: false, status: 503 } as Response);
      }
      return fixtureFetch(input);
    }));
    renderHome();
    await waitFor(() => expect(screen.getByText(/season: unavailable/)).toBeInTheDocument());
    expect(screen.getByText(/activity: unavailable/)).toBeInTheDocument();
    // The rest of the page still renders.
    expect(await screen.findByText(/session 152/)).toBeInTheDocument();
  });

  it('searches players once two characters are typed', async () => {
    const fetchSpy = vi.fn(fixtureFetch);
    vi.stubGlobal('fetch', fetchSpy);
    const { getByLabelText } = renderHome();
    const input = getByLabelText('Find your stats') as HTMLInputElement;
    const { fireEvent } = await import('@testing-library/react');
    fireEvent.change(input, { target: { value: 'v' } });
    expect(fetchSpy.mock.calls.map((c) => String(c[0])).some((u) => u.includes('players/search'))).toBe(false);
    fireEvent.change(input, { target: { value: 'vi' } });
    // The recording is an empty result — said, not blank.
    await waitFor(() => expect(screen.getByText(/no player matches "vi"/)).toBeInTheDocument());
    const call = fetchSpy.mock.calls.map((c) => String(c[0])).find((u) => u.includes('players/search'));
    expect(call).toContain('q=vi');
  });
  it('says a missing trend series is missing, not unavailable', async () => {
    // /api/stats/trends omits a series the request did not ask for: the KEY
    // is absent, not null (measured on #830, where the route gains
    // response_model_exclude_none). "unavailable" would blame the endpoint
    // for doing what it was asked.
    const partial = { ...(trends as object), rounds: undefined, active_players: undefined };
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL): Promise<Response> => {
      const pathname = String(input).split('?')[0];
      if (pathname === '/api/stats/trends') {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(partial) } as Response);
      }
      return fixtureFetch(input);
    }));
    renderHome();
    await waitFor(() => expect(screen.getAllByText('not in this response').length).toBeGreaterThan(0));
    expect(screen.queryByText(/trend: unavailable/)).toBeNull();
  });
  it('shows the hero without scores when the session has no scoring', async () => {
    // The short form: {available: false, reason} — no names, no scores. All
    // eight sessions in the database answer the long form, so this shape can
    // only be reached by forcing it (the brother did, on #830), and a page
    // typed off the corpus would read names that are not there.
    const short = {
      ...(lastSession as object),
      scoring: { available: false, reason: 'no persistent teams' },
    };
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL): Promise<Response> => {
      const pathname = String(input).split('?')[0];
      if (pathname === '/api/stats/last-session') {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(short) } as Response);
      }
      return fixtureFetch(input);
    }));
    renderHome();
    // The evening still renders — date, players, rounds — without a scoreline.
    await waitFor(() => expect(screen.getAllByText(/players/i).length).toBeGreaterThan(0));
    expect(screen.queryByText('Team A')).toBeNull();
  });
  it('quotes the server threshold rather than keeping its own', async () => {
    // session_ready.threshold is the number that fires the Discord notice.
    // A card with its own copy of it drifts the day somebody changes the
    // rule, and nobody finds out from the page.
    const ready = {
      ...(availability as object),
      // NOT 6. The recorded threshold is 6, so a page with a hardcoded 6
      // would satisfy a test written against 6 — the control mutation
      // proved exactly that before this line said 8.
      session_ready: { date: '2026-08-29', ready: false, looking_count: 4, threshold: 8, event_key: 'x' },
    };
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL): Promise<Response> => {
      if (String(input).split('?')[0] === '/api/availability') {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(ready) } as Response);
      }
      return fixtureFetch(input);
    }));
    renderHome();
    await waitFor(() => expect(screen.getByText(/4 of 8 looking for tonight/)).toBeInTheDocument());
  });
  it('suppresses the active-days line when the calendar itself failed', async () => {
    // The endpoint answers 200 with an empty (or partial) activity map when
    // its query fails. Counting keys then reports a number about the
    // outage, not about the season — #830 adds the status that says so.
    const failed = { ...(calendar as object), status: 'unavailable', note: 'the activity query failed' };
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL): Promise<Response> => {
      if (String(input).split('?')[0] === '/api/stats/activity-calendar') {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(failed) } as Response);
      }
      return fixtureFetch(input);
    }));
    renderHome();
    // The line the healthy fixture DOES render, so its absence here means
    // the status was read — not that the text never appears.
    await waitFor(() => expect(screen.getAllByText(/days left/).length).toBeGreaterThan(0));
    expect(screen.queryByText(/active on \d+ of the last/)).toBeNull();
  });
  it('names a missing map and drops the link when a round can name no evening', async () => {
    // Both fields are nullable in `rounds` and this query filters neither,
    // so the row can arrive with no map and with neither of the two ways to
    // identify an evening. Linking anyway spells the missing half into the
    // URL (/session-detail/date/null) — a 404 dressed as a working row —
    // and an unnamed map renders as an empty gap. Codex on #841; the
    // backend half of the same finding stops `str(None)` from answering
    // the string "None", which would sail past this guard looking present.
    const rows = matches as { id: number }[];
    const orphan = [
      { ...rows[0], id: 999001, map_name: null, date: null, gaming_session_id: null },
      ...rows.slice(1),
    ];
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL): Promise<Response> => {
      if (String(input).split('?')[0] === '/api/stats/matches') {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(orphan) } as Response);
      }
      return fixtureFetch(input);
    }));
    const { container } = renderHome();

    await waitFor(() => expect(screen.getByText('unknown map')).toBeInTheDocument());
    // No link anywhere on the page carries the missing half in its href.
    const hrefs = screen.getAllByRole('link').map((a) => a.getAttribute('href'));
    expect(hrefs.some((h) => h?.includes('/date/null') || h?.includes('/date/None'))).toBe(false);
    // …and the row it belongs to is still on the page, just not clickable.
    // Counted inside the panel, because the rest of Home links to
    // /session-detail/ too and a page-wide count would answer about them.
    const panel = container.querySelector('[data-parity="home.latest-games"]')!;
    const rowLinks = [...panel.querySelectorAll('a')]
      .filter((a) => a.getAttribute('href')?.startsWith('/session-detail/'));
    expect(rowLinks.length).toBe(orphan.length - 1);
    expect(panel.textContent).toContain('unknown map');
  });

  it('marks a partial overview figure as missing, by name, without blanking the panel', async () => {
    // #830 answers 200 + status:"partial" with fallback zeros when a
    // subquery fails; only failed_metrics can tell a missing figure from a
    // measured zero. Both directions pinned: the named figure says
    // "missing", the unnamed ones keep their real numbers.
    const partialOverview = {
      ...(FIXTURES.get('/api/stats/overview') as Record<string, unknown>),
      rounds: 0, total_kills: 110816, sessions: 151, players_all_time: 94,
      status: 'partial', note: 'rounds subquery failed', failed_metrics: ['rounds'],
    };
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      if (String(input).split('?')[0] === '/api/stats/overview') {
        return Promise.resolve({
          ok: true, status: 200, json: () => Promise.resolve(partialOverview),
        } as Response);
      }
      return fixtureFetch(input);
    }));
    renderHome();
    await waitFor(() => expect(screen.getByText('missing')).toBeInTheDocument());
    expect(screen.getByText('110,816')).toBeInTheDocument();
    expect(screen.getByText('151')).toBeInTheDocument();
    // a measured zero elsewhere must NOT read as missing (that would be the
    // circular flag this codebase keeps refusing)
    expect(screen.getAllByText('missing').length).toBe(1);
  });

});
