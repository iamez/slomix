import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { ProximityReplayPage } from './ProximityReplayPage';
import type { ProxRoundTimeline, ProxRoundTracks } from '../lib/types';
import timelineJson from './__fixtures__/api_proximity_round_round_id_timeline.json';
import tracksJson from './__fixtures__/api_proximity_round_round_id_tracks.json';
import uncapturedJson from './__fixtures__/api_proximity_timeline_uncaptured_form.json';

// The recorded round (11344, et_brewdog r2) carries all FOUR event types —
// chosen for that, so the union has no branch a fixture cannot reach.
const timeline = timelineJson satisfies ProxRoundTimeline;
const tracks = tracksJson satisfies ProxRoundTracks;
const uncaptured = uncapturedJson satisfies ProxRoundTimeline;

function stub(bodies: Map<string, unknown | { status: number }>) {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL): Promise<Response> => {
    const pathname = String(input).split('?')[0];
    const body = bodies.get(pathname);
    if (body === undefined) return Promise.reject(new Error(`unexpected endpoint: ${pathname}`));
    if (typeof body === 'object' && body != null && 'status' in body && Object.keys(body).length === 1) {
      const s = (body as { status: number }).status;
      return Promise.resolve({ ok: false, status: s, json: () => Promise.resolve({ detail: 'x' }) } as Response);
    }
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);
  }));
}

function renderAt(roundId: string) {
  return render(
    <QueryClientProvider client={makeQueryClient()}>
      <MemoryRouter initialEntries={[`/proximity/round/${roundId}`]}>
        <Routes>
          <Route path="/proximity/round/:roundId" element={<ProximityReplayPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe('ProximityReplayPage', () => {
  it('renders all four event shapes, the strip and the track stats from the recorded wire', async () => {
    stub(new Map<string, unknown>([
      ['/api/proximity/round/11344/timeline', timeline],
      ['/api/proximity/round/11344/tracks', tracks],
    ]));
    renderAt('11344');
    await waitFor(() => expect(screen.getByText(/3:08 played/)).toBeInTheDocument());
    expect(screen.getByLabelText('round timeline')).toBeInTheDocument();
    expect(screen.getByText(/158 events/)).toBeInTheDocument();
    // One recorded line per union member:
    expect(screen.getAllByText(/\.olz killed/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/SuperBoyy avenged Cru3lzor\./).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/kanii timed SuperBoyy/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/allies push · 3 players/).length).toBeGreaterThan(0);
    // Tracks: 27 recorded lives across both teams.
    await waitFor(() => expect(screen.getByText('27')).toBeInTheDocument());
    expect(screen.getByText('axis')).toBeInTheDocument();
  });

  it('the type filter narrows the list to one shape', async () => {
    stub(new Map<string, unknown>([
      ['/api/proximity/round/11344/timeline', timeline],
      ['/api/proximity/round/11344/tracks', tracks],
    ]));
    renderAt('11344');
    await waitFor(() => expect(screen.getByText(/3:08 played/)).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'trades' }));
    // 4 recorded trade kills; engagements are filtered out.
    expect(screen.getAllByText(/avenged/).length).toBe(4);
    expect(screen.queryByText(/\.olz killed/)).not.toBeInTheDocument();
  });

  it('renders the uncaptured form as absence with the round metadata kept', async () => {
    stub(new Map<string, unknown>([
      ['/api/proximity/round/10472/timeline', uncaptured],
      ['/api/proximity/round/10472/tracks', { status: 404 }],
    ]));
    renderAt('10472');
    await waitFor(() => expect(screen.getByText(/no proximity capture for this round/)).toBeInTheDocument());
    // The metadata still names the round (sw_goldrush_te r0, 2026-04-21).
    expect(screen.getByText(/2026-04-21/)).toBeInTheDocument();
  });

  it('a nonexistent id (404) is absence, not failure', async () => {
    stub(new Map<string, unknown>([
      ['/api/proximity/round/99999999/timeline', { status: 404 }],
      ['/api/proximity/round/99999999/tracks', { status: 404 }],
    ]));
    renderAt('99999999');
    await waitFor(() => expect(screen.getByText(/no round has id 99,?999,?999/)).toBeInTheDocument());
    expect(screen.queryByText(/unavailable/i)).not.toBeInTheDocument();
  });
});
