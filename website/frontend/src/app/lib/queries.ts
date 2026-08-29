import { QueryClient, useQuery } from '@tanstack/react-query';
import { apiGet } from './api';
import type {
  ActivityCalendar,
  AvailabilityOverview,
  AwardsLeaderboard,
  AwardsPage,
  BuildInfo,
  ChallengeCurrent,
  HallOfFame,
  LastSession,
  LeaderboardRow,
  LiveState,
  LiveStatus,
  MapRow,
  MapSegments,
  MapStatsRow,
  MatchRow,
  PlayerProfile,
  PlayerRivalries,
  QuickLeaders,
  RecentRound,
  RivalryLeaderboard,
  StoryBoxScore,
  StoryKillImpact,
  StoryMomentum,
  StoryMoments,
  StoryNarrative,
  StoryPlayerNarratives,
  StoryRoleBoard,
  StoryScopes,
  StorySynergy,
  StoryWinContribution,
  RoundViz,
  SeasonAwards,
  SeasonCurrent,
  SeasonLeaders,
  SeasonSummary,
  SessionLineups,
  SessionRounds,
  SessionDetail,
  SessionGoodNight,
  SessionMvp,
  SessionVerdicts,
  SessionSummary,
  SkillFormula,
  SkillLeaderboard,
  SkillMovers,
  SsrBoard,
  StatsOverview,
  StatsRecords,
  StatsTrends,
  StorytellingCompleteness,
  SystemOverview,
  TonightStatus,
  VoiceCurrent,
  WeaponRow,
  WeaponsByPlayer,
  WeaponsHallOfFame,
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

/** The sections this page renders, named explicitly so adding a panel is a
 * deliberate cost decision rather than a silent one. */
const PROFILE_SECTIONS = [
  'identity', 'skill', 'streaks', 'weapons', 'hit_regions', 'movement',
  'relationships', 'maps', 'recent_matches',
].join(',');

/** The profile is ONE endpoint with sections (players_profile_router): the
 * legacy page fanned out to a dozen calls; `sections=all` is a single
 * request whose parts each declare their own availability. */
export function usePlayerProfile(playerId: string) {
  return useQuery({
    queryKey: ['player-profile', playerId],
    enabled: playerId.length > 0,
    queryFn: () =>
      apiGet('/api/players/{identifier}/profile', {
        pathParams: { identifier: playerId },
        // NOT 'all': `aim` and `advanced` cost a measured 16.9 s and 11.1 s
        // cold (players_profile_router:1156-1170) and this page renders
        // neither — asking for them would make every cold profile wait ~28 s
        // for panels nobody sees.
        query: { sections: PROFILE_SECTIONS },
      }) as Promise<PlayerProfile>,
  });
}

export function useSessionLineups(sessionId: number, enabled: boolean) {
  return useQuery({
    queryKey: ['session-lineups', sessionId],
    queryFn: () =>
      apiGet('/api/stats/session/{gaming_session_id}/lineups', {
        pathParams: { gaming_session_id: sessionId },
      }) as Promise<SessionLineups>,
    enabled,
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


/* ---------- phase 2, batch 2 ---------- */

export function useLeaderboard(stat: string, period: string) {
  return useQuery({
    queryKey: ['leaderboard', stat, period],
    queryFn: () =>
      apiGet('/api/stats/leaderboard', { query: { stat, period, limit: 50 } }) as Promise<LeaderboardRow[]>,
  });
}

export function useRecords(mapName: string | null) {
  return useQuery({
    queryKey: ['records', mapName],
    queryFn: () =>
      apiGet('/api/stats/records', {
        // encodeURIComponent happens in buildQuery — the legacy call sent
        // the raw name (records.js:95).
        // limit=5 is load-bearing: the endpoint DEFAULTS to limit=1, and the
        // record book renders rows.slice(1) as the expanded ranks 2-5 — with
        // the default they would always be empty.
        query: mapName ? { limit: 5, map_name: mapName } : { limit: 5 },
      }) as Promise<StatsRecords>,
  });
}

export function useMaps() {
  return useQuery({
    queryKey: ['maps'],
    queryFn: () => apiGet('/api/stats/maps') as Promise<MapRow[]>,
  });
}

export function useHallOfFame(period: string) {
  return useQuery({
    queryKey: ['hall-of-fame', period],
    queryFn: () =>
      apiGet('/api/hall-of-fame', { query: { period, limit: 50 } }) as Promise<HallOfFame>,
  });
}

export function useSeasonAwards() {
  return useQuery({
    queryKey: ['season-awards'],
    // The spec's shape is /api/seasons/{season_id}/awards; 'current'
    // resolves server-side via SeasonManager (season_awards_router).
    queryFn: () =>
      apiGet('/api/seasons/{season_id}/awards', {
        pathParams: { season_id: 'current' },
      }) as Promise<SeasonAwards>,
  });
}

export function useAwards(page: number, days: number | null, awardType: string | null) {
  return useQuery({
    queryKey: ['awards', page, days, awardType],
    queryFn: () =>
      apiGet('/api/awards', {
        query: {
          limit: 20,
          offset: page * 20,
          ...(days != null ? { days } : {}),
          ...(awardType ? { award_type: awardType } : {}),
        },
      }) as Promise<AwardsPage>,
  });
}

export function useAwardsLeaderboard(days: number | null, awardType: string | null) {
  return useQuery({
    queryKey: ['awards-leaderboard', days, awardType],
    queryFn: () =>
      apiGet('/api/awards/leaderboard', {
        query: {
          limit: 50,
          ...(days != null ? { days } : {}),
          ...(awardType ? { award_type: awardType } : {}),
        },
      }) as Promise<AwardsLeaderboard>,
  });
}


/* ---------- phase 2, batch 3 ---------- */

/** Full map statistics (the maps PAGE view of /api/stats/maps — batch 2's
 * useMaps() reads the same endpoint for the slim dropdown shape). */
export function useMapStats() {
  return useQuery({
    queryKey: ['map-stats'],
    queryFn: () => apiGet('/api/stats/maps') as Promise<MapStatsRow[]>,
  });
}

export function useMapSegments() {
  return useQuery({
    queryKey: ['map-segments'],
    queryFn: () => apiGet('/api/records/maps/segments') as Promise<MapSegments>,
  });
}

export function useWeapons(period: string) {
  return useQuery({
    queryKey: ['weapons', period],
    queryFn: () =>
      apiGet('/api/stats/weapons', { query: { limit: 200, period } }) as Promise<WeaponRow[]>,
  });
}

export function useWeaponsHof(period: string) {
  return useQuery({
    queryKey: ['weapons-hof', period],
    queryFn: () =>
      apiGet('/api/stats/weapons/hall-of-fame', { query: { period } }) as Promise<WeaponsHallOfFame>,
  });
}

/** by_player FIXED (underscore): the legacy 404-fallback to by-player is
 * not carried — one path, one truth. */
export function useWeaponsByPlayer(period: string) {
  return useQuery({
    queryKey: ['weapons-by-player', period],
    queryFn: () =>
      apiGet('/api/stats/weapons/by_player', {
        query: { period, player_limit: 24, weapon_limit: 4 },
      }) as Promise<WeaponsByPlayer>,
  });
}

export function useFormMovers(metric: string) {
  return useQuery({
    queryKey: ['form-movers', metric],
    queryFn: () =>
      apiGet('/api/skill/movers', { query: { full: true, metric } }) as Promise<SkillMovers>,
  });
}

export function useRecentRounds() {
  return useQuery({
    queryKey: ['recent-rounds'],
    queryFn: () => apiGet('/api/rounds/recent', { query: { limit: 50 } }) as Promise<RecentRound[]>,
  });
}

export function useRoundViz(roundId: number | null) {
  return useQuery({
    queryKey: ['round-viz', roundId],
    enabled: roundId != null,
    queryFn: () =>
      apiGet('/api/rounds/{round_id}/viz', {
        pathParams: { round_id: roundId! },
      }) as Promise<RoundViz>,
  });
}

/** Every round of one session, each with its full roster.
 *
 * One call instead of 18 to `/rounds/{id}/viz`. Includes rounds that do not
 * count toward totals (`counts_toward_totals: false`) rather than filtering
 * them — a player who played a cancelled round has to be able to see it.
 */
export function useSessionRounds(sessionId: number | null) {
  return useQuery({
    queryKey: ['session-rounds', sessionId],
    enabled: sessionId != null,
    queryFn: () =>
      apiGet('/api/stats/session/{gaming_session_id}/rounds', {
        pathParams: { gaming_session_id: sessionId! },
      }) as Promise<SessionRounds>,
  });
}

/** The community's rivalry pairs, ordered by how often the two have met. */
export function useRivalryLeaderboard(limit: number) {
  return useQuery({
    queryKey: ['rivalry-leaderboard', limit],
    queryFn: () =>
      apiGet('/api/rivalries/leaderboard', { query: { limit } }) as Promise<RivalryLeaderboard>,
  });
}

/** One player's opponents. Either GUID length works since #834. */
export function usePlayerRivalries(guid: string | null) {
  return useQuery({
    queryKey: ['player-rivalries', guid],
    enabled: !!guid,
    queryFn: () =>
      apiGet('/api/rivalries/player/{guid}', {
        pathParams: { guid: guid! },
      }) as Promise<PlayerRivalries>,
  });
}

/** ET Rating v2.1 — the number the profile shows, with its components. */
export function useSkillLeaderboard(limit: number) {
  return useQuery({
    queryKey: ['skill-leaderboard', limit],
    queryFn: () =>
      apiGet('/api/skill/leaderboard', { query: { limit } }) as Promise<SkillLeaderboard>,
  });
}

/** The formula itself, so the page can quote it rather than paraphrase it. */
export function useSkillFormula() {
  return useQuery({
    queryKey: ['skill-formula'],
    queryFn: () => apiGet('/api/skill/formula') as Promise<SkillFormula>,
  });
}

/** SSR v0.3 — a second, session-scoped formula, still partially covered.
 *
 * `enabled` is not optional politeness: the endpoint takes a measured 2.4 s,
 * and the panel that shows it starts closed, so an unconditional query spent
 * that on every visit for data nobody had asked to see (Codex on #835). */
export function useSsr(enabled: boolean) {
  return useQuery({
    queryKey: ['skill-ssr'],
    enabled,
    queryFn: () => apiGet('/api/skill/ssr') as Promise<SsrBoard>,
  });
}

// ---------------------------------------------------------------------------
// Smart Stats. Thirteen endpoints, one session key.
//
// Every one is rate-limited to 10/minute on the server and several are slow
// (the role boards read the position tracker), so they share the gsid in
// their key and nothing re-fetches when the picker re-renders. The page
// mounts them together on purpose: they answer different questions about the
// same session, and a reader comparing them needs them to be the same run.
// ---------------------------------------------------------------------------

/** The session picker. gsid, never a date: a session can cross midnight. */
export function useStoryScopes(limit: number) {
  return useQuery({
    queryKey: ['story-scopes', limit],
    queryFn: () =>
      apiGet('/api/storytelling/scopes', { query: { limit } }) as Promise<StoryScopes>,
  });
}

function storyQuery<T>(name: string, path: StoryPath, gsid: number, extra?: Record<string, number>) {
  return {
    queryKey: [name, gsid, extra],
    queryFn: () =>
      apiGet(path, {
        query: { gaming_session_id: gsid, ...extra },
      }) as Promise<T>,
  };
}

/** The paths this module reads. Named so a typo is a compile error rather
 *  than a 404 at runtime — apiGet checks it against the OpenAPI spec. */
type StoryPath =
  | '/api/storytelling/narrative'
  | '/api/storytelling/box-score'
  | '/api/storytelling/moments'
  | '/api/storytelling/momentum'
  | '/api/storytelling/win-contribution'
  | '/api/storytelling/kill-impact'
  | '/api/storytelling/synergy'
  | '/api/storytelling/gravity'
  | '/api/storytelling/space-created'
  | '/api/storytelling/enabler'
  | '/api/storytelling/lurker-profile'
  | '/api/storytelling/player-narratives';

export function useStoryNarrative(gsid: number) {
  return useQuery(storyQuery<StoryNarrative>('story-narrative', '/api/storytelling/narrative', gsid));
}

export function useStoryBoxScore(gsid: number) {
  return useQuery(storyQuery<StoryBoxScore>('story-box-score', '/api/storytelling/box-score', gsid));
}

export function useStoryMoments(gsid: number) {
  return useQuery(storyQuery<StoryMoments>('story-moments', '/api/storytelling/moments', gsid, { limit: 10 }));
}

export function useStoryMomentum(gsid: number) {
  return useQuery(storyQuery<StoryMomentum>('story-momentum', '/api/storytelling/momentum', gsid));
}

export function useStoryWinContribution(gsid: number) {
  return useQuery(storyQuery<StoryWinContribution>('story-pwc', '/api/storytelling/win-contribution', gsid));
}

export function useStoryKillImpact(gsid: number) {
  return useQuery(storyQuery<StoryKillImpact>('story-kis', '/api/storytelling/kill-impact', gsid, { limit: 50 }));
}

export function useStorySynergy(gsid: number) {
  return useQuery(storyQuery<StorySynergy>('story-synergy', '/api/storytelling/synergy', gsid));
}

export function useStoryGravity(gsid: number) {
  return useQuery(storyQuery<StoryRoleBoard>('story-gravity', '/api/storytelling/gravity', gsid));
}

export function useStorySpace(gsid: number) {
  return useQuery(storyQuery<StoryRoleBoard>('story-space', '/api/storytelling/space-created', gsid));
}

export function useStoryEnabler(gsid: number) {
  return useQuery(storyQuery<StoryRoleBoard>('story-enabler', '/api/storytelling/enabler', gsid));
}

export function useStoryLurker(gsid: number) {
  return useQuery(storyQuery<StoryRoleBoard>('story-lurker', '/api/storytelling/lurker-profile', gsid));
}

export function useStoryPlayerNarratives(gsid: number) {
  return useQuery(storyQuery<StoryPlayerNarratives>('story-player-narratives', '/api/storytelling/player-narratives', gsid));
}

// ---------------------------------------------------------------------------
// Phase 4 — session detail. `useSessionRounds` above is shared with the
// /rounds page; these four are the panels around it.
// ---------------------------------------------------------------------------

/** Everything the session totals are built from: matches, per-player totals,
 *  stopwatch scoring and the team matrix. One 39 KB response rather than the
 *  legacy page's five calls. */
export function useSessionDetail(sessionId: number | null) {
  return useQuery({
    queryKey: ['session-detail', sessionId],
    enabled: sessionId != null,
    queryFn: () =>
      apiGet('/api/stats/session/{gaming_session_id}/detail', {
        pathParams: { gaming_session_id: sessionId! },
      }) as Promise<SessionDetail>,
  });
}

export function useSessionGoodNight(sessionId: number | null) {
  return useQuery({
    queryKey: ['session-good-night', sessionId],
    enabled: sessionId != null,
    queryFn: () =>
      apiGet('/api/stats/session/{gaming_session_id}/good-night', {
        pathParams: { gaming_session_id: sessionId! },
      }) as Promise<SessionGoodNight>,
  });
}

export function useSessionVerdicts(sessionId: number | null) {
  return useQuery({
    queryKey: ['session-verdicts', sessionId],
    enabled: sessionId != null,
    queryFn: () =>
      apiGet('/api/stats/session/{gaming_session_id}/verdicts', {
        pathParams: { gaming_session_id: sessionId! },
      }) as Promise<SessionVerdicts>,
  });
}

/** Peer votes, not a computed rating — see the type's note. */
export function useSessionMvp(sessionId: number | null) {
  return useQuery({
    queryKey: ['session-mvp', sessionId],
    enabled: sessionId != null,
    queryFn: () =>
      apiGet('/api/stats/session/{gaming_session_id}/mvp', {
        pathParams: { gaming_session_id: sessionId! },
      }) as Promise<SessionMvp>,
  });
}
