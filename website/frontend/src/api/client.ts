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
  SessionGraphsResponse,
  ProximityScope,
  ProximityTradeSummaryResponse,
  ProximityTradeEventsResponse,
  ProximityDuosResponse,
  ProximityTeamplayResponse,
  ProximityMoversResponse,
  RoundPlayerDetailResponse,
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
  KillOutcomesResponse,
  KillOutcomePlayerStatsResponse,
  HitRegionsResponse,
  WeaponHitRegionsResponse,
  HeadshotRatesResponse,
  CombatHeatmapResponse,
  KillLinesResponse,
  DangerZonesResponse,
  MomentumResponse,
  NarrativeResponse,
  PlayerNarrativesResponse,
  GravityResponse,
  SpaceCreatedResponse,
  EnablerResponse,
  LurkerResponse,
  SynergyResponse,
  WinContributionResponse,
  BoxScoreResponse,
} from './types';

const API_BASE = '/api';
const responseCache = new Map<string, unknown>();

function stripConditionalHeaders(headers?: HeadersInit): Headers {
  const cleaned = new Headers(headers);
  cleaned.delete('if-none-match');
  cleaned.delete('If-None-Match');
  cleaned.delete('if-modified-since');
  cleaned.delete('If-Modified-Since');
  return cleaned;
}

async function get<T>(path: string, init: RequestInit = {}): Promise<T> {
  const cacheKey = `${init.method ?? 'GET'}:${path}`;
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, init);

  if (res.status === 304) {
    const cached = responseCache.get(cacheKey);
    if (cached !== undefined) return cached as T;

    const retryRes = await fetch(url, {
      ...init,
      cache: 'no-store',
      headers: stripConditionalHeaders(init.headers),
    });
    if (!retryRes.ok) throw new Error(`API ${retryRes.status}: ${path}`);
    const retryData = await retryRes.json() as T;
    responseCache.set(cacheKey, retryData);
    return retryData;
  }

  if (!res.ok) throw new Error(`API ${res.status}: ${path}`);
  const data = await res.json() as T;
  responseCache.set(cacheKey, data);
  return data;
}

function buildScopedQuery(params?: ProximityScope, extra?: Record<string, string | number | boolean | null | undefined>) {
  const q = new URLSearchParams();
  if (params?.session_date) q.set('session_date', params.session_date);
  if (params?.map_name) q.set('map_name', params.map_name);
  if (params?.round_number != null) q.set('round_number', String(params.round_number));
  if (params?.round_start_unix != null) q.set('round_start_unix', String(params.round_start_unix));
  if (params?.range_days != null) q.set('range_days', String(params.range_days));
  if (extra) {
    Object.entries(extra).forEach(([key, value]) => {
      if (value != null) q.set(key, String(value));
    });
  }
  return q.toString();
}

export const api = {
  // Home / Overview
  getOverview: () => get<OverviewStats>('/stats/overview', { cache: 'no-store' }),
  getLiveStatus: () => get<LiveStatusResponse>('/live-status', { cache: 'no-store' }),
  getTrends: (days = 14) => get<TrendsResponse>(`/stats/trends?days=${days}`),
  getSeason: () => get<SeasonInfo>('/seasons/current', { cache: 'no-store' }),

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
  getWeaponsByPlayer: (period = 'all', playerLimit = 24, weaponLimit = 4, playerGuid?: string, gamingSessionId?: number) =>
    get<WeaponByPlayerResponse>(
      `/stats/weapons/by-player?period=${period}&player_limit=${playerLimit}&weapon_limit=${weaponLimit}${playerGuid ? `&player_guid=${encodeURIComponent(playerGuid)}` : ''}${gamingSessionId ? `&gaming_session_id=${gamingSessionId}` : ''}`,
    ),

  // Round Viz
  getRecentRounds: (limit = 50) =>
    get<RecentRound[]>(`/rounds/recent?limit=${limit}`),
  getRoundViz: (roundId: number) =>
    get<RoundVizData>(`/rounds/${roundId}/viz`),
  getRoundPlayerDetails: (roundId: number, playerGuid: string) =>
    get<RoundPlayerDetailResponse>(`/rounds/${roundId}/player/${encodeURIComponent(playerGuid)}/details`),

  // Session Detail
  getSessionDetail: (sessionId: number) =>
    get<SessionDetailResponse>(`/stats/session/${sessionId}/detail`),
  getSessionByDate: (date: string) =>
    get<SessionDetailResponse>(`/sessions/${encodeURIComponent(date)}`),
  getSessionGraphs: (date: string, gamingSessionId?: number | null) =>
    get<SessionGraphsResponse>(
      `/sessions/${encodeURIComponent(date)}/graphs${gamingSessionId ? `?gaming_session_id=${gamingSessionId}` : ''}`,
    ),
  getProximityTradeSummary: (params?: ProximityScope) =>
    get<ProximityTradeSummaryResponse>(`/proximity/trades/summary${buildScopedQuery(params) ? `?${buildScopedQuery(params)}` : ''}`),
  getProximityTradeEvents: (params?: ProximityScope, limit = 250) =>
    get<ProximityTradeEventsResponse>(`/proximity/trades/events?${buildScopedQuery(params, { limit })}`),
  getProximityDuos: (params?: ProximityScope, limit = 8) =>
    get<ProximityDuosResponse>(`/proximity/duos?${buildScopedQuery(params, { limit })}`),
  getProximityTeamplay: (params?: ProximityScope) =>
    get<ProximityTeamplayResponse>(`/proximity/teamplay${buildScopedQuery(params) ? `?${buildScopedQuery(params)}` : ''}`),
  getProximityMovers: (params?: ProximityScope, limit = 5) =>
    get<ProximityMoversResponse>(`/proximity/movers?${buildScopedQuery(params, { limit })}`),

  // Kill Outcomes (v5.2)
  getProximityKillOutcomes: (params?: ProximityScope) =>
    get<KillOutcomesResponse>(`/proximity/kill-outcomes${buildScopedQuery(params) ? `?${buildScopedQuery(params)}` : ''}`),
  getProximityKillOutcomePlayerStats: (params?: ProximityScope, playerGuid?: string) => {
    const q = buildScopedQuery(params, playerGuid ? { player_guid: playerGuid } : undefined);
    return get<KillOutcomePlayerStatsResponse>(`/proximity/kill-outcomes/player-stats?${q}`);
  },

  // Hit Regions (v5.2)
  getProximityHitRegions: (params?: ProximityScope, weaponId?: number) => {
    const q = new URLSearchParams();
    if (params?.range_days) q.set('range_days', String(params.range_days));
    if (params?.session_date) q.set('session_date', params.session_date);
    if (params?.map_name) q.set('map_name', params.map_name);
    if (weaponId != null) q.set('weapon_id', String(weaponId));
    return get<HitRegionsResponse>(`/proximity/hit-regions?${q.toString()}`);
  },
  getProximityHitRegionsByWeapon: (playerGuid: string, rangeDays = 30) =>
    get<WeaponHitRegionsResponse>(`/proximity/hit-regions/by-weapon?player_guid=${encodeURIComponent(playerGuid)}&range_days=${rangeDays}`),
  getProximityHeadshotRates: (params?: ProximityScope) => {
    const q = buildScopedQuery(params);
    return get<HeadshotRatesResponse>(`/proximity/hit-regions/headshot-rates${q ? `?${q}` : ''}`);
  },

  // Combat Positions (v5.2)
  getCombatHeatmap: (mapName: string, opts?: { weaponId?: number; perspective?: string; victimClass?: string; team?: string; rangeDays?: number }) => {
    const q = new URLSearchParams({ map_name: mapName, range_days: String(opts?.rangeDays ?? 30) });
    if (opts?.weaponId != null) q.set('weapon_id', String(opts.weaponId));
    if (opts?.perspective) q.set('perspective', opts.perspective);
    if (opts?.victimClass) q.set('victim_class', opts.victimClass);
    if (opts?.team) q.set('team', opts.team);
    return get<CombatHeatmapResponse>(`/proximity/combat-positions/heatmap?${q.toString()}`);
  },
  getKillLines: (mapName: string, opts?: { weaponId?: number; attackerGuid?: string; rangeDays?: number; limit?: number }) => {
    const q = new URLSearchParams({ map_name: mapName, range_days: String(opts?.rangeDays ?? 30), limit: String(opts?.limit ?? 100) });
    if (opts?.weaponId != null) q.set('weapon_id', String(opts.weaponId));
    if (opts?.attackerGuid) q.set('attacker_guid', opts.attackerGuid);
    return get<KillLinesResponse>(`/proximity/combat-positions/kill-lines?${q.toString()}`);
  },
  getDangerZones: (mapName: string, opts?: { victimClass?: string; rangeDays?: number }) => {
    const q = new URLSearchParams({ map_name: mapName, range_days: String(opts?.rangeDays ?? 30) });
    if (opts?.victimClass) q.set('victim_class', opts.victimClass);
    return get<DangerZonesResponse>(`/proximity/combat-positions/danger-zones?${q.toString()}`);
  },

  // Proximity Composite Scores
  getProxScores: (rangeDays = 30, playerGuid?: string, limit = 50) => {
    const q = new URLSearchParams({ range_days: String(rangeDays), limit: String(limit) });
    if (playerGuid) q.set('player_guid', playerGuid);
    return get<import('./types').ProxScoresResponse>(`/proximity/prox-scores?${q.toString()}`);
  },
  getProxFormula: () =>
    get<import('./types').ProxFormulaResponse>('/proximity/prox-scores/formula'),

  // Movement Analytics
  getMovementStats: (rangeDays = 30, playerGuid?: string) => {
    const q = new URLSearchParams({ range_days: String(rangeDays) });
    if (playerGuid) q.set('player_guid', playerGuid);
    return get<import('./types').MovementStatsResponse>(`/proximity/movement-stats?${q.toString()}`);
  },

  // Proximity Player Profile
  getProximityPlayerProfile: (guid: string, rangeDays = 90) =>
    get<import('./types').ProximityPlayerProfile>(`/proximity/player/${encodeURIComponent(guid)}/profile?range_days=${rangeDays}`),
  getProximityPlayerRadar: (guid: string, rangeDays = 90) =>
    get<import('./types').ProximityRadar>(`/proximity/player/${encodeURIComponent(guid)}/radar?range_days=${rangeDays}`),

  // Proximity Round
  getProximityRoundTimeline: (roundId: number) =>
    get<import('./types').ProximityTimelineResponse>(`/proximity/round/${roundId}/timeline`),
  getProximityRoundTracks: (roundId: number) =>
    get<import('./types').ProximityTracksResponse>(`/proximity/round/${roundId}/tracks`),
  getProximityRoundTeamComparison: (roundId: number) =>
    get<import('./types').ProximityTeamComparisonResponse>(`/proximity/round/${roundId}/team-comparison`),

  // Proximity Leaderboards
  getProximityLeaderboards: (category = 'power', rangeDays = 30, limit = 10) =>
    get<import('./types').ProximityLeaderboardResponse>(
      `/proximity/leaderboards?category=${category}&range_days=${rangeDays}&limit=${limit}`,
    ),

  getProximitySessionScores: (sessionDate?: string) =>
    get<import('./types').ProximitySessionScoresResponse>(
      `/proximity/session-scores${sessionDate ? `?session_date=${sessionDate}` : ''}`,
    ),

  // Weapon Accuracy
  getProximityWeaponAccuracy: (params?: { player_guid?: string; map_name?: string; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.player_guid) q.set('player_guid', params.player_guid);
    if (params?.map_name) q.set('map_name', params.map_name);
    if (params?.limit) q.set('limit', String(params.limit));
    return get<import('./types').ProximityWeaponAccuracyResponse>(`/proximity/weapon-accuracy?${q.toString()}`);
  },

  // VS Stats
  getPlayerVsStats: (guid: string, scope = 'all', sessionId?: number, roundId?: number, limit = 5) => {
    const q = new URLSearchParams();
    q.set('scope', scope);
    if (sessionId) q.set('session_id', String(sessionId));
    if (roundId) q.set('round_id', String(roundId));
    q.set('limit', String(limit));
    return get<import('./types').PlayerVsStatsResponse>(`/player/${encodeURIComponent(guid)}/vs-stats?${q.toString()}`);
  },

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

  // Skill Rating
  getSkillLeaderboard: (limit = 50) =>
    get<import('./types').SkillLeaderboardResponse>(`/skill/leaderboard?limit=${limit}`),
  getSkillFormula: () =>
    get<import('./types').SkillFormulaResponse>('/skill/formula'),
  getSkillHistory: (identifier: string, rangeDays = 30, sessionDate?: string) => {
    const params = new URLSearchParams({ range_days: String(rangeDays) });
    if (sessionDate) params.set('session_date', sessionDate);
    return get<import('./types').SkillHistoryResponse>(
      `/skill/player/${encodeURIComponent(identifier)}/history?${params.toString()}`
    );
  },

  // Storytelling / Smart Stats
  getStoryKillImpact: (sessionDate: string, limit = 20) =>
    get<import('./types').KillImpactResponse>(`/storytelling/kill-impact?session_date=${sessionDate}&limit=${limit}`),

  getStoryMoments: (sessionDate: string, limit = 10) =>
    get<import('./types').MomentsResponse>(`/storytelling/moments?session_date=${sessionDate}&limit=${limit}`),

  getStoryMomentum: (sessionDate: string) =>
    get<MomentumResponse>(`/storytelling/momentum?session_date=${sessionDate}`),

  getStoryNarrative: (sessionDate: string) =>
    get<NarrativeResponse>(`/storytelling/narrative?session_date=${sessionDate}`),

  getPlayerNarratives: (sessionDate: string) =>
    get<PlayerNarrativesResponse>(`/storytelling/player-narratives?session_date=${sessionDate}`),

  getStoryGravity: (sessionDate: string) =>
    get<GravityResponse>(`/storytelling/gravity?session_date=${sessionDate}`),

  getStorySpaceCreated: (sessionDate: string) =>
    get<SpaceCreatedResponse>(`/storytelling/space-created?session_date=${sessionDate}`),

  getStoryEnabler: (sessionDate: string) =>
    get<EnablerResponse>(`/storytelling/enabler?session_date=${sessionDate}`),

  getStoryLurkerProfile: (sessionDate: string) =>
    get<LurkerResponse>(`/storytelling/lurker-profile?session_date=${sessionDate}`),

  getStorySynergy: (sessionDate: string) =>
    get<SynergyResponse>(`/storytelling/synergy?session_date=${sessionDate}`),

  getStoryWinContribution: (sessionDate: string) =>
    get<WinContributionResponse>(`/storytelling/win-contribution?session_date=${sessionDate}`),

  getStoryBoxScore: (sessionDate: string) =>
    get<BoxScoreResponse>(`/storytelling/box-score?session_date=${sessionDate}`),

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
