import { render, screen, waitFor } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { LivePage } from './LivePage';
import type {
  ActivityHistory, ApiHealth, LiveFeed, LiveState, MonitoringStatus, VoiceHistory,
} from '../lib/types';
import stateJson from './__fixtures__/api_live_state_quiet_form.json';
import feedJson from './__fixtures__/api_live_feed.json';
import serverJson from './__fixtures__/api_server_activity_history.json';
import voiceJson from './__fixtures__/api_voice_activity_history.json';
import monitoringJson from './__fixtures__/api_monitoring_status.json';
import statusJson from './__fixtures__/api_status.json';

const liveState = stateJson satisfies LiveState;
const feed = feedJson satisfies LiveFeed;
const serverHist = serverJson satisfies ActivityHistory;
const voiceHist = voiceJson satisfies VoiceHistory;
const monitoring = monitoringJson satisfies MonitoringStatus;
const health = statusJson satisfies ApiHealth;

function stub() {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL): Promise<Response> => {
    const pathname = String(input).split('?')[0];
    const body = {
      '/api/live/state': liveState,
      '/api/live/feed': feed,
      '/api/server-activity/history': serverHist,
      '/api/voice-activity/history': voiceHist,
      '/api/monitoring/status': monitoring,
      '/api/status': health,
    }[pathname];
    if (body === undefined) return Promise.reject(new Error(`unexpected: ${pathname}`));
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);
  }));
}

afterEach(() => vi.unstubAllGlobals());

// The recorded quiet feed carries last_seq 0, which can never exercise the
// cursor — a fixture cannot fail on a value it lacks — so the advance is
// pinned with a synthetic two-event page (contract: seq > since).
it('the feed cursor advances to last_seq and the next poll asks from there', async () => {
  const urls: string[] = [];
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL): Promise<Response> => {
    const url = String(input);
    const pathname = url.split('?')[0];
    if (pathname === '/api/live/feed') {
      urls.push(url);
      const since = Number(new URL(url, 'http://x').searchParams.get('since'));
      const events = since === 0
        ? [{ seq: 5, type: 'ROUND_START' }, { seq: 6, type: 'PLAYER_JOIN' }]
        : [];
      const body: LiveFeed = { status: 'ok', events, oldest_seq: 5, last_seq: 6, server_time: 0 };
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);
    }
    const body = {
      '/api/live/state': liveState,
      '/api/server-activity/history': serverHist,
      '/api/voice-activity/history': voiceHist,
      '/api/monitoring/status': monitoring,
      '/api/status': health,
    }[pathname];
    if (body === undefined) return Promise.reject(new Error(`unexpected: ${pathname}`));
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);
  }));
  render(
    <QueryClientProvider client={makeQueryClient()}>
      <MemoryRouter><LivePage /></MemoryRouter>
    </QueryClientProvider>,
  );
  await waitFor(() => expect(screen.getByText(/round start/)).toBeInTheDocument());
  // Advancing since changes the query key, so React Query fetches again at once.
  await waitFor(() => expect(urls.some((u) => u.includes('since=6'))).toBe(true));
  // The two accumulated events stay rendered even though the since=6 page is empty.
  expect(screen.getByText(/player join/)).toBeInTheDocument();
});

describe('LivePage', () => {
  it('renders the recorded quiet server honestly, with fresh monitoring and real history', async () => {
    stub();
    render(
      <QueryClientProvider client={makeQueryClient()}>
        <MemoryRouter initialEntries={['/live']}>
          <LivePage />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    // The recording is a QUIET server: the page says so, not a spinner.
    // 'nobody on' renders BEFORE data via optional chaining — wait for the
    // data-carrying line, then assert the heading.
    await waitFor(() => expect(screen.getByText(/wakes the moment the first player connects/)).toBeInTheDocument());
    expect(screen.getByText('nobody on')).toBeInTheDocument();
    expect(screen.getByText(/quiet — no renderable events/)).toBeInTheDocument();
    // 24h history: the recorded peak and uptime in the aside.
    await waitFor(() => expect(screen.getByText(new RegExp(`peak ${serverHist.summary.peak_players} · uptime`))).toBeInTheDocument());
    expect(screen.getByLabelText('players over 24h')).toBeInTheDocument();
    expect(screen.getByLabelText('voice members over 24h')).toBeInTheDocument();
    // Monitoring: both recorded samplers fresh, said plainly.
    expect(screen.getByText(/server sampling fresh/)).toBeInTheDocument();
    expect(screen.getByText(/voice sampling fresh/)).toBeInTheDocument();
    // The recorded health says 'online', not 'ok' — assert the recording.
    expect(screen.getByText(new RegExp(`api ${health.status} · database ${health.database}`))).toBeInTheDocument();
  });

  it('a STALE sampler is a warning, not a quiet line', async () => {
    stub();
    const staleMon: MonitoringStatus = {
      ...monitoring,
      voice: { ...monitoring.voice, is_stale: true, age_seconds: 5400 },
    };
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL): Promise<Response> => {
      const pathname = String(input).split('?')[0];
      const body = pathname === '/api/monitoring/status' ? staleMon : {
        '/api/live/state': liveState, '/api/live/feed': feed,
        '/api/server-activity/history': serverHist,
        '/api/voice-activity/history': voiceHist, '/api/status': health,
      }[pathname];
      if (body === undefined) return Promise.reject(new Error(`unexpected: ${pathname}`));
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);
    }));
    render(
      <QueryClientProvider client={makeQueryClient()}>
        <MemoryRouter initialEntries={['/live']}>
          <LivePage />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await waitFor(() => expect(screen.getByText(/voice sampling is STALE — last record 90 min ago/)).toBeInTheDocument());
  });
});
