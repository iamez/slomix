import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { Link, MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { ComparePage } from './ComparePage';
import type { PlayerIdentity } from '../lib/types';
import aJson from './__fixtures__/api_stats_player_compare_a.json';
import bJson from './__fixtures__/api_stats_player_compare_b.json';

// Two real players recorded from the dev server, renamed. B wins four of the
// five contests; A wins games played AND has the longer playtime — which is
// what makes the divergence below observable.
const A = aJson satisfies PlayerIdentity;
const B = bJson satisfies PlayerIdentity;

function stub(map: Record<string, { body?: unknown; status?: number }>) {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL): Promise<Response> => {
    const name = decodeURIComponent(String(input).split('?')[0].split('/').pop() ?? '');
    const hit = map[name];
    if (hit === undefined) return Promise.reject(new Error(`unexpected: ${name}`));
    const status = hit.status ?? 200;
    return Promise.resolve({
      ok: status < 400, status, json: () => Promise.resolve(hit.body ?? { detail: 'x' }),
    } as Response);
  }));
}

function renderAt(path: string) {
  return render(
    <QueryClientProvider client={makeQueryClient()}>
      <MemoryRouter initialEntries={[path]}>
        {/* A navigation target that stays mounted, so a test can change the
            URL WITHOUT remounting the page — the only way to see the
            URL→fields sync fail (useState seeds the fields on first render,
            so a mount-only test passes with the sync deleted). */}
        <Link to="/compare?a=bravo&b=alpha">swap</Link>
        <Routes><Route path="/compare" element={<ComparePage />} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const BOTH = { alpha: { body: A }, bravo: { body: B } };

afterEach(() => vi.unstubAllGlobals());

describe('ComparePage', () => {
  it('with no names it asks for two, and calls nothing', async () => {
    const spy = vi.fn();
    vi.stubGlobal('fetch', spy);
    renderAt('/compare');
    expect(await screen.findByText(/name two players/)).toBeInTheDocument();
    expect(spy).not.toHaveBeenCalled();
  });

  it('the comparison comes from the URL, so the link is the state', async () => {
    stub(BOTH);
    renderAt('/compare?a=alpha&b=bravo');
    // ⚠️ The marker shares the element with the number ('▸ 1.21'), so an
    // exact match on the figure alone finds nothing. Matching the rendered
    // string is the honest assertion — it is what a reader sees.
    await waitFor(() => expect(screen.getByText('▸ 1.21')).toBeInTheDocument());
    // Both fields are filled from the URL, not left empty for retyping.
    expect(screen.getByLabelText('first player')).toHaveValue('alpha');
    expect(screen.getByLabelText('second player')).toHaveValue('bravo');
    // A loses this row, so its figure is unmarked and stands alone.
    expect(screen.getByText('0.93')).toBeInTheDocument();
  });

  it('marks the better side on each contest, and the winner is per row', async () => {
    stub(BOTH);
    renderAt('/compare?a=alpha&b=bravo');
    // B takes K/D, DPM, kills and win rate; A takes games played. A row-by-row
    // check, not a single "who won" — a comparison that only ever marks one
    // column is broken in a way a totals check cannot see.
    await waitFor(() => expect(screen.getByText('▸ 1.21')).toBeInTheDocument());  // B: K/D
    expect(screen.getByText('▸ 289')).toBeInTheDocument();      // B: DPM
    expect(screen.getByText('▸ 52.3%')).toBeInTheDocument();    // B: win rate
    expect(screen.getByText('1,850 ◂')).toBeInTheDocument();    // A: games
  });

  it('⛔ playtime carries no marker — the deliberate divergence from legacy', async () => {
    // compare.js:69 sets `higherIsBetter: false` for Playtime, so legacy puts
    // the trophy on whoever played LESS, rendered identically to K/D where the
    // trophy means better. A has 205.2h and B 183.7h: legacy would decorate
    // B's 183.7h as the win. As displayed that is a false claim, so neither
    // side is marked here and the page says why.
    stub(BOTH);
    renderAt('/compare?a=alpha&b=bravo');
    await waitFor(() => expect(screen.getByText('205.2h')).toBeInTheDocument());
    expect(screen.getByText('183.7h')).toBeInTheDocument();
    expect(screen.queryByText('▸ 183.7h')).not.toBeInTheDocument();
    expect(screen.queryByText('205.2h ◂')).not.toBeInTheDocument();
    expect(screen.getByText(/playtime is context, not a contest/)).toBeInTheDocument();
  });

  it('one unknown name is that name\'s problem, not an outage', async () => {
    stub({ alpha: { body: A }, ghost: { status: 404 } });
    renderAt('/compare?a=alpha&b=ghost');
    await waitFor(() => expect(screen.getByText(/no player called "ghost"/)).toBeInTheDocument());
    // ⛔ And no half-comparison: rows need both sides, or they would silently
    // compare a player against nothing.
    expect(screen.queryByText('0.93')).not.toBeInTheDocument();
    expect(screen.getByText(/both names have to resolve/)).toBeInTheDocument();
  });

  it('submitting the form writes the names into the URL', async () => {
    stub(BOTH);
    renderAt('/compare');
    fireEvent.change(screen.getByLabelText('first player'), { target: { value: 'alpha' } });
    fireEvent.change(screen.getByLabelText('second player'), { target: { value: 'bravo' } });
    fireEvent.click(screen.getByRole('button', { name: /compare/ }));
    await waitFor(() => expect(screen.getByText('▸ 1.21')).toBeInTheDocument());
  });

  it('⛔ a URL change while mounted moves the fields too', async () => {
    // The back button, or an in-app link to another comparison. `useState`
    // seeds the inputs once; without the effect the fields would keep showing
    // the previous pair while the results below them changed — two answers on
    // one screen.
    stub(BOTH);
    renderAt('/compare?a=alpha&b=bravo');
    await waitFor(() => expect(screen.getByLabelText('first player')).toHaveValue('alpha'));
    fireEvent.click(screen.getByText('swap'));
    await waitFor(() => expect(screen.getByLabelText('first player')).toHaveValue('bravo'));
    expect(screen.getByLabelText('second player')).toHaveValue('alpha');
  });
});
