import { afterEach, expect, it, vi } from 'vitest';

const fetchJSON = vi.hoisted(() => vi.fn());
vi.mock('../../../js/utils.js', () => ({
  API_BASE: '/api', fetchJSON,
  escapeHtml: (value: unknown) => String(value ?? ''), safeInsertHTML: (host: HTMLElement, position: InsertPosition, html: string) => host.insertAdjacentHTML(position, html),
}));
vi.mock('../../../js/live-state.js?v=20261012-live-audit', () => ({ getSnapshot: () => null }));

afterEach(() => { vi.useRealTimers(); localStorage.clear(); vi.resetModules(); fetchJSON.mockReset(); });

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


it('renders a failed poll immediately and recovers on an empty response', async () => {
  vi.useFakeTimers();
  document.body.innerHTML = '<div id="view-live" class="active"></div><div id="live-ticker"></div>';
  Object.defineProperty(document, 'hidden', { configurable: true, value: false });
  const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
  fetchJSON.mockRejectedValueOnce(new Error('offline')).mockResolvedValue({ events: [], last_seq: 0 });
  // @ts-expect-error existing JS module has no declaration file
  const ticker = await import('../../../js/live-ticker.js');
  try {
    ticker.startLiveTicker();
    await vi.advanceTimersByTimeAsync(0);
    expect(document.getElementById('live-ticker')?.textContent).toContain('feed error');
    await vi.advanceTimersByTimeAsync(3000);
    expect(document.getElementById('live-ticker')?.textContent).toContain('quiet');
    expect(document.getElementById('live-ticker')?.textContent).not.toContain('feed error');
  } finally { ticker.stopLiveTicker(); warn.mockRestore(); }
});

it('expires old rows and clears derived scores on an empty gap response', async () => {
  vi.useFakeTimers();
  document.body.innerHTML = '<div id="view-live" class="active"></div><div id="live-ticker"></div>';
  Object.defineProperty(document, 'hidden', { configurable: true, value: false });
  const received = Date.now() / 1000;
  fetchJSON.mockResolvedValueOnce({ last_seq: 1, events: [
    { seq: 1, type: 'REVIVE', slots: '1 2', received_at: received },
  ] }).mockResolvedValue({ events: [], last_seq: 2, gap: true });
  // @ts-expect-error existing JS module has no declaration file
  const ticker = await import('../../../js/live-ticker.js');
  try {
    ticker.startLiveTicker();
    await vi.advanceTimersByTimeAsync(0);
    expect(ticker.getLiveMVP()).not.toBeNull();
    document.querySelector<HTMLInputElement>('input[data-live-cat="support"]')!.click();
    expect(document.getElementById('live-ticker')?.textContent).toContain('revived');
    vi.setSystemTime(new Date((received + 601) * 1000));
    await vi.advanceTimersByTimeAsync(3000);
    expect(ticker.getLiveMVP()).toBeNull();
    expect(document.getElementById('live-ticker')?.textContent).not.toContain('revived');
    expect(document.getElementById('live-ticker')?.textContent).toContain('No live events');
  } finally { ticker.stopLiveTicker(); }
});

it('removes the previous worker from the DOM when its replacement read fails', async () => {
  vi.useFakeTimers();
  document.body.innerHTML = '<div id="view-live" class="active"></div><div id="live-ticker"></div>';
  Object.defineProperty(document, 'hidden', { configurable: true, value: false });
  const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
  fetchJSON.mockResolvedValueOnce({ stream_id: 'old', last_seq: 100, events: [
    { seq: 100, type: 'ROUND_START', received_at: Date.now() / 1000 },
  ] }).mockResolvedValueOnce({ stream_id: 'new', last_seq: 1, events: [] })
    .mockRejectedValueOnce(new Error('replacement unavailable'));
  // @ts-expect-error existing JS module has no declaration file
  const ticker = await import('../../../js/live-ticker.js');
  try {
    ticker.startLiveTicker();
    await vi.advanceTimersByTimeAsync(0);
    expect(document.getElementById('live-ticker')?.textContent).toContain('ROUND START');
    await vi.advanceTimersByTimeAsync(3000);
    expect(document.getElementById('live-ticker')?.textContent).toContain('feed error');
    expect(document.getElementById('live-ticker')?.textContent).not.toContain('ROUND START');
  } finally { ticker.stopLiveTicker(); warn.mockRestore(); }
});

it.each(['DISCONNECT', 'CONNECT'])('keeps historical identity and clears MVP/streak at %s', async (boundary) => {
  vi.useFakeTimers();
  document.body.innerHTML = '<div id="view-live" class="active"></div><div id="live-ticker"></div>';
  Object.defineProperty(document, 'hidden', { configurable: true, value: false });
  localStorage.setItem('slomix.liveFeedFilters.v1', JSON.stringify({ kills: true, objectives: true, support: true }));
  let seq = 0;
  const page = (events: Record<string, unknown>[]) => ({ events: events.map(e => ({ ...e, seq: ++seq, received_at: Date.now() / 1000 })), last_seq: seq });
  fetchJSON.mockResolvedValueOnce(page([
    { type: 'TEAM_CHANGE', slot: 3, team: 1, name: 'original' },
    { type: 'TEAM_CHANGE', slot: 4, team: 2, name: 'victim' },
    { type: 'KILL', killer_slot: 3, victim_slot: 4, killer: 'original', victim: 'victim' },
    { type: 'KILL', killer_slot: 3, victim_slot: 4, killer: 'original', victim: 'victim' },
  ])).mockResolvedValueOnce(page([
    { type: boundary, slot: '3' },
    { type: 'TEAM_CHANGE', slot: 3, team: 1, name: 'replacement' },
    { type: 'KILL', killer_slot: 3, victim_slot: 4, killer: 'replacement', victim: 'victim' },
  ])).mockResolvedValueOnce(page([
    { type: 'LIVE_KILL', killer_slot: 3, victim_slot: 4, killer: 'original', victim: 'victim' },
    { type: 'LIVE_KILL', killer_slot: 3, victim_slot: 4 },
    { type: 'DYNAMITE', slot: 3, action: 'plant', objective: 'fixture' },
    { type: 'REVIVE', slots: '3 4', actor_name: 'original', target_name: 'victim' },
  ])).mockResolvedValue(page([]));
  // @ts-expect-error existing JS module has no declaration file
  const ticker = await import('../../../js/live-ticker.js');
  try {
    ticker.startLiveTicker(); await vi.advanceTimersByTimeAsync(0);
    expect(ticker.getLiveMVP()).toMatchObject({ name: 'original', score: 2 });
    await vi.advanceTimersByTimeAsync(3000);
    expect(ticker.getLiveMVP()).toMatchObject({ name: 'replacement', score: 1 });
    expect(document.getElementById('live-ticker')?.textContent).not.toContain('3 streak');
    await vi.advanceTimersByTimeAsync(3000);
    const text = document.getElementById('live-ticker')!.textContent!;
    expect(text).toContain('original → victim');
    expect(text).toContain('#3 → #4');
    expect(text).toContain('#3 planted dynamite at fixture');
    expect(text).toContain('original revived victim');
    expect(text).not.toContain('replacement → victim');
  } finally { ticker.stopLiveTicker(); }
});

it('ignores invalid engine slots in roster, streak and MVP including partially numeric strings', async () => {
  vi.useFakeTimers();
  document.body.innerHTML = '<div id="view-live" class="active"></div><div id="live-ticker"></div>';
  Object.defineProperty(document, 'hidden', { configurable: true, value: false });
  localStorage.setItem('slomix.liveFeedFilters.v1', JSON.stringify({ kills: true }));
  let seq = 0;
  const events: Record<string, unknown>[] = [];
  for (const slot of [-1, 64, 1022, 2.5, true, null, '3bad', ...Array.from({ length: 70 }, (_, i) => 100 + i)]) {
    events.push({ type: 'TEAM_CHANGE', slot, team: 1, name: 'invalid' },
      ...Array.from({ length: 3 }, () => ({ type: 'KILL', killer_slot: slot, victim_slot: slot, killer: 'invalid', victim: 'invalid' })),
      { type: 'REVIVE', slots: `${slot} 2` }, { type: 'DYNAMITE', slot, action: 'plant' });
  }
  fetchJSON.mockResolvedValueOnce({ events: events.map(e => ({ ...e, seq: ++seq, received_at: Date.now() / 1000 })), last_seq: events.length })
    .mockResolvedValue({ events: [], last_seq: events.length });
  // @ts-expect-error existing JS module has no declaration file
  const ticker = await import('../../../js/live-ticker.js');
  try {
    ticker.startLiveTicker(); await vi.advanceTimersByTimeAsync(0);
    expect(ticker.getLiveRoster().axis).toEqual([]);
    expect(ticker.getLiveMVP()).toBeNull();
    expect(document.getElementById('live-ticker')?.textContent).not.toContain('streak');
  } finally { ticker.stopLiveTicker(); }
});

it.each([false, true])('retains named twin evidence across polls without double effects (split=%s)', async (split) => {
  vi.useFakeTimers();
  localStorage.setItem('slomix.liveFeedFilters.v1', JSON.stringify({ kills: true }));
  vi.setSystemTime(new Date('2026-10-13T12:00:00Z'));
  document.body.innerHTML = '<div id="view-live" class="active"><div id="live-ticker"></div></div>';
  Object.defineProperty(document, 'hidden', { configurable: true, value: false });
  const now = Date.now() / 1000;
  const original = { seq: 2, type: 'LIVE_KILL', killer_slot: 3, victim_slot: 5, killer: null, victim: null, distance: 120, received_at: now };
  const named = { seq: 3, type: 'KILL', duplicate_of: 2, killer_slot: 3, victim_slot: 5, killer: 'Source A', victim: 'Source B', received_at: now + 0.5 };
  const start = { seq: 1, type: 'ROUND_START', received_at: now };
  let polls = 0;
  fetchJSON.mockImplementation(async () => {
    const events = polls++ === 0 ? [start, original, ...(split ? [] : [named])] : split && polls === 2 ? [named] : [];
    return { status: 'ok', stream_id: 'fixture', last_seq: 3, events };
  });
  // @ts-expect-error existing JS module has no declaration file
  const ticker = await import('../../../js/live-ticker.js');
  ticker.startLiveTicker();
  try {
    await vi.advanceTimersByTimeAsync(0);
    const score = ticker.getLiveMVP().score;
    expect(score).toBe(1);
    await vi.advanceTimersByTimeAsync(3000);
    expect(ticker.getLiveMVP().score).toBe(score);
    expect(ticker.getLiveMVP().name).toBe('Source A');
    const text = document.getElementById('live-ticker')!.textContent!;
    expect(text).toContain('Source A');
    expect(text).toContain('Source B');
    expect(text.match(/Source A/g)).toHaveLength(2); // One MVP badge and one obituary.
    expect(text.match(/Source B/g)).toHaveLength(1);
    expect(text.match(/→/g)).toHaveLength(1);
    expect(text).not.toContain('#3 → #5');
    expect(text).toContain('120u');
  } finally { ticker.stopLiveTicker(); }
});

it('renders orphaned source-name evidence while LIVE_KILL events are active', async () => {
  vi.useFakeTimers();
  localStorage.setItem('slomix.liveFeedFilters.v1', JSON.stringify({ kills: true }));
  document.body.innerHTML = '<div id="view-live" class="active"><div id="live-ticker"></div></div>';
  Object.defineProperty(document, 'hidden', { configurable: true, value: false });
  const now = Date.now() / 1000;
  fetchJSON.mockResolvedValue({ status: 'ok', stream_id: 'fixture', last_seq: 20, events: [
    { seq: 19, type: 'LIVE_KILL', killer_slot: 1, victim_slot: 2, received_at: now },
    { seq: 20, type: 'KILL', duplicate_of: 5, killer_slot: 3, victim_slot: 4, killer: 'Orphan A', victim: 'Orphan B', received_at: now },
  ] });
  // @ts-expect-error existing JS module has no declaration file
  const ticker = await import('../../../js/live-ticker.js');
  ticker.startLiveTicker();
  try {
    await vi.advanceTimersByTimeAsync(0);
    expect(document.getElementById('live-ticker')!.textContent).toContain('Orphan A');
    expect(document.getElementById('live-ticker')!.textContent).toContain('Orphan B');
  } finally { ticker.stopLiveTicker(); }
});

it.each([false, true])('folds source-named KILL before LIVE_KILL once across polls (split=%s)', async (split) => {
  vi.useFakeTimers();
  localStorage.setItem('slomix.liveFeedFilters.v1', JSON.stringify({ kills: true }));
  document.body.innerHTML = '<div id="view-live" class="active"><div id="live-ticker"></div></div>';
  Object.defineProperty(document, 'hidden', { configurable: true, value: false });
  const now = Date.now() / 1000;
  const named = { seq: 2, type: 'KILL', killer_slot: 3, victim_slot: 5, killer: 'Reverse A', victim: 'Reverse B', received_at: now };
  const live = { seq: 3, type: 'LIVE_KILL', killer_slot: 3, victim_slot: 5, killer: null, victim: null, distance: 120, received_at: now + 0.5 };
  fetchJSON.mockResolvedValueOnce({ stream_id: 'reverse', last_seq: split ? 2 : 3, events: [{ seq: 1, type: 'ROUND_START', received_at: now }, named, ...(split ? [] : [live])] })
    .mockResolvedValueOnce({ stream_id: 'reverse', last_seq: 3, events: split ? [live] : [] })
    .mockResolvedValue({ stream_id: 'reverse', last_seq: 6, events: [
      { seq: 4, type: 'KILL', duplicate_of: 3, killer_slot: 3, victim_slot: 5, killer: 'Reverse A', victim: 'Reverse B', received_at: now + 0.7 },
      { seq: 5, type: 'CONNECT', slot: 3, received_at: now + 1 },
      { seq: 6, type: 'TEAM_CHANGE', slot: 3, team: 1, name: 'Replacement', received_at: now + 1 },
    ] });
  // @ts-expect-error existing JS module has no declaration file
  const ticker = await import('../../../js/live-ticker.js');
  ticker.startLiveTicker();
  try {
    await vi.advanceTimersByTimeAsync(0);
    expect(ticker.getLiveMVP().score).toBe(1);
    await vi.advanceTimersByTimeAsync(3000);
    expect(ticker.getLiveMVP().score).toBe(1);
    let text = document.getElementById('live-ticker')!.textContent!;
    expect(text).toContain('Reverse A'); expect(text).toContain('Reverse B');
    expect(text).toContain('120u'); expect(text).not.toContain('#3 → #5');
    expect(text.match(/Reverse A → Reverse B/g)).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(3000);
    text = document.getElementById('live-ticker')!.textContent!;
    expect(text).toContain('Reverse A'); expect(text).not.toContain('Replacement →');
    expect(text.match(/Reverse A → Reverse B/g)).toHaveLength(1);
    expect(text).not.toContain('Reverse A killed Reverse B');
  } finally { ticker.stopLiveTicker(); }
});

it.each([
  [{ type: 'CONNECT', slot: 3 }, false], [{ type: 'DISCONNECT', slot: 5 }, false],
  [{ type: 'ROUND_START' }, false], [{ type: 'ROUND_END' }, false], [{ type: 'INIT_GAME' }, false],
  [{ type: 'MAP', map_name: 'supply' }, false], [{ type: 'LIVE_MAP', map_name: 'supply', map_accepted: true }, false],
  [{ type: 'LIVE_MAP', map_name: 'radar', map_accepted: true }, true],
  [{ type: 'LIVE_MAP', map_name: 'supply', map_accepted: false }, true],
  [{ type: 'LIVE_MAP', map_name: '' }, true],
])('reverse twins respect explicit context boundary %j (fold=%s)', async (boundary, fold) => {
  vi.useFakeTimers();
  localStorage.setItem('slomix.liveFeedFilters.v1', JSON.stringify({ kills: true }));
  document.body.innerHTML = '<div id="view-live" class="active"><div id="live-ticker"></div></div>';
  Object.defineProperty(document, 'hidden', { configurable: true, value: false });
  const now = Date.now() / 1000;
  const events = [
    { type: 'MAP', map_name: 'radar' },
    { type: 'KILL', killer_slot: 3, victim_slot: 5, killer: 'Original A', victim: 'Original B' },
    boundary,
    { type: 'LIVE_KILL', killer_slot: 3, victim_slot: 5, killer: null, victim: null, distance: 120 },
  ].map((event, i) => ({ ...event, seq: i + 1, received_at: now + i / 10 }));
  fetchJSON.mockResolvedValue({ events, last_seq: 4, stream_id: 'context' });
  // @ts-expect-error existing JS module has no declaration file
  const ticker = await import('../../../js/live-ticker.js');
  ticker.startLiveTicker();
  try {
    await vi.advanceTimersByTimeAsync(0);
    const text = document.getElementById('live-ticker')!.textContent!;
    expect(text.includes('Original A → Original B')).toBe(fold);
    expect(text.includes('#3 → #5')).toBe(!fold);
  } finally { ticker.stopLiveTicker(); }
});

it.each(['expired', 'conflict', 'already-active'])('reverse twins handle %s without losing or duplicating MVP', async (scenario) => {
  vi.useFakeTimers();
  localStorage.setItem('slomix.liveFeedFilters.v1', JSON.stringify({ kills: true }));
  document.body.innerHTML = '<div id="view-live" class="active"><div id="live-ticker"></div></div>';
  Object.defineProperty(document, 'hidden', { configurable: true, value: false });
  const now = Date.now() / 1000;
  const events = [
    ...(scenario === 'already-active' ? [{ type: 'LIVE_KILL', killer_slot: 7, victim_slot: 7, received_at: now }] : []),
    { type: 'KILL', killer_slot: 3, victim_slot: 5, killer: 'First A', victim: 'First B', received_at: now },
    { type: 'LIVE_KILL', killer_slot: 3, victim_slot: 5, killer: scenario === 'conflict' ? 'Other A' : null, victim: null, distance: 120, received_at: now + (scenario === 'expired' ? 4 : 0.5) },
  ].map((event, i) => ({ ...event, seq: i + 1 }));
  fetchJSON.mockResolvedValue({ events, last_seq: events.length, stream_id: 'bounded' });
  // @ts-expect-error existing JS module has no declaration file
  const ticker = await import('../../../js/live-ticker.js');
  ticker.startLiveTicker();
  try {
    await vi.advanceTimersByTimeAsync(0);
    expect(ticker.getLiveMVP().score).toBe(scenario === 'already-active' ? 1 : 2);
    const text = document.getElementById('live-ticker')!.textContent!;
    if (scenario === 'already-active') expect(text).toContain('First A');
    else expect(text).not.toContain('First A');
    if (scenario === 'conflict') expect(text).toContain('Other A');
  } finally { ticker.stopLiveTicker(); }
});

it('does not consume a LIVE kill when its pending legacy row was evicted in the same batch', async () => {
  vi.useFakeTimers();
  localStorage.setItem('slomix.liveFeedFilters.v1', JSON.stringify({ kills: true }));
  document.body.innerHTML = '<div id="view-live" class="active"><div id="live-ticker"></div></div>';
  Object.defineProperty(document, 'hidden', { configurable: true, value: false });
  const now = Date.now() / 1000;
  const events = [
    { type: 'KILL', killer_slot: 3, victim_slot: 5, killer: 'Evicted A', victim: 'Evicted B' },
    ...Array.from({ length: 200 }, () => ({ type: 'SAY', name: 'speaker', text: 'buffer row' })),
    { type: 'LIVE_KILL', killer_slot: 3, victim_slot: 5, killer: null, victim: null, distance: 120 },
  ].map((event, i) => ({ ...event, seq: i + 1, received_at: now }));
  fetchJSON.mockResolvedValue({ events, last_seq: events.length, stream_id: 'eviction' });
  // @ts-expect-error existing JS module has no declaration file
  const ticker = await import('../../../js/live-ticker.js');
  ticker.startLiveTicker();
  try {
    await vi.advanceTimersByTimeAsync(0);
    const text = document.getElementById('live-ticker')!.textContent!;
    expect(text).toContain('#3 → #5'); expect(text).toContain('120u');
  } finally { ticker.stopLiveTicker(); }
});


it('does not replace a later roster rename with historical enrichment', async () => {
  vi.useFakeTimers();
  document.body.innerHTML = '<div id="view-live" class="active"><div id="live-ticker"></div></div>';
  Object.defineProperty(document, 'hidden', { configurable: true, value: false });
  const now = Date.now() / 1000;
  fetchJSON.mockResolvedValueOnce({ last_seq: 4, events: [
    { seq: 1, type: 'ROUND_START', received_at: now },
    { seq: 2, type: 'LIVE_KILL', killer_slot: 3, victim_slot: 5, received_at: now },
    { seq: 3, type: 'TEAM_CHANGE', slot: 3, team: 1, name: 'Current name', received_at: now + 0.1 },
    { seq: 4, type: 'KILL', duplicate_of: 2, killer_slot: 3, victim_slot: 5, killer: 'Historical name', victim: 'Victim', received_at: now + 0.2 },
  ] }).mockResolvedValue({ last_seq: 4, events: [] });
  // @ts-expect-error existing JS module has no declaration file
  const ticker = await import('../../../js/live-ticker.js');
  ticker.startLiveTicker();
  try {
    await vi.advanceTimersByTimeAsync(0);
    expect(ticker.getLiveMVP()).toMatchObject({ name: 'Current name', score: 1 });
    expect(ticker.getLiveRoster().axis).toEqual(['Current name']);
  } finally { ticker.stopLiveTicker(); }
});


it.each(['death', 'continuity', 'live-first', 'legacy-first'] as const)(
  'keeps accepted kill streak continuity through legacy fallback (%s)', async (scenario) => {
    vi.useFakeTimers();
    localStorage.setItem('slomix.liveFeedFilters.v1', JSON.stringify({ kills: true }));
    document.body.innerHTML = '<div id="view-live" class="active"><div id="live-ticker"></div></div>';
    Object.defineProperty(document, 'hidden', { configurable: true, value: false });
    const now = Date.now() / 1000;
    const kill = (seq: number, type: string, killer_slot = 3, victim_slot = 5) => ({
      seq, type, killer_slot, victim_slot, killer: 'Source A', victim: 'Source B', received_at: now,
    });
    const events = scenario === 'death'
      ? [kill(2, 'KILL'), kill(3, 'KILL'), kill(4, 'LIVE_KILL', 5, 3)]
      : scenario === 'continuity' ? [kill(2, 'LIVE_KILL'), kill(3, 'LIVE_KILL')]
      : scenario === 'live-first' ? [kill(2, 'LIVE_KILL'), { ...kill(3, 'KILL'), duplicate_of: 2 }]
      : [kill(2, 'KILL'), kill(3, 'LIVE_KILL')];
    const fallback = { ...kill(5, 'KILL'), received_at: now + 124, _streak: undefined as number | undefined };
    fetchJSON.mockResolvedValueOnce({ last_seq: 4, events: [{ seq: 1, type: 'ROUND_START', received_at: now }, ...events] })
      .mockResolvedValue({ last_seq: 4, events: [] });
    // @ts-expect-error existing JS module has no declaration file
    const ticker = await import('../../../js/live-ticker.js');
    ticker.startLiveTicker();
    try {
      await vi.advanceTimersByTimeAsync(121000);
      fetchJSON.mockResolvedValueOnce({ last_seq: 5, events: [fallback] });
      await vi.advanceTimersByTimeAsync(3000);
      const expected = scenario === 'death' ? 1 : scenario === 'continuity' ? 3 : 2;
      expect(fallback._streak).toBe(expected);
      const text = document.getElementById('live-ticker')!.textContent!;
      if (expected === 3) expect(text).toContain('🔥 3 streak');
      else expect(text).not.toContain('🔥 3 streak');
    } finally { ticker.stopLiveTicker(); }
  },
);
