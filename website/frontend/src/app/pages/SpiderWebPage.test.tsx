import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { SpiderWebPage } from './SpiderWebPage';
import type { SpiderWebSnapshot } from '../lib/types';
import { isClockOwnHud, isClockWithheld } from '../lib/types';
import worldJson from './__fixtures__/api_replay_round_round_id_web.json';
import povJson from './__fixtures__/api_replay_web_pov_form.json';

// The clock is a discriminated union (withheld vs known), which a JSON
// import cannot satisfy at compile time — the check runs at runtime below,
// like the replay page's event union.
const world = worldJson as unknown as SpiderWebSnapshot;
const povForm = povJson as unknown as SpiderWebSnapshot;

describe('the recorded snapshots against the clock union', () => {
  it('world clocks are the known form; the pov enemy clock is withheld with a reason', () => {
    for (const team of Object.keys(world.clock)) {
      const c = world.clock[team];
      expect(isClockWithheld(c)).toBe(false);
      if (!isClockWithheld(c)) {
        for (const k of ['interval_ms', 'offset_ms', 'pass_ratio', 'time_to_next_wave_ms']) {
          expect(c, `${team} clock missing ${k}`).toHaveProperty(k);
        }
      }
    }
    // The pov's OWN clock is the third form: own_hud, with phase but
    // without observation counts (the grade stays in the oracle view).
    const own = povForm.clock.AXIS;
    expect(isClockOwnHud(own)).toBe(true);
    if (isClockOwnHud(own)) {
      expect(Object.keys(own).sort()).toEqual(
        ['interval_ms', 'offset_ms', 'phase_ms', 'reason', 'status', 'time_to_next_wave_ms']);
    }
    const enemy = povForm.clock.ALLIES;
    expect(isClockWithheld(enemy)).toBe(true);
    if (isClockWithheld(enemy)) {
      expect(enemy.reason.length).toBeGreaterThan(0);
      // ⛔ The withheld form must NOT leak the oracle: only status, the
      // public interval and the reason may be present (#807's allowlist).
      expect(Object.keys(enemy).sort()).toEqual(['interval_ms', 'reason', 'status']);
    }
  });

  it('the pov snapshot withholds players on the server, and names them', () => {
    expect(povForm.players.length).toBeLessThan(world.players.length);
    expect(povForm.withheld_by_pov.length).toBe(world.players.length - povForm.players.length);
    const shown = new Set(povForm.players.map((p) => p.guid));
    for (const g of povForm.withheld_by_pov) {
      expect(shown.has(g), `withheld guid ${g} still present`).toBe(false);
    }
  });
});

function stub(byUrl: (url: string) => unknown | undefined) {
  const spy = vi.fn((input: RequestInfo | URL): Promise<Response> => {
    const url = String(input);
    const body = byUrl(url);
    if (body === undefined) return Promise.reject(new Error(`unexpected: ${url}`));
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);
  });
  vi.stubGlobal('fetch', spy);
  return spy;
}

function renderAt(roundId = '11344', search = '') {
  return render(
    <QueryClientProvider client={makeQueryClient()}>
      <MemoryRouter initialEntries={[`/spider-web/round/${roundId}${search}`]}>
        <Routes>
          <Route path="/spider-web/round/:roundId" element={<SpiderWebPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe('SpiderWebPage', () => {
  it('renders the moment, both clocks and the manifest from the recorded wire', async () => {
    const spy = stub((url) => {
      if (url.includes('/api/replay/round/11344/web')) return url.includes('pov=') ? povForm : world;
      if (url.includes('/assets/maps/geometry/')) return { map_name: 'et_brewdog', vertices: [], indexes: [], floor_normal_z: 0.7, bounds: null };
      return undefined;
    });
    renderAt();
    await waitFor(() => expect(screen.getByText(/round #11,?344/)).toBeInTheDocument());
    expect(screen.getByLabelText('reconstructed moment')).toBeInTheDocument();
    // Both clocks in the known form, with the recorded interval and ratio.
    expect(screen.getByText(/axis clock · validated/)).toBeInTheDocument();
    // Recorded: axis waves every 30 s, allies every 25 — not the same number.
    expect(screen.getByText(/wave every 30 s/)).toBeInTheDocument();
    expect(screen.getByText(/wave every 25 s/)).toBeInTheDocument();
    // The manifest's tri-states, recorded: shot_fired enabled.
    expect(screen.getByText(/shot fired: enabled/)).toBeInTheDocument();
    // The world view sends NO pov parameter.
    const urls = spy.mock.calls.map((c) => String(c[0])).filter((u) => u.includes('/web'));
    expect(urls.every((u) => !u.includes('pov='))).toBe(true);
  });

  it('lists the placed players with their track fields, what each player knows, and the accuracy the snapshot cites', async () => {
    stub((url) => {
      if (url.includes('/api/replay/round/11344/web')) return url.includes('pov=') ? povForm : world;
      if (url.includes('/assets/maps/geometry/')) return { map_name: 'et_brewdog', vertices: [], indexes: [], floor_normal_z: 0.7, bounds: null };
      return undefined;
    });
    renderAt();
    await waitFor(() => expect(screen.getByText(/round #11,?344/)).toBeInTheDocument());
    const w = world as { players: { name: string | null; guid: string }[]; information_state: { holders: Record<string, { beliefs: unknown[] }> }; reconstruction_accuracy: { rounds: number } };
    // every placed player is a row, with the track columns the canvas cannot show
    const players = document.querySelector('[data-parity="spider-web.players.table"]') as HTMLElement;
    for (const p of w.players) expect(players.textContent).toContain(p.name ?? p.guid.slice(0, 8));
    expect(screen.getByTitle('two tracks claimed this player at once')).toBeInTheDocument();
    expect(screen.getByTitle(/nearest teammate — not tactical/)).toBeInTheDocument();
    // one row per belief across all holders
    const beliefs = document.querySelector('[data-parity="spider-web.beliefs.table"]') as HTMLElement;
    const expected = Object.values(w.information_state.holders).reduce((n, h) => n + h.beliefs.length, 0);
    expect(expected).toBeGreaterThan(0);
    expect(beliefs.querySelectorAll('[data-row-key]').length || beliefs.textContent!.split('public obituary').length - 1).toBeGreaterThan(0);
    expect(screen.getAllByText(/knows of \d+ enem/).length).toBe(Object.keys(w.information_state.holders).length);
    // the validation the snapshot cites, in its own words
    expect(screen.getByText(new RegExp(`${w.reconstruction_accuracy.rounds} rounds ·`))).toBeInTheDocument();
    expect(screen.getByText(/measured 2026-08-22/)).toBeInTheDocument();
  });

  it('prints intervals as ranges, keeps two decimals of confidence, names a team holder whole, and calls a missing state unavailable', async () => {
    const w = world as unknown as SpiderWebSnapshot;
    const shaped: SpiderWebSnapshot = {
      ...w,
      first_position_ms: null, velocity_max_dt_ms: null,
      capture_policy: { ...w.capture_policy, manifest_version: null, manifest_count: 2 },
      players: w.players.map((p, i) => (i === 0 ? { ...p, speed: null, stance: null } : p)),
      information_state: {
        holders: {
          'team:AXIS': { holder_guid: 'team:AXIS', known_enemy_count: 2, nearest_known_enemy_distance: { min: 0, max: 831.9 }, nearest_heard_activity_distance: null,
            beliefs: [{ kind: 'position_region', source: 'gunfire', subject_guid: null, roster_state: null, t_observed: 5000, confidence: 0.031, counts_as_known: false, capability: null, expiry_basis: null, region: { x: 1, y: 2, z: 300, radius: 500 } }],
            position_claim_max_radius: null, unavailable: {}, notes: [] },
        },
        audible_gunfire_radius: 1330, pov: 'team:AXIS', pov_unavailable: null, unavailable: { comm_events: 'voice macros are not read' },
      },
    };
    const povUnavailable: SpiderWebSnapshot = { ...shaped, information_state: { ...shaped.information_state, holders: {}, pov_unavailable: "no players on team 'ALLIES' in this round" } };
    let serve = shaped;
    stub((url) => {
      if (url.includes('/api/replay/round/11344/web')) return serve;
      if (url.includes('/assets/maps/geometry/')) return { map_name: 'et_brewdog', vertices: [], indexes: [], floor_normal_z: 0.7, bounds: null };
      return undefined;
    });
    const first = renderAt();
    await waitFor(() => expect(screen.getByText(/round #11,?344/)).toBeInTheDocument());
    expect(screen.getByText(/first position unknown \(no tracks\) · velocity window unknown \(no valid manifest\) · 2 manifests \(versions disagree\)/)).toBeInTheDocument();
    expect(screen.getAllByText(/AXIS \(team union\)/).length).toBeGreaterThan(0);
    expect(screen.getByText(/nearest known 0–832/)).toBeInTheDocument();
    expect(screen.getByText('0.03')).toBeInTheDocument();
    expect(screen.getByText(/r 500 at 1, 2, 300/)).toBeInTheDocument();
    expect(screen.getByText(/comm events unavailable for this pov/)).toBeInTheDocument();
    const players = document.querySelector('[data-parity="spider-web.players.table"]') as HTMLElement;
    expect(players.textContent).not.toContain('null');
    first.unmount();
    serve = povUnavailable;
    renderAt();
    await waitFor(() => expect(screen.getByText(/beliefs — no players on team 'ALLIES' in this round: unavailable/)).toBeInTheDocument());
    expect(screen.queryByText(/nothing has been seen, heard or reported yet/)).toBeNull();
  });

  it('a team pov is a SERVER parameter, and the withheld players are named', async () => {
    const spy = stub((url) => {
      if (url.includes('/api/replay/round/11344/web')) return url.includes('pov=team%3AAXIS') || url.includes('pov=team:AXIS') ? povForm : world;
      if (url.includes('/assets/maps/geometry/')) return { map_name: 'et_brewdog', vertices: [], indexes: [], floor_normal_z: 0.7, bounds: null };
      return undefined;
    });
    renderAt();
    await waitFor(() => expect(screen.getByText(/round #11,?344/)).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'axis pov' }));
    await waitFor(() => expect(screen.getByText(/3 players withheld from this point of view/)).toBeInTheDocument());
    // The enemy clock renders the withheld branch, not a quality state.
    expect(screen.getByText(/allies clock · withheld/)).toBeInTheDocument();
    expect(screen.getByText(/oracle truth/)).toBeInTheDocument();
    // And the own team's clock renders as the HUD form.
    expect(screen.getByText(/axis clock · own hud/)).toBeInTheDocument();
    // And the pov really went to the server.
    const povUrls = spy.mock.calls.map((c) => String(c[0])).filter((u) => u.includes('pov='));
    expect(povUrls.length).toBeGreaterThan(0);
  });
});

describe('SpiderWebPage — the scene (SW-2)', () => {
  const geometry = { map_name: 'et_brewdog', vertices: [0, 0, 0, 100, 0, 0, 0, 100, 0, 0, 0, 200, 100, 0, 200, 0, 100, 200], indexes: [0, 1, 2, 3, 4, 5], floor_normal_z: 0.7, bounds: { min: [-1000, -1000, -100], max: [1000, 1000, 400] } };
  const serve = (spyUrls?: string[]) => stub((url) => {
    if (spyUrls) spyUrls.push(url);
    if (url.includes('/api/replay/round/11344/web')) return url.includes('pov=') ? povForm : world;
    if (url.includes('/assets/maps/geometry/')) return geometry;
    return undefined;
  });

  it('draws one dot per placed player, the floors by height band, a scale bar, and no belief under the oracle', async () => {
    serve();
    renderAt();
    await waitFor(() => expect(screen.getByText(/round #11,?344/)).toBeInTheDocument());
    const svg = screen.getByLabelText('reconstructed moment');
    await waitFor(() => expect(svg.querySelectorAll('[data-player]').length).toBe(world.players.length));
    // dead players are hollow rings, alive ones filled discs
    expect(svg.querySelectorAll('[data-player][data-alive="no"]').length).toBe(world.players.filter((p) => !p.alive).length);
    await waitFor(() => expect(svg.querySelectorAll('path').length).toBeGreaterThan(0));
    expect(svg.querySelector('[data-scale-bar="512"]')).toBeTruthy();
    expect(svg.querySelectorAll('[data-belief-subject]').length).toBe(0);
    expect(screen.getByText(/oracle: you see everything that happened/)).toBeInTheDocument();
    expect(screen.getByText(new RegExp(`${world.players.length}/${world.players.length} placed · 0 overlap conflicts`))).toBeInTheDocument();
    // every mark takes its colour from a token, never a literal
    for (const el of svg.querySelectorAll('[fill], [stroke]')) {
      for (const attr of ['fill', 'stroke']) {
        const v = el.getAttribute(attr);
        if (v && v !== 'none' && v !== 'transparent') expect(v).toMatch(/^var\(--color-/);
      }
    }
  });

  it('under a team view names the enemies known but not placed, and states the own-team simplification', async () => {
    // The recording, at 1:00: every contact region this side holds has
    // widened past the 1,000-unit horizon (1,761–4,222 units). Drawing one
    // would claim the whole map; the side still knows three enemies exist.
    serve();
    renderAt('11344', '?pov=team:AXIS');
    await waitFor(() => expect(screen.getByText(/round #11,?344/)).toBeInTheDocument());
    const svg = screen.getByLabelText('reconstructed moment');
    const holder = Object.values(povForm.information_state.holders)[0];
    const horizon = holder.position_claim_max_radius ?? Infinity;
    const subjects = new Set(holder.beliefs.filter((b) => b.subject_guid && b.region).map((b) => b.subject_guid));
    expect(holder.beliefs.some((b) => b.subject_guid && b.region && b.region.radius <= horizon)).toBe(false);
    expect(subjects.size).toBe(3);
    await waitFor(() => expect(screen.getByText(/known but not placed \(region wider than the published horizon\)/)).toBeInTheDocument());
    expect(svg.querySelectorAll('[data-belief-subject]').length).toBe(0);
    // only the pov's own side is placed as dots; the enemy is a region, never a dot
    expect(svg.querySelectorAll('[data-player]').length).toBe(povForm.players.length);
    expect(screen.getByText(/own-team positions are drawn as known — a simplification/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'axis pov' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('draws a region inside the horizon as a dashed disc whose opacity is the confidence', async () => {
    const holder = Object.values(povForm.information_state.holders)[0];
    const fresh = holder.beliefs.findIndex((b) => b.subject_guid && b.region);
    const shaped = {
      ...povForm,
      information_state: {
        ...povForm.information_state,
        holders: { [holder.holder_guid]: { ...holder, beliefs: holder.beliefs.map((b, i) => (i === fresh ? { ...b, region: { ...b.region!, radius: 300 }, confidence: 0.4 } : b)) } },
      },
    };
    stub((url) => {
      if (url.includes('/api/replay/round/11344/web')) return shaped;
      if (url.includes('/assets/maps/geometry/')) return geometry;
      return undefined;
    });
    renderAt('11344', '?pov=team:AXIS');
    await waitFor(() => expect(screen.getByText(/round #11,?344/)).toBeInTheDocument());
    const svg = screen.getByLabelText('reconstructed moment');
    await waitFor(() => expect(svg.querySelectorAll('[data-belief-subject]').length).toBe(1));
    const disc = svg.querySelector('[data-belief-subject]')!;
    expect(disc.getAttribute('data-belief-subject')).toBe(holder.beliefs[fresh].subject_guid);
    expect(disc.getAttribute('stroke-dasharray')).toBe('5 4');
    expect(Number(disc.getAttribute('stroke-opacity'))).toBeCloseTo(0.4, 5);
    // the other two subjects stay known in words
    expect(screen.getByText(/known but not placed/).textContent).not.toContain(holder.beliefs[fresh].subject_guid!.slice(0, 8));
  });

  it('keeps the moment and the view in the URL, and a nudge reloads the next moment', async () => {
    const urls: string[] = [];
    serve(urls);
    renderAt('11344', '?t=30000');
    await waitFor(() => expect(screen.getByText(/round #11,?344/)).toBeInTheDocument());
    expect(urls.some((u) => u.includes('/web?t=30000'))).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: '+1 s' }));
    await waitFor(() => expect(urls.some((u) => u.includes('/web?t=31000'))).toBe(true));
    fireEvent.click(screen.getByRole('button', { name: '−200 ms' }));
    await waitFor(() => expect(urls.some((u) => u.includes('/web?t=30800'))).toBe(true));
    // a moment before the round's start is clamped, never requested as negative
    expect(urls.every((u) => !u.includes('t=-'))).toBe(true);
  });

  it('offers every player as a point of view, remembering names across a switch', async () => {
    const urls: string[] = [];
    serve(urls);
    renderAt();
    await waitFor(() => expect(screen.getByText(/round #11,?344/)).toBeInTheDocument());
    const first = world.players[0];
    const chip = screen.getByRole('button', { name: first.name ?? first.guid.slice(0, 8) });
    fireEvent.click(chip);
    await waitFor(() => expect(urls.some((u) => u.includes(`pov=${first.guid}`))).toBe(true));
    // the pov snapshot withholds three players, but their chips keep the names the world view carried
    for (const g of povForm.withheld_by_pov) {
      const known = world.players.find((p) => p.guid === g);
      expect(screen.getByRole('button', { name: known?.name ?? g.slice(0, 8) })).toBeInTheDocument();
    }
  });

  it('the camera turns on drag and flattens to plan on a click', async () => {
    serve();
    renderAt();
    await waitFor(() => expect(screen.getByText(/round #11,?344/)).toBeInTheDocument());
    const svg = screen.getByLabelText('reconstructed moment');
    await waitFor(() => expect(svg.querySelectorAll('[data-player] circle').length).toBeGreaterThan(0));
    const before = svg.getAttribute('data-camera-yaw');
    fireEvent.pointerDown(svg, { clientX: 100, clientY: 100, pointerId: 1 });
    fireEvent.pointerMove(svg, { clientX: 160, clientY: 100, pointerId: 1 });
    fireEvent.pointerUp(svg, { pointerId: 1 });
    await waitFor(() => expect(svg.getAttribute('data-camera-yaw')).not.toBe(before));
    fireEvent.click(screen.getByRole('button', { name: 'plan' }));
    await waitFor(() => expect(svg.getAttribute('data-camera-pitch')).toBe('0.000'));
    expect(screen.getByRole('button', { name: 'plan' })).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(screen.getByRole('button', { name: 'reset view' }));
    await waitFor(() => expect(svg.getAttribute('data-camera-yaw')).toBe('0.600'));
  });

  it('a map without floors still places the players and says the stage is missing', async () => {
    stub((url) => {
      if (url.includes('/api/replay/round/11344/web')) return world;
      return undefined;
    });
    vi.spyOn(globalThis, 'fetch').mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/assets/maps/geometry/')) return Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({}) } as Response);
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(world) } as Response);
    });
    renderAt();
    await waitFor(() => expect(screen.getByText(/round #11,?344/)).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText(/floor mesh was never exported/)).toBeInTheDocument());
    const svg = screen.getByLabelText('reconstructed moment');
    expect(svg.querySelectorAll('[data-player]').length).toBe(world.players.length);
    expect(svg.querySelectorAll('path').length).toBe(0);
  });
});

