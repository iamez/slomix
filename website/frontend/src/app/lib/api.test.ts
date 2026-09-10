import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, apiDelete, apiGet, apiGetResponse, apiPost, apiUploadWithProgress } from './api';

/**
 * Compile-time contract (checked by `npm run typecheck`, which compiles this
 * file): the generated paths map is load-bearing — a nonexistent path or a
 * wrong query parameter name must fail the BUILD, because that is exactly
 * where the real bugs lived (client.ts:456 called a 404 path for months —
 * docs/design/07 §C.1).
 */
function compileTimeContract() {
  void apiGet('/api/stats/session-leaderboard', { query: { limit: 5, session_id: 150 } });
  // @ts-expect-error nonexistent path must not compile
  void apiGet('/api/does-not-exist');
  // @ts-expect-error wrong query parameter name must not compile
  void apiGet('/api/stats/session-leaderboard', { query: { days: 5 } });
  void apiGet('/api/rounds/{round_id}/awards', { pathParams: { round_id: 11277 } });
  // @ts-expect-error templated path without pathParams must not compile
  void apiGet('/api/rounds/{round_id}/awards');
  // @ts-expect-error wrong path parameter name must not compile
  void apiGet('/api/rounds/{round_id}/awards', { pathParams: { roundId: 11277 } });
  // @ts-expect-error plain path must not accept pathParams
  void apiGet('/api/stats/overview', { pathParams: { round_id: 1 } });
  void apiGet('/api/player/search', { query: { query: 'vid' } });
  // @ts-expect-error required query must not compile without it
  void apiGet('/api/player/search');
  void apiGet('/api/replay/round/{round_id}/positions', {
    pathParams: { round_id: 11277 },
    query: { t: 148600 },
  });
  // @ts-expect-error required query t missing must not compile
  void apiGet('/api/replay/round/{round_id}/positions', { pathParams: { round_id: 11277 } });
  void apiDelete('/api/availability/subscriptions/{channel_type}', { pathParams: { channel_type: 'telegram' } });
  // @ts-expect-error a GET-only path is not a DELETE path
  void apiDelete('/api/availability/settings');
  // @ts-expect-error a DELETE-only path is not a POST path
  void apiPost('/api/availability/subscriptions/{channel_type}', {});
}
void compileTimeContract;

describe('apiGet', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('fills path params and serialises query', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ ok: true }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await apiGet('/api/rounds/{round_id}/awards', { pathParams: { round_id: 11277 } });
    expect(fetchMock).toHaveBeenCalledWith('/api/rounds/11277/awards', { signal: undefined });

    await apiGet('/api/stats/session-leaderboard', { query: { limit: 5, session_id: null } });
    expect(fetchMock).toHaveBeenLastCalledWith('/api/stats/session-leaderboard?limit=5', {
      signal: undefined,
    });
  });

  it('apiGetResponse returns the raw Response for file-producing routes', async () => {
    const response = { ok: true, json: () => Promise.reject(new Error('not json')) };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response));
    const res = await apiGetResponse('/api/uploads/{upload_id}/download', {
      pathParams: { upload_id: 'abc' },
    });
    expect(res).toBe(response);
  });

  it('throws ApiError with status and path on non-2xx', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 404 }));
    await expect(apiGet('/api/stats/overview')).rejects.toMatchObject({
      name: 'ApiError',
      status: 404,
    });
    await expect(apiGet('/api/stats/overview')).rejects.toBeInstanceOf(ApiError);
  });
});

describe('apiDelete', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('sends DELETE with the CSRF header and fills path params', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
    vi.stubGlobal('fetch', fetchMock);
    const body = await apiDelete('/api/availability/subscriptions/{channel_type}', {
      pathParams: { channel_type: 'telegram' },
    });
    expect(body).toEqual({ success: true });
    expect(fetchMock).toHaveBeenCalledWith('/api/availability/subscriptions/telegram', {
      method: 'DELETE',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      credentials: 'same-origin',
    });
  });

  it("carries the backend's own detail on a non-2xx", async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false, status: 403, json: () => Promise.resolve({ detail: 'Linked Discord account required' }),
    }));
    await expect(apiDelete('/api/availability/subscriptions/{channel_type}', {
      pathParams: { channel_type: 'signal' },
    })).rejects.toMatchObject({ name: 'ApiError', status: 403, detail: 'Linked Discord account required' });
  });
});

/** A minimal XMLHttpRequest double: records what was sent, lets the test
 *  fire upload progress and the terminal event it chooses. */
class FakeXhr {
  static last: FakeXhr | null = null;
  method = ''; url = ''; headers = new Map<string, string>(); withCredentials = false; responseType = '';
  status = 0; responseText = ''; sent: unknown = null; aborted = false;
  upload = { onprogress: null as null | ((e: { lengthComputable: boolean; loaded: number; total: number }) => void) };
  onload: null | (() => void) = null; onerror: null | (() => void) = null; onabort: null | (() => void) = null;
  constructor() { FakeXhr.last = this; }
  open(method: string, url: string) { this.method = method; this.url = url; }
  setRequestHeader(k: string, v: string) { this.headers.set(k, v); }
  send(body: unknown) { this.sent = body; }
  abort() { this.aborted = true; this.onabort?.(); }
}

describe('apiUploadWithProgress', () => {
  afterEach(() => { vi.unstubAllGlobals(); });

  it('POSTs the form over XHR with the CSRF header, reports progress, resolves the JSON', async () => {
    vi.stubGlobal('XMLHttpRequest', FakeXhr);
    const seen: [number, number][] = [];
    const form = new FormData();
    const p = apiUploadWithProgress('/api/uploads', form, { onProgress: (a, b) => { seen.push([a, b]); } });
    const xhr = FakeXhr.last;
    if (!xhr) throw new Error('no XHR was opened');
    expect(xhr.method).toBe('POST');
    expect(xhr.url).toBe('/api/uploads');
    expect(xhr.headers.get('X-Requested-With')).toBe('XMLHttpRequest');
    expect(xhr.withCredentials).toBe(true);
    expect(xhr.sent).toBe(form);
    xhr.upload.onprogress?.({ lengthComputable: true, loaded: 40, total: 80 });
    xhr.status = 200; xhr.responseText = JSON.stringify({ upload_id: 'x' }); xhr.onload?.();
    await expect(p).resolves.toEqual({ upload_id: 'x' });
    expect(seen).toEqual([[40, 80]]);
  });

  it("rejects with ApiError carrying the backend's detail on non-2xx", async () => {
    vi.stubGlobal('XMLHttpRequest', FakeXhr);
    const p = apiUploadWithProgress('/api/uploads', new FormData());
    const xhr = FakeXhr.last;
    if (!xhr) throw new Error('no XHR was opened');
    xhr.status = 413; xhr.responseText = JSON.stringify({ detail: 'Upload too large (9 bytes). Max allowed is 2 bytes' }); xhr.onload?.();
    await expect(p).rejects.toMatchObject({ name: 'ApiError', status: 413, detail: 'Upload too large (9 bytes). Max allowed is 2 bytes' });
  });

  it('an AbortSignal aborts the request and rejects with AbortError', async () => {
    vi.stubGlobal('XMLHttpRequest', FakeXhr);
    const ctl = new AbortController();
    const p = apiUploadWithProgress('/api/uploads', new FormData(), { signal: ctl.signal });
    ctl.abort();
    await expect(p).rejects.toMatchObject({ name: 'AbortError' });
    expect(FakeXhr.last?.aborted).toBe(true);
  });
});
