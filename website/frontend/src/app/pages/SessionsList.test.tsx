import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { SessionsList } from './SessionsList';
import sessions from './__fixtures__/api_sessions.json';
import lineups from './__fixtures__/api_stats_session_gaming_session_id_lineups.json';

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

function renderList(box: boolean) {
  const client = makeQueryClient();
  client.setDefaultOptions({ queries: { retry: false } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <SessionsList box={box} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('SessionsList', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders the archive with recorded rows, linked by session_id', async () => {
    vi.stubGlobal('fetch', vi.fn(fixtureFetch));
    renderList(false);
    await waitFor(() => expect(screen.getByText('7 / 3')).toBeInTheDocument());
    const rows = screen.getAllByRole('link').filter((a) => a.getAttribute('href')?.startsWith('/session-detail/'));
    expect(rows[0].getAttribute('href')).toBe('/session-detail/152');
    // Plain view has no side-wins columns.
    expect(screen.queryByText('allies')).not.toBeInTheDocument();
  });

  it('box view adds the side-wins columns from the recorded fields', async () => {
    vi.stubGlobal('fetch', vi.fn(fixtureFetch));
    renderList(true);
    await waitFor(() => expect(screen.getByText('allies')).toBeInTheDocument());
    expect(screen.getByText('axis')).toBeInTheDocument();
    expect(screen.getByText(/2 points per map won/)).toBeInTheDocument();
  });

  it('says so on a successful empty archive', async () => {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      if (String(input).split('?')[0] === '/api/sessions') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) } as Response);
      }
      return fixtureFetch(input);
    }));
    renderList(false);
    await waitFor(() => expect(screen.getByText(/no sessions recorded yet/)).toBeInTheDocument());
  });

  it('the lineup strip stays lazy until asked, then names both teams', async () => {
    const fetchSpy = vi.fn(fixtureFetch);
    vi.stubGlobal('fetch', fetchSpy);
    const { container } = renderList(true);
    await waitFor(() => expect(screen.getByText('7 / 3')).toBeInTheDocument());
    // Lazy: nothing fetched the lineups yet.
    expect(fetchSpy.mock.calls.map((c) => String(c[0])).some((u) => u.includes('/lineups'))).toBe(false);
    fireEvent.click(screen.getAllByRole('button', { name: /lineup/ })[0]);
    // Recorded session 153: team a and team b tinted by the team tokens.
    await waitFor(() => expect(container.querySelector('[data-parity="sessions2.lineups"]')).toBeTruthy());
    await waitFor(() => expect(screen.getByText(/\.olz \u00b7 Cru3lzor\./)).toBeInTheDocument());
    expect(screen.getByText(/kanii \u00b7 vid/)).toBeInTheDocument();
  });

  it('a mirror joined/left pair folds into one team-switch event', async () => {
    vi.stubGlobal('fetch', vi.fn(fixtureFetch));
    renderList(true);
    await waitFor(() => expect(screen.getByText('7 / 3')).toBeInTheDocument());
    fireEvent.click(screen.getAllByRole('button', { name: /lineup/ })[0]);
    // The recording carries the real mid-evening switch: SuperBoyy joined a
    // while leaving b, .olz the reverse — two events, not four +/- rows.
    await waitFor(() => expect(screen.getByText(/SuperBoyy \u21c4 switched to team a/)).toBeInTheDocument());
    expect(screen.getByText(/\.olz \u21c4 switched to team b/)).toBeInTheDocument();
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
    renderList(true);
    await waitFor(() => expect(screen.getByText('7 / 3')).toBeInTheDocument());
    fireEvent.click(screen.getAllByRole('button', { name: /lineup/ })[0]);
    await waitFor(() => expect(screen.getByText(/no roster capture for this evening/)).toBeInTheDocument());
  });
});
