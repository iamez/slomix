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

function renderAt(roundId = '11344') {
  return render(
    <QueryClientProvider client={makeQueryClient()}>
      <MemoryRouter initialEntries={[`/spider-web/round/${roundId}`]}>
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
