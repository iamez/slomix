import { QueryClient } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';
import { makeQueryClient } from './queries';
import { ApiError } from './api';

/**
 * The retry policy, which is a decision about what to do when the server has
 * already answered.
 *
 * `retry: 1` retried EVERYTHING, and for a 4xx that is the wrong move twice
 * over: the answer will not change on a second ask, and the page's honest
 * "unavailable" arrives a round-trip later than it could. On the
 * rate-limited endpoints it is worse than pointless — the storytelling
 * routes allow 10 requests a minute EACH, the story page issues thirteen
 * per session, and a reader clicking through sessions can reach the limit.
 * Retrying a 429 doubles exactly the traffic that caused it.
 *
 * 5xx and network failures keep their retry: those are the cases where the
 * same question can get a different answer.
 */
describe('query client retry policy', () => {
  const retryOf = (client: QueryClient) =>
    client.getDefaultOptions().queries?.retry;

  it('does not retry an answer the server already gave (4xx)', () => {
    const retry = retryOf(makeQueryClient());
    expect(typeof retry).toBe('function');
    const fn = retry as (count: number, error: Error) => boolean;
    expect(fn(0, new ApiError(404, '/api/x'))).toBe(false);
    expect(fn(0, new ApiError(429, '/api/x'))).toBe(false);
    expect(fn(0, new ApiError(400, '/api/x'))).toBe(false);
  });

  it('retries once when the server broke or the network did', () => {
    const fn = retryOf(makeQueryClient()) as (count: number, error: Error) => boolean;
    expect(fn(0, new ApiError(500, '/api/x'))).toBe(true);
    expect(fn(0, new ApiError(502, '/api/x'))).toBe(true);
    // A TypeError is what fetch throws when the request never reached a
    // server at all — worth one more try, unlike a considered 404.
    expect(fn(0, new TypeError('Failed to fetch'))).toBe(true);
    // …once, not forever.
    expect(fn(1, new ApiError(500, '/api/x'))).toBe(false);
  });
});
