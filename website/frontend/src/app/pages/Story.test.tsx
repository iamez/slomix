import { fireEvent, render, screen, waitFor } from '@testing-library/react';
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
import momentumSession from './__fixtures__/api_storytelling_momentum_session.json';
import killMatrix from './__fixtures__/api_storytelling_kill_matrix.json';
import movement from './__fixtures__/api_storytelling_movement.json';
import uselessDefense from './__fixtures__/api_storytelling_useless_defense_deaths.json';
import kisFormula from './__fixtures__/api_storytelling_formula.json';
import pwcFormula from './__fixtures__/api_storytelling_win_contribution_formula.json';
import kisDetails from './__fixtures__/api_storytelling_kill_impact_details.json';

/** The recorded session 154 — 12 rounds over 6 maps, 2026-08-27.
 *
 * `api_storytelling_kill_impact_details.json` is the one recording that was
 * edited: kanii's 78 kills were cut to the first 25 so the fixture stays a
 * fifth of its recorded size. `summary` is left exactly as the server sent
 * it (78), which makes the pair a test in itself — a page that counted the
 * array instead of reading the summary would now disagree with the server.
 */
const BODIES: [string, unknown][] = [
  ['/storytelling/scopes', scopes],
  ['/storytelling/narrative', narrative],
  ['/storytelling/box-score', boxScore],
  ['/storytelling/moments', moments],
  ['/storytelling/momentum', momentum],
  ['/storytelling/momentum-session', momentumSession],
  ['/storytelling/win-contribution', pwc],
  ['/storytelling/win-contribution/formula', pwcFormula],
  ['/storytelling/kill-impact', kis],
  ['/storytelling/kill-impact/details', kisDetails],
  ['/storytelling/kill-matrix', killMatrix],
  ['/storytelling/movement', movement],
  ['/storytelling/useless-defense-deaths', uselessDefense],
  ['/storytelling/formula', kisFormula],
  ['/storytelling/synergy', synergy],
  ['/storytelling/gravity', gravity],
  ['/storytelling/space-created', space],
  ['/storytelling/enabler', enabler],
  ['/storytelling/lurker-profile', lurker],
  ['/storytelling/player-narratives', playerNarratives],
];

/** Match the PATH, not a substring of the URL.
 *
 * The first version of this matched with `url.includes(path)`, which was
 * fine while no endpoint was a prefix of another — and then
 * `/storytelling/momentum` started answering for
 * `/storytelling/momentum-session`, and `/storytelling/kill-impact` for
 * `/storytelling/kill-impact/details`. The page did not crash on nonsense
 * data; it crashed on plausible data from the wrong endpoint, which is the
 * harder failure to read. Compare the pathname exactly.
 */
function bodyFor(url: string): unknown | undefined {
  const path = new URL(url, 'http://test.local').pathname.replace(/^\/api/, '');
  return BODIES.find(([p]) => p === path)?.[1];
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

/** Replace one endpoint's response, keeping the rest of the corpus.
 *
 *  Same exact-path rule as bodyFor, and for the same reason: an override on
 *  `/storytelling/momentum` written with `includes` also silently replaced
 *  `/storytelling/momentum-session`, so a test aimed at one panel changed
 *  two. */
function withOverride(path: string, make: (input: RequestInfo | URL) => Promise<Response>) {
  return (input: RequestInfo | URL) => {
    const p = new URL(String(input), 'http://test.local').pathname.replace(/^\/api/, '');
    return p === path ? make(input) : fixtureFetch(input);
  };
}

function jsonOnce(body: unknown) {
  return () => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);
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

  it('says a session with no accepted rounds has no story, once', async () => {
    // Measured on sessions 151, 146, 145 and 128: every storytelling
    // endpoint resolves the same scope, so they 404 together with
    // "has no accepted rounds". Nine `unavailable` lines describe nine
    // broken panels; this is one fact about the session.
    renderPage((input) => {
      if (String(input).includes('/storytelling/scopes')) return fixtureFetch(input);
      return Promise.resolve({
        ok: false, status: 404,
        json: () => Promise.resolve({ detail: 'gaming_session_id=151 has no accepted rounds.' }),
      } as Response);
    });
    await waitFor(() => expect(screen.getByText(/no accepted rounds, so there is no story/)).toBeInTheDocument());
    expect(screen.queryByText(/moments: unavailable/)).toBeNull();
    expect(screen.queryByText(/synergy: unavailable/)).toBeNull();
  });

  it('still shows per-panel failures when only one endpoint is down', async () => {
    // The single-line message must not swallow a genuine partial failure.
    renderPage(withOverride('/storytelling/synergy', () =>
      Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) } as Response)));
    await waitFor(() => expect(screen.getByText(/synergy: unavailable/)).toBeInTheDocument());
    expect(screen.getByText(/The night's story was resilience/)).toBeInTheDocument();
  });

  it('draws both momentum series on one scale, one drawing per round', async () => {
    const { container } = renderPage();
    await waitFor(() => expect(screen.getAllByRole('img', { name: /momentum/ }).length).toBeGreaterThan(0));
    // Counted inside the per-round panel. A page-wide count answers about
    // the session curve too, which is a DIFFERENT drawing (by roster, not by
    // side) and would make this assertion drift by one for the wrong reason.
    const panel = container.querySelector('[data-parity="story.momentum"]')!;
    const charts = [...panel.querySelectorAll('svg')];
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

  it('keeps the server\'s 0–100 momentum domain instead of stretching the data', async () => {
    // The endpoint normalises onto 0–100 and both legacy charts pin their
    // axis there (story.js:638, :741). A min/max fit is a different claim:
    // this recording never goes below 47.5, so a stretched chart draws a
    // team at HALF strength sitting on the floor. Codex on #842.
    const { container } = renderPage();
    await waitFor(() => expect(screen.getByRole('img', { name: /across the session/ })).toBeInTheDocument());
    const svg = screen.getByRole('img', { name: /across the session/ });
    const ys = [...svg.querySelectorAll('path')]
      .flatMap((p) => [...(p.getAttribute('d') ?? '').matchAll(/[ML][\d.]+,([\d.]+)/g)].map((m) => Number(m[1])));
    const H = Number(svg.getAttribute('height'));
    const values = (momentumSession as { points: { team_a: number; team_b: number }[] }).points
      .flatMap((p) => [p.team_a, p.team_b]);
    const expected = (v: number) => H - 2 - (v / 100) * (H - 4);
    // The lowest point of the drawing is where the data's minimum belongs on
    // the fixed domain — NOT at the floor.
    expect(Math.max(...ys)).toBeCloseTo(expected(Math.min(...values)), 1);
    expect(Math.max(...ys)).toBeLessThan(H - 3);
    expect(Math.min(...ys)).toBeCloseTo(expected(Math.max(...values)), 1);
    // Same domain for the per-round sparklines, or one page shows two
    // different pictures of the same numbers.
    const round = container.querySelector('[data-parity="story.momentum"] svg')!;
    const rh = Number(round.getAttribute('height'));
    const rys = [...round.querySelectorAll('path')]
      .flatMap((p) => [...(p.getAttribute('d') ?? '').matchAll(/[ML][\d.]+,([\d.]+)/g)].map((m) => Number(m[1])));
    expect(Math.max(...rys)).toBeLessThan(rh - 3);
  });

  it('scales rather than clips on a narrow viewport', async () => {
    // maxWidth:100% shrinks the VIEWPORT; without a viewBox the coordinates
    // stay at 620 and the right-hand two thirds of the evening are simply
    // not drawn on a phone (the shell leaves ~319 px on a 375 px screen).
    renderPage();
    await waitFor(() => expect(screen.getByRole('img', { name: /across the session/ })).toBeInTheDocument());
    for (const svg of screen.getAllByRole('img', { name: /momentum/ })) {
      expect(svg.getAttribute('viewBox')).toBe(`0 0 ${svg.getAttribute('width')} ${svg.getAttribute('height')}`);
    }
  });

  it('draws the evening as one curve and names the rosters it belongs to', async () => {
    const { container } = renderPage();
    await waitFor(() => expect(screen.getByRole('img', { name: /across the session/ })).toBeInTheDocument());
    const svg = screen.getByRole('img', { name: /across the session/ });
    // Two lines, and one dashed marker per round boundary: the curve is
    // continuous, so without the markers a reader cannot tell where one
    // round ended and the next began.
    expect(svg.querySelectorAll('path').length).toBe(2);
    expect(svg.querySelectorAll('line').length)
      .toBe((momentumSession as { round_boundaries: unknown[] }).round_boundaries.length);
    // The lines mean nothing until you know who is in them.
    const panel = container.querySelector('[data-parity="story.momentum-session"]')!;
    for (const name of (momentumSession as { teams: { team_a: { players: string[] } } }).teams.team_a.players) {
      expect(panel.textContent).toContain(name);
    }
  });

  it('says which rounds the session curve leaves out', async () => {
    // The recording has nothing to leave out (unmapped_rounds 0), so this
    // sentence can only be produced by a payload that HAS a gap — and the
    // healthy fixture proves the sentence is not printed unconditionally.
    expect((momentumSession as { meta: { unmapped_rounds: number } }).meta.unmapped_rounds).toBe(0);
    const gapped = {
      ...momentumSession,
      meta: { ...(momentumSession as { meta: object }).meta, unmapped_rounds: 3, defaulted_players_count: 2 },
    };
    renderPage(withOverride('/storytelling/momentum-session', jsonOnce(gapped)));
    await waitFor(() => expect(screen.getByText(/not attributable to either roster/)).toBeInTheDocument());
    expect(screen.getByText(/scored at the default for lack of telemetry/)).toBeInTheDocument();
  });

  it('gives the server reason when no roster could be built', async () => {
    // A third shape, not an error: rounds exist, teams do not. Rendering
    // "unavailable" here would send a reader looking for an outage.
    renderPage(withOverride('/storytelling/momentum-session', jsonOnce({
      status: 'no_team_data', session_date: '2026-08-27', reason: 'no_pcs_rows', points: [],
    })));
    await waitFor(() => expect(screen.getByText(/no persistent teams could be built/)).toBeInTheDocument());
    expect(screen.getByText(/no_pcs_rows/)).toBeInTheDocument();
    expect(screen.queryByText(/session momentum: unavailable/)).toBeNull();
  });

  it('pairs killer with victim and leaves the diagonal blank', async () => {
    const { container } = renderPage();
    await waitFor(() => expect(screen.getByText(/kills paired/)).toBeInTheDocument());
    const panel = container.querySelector('[data-parity="story.kill-matrix"]')!;
    const rows = panel.querySelectorAll('tbody tr');
    const players = (killMatrix as { players: unknown[] }).players;
    expect(rows.length).toBe(players.length);
    // A player cannot duel himself: the diagonal carries the placeholder,
    // not a 0, because 0 would claim a duel that was never possible.
    const firstRow = rows[0].querySelectorAll('td');
    expect(firstRow[1].textContent).toBe('\u00b7');
    // A real pairing is the count the server sent, read at the position the
    // two axes put it — both keyed the same way, or the grid stops being
    // square. Picked from the payload rather than hardcoded, because only 18
    // of the 30 ordered pairs exist.
    const keys = (killMatrix as { players: { guid_short: string }[] }).players.map((p) => p.guid_short);
    const cells = (killMatrix as { cells: { killer: string; victim: string; kills: number }[] }).cells;
    const pair = cells.find((c) => keys.includes(c.killer) && keys.includes(c.victim))!;
    const row = rows[keys.indexOf(pair.killer)].querySelectorAll('td');
    expect(row[keys.indexOf(pair.victim) + 1].textContent).toBe(String(pair.kills));
    // A pair the server never emitted is 0 kills, not a gap: the GROUP BY
    // only produces rows for duels that happened.
    const missing = keys.flatMap((k) => keys.map((v) => [k, v] as const))
      .find(([k, v]) => k !== v && !cells.some((c) => c.killer === k && c.victim === v))!;
    const emptyRow = rows[keys.indexOf(missing[0])].querySelectorAll('td');
    expect(emptyRow[keys.indexOf(missing[1]) + 1].textContent).toBe('0');
  });

  it('says why the matrix is empty rather than drawing an empty grid', async () => {
    renderPage(withOverride('/storytelling/kill-matrix', jsonOnce({
      status: 'ok', available: false, reason: 'no_kill_data', players: [], cells: [],
    })));
    await waitFor(() => expect(screen.getByText(/no per-kill telemetry for this session/)).toBeInTheDocument());
    expect(screen.getByText(/no_kill_data/)).toBeInTheDocument();
  });

  it('prints a dash, not a zero, when a player has no alive time to divide by', async () => {
    // distance_per_min is null exactly when alive_ms is 0. Nobody in the
    // recording is (the fixture proves the healthy path renders numbers), so
    // the null case is forced — and 0 here would read as "stood still".
    const players = (movement as { players: { distance_per_min: number | null }[] }).players;
    expect(players.every((p) => p.distance_per_min != null)).toBe(true);
    const withNull = {
      ...movement,
      players: [{ ...players[0], distance_per_min: null, sprint_pct: null }, ...players.slice(1)],
    };
    const { container } = renderPage(withOverride('/storytelling/movement', jsonOnce(withNull)));
    await waitFor(() => expect(screen.getByText(/engine units, not metres/)).toBeInTheDocument());
    const panel = container.querySelector('[data-parity="story.movement"]')!;
    // The dash is asserted on the ROW, not on the panel: the panel's own
    // caption contains an em dash, so a page-wide `toContain` passed even
    // with the guard removed. (Found by reverting the guard and watching
    // this test stay green.)
    const name = (players[0] as unknown as { name: string }).name;
    const row = [...panel.querySelectorAll('.row')].find((r) => r.textContent?.startsWith(name))!;
    expect(row.textContent).toContain('\u2014per min');
    expect(row.textContent).not.toMatch(/\b0per min/);
    // The sprint share disappears with the same denominator rather than
    // printing 0%.
    expect(row.textContent).not.toContain('% sprint');
  });

  it('shows the defensive-death thresholds that decide the count', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText(/free\s+objective time, no trade/)).toBeInTheDocument());
    const t = (uselessDefense as { thresholds: { min_reinf_seconds: number; min_killer_health: number } }).thresholds;
    // Quoted from the payload, not kept as a constant here: the thresholds
    // are query parameters with defaults, and a page that hardcodes them
    // would keep saying 25/80 after the server stopped meaning it.
    expect(screen.getByText(new RegExp(`${t.min_reinf_seconds}s away`))).toBeInTheDocument();
    // ≥, not "above": the backend counts killer_health >= min_killer_health
    // (advanced_metrics.py `ski.killer_health >= $3`), so the caption must
    // agree with the count at exactly the bound (Codex on #842).
    expect(screen.getByText(new RegExp(`at ≥${t.min_killer_health} HP`))).toBeInTheDocument();
    expect(screen.queryByText(/above \d+ HP/)).toBeNull();
  });

  it('keeps the defensive board when the tracker boards are all unavailable', async () => {
    // The four role boards read the position tracker; this one is counted
    // from kill outcomes, so a tracker outage must not take it down with
    // them — that would hide a measurement that is perfectly available.
    const fail = () => Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) } as Response);
    renderPage((input: RequestInfo | URL) => {
      const p = new URL(String(input), 'http://test.local').pathname.replace(/^\/api/, '');
      return ['/storytelling/gravity', '/storytelling/space-created', '/storytelling/enabler', '/storytelling/lurker-profile'].includes(p)
        ? fail()
        : fixtureFetch(input);
    });
    await waitFor(() => expect(screen.getByText(/roles: unavailable/)).toBeInTheDocument());
    expect(screen.getByText(/free\s+objective time, no trade/)).toBeInTheDocument();
  });

  it('fetches a formula only when the reader opens it', async () => {
    const spy = vi.fn(fixtureFetch);
    renderPage(spy);
    await waitFor(() => expect(screen.getByText(/how is kis computed\?/)).toBeInTheDocument());
    const called = () => spy.mock.calls.some(([u]) => String(u).includes('/storytelling/formula'));
    expect(called()).toBe(false);
    fireEvent.click(screen.getByText(/how is kis computed\?/));
    await waitFor(() => expect(called()).toBe(true));
    // The retired term is published WITH its status, and hiding that would
    // leave a reader thinking push kills still score.
    await waitFor(() => expect(screen.getByText(/retired in kis-v5/)).toBeInTheDocument());
    expect(screen.getByText(/what it does and does not measure/)).toBeInTheDocument();
  });

  it('accounts for the objective-area term, which the payload spells as a flag', async () => {
    // The six objective-area kills in the recording are exactly the six
    // whose listed factors do not multiply out to total_impact, each short
    // by the published x1.40 (measured; Codex on #842). A breakdown whose
    // product cannot reach its own total is not a breakdown.
    const kills = (kisDetails as { kills: { is_objective_area: boolean; total_impact: number }[] }).kills;
    const objective = kills.filter((k) => k.is_objective_area);
    expect(objective.length).toBeGreaterThan(0);

    renderPage();
    const target = (kis as { players: { name: string; guid: string }[] }).players
      .find((p) => p.guid === (kisDetails as { player_guid: string }).player_guid)!;
    // Wait for the KIS ROW specifically: the formula toggles also carry
    // aria-expanded=false, so "some collapsed button exists" is true before
    // the board has rendered at all.
    const row = () => screen.getAllByRole('button', { expanded: false })
      .find((b) => b.textContent?.includes(target.name));
    await waitFor(() => expect(row()).toBeDefined());
    fireEvent.click(row()!);

    const value = (kisFormula as { objective_multipliers: { objective_area: { value: number } } })
      .objective_multipliers.objective_area.value;
    // The value is quoted from the formula endpoint, not kept as a constant
    // in the page — a constant is what goes stale when the scorer changes.
    await waitFor(() => expect(screen.getAllByText(new RegExp(`objective area ×${value}`)).length).toBeGreaterThan(0));
  });

  it('says when a score was soft-capped, in the breakdown and in the formula', async () => {
    // Above the threshold the total is NOT the product of the terms, so a
    // breakdown that stays silent about the cap reads as arithmetic that
    // does not work.
    const cap = (kisFormula as { soft_cap: { threshold: number; compression: number } }).soft_cap;
    const kills = (kisDetails as { kills: { total_impact: number }[] }).kills;
    expect(kills.some((k) => k.total_impact > cap.threshold)).toBe(true);

    renderPage();
    const target = (kis as { players: { name: string; guid: string }[] }).players
      .find((p) => p.guid === (kisDetails as { player_guid: string }).player_guid)!;
    // Wait for the KIS ROW specifically: the formula toggles also carry
    // aria-expanded=false, so "some collapsed button exists" is true before
    // the board has rendered at all.
    const row = () => screen.getAllByRole('button', { expanded: false })
      .find((b) => b.textContent?.includes(target.name));
    await waitFor(() => expect(row()).toBeDefined());
    fireEvent.click(row()!);
    await waitFor(() => expect(screen.getAllByText(/soft-capped/).length).toBeGreaterThan(0));

    // …and the panel that explains the score publishes both parameters.
    fireEvent.click(screen.getByText(/how is kis computed\?/));
    await waitFor(() => expect(screen.getByText('soft cap')).toBeInTheDocument());
    expect(screen.getByText(new RegExp(`above ${cap.threshold}`))).toBeInTheDocument();
    expect(screen.getByText(new RegExp(`×${cap.compression} above it`))).toBeInTheDocument();
  });

  it('opens one player\'s kills and prints only the multipliers that moved', async () => {
    renderPage();
    const kisPlayers = (kis as { players: { name: string; guid: string }[] }).players;
    const target = kisPlayers.find((p) => p.guid === (kisDetails as { player_guid: string }).player_guid)!;
    await waitFor(() => expect(screen.getAllByText(new RegExp(target.name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))).length).toBeGreaterThan(0));
    fireEvent.click(screen.getAllByRole('button', { expanded: false })
      .find((b) => b.textContent?.includes(target.name))!);
    // The summary line is the SERVER's count. The fixture's kills array was
    // truncated to 25 of 78, so a page that counted the array instead of
    // reading the summary prints 25 here and fails.
    const summary = (kisDetails as { summary: { kills: number } }).summary;
    await waitFor(() => expect(screen.getByText(new RegExp(`${summary.kills} kills`))).toBeInTheDocument());
    // Nine multipliers per kill, mostly x1.0; printing them all buries the
    // two that did the work.
    expect(screen.queryByText(/class ×1 · distance ×1/)).toBeNull();
  });

  it('renders every published reinforcement tier, not a count of them', async () => {
    // The endpoint publishes seven (cutoff, multiplier) pairs; "7 tiers"
    // reduces five of them to hearsay, so a reader could not reproduce the
    // factor (Codex on #842). Every cutoff is quoted from the fixture, and
    // the open-ended last tier (max_reinf_seconds: null) is labelled from the
    // PREVIOUS tier's cutoff rather than a constant.
    renderPage();
    await waitFor(() => expect(screen.getByText(/how is kis computed\?/)).toBeInTheDocument());
    fireEvent.click(screen.getByText(/how is kis computed\?/));
    const tiers = (kisFormula as {
      oksii_multipliers: { reinforcement: { tiers: { max_reinf_seconds: number | null; multiplier: number }[] } };
    }).oksii_multipliers.reinforcement.tiers;
    expect(tiers.length).toBe(7);
    await waitFor(() => expect(screen.getByText(`≤ ${tiers[0].max_reinf_seconds}s`)).toBeInTheDocument());
    for (const t of tiers) {
      if (t.max_reinf_seconds != null) {
        expect(screen.getByText(`≤ ${t.max_reinf_seconds}s`)).toBeInTheDocument();
      }
      expect(screen.getAllByText(`×${t.multiplier}`).length).toBeGreaterThan(0);
    }
    const lastCutoff = tiers[tiers.length - 2].max_reinf_seconds;
    expect(screen.getByText(`> ${lastCutoff}s`)).toBeInTheDocument();
  });

  it('shows the alive sub-terms with their published thresholds', async () => {
    // solo_clutch and outnumbered each publish the threshold that decides
    // which applies; the head's "×2 / ×1.5" alone left both unstated
    // (Codex on #842, the same thread as the tiers).
    renderPage();
    await waitFor(() => expect(screen.getByText(/how is kis computed\?/)).toBeInTheDocument());
    fireEvent.click(screen.getByText(/how is kis computed\?/));
    const alive = (kisFormula as {
      oksii_multipliers: { alive: { solo_clutch: { threshold: string }; outnumbered: { threshold: string } } };
    }).oksii_multipliers.alive;
    await waitFor(() => expect(screen.getByText('solo clutch')).toBeInTheDocument());
    expect(screen.getByText(alive.solo_clutch.threshold)).toBeInTheDocument();
    expect(screen.getByText(alive.outnumbered.threshold)).toBeInTheDocument();
  });

  it('declares the formula half unavailable rather than quietly dropping its factors', async () => {
    // /storytelling/kill-impact/details succeeded, /storytelling/formula did
    // not — before this guard the breakdown rendered anyway, minus the
    // objective-area factor and the soft-cap marker, with no sign anything
    // was missing (Codex on #842). A failed request is a FAILURE (red
    // unavailable), never a grey absence.
    renderPage(withOverride('/storytelling/formula', () =>
      Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) } as Response)));
    const target = (kis as { players: { name: string; guid: string }[] }).players
      .find((p) => p.guid === (kisDetails as { player_guid: string }).player_guid)!;
    const row = () => screen.getAllByRole('button', { expanded: false })
      .find((b) => b.textContent?.includes(target.name));
    await waitFor(() => expect(row()).toBeDefined());
    fireEvent.click(row()!);
    await waitFor(() => expect(screen.getByText(/the formula request failed\): unavailable/)).toBeInTheDocument());
    // The rows themselves still render — their multipliers come from the
    // details payload, which answered.
    const summary = (kisDetails as { summary: { kills: number } }).summary;
    expect(screen.getByText(new RegExp(`${summary.kills} kills`))).toBeInTheDocument();
    // …but no annotation is invented from the formula that never arrived.
    expect(screen.queryByText(/objective area ×/)).toBeNull();
    expect(screen.queryByText(/soft-capped/)).toBeNull();
  });

  it('keeps the breakdown pending until the formula answers too', async () => {
    // The breakdown depends on two requests. Gating only on the details one
    // meant a window where the rows rendered with the formula still in
    // flight — the same incomplete arithmetic as a failure, just transient.
    // A formula fetch that never settles pins the window open.
    renderPage(withOverride('/storytelling/formula', () => new Promise<Response>(() => { /* never settles */ })));
    const target = (kis as { players: { name: string; guid: string }[] }).players
      .find((p) => p.guid === (kisDetails as { player_guid: string }).player_guid)!;
    const row = () => screen.getAllByRole('button', { expanded: false })
      .find((b) => b.textContent?.includes(target.name));
    await waitFor(() => expect(row()).toBeDefined());
    fireEvent.click(row()!);
    const pending = () => screen.queryAllByText(
      (_, el) => (el?.textContent ?? '') === `${target.name}'s kills…`,
    ).length;
    await waitFor(() => expect(pending()).toBeGreaterThan(0));
    // ⛔ The line above alone is satisfiable by the DETAILS request's own
    // transient pending window — the first mutation run proved it: with the
    // gate reverted to q.isPending only, this test still passed. So let the
    // details request settle (its fixture resolves in microtasks; 150 ms is
    // margin) and assert the panel is STILL pending — a state only the
    // formula gate can hold open.
    await new Promise((r) => setTimeout(r, 150));
    expect(pending()).toBeGreaterThan(0);
    const summary = (kisDetails as { summary: { kills: number } }).summary;
    expect(screen.queryByText(new RegExp(`${summary.kills} kills`))).toBeNull();
  });

  it('states the movement cutoff when the session has more than ten tracked players', async () => {
    // The recording holds 6 players, below the cutoff — so first prove the
    // line is not printed unconditionally…
    const players = (movement as { players: { guid_short: string; name: string }[] }).players;
    expect(players.length).toBeLessThanOrEqual(10);
    renderPage();
    await waitFor(() => expect(screen.getByText(/engine units, not metres/)).toBeInTheDocument());
    expect(screen.queryByText(/showing the top/)).toBeNull();

    // …then a 12-player night (substitutes) forces it: without the line the
    // two players below the slice read as having no telemetry at all
    // (Codex on #842). Counts are measured from the payload, not hardcoded
    // in the page.
    const twelve = Array.from({ length: 12 }, (_, i) => ({
      ...players[0], guid_short: `SYNTH${i}`, name: `player${i}`,
    }));
    renderPage(withOverride('/storytelling/movement', jsonOnce({ ...movement, players: twelve })));
    await waitFor(() => expect(
      screen.getByText(/showing the top 10 of 12 tracked players by total distance/),
    ).toBeInTheDocument());
  });

  it('names each dashed round boundary on the session curve, in order', async () => {
    // The payload sends map_name and round_number for every boundary; the
    // first render consumed them only as React keys, leaving indistinguishable
    // dashed lines (Codex on #842). The legend is keyed by position — the
    // boundaries arrive sorted by x_ms — so the joined string also asserts
    // the ORDER.
    const { container } = renderPage();
    await waitFor(() => expect(screen.getByRole('img', { name: /across the session/ })).toBeInTheDocument());
    const expected = (momentumSession as { round_boundaries: { map_name: string; round_number: number }[] })
      .round_boundaries.map((b) => `${b.map_name} R${b.round_number}`).join(' · ');
    const panel = container.querySelector('[data-parity="story.momentum-session"]')!;
    expect(panel.textContent).toContain(`dashed lines, left → right: ${expected}`);
  });

  it('does not claim an empty costly-deaths board is a measured zero', async () => {
    // players: [] is also what a session with no storytelling_kill_impact
    // rows returns — the KIS precompute is caller-triggered and public reads
    // never trigger it — and the wire carries no coverage field to tell an
    // unscored night from a clean one (Codex on #842; a backend contract
    // gap). The wording may claim only what the wire can back.
    const empty = { ...uselessDefense, players: [] };
    renderPage(withOverride('/storytelling/useless-defense-deaths', jsonOnce(empty)));
    await waitFor(() => expect(screen.getByText(/no defender cleared both thresholds among the scored kills/)).toBeInTheDocument());
    expect(screen.getByText(/cannot say whether this session's kills were scored at all/)).toBeInTheDocument();
    expect(screen.queryByText(/not a missing measurement/)).toBeNull();
  });

  it('renders the published MVP selection rules, not just the description', async () => {
    // eligibility, ordered tiebreakers and the fallback decide who CAN win
    // and how ties resolve; without them the disclosure cannot reproduce the
    // badge for a player near the participation floor (Codex on #842).
    renderPage();
    await waitFor(() => expect(screen.getByText(/how is pwc computed\?/)).toBeInTheDocument());
    fireEvent.click(screen.getByText(/how is pwc computed\?/));
    const mvp = (pwcFormula as { mvp: { eligibility: string; tiebreakers: string[]; fallback: string } }).mvp;
    // Substring matchers, not regexes built from data: eligibility carries
    // parentheses and a division slash.
    await waitFor(() => expect(
      screen.getAllByText((_, el) => (el?.textContent ?? '').includes(mvp.eligibility)).length,
    ).toBeGreaterThan(0));
    // ", then" is the joiner because the array is ORDERED — asserting the
    // joined string pins the order, not just membership.
    expect(
      screen.getAllByText((_, el) => (el?.textContent ?? '').includes(mvp.tiebreakers.join(', then '))).length,
    ).toBeGreaterThan(0);
    expect(
      screen.getAllByText((_, el) => (el?.textContent ?? '').includes(mvp.fallback)).length,
    ).toBeGreaterThan(0);
  });
});
