import { afterEach, expect, it, vi } from 'vitest';
const fetchJSON = vi.hoisted(() => vi.fn());
vi.mock('../../../js/utils.js', () => ({
  API_BASE: '/api', fetchJSON, escapeHtml: (value: unknown) => String(value ?? ''),
  safeInsertHTML: (host: HTMLElement, position: InsertPosition, html: string) => host.insertAdjacentHTML(position, html),
}));
vi.mock('../../../js/player-card.js?v=20260819-card', () => ({ openPlayerCard: vi.fn() }));
afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); vi.resetModules(); fetchJSON.mockReset(); });
function setup() {
  vi.useFakeTimers();
  document.body.innerHTML = '<div id="view-live" class="active"></div><div id="live-state"></div>';
  Object.defineProperty(document, 'hidden', { configurable: true, value: false });
  vi.spyOn(console, 'warn').mockImplementation(() => {});
}
it('renders initial loading, failure, and successful recovery without a parent refresh', async () => {
  setup();
  fetchJSON.mockRejectedValueOnce(new Error('offline')).mockResolvedValue({
    is_live: true, game_state: 'live', current_map: 'supply',
    roster: { axis: [], allies: [], spectators: [] },
  });
  // @ts-expect-error existing JS module has no declaration file
  const state = await import('../../../js/live-state.js');
  try {
    state.startLiveState();
    expect(document.getElementById('live-state')?.textContent).toContain('checking live updates');
    await vi.advanceTimersByTimeAsync(0);
    expect(document.getElementById('live-state')?.textContent).toContain('state unavailable');
    await vi.advanceTimersByTimeAsync(4000);
    expect(document.getElementById('live-state')?.textContent).toContain('supply');
    expect(document.getElementById('live-state')?.textContent).not.toContain('state unavailable');
    fetchJSON.mockRejectedValue(new Error('offline again'));
    await vi.advanceTimersByTimeAsync(4000);
    expect(document.getElementById('live-state')?.textContent).toContain('state unavailable');
    expect(document.getElementById('live-state')?.textContent).toContain('supply');
  } finally { state.stopLiveState(); }
});
