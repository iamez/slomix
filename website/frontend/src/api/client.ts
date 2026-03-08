import type {
  RecordsResponse,
  LeaderboardEntry,
  QuickLeadersResponse,
  MapStats,
  HallOfFameResponse,
  AwardLeaderboardResponse,
  AwardsListResponse,
  PlayerAwardsResponse,
  PlayerProfileResponse,
  PlayerFormEntry,
  PlayerRound,
  SessionSummary,
  WeaponStat,
  WeaponHoFResponse,
  WeaponByPlayerResponse,
  RecentRound,
  RoundVizData,
  SessionDetailResponse,
  UploadListResponse,
  UploadDetail,
  PopularTag,
  AuthUser,
  OverviewStats,
  LiveStatusResponse,
  TrendsResponse,
  SeasonInfo,
  GreatshotListResponse,
  GreatshotDetailResponse,
  GreatshotStatus,
  GreatshotCrossref,
  AvailabilityAccess,
  AvailabilityRangeResponse,
  AvailabilitySettings,
  PlanningState,
  PromotionPreview,
} from './types';

const API_BASE = '/api';

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`);
  return res.json();
}

export const api = {
  // Home / Overview
  getOverview: () => get<OverviewStats>('/stats/overview'),
  getLiveStatus: () => get<LiveStatusResponse>('/live-status'),
  getTrends: (days = 14) => get<TrendsResponse>(`/stats/trends?days=${days}`),
  getSeason: () => get<SeasonInfo>('/seasons/current'),

  // Records
  getRecords: (mapName?: string) =>
    get<RecordsResponse>(
      `/stats/records?limit=5${mapName ? `&map_name=${encodeURIComponent(mapName)}` : ''}`,
    ),
  getMaps: () =>
    get<{ name: string }[]>('/stats/maps').then((maps) => maps.map((m) => m.name)),

  // Leaderboard
  getLeaderboard: (stat = 'dpm', period = '30d', limit = 50) =>
    get<LeaderboardEntry[]>(`/stats/leaderboard?stat=${stat}&period=${period}&limit=${limit}`),
  getQuickLeaders: () => get<QuickLeadersResponse>('/stats/quick-leaders'),

  // Maps
  getMapStats: () => get<MapStats[]>('/stats/maps'),

  // Hall of Fame
  getHallOfFame: (period = 'all_time', limit = 10) =>
    get<HallOfFameResponse>(`/hall-of-fame?period=${period}&limit=${limit}`),

  // Awards
  getAwardsLeaderboard: (params?: { days?: string; award_type?: string; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.days) q.set('days', params.days);
    if (params?.award_type) q.set('award_type', params.award_type);
    if (params?.limit) q.set('limit', String(params.limit));
    const qs = q.toString();
    return get<AwardLeaderboardResponse>(`/awards/leaderboard${qs ? `?${qs}` : ''}`);
  },
  getAwards: (params?: { days?: string; award_type?: string; limit?: number; offset?: number }) => {
    const q = new URLSearchParams();
    if (params?.days) q.set('days', params.days);
    if (params?.award_type) q.set('award_type', params.award_type);
    if (params?.limit) q.set('limit', String(params.limit));
    if (params?.offset) q.set('offset', String(params.offset));
    const qs = q.toString();
    return get<AwardsListResponse>(`/awards${qs ? `?${qs}` : ''}`);
  },
  getPlayerAwards: (id: string, limit = 12) =>
    get<PlayerAwardsResponse>(`/players/${encodeURIComponent(id)}/awards?limit=${limit}`),

  // Player Profile
  getPlayerProfile: (name: string) =>
    get<PlayerProfileResponse>(`/stats/player/${encodeURIComponent(name)}`),
  getPlayerForm: (name: string) =>
    get<PlayerFormEntry[]>(`/stats/player/${encodeURIComponent(name)}/form`),
  getPlayerRounds: (name: string, limit = 20) =>
    get<PlayerRound[]>(`/stats/player/${encodeURIComponent(name)}/rounds?limit=${limit}`),

  // Weapons
  getWeapons: (period = 'all', limit = 200) =>
    get<WeaponStat[]>(`/stats/weapons?period=${period}&limit=${limit}`),
  getWeaponHoF: (period = 'all') =>
    get<WeaponHoFResponse>(`/stats/weapons/hall-of-fame?period=${period}`),
  getWeaponsByPlayer: (period = 'all', playerLimit = 24, weaponLimit = 4) =>
    get<WeaponByPlayerResponse>(
      `/stats/weapons/by-player?period=${period}&player_limit=${playerLimit}&weapon_limit=${weaponLimit}`,
    ),

  // Round Viz
  getRecentRounds: (limit = 50) =>
    get<RecentRound[]>(`/rounds/recent?limit=${limit}`),
  getRoundViz: (roundId: number) =>
    get<RoundVizData>(`/rounds/${roundId}/viz`),

  // Session Detail
  getSessionDetail: (sessionId: number) =>
    get<SessionDetailResponse>(`/stats/session/${sessionId}/detail`),
  getSessionByDate: (date: string) =>
    get<SessionDetailResponse>(`/sessions/${encodeURIComponent(date)}`),

  // Sessions
  getSessions: (params?: { limit?: number; offset?: number; search?: string }) => {
    const q = new URLSearchParams();
    if (params?.limit) q.set('limit', String(params.limit));
    if (params?.offset) q.set('offset', String(params.offset));
    if (params?.search) q.set('search', params.search);
    return get<SessionSummary[]>(`/stats/sessions?${q.toString()}`);
  },

  // Uploads
  getUploads: (params?: { category?: string; tag?: string; search?: string; limit?: number; offset?: number }) => {
    const q = new URLSearchParams();
    if (params?.category) q.set('category', params.category);
    if (params?.tag) q.set('tag', params.tag);
    if (params?.search) q.set('search', params.search);
    if (params?.limit) q.set('limit', String(params.limit));
    if (params?.offset) q.set('offset', String(params.offset));
    return get<UploadListResponse>(`/uploads?${q.toString()}`);
  },
  getUpload: (id: string) =>
    get<UploadDetail>(`/uploads/${encodeURIComponent(id)}`),
  getPopularTags: (limit = 15) =>
    get<PopularTag[]>(`/uploads/tags/popular?limit=${limit}`),

  // Greatshot (auth-required)
  getGreatshotDemos: () => get<GreatshotListResponse>('/greatshot'),
  getGreatshotDetail: (id: string) =>
    get<GreatshotDetailResponse>(`/greatshot/${encodeURIComponent(id)}`),
  getGreatshotStatus: (id: string) =>
    get<GreatshotStatus>(`/greatshot/${encodeURIComponent(id)}/status`),
  getGreatshotCrossref: (id: string) =>
    get<GreatshotCrossref>(`/greatshot/${encodeURIComponent(id)}/crossref`),
  queueGreatshotRender: async (demoId: string, highlightId: string) => {
    const res = await fetch(`${API_BASE}/greatshot/${encodeURIComponent(demoId)}/highlights/render`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ highlight_id: highlightId }),
    });
    if (!res.ok) throw new Error(`API ${res.status}`);
    return res.json();
  },

  // Availability
  getAvailabilityAccess: () => get<AvailabilityAccess>('/availability/access'),
  getAvailabilityRange: (from?: string, to?: string, includeUsers = false) => {
    const q = new URLSearchParams();
    if (from) q.set('from', from);
    if (to) q.set('to', to);
    if (includeUsers) q.set('include_users', 'true');
    return get<AvailabilityRangeResponse>(`/availability?${q.toString()}`);
  },
  setAvailability: async (dateIso: string, status: string) => {
    const res = await fetch(`${API_BASE}/availability`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      credentials: 'same-origin',
      body: JSON.stringify({ date: dateIso, status }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      throw new Error(body?.detail || `HTTP ${res.status}`);
    }
    return res.json();
  },
  getAvailabilitySettings: () => get<AvailabilitySettings>('/availability/settings'),
  saveAvailabilitySettings: async (settings: Record<string, unknown>) => {
    const res = await fetch(`${API_BASE}/availability/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      credentials: 'same-origin',
      body: JSON.stringify(settings),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      throw new Error(body?.detail || `HTTP ${res.status}`);
    }
    return res.json() as Promise<AvailabilitySettings>;
  },
  getPlanningState: () => get<PlanningState>('/availability/planning/today'),
  postPlanning: async (path: string, body: Record<string, unknown> = {}) => {
    const res = await fetch(`${API_BASE}/availability/planning${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      credentials: 'same-origin',
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const payload = await res.json().catch(() => null);
      throw new Error(payload?.detail || `HTTP ${res.status}`);
    }
    return res.json();
  },
  getPromotionPreview: (includeAvailable = true, includeMaybe = false) =>
    get<PromotionPreview>(
      `/availability/promotions/preview?include_available=${includeAvailable}&include_maybe=${includeMaybe}`,
    ),
  schedulePromotion: async (opts: { include_available: boolean; include_maybe: boolean; dry_run: boolean }) => {
    const res = await fetch(`${API_BASE}/availability/promotions/campaigns`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      credentials: 'same-origin',
      body: JSON.stringify(opts),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      throw new Error(body?.detail || `HTTP ${res.status}`);
    }
    return res.json();
  },

  // Auth
  getAuthMe: async (): Promise<AuthUser | null> => {
    try {
      const res = await fetch('/auth/me');
      if (!res.ok) return null;
      return res.json();
    } catch {
      return null;
    }
  },
};
