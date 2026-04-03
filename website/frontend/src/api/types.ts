// Records
export interface RecordEntry {
  player: string;
  value: number;
  map: string;
  date: string;
}
export type RecordsResponse = Record<string, RecordEntry[]>;

// Leaderboard
export interface LeaderboardEntry {
  rank: number;
  guid: string;
  name: string;
  value: number;
  rounds: number;
  kills: number;
  deaths: number;
  kd: number;
}

// Quick Leaders
export interface QuickLeaderEntry {
  rank: number;
  guid: string;
  name: string;
  value: number;
  rounds?: number;
  sessions?: number;
  label: string;
}
export interface QuickLeadersResponse {
  window_days: number;
  xp: QuickLeaderEntry[];
  dpm_sessions: QuickLeaderEntry[];
}

// Maps
export interface MapStats {
  name: string;
  total_rounds: number;
  matches_played: number;
  allies_wins: number;
  axis_wins: number;
  allies_win_rate: number;
  axis_win_rate: number;
  avg_duration: number;
  min_duration: number;
  max_duration: number;
  last_played: string;
  total_kills: number;
  total_deaths: number;
  avg_dpm: number;
  unique_players: number;
  grenade_kills: number;
  panzer_kills: number;
  mortar_kills: number;
}

// Hall of Fame
export interface HallOfFameEntry {
  rank: number;
  player_guid: string;
  player_name: string;
  value: number;
  unit: string;
}
export interface HallOfFameResponse {
  categories: Record<string, HallOfFameEntry[]>;
  period: string;
  generated_at: string;
}

// Awards
export interface AwardLeaderboardEntry {
  player: string;
  guid: string;
  award_count: number;
  top_award: string;
  top_award_count?: number;
}
export interface AwardLeaderboardResponse {
  leaderboard: AwardLeaderboardEntry[];
}
export interface RoundAward {
  round_id: number;
  date: string;
  map: string;
  round_number: number;
  award: string;
  player: string;
  guid: string;
  value: string | number;
}
export interface AwardsListResponse {
  awards: RoundAward[];
  total: number;
}
export interface PlayerAwardsResponse {
  player: string;
  guid: string;
  total_awards: number;
  by_type: Record<string, number>;
  recent: Array<{ award: string; map: string; round: number; date: string }>;
}

// Player Profile
export interface PlayerStats {
  kills: number;
  deaths: number;
  damage: number;
  games: number;
  wins: number;
  losses: number;
  win_rate: number;
  kd: number;
  dpm: number;
  total_xp: number;
  playtime_hours: number;
  last_seen: string;
  favorite_weapon: string | null;
  favorite_map: string | null;
  highest_dpm: number | null;
  lowest_dpm: number | null;
}
export interface PlayerAchievement {
  name: string;
  description: string;
  icon: string;
  unlocked: boolean;
}
export interface PlayerProfileResponse {
  name: string;
  guid: string;
  stats: PlayerStats;
  aliases: string[];
  discord_linked: boolean;
  achievements: PlayerAchievement[];
}

// Player Form
export interface PlayerFormEntry {
  date: string;
  kills: number;
  deaths: number;
  damage: number;
  dpm: number;
  kd: number;
}

// Player Rounds
export interface PlayerRound {
  round_id: number;
  map_name: string;
  round_number: number;
  round_date: string;
  kills: number;
  deaths: number;
  damage_given: number;
  dpm: number;
  kd: number;
  team: number;
  winner_team: number;
}

// Weapons
export interface WeaponStat {
  name: string;
  weapon_key: string;
  kills: number;
  headshots: number;
  hs_rate: number;
  accuracy: number;
}
export interface WeaponHoFEntry {
  weapon: string;
  weapon_key: string;
  player_guid: string;
  player_name: string;
  kills: number;
  headshots: number;
  accuracy: number;
}
export interface WeaponHoFResponse {
  period: string;
  leaders: Record<string, WeaponHoFEntry>;
}
export interface PlayerWeaponEntry {
  name: string;
  weapon_key: string;
  kills: number;
  headshots: number;
  hs_rate: number;
  shots: number;
  hits: number;
  accuracy: number;
}
export interface WeaponPlayerStat {
  player_guid: string;
  player_name: string;
  total_kills: number;
  weapons: PlayerWeaponEntry[];
}
export interface WeaponByPlayerResponse {
  period: string;
  player_count: number;
  players: WeaponPlayerStat[];
}

// Round Viz
export interface RecentRound {
  id: number;
  map_name: string;
  round_date: string | null;
  round_number: number;
  round_label: string;
  player_count: number;
}
export interface VizPlayer {
  name: string;
  guid: string;
  kills: number;
  deaths: number;
  damage_given: number;
  damage_received: number;
  team_damage_given: number;
  team_damage_received: number;
  time_played_seconds: number;
  time_dead_seconds: number;
  revives_given: number;
  gibs: number;
  self_kills: number;
  denied_playtime: number;
  xp: number;
  kill_assists: number;
  efficiency: number;
  dpm: number;
}
export interface RoundVizData {
  round_id: number;
  map_name: string;
  round_date: string | null;
  round_number: number;
  round_label: string;
  winner_team: number | null;
  duration_seconds: number | null;
  player_count: number;
  players: VizPlayer[];
  highlights: {
    mvp?: { name: string; dpm: number };
    most_kills?: { name: string; kills: number };
    most_damage?: { name: string; damage_given: number };
  };
}

// Session Detail
export interface SessionRound {
  round_id: number;
  round_number: number;
  map_name: string;
  winner_team: number | null;
  allies_score: number | null;
  axis_score: number | null;
  duration_seconds: number | null;
  round_date: string | null;
  round_time: string | null;
  round_start_unix: number;
}
export interface SessionMatch {
  map_name: string;
  rounds: SessionRound[];
}
export interface SessionPlayer {
  player_guid: string;
  player_name: string;
  kills: number;
  deaths: number;
  damage_given: number;
  damage_received: number;
  dpm: number;
  kd: number;
  headshot_kills: number;
  gibs: number;
  self_kills: number;
  revives_given: number;
  times_revived: number;
  kill_assists: number;
  time_played_seconds: number;
  accuracy?: number;
  headshot_pct?: number;
  efficiency?: number;
  alive_pct?: number | null;
  alive_pct_lua?: number | null;
  alive_pct_diff?: number | null;
  alive_pct_drift?: boolean;
  played_pct?: number | null;
  played_pct_lua?: number | null;
  played_pct_diff?: number | null;
  played_pct_drift?: boolean;
  supastats_tmp_pct?: number | null;
  supastats_tmp_ratio?: number | null;
  time_dead_minutes?: number | null;
  denied_playtime?: number | null;
  time_denied_seconds?: number | null;
  alive_percent?: number | null;
  played_percent?: number | null;
}
export interface SessionScoringMap {
  map_name: string;
  team_a_points?: number;
  team_b_points?: number;
  allies_score?: number;
  axis_score?: number;
}
export interface SessionScoring {
  available: boolean;
  team_a_total?: number;
  team_b_total?: number;
  maps?: SessionScoringMap[];
}
export interface SessionDetailResponse {
  session_id: number | null;
  date: string | null;
  player_count: number;
  round_count: number;
  matches: SessionMatch[];
  players: SessionPlayer[];
  scoring: SessionScoring;
}

export interface SessionGraphTimelinePoint {
  label: string;
  dpm: number;
}

export interface SessionGraphCombatOffense {
  kills: number;
  deaths: number;
  damage_given: number;
  kd: number;
  dpm: number;
}

export interface SessionGraphCombatDefense {
  revives: number;
  kill_assists: number;
  gibs: number;
  headshots: number;
  times_revived: number;
  team_kills: number;
  self_kills: number;
}

export interface SessionGraphAdvancedMetrics {
  frag_potential: number;
  damage_efficiency: number;
  survival_rate: number;
  time_denied: number;
  time_denied_raw_seconds: number;
  time_dead_raw_seconds: number;
}

export interface SessionGraphPlaystyle {
  aggression: number;
  precision: number;
  survivability: number;
  support: number;
  lethality: number;
  brutality: number;
  consistency: number;
  efficiency: number;
}

export interface SessionGraphPlayer {
  name: string;
  combat_offense: SessionGraphCombatOffense;
  combat_defense: SessionGraphCombatDefense;
  advanced_metrics: SessionGraphAdvancedMetrics;
  playstyle: SessionGraphPlaystyle;
  dpm_timeline: SessionGraphTimelinePoint[];
}

export interface SessionGraphsResponse {
  date: string;
  player_count: number;
  players: SessionGraphPlayer[];
}

export interface ProximityScope {
  range_days?: number;
  session_date?: string | null;
  map_name?: string | null;
  round_number?: number | null;
  round_start_unix?: number | null;
}

export interface ProximityTradeSummaryResponse {
  status: string;
  ready: boolean;
  message?: string | null;
  scope?: Record<string, unknown>;
  events: number;
  trade_opportunities: number;
  trade_attempts: number;
  trade_success: number;
  missed_trade_candidates: number;
  support_uptime_pct: number | null;
  isolation_deaths: number | null;
}

export interface ProximityTradeEvent {
  date: string;
  round: number;
  map: string;
  victim: string;
  killer: string;
  opportunities: number;
  attempts: number;
  success: number;
  missed: number;
  round_id: number | null;
  round_date: string | null;
  round_time: string | null;
  outcome: string;
}

export interface ProximityTradeEventsResponse {
  status: string;
  ready: boolean;
  message?: string | null;
  scope?: Record<string, unknown>;
  limit: number;
  events: ProximityTradeEvent[];
}

export interface ProximityDuo {
  player1?: string;
  player1_name?: string;
  player2?: string;
  player2_name?: string;
  crossfire_kills?: number;
  crossfires?: number;
  avg_delay_ms?: number | null;
}

export interface ProximityDuosResponse {
  status: string;
  ready: boolean;
  message?: string | null;
  scope?: Record<string, unknown>;
  limit: number;
  duos: ProximityDuo[];
}

export interface ProximityTeamplayEntry {
  guid?: string | null;
  name: string;
  crossfire_kills?: number;
  crossfire_participations?: number;
  crossfire_final_blows?: number;
  avg_delay_ms?: number | null;
  count?: number;
  value?: number;
  survival_rate_pct?: number | null;
}

export interface ProximityTeamplayResponse {
  status: string;
  ready: boolean;
  message?: string | null;
  scope?: Record<string, unknown>;
  limit: number;
  sampled_engagements?: number;
  crossfire_kills: ProximityTeamplayEntry[];
  sync: ProximityTeamplayEntry[];
  focus_survival: ProximityTeamplayEntry[];
}

export interface ProximityMoverEntry {
  guid?: string | null;
  name: string;
  total_distance?: number | null;
  sprint_pct?: number | null;
  reaction_ms?: number | null;
  duration_ms?: number | null;
  tracks?: number;
}

export interface ProximityMoversResponse {
  status: string;
  ready: boolean;
  message?: string | null;
  scope?: Record<string, unknown>;
  limit: number;
  distance: ProximityMoverEntry[];
  sprint: ProximityMoverEntry[];
  reaction: ProximityMoverEntry[];
  survival: ProximityMoverEntry[];
}

export interface RoundPlayerDetailResponse {
  player_name: string;
  round: {
    id: number;
    map_name: string;
    round_number: number;
    round_date: string;
  };
  combat: {
    kills: number;
    deaths: number;
    damage_given: number;
    damage_received: number;
    headshots: number;
    gibs: number;
    accuracy: number;
    shots: number;
    hits: number;
  };
  support: {
    revives_given: number;
    times_revived: number;
    useful_kills: number;
    useless_kills: number;
    kill_assists: number;
  };
  objectives: {
    stolen: number;
    returned: number;
    dynamites_planted: number;
    dynamites_defused: number;
  };
  sprees: {
    double_kills: number;
    triple_kills: number;
    quad_kills: number;
    multi_kills: number;
    mega_kills: number;
  };
  time: {
    played_seconds: number;
    dead_minutes: number;
    denied_playtime: number;
  };
  misc: {
    xp: number;
    team_kills: number;
    self_kills: number;
  };
  weapons: Array<{
    name: string;
    kills: number;
    deaths: number;
    headshots: number;
    hits: number;
    shots: number;
    accuracy: number;
  }>;
}

// Home / Overview
export interface OverviewStats {
  rounds: number;
  rounds_since: string | null;
  rounds_14d: number;
  players_14d: number;
  players_all_time: number;
  sessions: number;
  sessions_14d: number;
  total_kills: number;
  total_kills_14d: number;
  window_days: number;
  most_active_overall: { name: string; rounds: number } | null;
  most_active_14d: { name: string; rounds: number } | null;
}

export interface LiveStatusServer {
  online: boolean;
  hostname: string;
  map: string;
  player_count: number;
  max_players: number;
  ping_ms: number | null;
  players: Array<{ name: string }>;
  error?: string;
}
export interface LiveStatusVoice {
  count: number;
  members: Array<{ name: string }>;
}
export interface LiveStatusResponse {
  game_server: LiveStatusServer;
  voice_channel: LiveStatusVoice;
}

export interface TrendsResponse {
  dates: string[];
  rounds: number[];
  active_players: number[];
  map_distribution: Record<string, number>;
}

export interface SeasonInfo {
  id: string;
  name: string;
  days_left: number;
  start_date: string;
  end_date: string;
  next_season_id: string;
  next_season_name: string;
  next_season_start: string;
}

// Greatshot
export interface GreatshotItem {
  id: string;
  filename: string;
  status: string;
  error: string | null;
  created_at: string | null;
  map: string | null;
  duration_ms: number | null;
  highlight_count: number;
  render_job_count: number;
  rendered_count: number;
}
export interface GreatshotListResponse {
  items: GreatshotItem[];
}
export interface GreatshotHighlight {
  id: string;
  type: string;
  player: string;
  start_ms: number;
  end_ms: number;
  score: number;
  meta: Record<string, unknown>;
  explanation: string | null;
  clip_download: string | null;
}
export interface GreatshotRenderJob {
  id: string;
  highlight_id: string;
  status: string;
  video_download: string | null;
  error: string | null;
}
export interface GreatshotEvent {
  t_ms?: number;
  type?: string;
  attacker?: string;
  victim?: string;
  weapon?: string;
  message?: string;
}
export interface GreatshotDetailResponse {
  id: string;
  filename: string;
  status: string;
  error: string | null;
  created_at: string | null;
  metadata: Record<string, unknown>;
  analysis: {
    metadata: Record<string, unknown>;
    stats: Record<string, unknown>;
    events: GreatshotEvent[];
  } | null;
  highlights: GreatshotHighlight[];
  renders: GreatshotRenderJob[];
  player_stats: Record<string, Record<string, number>> | null;
  downloads: { json: string | null; txt: string | null };
}
export interface GreatshotStatus {
  status: string;
  error: string | null;
  highlight_count: number;
  map: string | null;
}
export interface GreatshotCrossref {
  matched: boolean;
  reason?: string;
  round?: Record<string, unknown>;
  comparison?: Array<Record<string, unknown>>;
}

// Uploads
export interface UploadItem {
  id: string;
  title: string;
  filename: string;
  category: string;
  extension: string;
  file_size_bytes: number;
  uploader_name: string;
  uploader_discord_id: number;
  download_count: number;
  created_at: string | null;
  share_url: string;
}
export interface UploadListResponse {
  items: UploadItem[];
  total: number;
  limit: number;
  offset: number;
}
export interface UploadDetail {
  id: string;
  title: string;
  description: string | null;
  filename: string;
  category: string;
  extension: string;
  file_size_bytes: number;
  mime_type: string;
  uploader_name: string;
  uploader_discord_id: number;
  download_count: number;
  content_hash: string;
  created_at: string | null;
  tags: string[];
  share_url: string;
  download_url: string;
  is_playable: boolean;
}
export interface PopularTag {
  tag: string;
  count: number;
}
export interface AuthUser {
  id: string;
  username: string;
  discriminator: string;
  avatar: string | null;
  global_name: string | null;
}

// Availability
export interface AvailabilityAccess {
  authenticated: boolean;
  linked_discord: boolean;
  can_submit: boolean;
  is_admin: boolean;
  can_promote: boolean;
  website_user_id: number | null;
}

export interface AvailabilityDayCounts {
  LOOKING: number;
  AVAILABLE: number;
  MAYBE: number;
  NOT_PLAYING: number;
}

export interface AvailabilityUser {
  user_id: number;
  display_name: string;
}

export interface AvailabilityDay {
  date: string;
  counts: AvailabilityDayCounts;
  total: number;
  my_status?: string | null;
  users_by_status?: Record<string, AvailabilityUser[]>;
}

export interface AvailabilitySessionReady {
  date: string;
  ready: boolean;
  looking_count: number;
  threshold: number;
  event_key: string;
}

export interface AvailabilityRangeResponse {
  from: string;
  to: string;
  statuses: string[];
  days: AvailabilityDay[];
  viewer: { authenticated: boolean; linked_discord: boolean };
  session_ready: AvailabilitySessionReady;
}

export interface AvailabilitySettings {
  user_id: number;
  sound_enabled: boolean;
  get_ready_sound: boolean;
  sound_cooldown_seconds: number;
  availability_reminders_enabled: boolean;
  timezone: string;
  discord_notify: boolean;
  telegram_notify: boolean;
  signal_notify: boolean;
}

export interface PlanningParticipant {
  user_id: number;
  display_name: string;
  status: string;
}

export interface PlanningSuggestion {
  id: number;
  name: string;
  suggested_by_name: string;
  votes: number;
  voted_by_me: boolean;
}

export interface PlanningSession {
  id: number;
  date: string;
  created_by_user_id: number;
  discord_thread_id: string | null;
  is_mock?: boolean;
  suggestions: PlanningSuggestion[];
  teams: Record<string, { members: Array<{ user_id: number }> }>;
}

export interface PlanningState {
  session: PlanningSession | null;
  participants: PlanningParticipant[];
  unlocked: boolean;
  session_ready: AvailabilitySessionReady;
  viewer: { website_user_id: number };
  is_mock?: boolean;
}

export interface PromotionPreview {
  campaign_date: string;
  recipient_count: number;
  channels_summary: Record<string, number>;
}

// Sessions
export interface SessionSummary {
  session_id: number | null;
  date: string;
  formatted_date: string;
  time_ago: string;
  round_count: number;
  rounds?: number;
  player_count: number;
  players?: number;
  maps_played: string[];
  maps?: number;
  total_kills: number;
  duration_seconds: number;
  start_time: string;
  end_time: string;
  player_names: string[];
  allies_wins: number;
  axis_wins: number;
}

// Proximity Player Profile
export interface ProximityPlayerProfile {
  status: string;
  guid: string;
  range_days: number;
  engagement: {
    total: number;
    escapes: number;
    deaths: number;
    avg_duration_ms: number;
    avg_damage_taken: number;
    avg_distance: number;
    crossfire_count: number;
    escape_rate: number;
  };
  kills: { total: number };
  spawn_timing: { avg_score: number; timed_kills: number; avg_denial_ms: number };
  reactions: { avg_return_fire_ms: number; avg_dodge_ms: number; avg_support_ms: number; samples: number };
  movement: { avg_speed: number; avg_sprint_pct: number; avg_distance_per_life: number; tracks: number };
  trades: { made: number };
}

export interface ProximityRadar {
  status: string;
  guid: string;
  axes: { aggression: number; awareness: number; teamplay: number; timing: number; mechanical: number };
  composite: number;
}

// Proximity Round Timeline
export interface ProximityTimelineEvent {
  type: string;
  time: number;
  end_time?: number;
  data: Record<string, unknown>;
}

export interface ProximityTimelineResponse {
  status: string;
  round_id: number;
  map_name: string;
  round_number: number;
  round_date: string | null;
  event_count: number;
  events: ProximityTimelineEvent[];
}

export interface ProximityTrack {
  guid: string;
  name: string;
  team: string;
  class: string;
  spawn_time: number;
  death_time: number;
  first_move_time: number | null;
  death_type: string;
  path: unknown[];
}

export interface ProximityTracksResponse {
  status: string;
  round_id: number;
  track_count: number;
  tracks: ProximityTrack[];
}

// Proximity Team Comparison
export interface ProximityTeamComparisonResponse {
  status: string;
  round_id: number;
  cohesion: Array<{ team: string; avg_dispersion: number; avg_max_spread: number; avg_stragglers: number; samples: number }>;
  pushes: Array<{ team: string; push_count: number; avg_quality: number; avg_alignment: number }>;
  crossfire: Array<{ target_team: string; total: number; executed: number; rate: number }>;
}

// Proximity Leaderboard
export interface ProximityLeaderboardEntry {
  guid: string;
  name: string;
  value: number;
  partner_guid?: string;
  partner_name?: string;
  axes?: { aggression: number; awareness: number; teamplay: number; timing: number; mechanical: number };
  timed_kills?: number;
  avg_denial_ms?: number;
  total?: number;
  avg_delay_ms?: number;
  avg_trade_ms?: number;
  avg_dodge_ms?: number;
  avg_support_ms?: number;
  samples?: number;
  escapes?: number;
  sprint_pct?: number;
  total_distance?: number;
  tracks?: number;
  times_focused?: number;
  avg_attackers?: number;
  avg_damage?: number;
}

export interface ProximityLeaderboardResponse {
  status: string;
  category: string;
  entries: ProximityLeaderboardEntry[];
}

// Proximity Session Scores
export interface SessionScoreCategory {
  raw: number;
  weighted: number;
  detail?: string;
}
export interface SessionScoreEntry {
  guid: string;
  name: string;
  total_score: number;
  categories: Record<string, SessionScoreCategory>;
  engagement_count: number;
}
export interface ProximitySessionScoresResponse {
  status: string;
  session_date: string | null;
  players: SessionScoreEntry[];
}

// VS Stats (Easiest Preys / Worst Enemies)
export interface VsStatsEntry {
  opponent_name: string;
  opponent_guid: string | null;
  kills: number;
  deaths: number;
  kd: number;
}
export interface PlayerVsStatsResponse {
  guid: string;
  scope: string;
  round_id: number | null;
  session_id: number | null;
  easiest_preys: VsStatsEntry[];
  worst_enemies: VsStatsEntry[];
}

// Proximity Weapon Accuracy
export interface ProximityWeaponAccuracyResponse {
  status: string;
  leaders: Array<{ guid: string; name: string; shots: number; hits: number; kills: number; headshots: number; accuracy: number }>;
  weapon_breakdown: Array<{ weapon_id: number; shots: number; hits: number; kills: number; headshots: number; accuracy: number }>;
}

// Skill Rating
export interface SkillComponent {
  raw: number;
  percentile: number;
  weight: number;
  contribution: number;
}

export interface RatedPlayer {
  rank: number;
  player_guid: string;
  display_name: string;
  et_rating: number;
  games_rated: number;
  last_rated_at: string | null;
  components: Record<string, SkillComponent>;
  confidence?: number;
  tier?: string;
}

export interface SkillLeaderboardResponse {
  status: string;
  players: RatedPlayer[];
  meta: {
    total: number;
    min_rounds: number;
    weights: Record<string, number>;
    constant: number;
    version: string;
  };
}

export interface SkillFormulaResponse {
  status: string;
  version: string;
  name: string;
  description: string;
  formula: string;
  constant: number;
  weights: Record<string, number>;
  min_rounds: number;
  metrics: Record<string, string>;
  normalization: string;
  range: string;
}

// Skill Rating History — session-scoped
export interface SkillSessionEntry {
  session_date: string;
  rounds: number;
  maps: number;
  session_rating: number;
  components: Record<string, SkillComponent>;
  cumulative_rating: number | null;
  delta: number | null;
}

export interface SkillMapEntry {
  map_name: string;
  rounds: number;
  map_rating: number;
  components: Record<string, SkillComponent>;
}

export interface SkillHistoryResponse {
  status: string;
  player_guid: string;
  range_days?: number;
  sessions?: SkillSessionEntry[];
  total_sessions?: number;
  // When session_date is specified (drill-down):
  session_date?: string;
  session_summary?: SkillSessionEntry | null;
  maps?: SkillMapEntry[];
}

// Kill Outcomes (v5.2)
export interface KillOutcomeEvent {
  kill_time: number;
  victim_guid: string;
  victim_name: string;
  killer_guid: string;
  killer_name: string;
  kill_mod: number;
  outcome: string;
  delta_ms: number;
  effective_denied_ms: number;
  gibber_guid: string;
  gibber_name: string;
  reviver_guid: string;
  reviver_name: string;
  session_date: string | null;
  map_name: string;
  round_number: number;
}

export interface KillOutcomeSummary {
  total_kills: number;
  gibbed: number;
  revived: number;
  tapped_out: number;
  expired: number;
  round_end: number;
  gib_rate: number;
  revive_rate: number;
  avg_delta_ms: number;
  avg_denied_ms: number;
}

export interface KillOutcomesResponse {
  status: string;
  scope: Record<string, unknown>;
  summary: KillOutcomeSummary;
  outcomes: Record<string, { count: number; avg_delta_ms: number; avg_denied_ms: number }>;
  events: KillOutcomeEvent[];
}

export interface KillPermanenceEntry {
  guid: string;
  name: string;
  total_kills: number;
  gibs: number;
  revives_against: number;
  tapouts: number;
  kpr: number;
  avg_denied_ms: number;
}

export interface ReviveRateEntry {
  guid: string;
  name: string;
  times_killed: number;
  times_gibbed: number;
  times_revived: number;
  times_tapped: number;
  revive_rate: number;
  gib_rate: number;
  avg_wait_ms: number;
}

export interface KillOutcomePlayerStatsResponse {
  status: string;
  scope: Record<string, unknown>;
  kill_permanence_leaders: KillPermanenceEntry[];
  revive_rate_leaders: ReviveRateEntry[];
}

// Hit Regions (v5.2)
export interface HitRegionPlayer {
  guid: string;
  name: string;
  head: number;
  arms: number;
  body: number;
  legs: number;
  head_pct: number;
  total_hits: number;
  total_damage: number;
}

export interface HitRegionsResponse {
  status: string;
  scope: Record<string, unknown>;
  players: HitRegionPlayer[];
}

export interface WeaponHitRegion {
  weapon_id: number;
  head: number;
  arms: number;
  body: number;
  legs: number;
  total: number;
  headshot_pct: number;
  total_damage: number;
}

export interface WeaponHitRegionsResponse {
  status: string;
  weapons: WeaponHitRegion[];
}

export interface HeadshotRateEntry {
  guid: string;
  name: string;
  headshot_pct: number;
  head_hits: number;
  total_hits: number;
}

export interface HeadshotRatesResponse {
  status: string;
  leaders: HeadshotRateEntry[];
}

// Combat Positions (v5.2)
export interface HotzonePoint {
  x: number;
  y: number;
  count: number;
}

export interface CombatHeatmapResponse {
  status: string;
  map_name: string;
  grid_size: number;
  perspective: 'kills' | 'deaths';
  hotzones: HotzonePoint[];
}

export interface KillLine {
  ax: number;
  ay: number;
  vx: number;
  vy: number;
  weapon_id: number;
  attacker_team: string;
}

export interface KillLinesResponse {
  status: string;
  map_name: string;
  lines: KillLine[];
}

export interface DangerZone {
  x: number;
  y: number;
  deaths: number;
  classes: Record<string, number>;
}

export interface DangerZonesResponse {
  status: string;
  map_name: string;
  grid_size: number;
  zones: DangerZone[];
}

// Proximity Composite Scores (v5.2)
export interface ProxMetricBreakdown {
  raw: number | null;
  percentile: number;
  weight: number;
  contribution: number;
  label: string;
}

export interface ProxCategoryBreakdown {
  [metricKey: string]: ProxMetricBreakdown;
}

export interface ProxRadarAxis {
  label: string;
  value: number;
}

export interface ProxScorePlayer {
  rank: number;
  guid: string;
  name: string;
  engagements: number;
  tracks: number;
  prox_combat: number;
  prox_team: number;
  prox_gamesense: number;
  prox_overall: number;
  prox_radar: ProxRadarAxis[];
  breakdown: Record<string, ProxCategoryBreakdown>;
}

export interface ProxScoresResponse {
  status: string;
  version: string;
  range_days: number;
  player_count: number;
  players: ProxScorePlayer[];
}

export interface ProxFormulaMetric {
  label: string;
  weight: number;
  invert: boolean;
}

export interface ProxFormulaCategory {
  label: string;
  description: string;
  weight_in_overall: number;
  metrics: Record<string, ProxFormulaMetric>;
}

export interface ProxFormulaResponse {
  status: string;
  version: string;
  min_engagements: number;
  category_weights: Record<string, number>;
  categories: Record<string, ProxFormulaCategory>;
}

// Movement Analytics (Phase A)
export interface MovementStatsPlayer {
  guid: string;
  name: string;
  tracks: number;
  alive_sec: number;
  avg_peak_speed: number;
  max_peak_speed: number;
  avg_speed: number;
  total_distance: number;
  standing_sec: number;
  crouching_sec: number;
  prone_sec: number;
  standing_pct: number;
  crouching_pct: number;
  prone_pct: number;
  sprint_sec: number;
  avg_sprint_pct: number;
  avg_post_spawn_dist: number;
  avg_distance_per_sec: number;
}

export interface MovementStatsResponse {
  status: string;
  scope: Record<string, unknown>;
  players: MovementStatsPlayer[];
}

// ── Storytelling / Smart Stats ──
export interface KillImpactEntry {
  guid: string;
  name: string;
  total_kis: number;
  kills: number;
  carrier_kills: number;
  push_kills: number;
  crossfire_kills: number;
  avg_impact: number;
  archetype?: string;
}

export interface KillImpactResponse {
  status: string;
  session_date: string;
  entries: KillImpactEntry[];
  total_kills: number;
}

// ── Match Moments ──
export interface MatchMoment {
  type: 'kill_streak' | 'carrier_chain' | 'focus_survival' | 'push_success' | 'trade_chain';
  round_number: number;
  map_name: string;
  time_ms: number;
  player: string;
  narrative: string;
  impact_stars: number;
  detail: Record<string, unknown>;
}

export interface MomentsResponse {
  status: string;
  session_date: string;
  moments: MatchMoment[];
  total: number;
}

export interface KillImpactDetail {
  kill_id: number;
  killer_name: string;
  victim_name: string;
  round_number: number;
  kill_time_ms: number;
  total_impact: number;
  base_impact: number;
  distance_multiplier: number;
  is_objective_area: boolean;
  carrier_multiplier: number;
  push_multiplier: number;
  crossfire_multiplier: number;
  spawn_multiplier: number;
  outcome_multiplier: number;
  class_multiplier: number;
  is_carrier_kill: boolean;
  is_during_push: boolean;
  is_crossfire: boolean;
}

// ── Momentum Chart ──
export interface MomentumPoint {
  t_ms: number;
  axis: number;
  allies: number;
}

export interface MomentumRound {
  round_number: number;
  map_name: string;
  points: MomentumPoint[];
}

export interface MomentumResponse {
  status: string;
  session_date: string;
  rounds: MomentumRound[];
}

// ── Session Narrative ──
export interface NarrativeResponse {
  status: string;
  session_date: string;
  narrative: string;
}

// ── Player Narratives ──
export interface PlayerNarrativeMetrics {
  gravity: number;
  space_score: number;
  enabler_score: number;
  solo_pct: number;
  kills: number;
  total_kis: number;
  archetype: string;
  clutch_kills: number;
  carrier_kills: number;
  denied_time: number;
  revives: number;
}

export interface PlayerNarrative {
  guid_short: string;
  name: string;
  narrative: string;
  archetype: string;
  top_trait: string;
  metrics: PlayerNarrativeMetrics;
}

export interface PlayerNarrativesResponse {
  status: string;
  session_date: string;
  player_narratives: PlayerNarrative[];
}
