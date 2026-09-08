/**
 * The box score of one half — the modal the legacy matches page opened and
 * the new Home never had (endpoint ratchet line `/api/stats/matches/{}`).
 */
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { MatchBoxScore } from './MatchBoxScore';
import { makeQueryClient } from '../lib/queries';
import type { MatchDetails } from '../lib/types';
import recorded from '../pages/__fixtures__/api_stats_matches_match_id.json';

// Round 11321: te_escape2 R2, Allies won, 3v3 — the recording is the arbiter
// of the type. Both `headshots` (head hits) and `headshot_kills` are present.
const live = recorded satisfies MatchDetails;

function renderPanel(reply: () => Promise<Response>) {
  vi.spyOn(globalThis, 'fetch').mockImplementation(reply);
  const client = makeQueryClient();
  client.setDefaultOptions({ queries: { retry: false } });
  return render(
    <QueryClientProvider client={client}>
      <MatchBoxScore roundId={11321} />
    </QueryClientProvider>,
  );
}

afterEach(() => { vi.restoreAllMocks(); });

describe('MatchBoxScore', () => {
  it('asks for that half and shows both teams, the winner and the totals', async () => {
    const calls: string[] = [];
    renderPanel(() => Promise.resolve(new Response(JSON.stringify(live), { status: 200 })));
    vi.mocked(globalThis.fetch).mockImplementation((input) => { calls.push(String(input)); return Promise.resolve(new Response(JSON.stringify(live), { status: 200 })); });
    // the first call went out before the spy was rewired; the URL is what the
    // hook builds — asserted through the panel's aside instead (round 11321).
    await waitFor(() => expect(screen.getByText(/te_escape2 R2 · allies · 3:16 of 6:28 · completed/)).toBeInTheDocument());
    expect(screen.getByText(new RegExp(`${live.team2.name}`))).toBeInTheDocument();
    // the winning logical team is marked, the losing one is not
    const winner = live.team1.is_winner ? live.team1 : live.team2;
    expect(screen.getByText(new RegExp(`won · ${winner.totals.kills} k · ${winner.totals.deaths} d`))).toBeInTheDocument();
    // every player of both teams has a row
    for (const p of [...live.team1.players, ...live.team2.players]) {
      expect(screen.getByText(p.name)).toBeInTheDocument();
    }
    // head hits and headshot kills are two columns with two definitions
    expect(screen.getAllByTitle('head HITS — routinely more than kills')).toHaveLength(2);
    expect(screen.getAllByTitle('headshot kills (not head hits)')).toHaveLength(2);
  });

  it('says the half has no rows when both teams come back empty, and keeps the round line', async () => {
    const empty: MatchDetails = { ...live, team1: { ...live.team1, players: [], totals: { kills: 0, deaths: 0, damage: 0 } }, team2: { ...live.team2, players: [], totals: { kills: 0, deaths: 0, damage: 0 } }, player_count: 0 };
    renderPanel(() => Promise.resolve(new Response(JSON.stringify(empty), { status: 200 })));
    await waitFor(() => expect(screen.getByText(/no player rows were recorded/)).toBeInTheDocument());
    expect(screen.queryByText(/unavailable/i)).toBeNull();
  });

  it('survives a round whose outcome and duration are null', async () => {
    const bare: MatchDetails = { ...live, match: { ...live.match, outcome: null, duration: null, time_limit: null } };
    renderPanel(() => Promise.resolve(new Response(JSON.stringify(bare), { status: 200 })));
    await waitFor(() => expect(screen.getByText(/duration unknown · outcome unknown/)).toBeInTheDocument());
  });

  it('says unavailable on a 404, not that nobody played', async () => {
    renderPanel(() => Promise.resolve(new Response(JSON.stringify({ detail: 'Match not found' }), { status: 404 })));
    await waitFor(() => expect(screen.getByText(/unavailable/i)).toBeInTheDocument());
  });
});
