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
  efficiency?: number;
  alive_percent?: number;
  played_percent?: number;
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
  session_id: number;
  date: string | null;
  player_count: number;
  round_count: number;
  matches: SessionMatch[];
  players: SessionPlayer[];
  scoring: SessionScoring;
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
  suggestions: PlanningSuggestion[];
  teams: Record<string, { members: Array<{ user_id: number }> }>;
}

export interface PlanningState {
  session: PlanningSession | null;
  participants: PlanningParticipant[];
  unlocked: boolean;
  session_ready: AvailabilitySessionReady;
  viewer: { website_user_id: number };
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
