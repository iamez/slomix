import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { PlayerSearch } from './PlayerSearch';

function Where() { const { pathname } = useLocation(); return <div data-testid="where">{pathname}</div>; }

function renderSearch(compact = false) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route path="*" element={<><PlayerSearch ariaLabel="Find a player" placeholder="find a player" compact={compact} /><Where /></>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const HITS = [{ guid: 'E587CA5F', name: 'owner' }, { guid: '9F2B3930', name: 'jakazc' }];

afterEach(() => { vi.restoreAllMocks(); });

describe('PlayerSearch', () => {
  it('asks the server only after two characters and a 300 ms pause, then links each hit to its profile', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify(HITS), { status: 200, headers: { 'content-type': 'application/json' } }));
    renderSearch();
    const input = screen.getByLabelText('Find a player');
    fireEvent.change(input, { target: { value: 'o' } });
    await act(async () => { await new Promise((r) => setTimeout(r, 350)); });
    expect(fetchSpy).not.toHaveBeenCalled();
    fireEvent.change(input, { target: { value: 'ow' } });
    await waitFor(() => expect(screen.getByRole('option', { name: 'owner' })).toHaveAttribute('href', '/profile/E587CA5F'));
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(String(fetchSpy.mock.calls[0][0])).toContain('q=ow');
  });

  it('in the header, Enter takes the first hit and clears the box', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify(HITS), { status: 200, headers: { 'content-type': 'application/json' } }));
    renderSearch(true);
    const input = screen.getByLabelText('Find a player') as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'ja' } });
    await waitFor(() => expect(screen.getByRole('option', { name: 'owner' })).toBeInTheDocument());
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(screen.getByTestId('where').textContent).toBe('/profile/E587CA5F');
    expect(input.value).toBe('');
    expect(screen.queryByRole('listbox')).toBeNull();
  });

  it('says when nothing matches', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('[]', { status: 200, headers: { 'content-type': 'application/json' } }));
    renderSearch();
    fireEvent.change(screen.getByLabelText('Find a player'), { target: { value: 'zz' } });
    await waitFor(() => expect(screen.getByText(/no player matches "zz"/)).toBeInTheDocument());
  });
});
