import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { MapsPage } from './MapsPage';
import { WeaponsPage } from './WeaponsPage';
import { FormPage } from './FormPage';
import { RetroViz } from './RetroViz';
import maps from './__fixtures__/api_stats_maps.json';
import segments from './__fixtures__/api_records_maps_segments.json';
import weapons from './__fixtures__/api_stats_weapons.json';
import weaponsHof from './__fixtures__/api_stats_weapons_hall_of_fame.json';
import weaponsByPlayer from './__fixtures__/api_stats_weapons_by_player.json';
import movers from './__fixtures__/api_skill_movers.json';
import recentRounds from './__fixtures__/api_rounds_recent.json';
import roundViz from './__fixtures__/api_rounds_round_id_viz.json';

/** Batch-3 pages against RECORDED responses (docs/design/09 §H4). */
const FIXTURES = new Map<string, unknown>([
  ['/api/stats/maps', maps],
  ['/api/records/maps/segments', segments],
  ['/api/stats/weapons', weapons],
  ['/api/stats/weapons/hall-of-fame', weaponsHof],
  ['/api/stats/weapons/by_player', weaponsByPlayer],
  ['/api/skill/movers', movers],
  ['/api/rounds/recent', recentRounds],
]);

function fixtureFetch(input: RequestInfo | URL): Promise<Response> {
  const pathname = String(input).split('?')[0];
  if (/^\/api\/rounds\/\d+\/viz$/.test(pathname)) {
    return Promise.resolve({ ok: true, json: () => Promise.resolve(roundViz) } as Response);
  }
  const body = FIXTURES.get(pathname);
  if (body === undefined) {
    return Promise.reject(new Error(`unexpected endpoint: ${pathname}`));
  }
  return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);
}

/** fixtureFetch with per-path replacements for shape-variant tests. */
function overrideFetch(overrides: Record<string, unknown>) {
  const table = new Map(Object.entries(overrides));
  return (input: RequestInfo | URL): Promise<Response> => {
    const pathname = String(input).split('?')[0];
    if (table.has(pathname)) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(table.get(pathname)) } as Response);
    }
    return fixtureFetch(input);
  };
}

function renderPage(el: React.ReactElement) {
  const client = makeQueryClient();
  client.setDefaultOptions({ queries: { retry: false } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{el}</MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('MapsPage', () => {
  it('renders summary, objective records and the sorted grid from recorded data', async () => {
    vi.stubGlobal('fetch', vi.fn(fixtureFetch));
    renderPage(<MapsPage />);
    // Recorded top by matches_played: te_escape2 (287) — label is prettified.
    await waitFor(() => expect(screen.getAllByText('te escape2').length).toBeGreaterThan(0));
    expect(screen.getAllByText('287 matches').length).toBeGreaterThan(0);
    // Objective record row from the recording (server's winner_side word).
    expect((await screen.findAllByText('3:25')).length).toBeGreaterThan(0);
    // Win-rate renders the recorded split, not an invented 50/50.
    expect(screen.getByText(/allies 72\.5%/)).toBeInTheDocument();
  });

  it('re-sorts client-side without refetching', async () => {
    const fetchSpy = vi.fn(fixtureFetch);
    vi.stubGlobal('fetch', fetchSpy);
    renderPage(<MapsPage />);
    await waitFor(() => expect(screen.getAllByText('te escape2').length).toBeGreaterThan(0));
    const calls = fetchSpy.mock.calls.length;
    fireEvent.click(screen.getByRole('button', { name: 'Nade spam' }));
    expect(fetchSpy.mock.calls.length).toBe(calls);
  });

  it('an undecided map shows no win bar even though the endpoint says 50/50', async () => {
    // records_maps serializes BOTH rates as 50 for a map no side ever won —
    // the win counts are the only honest detector.
    const undecided = {
      ...(maps as Record<string, unknown>[])[0],
      name: 'sw_nowins', matches_played: 1, allies_wins: 0, axis_wins: 0,
      allies_win_rate: 50, axis_win_rate: 50,
    };
    vi.stubGlobal('fetch', vi.fn(overrideFetch({ '/api/stats/maps': [...(maps as unknown[]), undecided] })));
    renderPage(<MapsPage />);
    await waitFor(() => expect(screen.getAllByText('sw nowins').length).toBeGreaterThan(0));
    expect(screen.getByText(/no decided maps yet/)).toBeInTheDocument();
  });

  it('unknown durations and null dates neither win Fastest nor crash Last played', async () => {
    const real = (maps as Record<string, unknown>[])[0]; // te_escape2, avg 330
    const hollow = {
      ...real, name: 'sw_notime', matches_played: 1,
      avg_duration: 0, last_played: null,
    };
    vi.stubGlobal('fetch', vi.fn(overrideFetch({ '/api/stats/maps': [real, hollow] })));
    renderPage(<MapsPage />);
    await waitFor(() => expect(screen.getAllByText('sw notime').length).toBeGreaterThan(0));
    // The 0-sentinel is UNKNOWN — it must not outrank the measured 330s.
    const fastestCard = screen.getByText('fastest avg').parentElement;
    expect(fastestCard?.textContent).toContain('te escape2');
    // Null last_played renders a dash and the sort survives it.
    fireEvent.click(screen.getByRole('button', { name: 'Last played' }));
    expect(screen.getAllByText('sw notime').length).toBeGreaterThan(0);
    expect(screen.getAllByText('—').length).toBeGreaterThan(0);
  });

  it('a 200 with status:"error" from segments reads as an outage, not an empty record book', async () => {
    vi.stubGlobal('fetch', vi.fn(overrideFetch({ '/api/records/maps/segments': { status: 'error', records: [] } })));
    renderPage(<MapsPage />);
    await waitFor(() => expect(screen.getByText('objective records: unavailable')).toBeInTheDocument());
    expect(screen.queryByText(/no objective records yet/)).toBeNull();
  });
});

describe('WeaponsPage', () => {
  it('renders hof, grid with GLOBAL share, and mastery with honest labels', async () => {
    vi.stubGlobal('fetch', vi.fn(fixtureFetch));
    renderPage(<WeaponsPage />);
    await waitFor(() => expect(screen.getAllByText('Mp40').length).toBeGreaterThan(0));
    // 'head hits' label is load-bearing (hit locations exceed kills).
    expect(screen.getAllByText(/head hits/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/head-hit/).length).toBeGreaterThan(0);
    // Mastery counts are ABSOLUTE — vid's recorded Mp40 16,148 kills must
    // never render as '16,148k'.
    expect(screen.getByText('16,148')).toBeInTheDocument();
    expect(screen.queryByText('16,148k')).toBeNull();
    // Category filter narrows client-side; the share text stays global.
    fireEvent.click(screen.getByRole('button', { name: 'smg' }));
    // The grid heading counts the filtered rows (smg = mp40/thompson/sten);
    // the mastery panel below keeps every weapon — the filter is the
    // grid's, exactly like legacy.
    expect(screen.getByText(/^3 weapons/)).toBeInTheDocument();
  });

  it('all eight categories have buttons (legacy UI offered five)', () => {
    vi.stubGlobal('fetch', vi.fn(fixtureFetch));
    renderPage(<WeaponsPage />);
    for (const c of ['smg', 'rifle', 'heavy', 'pistol', 'melee', 'explosive', 'support', 'other']) {
      expect(screen.getByRole('button', { name: c })).toBeInTheDocument();
    }
  });

  it('airstrike and artillery are Support, so the filter is not empty', async () => {
    vi.stubGlobal('fetch', vi.fn(fixtureFetch));
    renderPage(<WeaponsPage />);
    await waitFor(() => expect(screen.getAllByText('Mp40').length).toBeGreaterThan(0));
    fireEvent.click(screen.getByRole('button', { name: 'support' }));
    // Recorded corpus: exactly Airstrike + Artillery carry the fieldops calls.
    expect(screen.getByText(/^2 weapons/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'explosive' }));
    // Grenade, Grenadelauncher, Landmine, Dynamite — the calls left with Support.
    expect(screen.getByText(/^4 weapons/)).toBeInTheDocument();
  });

  it('a smoke grenade is Support even though its key contains "grenade"', async () => {
    const w = weapons as Record<string, unknown>[];
    const smoke = { ...w[0], name: 'Smokegrenade', weapon_key: 'smokegrenade', kills: 3 };
    vi.stubGlobal('fetch', vi.fn(overrideFetch({ '/api/stats/weapons': [...w, smoke] })));
    renderPage(<WeaponsPage />);
    await waitFor(() => expect(screen.getAllByText('Mp40').length).toBeGreaterThan(0));
    fireEvent.click(screen.getByRole('button', { name: 'support' }));
    expect(screen.getByText(/^3 weapons/)).toBeInTheDocument();
    expect(screen.getAllByText('Smokegrenade').length).toBeGreaterThan(0);
    // …and explosive did NOT absorb it.
    fireEvent.click(screen.getByRole('button', { name: 'explosive' }));
    expect(screen.getByText(/^4 weapons/)).toBeInTheDocument();
  });
});

describe('FormPage', () => {
  it('renders the three sections with sparklines and the rank-vs-self note', async () => {
    vi.stubGlobal('fetch', vi.fn(fixtureFetch));
    renderPage(<FormPage />);
    await waitFor(() => expect(screen.getByText('#smetarski.proner')).toBeInTheDocument());
    expect(screen.getByText(/heating up · above own average/)).toBeInTheDocument();
    expect(screen.getByText(/▲ \+36\.4%/)).toBeInTheDocument();
    // First-night section from the recording (JaKaZc is_new).
    expect(screen.getByText('JaKaZc')).toBeInTheDocument();
    expect(screen.getByText(/rank-vs-self, not a ranking/)).toBeInTheDocument();
    // A newcomer's null composite omits the comparison — never '—% vs 100%'.
    expect(screen.queryByText(/—% vs 100%/)).toBeNull();
  });

  it('switching metric refetches with the metric key', async () => {
    const fetchSpy = vi.fn(fixtureFetch);
    vi.stubGlobal('fetch', fetchSpy);
    renderPage(<FormPage />);
    await waitFor(() => expect(screen.getByText('#smetarski.proner')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'Accuracy' }));
    await waitFor(() => {
      expect(fetchSpy.mock.calls.map((c) => String(c[0])).some((u) => u.includes('metric=acc'))).toBe(true);
    });
  });

  it('the Overall tab renders each mover\'s breakdown contributions', async () => {
    vi.stubGlobal('fetch', vi.fn(fixtureFetch));
    renderPage(<FormPage />);
    await waitFor(() => expect(screen.getByText('#smetarski.proner')).toBeInTheDocument());
    // Recorded breakdown[0] of the top mover: dpm +14.5%.
    expect(screen.getAllByText(/damage \/ min \+14\.5%/).length).toBeGreaterThan(0);
  });

  it('a sick-leave alternate never reads as a first-night player', async () => {
    const m = movers as { new_players: Record<string, unknown>[] };
    const alt = {
      ...m.new_players[0], guid: 'ALT00001', name: 'ownator',
      sick_leave: { primary_name: 'carniee', active: true },
    };
    vi.stubGlobal('fetch', vi.fn(overrideFetch({
      '/api/skill/movers': { ...(movers as object), new_players: [...m.new_players, alt] },
    })));
    renderPage(<FormPage />);
    await waitFor(() => expect(screen.getByText(/ownator · alt of carniee/)).toBeInTheDocument());
    expect(screen.getByText('on sick leave')).toBeInTheDocument();
    // The genuine newcomer still gets the label — exactly once.
    expect(screen.getAllByText('first night').length).toBeGreaterThan(0);
  });

  it('a missing baseline on a metric tab renders only the latest value', async () => {
    const m = movers as { movers_up: Record<string, unknown>[] };
    const fresh = { ...m.movers_up[0], guid: 'NEW00001', name: 'freshEye', latest: 400, baseline: null, delta_pct: null };
    vi.stubGlobal('fetch', vi.fn(overrideFetch({
      '/api/skill/movers': { ...(movers as object), movers_up: [...m.movers_up, fresh] },
    })));
    renderPage(<FormPage />);
    await waitFor(() => expect(screen.getByText('freshEye')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'Accuracy' }));
    await waitFor(() => expect(screen.getByText('freshEye')).toBeInTheDocument());
    // The legacy view omitted the comparison — never "400 vs null".
    expect(screen.queryByText(/vs null/)).toBeNull();
    expect(screen.getByText('400')).toBeInTheDocument();
  });
});

describe('RetroViz', () => {
  it('filters R0, autoloads the newest round and renders the six panels', async () => {
    vi.stubGlobal('fetch', vi.fn(fixtureFetch));
    renderPage(<RetroViz />);
    // Picker options come from the recording; none may be a Match Summary.
    await waitFor(() => expect(screen.getAllByRole('option').length).toBeGreaterThan(0));
    for (const opt of screen.getAllByRole('option')) {
      expect(opt.textContent).not.toMatch(/match summary/i);
    }
    // Recorded round 11277: supply R1, winner_team 2 = Allies.
    await waitFor(() => expect(screen.getByText('Allies')).toBeInTheDocument());
    expect(screen.getByText('11:54')).toBeInTheDocument();
    // Damage table sorted by damage_given — vid (4116) present.
    expect(screen.getByText('4,116')).toBeInTheDocument();
    // Highlight cards from the recorded keyed object (mvp/most_kills/most_damage).
    expect(screen.getByText('mvp')).toBeInTheDocument();
    expect(screen.getByText('354.3 dpm')).toBeInTheDocument();
    expect(screen.getByText('26 kills')).toBeInTheDocument();
  });

  it('a round with the 0-sentinel duration says unknown, not 0:00', async () => {
    // test_round_duration_truth defines zero as MISSING, not a measurement.
    const noDuration = { ...(roundViz as object), duration_seconds: 0 };
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL): Promise<Response> => {
      if (/^\/api\/rounds\/\d+\/viz$/.test(String(input).split('?')[0])) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(noDuration) } as Response);
      }
      return fixtureFetch(input);
    }));
    renderPage(<RetroViz />);
    await waitFor(() => expect(screen.getByText('unknown')).toBeInTheDocument());
    expect(screen.queryByText('0:00')).toBeNull();
  });
});
