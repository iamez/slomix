import { useQuery } from '@tanstack/react-query';
import { api } from './client';

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

export const useWeaponsByPlayer = (period = 'all') =>
  useQuery({
    queryKey: ['weapons-by-player', period],
    queryFn: () => api.getWeaponsByPlayer(period),
    staleTime: 60_000,
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

// Sessions
export const useSessions = (params?: { limit?: number; offset?: number; search?: string }) =>
  useQuery({
    queryKey: ['sessions', params],
    queryFn: () => api.getSessions(params),
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
