import { render, screen, waitFor } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { Story } from './Story';
import scopes from './__fixtures__/api_storytelling_scopes.json';
import narrative from './__fixtures__/api_storytelling_narrative.json';
import boxScore from './__fixtures__/api_storytelling_box_score.json';
import moments from './__fixtures__/api_storytelling_moments.json';
import momentum from './__fixtures__/api_storytelling_momentum.json';
import pwc from './__fixtures__/api_storytelling_win_contribution.json';
import kis from './__fixtures__/api_storytelling_kill_impact.json';
import synergy from './__fixtures__/api_storytelling_synergy.json';
import gravity from './__fixtures__/api_storytelling_gravity.json';
import space from './__fixtures__/api_storytelling_space_created.json';
import enabler from './__fixtures__/api_storytelling_enabler.json';
import lurker from './__fixtures__/api_storytelling_lurker_profile.json';
import playerNarratives from './__fixtures__/api_storytelling_player_narratives.json';

/** The recorded session 154 — 12 rounds over 6 maps, 2026-08-27. */
const BODIES: [string, unknown][] = [
  ['/storytelling/scopes', scopes],
  ['/storytelling/narrative', narrative],
  ['/storytelling/box-score', boxScore],
  ['/storytelling/moments', moments],
  ['/storytelling/momentum', momentum],
  ['/storytelling/win-contribution', pwc],
  ['/storytelling/kill-impact', kis],
  ['/storytelling/synergy', synergy],
  ['/storytelling/gravity', gravity],
  ['/storytelling/space-created', space],
  ['/storytelling/enabler', enabler],
  ['/storytelling/lurker-profile', lurker],
  ['/storytelling/player-narratives', playerNarratives],
];

function bodyFor(url: string): unknown | undefined {
  return BODIES.find(([path]) => url.includes(path))?.[1];
}

function fixtureFetch(input: RequestInfo | URL): Promise<Response> {
  const url = String(input);
  const body = bodyFor(url);
  if (body === undefined) return Promise.reject(new Error(`unexpected endpoint: ${url}`));
  return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);
}

function renderPage(fetchImpl = fixtureFetch, entry = '/story') {
  vi.stubGlobal('fetch', vi.fn(fetchImpl));
  const client = makeQueryClient();
  client.setDefaultOptions({ queries: { retry: false } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[entry]}>
        <Routes>
          <Route path="/story" element={<Story />} />
          <Route path="/story/session/:gsid" element={<Story />} />
          <Route path="/story/date/:date" element={<Story />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

/** Replace one endpoint's response, keeping the rest of the corpus. */
function withOverride(path: string, make: (input: RequestInfo | URL) => Promise<Response>) {
  return (input: RequestInfo | URL) =>
    String(input).includes(path) ? make(input) : fixtureFetch(input);
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('Story', () => {
  it('opens on the most recent session without being told which', async () => {
    // The picker's first entry is the newest session in the recording; a
    // first visit with no gsid has to land somewhere real rather than empty.
    renderPage();
    await waitFor(() => expect(screen.getByText(/2026-08-27 · 12r/)).toBeInTheDocument());
    expect(screen.getByRole('button', { name: /2026-08-27 · 12r/ })).toHaveAttribute('aria-pressed', 'true');
  });

  it('follows the gsid in the legacy path, not the newest session', async () => {
    // /story/session/:gsid is the hash the old page linked with, and a link
    // that silently lands on a different night is worse than a dead one.
    renderPage(fixtureFetch, '/story/session/153');
    await waitFor(() => expect(screen.getByRole('button', { name: /2026-08-26/ })).toHaveAttribute('aria-pressed', 'true'));
    expect(screen.getByRole('button', { name: /2026-08-27 · 12r/ })).toHaveAttribute('aria-pressed', 'false');
  });

  it('prints the narrative as prose and says a machine wrote it', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText(/The night's story was resilience/)).toBeInTheDocument());
    // The distinction the whole page is built on: this paragraph is a
    // description of aggregates, not a measurement of anything.
    expect(screen.getByText(/a description, not a measurement/)).toBeInTheDocument();
    expect(screen.getByText('comeback')).toBeInTheDocument();
  });

  it('shows the scoreboard map by map with both halves', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('etl_adlernest')).toBeInTheDocument());
    // Map 1 in the recording: 2–0, halves of 599 s and 213 s. Several maps
    // ended 2–0, so the assertion is on the pair, which is unique.
    expect(screen.getByText('9:59 / 3:33')).toBeInTheDocument();
    expect(screen.getAllByText('2 — 0').length).toBeGreaterThan(0);
    // Map 3 is a full hold, which draws 1–1 and must not read as a win.
    expect(screen.getByText('full hold')).toBeInTheDocument();
  });

  it('keeps the MVP and the top of the board apart', async () => {
    // MVP comes from waa_bayes with an eligibility floor; the board is
    // ordered by total_pwc. #783 landed this distinction on the old page
    // because the badge looks arbitrary without it.
    renderPage();
    await waitFor(() => expect(screen.getByText('mvp')).toBeInTheDocument());
    expect(screen.getByText(/two different metrics|picked by waa_bayes/)).toBeInTheDocument();
  });

  it('names the board leader when the MVP is somebody else', async () => {
    const swapped = {
      ...pwc,
      mvp: { ...(pwc as { mvp: { name: string } }).mvp, guid: 'OTHER123', name: 'somebody else' },
    };
    renderPage(withOverride('/storytelling/win-contribution', () =>
      Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(swapped) } as Response)));
    await waitFor(() => expect(screen.getByText(/picked by waa_bayes/)).toBeInTheDocument());
    // The sentence has to say who leads the board, or the reader is left
    // comparing two numbers with no idea which one ranked the list.
    // Matched by substring rather than by a regex built from data — the
    // name carries brackets and dots, and escaping them by hand is a worse
    // bug than the one it guards against.
    const leader = (pwc as { players: { name: string }[] }).players[0].name;
    // getAllByText: ancestors match a textContent predicate too, and the
    // question here is whether the sentence is on the page at all.
    expect(
      screen.getAllByText((_, el) => (el?.textContent ?? '').includes(`${leader} leads`)).length,
    ).toBeGreaterThan(0);
  });

  it('does not crash when the board is empty', async () => {
    // players[0] types as if it always hits; it does not when nobody met the
    // round floor, and the guard that saves it looked like dead code to the
    // scanner until the read became .at(0) (Codacy on #839).
    const noPlayers = { ...pwc, players: [], mvp: null };
    renderPage(withOverride('/storytelling/win-contribution', () =>
      Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(noPlayers) } as Response)));
    await waitFor(() => expect(screen.getByText('win contribution')).toBeInTheDocument());
    expect(screen.queryByText('mvp')).toBeNull();
  });

  it('draws both momentum series on one scale, one drawing per round', async () => {
    renderPage();
    await waitFor(() => expect(screen.getAllByRole('img', { name: /momentum/ }).length).toBeGreaterThan(0));
    const charts = screen.getAllByRole('img', { name: /momentum/ });
    // The recording holds 12 rounds; the sides swap between halves, so each
    // round is its own drawing and never one line across the session.
    expect(charts.length).toBe((momentum as { rounds: unknown[] }).rounds.length);
    // Two paths per chart — axis and allies — and both are drawn, since a
    // chart missing a series looks exactly like a team that never moved.
    expect(charts[0].querySelectorAll('path').length).toBe(2);
  });

  it('says a moment-less session is a result, not a gap', async () => {
    const empty = { ...moments, moments: [], total: 0 };
    renderPage(withOverride('/storytelling/moments', () =>
      Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(empty) } as Response)));
    await waitFor(() => expect(screen.getByText(/cleared the detector's thresholds/)).toBeInTheDocument());
  });

  it('labels the role boards as telemetry and distinguishes a failed one', async () => {
    // gravity/space/enabler/lurker come off the 200 ms tracker; an empty
    // board and an unmeasured one have the same shape on screen unless the
    // page says which it is.
    renderPage(withOverride('/storytelling/gravity', () =>
      Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) } as Response)));
    await waitFor(() => expect(screen.getByText(/from the 200 ms position tracker/)).toBeInTheDocument());
    expect(await screen.findByText(/the boards shown are complete, the missing ones are unknown/)).toBeInTheDocument();
    // …and the boards that DID answer are still shown.
    expect(screen.getByText('enabler')).toBeInTheDocument();
  });

  it('says how much of the synergy composite was defaulted', async () => {
    const defaulted = { ...synergy, defaulted_players_count: 2 };
    renderPage(withOverride('/storytelling/synergy', () =>
      Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(defaulted) } as Response)));
    await waitFor(() => expect(screen.getByText(/2 player\(s\) had no telemetry/)).toBeInTheDocument());
  });

  it('marks a section unavailable rather than empty when its endpoint fails', async () => {
    renderPage(withOverride('/storytelling/box-score', () =>
      Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) } as Response)));
    await waitFor(() => expect(screen.getByText(/scoreboard: unavailable/)).toBeInTheDocument());
    // The rest of the page still renders — one dead endpoint is not a dead
    // session.
    expect(await screen.findByText(/The night's story was resilience/)).toBeInTheDocument();
  });

  it('resolves a dated legacy link to that night, not the newest one', async () => {
    // /story/date/:date was a legacy hash, and the recording holds one
    // session on 2026-08-26 (gsid 153). Ignoring the date and showing the
    // newest session is the silent-wrong-answer this route exists to avoid.
    renderPage(fixtureFetch, '/story/date/2026-08-26');
    await waitFor(() => expect(screen.getByRole('button', { name: /2026-08-26/ })).toHaveAttribute('aria-pressed', 'true'));
  });

  it('asks which session when a date holds two of them', async () => {
    const twoOnOneDay = {
      ...scopes,
      sessions: [
        { ...(scopes as { sessions: Record<string, unknown>[] }).sessions[0], gaming_session_id: 900, start_date: '2026-08-27', end_date: '2026-08-27' },
        { ...(scopes as { sessions: Record<string, unknown>[] }).sessions[1], gaming_session_id: 901, start_date: '2026-08-27', end_date: '2026-08-27' },
      ],
    };
    renderPage(withOverride('/storytelling/scopes', () =>
      Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(twoOnOneDay) } as Response)),
    '/story/date/2026-08-27');
    await waitFor(() => expect(screen.getByText(/two sessions were played on 2026-08-27/)).toBeInTheDocument());
    // …and nothing is shown as if it were the answer.
    expect(screen.queryByText(/scoreboard/i)).toBeNull();
  });

  it('says a dated link fell outside the window instead of showing another night', async () => {
    renderPage(fixtureFetch, '/story/date/2019-01-01');
    await waitFor(() => expect(screen.getByText(/no session in the recent window/)).toBeInTheDocument());
  });

  it('shows each player note with the archetype that produced it', async () => {
    renderPage();
    const first = (playerNarratives as { player_narratives: { name: string; archetype: string; narrative: string }[] })
      .player_narratives[0];
    await waitFor(() => expect(screen.getAllByText(first.name).length).toBeGreaterThan(0));
    expect(screen.getAllByText(first.archetype).length).toBeGreaterThan(0);
    expect(screen.getByText(first.narrative)).toBeInTheDocument();
  });
});
