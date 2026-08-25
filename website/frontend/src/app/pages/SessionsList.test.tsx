import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { SessionsList } from './SessionsList';
import sessions from './__fixtures__/api_sessions.json';

function fixtureFetch(input: RequestInfo | URL): Promise<Response> {
  const url = String(input);
  if (url.split('?')[0] === '/api/sessions') {
    return Promise.resolve({ ok: true, json: () => Promise.resolve(sessions) } as Response);
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
});
