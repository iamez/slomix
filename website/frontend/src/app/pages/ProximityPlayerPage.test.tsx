import { render, screen, waitFor } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { ProximityPlayerPage } from './ProximityPlayerPage';
import type {
  ProxHitRegions, ProxHitRegionsByWeapon, ProxKillOutcomePlayerStats,
  ProxMovementStats, ProxPlayerProfile, ProxPlayerRadar, ProxScores,
} from '../lib/types';
import profileJson from './__fixtures__/api_proximity_player_guid_profile.json';
import radarJson from './__fixtures__/api_proximity_player_guid_radar.json';
import radarFallback from './__fixtures__/api_proximity_player_radar_fallback_form.json';
import scoresJson from './__fixtures__/api_proximity_prox_scores.json';
import outcomesJson from './__fixtures__/api_proximity_kill_outcomes_player_stats.json';
import hitRegionsJson from './__fixtures__/api_proximity_hit_regions.json';
import byWeaponJson from './__fixtures__/api_proximity_hit_regions_by_weapon.json';
import movementJson from './__fixtures__/api_proximity_movement_stats.json';

// `satisfies` holds every RECORDED fixture against its wire type. The radar
// has TWO recorded forms: the scored one (no fallback keys) and the
// degraded one (sample_count + fallback_reason present) — both must fit.
const profile = profileJson satisfies ProxPlayerProfile;
const radar = radarJson satisfies ProxPlayerRadar;
const radarFallbackChecked = radarFallback satisfies ProxPlayerRadar;
const scores = scoresJson satisfies ProxScores;
const outcomes = outcomesJson satisfies ProxKillOutcomePlayerStats;
const hitRegions = hitRegionsJson satisfies ProxHitRegions;
const byWeapon = byWeaponJson satisfies ProxHitRegionsByWeapon;
const movement = movementJson satisfies ProxMovementStats;

const GUID = '1EDBF3002CE66FE4DFA626D92130E561';

const BODIES = new Map<string, unknown>([
  [`/api/proximity/player/${GUID}/profile`, profile],
  [`/api/proximity/player/${GUID}/radar`, radar],
  ['/api/proximity/prox-scores', scores],
  ['/api/proximity/kill-outcomes/player-stats', outcomes],
  ['/api/proximity/hit-regions', hitRegions],
  ['/api/proximity/hit-regions/by-weapon', byWeapon],
  ['/api/proximity/movement-stats', movement],
]);

function fetchFor(overrides?: Map<string, unknown>) {
  return (input: RequestInfo | URL): Promise<Response> => {
    const pathname = String(input).split('?')[0];
    const body = overrides?.get(pathname) ?? BODIES.get(pathname);
    if (body === undefined) return Promise.reject(new Error(`unexpected endpoint: ${pathname}`));
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);
  };
}

function renderPage(guid: string = GUID) {
  return render(
    <QueryClientProvider client={makeQueryClient()}>
      <MemoryRouter initialEntries={[`/proximity/player/${guid}`]}>
        <Routes>
          <Route path="/proximity/player/:guid" element={<ProximityPlayerPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe('ProximityPlayerPage', () => {
  it('renders every panel from the recorded wire', async () => {
    vi.stubGlobal('fetch', vi.fn(fetchFor()));
    renderPage();
    // Header: colour codes stripped ('^7kan^6i^7i' → 'kanii').
    await waitFor(() => expect(screen.getByRole('heading', { name: 'kanii' })).toBeInTheDocument());
    // The record: 8,054 engagements, 2,046 kills, 45.9% escapes, 301 trades.
    expect(screen.getByText('8,054')).toBeInTheDocument();
    expect(screen.getByText('2,046')).toBeInTheDocument();
    expect(screen.getByText('45.9%')).toBeInTheDocument();
    expect(screen.getByText('301')).toBeInTheDocument();
    // Radar drawn with its recorded composite and formula version.
    await waitFor(() => expect(screen.getByLabelText('player radar')).toBeInTheDocument());
    expect(screen.getByText('40.2')).toBeInTheDocument();
    expect(screen.getByText('player-radar-v2')).toBeInTheDocument();
    // Prox score: overall 32.81 → '32.8', rank 1 in window.
    await waitFor(() => expect(screen.getByText('32.8')).toBeInTheDocument());
    expect(screen.getByText(/rank 1 in window/)).toBeInTheDocument();
    // Kill permanence: 40 gibs of 2,032 kills; own revive rate 21.7%.
    expect(screen.getByText(/40 of 2,032/)).toBeInTheDocument();
    expect(screen.getByText('21.7%')).toBeInTheDocument();
    // Per weapon: engine ids named, not guessed (8 = MP40).
    expect(screen.getByText('MP40')).toBeInTheDocument();
    // Movement: standing share from the recorded row.
    expect(screen.getByText(/stand 70.5%/)).toBeInTheDocument();
    // Every panel names its window.
    expect(screen.getAllByText(/90d/).length).toBeGreaterThan(2);
    expect(screen.getByText(/30d window/)).toBeInTheDocument();
  });

  it('treats the zero-form as "nothing captured", never as a player of zeros', async () => {
    // Recorded live: an unknown guid answers 200 with every number 0 and
    // the guid echoed as player_name.
    const zero: ProxPlayerProfile = {
      ...profile, player_name: GUID, total_engagements: 0, escapes: 0,
      deaths: 0, escape_rate: 0, total_kills: 0, crossfire_count: 0,
      trades_made: 0, timed_kills: 0,
    };
    vi.stubGlobal('fetch', vi.fn(fetchFor(new Map([[`/api/proximity/player/${GUID}/profile`, zero]]))));
    renderPage();
    await waitFor(() => expect(screen.getByText(/no proximity capture for this player/)).toBeInTheDocument());
    expect(screen.queryByText('escape rate')).not.toBeInTheDocument();
  });

  it('every call carries the guid and a named window', async () => {
    const fetchSpy = vi.fn(fetchFor());
    vi.stubGlobal('fetch', fetchSpy);
    renderPage();
    await waitFor(() => expect(screen.getByRole('heading', { name: 'kanii' })).toBeInTheDocument());
    const calls = fetchSpy.mock.calls.map((c) => String(c[0]));
    expect(calls.length).toBeGreaterThanOrEqual(7);
    for (const u of calls) {
      expect(u, `unscoped call: ${u}`).toMatch(/range_days=\d+/);
      expect(u, `call without the player: ${u}`).toMatch(new RegExp(`player_guid=${GUID}|/player/${GUID}/`));
    }
  });

  it('surfaces the degraded teamplay axis instead of hiding it', async () => {
    vi.stubGlobal('fetch', vi.fn(fetchFor(new Map([[`/api/proximity/player/${GUID}/radar`, radarFallbackChecked]]))));
    renderPage();
    await waitFor(() => expect(screen.getByRole('heading', { name: 'kanii' })).toBeInTheDocument());
    if (radarFallbackChecked.teamplay_degraded) {
      await waitFor(() => expect(screen.getByText(/teamplay axis degraded/)).toBeInTheDocument());
    }
  });
});
