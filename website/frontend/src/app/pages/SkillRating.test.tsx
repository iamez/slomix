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

  it('explains an order when asked: weight times percentile, per component', async () => {
    // The whole point of the page. A rank nobody can argue with is a rank
    // nobody can check.
    renderPage();
    await waitFor(() => expect(screen.getAllByRole('button', { name: 'why' }).length).toBeGreaterThan(0));
    screen.getAllByRole('button', { name: 'why' })[0].click();
    await waitFor(() => expect(screen.getByText('dpm')).toBeInTheDocument());
    // dpm for vid in the recording: raw 314.093, percentile 0.839, weight
    // 0.12, contribution 0.1007.
    expect(screen.getByText('+0.1007')).toBeInTheDocument();
    expect(screen.getByText('84%')).toBeInTheDocument();
    expect(screen.getByText('+0.12')).toBeInTheDocument();
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

  it('says when a published number was pulled toward the mean', async () => {
    // Confidence below 1 means shrinkage did the talking; a rank read
    // without that is a rank read wrong.
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
    await waitFor(() => expect(screen.getByText('42% weight')).toBeInTheDocument());
  });
});
