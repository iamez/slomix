import { QueryClient, useQuery } from '@tanstack/react-query';
import { apiGet } from './api';
import type {
  ActivityCalendar, AvailabilityOverview, BuildInfo, ChallengeCurrent,
  LastSession, LiveState, LiveStatus, MatchRow, QuickLeaders, SeasonCurrent,
  SeasonLeaders, SeasonSummary, SessionSummary, SkillMovers, StatsOverview,
  StatsTrends, StorytellingCompleteness, SystemOverview, TonightStatus,
  VoiceCurrent,
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


/* ---------- phase 2: home + sessions core ---------- */

/** Legacy polls this at 60/300 s while home is visible; one endpoint carries
 * both the game-server line and the voice line of the top band. */
export function useLiveStatus() {
  return useQuery({
    queryKey: ['live-status'],
    queryFn: () => apiGet('/api/live-status', { cache: 'no-store' }) as Promise<LiveStatus>,
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}

export function useLastSession() {
  return useQuery({
    queryKey: ['last-session'],
    queryFn: () => apiGet('/api/stats/last-session') as Promise<LastSession>,
  });
}

export function useTrends(days: number) {
  return useQuery({
    queryKey: ['trends', days],
    queryFn: () => apiGet('/api/stats/trends', { query: { days } }) as Promise<StatsTrends>,
  });
}

export function useSeasonCurrent() {
  return useQuery({
    queryKey: ['season-current'],
    queryFn: () => apiGet('/api/seasons/current') as Promise<SeasonCurrent>,
  });
}

export function useSeasonSummary() {
  return useQuery({
    queryKey: ['season-summary'],
    queryFn: () => apiGet('/api/seasons/current/summary') as Promise<SeasonSummary>,
  });
}

export function useSeasonLeaders() {
  return useQuery({
    queryKey: ['season-leaders'],
    queryFn: () => apiGet('/api/seasons/current/leaders') as Promise<SeasonLeaders>,
  });
}

export function useRecentMatches(limit = 5) {
  return useQuery({
    queryKey: ['recent-matches', limit],
    queryFn: () => apiGet('/api/stats/matches', { query: { limit } }) as Promise<MatchRow[]>,
  });
}

export function useAvailabilityOverview() {
  return useQuery({
    queryKey: ['availability-overview'],
    queryFn: () => apiGet('/api/availability') as Promise<AvailabilityOverview>,
  });
}

export function useSkillMovers() {
  return useQuery({
    queryKey: ['skill-movers'],
    queryFn: () => apiGet('/api/skill/movers') as Promise<SkillMovers>,
  });
}

export function useChallengeCurrent() {
  return useQuery({
    queryKey: ['challenge-current'],
    queryFn: () => apiGet('/api/challenges/current') as Promise<ChallengeCurrent>,
  });
}

/** no-store like legacy: an active evening must appear without a reload. */
export function useTonight() {
  return useQuery({
    queryKey: ['tonight'],
    queryFn: () => apiGet('/api/stats/tonight', { cache: 'no-store' }) as Promise<TonightStatus>,
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}

export function useActivityCalendar(days = 90) {
  return useQuery({
    queryKey: ['activity-calendar', days],
    queryFn: () => apiGet('/api/stats/activity-calendar', { query: { days } }) as Promise<ActivityCalendar>,
  });
}
