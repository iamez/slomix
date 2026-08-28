import { render, screen, waitFor } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { Rivalries } from './Rivalries';
import board from './__fixtures__/api_rivalries_leaderboard.json';
import player from './__fixtures__/api_rivalries_player_guid.json';

/** Against the recorded responses — the community board and vid's opponents. */
function fixtureFetch(input: RequestInfo | URL): Promise<Response> {
  const url = String(input);
  const body = url.includes('/rivalries/player/') ? player : board;
  if (url.includes('/api/rivalries/')) {
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);
  }
  return Promise.reject(new Error(`unexpected endpoint: ${url}`));
}

function renderPage(search = '', fetchImpl = fixtureFetch) {
  vi.stubGlobal('fetch', vi.fn(fetchImpl));
  const client = makeQueryClient();
  client.setDefaultOptions({ queries: { retry: false } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/rivalries${search}`]}>
        <Routes>
          <Route path="/rivalries" element={<Rivalries />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('Rivalries', () => {
  it('prints the rule beside each label, so a classification can be checked', async () => {
    // NEMESIS/PREY/RIVAL are thresholds on one number, not adjectives. A page
    // that shows the label without the rule leaves the reader guessing why
    // their 58% opponent is a rival and their 61% one is not.
    renderPage();
    await waitFor(() => expect(screen.getByText('you win 70%+')).toBeInTheDocument());
    expect(screen.getByText('they win 70%+')).toBeInTheDocument();
    expect(screen.getByText('within 40-60%')).toBeInTheDocument();
    expect(screen.getByText('fewer than 5 meetings')).toBeInTheDocument();
  });

  it('shows the recorded pair with the kills each way', async () => {
    renderPage();
    // .olz vs vid, 872 and 1096 — the top pair in the recording.
    await waitFor(() => expect(screen.getAllByText(/\.olz/).length).toBeGreaterThan(0));
    expect(screen.getByText('872 — 1,096')).toBeInTheDocument();
  });

  it('says a missing role is a result, not a gap', async () => {
    // vid has a rival and prey but no nemesis: nobody kills him 70% of the
    // time. "—" would read as missing data about a measured fact.
    renderPage('?guid=D8423F90');
    await waitFor(() => expect(screen.getByText('nobody wins 70% against them')).toBeInTheDocument());
    expect(screen.getAllByText(/opponents/).length).toBeGreaterThan(0);
  });

  it('separates an untracked id from a player without rivals', async () => {
    const unresolved = { ...player, resolved: false, all_pairs: [], total_opponents: 0, player_name: null };
    renderPage('?guid=AAAAAAAA', (input) => {
      const url = String(input);
      if (url.includes('/rivalries/player/')) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(unresolved) } as Response);
      }
      return fixtureFetch(input);
    });
    await waitFor(() => expect(screen.getByText(/never tracked/)).toBeInTheDocument());
  });

  it('tells two opponents apart when they share a display name', async () => {
    // Measured in the recording: `ownator` appears twice in vid's list —
    // FB0EC840 and EF561EAA, the sick-leave alt from migration 073. Two
    // identical names against different numbers is a page contradicting
    // itself, so the id joins the name exactly where it has to.
    renderPage('?guid=D8423F90');
    await waitFor(() => expect(screen.getAllByText('ownator').length).toBe(2));
    expect(screen.getByText('FB0EC840')).toBeInTheDocument();
    expect(screen.getByText('EF561EAA')).toBeInTheDocument();
    // …and only where it has to: an unambiguous name carries no id.
    expect(screen.queryByText('5D989160')).toBeNull();
  });

  it('links both sides of a pair to their profiles by the short GUID', async () => {
    // The page receives 32-character GUIDs and every profile route in this
    // app takes the 8-character form.
    renderPage();
    await waitFor(() => expect(screen.getAllByRole('link').length).toBeGreaterThan(2));
    const hrefs = screen.getAllByRole('link').map((a) => a.getAttribute('href') ?? '');
    expect(hrefs.some((h) => h === '/profile/5D989160')).toBe(true);
    expect(hrefs.some((h) => h === '/profile/D8423F90')).toBe(true);
    expect(hrefs.every((h) => !/\/profile\/[0-9A-F]{9,}/.test(h))).toBe(true);
  });
});
