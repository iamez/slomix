import { render, screen, waitFor } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { SkillRating } from './SkillRating';
import leaderboard from './__fixtures__/api_skill_leaderboard.json';
import formula from './__fixtures__/api_skill_formula.json';
import ssr from './__fixtures__/api_skill_ssr.json';

function fixtureFetch(input: RequestInfo | URL): Promise<Response> {
  const url = String(input);
  const body = url.includes('/skill/formula') ? formula
    : url.includes('/skill/ssr') ? ssr
      : leaderboard;
  if (url.includes('/api/skill/')) {
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);
  }
  return Promise.reject(new Error(`unexpected endpoint: ${url}`));
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
});
