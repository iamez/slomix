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

// ---------------------------------------------------------------------------
// phase 7 — the four section hubs
//
// The route has carried `:section?` since phase 6 and the page ignored it:
// /greatshot/clips and /greatshot/renders were reachable URLs rendering the
// demo list. Legacy has four panels (index.html:3450-3540, greatshot.js:77-95).

const TWO_DEMOS = {
  items: [
    { ...list.items[0], id: 'a', filename: 'analysed.dm_84',
      highlight_count: 3, render_job_count: 2, rendered_count: 1 },
    { ...list.items[0], id: 'b', filename: 'untouched.dm_84',
      highlight_count: 0, render_job_count: 0, rendered_count: 0 },
    // ⛔ THE DISCRIMINATOR. Without a demo that has highlights but NO render
    // jobs, the renders hub could filter on `highlight_count` and every test
    // still pass — 'a' has both, so either field includes it. Mutating the
    // renders filter survived until this row existed.
    { ...list.items[0], id: 'c', filename: 'clipped-not-rendered.dm_84',
      highlight_count: 5, render_job_count: 0, rendered_count: 0 },
  ],
} satisfies GreatshotList;

function stubList(body: GreatshotList) {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL): Promise<Response> => {
    const pathname = String(input).split('?')[0];
    if (pathname !== '/api/greatshot') return Promise.reject(new Error(`unexpected: ${pathname}`));
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);
  }));
}

function renderAt(path: string) {
  return render(
    <QueryClientProvider client={makeQueryClient()}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/greatshot/:section?" element={<GreatshotPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('GreatshotPage sections', () => {
  it('clips: only demos with clip windows, counted, and a way in', async () => {
    stubList(TWO_DEMOS);
    renderAt('/greatshot/clips');
    expect(await screen.findByText(/3 clip windows/)).toBeInTheDocument();
    expect(screen.getByText('analysed.dm_84')).toBeInTheDocument();
    // A demo with nothing to clip is not a row — legacy filters on
    // highlight_count > 0 (greatshot.js:164) and so does this.
    expect(screen.queryByText('untouched.dm_84')).not.toBeInTheDocument();
    // …but a demo with clip windows and no render job IS a clip candidate.
    expect(screen.getByText('clipped-not-rendered.dm_84')).toBeInTheDocument();
  });

  it('renders: counts render JOBS, not highlights', async () => {
    stubList(TWO_DEMOS);
    renderAt('/greatshot/renders');
    expect(await screen.findByText(/1 rendered · 2 jobs/)).toBeInTheDocument();
    // A demo with five clip windows and no queued render is not a render job.
    expect(screen.queryByText('clipped-not-rendered.dm_84')).not.toBeInTheDocument();
  });

  it('⛔ the upload form belongs to the demos panel only', async () => {
    // Legacy keeps it inside `data-greatshot-panel="demos"`. Without this the
    // hub tests above would still pass while the page offered an upload on
    // every tab — a difference nobody would notice until parity review.
    stubList(TWO_DEMOS);
    const { container } = renderAt('/greatshot/clips');
    await screen.findByText(/3 clip windows/);
    const upload = container.querySelector('[data-parity="greatshot.upload"]');
    expect(upload).not.toBeNull();
    expect(upload).toHaveAttribute('hidden');
  });

  it('⛔ the control: an unknown section falls back to demos, it does not blank', async () => {
    // greatshot.js:77-80 normalises anything outside the four names to
    // 'demos'. A page that rendered nothing for /greatshot/nonsense would be a
    // dead URL, and every hub test above would still be green.
    stubList(TWO_DEMOS);
    const { container } = renderAt('/greatshot/nonsense');
    // ⚠️ A substring match, not an exact one: in the demo LIST the filename
    // shares its element with the duration and the mod, so an exact match
    // finds nothing. In the hubs it is a node of its own — which is why the
    // clips test above can be exact and this one cannot.
    await screen.findByText(/untouched\.dm_84/);
    const listPanel = container.querySelector('[data-parity="greatshot.list"]');
    expect(listPanel).not.toHaveAttribute('hidden');
    expect(screen.queryByText(/clip windows/)).not.toBeInTheDocument();
  });
});
