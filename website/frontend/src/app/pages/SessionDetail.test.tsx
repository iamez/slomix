import { fireEvent, render, screen, waitFor } from '@testing-library/react';
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
// Session 151 answers 200 with the SHORT form of three endpoints — the
// fields the long form carries are absent, not zero. One session's corpus
// could never show that, and typing from it produced a page that crashed on
// three of the four older sessions it was first pointed at.
import mvp151 from './__fixtures__/api_session_151_mvp.json';
import verdicts151 from './__fixtures__/api_session_151_verdicts.json';
import goodNight151 from './__fixtures__/api_session_151_good_night.json';
import bestLives from './__fixtures__/api_storytelling_best_lives.json';
// Stats 2.0 (R2 recordings): 154 in full, 80 without KIS, teams or many awards.
import basics from './__fixtures__/api_stats_session_gaming_session_id_basics.json';
import awards from './__fixtures__/api_stats_session_gaming_session_id_awards.json';
import basics80 from './__fixtures__/api_stats_session_gaming_session_id_basics_80.json';
import awards80 from './__fixtures__/api_stats_session_gaming_session_id_awards_80.json';
import synergy from './__fixtures__/api_storytelling_synergy.json';
import synergy80 from './__fixtures__/api_storytelling_synergy_80.json';
import trades154 from './__fixtures__/api_proximity_trades_player_stats_session_154.json';
import type { SessionAwards, SessionBasics } from '../lib/types';

const basicsFull = basics satisfies SessionBasics;
const awardsFull = awards satisfies SessionAwards;
const basicsThin = basics80 satisfies SessionBasics;
const awardsThin = awards80 satisfies SessionAwards;

/** Session 154, recorded 2026-08-29: 12 rounds, 6 maps, 6 players, 5–7. */
const BODIES: [string, unknown][] = [
  ['/detail', detail],
  ['/rounds', rounds],
  ['/mvp', mvp],
  ['/verdicts', verdicts],
  ['/good-night', goodNight],
  ['/storytelling/best-lives', bestLives],
  ['/basics', basicsFull],
  ['/awards', awardsFull],
  ['/api/sessions', sessions],
  // R4 tabs: synergy is session-keyed, the trade table date-keyed (154 = 2026-08-27).
  ['/storytelling/synergy', synergy],
  ['/proximity/trades/player-stats', trades154],
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

/** Stats 2.0 moved the scoreboard, team totals, lives, form and top-dpm
 *  panels behind a "more" expander (docs/design/18 §C); the tests that
 *  read them open it first. */
async function openMore() {
  // Every collapsed "more" on the page: a test that renders twice has two.
  // A page that never reaches the summary (404, failure, another tab) has
  // none — then there is nothing to open and the test goes on.
  let buttons: HTMLElement[] = [];
  try {
    buttons = await screen.findAllByRole('button', { name: /more about the night ▸/ }, { timeout: 1500 });
  } catch {
    return; // nothing to open on this page
  }
  for (const b of buttons) fireEvent.click(b);
}


describe('SessionDetail', () => {
  it('opens on the scoreboard with the stopwatch result', async () => {
    renderPage();
    await openMore();
    await waitFor(() => expect(screen.getByText('Team A 5 — 7 Team B')).toBeInTheDocument());
    expect(screen.getAllByText('etl_adlernest').length).toBeGreaterThan(0);
    // A full hold is not a time, and the recording has one.
    expect(screen.getAllByText(/fullhold/).length).toBeGreaterThan(0);
  });

  it('says scoring is unavailable rather than showing a 0–0', async () => {
    // The 2026-08-12 bug: an unpairable session rendered as a real draw.
    const noScoring = { ...detail, scoring: { ...(detail as { scoring: object }).scoring, available: false, maps: [] } };
    renderPage(withOverride('/detail', () => json(noScoring)));
    await openMore();
    await waitFor(() => expect(screen.getByText(/could not be paired, which is not the same as a 0–0/)).toBeInTheDocument());
  });

  it('shows the night score with the components that produced it', async () => {
    renderPage();
    await openMore();
    await waitFor(() => expect(screen.getByText('night score')).toBeInTheDocument());
    // A bare index invites an argument nobody can settle; the seven
    // components are the argument.
    expect(screen.getByText('balance')).toBeInTheDocument();
    expect(screen.getByText('tension')).toBeInTheDocument();
    expect(screen.getByText(String((goodNight as { score: number }).score))).toBeInTheDocument();
  });

  it('separates "not computed" from a low night score', async () => {
    renderPage(withOverride('/good-night', () => json({ ...goodNight, available: false })));
    await openMore();
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
    await openMore();
    await waitFor(() => expect(screen.getByText(/first night — no baseline yet/)).toBeInTheDocument());
  });

  it('calls the MVP panel a vote and keeps it away from the model', async () => {
    const voted = {
      ...mvp,
      total_votes: 3,
      candidates: [{ ...(mvp as { candidates: Record<string, unknown>[] }).candidates[0], votes: 3, vote_pct: 100 }],
    };
    renderPage(withOverride('/mvp', () => json(voted)));
    await openMore();
    await waitFor(() => expect(screen.getByText(/a vote, not a rating/)).toBeInTheDocument());
  });

  it('says an empty ballot is empty rather than showing a tie', async () => {
    renderPage();
    await openMore();
    await waitFor(() => expect(screen.getByText(/an empty ballot, not a tie/)).toBeInTheDocument());
  });

  it('survives the short form every one of these endpoints can return', async () => {
    // Measured on sessions 151, 146 and 128: an unavailable good-night is
    // `{status, available: false, gaming_session_id}` — no score, no hours,
    // no components — verdicts drop `baseline`, and the MVP panel drops
    // `total_votes` entirely. The page read `total_votes === 0`, which is
    // false for `undefined`, fell through to the render path and crashed the
    // whole route on `figure(undefined)`.
    renderPage((input) => {
      const url = String(input);
      if (url.includes('/mvp')) return json(mvp151);
      if (url.includes('/verdicts')) return json(verdicts151);
      if (url.includes('/good-night')) return json(goodNight151);
      return fixtureFetch(input);
    });
    await openMore();
    await waitFor(() => expect(screen.getByText('Team A 5 — 7 Team B')).toBeInTheDocument());
    // Each of the three says what it is rather than throwing or inventing a 0.
    await waitFor(() => expect(screen.getByText(/different from a low score/)).toBeInTheDocument());
    expect(screen.getByText(/nobody in this session has a baseline/)).toBeInTheDocument();
    expect(screen.getByText(/an empty ballot, not a tie/)).toBeInTheDocument();
  });

  it('survives a session whose scoring block is only {available:false}', async () => {
    // The handler's own unavailable payload — no team names, no maps array.
    const bare = { ...detail, scoring: { available: false }, team_matrix: { available: false, reason: 'no_teams' } };
    renderPage(withOverride('/detail', () => json(bare)));
    await openMore();
    await waitFor(() => expect(screen.getByText(/could not be paired/)).toBeInTheDocument());
    expect(screen.getByText(/lua roster for every round/)).toBeInTheDocument();
  });

  it('tells a session with no counted rounds apart from a broken one', async () => {
    // Session 145 on dev: six rounds, every one orphan_r2, so /detail
    // answers 404 while /rounds lists all six. "unavailable" would send the
    // reader hunting a bug that is not there.
    renderPage(withOverride('/detail', () =>
      Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({ detail: 'Session not found' }) } as Response)));
    await openMore();
    await waitFor(() => expect(screen.getByText(/no counted rounds in this session/)).toBeInTheDocument());
    expect(screen.queryByText(/session: unavailable/)).toBeNull();
  });

  it('still says unavailable when the endpoint actually fails', async () => {
    renderPage(withOverride('/detail', () =>
      Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) } as Response)));
    await openMore();
    await waitFor(() => expect(screen.getByText(/session: unavailable/)).toBeInTheDocument());
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
    await openMore();
    await waitFor(() => expect(screen.getByText(/11 of 12 count toward totals/)).toBeInTheDocument());
    // Shown, not hidden: a player who played it has to be able to find it.
    // RoundsTable (the retired /rounds page's table, now this tab) marks it
    // with its status and keeps the row.
    expect(screen.getByText(/cancelled · not counted/)).toBeInTheDocument();
    expect(screen.getAllByText(/^R[12]$/).length).toBe((rounds as { rounds: unknown[] }).rounds.length);
    // The two views of the same data — by round, one player — are here too.
    expect(screen.getByRole('button', { name: 'one player' })).toHaveAttribute('aria-pressed', 'false');
  });

  it('shows the per-player totals on their own tab', async () => {
    renderPage(fixtureFetch, '/session-detail/154/players');
    await openMore();
    await waitFor(() => expect(screen.getByText(/sorted by dpm/)).toBeInTheDocument());
    const first = (detail as { players: { player_name: string }[] }).players[0];
    expect(screen.getAllByText(first.player_name).length).toBeGreaterThan(0);
  });

  it('does not fetch the session list when the URL already names a session', async () => {
    // Thirty sessions loaded to be ignored is the same waste the story
    // page's SSR panel was called out for; the list exists only to resolve
    // a DATE.
    const spy = vi.fn(fixtureFetch);
    renderPage(spy);
    await openMore();
    await waitFor(() => expect(screen.getByText('Team A 5 — 7 Team B')).toBeInTheDocument());
    expect(spy.mock.calls.some(([u]) => String(u).includes('/api/sessions?'))).toBe(false);
  });

  it('resolves a dated legacy link to that session', async () => {
    // /session-detail/date/:date is a legacy hash. The recording's newest
    // session is 154 on 2026-08-27; the link has to land there because of
    // the date, not because it is the newest.
    renderPage(fixtureFetch, '/session-detail/date/2026-08-27');
    await openMore();
    await waitFor(() => expect(screen.getByText('Team A 5 — 7 Team B')).toBeInTheDocument());
  });

  it('asks which session when one date holds two', async () => {
    const twoOnOneDay = [
      { ...(sessions as Record<string, unknown>[])[0], session_id: 900, date: '2026-08-27' },
      { ...(sessions as Record<string, unknown>[])[0], session_id: 901, date: '2026-08-27' },
    ];
    renderPage(withOverride('/api/sessions', () => json(twoOnOneDay)), '/session-detail/date/2026-08-27');
    await openMore();
    await waitFor(() => expect(screen.getByText(/two sessions were played on 2026-08-27/)).toBeInTheDocument());
    expect(screen.queryByText('Team A 5 — 7 Team B')).toBeNull();
  });

  it('marks a section unavailable rather than empty when its endpoint fails', async () => {
    renderPage(withOverride('/verdicts', () =>
      Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) } as Response)));
    await openMore();
    await waitFor(() => expect(screen.getByText(/form: unavailable/)).toBeInTheDocument());
    // …and the rest of the session still renders.
    expect(screen.getByText('Team A 5 — 7 Team B')).toBeInTheDocument();
  });

  it('shows the biggest single life, which the session totals flatten away', async () => {
    const { container } = renderPage();
    await openMore();
    const lives = (bestLives as { lives: { name: string; kills: number; map_name: string; life_seconds: number }[] }).lives;
    await waitFor(() => expect(container.querySelector('[data-parity="session.lives"]')).not.toBeNull());
    const panel = container.querySelector('[data-parity="session.lives"]')!;
    // Every card, not just the best one: the strip is the point, and a page
    // that renders only lives[0] looks identical for a five-card night.
    expect(panel.querySelectorAll('a').length).toBe(lives.length);
    const first = lives[0];
    expect(panel.textContent).toContain(String(first.kills));
    expect(panel.textContent).toContain(first.map_name);
    expect(panel.textContent).toContain(`${first.life_seconds}s alive`);
  });

  it('states the lives cutoff from the payload, and stays silent on older wire shapes', async () => {
    // The endpoint's `total` is len(lives) AFTER the limit — a total that is
    // not a total — so the disclosure reads qualifying_total, counted before
    // the cut (Codex on #842, fourth cutoff of the family). The recorded
    // session really had 51 qualifying lives behind its top five, measured
    // live 2026-08-31; all three numbers come from the fixture.
    const f = bestLives as { lives: unknown[]; qualifying_total: number; min_kills: number };
    expect(f.qualifying_total).toBeGreaterThan(f.lives.length);
    renderPage();
    await openMore();
    await waitFor(() => expect(screen.getByText(
      new RegExp(`showing the top ${f.lives.length} of ${f.qualifying_total} lives with ≥${f.min_kills} kills`),
    )).toBeInTheDocument());

    // A response recorded before the fields existed omits them — an absent
    // key is not 0, and the line must vanish rather than crash or claim
    // "of undefined". Scoped to THIS render's container: the first tree
    // above is still mounted and carries the line, so a screen-wide
    // queryByText would look at the wrong page and could never fail.
    const { qualifying_total: _qt, min_kills: _mk, ...old } = bestLives as Record<string, unknown>;
    const second = renderPage(withOverride('/storytelling/best-lives', () => json(old)));
    await openMore();
    await waitFor(() => expect(second.container.querySelector('[data-parity="session.lives"]')).not.toBeNull());
    expect(second.container.textContent).toContain('s alive');
    expect(second.container.textContent).not.toContain('showing the top');

    // And when everything qualifying is already on screen there is no cutoff
    // to disclose.
    const third = renderPage(withOverride('/storytelling/best-lives', () =>
      json({ ...(bestLives as object), qualifying_total: f.lives.length })));
    await openMore();
    await waitFor(() => expect(third.container.querySelector('[data-parity="session.lives"]')).not.toBeNull());
    expect(third.container.textContent).toContain('s alive');
    expect(third.container.textContent).not.toContain('showing the top');

    // The threshold is QUOTED, not hardcoded — the fixture's 3 equals the
    // backend constant, so only a moved value can tell the two apart (a
    // fixture cannot fail on a value it does not contain).
    const fourth = renderPage(withOverride('/storytelling/best-lives', () =>
      json({ ...(bestLives as object), min_kills: 4 })));
    await openMore();
    await waitFor(() => expect(fourth.container.textContent).toContain('≥4 kills'));
  });

  it('tells an empty night apart from a failed request', async () => {
    // The legacy panel did neither — it returned early on both, so "nobody
    // had a standout life" and "the endpoint is down" looked the same.
    renderPage(withOverride('/storytelling/best-lives', () => json({ status: 'ok', lives: [], total: 0 })));
    await openMore();
    // The wording must not claim telemetry was present: lives:[] is also what
    // an untracked night returns, and the wire carries no coverage field to
    // tell the two apart (Codex on #842 — a backend contract gap).
    await waitFor(() => expect(screen.getByText(/no tracked life in this session cleared the minimum/)).toBeInTheDocument());
    expect(screen.getByText(/cannot say how much of the night was tracked/)).toBeInTheDocument();
    expect(screen.queryByText(/the best lives: unavailable/)).toBeNull();

    renderPage(withOverride('/storytelling/best-lives', () =>
      Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) } as Response)));
    await openMore();
    await waitFor(() => expect(screen.getByText(/the best lives: unavailable/)).toBeInTheDocument());
  });

  it('gives two near-identical lives distinct keys', async () => {
    // :432 (Codex on #842): same player, same map, same round, durations
    // rounding to the same second — the composite key collapsed and React
    // reused one card for both. The index joined the key; the guard is the
    // absence of React's duplicate-key warning, which is the only observable
    // the collision has.
    const twin = (kills: number) => ({
      guid: 'AAAA0001', name: 'twin', map_name: 'supply', round_number: 1,
      life_seconds: 42, kills, gibs: 0, started_at: '20:00:00',
    });
    const errors: string[] = [];
    const orig = console.error;
    vi.spyOn(console, 'error').mockImplementation((...args: unknown[]) => {
      errors.push(String(args[0]));
      orig.apply(console, args as []);
    });
    try {
      renderPage(withOverride('/api/storytelling/best-lives', () => json({
        status: 'ok', available: true, total: 2, qualifying_total: 2, min_kills: 3,
        lives: [twin(5), twin(4)],
      })));
      await openMore();
      await waitFor(() => expect(screen.getAllByText('twin').length).toBeGreaterThan(0));
      expect(errors.filter((e) => e.includes('same key')).length).toBe(0);
    } finally {
      vi.mocked(console.error).mockRestore();
    }
  });

});


describe('SessionDetail — stats 2.0 summary', () => {
  it('opens on the head: BOX score, the map strip with levelshots, and the figures', async () => {
    const { container } = renderPage();
    await waitFor(() => expect(container.querySelector('[data-parity="session.head"]')).toBeTruthy());
    // BigScore from basics.teams — team a accent, team b warm; the scores as two numbers, not a string.
    await waitFor(() => expect(screen.getByText('team a')).toBeInTheDocument());
    expect(screen.getByText('5')).toBeInTheDocument();
    expect(screen.getByText('7')).toBeInTheDocument();
    // Six maps, each with its levelshot resolved by lib/maps.
    const imgs = container.querySelectorAll('[data-parity="session.maps"] img');
    expect(imgs.length).toBe(detail.matches.length);
    expect(imgs[0].getAttribute('src')).toMatch(/^\/assets\/maps\/levelshots\//);
    // Figures: counted rounds and the KIS coverage read from the basics payload.
    const figures = container.querySelector('[data-parity="session.figures"]');
    expect(figures?.textContent).toContain('rounds counted');
    expect(figures?.textContent).toContain('kills with KIS');
  });

  it('the map strip pairs a scoring row with its own map, never with a neighbour by index', async () => {
    // Drop the second scoring row (etl_sp_delivery). Pairing by index would
    // hand supply's score to delivery and shift every later map by one;
    // pairing by map name leaves delivery a dash and keeps supply's score.
    type Scored = { map: string; team_a_points: number; team_b_points: number };
    const scoring = (detail as { scoring: { maps: Scored[] } }).scoring;
    const kept = scoring.maps.filter((_, i) => i !== 1);
    const shifted = { ...detail, scoring: { ...scoring, maps: kept } };
    const { container } = renderPage(withOverride('/detail', () => json(shifted)));
    const strip = await waitFor(() => {
      const el = container.querySelector('[data-parity="session.maps"]');
      expect(el).toBeTruthy();
      return el as HTMLElement;
    });
    const rows = [...strip.querySelectorAll('.row')].map((r) => r.textContent ?? '');
    // A dash alone — not a score (the score text also carries a dash between two numbers).
    expect(rows[1]).not.toMatch(/\d+ — \d+/);
    expect(rows[1]).toMatch(/—$/);
    const supply = kept[1];
    expect(rows[2]).toContain(`${supply.team_a_points} — ${supply.team_b_points}`);
  });

  it('the basics table: one row per player, sorted by dpm, every header carrying its definition', async () => {
    const { container } = renderPage();
    const table = await waitFor(() => {
      const el = container.querySelector('[data-parity="session.basics"]');
      expect(el).toBeTruthy();
      return el as HTMLElement;
    });
    await openMore();
    const first = [...basicsFull.players].sort((a, b) => b.dpm - a.dpm)[0];
    await waitFor(() => expect(screen.getAllByText(first.name).length).toBeGreaterThan(0));
    // The definitions ride on the headers.
    expect(screen.getByRole('button', { name: /^denied %/ })).toHaveAttribute('title', expect.stringMatching(/denied to opponents/));
    expect(screen.getByRole('button', { name: /^hs %/ })).toHaveAttribute('title', expect.stringMatching(/never headshot kills/));
    expect(screen.getByRole('button', { name: /^kis$|^kis ▾|^kis ▴/ })).toHaveAttribute('title', expect.stringMatching(/not a ranking/));
    // 17 columns; uk is the legacy Useful Kills column, useless its own (owner, 2026-09-03).
    // The definition is the Lua writer's (half a spawn cycle ahead), not the legacy tooltip's.
    expect(table.querySelectorAll('.row')[0].children.length).toBe(17);
    expect(screen.getByRole('button', { name: /^uk$|^uk ▾|^uk ▴/ })).toHaveAttribute('title', expect.stringMatching(/^useful kills — the victim had at least half the spawn cycle/));
    expect(screen.getByRole('button', { name: /^useless/ })).toHaveAttribute('title', expect.stringMatching(/next spawn wave/));
    // The expander names the player, not the guid, though the cell is a Link.
    expect(screen.getByRole('button', { name: `weapons for ${first.name}` })).toBeInTheDocument();
    // No unmeasured cell prints undefined/NaN.
    expect(table.textContent).not.toMatch(/undefined|NaN/);
  });

  it('a header click re-sorts the basics', async () => {
    renderPage();
    const kills = await screen.findByRole('button', { name: /^dmg/ });
    fireEvent.click(kills);
    expect(kills).toHaveAttribute('aria-sort', 'descending');
    fireEvent.click(kills);
    expect(kills).toHaveAttribute('aria-sort', 'ascending');
  });

  it('the awards read as sentences with the nickname and the engine name behind it', async () => {
    const { container } = renderPage();
    await waitFor(() => expect(container.querySelector('[data-parity="session.awards"]')).toBeTruthy());
    const dealer = awardsFull.categories.flatMap((c) => c.awards).find((a) => a.nickname === 'Damage Dealer');
    expect(dealer).toBeDefined();
    await waitFor(() => expect(screen.getByText('Damage Dealer')).toBeInTheDocument());
    expect(screen.getByText('Damage Dealer').closest('span')).toHaveAttribute('title', 'Most damage given');
    expect(screen.getByText(/Top Fragger/)).toBeInTheDocument();
  });

  it('the thin evening (80): no KIS says so, the kis cells are dashes, the score is not attributed', async () => {
    const { container } = renderPage(
      (input) => {
        const url = String(input);
        if (url.includes('/basics')) return json(basicsThin);
        if (url.includes('/awards')) return json(awardsThin);
        return fixtureFetch(input);
      },
    );
    await waitFor(() => expect(container.querySelector('[data-parity="session.basics"]')).toBeTruthy());
    await waitFor(() => expect(screen.getByText(/KIS is not covered for this session/)).toBeInTheDocument());
    expect(basicsThin.coverage.kis_covered).toBe(false);
    expect(container.querySelector('[data-parity="session.basics"]')?.textContent).not.toMatch(/undefined|NaN/);
    // 80 has teams; the awards are the three computed ones plus one round's engine awards.
    expect(screen.getByText(/1 of 8 rounds carried engine awards/)).toBeInTheDocument();
  });

  it('the old panels live behind "more" and come back on a click', async () => {
    renderPage();
    const more = await screen.findByRole('button', { name: /more about the night ▸/ });
    expect(screen.queryByText('scoreboard')).toBeNull();
    fireEvent.click(more);
    await waitFor(() => expect(screen.getByText('scoreboard')).toBeInTheDocument());
    expect(screen.getByText('Team A 5 — 7 Team B')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /more about the night ▾/ })).toHaveAttribute('aria-expanded', 'true');
  });

  it('a failed basics call leaves the rest of the summary standing', async () => {
    renderPage(withOverride('/basics', () => Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) } as Response)));
    await waitFor(() => expect(screen.getByText(/the basics: unavailable/)).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText('Damage Dealer')).toBeInTheDocument());
  });
});

describe('SessionDetail — stats 2.0 R4 tabs', () => {
  it('the players tab is the legacy 22-column table on the one DataTable, definitions on every header', async () => {
    const { container } = renderPage(fixtureFetch, '/session-detail/154/players');
    const table = await waitFor(() => {
      const el = container.querySelector('[data-parity="session.players"]');
      expect(el).toBeTruthy();
      return el as HTMLElement;
    });
    await waitFor(() => expect(screen.getByText(/sorted by dpm/)).toBeInTheDocument());
    // 21 data columns; the expander rides in the first cell (legacy's 22nd).
    expect(table.querySelectorAll('.row')[0].children.length).toBe(21);
    // The definitions are the writer's, not the legacy tooltips'.
    expect(screen.getByRole('button', { name: /^uk$|^uk ▾|^uk ▴/ })).toHaveAttribute('title', expect.stringMatching(/^useful kills — the victim had at least half the spawn cycle/));
    expect(screen.getByRole('button', { name: /^fsk/ })).toHaveAttribute('title', expect.stringMatching(/health > 0/));
    expect(screen.getByRole('button', { name: /^alive %/ })).toHaveAttribute('title', expect.stringMatching(/^Alive%: time not dead/));
    expect(screen.getByRole('button', { name: /^hs %/ })).toHaveAttribute('title', expect.stringMatching(/never headshot kills/));
    // "Lua Played%" printed a duplicate of Played% as a second measurement; it is not drawn.
    expect(screen.queryByRole('button', { name: /lua/i })).toBeNull();
    // Sorted by dpm: the top row is the fixture's highest dpm.
    const top = [...(detail as { players: { player_name: string; dpm: number }[] }).players].sort((a, b) => b.dpm - a.dpm)[0];
    const firstRow = table.querySelectorAll('.rows > div')[0];
    expect(firstRow.textContent).toContain(top.player_name);
    expect(screen.getByRole('button', { name: `weapons for ${top.player_name}` })).toBeInTheDocument();
    expect(table.textContent).not.toMatch(/undefined|NaN/);
  });

  it('the rounds tab keeps the two views — by round, one player — with the roster in the select', async () => {
    renderPage(fixtureFetch, '/session-detail/154/rounds');
    await waitFor(() => expect(screen.getByText(/12 of 12 count toward totals|11 of 12 count toward totals/)).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'one player' }));
    // Typed through the query's generic, not a cast the html-scanner reads as raw markup.
    const options = screen.getByLabelText<HTMLSelectElement>('player').options;
    expect(options.length).toBeGreaterThan(1);
    expect(screen.getByRole('button', { name: 'one player' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('the teamplay tab draws the five axes per group as bars and the trade table for the date', async () => {
    const { container } = renderPage(fixtureFetch, '/session-detail/154/teamplay');
    await waitFor(() => expect(container.querySelector('[data-parity="session.teamplay.synergy"]')).toBeTruthy());
    const a = (synergy as { groups: { group_a: { crossfire: number; players: string[] } } }).groups.group_a;
    // A bar per axis, its value in the accessible name — a bar is not a number.
    await waitFor(() => expect(screen.getAllByRole('img', { name: `crossfire rate ${a.crossfire.toFixed(0)}` }).length).toBeGreaterThan(0));
    expect(screen.getAllByRole('img', { name: /^medic bond \d+$/ }).length).toBe(2);
    // The group label and the trade table both name the player — at least
    // once each. A substring match, not a RegExp built from data (the
    // scanners flag a non-literal RegExp, and a name with a dot is one).
    expect(screen.getAllByText(a.players[0], { exact: false }).length).toBeGreaterThan(0);
    // The trade table, scoped to the session's date and saying so.
    await waitFor(() => expect(container.querySelector('[data-parity="session.teamplay.trades"] [role="region"]')).toBeTruthy());
    expect(screen.getByRole('button', { name: /^rate/ })).toHaveAttribute('title', expect.stringMatching(/success ÷ opportunities/));
    expect(screen.getByText(/scoped to 2026-08-27/)).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/undefined|NaN/);
  });

  it('a no_data synergy night (groups: {}) and a prototype trade tracker say so instead of drawing zeros', async () => {
    const fetchImpl = (input: RequestInfo | URL) => {
      const u = String(input);
      if (u.includes('/storytelling/synergy')) return json(synergy80);
      if (u.includes('/proximity/trades/player-stats')) return json({ status: 'prototype', ready: false, message: 'Proximity pipeline not connected.', range_days: 30, generated_at: null, scope: {}, players: [] });
      return fixtureFetch(input);
    };
    const { container } = renderPage(fetchImpl, '/session-detail/154/teamplay');
    await waitFor(() => expect(screen.getByText(/no synergy rows for this session/)).toBeInTheDocument());
    expect(screen.queryAllByRole('img').length).toBe(0);
    await waitFor(() => expect(screen.getByText('Proximity pipeline not connected.')).toBeInTheDocument());
    expect(container.textContent).not.toMatch(/undefined|NaN/);
  });

  it('a partial_data synergy answer reads as insufficient data, not as a measured zero', async () => {
    const partial = { status: 'partial_data', reason: 'no_r1_data', groups: {} };
    renderPage(withOverride('/storytelling/synergy', () => json(partial)), '/session-detail/154/teamplay');
    await waitFor(() => expect(screen.getByText(/insufficient data — no R1 rows/)).toBeInTheDocument());
    expect(screen.queryAllByRole('img').length).toBe(0);
  });

  it('an ok status with no groups (a shape the backend does not send today) is said, not drawn', async () => {
    // Synthetic on purpose: synergy.py answers groups:{} only under
    // no_data/partial_data. The guard exists for the day a status slips
    // through with the groups missing — and a guard nobody can see fail
    // is not a guard (the control-that-must-fail rule).
    const okNoGroups = { status: 'ok', groups: {}, weights: {}, defaulted_players_count: 0 };
    renderPage(withOverride('/storytelling/synergy', () => json(okNoGroups)), '/session-detail/154/teamplay');
    await waitFor(() => expect(screen.getByText(/no player groups could be built/)).toBeInTheDocument());
    expect(screen.queryAllByRole('img').length).toBe(0);
  });

  it('the story tab mounts the session story and folds a no-rounds night into one sentence', async () => {
    const fetchImpl = (input: RequestInfo | URL) => {
      const u = String(input);
      if (u.includes('/storytelling/narrative')) return Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({ detail: 'no accepted rounds' }) } as Response);
      // Every other story endpoint is left to the corpus stub, which rejects
      // what it does not hold: each panel goes unavailable, none crashes, and
      // the fold replaces them all once the narrative's 404 lands.
      return fixtureFetch(input);
    };
    const { container } = renderPage(fetchImpl, '/session-detail/154/story');
    await waitFor(() => expect(container.querySelector('[data-parity="session.story"]')).toBeTruthy());
    await waitFor(() => expect(screen.getByText(/no accepted rounds, so there is no story to tell/)).toBeInTheDocument());
  });
});
