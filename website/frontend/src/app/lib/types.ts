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
  /** From #808, not yet in the OpenAPI spec — read defensively. false means
   * no event since the last session boundary has confirmed the retained
   * map; the age is since the last CONFIRMATION (any map event, including
   * one naming the same map), null while unconfirmed. */
  map_confirmed?: boolean;
  map_age_seconds?: number | null;
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
  /** From #808 (defensive until response_model): 'ok' | 'stale' |
   * 'unavailable' — a malformed live_status row used to return the same
   * empty 200 as a genuinely empty channel, and a bot outage used to
   * present the last row as current forever. */
  status?: string;
  /** Server-measured snapshot age (#808) — the backend's own 180 s
   * staleness verdict travels with it, so the frontend never re-decides
   * freshness with the CLIENT's clock. */
  age_seconds?: number | null;
  total_count: number;
  /** Not returned by the endpoint today — the row's updated_at exists in the
   * database but is neither exposed nor validated (diagnostics_router;
   * Codex on #806, wave 5). Read defensively so the page starts qualifying
   * staleness the moment the backend exposes it (response_model work). */
  updated_at?: string | null;
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

/** One stage of the capture chain. detail keys vary per stage. */
export interface SystemStage {
  key: string;
  label: string;
  state: 'ok' | 'idle' | 'warn' | 'down' | 'unknown' | string;
  summary: string;
  detail: Record<string, unknown>;
}

/** GET /api/system/overview — corpus: api_system_overview.json */
export interface SystemOverview {
  generated_at: string;
  overall: SystemStage['state'];
  stages: SystemStage[];
  linkage: {
    available: boolean;
    /** assess_round_linkage_anomalies returns 'error' with PARTIAL metrics
     * when a subquery fails — an empty breaches list then proves nothing
     * (Codex on #809). */
    status?: string;
    metrics?: Record<string, number>;
    breach_count?: number;
    breaches?: { metric: string; value: number; threshold: number }[];
  };
}

/** GET /api/diagnostics/storytelling-completeness — corpus:
 * api_diagnostics_storytelling_completeness.json */
export interface StorytellingCompleteness {
  session_date: string;
  session_dates: string[];
  gaming_session_id: number | null;
  scope: string;
  status: string;
  kills_total: number;
  kills_with_round: number;
  unlinked_kills: number;
  wrong_round_kills: number;
  distinct_rounds_in_kills: number;
  kis_rows: number;
  kis_computed: boolean;
  rounds_total: number;
  rounds_correlated: number;
  completeness_ratio: number | null;
  linkage_ratio: number | null;
  correlation_ratio: number | null;
  kis_total_impact_sum: number | null;
  warnings: { level: string; message: string }[];
  known_issues: { key: string; title: string; detail: string }[];
}

/** GET /api/build — NOT in the OpenAPI spec (include_in_schema=False, by
 * design: it identifies the process, it is not part of the data contract).
 * Fixture recorded by hand from the live backend: api_build.json */
export interface BuildInfo {
  revision: string;
  /** null when the deployment has no .git directory (build_info.py). */
  revision_short: string | null;
  started_at: string;
  api_contract: string;
  /** null when migrations are not packaged with the deployment. */
  schema_ledger_max_file: string | null;
}
