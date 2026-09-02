import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { ProximityReplayPage } from './ProximityReplayPage';
import type { ProxRoundTimeline, ProxRoundTracks, ReplayTimelineEvent } from '../lib/types';
import timelineJson from './__fixtures__/api_proximity_round_round_id_timeline.json';
import tracksJson from './__fixtures__/api_proximity_round_round_id_tracks.json';
import uncapturedJson from './__fixtures__/api_proximity_timeline_uncaptured_form.json';

// The recorded round (11344, et_brewdog r2) carries all FOUR event types —
// chosen for that, so the union has no branch a fixture cannot reach.
// `satisfies` cannot hold a JSON import against a DISCRIMINATED union (the
// import widens `type` to string), so the union check runs at runtime
// below — it fails the suite on an unknown type or a missing member key,
// which is the same guarantee by another door.
const timeline = timelineJson as unknown as ProxRoundTimeline;
const tracks = tracksJson satisfies ProxRoundTracks;
const uncaptured = uncapturedJson as unknown as ProxRoundTimeline;

const REQUIRED_KEYS: Record<ReplayTimelineEvent['type'], string[]> = {
  engagement: ['id', 'time', 'victim_name', 'victim_team', 'outcome', 'damage', 'attackers'],
  spawn_timing_kill: ['time', 'attacker_name', 'victim_name', 'score'],
  trade_kill: ['time', 'trader_name', 'avenged_name', 'delta_ms'],
  team_push: ['time', 'team', 'quality', 'alignment', 'participants', 'duration_ms'],
};

describe('the recorded timeline fixture against the union', () => {
  it('carries only known event types, each with its required keys, and all four are present', () => {
    const seen = new Set<string>();
    for (const e of timelineJson.events) {
      const keys = REQUIRED_KEYS[e.type as ReplayTimelineEvent['type']];
      expect(keys, `unknown event type on the wire: ${e.type}`).toBeDefined();
      for (const k of keys) {
        expect(e, `${e.type} event missing ${k}`).toHaveProperty(k);
      }
      seen.add(e.type);
    }
    expect([...seen].sort()).toEqual(['engagement', 'spawn_timing_kill', 'team_push', 'trade_kill']);
  });
});

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
