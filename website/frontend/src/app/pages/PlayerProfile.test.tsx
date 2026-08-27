import { render, screen, waitFor } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { PlayerProfilePage } from './PlayerProfile';
import profile from './__fixtures__/api_players_identifier_profile.json';

/** The player page against the RECORDED profile (vid, sections=all). */
function fixtureFetch(input: RequestInfo | URL): Promise<Response> {
  const path = String(input).split('?')[0];
  if (/^\/api\/players\/[^/]+\/profile$/.test(path)) {
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(profile) } as Response);
  }
  return Promise.reject(new Error(`unexpected endpoint: ${path}`));
}

function renderProfile(id: string | null, fetchImpl = fixtureFetch) {
  vi.stubGlobal('fetch', vi.fn(fetchImpl));
  const client = makeQueryClient();
  client.setDefaultOptions({ queries: { retry: false } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[id === null ? '/profile' : `/profile/${id}`]}>
        <Routes>
          <Route path="/profile" element={<PlayerProfilePage />} />
          <Route path="/profile/:id" element={<PlayerProfilePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('PlayerProfilePage', () => {
  it('renders the recorded player: identity, rating and lifetime figures', async () => {
    renderProfile('D8423F90');
    await waitFor(() => expect(screen.getByText('vid')).toBeInTheDocument());
    // ET rating from the recording, three decimals (a rank, not a rounding).
    expect(screen.getByText('0.747')).toBeInTheDocument();
    expect(screen.getByText(/veteran/)).toBeInTheDocument();
    // Lifetime: 1,760 rounds and the 874 — 875 split.
    expect(screen.getAllByText('1,760').length).toBeGreaterThan(0);
    expect(screen.getByText('874 — 875')).toBeInTheDocument();
    // DPM is derived from damage/time, not invented: 3,575,214 / (683785/60).
    expect(screen.getByText('314')).toBeInTheDocument();
  });

  it('weapon rows keep the head-hit wording and the recorded ordering', async () => {
    renderProfile('D8423F90');
    await waitFor(() => expect(screen.getByText('Mp40')).toBeInTheDocument());
    expect(screen.getByText(/head hits, not headshot kills/)).toBeInTheDocument();
    // Recorded Mp40: 8,306 kills, 42.7% accuracy, 9,910 head hits.
    expect(screen.getByText('8,306')).toBeInTheDocument();
    expect(screen.getAllByText('42.7%').length).toBeGreaterThan(0);
  });

  it('a section that is unavailable says so instead of rendering an empty shape', async () => {
    const noMovement = {
      ...(profile as object),
      movement: { available: false, tracks: 0, avg_speed: null, peak_speed: null, sprint_pct: null, avg_distance_per_life: null, stance: null },
    };
    renderProfile('D8423F90', (input) => {
      const path = String(input).split('?')[0];
      if (/^\/api\/players\/[^/]+\/profile$/.test(path)) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(noMovement) } as Response);
      }
      return fixtureFetch(input);
    });
    await waitFor(() => expect(screen.getByText('movement: unavailable')).toBeInTheDocument());
    // …and an AVAILABLE-but-empty section reads differently (no data, not broken).
    expect(screen.queryByText('no movement recorded yet')).toBeNull();
  });

  it('an available but empty section reads as no data', async () => {
    const noMaps = { ...(profile as object), maps: { available: true, maps: [] } };
    renderProfile('D8423F90', (input) => {
      const path = String(input).split('?')[0];
      if (/^\/api\/players\/[^/]+\/profile$/.test(path)) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(noMaps) } as Response);
      }
      return fixtureFetch(input);
    });
    await waitFor(() => expect(screen.getByText('no map history recorded yet')).toBeInTheDocument());
    expect(screen.queryByText('map history: unavailable')).toBeNull();
  });

  it('a round with no attributed winner shows a dash, never a loss', async () => {
    const rows = (profile as { recent_matches: { matches: Record<string, unknown>[] } }).recent_matches.matches;
    const undecided = {
      ...(profile as object),
      recent_matches: { available: true, matches: [{ ...rows[0], round_id: 99999, result: null }] },
    };
    renderProfile('D8423F90', (input) => {
      const path = String(input).split('?')[0];
      if (/^\/api\/players\/[^/]+\/profile$/.test(path)) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(undecided) } as Response);
      }
      return fixtureFetch(input);
    });
    await waitFor(() => expect(screen.getByText(/last rounds/)).toBeInTheDocument());
    const dashes = screen.getAllByText('—');
    expect(dashes.length).toBeGreaterThan(0);
  });

  it('without an id the page asks for one and calls nothing', async () => {
    const spy = vi.fn(fixtureFetch);
    renderProfile(null, spy);
    await waitFor(() => expect(screen.getByText(/Pick a player/)).toBeInTheDocument());
    expect(spy).not.toHaveBeenCalled();
  });

  it('nemeses and victims lead with the figure each list ranks by', async () => {
    renderProfile('D8423F90');
    await waitFor(() => expect(screen.getByText(/the people/)).toBeInTheDocument());
    // The recorded pair tops BOTH lists (.olz kills vid most AND is killed
    // most) — legitimate, since the backend sorts the same pairs two ways.
    // Nemeses must lead with kills ON the player (872), victims with kills
    // BY the player (1096); printing one fixed order made them look alike.
    expect(screen.getByText(/kills ON them/)).toBeInTheDocument();
    expect(screen.getByText(/kills BY them/)).toBeInTheDocument();
    expect(screen.getAllByText('872').length).toBeGreaterThan(0);
    expect(screen.getAllByText('1096').length).toBeGreaterThan(0);
  });

  it('a section that is unavailable carries NO list — the page must not crash', async () => {
    // The real shape of an unavailable/failed section: {available:false,
    // reason} and nothing else (players_profile_router `_ok`). The first
    // version spread `.weapons` before SectionBody ever rendered.
    const stripped = {
      ...(profile as object),
      weapons: { available: false, reason: 'error' },
      relationships: { available: false, reason: 'error' },
      maps: { available: false, reason: 'error' },
      recent_matches: { available: false, reason: 'error' },
      hit_regions: { available: false, reason: 'error' },
      movement: { available: false, reason: 'error' },
    };
    renderProfile('D8423F90', (input) => {
      const path = String(input).split('?')[0];
      if (/^\/api\/players\/[^/]+\/profile$/.test(path)) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(stripped) } as Response);
      }
      return fixtureFetch(input);
    });
    await waitFor(() => expect(screen.getByText('vid')).toBeInTheDocument());
    expect(screen.getByText('weapon stats: unavailable')).toBeInTheDocument();
    expect(screen.getByText('map history: unavailable')).toBeInTheDocument();
    expect(screen.getByText('recent rounds: unavailable')).toBeInTheDocument();
  });

  it('requests only the sections it renders, never the heavy pair', async () => {
    const spy = vi.fn(fixtureFetch);
    renderProfile('D8423F90', spy);
    await waitFor(() => expect(screen.getByText('vid')).toBeInTheDocument());
    const url = String(spy.mock.calls[0][0]);
    // aim (16.9 s cold) and advanced (11.1 s cold) are not on this page.
    expect(url).toContain('sections=');
    expect(url).not.toContain('all');
    expect(url).not.toContain('aim');
    expect(url).not.toContain('advanced');
    expect(url).toContain('weapons');
  });

  it('teammate rows lead with synergy, the metric the list is ordered by', async () => {
    renderProfile('D8423F90');
    await waitFor(() => expect(screen.getByText(/best alongside/)).toBeInTheDocument());
    expect(screen.getByText(/synergy = dpm delta together/)).toBeInTheDocument();
    // Recorded top teammate: synergy 82 over 6 rounds at 66.7% together.
    expect(screen.getAllByText('+82').length).toBeGreaterThan(0);
    expect(screen.getAllByText(/6 rd · 66\.7%/).length).toBeGreaterThan(0);
  });
});
