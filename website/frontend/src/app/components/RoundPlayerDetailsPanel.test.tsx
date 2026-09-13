/**
 * One player's breakdown of one half — the drilldown the legacy matches page
 * opened in a modal and the new session page never had (endpoint ratchet
 * line `/api/rounds/{}/player/{}/details`, closed here).
 */
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { RoundPlayerDetailsPanel } from './RoundsTab';
import { makeQueryClient } from '../lib/queries';
import type { RoundPlayerDetails } from '../lib/types';
import recorded from '../pages/__fixtures__/api_rounds_round_id_player_player_guid_details.json';

// The recorded answer is the arbiter of the type: round 11430, one player,
// three weapons, one of them with deaths only (the MP40 that killed him).
const live = recorded satisfies RoundPlayerDetails;

function renderPanel(reply: () => Promise<Response>) {
  vi.spyOn(globalThis, 'fetch').mockImplementation(reply);
  const client = makeQueryClient();
  client.setDefaultOptions({ queries: { retry: false } });
  return render(
    <QueryClientProvider client={client}>
      <RoundPlayerDetailsPanel roundId={11430} playerGuid="E587CA5F" />
    </QueryClientProvider>,
  );
}

afterEach(() => { vi.restoreAllMocks(); });

describe('RoundPlayerDetailsPanel', () => {
  it('asks for that round and that player, and shows the groups the session table has no column for', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      void input;
      return Promise.resolve(new Response(JSON.stringify(live), { status: 200 }));
    });
    renderPanel(fetchMock as unknown as () => Promise<Response>);
    await waitFor(() => expect(screen.getByText(/imma\^>koala · etl_sp_delivery R2/)).toBeInTheDocument());
    expect(fetchMock.mock.calls.map((c) => String(c[0])).join(' ')).toContain('/api/rounds/11430/player/E587CA5F/details');
    // objectives and dynamite — the legacy modal's own columns
    expect(screen.getByText('objectives stolen')).toBeInTheDocument();
    expect(screen.getByText('dynamite planted')).toBeInTheDocument();
    // weapons by label, never by token, with the deaths column
    expect(screen.getByText('Thompson')).toBeInTheDocument();
    expect(screen.getByText('MP40')).toBeInTheDocument();
    expect(screen.queryByText(/WS_/)).toBeNull();
    expect(screen.getByTitle('deaths to this weapon')).toBeInTheDocument();
    // played 204 s → 3:24; useful kills live under support in the recording
    expect(screen.getByText('3:24')).toBeInTheDocument();
    expect(screen.getByText('useful kills')).toBeInTheDocument();
  });

  it('says the breakdown is unavailable on a 404, not that the player had nothing', async () => {
    renderPanel(() => Promise.resolve(new Response(JSON.stringify({ detail: 'Player stats not found' }), { status: 404 })));
    await waitFor(() => expect(screen.getByText(/unavailable/i)).toBeInTheDocument());
    expect(screen.queryByText('objectives stolen')).toBeNull();
  });
});
