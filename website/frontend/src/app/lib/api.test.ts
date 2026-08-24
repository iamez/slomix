import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, apiGet, apiGetResponse } from './api';

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
