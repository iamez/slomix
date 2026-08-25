/**
 * Hand-written response types, earned per phase (docs/design/06 §4b): the
 * backend declares almost no response_model, so these shapes are derived from
 * RECORDED responses — each type names its corpus fixture. A wrong field here
 * is a bug against a recording, never against a guess. Keep under 400 lines
 * to switchover; grow it only with the endpoints a phase actually uses.
 */

/** GET /api/live/state — corpus: api_live_state.json */
export interface LiveState {
  status: string;
  is_live: boolean;
  game_state: string;
  current_map: string | null;
  round_number: number | null;
  round_elapsed_seconds: number | null;
  roster: {
    axis: unknown[];
    allies: unknown[];
    spectators: unknown[];
    player_count: number;
    /** Age of the retained roster: the reducer flips is_live off after 180 s
     * but keeps the lineup up to 600 s for clients to QUALIFY, not present
     * as current (LiveStateReducer; Codex on #806, wave 4). */
    roster_age_seconds: number | null;
    has_bots: boolean;
  };
  last_event_age_seconds: number | null;
}

/** GET /api/voice-activity/current — corpus: api_voice_activity_current.json */
export interface VoiceCurrent {
  total_count: number;
  members: unknown[];
  channels: unknown[];
}

/** GET /api/stats/overview — corpus: api_stats_overview.json */
export interface StatsOverview {
  rounds: number;
  players: number;
  sessions: number;
  total_kills: number;
  /** MIN/MAX over the filtered rounds — None on a fresh database, passed
   * through as null (records_overview.py; Codex on #806, wave 3). */
  rounds_since: string | null;
  rounds_latest: string | null;
  rounds_14d: number;
  players_14d: number;
  sessions_14d: number;
  total_kills_14d: number;
  players_all_time: number;
  most_active_overall: { name: string; rounds: number } | null;
  most_active_14d: { name: string; rounds: number } | null;
  window_days: number;
}

/** One row of GET /api/sessions — corpus: api_sessions.json */
export interface SessionSummary {
  date: string;
  session_id: number;
  rounds: number;
  maps: number;
  players: number;
  total_kills: number;
  maps_played: string[];
  /** Team attribution comes from the session's `map_name = 'ALL'` row in
   * session_results — when that row is missing the API deliberately returns
   * null for all four team fields (sessions_router.py; Codex on #806). */
  team_1_name: string | null;
  team_2_name: string | null;
  team_1_score: number | null;
  team_2_score: number | null;
  winning_team: number | null;
  time_ago: string;
  formatted_date: string;
}

/** One row of the quick-leaders boards. The participation field differs per
 * board — xp rows carry `rounds`, dpm_sessions rows carry `sessions`
 * (players_router; Codex on #806) — so both are optional here rather than
 * one board lying about the other's shape. */
export interface QuickLeaderRow {
  rank: number;
  guid: string;
  name: string;
  value: number;
  rounds?: number;
  sessions?: number;
  label: string;
}

/** GET /api/stats/quick-leaders — corpus: api_stats_quick_leaders.json */
export interface QuickLeaders {
  window_days: number;
  xp: QuickLeaderRow[];
  dpm_sessions: QuickLeaderRow[];
  errors: unknown[];
}
