import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { SessionsList, sortNewestFirst } from './SessionsList';
import type { SessionSummary } from '../lib/types';
import sessionsJson from './__fixtures__/api_sessions.json';
import lineups from './__fixtures__/api_stats_session_gaming_session_id_lineups.json';

const sessions = sessionsJson satisfies SessionSummary[];

function fixtureFetch(input: RequestInfo | URL): Promise<Response> {
  const url = String(input);
  if (url.split('?')[0] === '/api/sessions') {
    return Promise.resolve({ ok: true, json: () => Promise.resolve(sessions) } as Response);
  }
  if (/^\/api\/stats\/session\/\d+\/lineups$/.test(url.split('?')[0])) {
    return Promise.resolve({ ok: true, json: () => Promise.resolve(lineups) } as Response);
  }
  return Promise.reject(new Error(`SessionsList called an unexpected endpoint: ${url}`));
}

function renderList() {
  const client = makeQueryClient();
  client.setDefaultOptions({ queries: { retry: false } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <SessionsList />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('SessionsList', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders the archive newest first with a levelshot, the id, the maps and the BOX, linked by session_id', async () => {
    vi.stubGlobal('fetch', vi.fn(fixtureFetch));
    renderList();
    await waitFor(() => expect(screen.getByText('7 / 3')).toBeInTheDocument());
    const rows = screen.getAllByRole('link').filter((a) => a.getAttribute('href')?.startsWith('/session-detail/'));
    expect(rows[0].getAttribute('href')).toBe('/session-detail/152');
    // The id is on the row — two evenings on one date differ by it.
    expect(screen.getByText('#152')).toBeInTheDocument();
    // The first map's levelshot, resolved through lib/maps, not the generic svg.
    const img = rows[0].querySelector('img');
    expect(img?.getAttribute('src')).toBe('/assets/maps/levelshots/etl_adlernest.png');
    expect(img?.getAttribute('alt')).toMatch(/adlernest levelshot/);
    // The maps of the evening, as labels.
    expect(screen.getAllByText(/etl adlernest · etl sp delivery · supply · te escape2/).length).toBeGreaterThan(0);
    // The BOX legend replaces the old plain/box toggle — there is one view.
    expect(screen.getByText(/2 points per map won/)).toBeInTheDocument();
    expect(screen.queryByText(/box view →/)).toBeNull();
    expect(screen.queryByText(/plain view →/)).toBeNull();
  });

  it('flags an odd round count as a missing half', async () => {
    const odd = [{ ...sessions[0], session_id: 999, date: '2026-09-01', rounds: 9 }, ...sessions.slice(1)];
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      if (String(input).split('?')[0] === '/api/sessions') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(odd) } as Response);
      }
      return fixtureFetch(input);
    }));
    renderList();
    await waitFor(() => expect(screen.getByText('#999')).toBeInTheDocument());
    // The recording already holds two odd evenings (137 and 132); plus ours.
    const oddInFixture = sessions.slice(1).filter((r) => r.rounds % 2 === 1).length;
    // Exact text: the legend line mentions the phrase too, and must not count.
    expect(screen.getAllByText('one half missing').length).toBe(oddInFixture + 1);
  });

  it('sorts by date then id, newest first, whatever order the API used', () => {
    const rows = [
      { ...sessions[0], session_id: 10, date: '2026-08-01' },
      { ...sessions[0], session_id: 12, date: '2026-08-02' },
      { ...sessions[0], session_id: 11, date: '2026-08-02' },
    ];
    expect(sortNewestFirst(rows).map((r) => r.session_id)).toEqual([12, 11, 10]);
  });

  it('says so on a successful empty archive', async () => {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      if (String(input).split('?')[0] === '/api/sessions') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) } as Response);
      }
      return fixtureFetch(input);
    }));
    renderList();
    await waitFor(() => expect(screen.getByText(/no sessions recorded yet/)).toBeInTheDocument());
  });

  it('the lineup strip stays lazy until asked, then names both teams', async () => {
    const fetchSpy = vi.fn(fixtureFetch);
    vi.stubGlobal('fetch', fetchSpy);
    const { container } = renderList();
    await waitFor(() => expect(screen.getByText('7 / 3')).toBeInTheDocument());
    // Lazy: nothing fetched the lineups yet.
    expect(fetchSpy.mock.calls.map((c) => String(c[0])).some((u) => u.includes('/lineups'))).toBe(false);
    fireEvent.click(screen.getAllByRole('button', { name: /lineup/ })[0]);
    // Recorded session 153: team a and team b tinted by the team tokens.
    await waitFor(() => expect(container.querySelector('[data-parity="sessions.lineups"]')).toBeTruthy());
    await waitFor(() => expect(screen.getByText(/\.olz · Cru3lzor\./)).toBeInTheDocument());
    expect(screen.getByText(/kanii · vid/)).toBeInTheDocument();
  });

  it('a mirror joined/left pair folds into one team-switch event', async () => {
    vi.stubGlobal('fetch', vi.fn(fixtureFetch));
    renderList();
    await waitFor(() => expect(screen.getByText('7 / 3')).toBeInTheDocument());
    fireEvent.click(screen.getAllByRole('button', { name: /lineup/ })[0]);
    // The recording carries the real mid-evening switch: SuperBoyy joined a
    // while leaving b, .olz the reverse — two events, not four +/- rows.
    await waitFor(() => expect(screen.getByText(/SuperBoyy ⇄ switched to team a/)).toBeInTheDocument());
    expect(screen.getByText(/\.olz ⇄ switched to team b/)).toBeInTheDocument();
    expect(screen.queryByText(/^\+ SuperBoyy/)).toBeNull();
  });

  it('an unmeasured evening says so instead of claiming stability', async () => {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL): Promise<Response> => {
      const path = String(input).split('?')[0];
      if (/\/lineups$/.test(path)) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({
          gaming_session_id: 152, teams: [], changes: [], rounds_without_roster: 14,
        }) } as Response);
      }
      return fixtureFetch(input);
    }));
    renderList();
    await waitFor(() => expect(screen.getByText('7 / 3')).toBeInTheDocument());
    fireEvent.click(screen.getAllByRole('button', { name: /lineup/ })[0]);
    await waitFor(() => expect(screen.getByText(/no roster capture for this evening/)).toBeInTheDocument());
  });
});
