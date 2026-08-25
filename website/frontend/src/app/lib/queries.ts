import { QueryClient, useQuery } from '@tanstack/react-query';
import { apiGet } from './api';
import type {
  BuildInfo, LiveState, QuickLeaders, SessionSummary, StatsOverview,
  StorytellingCompleteness, SystemOverview, VoiceCurrent,
} from './types';

/**
 * React Query owns caching in the standalone app (docs/design/06 §4c — the
 * legacy client's module-level Map is a leak in a long-lived SPA and is not
 * carried over). Stale times follow the tuned values the legacy hooks.ts
 * earned in production: live surfaces every 30 s, aggregates 5 min.
 */
export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      // refetchOnWindowFocus stays ON: with staleTime as the gate it fires
      // only when the tab returns after data went stale — without it the
      // non-live sections (overview, sessions, leaders) would never update
      // on a long-mounted page while the live panel keeps polling (Codex
      // on #806, wave 3).
      queries: { staleTime: 5 * 60_000, retry: 1 },
    },
  });
}

const LIVE = { staleTime: 30_000, refetchInterval: 30_000 } as const;

export function useLiveState() {
  return useQuery({
    queryKey: ['live-state'],
    queryFn: () => apiGet('/api/live/state') as Promise<LiveState>,
    ...LIVE,
  });
}

export function useVoiceCurrent() {
  return useQuery({
    queryKey: ['voice-current'],
    queryFn: () => apiGet('/api/voice-activity/current') as Promise<VoiceCurrent>,
    ...LIVE,
  });
}

export function useOverview() {
  return useQuery({
    queryKey: ['stats-overview'],
    queryFn: () => apiGet('/api/stats/overview') as Promise<StatsOverview>,
  });
}

export function useSessions(limit = 6) {
  return useQuery({
    queryKey: ['sessions', limit],
    queryFn: () => apiGet('/api/sessions', { query: { limit } }) as Promise<SessionSummary[]>,
  });
}

export function useQuickLeaders() {
  return useQuery({
    queryKey: ['quick-leaders'],
    queryFn: () => apiGet('/api/stats/quick-leaders') as Promise<QuickLeaders>,
  });
}

/**
 * A status page must never read from a cache — legacy system.js carried
 * that rule through two layers and it holds here: staleTime 0 defeats React
 * Query's memory, cache 'no-store' defeats the browser's, and the 30 s
 * interval is the page's acceptance test (a stage going bad shows up
 * without a manual reload).
 */
export function useSystemOverview() {
  return useQuery({
    queryKey: ['system-overview'],
    queryFn: () => apiGet('/api/system/overview', { cache: 'no-store' }) as Promise<SystemOverview>,
    staleTime: 0,
    refetchInterval: 30_000,
    refetchOnMount: 'always',
  });
}

/** The endpoint 422s without a scope ("One of gaming_session_id or
 * session_date is required" — measured live; the spec's `required: false`
 * on both params only means EITHER may be omitted, not both). The caller
 * supplies the date; until it has one the query stays disabled. Note
 * session_dates[] in the response is the dates the CHOSEN session touches
 * (midnight crossover), not a picker list. */
export type DiagScope =
  | { gaming_session_id: number }
  | { session_date: string };

export function useStorytellingCompleteness(scope: DiagScope | null) {
  return useQuery({
    queryKey: ['storytelling-completeness', scope],
    enabled: scope !== null,
    queryFn: () =>
      apiGet('/api/diagnostics/storytelling-completeness', {
        query: scope ?? {},
      }) as Promise<StorytellingCompleteness>,
  });
}

/** /api/build is deliberately outside the OpenAPI contract
 * (include_in_schema=False) — a raw fetch, typed by the hand-recorded
 * fixture, is the honest shape here. */
export function useBuildInfo() {
  return useQuery({
    queryKey: ['build-info'],
    queryFn: async (): Promise<BuildInfo> => {
      const res = await fetch('/api/build', { cache: 'no-store' });
      if (!res.ok) throw new Error(`API ${res.status}: /api/build`);
      return res.json() as Promise<BuildInfo>;
    },
    // Identity, not an aggregate: after a backend restart the five-minute
    // staleTime would keep showing the PREVIOUS process's revision (Codex
    // on #809) — the whole point of /api/build is to never do that.
    staleTime: 0,
    refetchOnMount: 'always',
  });
}
