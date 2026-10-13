import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { useStoryComposite } from './hooks';
import Story from '../pages/Story';

const clients: QueryClient[] = [];
function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  const calls: string[] = [];
  vi.stubGlobal('fetch', vi.fn(async (input: string) => {
    calls.push(input);
    const url = new URL(input, 'http://fixture');
    const gsid = Number(url.searchParams.get('gaming_session_id'));
    if (url.pathname === '/api/skill/composite') {
      if (!gsid) return new Response('{}', { status: 409 });
      return Response.json({ status: `session-${gsid}`, session_date: '2026-10-12', players: [] });
    }
    if (url.pathname.endsWith('/scopes')) return Response.json({ sessions: [71, 72].map((id) => ({
      gaming_session_id: id, start_date: '2026-10-12', end_date: '2026-10-12', accepted_round_count: 2,
    })) });
    // Keep unrelated story panels pending; the real composite hook/client and
    // page selection still execute without a fabricated full storytelling payload.
    return new Promise<Response>(() => {});
  }));
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  return { wrapper, calls };
}
afterEach(() => { cleanup(); clients.splice(0).forEach((c) => c.clear()); vi.unstubAllGlobals(); });

it('uses the canonical ID without a date and isolates two sessions on the same date', async () => {
  const { wrapper, calls } = setup();
  const { result, rerender } = renderHook(({ date, id }) => useStoryComposite(date, id), {
    wrapper, initialProps: { date: null as string | null, id: 71 as number | null },
  });
  await waitFor(() => expect(result.current.data?.status).toBe('session-71'));
  rerender({ date: '2026-10-12', id: 72 });
  await waitFor(() => expect(result.current.data?.status).toBe('session-72'));
  rerender({ date: '2026-10-12', id: 71 });
  await waitFor(() => expect(result.current.data?.status).toBe('session-71'));
  expect(calls).toEqual(['/api/skill/composite?gaming_session_id=71', '/api/skill/composite?gaming_session_id=72']);
});

it('keeps an absent scope disabled and preserves truthful date-only ambiguity', async () => {
  const { wrapper, calls } = setup();
  const { result, rerender } = renderHook(({ date }) => useStoryComposite(date), {
    wrapper, initialProps: { date: null as string | null },
  });
  expect(result.current.fetchStatus).toBe('idle');
  expect(calls).toEqual([]);
  rerender({ date: '2026-10-12' });
  await waitFor(() => expect(result.current.isError).toBe(true));
  expect(calls).toEqual(['/api/skill/composite?session_date=2026-10-12']);
});

it('executes the Story deep link and selector through the actual composite hook/client', async () => {
  const { wrapper, calls } = setup();
  const page = render(<Story params={{ gsid: '71' }} />, { wrapper });
  await waitFor(() => expect(calls).toContain('/api/skill/composite?gaming_session_id=71'));
  await waitFor(() => expect(page.getByRole('combobox').querySelectorAll('option')).toHaveLength(2));
  fireEvent.change(page.getByRole('combobox'), { target: { value: '72' } });
  await waitFor(() => expect(calls).toContain('/api/skill/composite?gaming_session_id=72'));
  expect(calls.filter((url) => url.includes('/skill/composite'))).toEqual([
    '/api/skill/composite?gaming_session_id=71', '/api/skill/composite?gaming_session_id=72',
  ]);
});
