import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { Rivalries } from './Rivalries';
import board from './__fixtures__/api_rivalries_leaderboard.json';
import player from './__fixtures__/api_rivalries_player_guid.json';
import h2h from './__fixtures__/api_rivalries_h2h_guid1_guid2.json';

/** Against the recorded responses — the community board, vid's opponents,
 *  and the .olz–vid duel.
 *
 *  Dispatch on the path PREFIX rather than "does the URL contain this":
 *  the previous `includes('/rivalries/player/') ? player : board` sent every
 *  other rivalries path to the board, so the moment /h2h/ existed it was
 *  answered with a leaderboard — plausible data from the wrong endpoint,
 *  which is harder to spot than nonsense (same trap as Story.test.tsx). */
function fixtureFetch(input: RequestInfo | URL): Promise<Response> {
  const path = new URL(String(input), 'http://test.local').pathname;
  const body = path.startsWith('/api/rivalries/player/')
    ? player
    : path.startsWith('/api/rivalries/h2h/')
      ? h2h
      : path === '/api/rivalries/leaderboard'
        ? board
        : undefined;
  if (body === undefined) return Promise.reject(new Error(`unexpected endpoint: ${String(input)}`));
  return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);
}

function renderPage(search = '', fetchImpl = fixtureFetch) {
  vi.stubGlobal('fetch', vi.fn(fetchImpl));
  const client = makeQueryClient();
  client.setDefaultOptions({ queries: { retry: false } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/rivalries${search}`]}>
        <Routes>
          <Route path="/rivalries" element={<Rivalries />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('Rivalries', () => {
  it('prints the rule beside each label, so a classification can be checked', async () => {
    // NEMESIS/PREY/RIVAL are thresholds on one number, not adjectives. A page
    // that shows the label without the rule leaves the reader guessing why
    // their 58% opponent is a rival and their 61% one is not.
    renderPage();
    await waitFor(() => expect(screen.getByText('you win 70%+')).toBeInTheDocument());
    expect(screen.getByText('they win 70%+')).toBeInTheDocument();
    expect(screen.getByText('within 40-60%')).toBeInTheDocument();
    expect(screen.getByText('fewer than 5 meetings')).toBeInTheDocument();
  });

  it('shows the recorded pair with the kills each way', async () => {
    renderPage();
    // .olz vs vid, 872 and 1096 — the top pair in the recording.
    await waitFor(() => expect(screen.getAllByText(/\.olz/).length).toBeGreaterThan(0));
    expect(screen.getByText('872 — 1,096')).toBeInTheDocument();
  });

  it('says a missing role is a result, not a gap', async () => {
    // vid has a rival and prey but no nemesis: nobody kills him 70% of the
    // time. "—" would read as missing data about a measured fact.
    renderPage('?guid=D8423F90');
    await waitFor(() => expect(screen.getByText('nobody wins 70% against them')).toBeInTheDocument());
    expect(screen.getAllByText(/opponents/).length).toBeGreaterThan(0);
  });

  it('separates an untracked id from a player without rivals', async () => {
    const unresolved = { ...player, resolved: false, all_pairs: [], total_opponents: 0, player_name: null };
    renderPage('?guid=AAAAAAAA', (input) => {
      const url = String(input);
      if (url.includes('/rivalries/player/')) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(unresolved) } as Response);
      }
      return fixtureFetch(input);
    });
    await waitFor(() => expect(screen.getByText(/never tracked/)).toBeInTheDocument());
  });

  it('tells two opponents apart when they share a display name', async () => {
    // Measured in the recording: `ownator` appears twice in vid's list —
    // FB0EC840 and EF561EAA, the sick-leave alt from migration 073. Two
    // identical names against different numbers is a page contradicting
    // itself, so the id joins the name exactly where it has to.
    renderPage('?guid=D8423F90');
    await waitFor(() => expect(screen.getAllByText('ownator').length).toBe(2));
    expect(screen.getByText('FB0EC840')).toBeInTheDocument();
    expect(screen.getByText('EF561EAA')).toBeInTheDocument();
    // …and only where it has to: an unambiguous name carries no id.
    expect(screen.queryByText('5D989160')).toBeNull();
  });

  it('links both sides of a pair to their profiles by the short GUID', async () => {
    // The page receives 32-character GUIDs and every profile route in this
    // app takes the 8-character form.
    renderPage();
    await waitFor(() => expect(screen.getAllByRole('link').length).toBeGreaterThan(2));
    const hrefs = screen.getAllByRole('link').map((a) => a.getAttribute('href') ?? '');
    expect(hrefs.some((h) => h === '/profile/5D989160')).toBe(true);
    expect(hrefs.some((h) => h === '/profile/D8423F90')).toBe(true);
    expect(hrefs.every((h) => !/\/profile\/[0-9A-F]{9,}/.test(h))).toBe(true);
  });
  it('opens the duel from the board and puts both ids in the url', async () => {
    // The score is the way in — before this the h2h endpoint existed and
    // nothing on the site could reach it.
    renderPage();
    const pair = (board as { pairs: { name1: string; name2: string; kills_1to2: number; kills_2to1: number }[] }).pairs[0];
    await waitFor(() => expect(screen.getAllByText(pair.name1).length).toBeGreaterThan(0));
    fireEvent.click(screen.getByTitle(`${pair.name1} against ${pair.name2}, kill by kill`));

    await waitFor(() => expect(screen.getByText('head to head')).toBeInTheDocument());
    const d = h2h as { p1_kills: number; p2_kills: number; total: number; classification: string; per_map: { map: string }[] };
    // Grouped, like every other figure on the site — asserting the raw
    // digits would pass only until someone crossed a thousand.
    expect(screen.getByText(d.p1_kills.toLocaleString('en-US'))).toBeInTheDocument();
    expect(screen.getByText(d.p2_kills.toLocaleString('en-US'))).toBeInTheDocument();
    expect(screen.getByText(`${d.total.toLocaleString('en-US')} meetings`)).toBeInTheDocument();
    // Every map they met on, not just the first — the split is the point.
    for (const m of d.per_map) expect(screen.getAllByText(m.map).length).toBeGreaterThan(0);
  });

  it('shows what each one landed it with, both sides', async () => {
    renderPage('?guid=5D9891600C7948FF85709360E669D5A4&vs=D8423F90F045D9D3E2C0550811C5A899');
    await waitFor(() => expect(screen.getByText('head to head')).toBeInTheDocument());
    const d = h2h as { p1_weapons: { weapon: string; kill_mod: number; kills: number }[]; p2_weapons: { weapon: string; kill_mod: number; kills: number }[] };
    // Top five each, because a full list of twelve weapons per side is a
    // table, not a comparison — and the fixture has twelve.
    expect(d.p1_weapons.length).toBeGreaterThan(5);
    // A shared display name is printed with its mod (see the next test), so
    // the label a row carries is the name plus, when it must, the mod.
    const counts = new Map<string, number>();
    for (const w of d.p1_weapons) counts.set(w.weapon, (counts.get(w.weapon) ?? 0) + 1);
    const label = (w: { weapon: string; kill_mod: number }) =>
      (counts.get(w.weapon) ?? 0) > 1 ? `${w.weapon} #${w.kill_mod}` : w.weapon;
    for (const w of d.p1_weapons.slice(0, 5)) expect(screen.getAllByText(label(w)).length).toBeGreaterThan(0);
    expect(screen.queryByText(label(d.p1_weapons[11]))).toBeNull();
  });

  it('disambiguates two weapons that share one name', async () => {
    // Measured in the recording: kill_mod 16 and 18 are BOTH "Grenade"
    // (hand and rifle), on both sides. Two identical labels with different
    // counts is a panel contradicting itself.
    const rows = (h2h as { p1_weapons: { weapon: string; kill_mod: number; kills: number }[] }).p1_weapons;
    const counts = new Map<string, number>();
    for (const w of rows) counts.set(w.weapon, (counts.get(w.weapon) ?? 0) + 1);
    const shared = [...counts].find(([, n]) => n > 1)![0];
    const mods = rows.filter((w) => w.weapon === shared).map((w) => w.kill_mod);

    renderPage('?guid=5D9891600C7948FF85709360E669D5A4&vs=D8423F90F045D9D3E2C0550811C5A899');
    await waitFor(() => expect(screen.getByText('head to head')).toBeInTheDocument());
    // The bare name never appears alone for the shared label…
    expect(screen.queryByText(shared)).toBeNull();
    // …and each of the colliding mods is named.
    for (const mod of mods) {
      expect(screen.getAllByText(`${shared} #${mod}`).length).toBeGreaterThan(0);
    }
    // A name only one weapon carries stays clean.
    const unique = [...counts].find(([, n]) => n === 1)![0];
    expect(screen.getAllByText(unique).length).toBeGreaterThan(0);
  });

  it('says "never tracked" rather than "never met" for an id with no rows', async () => {
    // The endpoint answers 200 with resolved:false and NAMES the side that
    // failed — the one thing the leaderboard cannot express, and the
    // difference between a fact about two players and a fact about an id.
    const unresolved = {
      status: 'ok', resolved: false, unresolved: ['00000000'],
      guid1: '00000000', guid2: 'D8423F90F045D9D3E2C0550811C5A899',
      p1_name: null, p2_name: null, p1_kills: 0, p2_kills: 0, total: 0,
      win_rate: 0.0, classification: null, p1_weapons: [], p2_weapons: [],
    };
    renderPage('?guid=00000000AAAA&vs=D8423F90F045D9D3E2C0550811C5A899', (input: RequestInfo | URL) => {
      const path = new URL(String(input), 'http://test.local').pathname;
      if (path.startsWith('/api/rivalries/h2h/')) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(unresolved) } as Response);
      }
      return fixtureFetch(input);
    });
    await waitFor(() => expect(screen.getByText(/never tracked/)).toBeInTheDocument());
    expect(screen.getByText(/00000000/)).toBeInTheDocument();
    // Not an outage, and not an empty duel either.
    expect(screen.queryByText(/the duel: unavailable/)).toBeNull();
    expect(screen.queryByText('head to head')).toBeInTheDocument();
  });
});
