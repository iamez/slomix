import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { WrappedPage } from './WrappedPage';
import wrapped from './__fixtures__/api_players_identifier_wrapped.json';
import type { Wrapped } from '../lib/types';

const DATA = wrapped as Wrapped;

function fetchWith(body: unknown, expectSeason?: string) {
  const seasons: string[] = [];
  const fn = vi.fn((input: RequestInfo | URL) => {
    const url = new URL(String(input), 'http://test.local');
    if (!/\/api\/players\/[^/]+\/wrapped$/.test(url.pathname)) {
      return Promise.reject(new Error(`unexpected endpoint: ${url.pathname}`));
    }
    seasons.push(url.searchParams.get('season') ?? '');
    if (expectSeason !== undefined) expect(url.searchParams.get('season')).toBe(expectSeason);
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);
  });
  vi.stubGlobal('fetch', fn);
  return seasons;
}

function testClient(): QueryClient {
  const client = makeQueryClient();
  client.setDefaultOptions({ queries: { retry: false } });
  return client;
}

function renderAt(url: string) {
  return render(
    <QueryClientProvider client={testClient()}>
      <MemoryRouter initialEntries={[url]}>
        <Routes><Route path="/profile/:id/wrapped" element={<WrappedPage />} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('WrappedPage', () => {
  afterEach(() => { vi.restoreAllMocks(); });

  it('lists the eight facts as text beside the card and keeps copy/download disabled until drawn', async () => {
    // jsdom has no 2D context: the card cannot be drawn here, which is
    // exactly the state the buttons must refuse to act in.
    fetchWith(DATA, 'current');
    renderAt(`/profile/${DATA.guid}/wrapped`);
    await waitFor(() => expect(screen.getByText('Rounds played')).toBeInTheDocument());
    const facts = document.querySelector('[data-parity="wrapped.facts"]')!;
    expect(facts.querySelectorAll('.row')).toHaveLength(8);
    expect(screen.getByText('291')).toBeInTheDocument();
    expect(screen.getByText('0.88 K/D')).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /Slomix Wrapped card for \.lgz/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'copy image' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'download png' })).toBeDisabled();
    expect(screen.getByText(/drawing the card/)).toBeInTheDocument();
  });

  it('passes ?season= through and says so in the head', async () => {
    fetchWith({ ...DATA, season_id: '2026-Q2', season_name: '2026 Summer (Q2)' }, '2026-Q2');
    renderAt(`/profile/${DATA.guid}/wrapped?season=2026-Q2`);
    await waitFor(() => expect(screen.getByText(/2026 Summer \(Q2\)/)).toBeInTheDocument());
  });

  it('a player without a round in the season gets a reason, not an empty card', async () => {
    fetchWith({ ...DATA, cards: [] });
    renderAt(`/profile/${DATA.guid}/wrapped`);
    expect(await screen.findByText(/no season data for \.lgz yet/)).toBeInTheDocument();
    expect(document.querySelector('[data-parity="wrapped.card"]')).toBeNull();
    expect(screen.queryByRole('button', { name: 'copy image' })).toBeNull();
  });
});
