import { render, screen, waitFor } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { LivePage } from './LivePage';
import type {
  ActivityHistory, ApiHealth, LiveFeed, LiveState, MonitoringStatus, TonightStatus, VoiceHistory,
} from '../lib/types';
import stateJson from './__fixtures__/api_live_state_quiet_form.json';
import feedJson from './__fixtures__/api_live_feed.json';
import serverJson from './__fixtures__/api_server_activity_history.json';
import voiceJson from './__fixtures__/api_voice_activity_history.json';
import monitoringJson from './__fixtures__/api_monitoring_status.json';
import statusJson from './__fixtures__/api_status.json';
import tonightJson from './__fixtures__/api_stats_tonight.json';
import tonightQuietJson from './__fixtures__/api_stats_tonight.quiet.json';
import eveningFeedJson from './__fixtures__/api_live_feed.evening.json';

const liveState = stateJson satisfies LiveState;
const feed = feedJson satisfies LiveFeed;
const serverHist = serverJson satisfies ActivityHistory;
const voiceHist = voiceJson satisfies VoiceHistory;
const monitoring = monitoringJson satisfies MonitoringStatus;
const health = statusJson satisfies ApiHealth;
const tonight = tonightJson satisfies TonightStatus;
const tonightQuiet = tonightQuietJson satisfies TonightStatus;
const eveningFeed = eveningFeedJson as unknown as LiveFeed;

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
      '/api/stats/tonight': tonightQuiet,
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

/** An evening in progress: the recorded score board of 2026-09-07 (eight
 *  maps, 5–2) beside a live state in its second half — the strip the
 *  visitor reads first, and the board the legacy page had that the new one
 *  fetched and never showed (ledger 2026-09-08). */
describe('LivePage — the evening', () => {
  const inSecondHalf: LiveState = {
    ...liveState,
    is_live: true,
    game_state: 'live',
    current_map: 'etl_adlernest',
    previous_map: 'supply',
    round_number: 2,
    round_elapsed_seconds: 72,
    session_start_seconds: 1500,
    attacking_side: 'allies',
    time_to_beat_seconds: 210,
    last_round_result: {
      round_number: 1, map: 'etl_adlernest', reason: 'timelimit', reason_raw: 'Timelimit hit.',
      winner_side: 'axis', duration_seconds: 210, full_hold: true, ended_age_seconds: 95,
    },
    roster: { ...liveState.roster, player_count: 6 },
  };

  it('says which half, the clock, the time to beat, who attacks, and what the last half ended on', async () => {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL): Promise<Response> => {
      const pathname = String(input).split('?')[0];
      const body = {
        '/api/live/state': inSecondHalf,
        '/api/live/feed': eveningFeed,
        '/api/server-activity/history': serverHist,
        '/api/voice-activity/history': voiceHist,
        '/api/monitoring/status': monitoring,
        '/api/status': health,
        '/api/stats/tonight': tonight,
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
    await waitFor(() => expect(screen.getByText(/R2 · 1:1[2-9]/)).toBeInTheDocument());
    expect(screen.getByText(/to beat 3:30/)).toBeInTheDocument();
    expect(screen.getByText('Allies attack')).toBeInTheDocument();
    expect(screen.getByText(/last: R1 full hold 3:30 \(Axis\)/)).toBeInTheDocument();
    expect(screen.getByText(/before that supply/)).toBeInTheDocument();
    // The board: the recorded director's sentence, the map score, the rosters,
    // every recorded map, and the hold curve with its marker sentence.
    await waitFor(() => expect(screen.getByText(tonight.director!)).toBeInTheDocument());
    expect(screen.getByText(/Team A 2 – 5 Team B/)).toBeInTheDocument();
    expect(screen.getByText(/rounds 7–9 · 8 completed/)).toBeInTheDocument();
    for (const m of tonight.maps) {
      expect(screen.getAllByText(new RegExp(`#${m.map_number}$`)).length).toBeGreaterThan(0);
    }
    expect(screen.getByLabelText(`hold probability on ${tonight.hold_probability!.map}`)).toBeInTheDocument();
    // `p` is a percentage already (0.9 at t=60 in the recording): printed as
    // received, not multiplied again — the marker at 1:12 reads the t=60 point.
    expect(screen.getByText(/by 1:1\d the attack had completed in 0\.9 % of recorded halves/)).toBeInTheDocument();
    expect(screen.getByText(/players on for 25:00/)).toBeInTheDocument();
    expect(screen.getByText(/last imported/)).toBeInTheDocument();
    expect(screen.queryByText(/^now /)).toBeNull();
    expect(screen.getByLabelText('team momentum')).toBeInTheDocument();
    // The ticker reads its events: a recorded kill as a sentence with its
    // weapon and (from the folded LIVE_KILL twin) its distance; no bare type
    // names; the plant once, not as POPUP and DYNAMITE.
    await waitFor(() => expect(screen.getAllByText(/killed .* · mp40/).length).toBeGreaterThan(0));
    expect(screen.getAllByText(/ · \d+ u/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/^live kill$/)).toBeNull();
    expect(screen.queryByText(/^team change$/)).toBeNull();
  });

  it('a night with no imported round says so instead of an empty board', async () => {
    stub();
    render(
      <QueryClientProvider client={makeQueryClient()}>
        <MemoryRouter initialEntries={['/live']}>
          <LivePage />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await waitFor(() => expect(screen.getByText(/no round has been imported today/)).toBeInTheDocument());
  });

  it('draws the mini map from the positions and kills the state carries, and nothing without them', async () => {
    const withPositions: LiveState = {
      ...inSecondHalf,
      roster: {
        ...inSecondHalf.roster,
        axis: [{ slot: 3, name: '^1one^7', on_server_seconds: 100, on_side_seconds: 100, pos: { x: 100, y: -200, yaw: 90, age_seconds: 4 }, live: { kills: 1, deaths: 0, damage: 50, dpm: null, alive: true } }],
        allies: [{ slot: 5, name: 'two', on_server_seconds: 100, on_side_seconds: 100, pos: { x: 300, y: 50, yaw: null, age_seconds: 9 }, live: { kills: 0, deaths: 1, damage: 0, dpm: null, alive: false } }],
      },
      recent_kills: [{ killer_slot: 3, victim_slot: 5, killer: 'one', victim: 'two', killer_pos: { x: 100, y: -200 }, victim_pos: { x: 300, y: 50 }, distance: 320, killer_health: 60, mod_id: 8, age_seconds: 6 }],
    };
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL): Promise<Response> => {
      const pathname = String(input).split('?')[0];
      if (pathname.startsWith('/assets/maps/geometry/')) return Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({}) } as Response);
      const body = {
        '/api/live/state': withPositions,
        '/api/live/feed': feed,
        '/api/server-activity/history': serverHist,
        '/api/voice-activity/history': voiceHist,
        '/api/monitoring/status': monitoring,
        '/api/status': health,
        '/api/stats/tonight': tonight,
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
    const map = await screen.findByLabelText('2 placed, 1 recent kills');
    expect(map.querySelectorAll('circle').length).toBe(2);
    expect(map.textContent).toContain('one');
    expect(map.textContent).not.toContain('^1');
    expect(screen.getByText(/no floor mesh exported for this map/)).toBeInTheDocument();
  });

  it('hides a last-round result older than the roster (a previous evening), a previous map the evening never imported, and names an unknown winner', async () => {
    const afterGap: LiveState = {
      ...inSecondHalf,
      previous_map: 'gammajump',
      session_start_seconds: 40,
      last_round_result: { ...inSecondHalf.last_round_result!, ended_age_seconds: 4 * 3600 },
    };
    const withUnknownWinner: TonightStatus = {
      ...tonight,
      maps: tonight.maps.map((m, i) => (i === 0 ? { ...m, rounds: [{ ...m.rounds[0], winner: null }, m.rounds[1]] } : m)),
    };
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL): Promise<Response> => {
      const pathname = String(input).split('?')[0];
      const body = {
        '/api/live/state': afterGap,
        '/api/live/feed': feed,
        '/api/server-activity/history': serverHist,
        '/api/voice-activity/history': voiceHist,
        '/api/monitoring/status': monitoring,
        '/api/status': health,
        '/api/stats/tonight': withUnknownWinner,
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
    await waitFor(() => expect(screen.getByText(/R2 · 1:1[2-9]/)).toBeInTheDocument());
    expect(screen.queryByText(/last: R1/)).toBeNull();
    expect(screen.queryByText(/before that/)).toBeNull();
    await waitFor(() => expect(screen.getByText(/R1 unknown · 3:30/)).toBeInTheDocument());
    expect(screen.queryByText(/R1 pending/)).toBeNull();
  });
});

describe('LivePage long tail (ledger 2026-09-09)', () => {
  it('names the server clock on the ticker, the last record of each sampler, and the api by its service name', async () => {
    stub();
    render(
      <QueryClientProvider client={makeQueryClient()}>
        <MemoryRouter initialEntries={['/live']}>
          <LivePage />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    // feed.server_time is epoch seconds (recorded 1788349751.86 → 2026-09-02 11:49 UTC).
    await waitFor(() => expect(screen.getByText(/server clock 2026-09-02 11:49 UTC/)).toBeInTheDocument());
    // monitoring.server.last_recorded_at, recorded 2026-09-02T11:45:40Z.
    expect(screen.getByText(/server sampling fresh · [\d,]+ records · last 2026-09-02 11:45 UTC/)).toBeInTheDocument();
    expect(screen.getByText(/voice sampling fresh · [\d,]+ records · last 2026-09-02 11:48 UTC/)).toBeInTheDocument();
    expect(screen.getByText(/^Slomix API: api /)).toBeInTheDocument();
  });
});
