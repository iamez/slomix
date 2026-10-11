import { afterEach, expect, it, vi } from 'vitest';

const fetchJSON = vi.hoisted(() => vi.fn());
vi.mock('../../../js/utils.js', () => ({
  API_BASE: '/api', fetchJSON,
  escapeHtml: (value: unknown) => String(value ?? ''), safeInsertHTML: vi.fn(),
}));
vi.mock('../../../js/live-state.js?v=20260819-ladder', () => ({ getSnapshot: () => null }));

afterEach(() => { vi.useRealTimers(); vi.resetModules(); fetchJSON.mockReset(); });

it('legacy polling recovers a new worker and clears the old roster', async () => {
  vi.useFakeTimers();
  document.body.innerHTML = '<div id="view-live" class="active"></div>';
  Object.defineProperty(document, 'hidden', { configurable: true, value: false });
  let fresh = false;
  fetchJSON.mockImplementation(async () => ({
    status: 'ok', stream_id: fresh ? 'new' : 'old', last_seq: fresh ? 1 : 100,
    cursor_reset: fresh, gap: false,
    events: [{ seq: fresh ? 1 : 100, type: 'TEAM_CHANGE', slot: 1, team: 1,
      name: fresh ? 'new player' : 'old player', received_at: Date.now() / 1000 }],
  }));
  // @ts-expect-error existing JS module has no declaration file
  const ticker = await import('../../../js/live-ticker.js');
  ticker.startLiveTicker();
  await vi.advanceTimersByTimeAsync(0);
  expect(ticker.getLiveRoster().axis).toEqual(['old player']);
  fresh = true;
  await vi.advanceTimersByTimeAsync(3000);
  expect(ticker.getLiveRoster().axis).toEqual(['new player']);
  expect(fetchJSON.mock.calls.at(-1)?.[0]).toBe('/api/live/feed?since=0');
  ticker.stopLiveTicker();
});

it('does not overlap requests when the feed is slow', async () => {
  vi.useFakeTimers();
  document.body.innerHTML = '<div id="view-live" class="active"></div>';
  Object.defineProperty(document, 'hidden', { configurable: true, value: false });
  let finish!: (value: unknown) => void;
  fetchJSON.mockImplementation(() => new Promise((resolve) => { finish = resolve; }));
  // @ts-expect-error existing JS module has no declaration file
  const ticker = await import('../../../js/live-ticker.js');
  ticker.startLiveTicker();
  await vi.advanceTimersByTimeAsync(9000);
  expect(fetchJSON).toHaveBeenCalledTimes(1);
  finish({ events: [], last_seq: 0 });
  await vi.advanceTimersByTimeAsync(0);
  ticker.stopLiveTicker();
});
