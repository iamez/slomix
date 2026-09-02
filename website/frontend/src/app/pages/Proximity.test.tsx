import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { Proximity } from './Proximity';
import type { ProximityLeaderboard } from '../lib/types';
import boardJson from './__fixtures__/api_proximity_leaderboards.json';
import scopes from './__fixtures__/api_proximity_scopes.json';
import quality from './__fixtures__/api_proximity_quality.json';
import spawnTiming from './__fixtures__/api_proximity_spawn_timing.json';
import aimLock from './__fixtures__/api_proximity_aim_lock.json';
import cohesion from './__fixtures__/api_proximity_cohesion.json';
import crossfireAngles from './__fixtures__/api_proximity_crossfire_angles.json';
import pushes from './__fixtures__/api_proximity_pushes.json';
import luaTrades from './__fixtures__/api_proximity_lua_trades.json';
import revives from './__fixtures__/api_proximity_revives.json';
import focusFire from './__fixtures__/api_proximity_focus_fire.json';
import supportSummary from './__fixtures__/api_proximity_support_summary.json';
import combatPositions from './__fixtures__/api_proximity_combat_position_stats.json';
import classes from './__fixtures__/api_proximity_classes.json';
import reactions from './__fixtures__/api_proximity_reactions.json';
import compStagger from './__fixtures__/api_proximity_competitive_stagger.json';
import compFirstBlood from './__fixtures__/api_proximity_competitive_first_blood.json';
import compBests from './__fixtures__/api_proximity_competitive_personal_bests.json';
import compAdvantage from './__fixtures__/api_proximity_competitive_man_advantage.json';
import compClutch from './__fixtures__/api_proximity_competitive_clutch.json';
import compSplits from './__fixtures__/api_proximity_competitive_side_splits.json';
import v7Status from './__fixtures__/api_proximity_v7_status.json';
import carrierEvents from './__fixtures__/api_proximity_carrier_events.json';
import carrierKills from './__fixtures__/api_proximity_carrier_kills.json';
import carrierReturns from './__fixtures__/api_proximity_carrier_returns.json';
import vehicleProgress from './__fixtures__/api_proximity_vehicle_progress.json';
import escortCredits from './__fixtures__/api_proximity_escort_credits.json';
import constructionEvents from './__fixtures__/api_proximity_construction_events.json';
import objectiveRuns from './__fixtures__/api_proximity_objective_runs.json';
import objectiveFocus from './__fixtures__/api_proximity_objective_focus.json';
import proxPlayers from './__fixtures__/api_proximity_players.json';
import journey from './__fixtures__/api_proximity_player_journey.json';
import heatmap from './__fixtures__/api_proximity_push_deaths_heatmap.json';
import waveCycles from './__fixtures__/api_proximity_competitive_wave_cycles.json';
import proxEvents from './__fixtures__/api_proximity_events.json';
import eventLong from './__fixtures__/api_proximity_event_event_id.json';
import eventShort from './__fixtures__/api_proximity_event_short.json';
import engagements from './__fixtures__/api_proximity_engagements.json';
import killOutcomes from './__fixtures__/api_proximity_kill_outcomes.json';
import headshotRates from './__fixtures__/api_proximity_hit_regions_headshot_rates.json';
import teamplay from './__fixtures__/api_proximity_teamplay.json';
import tradesSummary from './__fixtures__/api_proximity_trades_summary.json';
import tradesEvents from './__fixtures__/api_proximity_trades_events.json';
import weaponAccuracy from './__fixtures__/api_proximity_weapon_accuracy.json';
import objectivePressure from './__fixtures__/api_proximity_objective_pressure.json';
import proxSummary from './__fixtures__/api_proximity_summary.json';
import type {
  CarrierEvents, CarrierKills, CarrierReturns, ConstructionEvents,
  EscortCredits, ObjectiveFocus, ObjectiveRuns, ProxEngagements,
  ProxEventDetail, ProxEvents, ProxHeadshotRates, ProxKillOutcomes,
  ProxObjectivePressure, ProxSummary, ProxTeamplay, ProxTradesEvents,
  ProxTradesSummary, ProxWeaponAccuracy, VehicleProgress,
} from '../lib/types';

// `satisfies` holds each RECORDED fixture against its wire type — the same
// check that caught attribution.mode on #856 (CodeRabbit on #864: a map of
// `unknown` lets a renamed field mock successfully while the page reads the
// wrong shape).
const carrierEventsChecked = carrierEvents satisfies CarrierEvents;
const carrierKillsChecked = carrierKills satisfies CarrierKills;
const carrierReturnsChecked = carrierReturns satisfies CarrierReturns;
const vehicleProgressChecked = vehicleProgress satisfies VehicleProgress;
const escortCreditsChecked = escortCredits satisfies EscortCredits;
const constructionEventsChecked = constructionEvents satisfies ConstructionEvents;
const objectiveRunsChecked = objectiveRuns satisfies ObjectiveRuns;
const objectiveFocusChecked = objectiveFocus satisfies ObjectiveFocus;
const proxEventsChecked = proxEvents satisfies ProxEvents;
// The drill-down's TWO recorded forms — the long one (valid times: attackers
// parsed, strafe present) and the short one (zero times: attackers still the
// raw DB string, the strafe-branch keys ABSENT). Both must satisfy the union.
const eventLongChecked = eventLong satisfies ProxEventDetail;
const eventShortChecked = eventShort satisfies ProxEventDetail;
const engagementsChecked = engagements satisfies ProxEngagements;
const killOutcomesChecked = killOutcomes satisfies ProxKillOutcomes;
const headshotRatesChecked = headshotRates satisfies ProxHeadshotRates;
const teamplayChecked = teamplay satisfies ProxTeamplay;
const tradesSummaryChecked = tradesSummary satisfies ProxTradesSummary;
const tradesEventsChecked = tradesEvents satisfies ProxTradesEvents;
const weaponAccuracyChecked = weaponAccuracy satisfies ProxWeaponAccuracy;
const objectivePressureChecked = objectivePressure satisfies ProxObjectivePressure;
const proxSummaryChecked = proxSummary satisfies ProxSummary;

const INSTRUMENTS = new Map<string, unknown>([
  ['/api/proximity/scopes', scopes],
  ['/api/proximity/quality', quality],
  ['/api/proximity/spawn-timing', spawnTiming],
  ['/api/proximity/aim-lock', aimLock],
  ['/api/proximity/cohesion', cohesion],
  ['/api/proximity/crossfire-angles', crossfireAngles],
  ['/api/proximity/pushes', pushes],
  ['/api/proximity/lua-trades', luaTrades],
  ['/api/proximity/revives', revives],
  ['/api/proximity/focus-fire', focusFire],
  ['/api/proximity/support-summary', supportSummary],
  ['/api/proximity/combat-position-stats', combatPositions],
  ['/api/proximity/classes', classes],
  ['/api/proximity/reactions', reactions],
  ['/api/proximity/competitive/stagger', compStagger],
  ['/api/proximity/competitive/first-blood', compFirstBlood],
  ['/api/proximity/competitive/personal-bests', compBests],
  ['/api/proximity/competitive/man-advantage', compAdvantage],
  ['/api/proximity/competitive/clutch', compClutch],
  ['/api/proximity/competitive/side-splits', compSplits],
  ['/api/proximity/v7-status', v7Status],
  ['/api/proximity/carrier-events', carrierEventsChecked],
  ['/api/proximity/carrier-kills', carrierKillsChecked],
  ['/api/proximity/carrier-returns', carrierReturnsChecked],
  ['/api/proximity/vehicle-progress', vehicleProgressChecked],
  ['/api/proximity/escort-credits', escortCreditsChecked],
  ['/api/proximity/construction-events', constructionEventsChecked],
  ['/api/proximity/objective-runs', objectiveRunsChecked],
  ['/api/proximity/objective-focus', objectiveFocusChecked],
  ['/api/proximity/players', proxPlayers],
  ['/api/proximity/player-journey', journey],
  ['/api/proximity/push-deaths/heatmap', heatmap],
  ['/api/proximity/competitive/wave-cycles', waveCycles],
  ['/api/proximity/events', proxEventsChecked],
  ['/api/proximity/engagements', engagementsChecked],
  ['/api/proximity/event/297937', eventLongChecked],
  ['/api/proximity/event/297936', eventShortChecked],
  ['/api/proximity/kill-outcomes', killOutcomesChecked],
  ['/api/proximity/hit-regions/headshot-rates', headshotRatesChecked],
  ['/api/proximity/teamplay', teamplayChecked],
  ['/api/proximity/trades/summary', tradesSummaryChecked],
  ['/api/proximity/trades/events', tradesEventsChecked],
  ['/api/proximity/weapon-accuracy', weaponAccuracyChecked],
  ['/api/proximity/objective-pressure', objectivePressureChecked],
  ['/api/proximity/summary', proxSummaryChecked],
]);

// `satisfies` makes the compiler hold the RECORDED fixture against the
// declared wire type — this is what caught attribution.mode being a string
// while the type only allowed numeric extensions (CodeRabbit on #856).
const board = boardJson satisfies ProximityLeaderboard;

/** Rendered against the RECORDED power board (10 entries, attribution
 * block, formula_version) — every asserted string is something the backend
 * really said on 31. 8. */

function fetchFor(bodyByPath: Map<string, unknown>) {
  return (input: RequestInfo | URL): Promise<Response> => {
    const pathname = String(input).split('?')[0];
    const body = bodyByPath.get(pathname) ?? INSTRUMENTS.get(pathname);
    if (body === undefined) {
      return Promise.reject(new Error(`Proximity called an unexpected endpoint: ${pathname}`));
    }
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);
  };
}

function renderPage() {
  const client = makeQueryClient();
  client.setDefaultOptions({ queries: { retry: false } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Proximity />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('Proximity', () => {
  it('opens on the power board with the attribution the wire sent', async () => {
    vi.stubGlobal('fetch', vi.fn(fetchFor(new Map([['/api/proximity/leaderboards', board]]))));
    renderPage();
    const first = (board as { entries: { name: string }[] }).entries[0];
    // The recorded first entry, colour codes stripped.
    await waitFor(() =>
      expect(screen.getByText(first.name.replace(/\^[0-9A-Za-z]/g, ''))).toBeInTheDocument(),
    );
    // The attribution block is the board's own honesty statement — it must
    // survive the render, not just the wire.
    expect(screen.getByText(/source rows linkable/)).toBeInTheDocument();
  });

  it('names all ten boards, so none can be lost at build time', () => {
    vi.stubGlobal('fetch', vi.fn(fetchFor(new Map([['/api/proximity/leaderboards', board]]))));
    renderPage();
    for (const label of [
      'power rating', 'spawn timing', 'crossfire', 'trade kills', 'reactions',
      'survivors', 'movement', 'focus fire', 'krogt', 'comp skill',
    ]) {
      expect(screen.getByRole('tab', { name: label })).toBeInTheDocument();
    }
  });

  it('renders an empty window as a reasoned absence, not a blank board', async () => {
    vi.stubGlobal('fetch', vi.fn(fetchFor(new Map([
      ['/api/proximity/leaderboards', { status: 'ok', category: 'power', entries: [] }],
    ]))));
    renderPage();
    await waitFor(() =>
      expect(screen.getByText(/proximity capture only covers sessions where the tracker ran/)).toBeInTheDocument(),
    );
  });

  it('renders the instruments against the recorded scope, quality band first', async () => {
    vi.stubGlobal('fetch', vi.fn(fetchFor(new Map([['/api/proximity/leaderboards', board]]))));
    renderPage();
    // The data-completeness band is the truth strip the design asks for —
    // it must render the per-source chips, correlation completeness, and
    // the recorded scope's numbers, not a generic 'ok'.
    await waitFor(() => expect(screen.getByText(/correlation 99\.1%/)).toBeInTheDocument());
    // One leader from each of two instruments, colour codes stripped —
    // both values the backend really said.
    const spawnLeader = (spawnTiming as { leaders: { name: string }[] }).leaders[0];
    await waitFor(() =>
      expect(screen.getAllByText(spawnLeader.name.replace(/\^[0-9A-Za-z]/g, '')).length).toBeGreaterThan(0),
    );
    // Crossfire duos carry partner_name HERE (the field legacy tried to
    // read off the leaderboards endpoint, which never sent it).
    expect(screen.getByText(/kanii \+ bronze/)).toBeInTheDocument();
  });

  it('scopes the instruments to the newest CAPTURE date by default', async () => {
    const fetchSpy = vi.fn(fetchFor(new Map([['/api/proximity/leaderboards', board]])));
    vi.stubGlobal('fetch', fetchSpy);
    renderPage();
    await waitFor(() => expect(screen.getByText(/correlation/)).toBeInTheDocument());
    const newest = (scopes as { sessions: { session_date: string }[] }).sessions[0].session_date;
    const instrumentCalls = fetchSpy.mock.calls
      .map((c) => String(c[0]))
      // v7-status is the ONE deliberate exemption: the capture roadmap is
      // global by design (no scope parameter exists on it).
      .filter((u) => u.includes('/api/proximity/') && !u.includes('leaderboards') && !u.includes('scopes') && !u.includes('v7-status'));
    expect(instrumentCalls.length).toBeGreaterThan(0);
    for (const u of instrumentCalls) {
      // ⛔ Unscoped instruments measured up to 1.9 s cold — the first
      // paint must NEVER be the unbounded window.
      expect(u, `unscoped instrument call: ${u}`).toContain(`session_date=${newest}`);
    }
  });

  it('mounts nothing unscoped when the scope lookup fails', async () => {
    // Three reviewers independently: a failed /proximity/scopes must not
    // fall through into thirteen unbounded instrument queries.
    const fetchSpy = vi.fn((input: RequestInfo | URL) => {
      const pathname = String(input).split('?')[0];
      if (pathname === '/api/proximity/scopes') {
        return Promise.resolve({ ok: false, status: 503, json: () => Promise.resolve({}) } as Response);
      }
      const body = new Map([['/api/proximity/leaderboards', board as unknown]]).get(pathname) ?? INSTRUMENTS.get(pathname);
      if (body === undefined) return Promise.reject(new Error(`unexpected: ${pathname}`));
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);
    });
    vi.stubGlobal('fetch', fetchSpy);
    renderPage();
    await waitFor(() => expect(screen.getByText(/capture dates: unavailable/)).toBeInTheDocument());
    const instrumentCalls = fetchSpy.mock.calls
      .map((c) => String(c[0]))
      // v7-status is the ONE deliberate exemption: the capture roadmap is
      // global by design (no scope parameter exists on it).
      .filter((u) => u.includes('/api/proximity/') && !u.includes('leaderboards') && !u.includes('scopes') && !u.includes('v7-status'));
    expect(instrumentCalls).toEqual([]);
  });

  it('never calls a round-scoped canvas endpoint before the picker has its scope', async () => {
    // These endpoints 422 without map/round — the wire demanding scope.
    // The picker must make that state unreachable: no map or round is
    // picked in this render, so none of the three may be fetched.
    const fetchSpy = vi.fn(fetchFor(new Map([['/api/proximity/leaderboards', board]])));
    vi.stubGlobal('fetch', fetchSpy);
    renderPage();
    await waitFor(() => expect(screen.getByText(/correlation/)).toBeInTheDocument());
    const canvasCalls = fetchSpy.mock.calls
      .map((c) => String(c[0]))
      .filter((u) => u.includes('player-journey') || u.includes('push-deaths') || u.includes('wave-cycles'));
    expect(canvasCalls).toEqual([]);
    // And the section says what to do instead of showing nothing.
    expect(screen.getByText(/pick a map above/)).toBeInTheDocument();
  });

  it('renders the engagement record from the recorded wire: dispersion buckets and the events list', async () => {
    vi.stubGlobal('fetch', vi.fn(fetchFor(new Map([['/api/proximity/leaderboards', board]]))));
    renderPage();
    // The dispersion bucket really recorded: 1,581 engagements / 139 crossfires.
    await waitFor(() => expect(screen.getByText(/139 crossfires/)).toBeInTheDocument());
    // Colour codes stripped the ET way: '^7c^3a^7rniee' → 'carniee'.
    expect(screen.getAllByText(/carniee · supply r2/).length).toBeGreaterThan(0);
    // No drill-down was fetched before any row was clicked.
    const detailCalls = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls
      .map((c) => String(c[0])).filter((u) => u.includes('/api/proximity/event/'));
    expect(detailCalls).toEqual([]);
  });

  it('opens one drill-down at a time and survives BOTH recorded forms', { timeout: 20000 }, async () => {
    const fetchSpy = vi.fn(fetchFor(new Map([['/api/proximity/leaderboards', board]])));
    vi.stubGlobal('fetch', fetchSpy);
    renderPage();
    await waitFor(() => expect(screen.getByText(/139 crossfires/)).toBeInTheDocument());
    // Long form (recorded from event 297920, served for the first
    // 'carniee' row's id): attackers parsed, BOTH tracks drawn (16-point
    // target, 15-point attacker), strafe compared.
    fireEvent.click(screen.getAllByRole('button', { name: /carniee · supply r2/ })[0]);
    await waitFor(() => expect(screen.getByText(/\.lgz · 3 hits · 107 dmg/)).toBeInTheDocument());
    expect(screen.getByText(/carniee · 2 hits · 36 dmg/)).toBeInTheDocument();
    expect(screen.getByLabelText('engagement path')).toBeInTheDocument();
    expect(screen.getByText('solid — target · dashed — attacker')).toBeInTheDocument();
    expect(screen.getByText(/movement — target 283 u\/s · 3 turns/)).toBeInTheDocument();
    // Short form (served for the 'vid' row's id; recorded from event
    // 306062): attackers is the RAW DB string WITH a real record inside —
    // the panel must parse it (.lgz · 1 hits · 166 dmg), not blank it,
    // and the 3-point path still draws.
    fireEvent.click(screen.getAllByRole('button', { name: /vid · supply r2/ })[0]);
    await waitFor(() => expect(screen.getByText(/\.lgz · 1 hits · 166 dmg/)).toBeInTheDocument());
    expect(screen.getByLabelText('engagement path')).toBeInTheDocument();
    // One at a time: the long form's attacker row is gone.
    expect(screen.queryByText(/3 hits · 107 dmg/)).not.toBeInTheDocument();
    // Exactly the two clicked ids were fetched, nothing else.
    const detailCalls = fetchSpy.mock.calls.map((c) => String(c[0]))
      .filter((u) => u.includes('/api/proximity/event/'));
    expect(detailCalls).toEqual(['/api/proximity/event/297937', '/api/proximity/event/297936']);
  });

  it('renders the outcome instruments from the recorded wire', async () => {
    vi.stubGlobal('fetch', vi.fn(fetchFor(new Map([['/api/proximity/leaderboards', board]]))));
    renderPage();
    // The evening in numbers: 1,382 engagements, 136 crossfires, 53.5% escapes.
    await waitFor(() => expect(screen.getByText('1,382')).toBeInTheDocument());
    expect(screen.getByText('53.5%')).toBeInTheDocument();
    // What kills became: the rates arrive as PERCENTAGES on this wire —
    // these assertions are what catches the fraction-pattern bug (2.6%
    // rendered as 260%).
    expect(screen.getByText('2.6% of kills')).toBeInTheDocument();
    expect(screen.getByText('18%')).toBeInTheDocument();
    expect(screen.getByText(/lasted to round end/)).toBeInTheDocument();
    // Headshot rates leader, colour codes stripped.
    expect(screen.getAllByText(/carniee/).length).toBeGreaterThan(0);
    expect(screen.getByText('16.2%')).toBeInTheDocument();
    // Trades: 97 made of 514 opportunities; support uptime recorded.
    expect(screen.getByText('514')).toBeInTheDocument();
    expect(screen.getByText(/21 support uptime|21\.0%/)).toBeInTheDocument();
    // Accuracy leader from the shots-fired capture.
    expect(screen.getByText('48.6%')).toBeInTheDocument();
    // Objective pressure names its own scope vocabulary verbatim.
    expect(screen.getByText(/session-wide metric; map\/round filters are not applied/)).toBeInTheDocument();
  });

  it('treats a 200 with status:error as a failure, not as data', async () => {
    // The endpoint's own answer for an unknown category — recorded live:
    // {"status":"error","detail":"Unknown category: …"} with HTTP 200.
    vi.stubGlobal('fetch', vi.fn(fetchFor(new Map([
      ['/api/proximity/leaderboards', { status: 'error', detail: 'Unknown category: nonsense', entries: [] }],
    ]))));
    renderPage();
    await waitFor(() => expect(screen.getByText(/leaderboard: unavailable/)).toBeInTheDocument());
  });
});
