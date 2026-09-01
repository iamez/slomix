import { QueryClient, useQuery } from '@tanstack/react-query';
import type { paths } from '../../api/generated/openapi.d';
import { ApiError, apiGet } from './api';
import type {
  AdjustedLifetime,
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
  HeadToHead,
  StoryBestLives,
  StoryBoxScore,
  StoryKillImpact,
  StoryKillMatrix,
  StoryKisDetails,
  StoryKisFormula,
  StoryMomentumSession,
  StoryMovement,
  StoryPwcFormula,
  StoryUselessDefense,
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
  CompositeStats,
  LiveSession,
  PlayerIdentity,
  PlayerMatchRound,
  CarrierEvents,
  CarrierKills,
  CarrierReturns,
  CompClutch,
  CompFirstBlood,
  CompManAdvantage,
  CompPersonalBests,
  CompSideSplits,
  CompStagger,
  PlayerJourney,
  ProxAimLock,
  ProxClasses,
  ProxCohesion,
  ProxCombatPositions,
  ProxCrossfireAngles,
  ProxFocusFire,
  ProximityLeaderboard,
  ProxLuaTrades,
  ProxPushes,
  ProxQuality,
  ProxReactions,
  ProxScopes,
  ProxRevives,
  ConstructionEvents,
  EscortCredits,
  ObjectiveFocus,
  ObjectiveRuns,
  ProxPlayers,
  ProxSpawnTiming,
  ProxSupportSummary,
  PushHeatmap,
  V7Status,
  VehicleProgress,
  WaveCycles,
  RecentPrediction,
  SessionLeaderRow,
  SkillPlayer,
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
      queries: {
        staleTime: 5 * 60_000,
        // Retry only what a second ask could answer differently. A 4xx is a
        // considered answer: asking again cannot change it, and it delays
        // the page's honest "unavailable" by a round trip. On the
        // rate-limited routes it is actively harmful — the storytelling
        // endpoints allow 10 requests a minute EACH, the story page issues
        // thirteen per session, and retrying a 429 doubles precisely the
        // traffic that caused it. 5xx and network failures keep their retry.
        retry: (failureCount: number, error: Error) => {
          if (error instanceof ApiError && error.status < 500) return false;
          return failureCount < 1;
        },
      },
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

export function useSessions(limit = 6, enabled = true) {
  return useQuery({
    queryKey: ['sessions', limit],
    enabled,
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

/** The four windows the weapon endpoints accept, taken FROM THE SCHEMA rather
 * than retyped here.
 *
 * The backend used to take `period` as a bare string and let anything it did
 * not recognise fall through to all-time — so `period=nonsense` answered 200
 * with all-time numbers and echoed the value back as though it had been
 * honoured. It is now a closed set in Python, which reaches the generated
 * types through `openapi.json`; deriving the alias here keeps that ONE fact in
 * ONE place. A hand-written copy would be a second place to forget. */
export type WeaponPeriod = NonNullable<
  NonNullable<paths['/api/stats/weapons']['get']['parameters']['query']>['period']
>;

export function useWeapons(period: WeaponPeriod) {
  return useQuery({
    queryKey: ['weapons', period],
    queryFn: () =>
      apiGet('/api/stats/weapons', { query: { limit: 200, period } }) as Promise<WeaponRow[]>,
  });
}

export function useWeaponsHof(period: WeaponPeriod) {
  return useQuery({
    queryKey: ['weapons-hof', period],
    queryFn: () =>
      apiGet('/api/stats/weapons/hall-of-fame', { query: { period } }) as Promise<WeaponsHallOfFame>,
  });
}

/** by_player FIXED (underscore): the legacy 404-fallback to by-player is
 * not carried — one path, one truth. */
export function useWeaponsByPlayer(period: WeaponPeriod) {
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

/** The duel between two named players: kills each way, the weapons each
 *  used on the other, and the per-map split. Only fetched once BOTH ids are
 *  known — the endpoint 400s on anything shorter than 8 characters, so a
 *  half-typed pair would spend a request on a guaranteed error. */
export function useHeadToHead(guid1: string | null, guid2: string | null) {
  return useQuery({
    queryKey: ['rivalry-h2h', guid1, guid2],
    enabled: (guid1?.length ?? 0) >= 8 && (guid2?.length ?? 0) >= 8,
    queryFn: () =>
      apiGet('/api/rivalries/h2h/{guid1}/{guid2}', {
        pathParams: { guid1: guid1!, guid2: guid2! },
      }) as Promise<HeadToHead>,
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
/** The pool-adjusted lifetime board. Gated behind a toggle like SSR, and for
 *  a sharper reason than tidiness: it recomputes an SRS iteration server-side
 *  and measured 1.0 s cold, ten times the rest of this page. */
export function useAdjustedLifetime(enabled: boolean) {
  return useQuery({
    queryKey: ['skill-adjusted-lifetime'],
    enabled,
    queryFn: () => apiGet('/api/skill/adjusted-lifetime') as Promise<AdjustedLifetime>,
    staleTime: 5 * 60 * 1000,
  });
}

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
  | '/api/storytelling/player-narratives'
  | '/api/storytelling/momentum-session'
  | '/api/storytelling/kill-matrix'
  | '/api/storytelling/movement'
  | '/api/storytelling/useless-defense-deaths'
  | '/api/storytelling/best-lives';

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

export function useStoryMomentumSession(gsid: number) {
  return useQuery(storyQuery<StoryMomentumSession>('story-momentum-session', '/api/storytelling/momentum-session', gsid));
}

export function useStoryKillMatrix(gsid: number) {
  return useQuery(storyQuery<StoryKillMatrix>('story-kill-matrix', '/api/storytelling/kill-matrix', gsid));
}

export function useStoryMovement(gsid: number) {
  return useQuery(storyQuery<StoryMovement>('story-movement', '/api/storytelling/movement', gsid));
}

export function useStoryUselessDefense(gsid: number) {
  return useQuery(storyQuery<StoryUselessDefense>('story-useless-defense', '/api/storytelling/useless-defense-deaths', gsid));
}

export function useStoryBestLives(gsid: number, limit = 5) {
  return useQuery(storyQuery<StoryBestLives>('story-best-lives', '/api/storytelling/best-lives', gsid, { limit }));
}

/** The two formula endpoints take no scope and do not change between
 *  sessions, so they are cached for as long as the tab lives rather than per
 *  session — the legacy page kept a module-level cache for the same reason
 *  (`story.js:_kisFormulaCache`). `enabled` keeps them unfetched until a
 *  reader actually opens the disclosure. */
export function useStoryKisFormula(enabled = true) {
  return useQuery({
    queryKey: ['story-kis-formula'],
    queryFn: () => apiGet('/api/storytelling/formula') as Promise<StoryKisFormula>,
    staleTime: Infinity,
    enabled,
  });
}

export function useStoryPwcFormula(enabled = true) {
  return useQuery({
    queryKey: ['story-pwc-formula'],
    queryFn: () => apiGet('/api/storytelling/win-contribution/formula') as Promise<StoryPwcFormula>,
    staleTime: Infinity,
    enabled,
  });
}

/** Per-kill breakdown for ONE player, fetched only once a reader opens a row:
 *  the response carries one object per kill (205 of them for the top player
 *  of session 150), which is the right size for a disclosure and the wrong
 *  size for a page load. */
export function useStoryKisDetails(gsid: number, playerGuid: string | null) {
  return useQuery({
    queryKey: ['story-kis-details', gsid, playerGuid],
    queryFn: () =>
      apiGet('/api/storytelling/kill-impact/details', {
        query: { gaming_session_id: gsid, player_guid: playerGuid ?? '' },
      }) as Promise<StoryKisDetails>,
    enabled: playerGuid !== null,
  });
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


// ---------------------------------------------------------------------------
// The backwards-debt eight (docs/design plan §2a): hooks for paths only the
// legacy frontend called until now.

/** Rounds in the LAST 30 MINUTES — a stricter liveness than /api/stats/tonight
 *  (which answers "was there anything today"). no-store for the same reason
 *  as useTonight: an evening in progress must appear without a reload. */
export function useLiveSession() {
  return useQuery({
    queryKey: ['live-session'],
    queryFn: () => apiGet('/api/stats/live-session', { cache: 'no-store' }) as Promise<LiveSession>,
    refetchInterval: 60 * 1000,
  });
}

/** Published match predictions only (shadow program AUD-006) — the dev
 *  database has zero published rows, so [] is this hook's normal answer,
 *  not its failure. */
export function useRecentPredictions(limit: number) {
  return useQuery({
    queryKey: ['predictions-recent', limit],
    queryFn: () =>
      apiGet('/api/predictions/recent', { query: { limit } }) as Promise<RecentPrediction[]>,
  });
}

/** Top DPM rows of one session (or the latest, when sessionId is null —
 *  the endpoint's own default; the page passes the id so the claim is
 *  scoped, never "whatever was latest at fetch time"). */
export function useSessionLeaderboard(sessionId: number | null, limit: number) {
  return useQuery({
    queryKey: ['session-leaderboard', sessionId, limit],
    enabled: sessionId != null,
    queryFn: () =>
      apiGet('/api/stats/session-leaderboard', {
        query: { session_id: sessionId!, limit },
      }) as Promise<SessionLeaderRow[]>,
  });
}

/** One player's weapons within ONE session — the hyphen spelling, on
 *  purpose: this is the session-scoped call legacy session-detail.js made,
 *  and both spellings are one handler since #848. WeaponsPage keeps the
 *  underscore for its period-scoped grid; neither is a fallback of the
 *  other. */
export function useSessionPlayerWeapons(sessionId: number | null, playerGuid: string | null) {
  return useQuery({
    queryKey: ['session-player-weapons', sessionId, playerGuid],
    enabled: sessionId != null && !!playerGuid,
    queryFn: () =>
      apiGet('/api/stats/weapons/by-player', {
        query: {
          period: 'session',
          gaming_session_id: sessionId!,
          player_guid: playerGuid!,
          player_limit: 1,
          weapon_limit: 8,
        },
      }) as Promise<WeaponsByPlayer>,
  });
}

/** The composite five (tir/ci/kpi/sds/cp) with #848's coverage block —
 *  the first page anywhere to RENDER unmeasured_metrics instead of
 *  presenting an unmeasured zero as a score. */
export function useComposite(sessionId: number | null, sessionDate: string | null) {
  return useQuery({
    queryKey: ['skill-composite', sessionId, sessionDate],
    enabled: sessionId != null || sessionDate != null,
    queryFn: () =>
      apiGet('/api/skill/composite', {
        query: sessionId != null ? { gaming_session_id: sessionId } : { session_date: sessionDate! },
      }) as Promise<CompositeStats>,
  });
}

/** ET Rating v2.1 for one player — 200-with-status: "not rated yet (need
 *  5+ rounds)" arrives as {status:'error'}, which the panel renders as a
 *  fact about the player, not as a failure. */
export function useSkillPlayer(identifier: string | null) {
  return useQuery({
    queryKey: ['skill-player', identifier],
    enabled: !!identifier,
    queryFn: () =>
      apiGet('/api/skill/player/{identifier}', {
        pathParams: { identifier: identifier! },
      }) as Promise<SkillPlayer>,
  });
}

/** The identity card: aliases, Discord link, sick-leave attribution,
 *  achievement milestones. 404 on an unknown player — a real one. */
export function usePlayerIdentity(identifier: string | null) {
  return useQuery({
    queryKey: ['player-identity', identifier],
    enabled: !!identifier,
    queryFn: () =>
      apiGet('/api/stats/player/{player_name}', {
        pathParams: { player_name: identifier! },
      }) as Promise<PlayerIdentity>,
  });
}

/** Round-level recent rows, richer than the profile's recent_matches:
 *  gibs, damage received, headshot kills, revives. */
export function usePlayerMatchRounds(identifier: string | null, limit: number) {
  return useQuery({
    queryKey: ['player-match-rounds', identifier, limit],
    enabled: !!identifier,
    queryFn: () =>
      apiGet('/api/player/{player_name}/matches', {
        pathParams: { player_name: identifier! },
        query: { limit },
      }) as Promise<PlayerMatchRound[]>,
  });
}

// ---------------------------------------------------------------------------
// Phase 5 — proximity.

/** One of the nine leaderboard categories over a rolling window. Measured
 *  cold on 31. 8.: 20-500 ms per category at range_days=30 — this endpoint
 *  is NOT the /proximity/players backbone and needs no scope to be safe,
 *  but the range still ships with every call so the first paint is never
 *  an unbounded query. */
export function useProximityLeaderboard(category: string, rangeDays: number) {
  return useQuery({
    queryKey: ['proximity-leaderboard', category, rangeDays],
    queryFn: () =>
      apiGet('/api/proximity/leaderboards', {
        query: { category, range_days: rangeDays, limit: 10 },
      }) as Promise<ProximityLeaderboard>,
    staleTime: 5 * 60 * 1000,
  });
}


// ---------------------------------------------------------------------------
// Phase 5, slice 2 — the instruments. One generic hook, thirteen paths:
// every one takes the same optional session_date scope (the endpoint falls
// back to a 30-day window without it — measured up to 1.9 s cold, which is
// why the page defaults to a DATE and offers the window as an explicit
// choice, never as the first paint).

function useProxInstrument<T>(path: ProxInstrumentPath, sessionDate: string | null) {
  return useQuery({
    queryKey: ['prox-instrument', path, sessionDate],
    queryFn: () =>
      apiGet(path, {
        query: sessionDate != null ? { session_date: sessionDate } : {},
      }) as Promise<T>,
    staleTime: 5 * 60 * 1000,
  });
}

type ProxInstrumentPath =
  | '/api/proximity/quality'
  | '/api/proximity/spawn-timing'
  | '/api/proximity/aim-lock'
  | '/api/proximity/cohesion'
  | '/api/proximity/crossfire-angles'
  | '/api/proximity/pushes'
  | '/api/proximity/lua-trades'
  | '/api/proximity/revives'
  | '/api/proximity/focus-fire'
  | '/api/proximity/support-summary'
  | '/api/proximity/combat-position-stats'
  | '/api/proximity/classes'
  | '/api/proximity/reactions';

export const useProxQuality = (d: string | null) => useProxInstrument<ProxQuality>('/api/proximity/quality', d);
export const useProxSpawnTiming = (d: string | null) => useProxInstrument<ProxSpawnTiming>('/api/proximity/spawn-timing', d);
export const useProxAimLock = (d: string | null) => useProxInstrument<ProxAimLock>('/api/proximity/aim-lock', d);
export const useProxCohesion = (d: string | null) => useProxInstrument<ProxCohesion>('/api/proximity/cohesion', d);
export const useProxCrossfireAngles = (d: string | null) => useProxInstrument<ProxCrossfireAngles>('/api/proximity/crossfire-angles', d);
export const useProxPushes = (d: string | null) => useProxInstrument<ProxPushes>('/api/proximity/pushes', d);
export const useProxLuaTrades = (d: string | null) => useProxInstrument<ProxLuaTrades>('/api/proximity/lua-trades', d);
export const useProxRevives = (d: string | null) => useProxInstrument<ProxRevives>('/api/proximity/revives', d);
export const useProxFocusFire = (d: string | null) => useProxInstrument<ProxFocusFire>('/api/proximity/focus-fire', d);
export const useProxSupportSummary = (d: string | null) => useProxInstrument<ProxSupportSummary>('/api/proximity/support-summary', d);
export const useProxCombatPositions = (d: string | null) => useProxInstrument<ProxCombatPositions>('/api/proximity/combat-position-stats', d);
export const useProxClasses = (d: string | null) => useProxInstrument<ProxClasses>('/api/proximity/classes', d);
export const useProxReactions = (d: string | null) => useProxInstrument<ProxReactions>('/api/proximity/reactions', d);


/** The dates where the proximity tracker actually captured data — the
 *  instrument chips' only honest source (the sessions list names parsed
 *  evenings, and an evening can exist with no telemetry). */
export function useProxScopes() {
  return useQuery({
    queryKey: ['prox-scopes'],
    queryFn: () => apiGet('/api/proximity/scopes') as Promise<ProxScopes>,
    staleTime: 5 * 60 * 1000,
  });
}


// Phase 5, slice 3 — the competitive section (same scope contract as the
// instruments: a date or the explicit window, never an implicit unscoped
// first paint).

type CompPath =
  | '/api/proximity/competitive/stagger'
  | '/api/proximity/competitive/first-blood'
  | '/api/proximity/competitive/personal-bests'
  | '/api/proximity/competitive/man-advantage'
  | '/api/proximity/competitive/clutch'
  | '/api/proximity/competitive/side-splits';

function useCompetitive<T>(path: CompPath, sessionDate: string | null) {
  return useQuery({
    queryKey: ['prox-competitive', path, sessionDate],
    queryFn: () =>
      apiGet(path, {
        query: sessionDate != null ? { session_date: sessionDate } : {},
      }) as Promise<T>,
    staleTime: 5 * 60 * 1000,
  });
}

export const useCompStagger = (d: string | null) => useCompetitive<CompStagger>('/api/proximity/competitive/stagger', d);
export const useCompFirstBlood = (d: string | null) => useCompetitive<CompFirstBlood>('/api/proximity/competitive/first-blood', d);
export const useCompPersonalBests = (d: string | null) => useCompetitive<CompPersonalBests>('/api/proximity/competitive/personal-bests', d);
export const useCompManAdvantage = (d: string | null) => useCompetitive<CompManAdvantage>('/api/proximity/competitive/man-advantage', d);
export const useCompClutch = (d: string | null) => useCompetitive<CompClutch>('/api/proximity/competitive/clutch', d);
export const useCompSideSplits = (d: string | null) => useCompetitive<CompSideSplits>('/api/proximity/competitive/side-splits', d);

/** The v7 capture roadmap — which Lua capabilities are live and how many
 *  rows each has produced. Global, no scope. */
export function useV7Status() {
  return useQuery({
    queryKey: ['prox-v7-status'],
    queryFn: () => apiGet('/api/proximity/v7-status') as Promise<V7Status>,
    staleTime: 5 * 60 * 1000,
  });
}


// Phase 5, slice 4 — carrier and objective intel, same scope contract.

type IntelPath =
  | '/api/proximity/carrier-events'
  | '/api/proximity/carrier-kills'
  | '/api/proximity/carrier-returns'
  | '/api/proximity/vehicle-progress'
  | '/api/proximity/escort-credits'
  | '/api/proximity/construction-events'
  | '/api/proximity/objective-runs'
  | '/api/proximity/objective-focus';

function useIntel<T>(path: IntelPath, sessionDate: string | null) {
  return useQuery({
    queryKey: ['prox-intel', path, sessionDate],
    queryFn: () =>
      apiGet(path, {
        query: sessionDate != null ? { session_date: sessionDate } : {},
      }) as Promise<T>,
    staleTime: 5 * 60 * 1000,
  });
}

export const useCarrierEvents = (d: string | null) => useIntel<CarrierEvents>('/api/proximity/carrier-events', d);
export const useCarrierKills = (d: string | null) => useIntel<CarrierKills>('/api/proximity/carrier-kills', d);
export const useCarrierReturns = (d: string | null) => useIntel<CarrierReturns>('/api/proximity/carrier-returns', d);
export const useVehicleProgress = (d: string | null) => useIntel<VehicleProgress>('/api/proximity/vehicle-progress', d);
export const useEscortCredits = (d: string | null) => useIntel<EscortCredits>('/api/proximity/escort-credits', d);
export const useConstructionEvents = (d: string | null) => useIntel<ConstructionEvents>('/api/proximity/construction-events', d);
export const useObjectiveRuns = (d: string | null) => useIntel<ObjectiveRuns>('/api/proximity/objective-runs', d);
export const useObjectiveFocus = (d: string | null) => useIntel<ObjectiveFocus>('/api/proximity/objective-focus', d);


// Phase 5, slice 5 — the round scope and its canvases. Every hook here is
// gated on the scope pieces its endpoint REQUIRES (the 422 is the wire
// demanding a scope, and the picker makes it unreachable).

/** The backbone, and the reason the scope discipline exists: measured
 *  12.7 s unbounded against 232 ms with a date. `enabled` gates on the
 *  date — the unbounded form is unreachable from this app. */
export function useProxPlayers(sessionDate: string | null) {
  return useQuery({
    queryKey: ['prox-players', sessionDate],
    enabled: sessionDate != null,
    queryFn: () =>
      apiGet('/api/proximity/players', {
        query: { session_date: sessionDate! },
      }) as Promise<ProxPlayers>,
    staleTime: 5 * 60 * 1000,
  });
}

/** round_start_unix travels with the selection: the same map is played
 *  more than once on one date (the recorded scopes fixture holds three
 *  distinct te_escape2 r1s), and date+map+number alone would silently
 *  merge them (Codex on #867, P1). */
export function usePlayerJourney(sessionDate: string | null, mapName: string | null, roundNumber: number | null, roundStartUnix: number | null, playerGuid: string | null) {
  return useQuery({
    queryKey: ['prox-journey', sessionDate, mapName, roundNumber, roundStartUnix, playerGuid],
    enabled: sessionDate != null && mapName != null && roundNumber != null && !!playerGuid,
    queryFn: () =>
      apiGet('/api/proximity/player-journey', {
        query: {
          session_date: sessionDate!, map_name: mapName!, round_number: roundNumber!,
          ...(roundStartUnix != null ? { round_start_unix: roundStartUnix } : {}),
          player_guid: playerGuid!,
        },
      }) as Promise<PlayerJourney>,
    staleTime: 5 * 60 * 1000,
  });
}

export function usePushHeatmap(sessionDate: string | null, mapName: string | null) {
  return useQuery({
    queryKey: ['prox-heatmap', sessionDate, mapName],
    enabled: sessionDate != null && mapName != null,
    queryFn: () =>
      apiGet('/api/proximity/push-deaths/heatmap', {
        query: { session_date: sessionDate!, map_name: mapName! },
      }) as Promise<PushHeatmap>,
    staleTime: 5 * 60 * 1000,
  });
}

export function useWaveCycles(sessionDate: string | null, mapName: string | null, roundNumber: number | null, roundStartUnix: number | null) {
  return useQuery({
    queryKey: ['prox-wave', sessionDate, mapName, roundNumber, roundStartUnix],
    enabled: sessionDate != null && mapName != null && roundNumber != null,
    queryFn: () =>
      apiGet('/api/proximity/competitive/wave-cycles', {
        query: {
          session_date: sessionDate!, map_name: mapName!, round_number: roundNumber!,
          ...(roundStartUnix != null ? { round_start_unix: roundStartUnix } : {}),
        },
      }) as Promise<WaveCycles>,
    staleTime: 5 * 60 * 1000,
  });
}
