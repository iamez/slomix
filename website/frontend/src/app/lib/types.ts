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
  /** Map wins by SIDE (sides swap every map) — the sessions2 BOX columns. */
  allies_wins: number;
  axis_wins: number;
  draws: number;
  time_ago: string;
  formatted_date: string;
}

/** One row of the XP board — participation field is `rounds`, mirroring
 * the backend's XpLeaderRow (players_router, #812). A single row type with
 * both fields optional let either board claim the other's shape, which is
 * exactly what response_model now forbids server-side. */
export interface XpLeaderRow {
  rank: number;
  guid: string;
  name: string;
  value: number;
  rounds: number;
  label: string;
}

/** One row of the DPM board — participation field is `sessions`
 * (backend DpmLeaderRow, #812). */
export interface DpmLeaderRow {
  rank: number;
  guid: string;
  name: string;
  value: number;
  sessions: number;
  label: string;
}

/** Either board's row, for shared rendering (rank/name/value only). */
export type QuickLeaderRow = XpLeaderRow | DpmLeaderRow;

/** GET /api/stats/quick-leaders — corpus: api_stats_quick_leaders.json.
 * `errors` is list[str], measured: the producer appends exactly
 * "xp_query_failed" or "dpm_query_failed" (backend QuickLeaders, #812). */
export interface QuickLeaders {
  window_days: number;
  xp: XpLeaderRow[];
  dpm_sessions: DpmLeaderRow[];
  errors: string[];
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

/* ---------- phase 2: home + sessions core (fixtures named per type) ---------- */

/** One R1/R2 row of the last session — corpus: api_stats_last_session.json */
export interface LastSessionMatch {
  id: number;
  map_name: string;
  round_number: number;
  duration: string;
  winner: string;
  outcome: string;
  date: string;
}

/** Per-player line inside last-session teams — only the fields home sums. */
export interface LastSessionPlayer {
  name: string;
  guid: string;
  kills: number;
  headshot_kills: number;
  revives_given: number;
}

/** GET /api/stats/last-session — corpus: api_stats_last_session.json.
 * scoring is the real BOX (2/1/0 per map) with per-map rows. */
export interface LastSession {
  date: string;
  /** null when the latest rounds carry no session id (sessions_router) —
   * the hero then links by DATE instead. */
  gaming_session_id: number | null;
  player_count: number;
  rounds: number;
  maps: string[];
  matches: LastSessionMatch[];
  teams: { name: string; players: LastSessionPlayer[] }[];
  /** Substitutes and players mapped to neither persistent team — the
   * evening totals must include them (Codex on #811). */
  unassigned_players: LastSessionPlayer[];
  scoring: {
    available: boolean;
    team_a_name: string;
    team_b_name: string;
    team_a_score: number;
    team_b_score: number;
  };
  warnings: unknown[];
}

/** GET /api/stats/trends?days= — corpus: api_stats_trends.json */
export interface StatsTrends {
  dates: string[];
  rounds: number[];
  active_players: number[];
  kills: number[];
  map_distribution: Record<string, number>;
}

/** One row of GET /api/stats/matches — corpus: api_stats_matches.json.
 * axis/allies score fields are null in the recording — read as nullable. */
export interface MatchRow {
  id: number;
  map_name: string;
  round_number: number;
  duration: string;
  winner: string;
  outcome: string;
  date: string;
  time_ago: string;
  /** null when the round could not be attributed to a session — the link
   * then falls back to the date route (Codex on #811, wave 2). */
  gaming_session_id: number | null;
  team1_players: string[];
  team2_players: string[];
  team1_name: string;
  team2_name: string;
  player_count: number;
  format: string;
}

/** GET /api/seasons/current — corpus: api_seasons_current.json */
export interface SeasonCurrent {
  id: string;
  name: string;
  days_left: number;
  start_date: string;
  end_date: string;
  next_season_name: string;
  next_season_start: string;
}

/** GET /api/seasons/current/leaders — corpus: api_seasons_current_leaders.json.
 * A metric can be null (longest_session in the recording). */
export interface SeasonLeaders {
  leaders: Record<string, { player: string; value: number } | null>;
}

/** GET /api/seasons/current/summary — corpus: api_seasons_current_summary.json */
export interface SeasonSummary {
  season_id: string;
  totals: {
    rounds: number;
    players: number;
    sessions: number;
    maps: number;
    kills: number;
  };
  top_map: { name: string; plays: number } | null;
}

/** GET /api/availability — corpus: api_availability.json. Day counts only —
 * names per day live behind a different endpoint, so home shows counts. */
export interface AvailabilityOverview {
  from: string;
  to: string;
  statuses: string[];
  days: { date: string; counts: Record<string, number>; total: number }[];
}

/** One breakdown contribution (Overall only) — corpus: api_skill_movers.json */
export interface SkillMoverBreakdown {
  metric: string;
  label: string;
  delta_pct: number | null;
  latest: number | null;
  baseline: number | null;
}

/** One mover row — corpus: api_skill_movers.json */
export interface SkillMoverRow {
  guid: string;
  name: string;
  latest: number | null;
  /** null when the player has no prior-session average for this metric
   * (skill_router:792) — a missing baseline, not a zero one. */
  baseline: number | null;
  delta_pct: number | null;
  series: number[];
  is_new: boolean;
  /** Empty for new players; per-metric contributions otherwise. */
  breakdown: SkillMoverBreakdown[];
  /** Present when a new-looking GUID is a linked sick-leave alternate of a
   * known player (skill_router:934) — the UI must not call them new. */
  sick_leave?: { primary_name: string; active?: boolean } | null;
}

/** GET /api/skill/movers — corpus: api_skill_movers.json */
export interface SkillMovers {
  status: string;
  session_date: string | null;
  metric_label: string;
  movers_up: SkillMoverRow[];
  movers_down: SkillMoverRow[];
  new_players: SkillMoverRow[];
}

/** GET /api/challenges/current — corpus: api_challenges_current.json
 * (challenge is null most weeks — the card renders only when it exists). */
export interface ChallengeCurrent {
  status: string;
  week_start_date: string;
  challenge: { title?: string; description?: string } | null;
}

/** GET /api/stats/tonight — corpus: api_stats_tonight.json */
export interface TonightStatus {
  status: string;
  active: boolean;
}

/** GET /api/live-status — fixture api_live_status.json RECORDED FRESH from
 * the live backend on 2026-08-25: the corpus copy from 24. 8. held a feed
 * -buffer shape ({buffered,last_seq}), not this one — measured, not
 * assumed. One endpoint carries both the game server and the voice room. */
export interface LiveStatus {
  voice_channel: {
    members: unknown[];
    count: number;
    channel_name: string;
    /** true when the voice read failed INSIDE a 200 — count is then an
     * initialized zero, not a measurement (Codex on #811, wave 3). */
    error?: boolean;
  };
  game_server: {
    online: boolean;
    hostname: string;
    map: string | null;
    player_count: number;
    max_players: number;
    ping_ms: number | null;
  };
}

/** GET /api/stats/activity-calendar?days= — corpus: api_stats_activity_calendar.json */
export interface ActivityCalendar {
  days: number;
  activity: Record<string, number>;
}

/* ---------- phase 2, batch 2: leaderboards · record-book · awards ---------- */

/** One row of GET /api/stats/leaderboard — corpus: api_stats_leaderboard.json.
 * `deaths` exists in the payload; legacy never rendered it. */
export interface LeaderboardRow {
  rank: number;
  guid: string;
  name: string;
  value: number;
  rounds: number;
  kills: number;
  deaths: number;
  kd: number;
}

/** One record holder — corpus: api_stats_records.json (map of category →
 * top-N rows, FE orders the categories itself). */
export interface RecordEntry {
  player: string;
  value: number;
  map: string;
  date: string;
}
export type StatsRecords = Record<string, RecordEntry[]>;

/** One map row of GET /api/stats/maps — corpus: api_stats_maps.json (only
 * the fields this batch reads; the maps PAGE in batch 3 will widen it). */
export interface MapRow {
  name: string;
  total_rounds: number;
}

/** GET /api/hall-of-fame — corpus: api_hall_of_fame.json. rank_delta/is_new
 * appear only when delta_window_days is set (recording has null). */
export interface HallOfFameEntry {
  rank: number;
  /** null for historical aggregates no alias map resolves
   * (valid_human_rows_gate permits them) — no profile link then. */
  player_guid: string | null;
  player_name: string;
  value: number;
  unit: string;
  rank_delta?: number;
  is_new?: boolean;
}
export interface HallOfFame {
  categories: Record<string, HallOfFameEntry[]>;
  period: string;
  delta_window_days: number | null;
}

/** GET /api/seasons/current/awards — corpus: api_seasons_current_awards.json
 * (engraved awards are [] until a season is closed — empty is the NORMAL
 * state, not a failure). */
export interface SeasonAwards {
  status: string;
  season_id: string;
  season_name: string;
  awards: { award_key?: string; key?: string; label?: string; player_guid?: string; player_name?: string; value_text?: string }[];
}

/** One row of GET /api/awards — corpus: api_awards.json. value is a STRING
 * ("48.54 percent", "2") — the backend formats it. */
export interface AwardRow {
  award: string;
  player: string;
  guid: string;
  value: string;
  date: string;
  map: string;
  round_number: number;
  round_id: number | null;
}
export interface AwardsPage {
  awards: AwardRow[];
  total: number;
  limit: number;
  offset: number;
}

/** One row of GET /api/awards/leaderboard — corpus:
 * api_awards_leaderboard.json. The field is top_award — legacy read
 * favorite_award and silently got an empty dropdown out of it. */
export interface AwardLeaderRow {
  rank: number;
  player: string;
  /** null when neither alias map resolves the historical winner
   * (records_awards.py) — no profile link then. */
  guid: string | null;
  award_count: number;
  top_award: string;
  top_award_count: number;
}
export interface AwardsLeaderboard {
  leaderboard: AwardLeaderRow[];
}

/* ---------- phase 2, batch 3: maps · weapons · form · retro-viz ---------- */

/** Full map row (widening batch-2's MapRow) — corpus: api_stats_maps.json.
 * Win rates are null when no side ever won — legacy defaulted them to 50,
 * an invented middle; here null renders a dash. */
export interface MapStatsRow {
  name: string;
  total_rounds: number;
  matches_played: number;
  allies_wins: number;
  axis_wins: number;
  allies_win_rate: number | null;
  axis_win_rate: number | null;
  /** 0 is the endpoint's sentinel for "no parseable duration", not a
   * measured zero — keep it out of fastest-map math. */
  avg_duration: number;
  /** null when every valid row for the map has a null round_date — a
   * supported historical state (records_maps MAX() passes it through). */
  last_played: string | null;
  total_kills: number;
  avg_dpm: number;
  unique_players: number;
  grenade_kills: number;
  panzer_kills: number;
  mortar_kills: number;
}

/** GET /api/records/maps/segments — corpus: api_records_maps_segments.json.
 * winner_side is the SERVER's string; winner_team numeric semantics differ
 * per endpoint family, so this page never interprets the number. */
export interface MapSegmentRecord {
  map_name: string;
  fastest_seconds: number;
  fastest_time: string;
  played: string;
  winner_side: string;
  gaming_session_id: number | null;
}
export interface MapSegments {
  status: string;
  records: MapSegmentRecord[];
}

/** One weapon row — corpus: api_stats_weapons.json. `headshots` are HIT
 * LOCATIONS, not headshot kills (they exceed kills: Mp40 110k kills /
 * 129k head hits) — the label must say 'head hits'. */
export interface WeaponRow {
  name: string;
  weapon_key: string;
  kills: number;
  headshots: number;
  hs_rate: number;
  accuracy: number;
}

/** GET /api/stats/weapons/hall-of-fame — corpus:
 * api_stats_weapons_hall_of_fame.json (object keyed by weapon_key). */
export interface WeaponsHallOfFame {
  period: string;
  leaders: Record<string, {
    weapon: string;
    weapon_key: string;
    player_guid: string;
    player_name: string;
    kills: number;
    headshots: number;
    accuracy: number;
  }>;
}

/** GET /api/stats/weapons/by_player — corpus:
 * api_stats_weapons_by_player.json. The by-player hs_rate is headshots/hits
 * — a HEAD-HIT rate, never a kill rate (records_weapons.py:150). */
export interface WeaponsByPlayer {
  period: string;
  player_count: number;
  players: {
    player_guid: string;
    player_name: string;
    total_kills: number;
    weapons: (WeaponRow & { deaths: number; shots: number; hits: number })[];
  }[];
}

/** One round in the retro-viz picker — corpus: api_rounds_recent.json.
 * round_number 0 is the legacy Match Summary aggregate and is filtered out. */
export interface RecentRound {
  id: number;
  map_name: string;
  round_date: string;
  round_number: number;
  round_label: string;
  player_count: number;
}

/** One player of GET /api/rounds/{round_id}/viz — corpus:
 * api_rounds_round_id_viz.json. */
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
  denied_playtime: number;
  gibs: number;
  dpm: number;
  efficiency: number;
  xp: number;
}

/** GET /api/rounds/{round_id}/viz. In THIS endpoint's convention
 * winner_team 1 = Axis, 2 = Allies (retro-viz.js mapping) — other
 * families disagree on the number, so it never leaves this page. */
export interface RoundViz {
  round_id: number;
  map_name: string;
  round_date: string;
  round_number: number;
  round_label: string;
  winner_team: number | null;
  /** null for historical rounds without a measured duration — unknown,
   * not zero (records_matches reads actual_duration_seconds raw). */
  duration_seconds: number | null;
  player_count: number;
  players: VizPlayer[];
  /** Keyed object, NOT an array (records_matches:446); {} for empty rounds. */
  highlights: {
    mvp?: { name: string; dpm: number };
    most_kills?: { name: string; kills: number };
    most_damage?: { name: string; damage_given: number };
  };
}

/** GET /api/stats/session/{id}/lineups — corpus: api_stats_session_gaming_session_id_lineups.json
 * (session 153: two trios, and a real mid-evening team switch). Derived from
 * lua_round_teams per-round rosters (cumulative since webhook v1.7.3). */
export interface LineupPlayer {
  guid: string;
  name: string;
}

export interface LineupSwap {
  out: LineupPlayer;
  incoming: LineupPlayer;
}

/** Membership delta of ONE team between two consecutive rounds. A player
 * moving BETWEEN teams appears as joined on one team and left on the other
 * in the same round — the UI folds that mirror pair into a single switch. */
export interface LineupChange {
  map_name: string;
  round_number: number;
  round_id: number;
  team: 'a' | 'b' | string;
  joined: LineupPlayer[];
  left: LineupPlayer[];
  swaps: LineupSwap[];
}

export interface TeamLineup {
  key: 'a' | 'b' | string;
  name: string;
  players: LineupPlayer[];
}

export interface SessionLineups {
  gaming_session_id: number;
  teams: TeamLineup[];
  changes: LineupChange[];
  /** Rounds with no lua roster (pre-webhook history) — an unmeasured
   * stretch, never "no changes". */
  rounds_without_roster: number;
}
