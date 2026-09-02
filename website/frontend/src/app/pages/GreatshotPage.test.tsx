import { render, screen, waitFor } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { GreatshotPage, GreatshotDemoPage } from './GreatshotPage';
import type { GreatshotDetail, GreatshotList, GreatshotStatus } from '../lib/types';
import listJson from './__fixtures__/api_greatshot.json';
import detailJson from './__fixtures__/api_greatshot_demo_id.json';
import statusJson from './__fixtures__/api_greatshot_demo_id_status.json';

// Recorded from a REAL demo uploaded and analyzed on this branch —
// 9 highlights on etl_adlernest, the scanner's genuine output.
const list = listJson satisfies GreatshotList;
const detail = detailJson satisfies GreatshotDetail;
const gsStatus = statusJson satisfies GreatshotStatus;
void gsStatus;

function stub(anonymous: boolean) {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL): Promise<Response> => {
    const pathname = String(input).split('?')[0];
    if (anonymous) {
      return Promise.resolve({ ok: false, status: 401, json: () => Promise.resolve({ detail: 'Not authenticated' }) } as Response);
    }
    const body = pathname === '/api/greatshot' ? list
      : pathname.startsWith('/api/greatshot/') ? detail
      : undefined;
    if (body === undefined) return Promise.reject(new Error(`unexpected: ${pathname}`));
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);
  }));
}

afterEach(() => vi.unstubAllGlobals());

describe('GreatshotPage', () => {
  it('anonymous is a sign-in state, not a failure', async () => {
    stub(true);
    render(
      <QueryClientProvider client={makeQueryClient()}>
        <MemoryRouter initialEntries={['/greatshot']}><GreatshotPage /></MemoryRouter>
      </QueryClientProvider>,
    );
    await waitFor(() => expect(screen.getByText(/sign in with CONNECT ID — greatshot analyses YOUR demos/)).toBeInTheDocument());
    expect(screen.queryByText(/demos: unavailable/)).not.toBeInTheDocument();
  });

  it('renders the recorded analysis list', async () => {
    stub(false);
    render(
      <QueryClientProvider client={makeQueryClient()}>
        <MemoryRouter initialEntries={['/greatshot']}><GreatshotPage /></MemoryRouter>
      </QueryClientProvider>,
    );
    // The map name appears in the link AND in the filename Meta — getAll.
    await waitFor(() => expect(screen.getAllByText(/adlernest/i).length).toBeGreaterThan(0));
    expect(screen.getByText(/analyzed · 9 highlights/)).toBeInTheDocument();
  });

  it('the detail renders the scanner’s nine recorded highlights with clip links', async () => {
    stub(false);
    render(
      <QueryClientProvider client={makeQueryClient()}>
        <MemoryRouter initialEntries={[`/greatshot/demo/${detail.id}`]}>
          <Routes><Route path="/greatshot/demo/:demoId" element={<GreatshotDemoPage />} /></Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await waitFor(() => expect(screen.getByText('9 found')).toBeInTheDocument());
    // No render job ever ran on this recording, so clip_download is null on
    // all nine — the recorded truth is ZERO clip links, asserted as such.
    const clips = screen.queryAllByText('clip →');
    expect(clips.length).toBe(detail.highlights.filter((h) => h.clip_download != null).length);
    expect(screen.getByText('report.json →').closest('a')).toHaveAttribute('href', detail.downloads.json);
  });
});
