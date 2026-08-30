import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { Leaderboards } from './Leaderboards';
import { RecordBook } from './RecordBook';
import { Awards } from './Awards';
import leaderboard from './__fixtures__/api_stats_leaderboard.json';
import records from './__fixtures__/api_stats_records.json';
import maps from './__fixtures__/api_stats_maps.json';
import hof from './__fixtures__/api_hall_of_fame.json';
import awards from './__fixtures__/api_awards.json';
import awardsBoard from './__fixtures__/api_awards_leaderboard.json';
import seasonAwards from './__fixtures__/api_seasons_season_id_awards.json';
import seasonCurrent from './__fixtures__/api_seasons_current.json';
import seasonLeaders from './__fixtures__/api_seasons_current_leaders.json';

/** Batch-2 pages against RECORDED responses (docs/design/09 §H4). */
const FIXTURES = new Map<string, unknown>([
  ['/api/stats/leaderboard', leaderboard],
  ['/api/stats/records', records],
  ['/api/stats/maps', maps],
  ['/api/hall-of-fame', hof],
  ['/api/awards', awards],
  ['/api/awards/leaderboard', awardsBoard],
  ['/api/seasons/current/awards', seasonAwards],
  ['/api/seasons/current', seasonCurrent],
  ['/api/seasons/current/leaders', seasonLeaders],
]);

function fixtureFetch(input: RequestInfo | URL): Promise<Response> {
  const pathname = String(input).split('?')[0];
  const body = FIXTURES.get(pathname);
  if (body === undefined) {
    return Promise.reject(new Error(`unexpected endpoint: ${pathname}`));
  }
  return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);
}

function renderPage(el: React.ReactElement, url = '/') {
  const client = makeQueryClient();
  client.setDefaultOptions({ queries: { retry: false } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[url]}>{el}</MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('Leaderboards', () => {
  it('renders the recorded board with legacy defaults and formats per stat', async () => {
    const fetchSpy = vi.fn(fixtureFetch);
    vi.stubGlobal('fetch', fetchSpy);
    renderPage(<Leaderboards />);
    await waitFor(() => expect(screen.getByText('SHIFT+W squAzE__')).toBeInTheDocument());
    // Legacy defaults: stat=games, period=season.
    const call = fetchSpy.mock.calls.map((c) => String(c[0])).find((u) => u.includes('leaderboard'));
    expect(call).toContain('stat=games');
    expect(call).toContain('period=season');
    // Row links carry the guid.
    const row = screen.getByText('SHIFT+W squAzE__').closest('a');
    expect(row?.getAttribute('href')).toBe('/profile/3C0354D3');
    // K/D formats to two decimals from the recording.
    expect(screen.getByText('1.51')).toBeInTheDocument();
  });

  it('switching the stat refetches with the new key', async () => {
    const fetchSpy = vi.fn(fixtureFetch);
    vi.stubGlobal('fetch', fetchSpy);
    renderPage(<Leaderboards />);
    await waitFor(() => expect(screen.getByText('SHIFT+W squAzE__')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'DPM' }));
    await waitFor(() => {
      const calls = fetchSpy.mock.calls.map((c) => String(c[0]));
      expect(calls.some((u) => u.includes('stat=dpm'))).toBe(true);
    });
  });

  it('prints a dash, not a zero, for an unknown kill count', async () => {
    // #830 types LeaderboardRow.kills as nullable: the aggregate can be
    // NULL. Zero kills and an unknown kill count are different facts, and
    // this column is auxiliary — the picked stat is `value`.
    // The endpoint answers a bare ARRAY, not an object with a key.
    const rows = leaderboard as Record<string, unknown>[];
    const withNull = [{ ...rows[0], kills: null }, ...rows.slice(1)];
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL): Promise<Response> => {
      if (String(input).split('?')[0] === '/api/stats/leaderboard') {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(withNull) } as Response);
      }
      return fixtureFetch(input);
    }));
    renderPage(<Leaderboards />);
    await waitFor(() => expect(screen.getAllByText('—').length).toBeGreaterThan(0));
    // …and no invented zero next to it.
    expect(screen.queryByText('0')).toBeNull();
  });
});

describe('RecordBook', () => {
  it('renders record cards in the FE-owned order and expands the top 5', async () => {
    vi.stubGlobal('fetch', vi.fn(fixtureFetch));
    renderPage(<RecordBook />);
    // Recorded single-round kills record.
    await waitFor(() => expect(screen.getByText('bronze.')).toBeInTheDocument());
    // Full-map section renders too.
    expect(screen.getByText(/full map · both rounds combined/)).toBeInTheDocument();
  });

  it('renders nothing rather than breaking when a filter matches no records', async () => {
    // Measured on #830 and re-measured here: /api/stats/records?map_name=
    // goldrush — a real ET map this server never recorded — answers `{}`
    // with HTTP 200 and ALL NINETEEN categories absent. The type used to
    // promise every key was present; the page survived only because it
    // happened to guard with `?.`.
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL): Promise<Response> => {
      if (String(input).split('?')[0] === '/api/stats/records') {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) } as Response);
      }
      return fixtureFetch(input);
    }));
    renderPage(<RecordBook />);
    // The page already answers this correctly — an empty object is truthy,
    // so two headings over empty grids would claim records that do not
    // exist (Codex on #813). What was missing was the TYPE saying the keys
    // can be absent at all; this test pins the behaviour to the measurement
    // rather than to that earlier review alone.
    await waitFor(() => expect(screen.getByText(/no records for this selection yet/)).toBeInTheDocument());
    expect(screen.queryByText('bronze.')).toBeNull();
    expect(screen.queryByText(/click a card for the top 5/)).toBeNull();
  });

  it('?tab=hof lands on the hall of fame (the hash-alias contract)', async () => {
    vi.stubGlobal('fetch', vi.fn(fixtureFetch));
    renderPage(<RecordBook />, '/record-book?tab=hof');
    await waitFor(() => expect(screen.getByText('Most active')).toBeInTheDocument());
    // Recorded top row of most_active.
    expect(screen.getAllByText('.olz').length).toBeGreaterThan(0);
    // Champions band hides on the recorded empty awards — the NORMAL state.
    expect(screen.queryByText(/champions/i)).not.toBeInTheDocument();
  });

  it('season tab shows leaders and says the awards are not engraved yet', async () => {
    vi.stubGlobal('fetch', vi.fn(fixtureFetch));
    renderPage(<RecordBook />, '/record-book?tab=season');
    await waitFor(() => expect(screen.getByText('2026 Fall (Q3)')).toBeInTheDocument());
    expect(screen.getByText(/no engraved season awards yet/)).toBeInTheDocument();
    // damage_given leader from the recording.
    expect(screen.getAllByText('vid').length).toBeGreaterThan(0);
  });
});

describe('Awards', () => {
  it('groups the recorded awards by round and shows the total', async () => {
    vi.stubGlobal('fetch', vi.fn(fixtureFetch));
    renderPage(<Awards />);
    await waitFor(() => expect(screen.getByText('24,859 awards')).toBeInTheDocument());
    // A recorded award with its string value.
    expect(screen.getByText(/highest light weapons accuracy/)).toBeInTheDocument();
    expect(screen.getByText('48.54 percent')).toBeInTheDocument();
  });

  it('by-player tab renders the leaderboard with real top_award values', async () => {
    vi.stubGlobal('fetch', vi.fn(fixtureFetch));
    renderPage(<Awards />);
    fireEvent.click(screen.getByRole('button', { name: 'By player' }));
    await waitFor(() => expect(screen.getByText('4,498')).toBeInTheDocument());
    expect(screen.getAllByText(/longest killing spree/).length).toBeGreaterThan(0);
    // The dropdown carries REAL award names from the leaderboard (the
    // legacy favorite_award bug left it hardcoded-only).
    expect(screen.getByRole('option', { name: 'Longest killing spree' })).toBeInTheDocument();
  });

  it('says so when the selection has no awards', async () => {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const pathname = String(input).split('?')[0];
      if (pathname === '/api/awards') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ awards: [], total: 0, limit: 20, offset: 0 }) } as Response);
      }
      return fixtureFetch(input);
    }));
    renderPage(<Awards />);
    await waitFor(() => expect(screen.getByText(/no awards found for this selection/)).toBeInTheDocument());
  });
});
