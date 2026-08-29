import { render, screen, waitFor } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { SessionDetail } from './SessionDetail';
import detail from './__fixtures__/api_stats_session_gaming_session_id_detail.json';
import rounds from './__fixtures__/api_session_detail_rounds.json';
import mvp from './__fixtures__/api_stats_session_gaming_session_id_mvp.json';
import verdicts from './__fixtures__/api_stats_session_gaming_session_id_verdicts.json';
import goodNight from './__fixtures__/api_stats_session_gaming_session_id_good_night.json';
import sessions from './__fixtures__/api_sessions_list.json';

/** Session 154, recorded 2026-08-29: 12 rounds, 6 maps, 6 players, 5–7. */
const BODIES: [string, unknown][] = [
  ['/detail', detail],
  ['/rounds', rounds],
  ['/mvp', mvp],
  ['/verdicts', verdicts],
  ['/good-night', goodNight],
  ['/api/sessions', sessions],
];

function fixtureFetch(input: RequestInfo | URL): Promise<Response> {
  const url = String(input);
  const hit = BODIES.find(([path]) => url.includes(path));
  if (!hit) return Promise.reject(new Error(`unexpected endpoint: ${url}`));
  return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(hit[1]) } as Response);
}

function withOverride(path: string, make: () => Promise<Response>) {
  return (input: RequestInfo | URL) =>
    String(input).includes(path) ? make() : fixtureFetch(input);
}

function json(body: unknown): Promise<Response> {
  return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);
}

function renderPage(fetchImpl = fixtureFetch, entry = '/session-detail/154') {
  vi.stubGlobal('fetch', vi.fn(fetchImpl));
  const client = makeQueryClient();
  client.setDefaultOptions({ queries: { retry: false } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[entry]}>
        <Routes>
          <Route path="/session-detail/:sessionId" element={<SessionDetail />} />
          <Route path="/session-detail/:sessionId/:tab" element={<SessionDetail />} />
          <Route path="/session-detail/date/:sessionDate" element={<SessionDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('SessionDetail', () => {
  it('opens on the scoreboard with the stopwatch result', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('Team A 5 — 7 Team B')).toBeInTheDocument());
    expect(screen.getAllByText('etl_adlernest').length).toBeGreaterThan(0);
    // A full hold is not a time, and the recording has one.
    expect(screen.getAllByText(/fullhold/).length).toBeGreaterThan(0);
  });

  it('says scoring is unavailable rather than showing a 0–0', async () => {
    // The 2026-08-12 bug: an unpairable session rendered as a real draw.
    const noScoring = { ...detail, scoring: { ...(detail as { scoring: object }).scoring, available: false, maps: [] } };
    renderPage(withOverride('/detail', () => json(noScoring)));
    await waitFor(() => expect(screen.getByText(/could not be paired, which is not the same as a 0–0/)).toBeInTheDocument());
  });

  it('shows the night score with the components that produced it', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('night score')).toBeInTheDocument());
    // A bare index invites an argument nobody can settle; the seven
    // components are the argument.
    expect(screen.getByText('balance')).toBeInTheDocument();
    expect(screen.getByText('tension')).toBeInTheDocument();
    expect(screen.getByText(String((goodNight as { score: number }).score))).toBeInTheDocument();
  });

  it('separates "not computed" from a low night score', async () => {
    renderPage(withOverride('/good-night', () => json({ ...goodNight, available: false })));
    await waitFor(() => expect(screen.getByText(/different from a low score/)).toBeInTheDocument());
  });

  it('gives a first night no percentile to compare against', async () => {
    const first = {
      ...verdicts,
      players: [{
        ...(verdicts as { players: Record<string, unknown>[] }).players[0],
        first_night: true, avg_dpm: null, percentile: null, sessions_in_baseline: 0,
      }],
    };
    renderPage(withOverride('/verdicts', () => json(first)));
    await waitFor(() => expect(screen.getByText(/first night — no baseline yet/)).toBeInTheDocument());
  });

  it('calls the MVP panel a vote and keeps it away from the model', async () => {
    const voted = {
      ...mvp,
      total_votes: 3,
      candidates: [{ ...(mvp as { candidates: Record<string, unknown>[] }).candidates[0], votes: 3, vote_pct: 100 }],
    };
    renderPage(withOverride('/mvp', () => json(voted)));
    await waitFor(() => expect(screen.getByText(/a vote, not a rating/)).toBeInTheDocument());
  });

  it('says an empty ballot is empty rather than showing a tie', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText(/an empty ballot, not a tie/)).toBeInTheDocument());
  });

  it('lists every round, marking the ones that do not count', async () => {
    const withCancelled = {
      ...rounds,
      counted_rounds: 11,
      total_rounds: 12,
      rounds: [
        { ...(rounds as { rounds: Record<string, unknown>[] }).rounds[0], counts_toward_totals: false, round_status: 'cancelled' },
        ...(rounds as { rounds: Record<string, unknown>[] }).rounds.slice(1),
      ],
    };
    renderPage(withOverride('/rounds', () => json(withCancelled)), '/session-detail/154/rounds');
    await waitFor(() => expect(screen.getByText(/11 of 12 count toward totals/)).toBeInTheDocument());
    // Shown, not hidden: a player who played it has to be able to find it.
    expect(screen.getByText(/cancelled · shown, not summed/)).toBeInTheDocument();
    expect(screen.getAllByText(/^R[12]$/).length).toBe((rounds as { rounds: unknown[] }).rounds.length);
  });

  it('shows the per-player totals on their own tab', async () => {
    renderPage(fixtureFetch, '/session-detail/154/players');
    await waitFor(() => expect(screen.getByText(/sorted by damage/)).toBeInTheDocument());
    const first = (detail as { players: { player_name: string }[] }).players[0];
    expect(screen.getAllByText(first.player_name).length).toBeGreaterThan(0);
  });

  it('does not fetch the session list when the URL already names a session', async () => {
    // Thirty sessions loaded to be ignored is the same waste the story
    // page's SSR panel was called out for; the list exists only to resolve
    // a DATE.
    const spy = vi.fn(fixtureFetch);
    renderPage(spy);
    await waitFor(() => expect(screen.getByText('Team A 5 — 7 Team B')).toBeInTheDocument());
    expect(spy.mock.calls.some(([u]) => String(u).includes('/api/sessions?'))).toBe(false);
  });

  it('resolves a dated legacy link to that session', async () => {
    // /session-detail/date/:date is a legacy hash. The recording's newest
    // session is 154 on 2026-08-27; the link has to land there because of
    // the date, not because it is the newest.
    renderPage(fixtureFetch, '/session-detail/date/2026-08-27');
    await waitFor(() => expect(screen.getByText('Team A 5 — 7 Team B')).toBeInTheDocument());
  });

  it('asks which session when one date holds two', async () => {
    const twoOnOneDay = [
      { ...(sessions as Record<string, unknown>[])[0], session_id: 900, date: '2026-08-27' },
      { ...(sessions as Record<string, unknown>[])[0], session_id: 901, date: '2026-08-27' },
    ];
    renderPage(withOverride('/api/sessions', () => json(twoOnOneDay)), '/session-detail/date/2026-08-27');
    await waitFor(() => expect(screen.getByText(/two sessions were played on 2026-08-27/)).toBeInTheDocument());
    expect(screen.queryByText('Team A 5 — 7 Team B')).toBeNull();
  });

  it('marks a section unavailable rather than empty when its endpoint fails', async () => {
    renderPage(withOverride('/verdicts', () =>
      Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) } as Response)));
    await waitFor(() => expect(screen.getByText(/form: unavailable/)).toBeInTheDocument());
    // …and the rest of the session still renders.
    expect(screen.getByText('Team A 5 — 7 Team B')).toBeInTheDocument();
  });
});
