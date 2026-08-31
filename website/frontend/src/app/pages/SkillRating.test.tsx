import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { SkillRating } from './SkillRating';
import leaderboard from './__fixtures__/api_skill_leaderboard.json';
import formula from './__fixtures__/api_skill_formula.json';
import ssr from './__fixtures__/api_skill_ssr.json';
import adjusted from './__fixtures__/api_skill_adjusted_lifetime.json';

/** Dispatch on the exact path. The previous chain fell through to the
 *  leaderboard for anything it did not recognise, so a new /skill/* endpoint
 *  would have been served a rating board — plausible data from the wrong
 *  place, which reads as a bug in the page rather than in the test. */
function fixtureFetch(input: RequestInfo | URL): Promise<Response> {
  const path = new URL(String(input), 'http://test.local').pathname;
  const bodies: Record<string, unknown> = {
    '/api/skill/formula': formula,
    '/api/skill/ssr': ssr,
    '/api/skill/adjusted-lifetime': adjusted,
    '/api/skill/leaderboard': leaderboard,
  };
  const body = bodies[path];
  if (body === undefined) return Promise.reject(new Error(`unexpected endpoint: ${String(input)}`));
  return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);
}

function renderPage(fetchImpl = fixtureFetch) {
  vi.stubGlobal('fetch', vi.fn(fetchImpl));
  const client = makeQueryClient();
  client.setDefaultOptions({ queries: { retry: false } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <SkillRating />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('SkillRating', () => {
  it('quotes the formula rather than paraphrasing it', async () => {
    // The endpoint publishes the expression; retyping it here is how a page
    // and its backend drift apart.
    renderPage();
    await waitFor(() => expect(screen.getByText(/ET_Rating = /)).toBeInTheDocument());
    expect(screen.getByText(/ET Rating v2 · v2.1/)).toBeInTheDocument();
  });

  it('shows the recorded ranking with its ratings', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('vid')).toBeInTheDocument());
    expect(screen.getByText('0.748')).toBeInTheDocument();
    expect(screen.getAllByText('veteran').length).toBeGreaterThan(0);
  });

  it('explains the RAW score, and says so rather than claiming the published one', async () => {
    // The first version claimed these components were "the sum the rating
    // is". They are not: constant + Σ gives the raw score, and the published
    // rating is that shrunk toward the pool mean — for vid 0.7523 against a
    // published 0.7481. A panel that shows one and labels it the other is
    // the failure this page exists to avoid (Codex on #835).
    renderPage();
    await waitFor(() => expect(screen.getAllByRole('button', { name: 'why' }).length).toBeGreaterThan(0));
    screen.getAllByRole('button', { name: 'why' })[0].click();
    await waitFor(() => expect(screen.getByText('dpm')).toBeInTheDocument());
    expect(screen.getByText('+0.1007')).toBeInTheDocument();
    expect(screen.getByText('84%')).toBeInTheDocument();
    expect(screen.getByText('+0.12')).toBeInTheDocument();
    // The raw sum is printed as the raw sum…
    expect(screen.getByText(/raw = constant \+ Σ = 0\.7523/)).toBeInTheDocument();
    // …and the second step is performed, not just named: weight n/(n+k) with
    // n=1760 and k=40 is 0.978, and the recording's pool mean is 0.5701.
    // 0.978 × 0.7523 + 0.022 × 0.5701 = 0.7483, and the published figure is
    // 0.7481. The 0.0002 gap is the components' own rounding to four
    // decimals — the same residual the whole cohort shows once the table
    // holds one run's worth of rows.
    expect(screen.getByText(/× 0\.978 \+ pool 0\.5701 × 0\.022 = 0\.7483 → published 0\.7481/))
      .toBeInTheDocument();
  });

  it('says so when the pool mean is missing instead of inventing the step', async () => {
    // Nothing rated yet → pool_mean is null. A page that quietly substituted
    // zero would print a shrinkage that never happened.
    const noPool = {
      ...(leaderboard as object),
      meta: { ...(leaderboard as { meta: object }).meta, pool_mean: null },
    };
    renderPage((input) => {
      const url = String(input);
      if (url.includes('/skill/leaderboard')) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(noPool) } as Response);
      }
      return fixtureFetch(input);
    });
    await waitFor(() => expect(screen.getAllByRole('button', { name: 'why' }).length).toBeGreaterThan(0));
    screen.getAllByRole('button', { name: 'why' })[0].click();
    await waitFor(() => expect(screen.getByText(/pool mean unavailable/)).toBeInTheDocument());
  });

  it('does not call the SSR endpoint until its panel is opened', async () => {
    // 2.4 s on every visit for a panel that starts closed.
    const spy = vi.fn(fixtureFetch);
    renderPage(spy);
    await waitFor(() => expect(screen.getByText('vid')).toBeInTheDocument());
    expect(spy.mock.calls.some(([u]) => String(u).includes('/skill/ssr'))).toBe(false);
    screen.getByRole('button', { name: /show ssr/i }).click();
    await waitFor(() => expect(spy.mock.calls.some(([u]) => String(u).includes('/skill/ssr'))).toBe(true));
  });

  it('keeps SSR behind its own switch and never mixes it with the rating', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByRole('button', { name: /show ssr/i })).toBeInTheDocument());
    // Before the switch, no SSR figure is on the page at all.
    expect(screen.queryByText('ssr-v0.3')).toBeNull();
    screen.getByRole('button', { name: /show ssr/i }).click();
    await waitFor(() => expect(screen.getByText(/ssr-v0.3/)).toBeInTheDocument());
    expect(screen.getByText(/not comparable/)).toBeInTheDocument();
  });

  it('prints coverage beside each SSR score, not under a footnote', async () => {
    // The recording holds one player measured on three of eight components
    // and thirteen on eight. Those are different measurements and must not
    // read alike.
    renderPage();
    await waitFor(() => expect(screen.getByRole('button', { name: /show ssr/i })).toBeInTheDocument());
    screen.getByRole('button', { name: /show ssr/i }).click();
    await waitFor(() => expect(screen.getByText('3/8')).toBeInTheDocument());
    expect(screen.getAllByText('8/8').length).toBeGreaterThan(1);
  });

  it('tells two rated players apart when they share a display name', async () => {
    // `ownator` sits at rank 7 and rank 9 in the recording, on 78 and 45
    // rounds — two GUIDs, one name. Identical names against different
    // ratings is a board contradicting itself.
    renderPage();
    await waitFor(() => expect(screen.getAllByText('ownator').length).toBe(2));
    expect(screen.getByText('FB0EC840')).toBeInTheDocument();
    expect(screen.getByText('EF561EAA')).toBeInTheDocument();
    // …and nowhere else: an unambiguous name carries no id.
    expect(screen.queryByText('D8423F90')).toBeNull();
  });

  it('names the sample-size confidence without calling it a weight', async () => {
    // The backend defines confidence as min(1, n/30); the shrinkage weight is
    // n/(n+40). For a 22-round player: 0.73 against 0.355.
    const shrunk = {
      ...(leaderboard as object),
      players: [
        { ...(leaderboard as { players: Record<string, unknown>[] }).players[0], confidence: 0.42 },
      ],
    };
    renderPage((input) => {
      const url = String(input);
      if (url.includes('/skill/leaderboard')) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(shrunk) } as Response);
      }
      return fixtureFetch(input);
    });
    // Labelled as what the field is — a sample-size confidence — not as the
    // shrinkage weight, which is n/(n+k) and a different number entirely.
    await waitFor(() => expect(screen.getByText('sample conf. 42%')).toBeInTheDocument());
  });
  it('does not fetch the adjusted board until it is asked for', async () => {
    // It recomputes an SRS iteration server-side and measured 1.0 s cold —
    // ten times the rest of this page. A panel that costs a second belongs
    // behind a click, not in the page load.
    const spy = vi.fn(fixtureFetch);
    renderPage(spy);
    await waitFor(() => expect(screen.getByText(/adjusted for who they played/i)).toBeInTheDocument());
    const asked = () => spy.mock.calls.some(([u]) => String(u).includes('/skill/adjusted-lifetime'));
    expect(asked()).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: /show adjusted/i }));
    await waitFor(() => expect(asked()).toBe(true));
  });

  it('shows the correction beside the sample it was computed from', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByRole('button', { name: /show adjusted/i })).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /show adjusted/i }));

    const players = (adjusted as { players: { name: string; lifetime_rating: number | null; adjusted_lifetime: number; n_sessions: number }[] }).players;
    const rated = players.find((p) => p.lifetime_rating != null)!;
    await waitFor(() => expect(screen.getAllByText(rated.adjusted_lifetime.toFixed(3)).length).toBeGreaterThan(0));
    expect(screen.getAllByText(rated.lifetime_rating!.toFixed(3)).length).toBeGreaterThan(0);
    const delta = rated.adjusted_lifetime - rated.lifetime_rating!;
    expect(screen.getAllByText(`${delta > 0 ? '+' : ''}${delta.toFixed(3)}`).length).toBeGreaterThan(0);
  });

  it('tells the two adjusted "ownator"s apart, the same way the main board does', async () => {
    // The committed fixture itself proves the need: EF561EAA and FB0EC840
    // both render as "ownator", with different ratings. Without the GUID tag
    // the board contradicts itself (Codex on #846).
    renderPage();
    await waitFor(() => expect(screen.getByRole('button', { name: /show adjusted/i })).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /show adjusted/i }));
    await waitFor(() => expect(screen.getAllByText('ownator').length).toBeGreaterThan(1));
    // The MAIN board already tags its own duplicates with the same GUIDs, so
    // presence alone would pass without this fix — the adjusted board must
    // ADD its tags on top of the main board's.
    expect(screen.getAllByText('EF561EAA').length).toBeGreaterThan(1);
    expect(screen.getAllByText('FB0EC840').length).toBeGreaterThan(1);
  });

  it('derives the thin-history claim from the rows instead of asserting a constant', async () => {
    // ⛔ The first version of this test compared against the committed
    // fixture — where the derived ratio happens to round to 5 — so the
    // hard-coded "~5×" it was written to reject ALSO passed. A fixture
    // cannot fail on a value it does not contain, so this one feeds the
    // board a synthetic pool built for a different answer: thin deltas of
    // 1.2 against deep deltas of 0.1 make the honest sentence "~12×", and
    // the constant 5 has no way to produce it.
    const synthetic = {
      available: true,
      formula_version: 's-effort-v1',
      players: [
        { player_guid: 'AAAA0001', name: 'thin-a', lifetime_rating: 1.0, adjusted_lifetime: 2.2, n_sessions: 2, formula_version: 's-effort-v1' },
        { player_guid: 'AAAA0002', name: 'thin-b', lifetime_rating: 1.0, adjusted_lifetime: 2.2, n_sessions: 3, formula_version: 's-effort-v1' },
        { player_guid: 'AAAA0003', name: 'deep-a', lifetime_rating: 1.0, adjusted_lifetime: 1.1, n_sessions: 30, formula_version: 's-effort-v1' },
        { player_guid: 'AAAA0004', name: 'deep-b', lifetime_rating: 1.0, adjusted_lifetime: 0.9, n_sessions: 40, formula_version: 's-effort-v1' },
      ],
    };
    renderPage((input) => {
      const path = new URL(String(input), 'http://test.local').pathname;
      if (path === '/api/skill/adjusted-lifetime') {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(synthetic) } as Response);
      }
      return fixtureFetch(input);
    });
    await waitFor(() => expect(screen.getByRole('button', { name: /show adjusted/i })).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /show adjusted/i }));
    await waitFor(() => expect(screen.getByText(/the correction is/)).toBeInTheDocument());
    expect(screen.getByText(/the correction is/).textContent).toContain('~12×');
  });

  it('says a player has no lifetime rating rather than crediting them a delta', async () => {
    // Measured on the recording: 3 of 31 players have lifetime_rating null —
    // they appear in the session history and not in the lifetime table, all
    // with one session. A delta against 0 would credit one of them with a
    // +0.63 improvement that never happened.
    const players = (adjusted as { players: { lifetime_rating: number | null }[] }).players;
    expect(players.filter((p) => p.lifetime_rating == null).length).toBeGreaterThan(0);

    renderPage();
    await waitFor(() => expect(screen.getByRole('button', { name: /show adjusted/i })).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /show adjusted/i }));
    await waitFor(() => expect(screen.getAllByText('no lifetime yet').length)
      .toBe(players.filter((p) => p.lifetime_rating == null).length));
    // …and none of them is shown a delta equal to their adjusted rating.
    const orphan = (adjusted as { players: { lifetime_rating: number | null; adjusted_lifetime: number }[] })
      .players.find((p) => p.lifetime_rating == null)!;
    expect(screen.queryByText(`+${orphan.adjusted_lifetime.toFixed(3)}`)).toBeNull();
  });

  it('marks a thin sample, because that is where the correction is largest', async () => {
    // 0.143 average correction below five sessions against 0.028 above
    // twenty — five times larger exactly where the evidence is thinnest, and
    // three of the top ten have played once or twice.
    renderPage();
    await waitFor(() => expect(screen.getByRole('button', { name: /show adjusted/i })).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /show adjusted/i }));

    const players = (adjusted as { players: { n_sessions: number }[] }).players;
    const thin = players.filter((p) => p.n_sessions < 5);
    expect(thin.length).toBeGreaterThan(0);
    await waitFor(() => expect(screen.getAllByText(/^\d+ sessions?$/).length).toBe(thin.length));
  });

  it('derives the DIRECTION of the correction claim, never asserts it', async () => {
    // ⛔ The mirrored pool (Codex on #846 + the verifier's #851): deep
    // corrections LARGER than thin ones must flip the sentence, not render
    // "~0× larger below". A fixture cannot fail on a value it does not
    // contain, so each branch gets a synthetic pool built for it.
    const pool = (players: unknown[]) => ({
      available: true, formula_version: 's-effort-v1', players,
    });
    const p = (guid: string, life: number, adj: number, n: number) => ({
      player_guid: guid, name: guid, lifetime_rating: life,
      adjusted_lifetime: adj, n_sessions: n, formula_version: 's-effort-v1',
    });
    const mirrored = pool([
      p('AAAA0001', 1.0, 1.05, 2), p('AAAA0002', 1.0, 1.05, 3),   // thin ±0.05
      p('AAAA0003', 1.0, 1.6, 30), p('AAAA0004', 1.0, 0.4, 40),   // deep ±0.6
    ]);
    renderPage((input) => {
      const path = new URL(String(input), 'http://test.local').pathname;
      if (path === '/api/skill/adjusted-lifetime') {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(mirrored) } as Response);
      }
      return fixtureFetch(input);
    });
    return (async () => {
      await waitFor(() => expect(screen.getByRole('button', { name: /show adjusted/i })).toBeInTheDocument());
      fireEvent.click(screen.getByRole('button', { name: /show adjusted/i }));
      await waitFor(() => expect(screen.getByText(/the correction is/)).toBeInTheDocument());
      const claim = screen.getByText(/the correction is/).textContent ?? '';
      expect(claim).toContain('larger above twenty sessions than below five');
      expect(claim).toContain('~12×');
      expect(claim).not.toMatch(/~[01]× larger below/);
    })();
  });

  it('claims no direction when a comparison bucket is missing', async () => {
    const thinOnly = {
      available: true, formula_version: 's-effort-v1',
      players: [{ player_guid: 'AAAA0001', name: 'only-thin', lifetime_rating: 1.0,
        adjusted_lifetime: 1.4, n_sessions: 2, formula_version: 's-effort-v1' }],
    };
    renderPage((input) => {
      const path = new URL(String(input), 'http://test.local').pathname;
      if (path === '/api/skill/adjusted-lifetime') {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(thinOnly) } as Response);
      }
      return fixtureFetch(input);
    });
    await waitFor(() => expect(screen.getByRole('button', { name: /show adjusted/i })).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /show adjusted/i }));
    await waitFor(() => expect(screen.getByText(/the correction/)).toBeInTheDocument());
    const claim = screen.getByText(/the correction/).textContent ?? '';
    // No comparison exists: the sentence says what the correction IS and
    // claims no direction — the old code asserted "largest for thin
    // histories" here with nothing behind it.
    expect(claim).toContain('rates each session against the opponents who actually played it');
    expect(claim).not.toContain('larger');
  });

  it('names the current formula when history under it is empty', async () => {
    // The service filters history to the CURRENT formula_version, so an
    // empty list also covers "history exists, under an earlier formula" —
    // the wording must not claim nothing was ever persisted, and the
    // version must come from the payload, not a constant.
    const empty = { available: false, formula_version: 's-effort-v9', players: [] };
    renderPage((input) => {
      const path = new URL(String(input), 'http://test.local').pathname;
      if (path === '/api/skill/adjusted-lifetime') {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(empty) } as Response);
      }
      return fixtureFetch(input);
    });
    await waitFor(() => expect(screen.getByRole('button', { name: /show adjusted/i })).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /show adjusted/i }));
    await waitFor(() => expect(screen.getByText(/no session history under the current formula/)).toBeInTheDocument());
    const line = screen.getByText(/no session history under the current formula/).textContent ?? '';
    expect(line).toContain('(s-effort-v9)');
    expect(line).toContain('scored under an earlier formula');
    expect(line).not.toMatch(/persisted yet, so there is nothing/);
  });

  it('says an unbuilt board is unbuilt, not unavailable', async () => {
    renderPage((input: RequestInfo | URL) => {
      const path = new URL(String(input), 'http://test.local').pathname;
      if (path === '/api/skill/adjusted-lifetime') {
        return Promise.resolve({
          ok: true, status: 200,
          json: () => Promise.resolve({ status: 'ok', available: false, formula_version: 's.effort-v0.2', players: [] }),
        } as Response);
      }
      return fixtureFetch(input);
    });
    await waitFor(() => expect(screen.getByRole('button', { name: /show adjusted/i })).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /show adjusted/i }));
    // Wording follows the :252 review fix: the old line claimed "no session
    // history has been persisted yet", which the wire cannot back — the
    // service filters to the CURRENT formula_version, so empty also covers
    // history under an earlier formula.
    await waitFor(() => expect(screen.getByText(/no session history under the current formula/)).toBeInTheDocument());
    expect(screen.queryByText(/adjusted ratings: unavailable/)).toBeNull();
  });
});
