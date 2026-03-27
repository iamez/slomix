import { useQuery } from '@tanstack/react-query';
import { api } from './client';
import type { ProximityScope } from './types';

// Home / Overview
export const useOverview = () =>
  useQuery({
    queryKey: ['overview'],
    queryFn: api.getOverview,
    staleTime: 60_000,
  });

export const useLiveStatus = () =>
  useQuery({
    queryKey: ['live-status'],
    queryFn: api.getLiveStatus,
    staleTime: 30_000,
    refetchInterval: 60_000,
  });

export const useTrends = (days = 14) =>
  useQuery({
    queryKey: ['trends', days],
    queryFn: () => api.getTrends(days),
    staleTime: 120_000,
  });

export const useSeason = () =>
  useQuery({
    queryKey: ['season'],
    queryFn: api.getSeason,
    staleTime: 300_000,
  });

// Records
export const useRecords = (mapName?: string) =>
  useQuery({
    queryKey: ['records', mapName],
    queryFn: () => api.getRecords(mapName),
    staleTime: 60_000,
  });

export const useMaps = () =>
  useQuery({
    queryKey: ['maps'],
    queryFn: api.getMaps,
    staleTime: 300_000,
  });

// Leaderboard
export const useLeaderboard = (stat = 'dpm', period = '30d', limit = 50) =>
  useQuery({
    queryKey: ['leaderboard', stat, period, limit],
    queryFn: () => api.getLeaderboard(stat, period, limit),
    staleTime: 60_000,
  });

export const useQuickLeaders = () =>
  useQuery({
    queryKey: ['quick-leaders'],
    queryFn: api.getQuickLeaders,
    staleTime: 60_000,
  });

// Maps
export const useMapStats = () =>
  useQuery({
    queryKey: ['map-stats'],
    queryFn: api.getMapStats,
    staleTime: 120_000,
  });

// Hall of Fame
export const useHallOfFame = (period = 'all_time', limit = 10) =>
  useQuery({
    queryKey: ['hall-of-fame', period, limit],
    queryFn: () => api.getHallOfFame(period, limit),
    staleTime: 120_000,
  });

// Awards
export const useAwardsLeaderboard = (params?: { days?: string; award_type?: string; limit?: number }) =>
  useQuery({
    queryKey: ['awards-leaderboard', params],
    queryFn: () => api.getAwardsLeaderboard(params),
    staleTime: 60_000,
  });

export const useAwards = (params?: { days?: string; award_type?: string; limit?: number; offset?: number }) =>
  useQuery({
    queryKey: ['awards', params],
    queryFn: () => api.getAwards(params),
    staleTime: 60_000,
  });

export const usePlayerAwards = (id: string) =>
  useQuery({
    queryKey: ['player-awards', id],
    queryFn: () => api.getPlayerAwards(id),
    enabled: !!id,
    staleTime: 60_000,
  });

// Player Profile
export const usePlayerProfile = (name: string) =>
  useQuery({
    queryKey: ['player-profile', name],
    queryFn: () => api.getPlayerProfile(name),
    enabled: !!name,
    staleTime: 60_000,
  });

export const usePlayerForm = (name: string) =>
  useQuery({
    queryKey: ['player-form', name],
    queryFn: () => api.getPlayerForm(name),
    enabled: !!name,
    staleTime: 120_000,
  });

export const usePlayerRounds = (name: string, limit = 20) =>
  useQuery({
    queryKey: ['player-rounds', name, limit],
    queryFn: () => api.getPlayerRounds(name, limit),
    enabled: !!name,
    staleTime: 60_000,
  });

// Weapons
export const useWeapons = (period = 'all') =>
  useQuery({
    queryKey: ['weapons', period],
    queryFn: () => api.getWeapons(period),
    staleTime: 60_000,
  });

export const useWeaponHoF = (period = 'all') =>
  useQuery({
    queryKey: ['weapon-hof', period],
    queryFn: () => api.getWeaponHoF(period),
    staleTime: 120_000,
  });

export const useWeaponsByPlayer = (
  period = 'all',
  playerGuid?: string | null,
  playerLimit = playerGuid ? 1 : 24,
  weaponLimit = playerGuid ? 8 : 4,
  enabled = true,
  gamingSessionId?: number,
) =>
  useQuery({
    queryKey: ['weapons-by-player', period, playerGuid, playerLimit, weaponLimit, gamingSessionId],
    queryFn: () => api.getWeaponsByPlayer(period, playerLimit, weaponLimit, playerGuid ?? undefined, gamingSessionId),
    staleTime: 60_000,
    enabled: enabled && (playerGuid === undefined || !!playerGuid),
  });

// Round Viz
export const useRecentRounds = (limit = 50) =>
  useQuery({
    queryKey: ['recent-rounds', limit],
    queryFn: () => api.getRecentRounds(limit),
    staleTime: 60_000,
  });

export const useRoundViz = (roundId: number | null) =>
  useQuery({
    queryKey: ['round-viz', roundId],
    queryFn: () => api.getRoundViz(roundId!),
    enabled: roundId !== null && roundId > 0,
    staleTime: 300_000,
  });

export const useRoundPlayerDetails = (roundId: number | null, playerGuid: string | null, enabled = true) =>
  useQuery({
    queryKey: ['round-player-details', roundId, playerGuid],
    queryFn: () => api.getRoundPlayerDetails(roundId!, playerGuid!),
    enabled: enabled && roundId !== null && roundId > 0 && !!playerGuid,
    staleTime: 300_000,
  });

// Session Detail
export const useSessionDetail = (sessionId: number | null) =>
  useQuery({
    queryKey: ['session-detail', sessionId],
    queryFn: () => api.getSessionDetail(sessionId!),
    enabled: sessionId !== null && sessionId > 0,
    staleTime: 60_000,
  });

export const useSessionByDate = (date: string | null) =>
  useQuery({
    queryKey: ['session-by-date', date],
    queryFn: () => api.getSessionByDate(date!),
    enabled: !!date,
    staleTime: 60_000,
  });

export const useSessionGraphs = (date: string | null, sessionId?: number | null, enabled = true) =>
  useQuery({
    queryKey: ['session-graphs', date, sessionId],
    queryFn: () => api.getSessionGraphs(date!, sessionId),
    enabled: enabled && !!date,
    staleTime: 60_000,
  });

export const useProximityTradeSummary = (params?: ProximityScope, enabled = true) =>
  useQuery({
    queryKey: ['proximity-trade-summary', params],
    queryFn: () => api.getProximityTradeSummary(params),
    enabled,
    staleTime: 30_000,
  });

export const useProximityTradeEvents = (params?: ProximityScope, limit = 250, enabled = true) =>
  useQuery({
    queryKey: ['proximity-trade-events', params, limit],
    queryFn: () => api.getProximityTradeEvents(params, limit),
    enabled,
    staleTime: 30_000,
  });

export const useProximityDuos = (params?: ProximityScope, limit = 8, enabled = true) =>
  useQuery({
    queryKey: ['proximity-duos', params, limit],
    queryFn: () => api.getProximityDuos(params, limit),
    enabled,
    staleTime: 30_000,
  });

export const useProximityTeamplay = (params?: ProximityScope, enabled = true) =>
  useQuery({
    queryKey: ['proximity-teamplay', params],
    queryFn: () => api.getProximityTeamplay(params),
    enabled,
    staleTime: 30_000,
  });

export const useProximityMovers = (params?: ProximityScope, limit = 5, enabled = true) =>
  useQuery({
    queryKey: ['proximity-movers', params, limit],
    queryFn: () => api.getProximityMovers(params, limit),
    enabled,
    staleTime: 30_000,
  });

export const useProximityPlayerProfile = (guid: string, rangeDays = 90) =>
  useQuery({
    queryKey: ['proximity-player-profile', guid, rangeDays],
    queryFn: () => api.getProximityPlayerProfile(guid, rangeDays),
    enabled: !!guid,
    staleTime: 60_000,
  });

export const useProximityPlayerRadar = (guid: string, rangeDays = 90) =>
  useQuery({
    queryKey: ['proximity-player-radar', guid, rangeDays],
    queryFn: () => api.getProximityPlayerRadar(guid, rangeDays),
    enabled: !!guid,
    staleTime: 60_000,
  });

export const useProximityRoundTimeline = (roundId: number) =>
  useQuery({
    queryKey: ['proximity-round-timeline', roundId],
    queryFn: () => api.getProximityRoundTimeline(roundId),
    enabled: roundId > 0,
    staleTime: 120_000,
  });

export const useProximityRoundTracks = (roundId: number) =>
  useQuery({
    queryKey: ['proximity-round-tracks', roundId],
    queryFn: () => api.getProximityRoundTracks(roundId),
    enabled: roundId > 0,
    staleTime: 120_000,
  });

export const useProximityRoundTeamComparison = (roundId: number) =>
  useQuery({
    queryKey: ['proximity-round-team-comparison', roundId],
    queryFn: () => api.getProximityRoundTeamComparison(roundId),
    enabled: roundId > 0,
    staleTime: 120_000,
  });

export const useProximityLeaderboards = (category = 'power', rangeDays = 30, limit = 10) =>
  useQuery({
    queryKey: ['proximity-leaderboards', category, rangeDays, limit],
    queryFn: () => api.getProximityLeaderboards(category, rangeDays, limit),
    staleTime: 60_000,
  });

export const useProximitySessionScores = (sessionDate?: string) =>
  useQuery({
    queryKey: ['proximity-session-scores', sessionDate],
    queryFn: () => api.getProximitySessionScores(sessionDate),
    staleTime: 60_000,
  });

export const useProximityWeaponAccuracy = (params?: { player_guid?: string; map_name?: string; limit?: number }) =>
  useQuery({
    queryKey: ['proximity-weapon-accuracy', params],
    queryFn: () => api.getProximityWeaponAccuracy(params),
    staleTime: 60_000,
  });

// VS Stats
export const usePlayerVsStats = (
  guid: string | null,
  scope = 'all',
  sessionId?: number,
  roundId?: number,
  enabled = true,
) =>
  useQuery({
    queryKey: ['player-vs-stats', guid, scope, sessionId, roundId],
    queryFn: () => api.getPlayerVsStats(guid!, scope, sessionId, roundId),
    enabled: enabled && !!guid,
    staleTime: 60_000,
  });

// Skill Rating
export const useSkillLeaderboard = (limit = 50) =>
  useQuery({
    queryKey: ['skill-leaderboard', limit],
    queryFn: () => api.getSkillLeaderboard(limit),
    staleTime: 60_000,
  });

export const useSkillFormula = () =>
  useQuery({
    queryKey: ['skill-formula'],
    queryFn: api.getSkillFormula,
    staleTime: 300_000,
  });

export const useSkillHistory = (identifier: string, rangeDays = 30, sessionDate?: string) =>
  useQuery({
    queryKey: ['skill-history', identifier, rangeDays, sessionDate],
    queryFn: () => api.getSkillHistory(identifier, rangeDays, sessionDate),
    staleTime: 60_000,
    enabled: !!identifier,
  });

// Sessions
export const useSessions = (params?: { limit?: number; offset?: number; search?: string }) =>
  useQuery({
    queryKey: ['sessions', params],
    queryFn: () => api.getSessions(params),
    staleTime: 30_000,
  });

export const useLatestSession = () =>
  useQuery({
    queryKey: ['latest-session'],
    queryFn: async () => {
      const sessions = await api.getSessions({ limit: 1 });
      return sessions[0] ?? null;
    },
    staleTime: 30_000,
  });

// Greatshot
export const useGreatshotDemos = (enabled = true) =>
  useQuery({
    queryKey: ['greatshot-demos'],
    queryFn: api.getGreatshotDemos,
    enabled,
    staleTime: 30_000,
  });

export const useGreatshotDetail = (id: string | null) =>
  useQuery({
    queryKey: ['greatshot-detail', id],
    queryFn: () => api.getGreatshotDetail(id!),
    enabled: !!id,
    staleTime: 30_000,
  });

export const useGreatshotCrossref = (id: string | null, enabled = true) =>
  useQuery({
    queryKey: ['greatshot-crossref', id],
    queryFn: () => api.getGreatshotCrossref(id!),
    enabled: !!id && enabled,
    staleTime: 120_000,
  });

// Uploads
export const useUploads = (params?: { category?: string; tag?: string; search?: string; limit?: number; offset?: number }) =>
  useQuery({
    queryKey: ['uploads', params],
    queryFn: () => api.getUploads(params),
    staleTime: 30_000,
  });

export const useUpload = (id: string | null) =>
  useQuery({
    queryKey: ['upload', id],
    queryFn: () => api.getUpload(id!),
    enabled: !!id,
    staleTime: 60_000,
  });

export const usePopularTags = (limit = 15) =>
  useQuery({
    queryKey: ['popular-tags', limit],
    queryFn: () => api.getPopularTags(limit),
    staleTime: 120_000,
  });

export const useAuthMe = () =>
  useQuery({
    queryKey: ['auth-me'],
    queryFn: api.getAuthMe,
    staleTime: 300_000,
    retry: false,
  });

// Availability
export const useAvailabilityAccess = () =>
  useQuery({
    queryKey: ['availability-access'],
    queryFn: api.getAvailabilityAccess,
    staleTime: 60_000,
  });

export const useAvailabilityRange = (from?: string, to?: string, includeUsers = false) =>
  useQuery({
    queryKey: ['availability-range', from, to, includeUsers],
    queryFn: () => api.getAvailabilityRange(from, to, includeUsers),
    staleTime: 30_000,
    refetchInterval: 45_000,
  });

export const useAvailabilitySettings = (enabled = true) =>
  useQuery({
    queryKey: ['availability-settings'],
    queryFn: api.getAvailabilitySettings,
    enabled,
    staleTime: 120_000,
    retry: false,
  });

export const usePlanningState = (enabled = true) =>
  useQuery({
    queryKey: ['planning-state'],
    queryFn: api.getPlanningState,
    enabled,
    staleTime: 30_000,
    refetchInterval: 45_000,
    retry: false,
  });

// Kill Outcomes (v5.2)
export const useProximityHitRegions = (params?: ProximityScope, weaponId?: number) =>
  useQuery({
    queryKey: ['proximity-hit-regions', params, weaponId],
    queryFn: () => api.getProximityHitRegions(params, weaponId),
    staleTime: 30_000,
  });

export const useProximityHeadshotRates = (params?: ProximityScope) =>
  useQuery({
    queryKey: ['proximity-headshot-rates', params],
    queryFn: () => api.getProximityHeadshotRates(params),
    staleTime: 30_000,
  });

export const useCombatHeatmap = (mapName: string, opts?: { weaponId?: number; perspective?: string; victimClass?: string; team?: string; rangeDays?: number }) =>
  useQuery({
    queryKey: ['combat-heatmap', mapName, opts],
    queryFn: () => api.getCombatHeatmap(mapName, opts),
    enabled: !!mapName,
    staleTime: 30_000,
  });

export const useKillLines = (mapName: string, opts?: { weaponId?: number; attackerGuid?: string; rangeDays?: number; limit?: number }) =>
  useQuery({
    queryKey: ['kill-lines', mapName, opts],
    queryFn: () => api.getKillLines(mapName, opts),
    enabled: !!mapName,
    staleTime: 30_000,
  });

export const useProximityKillOutcomes = (params?: ProximityScope) =>
  useQuery({
    queryKey: ['proximity-kill-outcomes', params],
    queryFn: () => api.getProximityKillOutcomes(params),
    staleTime: 30_000,
  });

export const useProximityKillOutcomePlayerStats = (params?: ProximityScope, playerGuid?: string) =>
  useQuery({
    queryKey: ['proximity-kill-outcome-player-stats', params, playerGuid],
    queryFn: () => api.getProximityKillOutcomePlayerStats(params, playerGuid),
    staleTime: 30_000,
  });

export const useDangerZones = (mapName: string, opts?: { victimClass?: string; rangeDays?: number }) =>
  useQuery({
    queryKey: ['danger-zones', mapName, opts],
    queryFn: () => api.getDangerZones(mapName, opts),
    enabled: !!mapName,
    staleTime: 30_000,
  });

export const useProximityHitRegionsByWeapon = (playerGuid: string, rangeDays = 30) =>
  useQuery({
    queryKey: ['proximity-hit-regions-by-weapon', playerGuid, rangeDays],
    queryFn: () => api.getProximityHitRegionsByWeapon(playerGuid, rangeDays),
    enabled: !!playerGuid,
    staleTime: 60_000,
  });

// Proximity Composite Scores
export const useProxScores = (rangeDays = 30, playerGuid?: string, limit = 50) =>
  useQuery({
    queryKey: ['prox-scores', rangeDays, playerGuid, limit],
    queryFn: () => api.getProxScores(rangeDays, playerGuid, limit),
    staleTime: 60_000,
  });

export const useProxFormula = () =>
  useQuery({
    queryKey: ['prox-formula'],
    queryFn: api.getProxFormula,
    staleTime: 300_000,
  });

// Movement Analytics (Phase A)
export const useMovementStats = (rangeDays = 30, playerGuid?: string) =>
  useQuery({
    queryKey: ['movement-stats', rangeDays, playerGuid],
    queryFn: () => api.getMovementStats(rangeDays, playerGuid),
    staleTime: 60_000,
  });

// Storytelling / Smart Stats
export function useStoryKillImpact(sessionDate: string | null) {
  return useQuery({
    queryKey: ['story-kill-impact', sessionDate],
    queryFn: () => api.getStoryKillImpact(sessionDate!),
    enabled: !!sessionDate,
  });
}

export function useStoryMoments(sessionDate: string | null) {
  return useQuery({
    queryKey: ['story-moments', sessionDate],
    queryFn: () => api.getStoryMoments(sessionDate!),
    enabled: !!sessionDate,
  });
}

export function useStoryMomentum(sessionDate: string | null) {
  return useQuery({
    queryKey: ['story-momentum', sessionDate],
    queryFn: () => api.getStoryMomentum(sessionDate!),
    enabled: !!sessionDate,
    staleTime: 60_000,
  });
}

export function useStoryNarrative(sessionDate: string | null) {
  return useQuery({
    queryKey: ['story-narrative', sessionDate],
    queryFn: () => api.getStoryNarrative(sessionDate!),
    enabled: !!sessionDate,
    staleTime: 60_000,
  });
}
