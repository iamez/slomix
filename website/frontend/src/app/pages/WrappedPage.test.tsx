import { render, screen, waitFor } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { WrappedPage } from './WrappedPage';
import type { WrappedSeason } from '../lib/types';
import wrappedJson from './__fixtures__/api_players_identifier_wrapped.json';

// Recorded from the live dev server for a real player: 8 cards, 2026 Fall (Q3).
const wrapped = wrappedJson satisfies WrappedSeason;

function stub(body: unknown, status = 200) {
  vi.stubGlobal('fetch', vi.fn((): Promise<Response> => Promise.resolve({
    ok: status < 400, status, json: () => Promise.resolve(body),
  } as Response)));
}

function renderAt(path: string) {
  return render(
    <QueryClientProvider client={makeQueryClient()}>
      <MemoryRouter initialEntries={[path]}>
        <Routes><Route path="/wrapped/:guid" element={<WrappedPage />} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe('WrappedPage', () => {
  it('every card is readable as text, not only painted into the canvas', async () => {
    // ⭐ This is the one thing the page adds over legacy. A canvas is a
    // picture to a screen reader, and legacy drew the numbers nowhere else —
    // so a reader who cannot see the image could not read their season.
    stub(wrapped);
    renderAt('/wrapped/5D989160');
    await waitFor(() => expect(screen.getByText('Rounds played')).toBeInTheDocument());
    expect(screen.getByText('281')).toBeInTheDocument();
    for (const c of wrapped.cards) {
      expect(screen.getByText(c.label), `card "${c.key}" has no label on the page`).toBeInTheDocument();
    }
    expect(screen.getByText('2026 Fall (Q3)')).toBeInTheDocument();
  });

  it('a player with no season data gets the reason, not an empty page', async () => {
    stub({ ...wrapped, cards: [] });
    renderAt('/wrapped/00000000');
    await waitFor(() => expect(screen.getByText(/no season data for this player yet/)).toBeInTheDocument());
    // ⛔ And no export controls: legacy disables them until the canvas holds a
    // card (wrapped.js:65), because a Download that yields a blank PNG is
    // worse than no button — the user only finds out after pasting it.
    expect(screen.queryByRole('button', { name: 'download' })).not.toBeInTheDocument();
  });

  it('a failed request is unavailable, which is not the same as empty', async () => {
    stub({ detail: 'boom' }, 500);
    renderAt('/wrapped/5D989160');
    await waitFor(() => expect(screen.getByText(/season card: unavailable/i)).toBeInTheDocument());
    expect(screen.queryByText(/no season data/)).not.toBeInTheDocument();
  });

  it('⛔ exports stay disabled when the canvas cannot be drawn', async () => {
    // jsdom has no 2d context unless the `canvas` package is installed, so
    // this is the real state here — and it is also a real browser state
    // (a blocked canvas). The numbers must still render; the buttons must not
    // promise an image that does not exist.
    stub(wrapped);
    renderAt('/wrapped/5D989160');
    await waitFor(() => expect(screen.getByText('Rounds played')).toBeInTheDocument());
    expect(screen.getByRole('button', { name: 'download' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'copy image' })).toBeDisabled();
    expect(screen.getByText(/the numbers above are the same card/)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// the drawing itself
//
// ⚠️ jsdom has no 2d context, so every test above exercises the page WITHOUT
// ever running drawWrapped — and drawWrapped is where the parity lives. A
// recording 2d stub is the only way to see the caps and the layout fail.

type Drawn = { text: string; x: number; y: number };

function fakeCanvas(): { canvas: HTMLCanvasElement; drawn: Drawn[] } {
  const drawn: Drawn[] = [];
  const ctx = {
    fillStyle: '', font: '', textAlign: '',
    createLinearGradient: () => ({ addColorStop: () => {} }),
    fillRect: () => {}, fill: () => {},
    beginPath: () => {}, moveTo: () => {}, arcTo: () => {}, closePath: () => {},
    fillText: (text: string, x: number, y: number) => { drawn.push({ text, x, y }); },
  };
  const canvas = { width: 0, height: 0, getContext: () => ctx } as unknown as HTMLCanvasElement;
  return { canvas, drawn };
}

describe('drawWrapped', () => {
  it('keeps legacy\'s caps: 8 cards, and every string truncated where legacy truncates it', async () => {
    const { drawWrapped } = await import('./WrappedPage');
    const { canvas, drawn } = fakeCanvas();
    const long = 'x'.repeat(60);
    const ok = drawWrapped(canvas, {
      status: 'ok', guid: 'g', season_id: 's', season_name: null,
      player_name: long,
      cards: Array.from({ length: 12 }, (_, i) => ({
        key: `k${i}`, label: long, value: long, sub: long,
      })),
    });
    expect(ok).toBe(true);
    expect(canvas.width).toBe(1080);
    expect(canvas.height).toBe(1920);

    // The name: 22 characters (wrapped.js:124).
    expect(drawn.find((d) => d.text.startsWith('xxx') && d.y === 250)?.text).toHaveLength(22);
    // 12 cards in, 8 drawn — three strings each (label, value, sub).
    const cardText = drawn.filter((d) => d.y >= 420 && d.text.startsWith('x') || d.text.startsWith('X'));
    expect(cardText.filter((d) => d.text.length === 22)).toHaveLength(8);  // labels, uppercased+cut
    expect(cardText.filter((d) => d.text.length === 16)).toHaveLength(8);  // values
    expect(cardText.filter((d) => d.text.length === 26)).toHaveLength(8);  // subs
    // The 9th card is not drawn at all.
    expect(cardText).toHaveLength(24);

    // Two columns: legacy lays cards out at 70 and 70 + tileW + 40.
    const xs = [...new Set(cardText.map((d) => d.x))].sort((a, b) => a - b);
    expect(xs).toHaveLength(2);
    expect(xs[0]).toBe(70 + 36);

    // The footer is the site, not the season.
    expect(drawn.some((d) => d.text === 'slomix.fyi')).toBe(true);
    expect(drawn.some((d) => d.text === 'SLOMIX WRAPPED')).toBe(true);
  });

  it('falls back to season_id when the season has no name, and survives a missing context', async () => {
    const { drawWrapped } = await import('./WrappedPage');
    const { canvas, drawn } = fakeCanvas();
    drawWrapped(canvas, {
      status: 'ok', guid: 'g', season_id: '2026-Q3', season_name: null,
      player_name: 'p', cards: [{ key: 'a', label: 'L', value: 'V' }],
    });
    expect(drawn.some((d) => d.text === '2026-Q3')).toBe(true);
    // A card without `sub` draws two strings, not three with an empty one.
    expect(drawn.filter((d) => d.y >= 420 && d.y < 700)).toHaveLength(2);

    const noCtx = { width: 0, height: 0, getContext: () => null } as unknown as HTMLCanvasElement;
    expect(drawWrapped(noCtx, {
      status: 'ok', guid: 'g', season_id: null, season_name: null, player_name: 'p', cards: [],
    })).toBe(false);
  });
});
