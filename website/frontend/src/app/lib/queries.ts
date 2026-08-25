import { QueryClient, useQuery } from '@tanstack/react-query';
import { apiGet } from './api';
import type { LiveState, QuickLeaders, SessionSummary, StatsOverview, VoiceCurrent } from './types';

/**
 * React Query owns caching in the standalone app (docs/design/06 §4c — the
 * legacy client's module-level Map is a leak in a long-lived SPA and is not
 * carried over). Stale times follow the tuned values the legacy hooks.ts
 * earned in production: live surfaces every 30 s, aggregates 5 min.
 */
export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { staleTime: 5 * 60_000, retry: 1, refetchOnWindowFocus: false },
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
