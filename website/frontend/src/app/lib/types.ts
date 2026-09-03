/**
 * Hand-written response types, earned per phase (docs/design/06 §4b): the
 * backend declares almost no response_model, so these shapes are derived from
 * RECORDED responses — each type names its corpus fixture. A wrong field here
 * is a bug against a recording, never against a guess. Keep under 400 lines
 * to switchover; grow it only with the endpoints a phase actually uses.
 */

/** GET /api/live/state — corpus: api_live_state.json */
export interface LiveRosterMember {
  slot: number;
  name: string;
  on_server_seconds: number;
  on_side_seconds: number;
  live?: {
    kills: number; deaths: number; damage: number;
    dpm: number | null; alive: boolean;
  };
}

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
    axis: LiveRosterMember[];
    allies: LiveRosterMember[];
    spectators: LiveRosterMember[];
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
  /** "ok" when every query answered, "partial" when at least one did not —
   *  the zeros below then mean MISSING, not measured. `failed_metrics` names
   *  which ones (#830). */
  status: string;
  note: string | null;
  failed_metrics: string[];
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
  /** NOT nullable — every one has an `else 0.0` in diagnostics_router, so a
   *  missing denominator answers 0, never null. Measured on three sessions
   *  (154, 153, 152): 1.0 / 1.0 / 1.0 and a real impact sum each time.
   *  Typing them nullable cost nothing at runtime and bought a dead branch
   *  in `ratioState`, which is the mirror of the AwardRow.round_id mistake:
   *  a guard placed where nothing can arrive. */
  completeness_ratio: number;
  linkage_ratio: number;
  correlation_ratio: number;
  kis_total_impact_sum: number;
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
  /** NULLABLE, and not because today's data says so — it does not. The
   *  brother widened these on #830 after Codex traced the path:
   *  `get_session_matches_by_round_ids()` selects `rounds.map_name` and
   *  `round_date` with no filter on either, and both columns are nullable.
   *  Measured on the live payload: 0 of 12 matches carry a null, so this is
   *  the branch that has not happened yet rather than the one that cannot.
   *  A `| null` the data never triggers costs one `??`; a non-null type the
   *  data contradicts is a broken render on a page that was working. */
  map_name: string | null;
  round_number: number;
  duration: string;
  winner: string;
  outcome: string;
  date: string | null;
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
export type LastSessionScoring =
  | {
    available: true;
    team_a_name: string;
    team_b_name: string;
    team_a_score: number;
    team_b_score: number;
  }
  | { available: false; reason?: string };

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
  /* A SUBSET by design: the response also carries `map_counts` and
   * `stats_checks`, which nothing on this page renders. Absent from the type
   * because unused, not because unsent (#830). */
  /** A DISCRIMINATED UNION, because the endpoint answers with two different
   *  shapes and the short one carries neither names nor scores:
   *
   *      available: true   → 8 keys (names, scores, maps, debug)
   *      available: false  → 2 keys: {available, reason}
   *
   *  All eight sessions in the database answer the long form, so a type read
   *  off the corpus would have made the names required — and 500'd (or here,
   *  crashed) the first time a session took one of the four early returns.
   *  The brother forced the short form on #830 to measure it. Written as a
   *  union rather than one shape with optional fields, so the compiler makes
   *  the `available` check mandatory before a name can be read. */
  scoring: LastSessionScoring;
  warnings: unknown[];
}

/** GET /api/stats/trends?days= — corpus: api_stats_trends.json */
export interface StatsTrends {
  dates: string[];
  /** OPTIONAL, not nullable: `?metrics=rounds` returns `{dates, rounds}`
   *  with `kills` ABSENT — measured by the brother on #830, where the route
   *  gains `response_model_exclude_none`. The key is missing, so the check
   *  is on PRESENCE; reading these as nullable is the shape of the
   *  `total_votes` crash. This page never filters, so it receives all four
   *  today — which is precisely the reasoning that failed on session 154,
   *  so the type states the contract rather than this caller's habit. */
  rounds?: number[];
  active_players?: number[];
  kills?: number[];
  map_distribution?: Record<string, number>;
}

/** One row of GET /api/stats/matches — corpus: api_stats_matches.json.
 * axis/allies score fields are null in the recording — read as nullable. */
export interface MatchRow {
  id: number;
  /** Nullable for the same reason as LastSessionMatch, and by the same rule
   *  rather than a different mood: `get_recent_matches` selects
   *  `r.map_name` and `r.round_date` under `WHERE r.round_number IN (1, 2)`
   *  and filters neither, and both columns are nullable. Measured
   *  2026-08-30: 0 nulls in 3,176 rounds and 0 in 100 sampled matches — a
   *  branch that has not happened, not one that cannot. (Contrast
   *  `round_start_unix`, nullable in the SAME table with 2,185 nulls, of
   *  which the newest is from 2026-08-27: that one is live.) */
  map_name: string | null;
  round_number: number;
  duration: string;
  winner: string;
  outcome: string;
  date: string | null;
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
/** A deliberate SUBSET: the response also carries `start_date` and
 *  `end_date`, which nothing renders — the board shows the season window
 *  from /seasons/current instead. (The brother's checker reports this type
 *  as absent from the API; that is a NAME collision, not drift — his schema
 *  for this route is `SeasonLeadersResponse`, and `SeasonLeaders` there is
 *  the inner object.) */
export interface SeasonLeaders {
  /** Same contract as SeasonSummary (#862): partial names its missing
   *  categories; a leaders board with a failed category must say WHICH. */
  status: string;
  note: string | null;
  failed_metrics: string[];
  leaders: Record<string, { player: string; value: number } | null>;
}

/** GET /api/seasons/current/summary — corpus: api_seasons_current_summary.json */
export interface SeasonSummary {
  /** "ok" or "partial" — REQUIRED on the wire (no model default, so a
   *  handler path that forgets fails loudly, #862). When partial,
   *  failed_metrics NAMES what is missing and the zeros below it mean
   *  MISSING, not measured — the same contract as /stats/overview. */
  status: string;
  note: string | null;
  failed_metrics: string[];
  season_id: string;
  start_date: string;
  end_date: string;
  totals: {
    rounds: number;
    players: number;
    sessions: number;
    maps: number;
    kills: number;
    active_days: number;
    /** int OR float on the wire: a real season answers 13.1, an empty one
     *  answers 0 as an integer (#830). `number` covers both in TS; the note
     *  is here so nobody formats it assuming a decimal. */
    avg_rounds_per_day: number;
  };
  /** ⚠️ The NULL is inside, not outside. This said
   *  `{ name: string; plays: number } | null`, which defended against a case
   *  that does not happen and promised one that does: a season with no
   *  rounds answers `{"name": null, "plays": 0}` — the object is always
   *  there, the name is what goes missing (#830). Nullability at the wrong
   *  level is not a smaller mistake than no nullability at all. */
  top_map: { name: string | null; plays: number };
}

/** GET /api/availability — corpus: api_availability.json. Day counts only —
 * names per day live behind a different endpoint, so home shows counts. */
/** One day in the window. `my_status` has THREE states and they are not
 *  interchangeable (#830 measured all three on one range):
 *
 *      key absent   the question was never asked — an anonymous caller
 *      null         asked, and this viewer has set nothing (50 of 55 days)
 *      "LOOKING"    asked and answered (5 days)
 *
 *  Optional AND nullable is the honest shape here, which is rare: usually
 *  one of the two is the wrong tool. `users_by_status` only appears for a
 *  signed-in caller who asked for it. */
export interface AvailabilityDay {
  date: string;
  counts: Record<string, number>;
  total: number;
  my_status?: string | null;
  users_by_status?: Record<string, unknown[]>;
}

export interface AvailabilityOverview {
  from: string;
  to: string;
  statuses: string[];
  days: AvailabilityDay[];
  /** Who is asking, as the server sees them. ALWAYS sent: the handler has a
   *  single return and both this and `session_ready` are in it — marking
   *  them optional was the same over-permissive mistake as a `| null` the
   *  data cannot produce, and it made every reader check for an absence
   *  that does not happen (brother's checker, #830). */
  viewer: { authenticated: boolean; linked_discord: boolean };
  /** How far tonight is from happening: the threshold is the server's, not
   *  the page's, so a card that quotes it cannot drift from the rule that
   *  actually fires the Discord notice. */
  session_ready: {
    date: string;
    ready: boolean;
    looking_count: number;
    threshold: number;
    event_key: string;
  };
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
  /** Three states, and the page must not collapse them: `ok` (measured),
   *  `no_data` (measured and empty) and `unavailable` (the query failed and
   *  the endpoint still answered 200). REQUIRED since #830 landed — the
   *  "optional until it arrives" hedge outlived the arrival, which is
   *  exactly the drift check_manual_types_against_openapi exists to catch
   *  (its first run with a caller, #860, named these six). `note` carries
   *  the reason and is null when the state is ok. */
  status: string;
  note?: string | null;
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
  /** Nullable from #830 onward: the aggregate can be NULL and the model
   *  says so. Measured 0 nulls in 3,176 rows today — this is the branch
   *  that has not happened yet, not the one that cannot.
   *
   *  ⚠️ Rendered as "—", never as 0: a player with an unknown kill count
   *  and a player who killed nobody are different facts, and the column is
   *  auxiliary here (the picked stat is `value`). */
  kills: number | null;
  deaths: number | null;
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
/** Nineteen categories, EVERY ONE optional — measured on #830:
 *  `?map_name=goldrush` (a real ET map this server never recorded) answers
 *  `{}` with HTTP 200 and all nineteen keys absent, while all eighteen maps
 *  that do have data answer with all nineteen.
 *
 *  ⚠️ And absence means the opposite of what it looks like: a MISSING key is
 *  "the query ran and found nothing", while a key present as `[]` is "the
 *  query threw and a per-category except swallowed it". `| undefined` is
 *  what makes the first case visible to the compiler — this alias used to
 *  promise every key was there, and `RecordBook.tsx` only survived because
 *  it happened to guard with `?.` anyway.
 *
 *  (An alias, not an interface: the brother's checker reads interfaces only,
 *  so it reported "agree" over ZERO compared schemas here — an empty
 *  comparison and a clean one have the same shape. It says NOT COMPARED now.
 *  This one is checked by hand against the generated schema.) */
export type StatsRecords = Record<string, RecordEntry[] | undefined>;

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
  /** When the board was computed — the page can say how old it is. */
  generated_at: string;
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
  /** Null when the winning legacy row carries no guid — the page already
   *  guarded the link; only this type lied (one null 500d the endpoint). */
  guid: string | null;
  value: string;
  date: string;
  map: string;
  round_number: number;
  /** NOT nullable, and this type said it was. `round_awards.round_id` is
   *  NOT NULL in the schema (measured: 0 of 26,301 rows), and the response
   *  model declares `int`, so a null could not reach a client — the
   *  endpoint would 500 first. Found by the brother's
   *  check_manual_types_against_openapi.py (#830), which is the first thing
   *  that ever compared these 75 hand-written interfaces to the generated
   *  schema. */
  round_id: number;
}
/** The filter set the response echoes back — every field null when the
 *  request carried no such filter. */
export interface AwardsFilters {
  player: string | null;
  award_type: string | null;
  days: number | null;
}

export interface AwardsPage {
  awards: AwardRow[];
  total: number;
  limit: number;
  offset: number;
  filters: AwardsFilters;
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
/** Every field the schema declares. `deaths`, `shots` and `hits` used to be
 *  bolted onto the by-player variant with an intersection, as though the
 *  base row lacked them — the schema says otherwise and always did. */
export interface WeaponRow {
  name: string;
  weapon_key: string;
  kills: number;
  deaths: number;
  headshots: number;
  hs_rate: number;
  accuracy: number;
  shots: number;
  hits: number;
}

/** GET /api/stats/weapons/hall-of-fame — corpus:
 * api_stats_weapons_hall_of_fame.json (object keyed by weapon_key). */
export interface WeaponsHallOfFame {
  period: string;
  /** Same three states as the activity calendar: `ok`, `no_data`,
   *  `unavailable` — it, not the emptiness of `leaders`, decides whether
   *  this is an outage rather than a quiet season. Required since #830
   *  landed (same drift, same first-run catch). */
  status: string;
  note?: string | null;
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
export interface PlayerWeapons {
  player_guid: string;
  player_name: string;
  total_kills: number;
  weapons: WeaponRow[];
}

export interface WeaponsByPlayer {
  period: string;
  player_count: number;
  players: PlayerWeapons[];
}

/** One round in the retro-viz picker — corpus: api_rounds_recent.json.
 * round_number 0 is the legacy Match Summary aggregate and is filtered out. */
export interface RecentRound {
  id: number;
  /** Schema-nullable only: 0 nulls in 3,176 rows, and no handler branch
   *  produces one. Typed nullable anyway on the brother's reasoning, which
   *  I agree with — a `| null` the data never triggers costs one `??`,
   *  while a non-null type the data contradicts is a broken render on a
   *  page that was working. */
  map_name: string | null;
  /** NULLABLE, not optional — the key is always present and the value can be
   *  null: `records_matches.py` emits `str(row[2]) if row[2] else None`. The
   *  brother's typing pass (#830) confirmed the same for `round_number`.
   *  Nullable means check the VALUE; optional would mean check presence, and
   *  conflating the two is how a page ends up rendering nothing where it
   *  should say something. */
  round_date: string | null;
  round_number: number | null;
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
  /** Nullable in the spec — the round row's map_name column allows it
   *  (same class as the two names #841 fixed). */
  map_name: string | null;
  /** Nullable in the handler — `str(row[2]) if row[2] else None`, the same
   *  expression as /rounds/recent. Neither of us has ever seen a null here;
   *  the branch exists, so the type says so and the page prints "unknown"
   *  rather than a blank cell (#830). */
  round_date: string | null;
  round_number: number | null;
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

/** One player's line in one round, as `/stats/session/{id}/rounds` returns it.
 *
 * ⚠️ Written from the MEASURED response, not from the field list — the three
 * fields the rest of the site omits per round (`time_played_seconds`, `gibs`,
 * `damage_received`) are the reason that endpoint exists.
 */
export interface RoundPlayerRow {
  player_guid: string;
  player_name: string;
  team: number;
  time_played_seconds: number;
  gibs: number;
  damage_received: number;
  damage_given: number;
  kills: number;
  deaths: number;
  headshots: number;
  headshot_kills: number;
  revives_given: number;
  times_revived: number;
  xp: number;
}

export interface SessionRound {
  round_id: number;
  map_name: string;
  round_number: number;
  played_at: string;
  /** Null when neither the Lua mirror nor a parseable clock survived. */
  duration_seconds: number | null;
  end_reason: string | null;
  /** 'completed' | 'substitution' | 'cancelled' | null — shown, never hidden. */
  round_status: string | null;
  /** False for a cancelled round: show it, leave it out of totals. */
  counts_toward_totals: boolean;
  match_id: string | null;
  players: RoundPlayerRow[];
}

export interface SessionRounds {
  gaming_session_id: number;
  session_date: string | null;
  counted_rounds: number;
  total_rounds: number;
  rounds: SessionRound[];
}

/* ---------- phase 3: the player ---------- */

/** GET /api/players/{id}/profile — corpus:
 * api_players_identifier_profile.json (recorded with sections=all for vid).
 * EVERY section carries `available`: a section can be off (no capture, no
 * rows, a failed sub-query) while the response is a 200, so the page must
 * read the flag rather than the emptiness of the list below it. */
export interface ProfileSection {
  available: boolean;
  /** Present when a section failed or was skipped — an UNAVAILABLE section
   * carries ONLY {available, reason}: every list/object below is absent,
   * not empty (players_profile_router `_ok`). */
  reason?: string;
}

export interface ProfileIdentity extends ProfileSection {
  /** All optional: identity passes through the same `_ok` wrapper, so a
   * failed subquery leaves {available:false} and nothing else. */
  guid?: string;
  name?: string;
  aliases?: string[];
  first_seen?: string | null;
  last_seen?: string | null;
  rounds?: number;
  discord_linked?: boolean;
  /** OBJECTS, not strings (players_profile_router:118-122): the locale-derived
   * flag is not a verified country, and the twitch handle carries its url. */
  country?: { flag?: string; country?: string; locale?: string } | null;
  twitch?: { login?: string; url?: string } | null;
  /** Sick-leave / alt attribution (migration 073). Two shapes, both measured
   * live: an ALT carries {role:'alt', primary_guid, primary_name, active,
   * since}, a PRIMARY carries {role:'primary', alts:[…]}. Statistics stay
   * separate per GUID — this is attribution only. */
  identity_link?: {
    role: 'alt' | 'primary' | string;
    link_type?: string;
    reason?: string | null;
    primary_guid?: string;
    primary_name?: string;
    active?: boolean;
    since?: string | null;
    alts?: { alt_guid: string; alt_name: string; link_type?: string; active?: boolean; since?: string | null }[];
  } | null;
}

export interface ProfileLifetime extends ProfileSection {
  rounds: number;
  wins: number;
  losses: number;
  win_rate: number;
  kills: number;
  deaths: number;
  kd: number;
  gibs: number;
  headshots: number;
  headshot_kills: number;
  damage_given: number;
  damage_received: number;
  time_played_seconds: number;
  xp: number;
}

export interface ProfileSkill extends ProfileSection {
  et_rating: number | null;
  tier: string | null;
  games_rated: number;
  rank: number | null;
  total_rated: number | null;
  percentile: number | null;
}

export interface ProfileStreaks extends ProfileSection {
  current_streak: number;
  /** 'W' | 'L' — the side of the current run. */
  current_type: string | null;
  longest_win: number;
  longest_loss: number;
}

export interface ProfileWeaponRow {
  weapon: string;
  kills: number;
  deaths: number;
  /** HIT LOCATIONS, not headshot kills — they legitimately exceed kills. */
  headshots: number;
  shots: number;
  hits: number;
  accuracy: number;
  hs_accuracy: number;
}

export interface ProfileWeapons extends ProfileSection {
  weapons?: ProfileWeaponRow[];
  overall_accuracy: number | null;
  overall_hs_accuracy: number | null;
}

export interface ProfileHitRegions extends ProfileSection {
  totals?: {
    head: number; arms: number; body: number; legs: number;
    head_pct: number; arms_pct: number; body_pct: number; legs_pct: number;
  } | null;
}

export interface ProfileMovement extends ProfileSection {
  tracks?: number;
  avg_speed: number | null;
  peak_speed: number | null;
  sprint_pct: number | null;
  avg_distance_per_life: number | null;
  stance?: {
    standing_pct: number; crouching_pct: number; prone_pct: number;
  } | null;
}

export interface ProfileOpponent {
  guid: string;
  name: string;
  kills_by_player: number;
  kills_on_player: number;
  total_encounters: number;
  /** 0..1 from this endpoint (NOT a percentage) — the page formats it. */
  win_rate: number | null;
  classification?: string;
}

export interface ProfileTeammate {
  guid: string;
  name: string;
  rounds_together: number;
  dpm_with: number | null;
  /** The DPM DELTA while playing together — this is what the backend SORTS
   * the teammate lists by (players_profile_router:516), so it is the figure
   * the column has to lead with. */
  synergy: number | null;
  /** percent here, unlike ProfileOpponent.win_rate — measured, not assumed. */
  win_rate_with: number | null;
}

export interface ProfileRelationships extends ProfileSection {
  top_killers?: ProfileOpponent[];
  top_victims?: ProfileOpponent[];
  best_teammates?: ProfileTeammate[];
  worst_teammates?: ProfileTeammate[];
  baseline_dpm: number | null;
}

export interface ProfileMapRow {
  map: string;
  rounds: number;
  wins: number;
  win_rate: number | null;
  kd: number | null;
  dpm: number | null;
}

export interface ProfileMaps extends ProfileSection {
  maps?: ProfileMapRow[];
}

export interface ProfileMatchRow {
  round_id: number;
  date: string;
  map: string;
  round_number: number;
  kills: number;
  deaths: number;
  kd: number | null;
  dpm: number | null;
  /** 'W' | 'L' | null — null when the round has no attributed winner. */
  result: string | null;
}

export interface ProfileRecentMatches extends ProfileSection {
  matches?: ProfileMatchRow[];
}

export interface PlayerProfile {
  guid: string;
  generated_at: string;
  /** Which sections this response actually carries (sorted, server-side). */
  sections: string[];
  identity: ProfileIdentity;
  lifetime: ProfileLifetime;
  skill: ProfileSkill;
  streaks: ProfileStreaks;
  weapons: ProfileWeapons;
  hit_regions: ProfileHitRegions;
  movement: ProfileMovement;
  relationships: ProfileRelationships;
  maps: ProfileMaps;
  recent_matches: ProfileRecentMatches;
}

/* ── Rivalries (docs/design/12 row 25) ────────────────────────────────────
 * Both endpoints answer with `resolved`, which exists because the empty
 * answer and the unresolvable id used to have the same shape: a player with
 * fourteen opponents looked exactly like a player with none when the short
 * GUID was passed (measured 2026-08-28). */

export interface RivalryPair {
  guid1: string;
  guid2: string;
  name1: string;
  name2: string;
  kills_1to2: number;
  kills_2to1: number;
  total: number;
  /** Share of encounters won by name1. */
  win_rate: number;
  classification: string;
}

export interface RivalryLeaderboard {
  status: string;
  pairs: RivalryPair[];
  total: number;
}

export interface RivalryOpponent {
  opponent_guid: string;
  opponent_name: string;
  guid: string;
  name: string;
  kills_by_player: number;
  kills_on_player: number;
  total_encounters: number;
  win_rate: number;
  classification: string;
}

export interface PlayerRivalries {
  status: string;
  /** false = no proximity rows were ever recorded under this id. */
  resolved?: boolean;
  player_guid: string;
  player_name: string | null;
  nemesis: RivalryOpponent | null;
  prey: RivalryOpponent | null;
  rival: RivalryOpponent | null;
  all_pairs: RivalryOpponent[];
  total_opponents: number;
}

/** One weapon in a head-to-head, as the killer used it on the other. */
export interface HeadToHeadWeapon {
  weapon: string;
  kill_mod: number;
  kills: number;
}

export interface HeadToHeadMap {
  map: string;
  p1_kills: number;
  p2_kills: number;
  total: number;
}

/** GET /api/rivalries/h2h/{guid1}/{guid2} — two named players, every duel
 *  between them.
 *
 *  A UNION, and the unresolved branch is the interesting half: it answers
 *  200 (not 404) and NAMES which side could not be resolved
 *  (rivalries_router.py:113-131), which is the difference between "these two
 *  never met" and "one of these ids was never tracked". It also omits
 *  `per_map` entirely rather than sending an empty list, so a consumer that
 *  reads the key without checking `resolved` gets `undefined`, not `[]`.
 *
 *  On the resolved branch nothing is null: `p1_name`/`p2_name` fall back to
 *  the guid prefix (rivalries_service.py:163-165) and `_classify` always
 *  returns a string — INSUFFICIENT_DATA below five meetings rather than
 *  nothing. `map` is NOT NULL in `proximity_kill_outcome` (checked in
 *  information_schema; 0 nulls in 47,385 rows). */
export type HeadToHead =
  | {
    status: string;
    resolved: false;
    /** The ids that could not be resolved — one of them, or both. */
    unresolved: string[];
    guid1: string;
    guid2: string;
    p1_name: null;
    p2_name: null;
    p1_kills: number;
    p2_kills: number;
    total: number;
    win_rate: number;
    classification: null;
    p1_weapons: [];
    p2_weapons: [];
  }
  | {
    status: string;
    resolved: true;
    guid1: string;
    guid2: string;
    p1_name: string;
    p2_name: string;
    p1_kills: number;
    p2_kills: number;
    total: number;
    /** p1's share of the pair's kills. */
    win_rate: number;
    classification: string;
    p1_weapons: HeadToHeadWeapon[];
    p2_weapons: HeadToHeadWeapon[];
    per_map: HeadToHeadMap[];
  };

/* ── ET Rating (v2.1) and SSR (v0.3) ──────────────────────────────────────
 * Two different formulas over the same players. Keeping them in one file is
 * deliberate: the page shows both, and the whole risk is a reader taking a
 * number from one and comparing it with a number from the other. */

export interface RatingComponent {
  raw: number | null;
  weight: number;
  percentile: number | null;
  contribution: number;
}

export interface RatedPlayer {
  rank: number;
  player_guid: string;
  display_name: string;
  et_rating: number;
  games_rated: number;
  last_rated_at: string | null;
  tier: string;
  /** Shrinkage confidence, 0..1 — how far the published number trusts n. */
  confidence: number;
  components: Record<string, RatingComponent>;
}

export interface SkillLeaderboard {
  status: string;
  meta: {
    total: number;
    min_rounds: number;
    weights: Record<string, number>;
    constant: number;
    version: string;
    shrinkage_k: number;
    /** Mean RAW rating over the rated cohort — the shrinkage prior. Null
     * when nothing is rated, which the page says rather than printing 0. */
    pool_mean?: number | null;
  };
  players: RatedPlayer[];
}

export interface SkillFormula {
  status: string;
  version: string;
  name: string;
  description: string;
  formula: string;
  constant: number;
  min_rounds: number;
  shrinkage_k: number;
  normalization: string;
  range: string;
}

export interface SsrComponent {
  raw: number | null;
  pct: number | null;
}

export interface SsrPlayer {
  player_guid: string;
  name: string;
  n_sessions: number;
  ssr: number;
  /** "3/8" — how many of the eight components were measurable at all. */
  coverage: string;
  components: Record<string, SsrComponent>;
}

export interface SsrBoard {
  status: string;
  formula_version: string;
  min_sessions: number;
  min_components: number;
  rated: number;
  players: SsrPlayer[];
}

/** One player in GET /api/skill/adjusted-lifetime — the lifetime rating and
 *  the same rating after a strength-of-schedule correction (SRS over the
 *  persisted per-session rows). Both are on the same 0–1 scale, which is why
 *  the difference between them is the panel's whole point. */
export interface AdjustedLifetimePlayer {
  player_guid: string;
  /** Two branches, and the first version of this type described only one
   *  (Codex on #846). No lifetime row -> the service falls back to the GUID
   *  (measured: the three such players are exactly the three with a null
   *  rating below). A lifetime row whose display_name is NULL -> the null is
   *  passed through UNCHANGED (s_effort_service.py:259). Today's sample has
   *  0 nulls in 28 rows, but the column is nullable — the type follows the
   *  schema, not the sample. */
  name: string | null;
  /** NULL, and by CODE rather than by accident: the rows are built from
   *  `player_skill_history`, and this field is filled only when the player
   *  also appears in `player_skill_ratings` (s_effort_service.py:260 —
   *  `if p in life else None`). Measured 2026-08-30: 3 of 31 players, all
   *  with a single session. The correction then has nothing to correct, and
   *  the page has to say so rather than print a delta against zero. */
  lifetime_rating: number | null;
  adjusted_lifetime: number;
  n_sessions: number;
  formula_version: string;
}

/** GET /api/skill/adjusted-lifetime — global, no scope. `available` is just
 *  `bool(rows)` (skill_router.py:300), so an empty pool answers `false` with
 *  an empty list rather than an error. Pre-sorted by `adjusted_lifetime`
 *  descending. Cold cost measured at 1.0 s — the heaviest of the skill
 *  endpoints, because it recomputes an SRS iteration on every call. */
export interface AdjustedLifetime {
  status: string;
  available: boolean;
  formula_version: string;
  players: AdjustedLifetimePlayer[];
}

// ---------------------------------------------------------------------------
// Smart Stats / storytelling — corpus: api_storytelling_*.json, recorded
// 2026-08-29 against gaming session 154 (12 rounds, 6 maps).
//
// None of these endpoints declares a response_model, so every field below is
// read off a recording AND checked against the handler that builds it
// (storytelling_router.py). Where the two disagree the handler wins: a
// session that happens to have no null today does not make a field non-null.
// ---------------------------------------------------------------------------

/** One entry of GET /api/storytelling/scopes — the session picker's row.
 *  `end_date` differs from `start_date` exactly when the session crossed
 *  midnight, which is why the gsid, not a date, is this page's key. */
export interface StoryScope {
  gaming_session_id: number;
  start_date: string;
  end_date: string;
  accepted_round_count: number;
  distinct_map_names: string[];
  scope_version: string;
}

export interface StoryScopes {
  scope_version: string;
  sessions: StoryScope[];
}

/** GET /api/storytelling/narrative. `session_arc` is built from the map
 *  results and is absent when the session has no completed maps to shape. */
export interface StoryNarrative {
  status: string;
  session_date: string;
  narrative: string;
  session_arc: { shape: string; winner: string; ws: number; ls: number } | null;
}

export interface StoryBoxScoreMap {
  map_number: number;
  map_name: string;
  alpha_points: number;
  beta_points: number;
  winner: string;
  is_fullhold_draw: boolean;
  /** Seconds; null for a half with no recorded time. */
  r1_time: number | null;
  r2_time: number | null;
}

/** GET /api/storytelling/box-score — the scoreboard, straight off the rounds. */
export interface StoryBoxScore {
  status: string;
  gaming_session_id: number;
  alpha_team: string;
  beta_team: string;
  alpha_score: number;
  beta_score: number;
  maps_completed: number;
  winner: string;
  winner_name: string;
  maps: StoryBoxScoreMap[];
}

/** GET /api/storytelling/moments. `detail` varies by `type` — a carrier run
 *  carries distances, a clutch carries counts — so it stays unknown until a
 *  panel needs one specific type and earns that type. */
export interface StoryMoment {
  type: string;
  round_number: number;
  map_name: string;
  time_ms: number;
  player: string;
  narrative: string;
  impact_stars: number;
  time_formatted: string;
  detail?: unknown;
}

export interface StoryMoments {
  status: string;
  moments: StoryMoment[];
  total: number;
}

/** One sample of GET /api/storytelling/momentum: team strength at t_ms. */
export interface StoryMomentumPoint {
  t_ms: number;
  axis: number;
  allies: number;
}

export interface StoryMomentumRound {
  round_number: number;
  map_name: string;
  points: StoryMomentumPoint[];
}

export interface StoryMomentum {
  status: string;
  rounds: StoryMomentumRound[];
}

/** GET /api/storytelling/win-contribution.
 *
 *  `mvp` and the top of `players` are DIFFERENT selections: the board sorts
 *  by total_pwc, the MVP is picked by waa_bayes with an eligibility floor,
 *  and `mvp` is null when the session has no eligible player at all. */
export interface StoryPwcPlayer {
  guid: string;
  name: string;
  total_pwc: number;
  wis: number;
  waa: number;
  waa_bayes: number;
  rounds_won: number;
  rounds_lost: number;
  total_rounds: number;
  components: Record<string, number>;
}

export interface StoryWinContribution {
  status: string;
  mvp: {
    guid: string;
    name: string;
    total_pwc: number;
    wis: number;
    waa_bayes: number;
    selected_by: string;
  } | null;
  players: StoryPwcPlayer[];
}

/** GET /api/storytelling/kill-impact — KIS, the per-kill impact model. */
export interface StoryKisPlayer {
  guid: string;
  name: string;
  total_kis: number;
  kills: number;
  carrier_kills: number;
  push_kills: number;
  crossfire_kills: number;
  clutch_kills: number;
  avg_impact: number;
  archetype: string;
}

export interface StoryKillImpact {
  status: string;
  players: StoryKisPlayer[];
  total: number;
  total_kills: number;
}

export interface StorySynergyGroup {
  players: string[];
  crossfire: number;
  trade: number;
  cohesion: number;
  push: number;
  medic: number;
  composite: number;
}

/** GET /api/storytelling/synergy. `defaulted_players_count` is how many
 *  players had no telemetry and were scored at the default — the composite
 *  is that much less measured, which the page has to say out loud.
 *
 *  ⚠️ A UNION OF SHAPES (synergy.py:40,48): `no_data` and `partial_data`
 *  answer `groups: {}` with no weights and no defaulted count — recorded
 *  on session 80 (api_storytelling_synergy_80.json). The optional marks
 *  are that union, not laziness. */
export interface StorySynergy {
  status: string;
  session_date?: string | null;
  reason?: string;
  groups: { group_a?: StorySynergyGroup; group_b?: StorySynergyGroup };
  weights?: Record<string, number>;
  defaulted_players_count?: number;
}

/** The four role boards (gravity / space-created / enabler / lurker-profile)
 *  return one players[] each with a shared identity and their own score
 *  field, so one row type carries all four rather than four near-copies. */
export interface StoryRolePlayer {
  name: string;
  guid?: string;
  guid_short?: string;
  gravity_score?: number;
  space_score?: number;
  enabler_score?: number;
  solo_pct?: number;
}

export interface StoryRoleBoard {
  status: string;
  metric: string;
  description: string;
  players: StoryRolePlayer[];
}

/** GET /api/storytelling/player-narratives — generated prose per player. */
export interface StoryPlayerNarrative {
  guid_short: string;
  name: string;
  narrative: string;
  archetype: string;
  top_trait: string;
}

export interface StoryPlayerNarratives {
  status: string;
  player_narratives: StoryPlayerNarrative[];
}

// ---------------------------------------------------------------------------
// The eight storytelling endpoints the story page never read. Typed from the
// handlers and services (storytelling_router.py, services/storytelling/*.py),
// not from one recording — three of them answer a DIFFERENT SHAPE when the
// session has no data, and a type read off the healthy sample would describe
// a payload the page then crashes on.
// ---------------------------------------------------------------------------

/** One life in GET /api/storytelling/best-lives — the most kills a player
 *  landed without dying once. Legacy drew these as the "lives of the night"
 *  cards on session detail (`session-detail.js:_loadLifeCards`).
 *
 *  Everything here is non-null on purpose, not by omission: the builder writes
 *  `short_guid(r["guid"]) if r["guid"] else None`, but `player_track`
 *  declares `player_guid`, `player_name`, `map_name` and `round_number` NOT
 *  NULL (checked in information_schema, 0 nulls in 71,752 rows), and
 *  `short_guid` returns "?" rather than None for an empty input. The null
 *  branch is unreachable through this query — a fact about the schema, not
 *  about today's rows. */
export interface StoryBestLife {
  guid: string;
  name: string;
  kills: number;
  life_seconds: number;
  map_name: string;
  round_number: number;
  narrative: string;
}

export interface StoryBestLives {
  status: string;
  lives: StoryBestLife[];
  /** ⚠️ Historically len(lives) AFTER the endpoint's limit — a field named
   *  total that is not a total. Kept as-is on the wire for compatibility;
   *  use qualifying_total for "of N". */
  total: number;
  /** Every life that cleared min_kills, counted BEFORE the limit — what the
   *  cutoff line needs (Codex on #842). Optional because responses recorded
   *  before 2026-08-31 do not carry it: an absent key is not 0, and the UI
   *  must render nothing rather than crash on an older backend. */
  qualifying_total?: number;
  /** The kills threshold the endpoint enforced, published so the caption can
   *  quote it instead of hardcoding the 3. Same vintage as qualifying_total. */
  min_kills?: number;
}

/** One published term of a formula. The two formula endpoints hand-build
 *  their dicts term by term, and the keys genuinely differ between terms:
 *  `spawn_timing` publishes a `range` and a `bonus` and no `value`,
 *  `long_range` publishes a `value` and a `threshold` and no `description`,
 *  the retired `push` term publishes a `status`. So every field here is
 *  optional because the server really omits them, and the renderer shows
 *  what is present rather than assuming a shape. */
export interface FormulaTerm {
  value?: number;
  range?: string;
  bonus?: number;
  /** A number where the cut-off is numeric (push: 0.9), a string where the
   *  server publishes the human form ("<30 HP", ">800u", "1v3+"). */
  threshold?: number | string;
  status?: string;
  description?: string;
  /** The soft-cap term publishes a compression factor beside its threshold:
   *  above the threshold the total is 5.0 + (raw - 5.0) x compression, which
   *  is why a high score is NOT the product of the multipliers. */
  compression?: number;
  /** The reinforcement term nests its own graduated tiers. */
  tiers?: FormulaReinfTier[];
  /** The `alive` term nests two sub-terms instead of carrying a value. */
  solo_clutch?: FormulaTerm;
  outnumbered?: FormulaTerm;
}

export interface FormulaReinfTier {
  /** null on the last tier — it is the open-ended one (">= 25s"). */
  max_reinf_seconds: number | null;
  inclusive: boolean;
  multiplier: number;
}

/** GET /api/storytelling/formula — how a kill's impact is computed. Published
 *  because a score nobody can check is a claim, not a measurement (#769). */
export interface StoryKisFormula {
  status: string;
  version: string;
  name: string;
  description: string;
  multipliers: Record<string, FormulaTerm>;
  outcome_multipliers: Record<string, FormulaTerm>;
  class_weights: Record<string, FormulaTerm>;
  distance_multipliers: Record<string, FormulaTerm>;
  objective_multipliers: Record<string, FormulaTerm>;
  oksii_multipliers: Record<string, FormulaTerm>;
  soft_cap: FormulaTerm;
  formula: string;
  /** What the score does and does not measure, in the server's own words. */
  validity: Record<string, string>;
}

/** GET /api/storytelling/win-contribution/formula — the PWC weights, plus
 *  the two things the number is most often misread as. */
export interface StoryPwcFormula {
  status: string;
  version: string;
  name: string;
  description: string;
  weights: Record<string, FormulaTerm>;
  zero_objective_rounds: FormulaTerm;
  /** Says in the payload that the MVP is picked by `waa_bayes` and not by
   *  the leaderboard's `total_pwc` — the distinction the board itself makes.
   *  The server also publishes the selection rules themselves: who may win
   *  (`eligibility`), how equal `waa_bayes` scores are resolved (ordered
   *  `tiebreakers`), and what happens when nobody qualifies (`fallback`).
   *  Optional like every FormulaTerm field, because the formula endpoints
   *  hand-build their dicts and omission is how they spell "not published". */
  mvp: FormulaTerm & {
    metric?: string;
    eligibility?: string;
    tiebreakers?: string[];
    fallback?: string;
  };
}

/** One kill inside GET /api/storytelling/kill-impact/details — every
 *  multiplier that produced its score, so a total can be checked.
 *
 *  Nullability read off `storytelling_kill_impact` and the SELECT that reads
 *  it (storytelling_router.py:358-372), not off the sample:
 *
 *  - the multipliers below are non-null because the handler calls `float()`
 *    on them: a NULL there would raise, so there is no response in which
 *    they arrive as null — a 500 is not a shape to type;
 *  - `health_multiplier`, `alive_multiplier`, `reinf_multiplier` and
 *    `killer_health` are nullable columns (added by a later migration) that
 *    the SELECT COALESCEs, so they too cannot be null here;
 *  - the four `is_*` flags, `kill_outcome_id`, `round_start_unix` and
 *    `kill_time_ms` are nullable columns passed straight through. Measured
 *    2026-08-30: 0 nulls in 45,964 rows — the branch that has not happened
 *    rather than the one that cannot. */
export interface StoryKisKill {
  kill_outcome_id: number | null;
  round_number: number;
  round_start_unix: number | null;
  map_name: string;
  victim_guid: string;
  victim_name: string;
  base_impact: number;
  carrier_multiplier: number;
  push_multiplier: number;
  crossfire_multiplier: number;
  spawn_multiplier: number;
  outcome_multiplier: number;
  class_multiplier: number;
  distance_multiplier: number;
  health_multiplier: number;
  alive_multiplier: number;
  reinf_multiplier: number;
  total_impact: number;
  is_carrier_kill: boolean | null;
  is_during_push: boolean | null;
  is_crossfire: boolean | null;
  is_objective_area: boolean | null;
  kill_time_ms: number | null;
  killer_health: number;
}

export interface StoryKisDetails {
  status: string;
  player_guid: string;
  /** The EMPTY STRING when the player has no kills in this scope — the
   *  handler only looks the name up if `kills` is non-empty
   *  (storytelling_router.py:410-419). Not null, so `??` will not catch it. */
  player_name: string;
  summary: {
    total_kis: number;
    kills: number;
    avg_impact: number;
    carrier_kills: number;
    push_kills: number;
    crossfire_kills: number;
  };
  kills: StoryKisKill[];
}

/** GET /api/storytelling/kill-matrix — who killed whom. A UNION, because the
 *  no-data branch returns a different object: `available: false` carries a
 *  `reason` and omits `total_kills` entirely (kill_matrix.py:87-94). */
export type StoryKillMatrix =
  | {
    status: string;
    available: false;
    reason: string;
    players: [];
    cells: [];
  }
  | {
    status: string;
    available: true;
    players: StoryKillMatrixPlayer[];
    cells: StoryKillMatrixCell[];
    total_kills: number;
  };

export interface StoryKillMatrixPlayer {
  guid_short: string;
  name: string;
  kills: number;
  deaths: number;
}

export interface StoryKillMatrixCell {
  killer: string;
  victim: string;
  kills: number;
  gibs: number;
  revived: number;
}

/** GET /api/storytelling/movement — distance and speed per player, in raw ET
 *  engine units (the server refuses to invent a metre conversion). Same union
 *  shape as the matrix: the empty branch omits `unit` (movement.py:78-95). */
export type StoryMovement =
  | { status: string; available: false; reason: string; players: [] }
  | { status: string; available: true; unit: string; players: StoryMovementPlayer[] };

export interface StoryMovementPlayer {
  guid_short: string;
  name: string;
  lives: number;
  total_distance: number;
  /** null when the player has no alive time at all — the per-minute rate has
   *  no denominator then, and 0 would read as "stood still" (movement.py:67). */
  distance_per_min: number | null;
  avg_speed: number;
  peak_speed: number;
  /** null for the same reason as distance_per_min (movement.py:70-73). */
  sprint_pct: number | null;
  post_spawn_distance: number;
  alive_ms: number;
}

/** GET /api/storytelling/useless-defense-deaths — defensive deaths that gave
 *  the attackers free objective time. One shape; `players` is empty when
 *  nobody cleared the thresholds, which is a real answer, not a failure. */
export interface StoryUselessDefensePlayer {
  guid: string;
  guid_short: string;
  name: string;
  useless_deaths: number;
  total_defense_deaths: number;
  /** useless / total, 0 when total is 0 — a ratio the server rounds to 3dp. */
  rate: number;
}

export interface StoryUselessDefense {
  status: string;
  metric: string;
  /** Carries the thresholds in prose; the numbers are in `thresholds`. */
  description: string;
  thresholds: { min_reinf_seconds: number; min_killer_health: number };
  players: StoryUselessDefensePlayer[];
}

/** GET /api/storytelling/momentum-session — the whole evening as one curve,
 *  by persistent team rather than by round.
 *
 *  THREE shapes, discriminated by `status` (momentum.py:275-331): `no_data`
 *  has neither teams nor a reason, `no_team_data` has a reason but still no
 *  teams, and only `ok` carries teams, boundaries and meta. The legacy page
 *  reads `reason || status` for exactly this. */
export type StoryMomentumSession =
  | { status: 'no_data'; session_date: string; points: [] }
  | { status: 'no_team_data'; session_date: string; reason: string; points: [] }
  | {
    status: 'ok';
    session_date: string;
    teams: { team_a: StoryMomentumTeam; team_b: StoryMomentumTeam };
    points: StoryMomentumSessionPoint[];
    round_boundaries: StoryMomentumBoundary[];
    meta: {
      rounds: number;
      /** Rounds whose players could not be mapped to either team — they are
       *  in the curve's time span but not in its two lines. */
      unmapped_rounds: number;
      defaulted_players_count: number;
    };
  };

export interface StoryMomentumTeam {
  label: string;
  players: string[];
}

export interface StoryMomentumSessionPoint {
  t_ms: number;
  team_a: number;
  team_b: number;
}

export interface StoryMomentumBoundary {
  x_ms: number;
  map_name: string;
  round_number: number;
}

// ---------------------------------------------------------------------------
// Phase 4 — session detail. Corpus: api_stats_session_*.json, recorded
// 2026-08-29 against gaming session 154 (12 rounds, 6 maps, 6 players).
//
// The nullability below comes from stats_router.py and session_scoring.py,
// not from the recording: session 154 fills nearly everything, and an early
// session with no Lua mirror fills much less.
// ---------------------------------------------------------------------------

/** One map's line in the stopwatch scoring block. `team_a_time` is a clock
 *  string OR the word "fullhold" — the two are different outcomes and the
 *  page must not print one as the other. */
export interface SessionScoringMap {
  map: string;
  team_a_points: number;
  team_b_points: number;
  team_a_time: string | null;
  team_b_time: string | null;
  winner: string | null;
  description: string | null;
  /** False when the map was played but is not counted (cancelled halves). */
  counted: boolean;
  match_id: string | null;
}

/** `available: false` when the session predates stopwatch scoring or its
 *  halves could not be paired — the page says which, rather than showing a
 *  0–0 that looks like a real draw (the 2026-08-12 bug).
 *
 *  ⚠️ An unavailable block carries ONLY `{available: false}` — every field
 *  below it is ABSENT, not zero (sessions_router: `scoring_payload =
 *  {"available": False}`). Measured on session 151: reading a name off it
 *  is reading `undefined`. */
export interface SessionScoring {
  available: boolean;
  team_a_name?: string;
  team_b_name?: string;
  team_a_score?: number;
  team_b_score?: number;
  maps?: SessionScoringMap[];
  total_maps?: number;
}

export interface SessionTeamAggregate {
  kills: number;
  deaths: number;
  damage: number;
  time_played: number;
  revives: number;
  assists: number;
  gibs: number;
  hs_kills: number;
  dpm_avg: number | null;
  kd_avg: number | null;
  accuracy_avg: number | null;
}

/** Same rule as the scoring block: unavailable means `{available: false,
 *  reason}` and nothing else. */
export interface SessionTeamMatrix {
  available: boolean;
  reason?: string;
  team_a_name?: string;
  team_b_name?: string;
  aggregates?: { team_a: SessionTeamAggregate; team_b: SessionTeamAggregate };
}

/** One player's session totals. `alive_pct` and `alive_pct_lua` are two
 *  measurements of the same thing — stats file against Lua mirror — and
 *  `alive_pct_diff` is their disagreement, which is data about the capture
 *  rather than about the player. */
export interface SessionPlayerTotals {
  player_guid: string;
  player_name: string;
  kills: number;
  deaths: number;
  damage_given: number;
  damage_received: number;
  dpm: number;
  kd: number;
  efficiency: number;
  headshot_kills: number;
  headshot_pct: number;
  gibs: number;
  revives_given: number;
  times_revived: number;
  kill_assists: number;
  accuracy: number;
  time_played_seconds: number;
  alive_pct: number | null;
  alive_pct_lua: number | null;
  alive_pct_diff: number | null;
  /** True when the engine's alive % and the computed one disagree by > 2 pp. */
  alive_pct_drift: boolean;
  /** Share of the session's duration the player was present; null without a duration. */
  played_pct: number | null;
  /** ⚠️ NOT the raw TAB[8]: sessions_router.py:2298 returns played_pct
   *  again "for frontend compat". The legacy "Lua Played%" column printed
   *  this duplicate as a second measurement; the app does not draw it. */
  played_pct_lua: number | null;
  self_kills: number;
  /** pcs.most_useful_kills — the victim had ≥ half the spawn cycle ahead
   *  (c0rnp0rn8.lua topshots[15]); the legacy "armed enemies" tooltip was wrong. */
  useful_kills: number;
  /** /kill at health > 0 with the full respawn ahead (the Lua's −2 s window). */
  full_selfkills: number;
  /** SUM over rounds of LEAST(time_dead, time_played) in minutes. */
  time_dead_minutes: number;
  /** Seconds of playtime denied to opponents (raw; the 2025 backfill rows are suspect). */
  denied_playtime: number;
}

export interface SessionMatchRound {
  round_id: number;
  round_number: number;
  winner_team: number | null;
  /** Nullable, measured: one session in forty answers null for both scores.
   *  Found by sampling every session rather than the newest — the brother's
   *  rule from #830, where `/api/sessions?limit=200` produced 420 nulls that
   *  `?limit=1` could not show, because they come from a LEFT JOIN and not
   *  from a nullable column. */
  allies_score: number | null;
  axis_score: number | null;
  duration_seconds: number | null;
}

export interface SessionMatch {
  map_name: string;
  rounds: SessionMatchRound[];
}

/** GET /api/stats/session/{id}/detail */
export interface SessionDetail {
  session_id: number;
  date: string;
  player_count: number;
  round_count: number;
  matches: SessionMatch[];
  players: SessionPlayerTotals[];
  scoring: SessionScoring;
  team_matrix: SessionTeamMatrix;
}

/** GET /api/stats/session/{id}/good-night — a 0-100 index over seven named
 *  components. `available: false` means it could not be computed; a low
 *  score means it was, and the night was quiet. */
export interface SessionGoodNight {
  status: string;
  available: boolean;
  gaming_session_id: number;
  /** Present only when `available` — the handler returns `{status,
   *  available: false, gaming_session_id}` and nothing else. */
  score?: number;
  components?: Record<string, number>;
  reasons?: string[];
  maps?: number;
  players?: number;
  hours?: number;
}

/** GET /api/stats/session/{id}/verdicts — each player against their OWN
 *  form, never against each other. `first_night` marks a player with no
 *  baseline: a verdict about them would be a comparison with nothing. */
export interface SessionVerdictPlayer {
  guid: string;
  name: string;
  dpm: number;
  avg_dpm: number | null;
  kills: number;
  first_night: boolean;
  percentile: number | null;
  label: string;
  sessions_in_baseline: number;
}

export interface SessionVerdicts {
  status: string;
  gaming_session_id: number;
  /** Absent when there is nothing to compare against: the early return is
   *  `{status, gaming_session_id, players: []}`. */
  baseline?: string;
  players: SessionVerdictPlayer[];
}

/** GET /api/stats/session/{id}/mvp — PEER VOTES, not a computed rating.
 *  Unrelated to storytelling's PWC MVP, and the page has to keep them
 *  apart: one is what people thought, the other is what the model says. */
export interface SessionMvpCandidate {
  guid: string;
  name: string;
  kills: number;
  dpm: number;
  votes: number;
  vote_pct: number;
  kis_rank: number | null;
}

export interface SessionMvp {
  status: string;
  gaming_session_id: number;
  /** ⚠️ ABSENT, not 0, when no candidate qualified — the early return is
   *  `{status, gaming_session_id, candidates: []}`. Typed as a required
   *  number, `total_votes === 0` was false for `undefined` and the page fell
   *  through to `figure(undefined)`, which crashed the whole route. Measured
   *  on sessions 151, 146 and 128. */
  total_votes?: number;
  my_vote?: string | null;
  most_underrated_guid?: string | null;
  candidates: SessionMvpCandidate[];
}

// ---------------------------------------------------------------------------
// Stats 2.0 (docs/design/18 §E) — the basics table and the evening's awards.
// Names and nullability mirror the backend models EXACTLY: openapi carries
// these schemas, so scripts/check_manual_types_against_openapi.py compares
// every field (required = no `?`; nullable = `| null`).

export interface SessionBasicsCoverage {
  rounds_counted: number;
  rounds_total: number;
  total_kills: number;
  /** Kills the Kill Impact Score has scored — the proximity-tracked subset. */
  kis_kills: number;
  /** False = no KIS row for the session; every kis_* cell is null then. */
  kis_covered: boolean;
  teams_attributed: boolean;
  /** Players whose denied figure the definition cannot produce (denied >
   *  2 × played — the 2025 backfill rows); their denied_pct is null. */
  denied_suspect_players: number;
}

export interface SessionBasicsTeam {
  key: string;
  name: string;
  score: number;
}

export interface SessionBasicsPlayer {
  guid: string;
  name: string;
  /** 'a' | 'b' from the roster; null when unattributed. */
  team: string | null;
  time_played_seconds: number;
  denied_playtime_seconds: number;
  denied_pct: number | null;
  dpm: number;
  kills: number;
  deaths: number;
  damage_given: number;
  damage_received: number;
  dmr: number;
  accuracy: number | null;
  headshot_pct: number | null;
  gibs: number;
  /** pcs.most_useful_kills — the legacy "Useful Kills" column (UK = useful): kills whose
   *  victim had ≥ half the spawn cycle ahead (c0rnp0rn8.lua topshots[15]). */
  useful_kills: number;
  useless_kills: number;
  self_kills: number;
  full_selfkills: number;
  revives_given: number;
  times_revived: number;
  kis_total: number | null;
  kis_per_min: number | null;
  played_pct: number | null;
  alive_pct: number | null;
  alive_pct_drift: boolean;
}

export interface SessionBasics {
  gaming_session_id: number;
  date: string | null;
  coverage: SessionBasicsCoverage;
  teams: SessionBasicsTeam[];
  players: SessionBasicsPlayer[];
}

export interface SessionAwardEntry {
  engine_name: string;
  nickname: string;
  sentence: string;
  player: string;
  guid: string | null;
  value: string;
  value_numeric: number | null;
  unit: string;
  rounds_won: number;
}

export interface SessionAwardCategory {
  key: string;
  label: string;
  awards: SessionAwardEntry[];
}

export interface SessionAwards {
  gaming_session_id: number;
  rounds_counted: number;
  rounds_with_awards: number;
  categories: SessionAwardCategory[];
}

// ---------------------------------------------------------------------------
// The backwards-debt eight: paths legacy called that the app had not adopted.

/** GET /api/stats/live-session — a UNION, not optional fields: the inactive
 *  answer is `{active: false}` and nothing else (players_router.py, two
 *  return statements). "Active" means rounds in the last 30 minutes — a
 *  different question from /api/stats/tonight (voice or rounds today) and
 *  from /api/live-status (game server reachable), so the page must label
 *  which one it is quoting. */
export type LiveSession =
  | { active: false }
  | {
      active: true;
      rounds_completed: number;
      current_players: number;
      /** "Unknown" when the detail lookup failed — a sentinel the handler
       *  writes, not a map name. */
      current_map: string;
      /** "m:ss" of the last round, or null when the detail lookup failed. */
      last_round_time: string | null;
      last_update: string;
    };

/** GET /api/predictions/recent — a bare array; only rows explicitly
 *  published (shadow program AUD-006) are ever returned, and the dev
 *  database holds zero of those today, so the recorded fixture is `[]` and
 *  the element shape is typed from the live schema, not a sample.
 *  ⚠️ `confidence` is TEXT and `actual_winner` an INTEGER team number in
 *  the schema — an invented "number score / team name" shape would have
 *  survived every fixture round-trip. Legacy app.js read `match_type` /
 *  `correct` / `description`, three fields this endpoint has never sent —
 *  do not copy legacy's names. */
export interface RecentPrediction {
  id: number;
  timestamp: string;
  format: string;
  team_a_probability: number;
  team_b_probability: number;
  confidence: string;
  insight: string;
  actual_winner: number | null;
  is_correct: boolean | null;
  accuracy: number | null;
}

/** GET /api/stats/session-leaderboard — response_model=list[SessionLeaderRow]
 *  (sessions_router.py). kills/deaths are nullable in the model. */
export interface SessionLeaderRow {
  rank: number;
  name: string;
  dpm: number;
  kills: number | null;
  deaths: number | null;
}

/** GET /api/skill/player/{identifier} — the 200-with-status convention:
 *  an unknown or under-rated player answers
 *  `{status: "error", detail: "…need 5+ rounds…"}`, never a 404. */
export interface SkillPlayerComponent {
  raw: number;
  weight: number;
  percentile: number;
  contribution: number;
}

export interface SkillPlayerOk {
  status: 'ok';
  player: {
    player_guid: string;
    display_name: string;
    et_rating: number;
    games_rated: number;
    last_rated_at: string | null;
    rank: number;
    total_rated: number;
    components: Record<string, SkillPlayerComponent>;
    confidence: number | null;
    tier: string | null;
  };
}

export type SkillPlayer = SkillPlayerOk | { status: 'error'; detail: string };

/** GET /api/skill/composite — per-session composite metrics with the
 *  coverage block #848 added: `unmeasured_metrics` names what the sources
 *  could not back for THIS session (measured corpus: [] on 154,
 *  [ci,kpi,tir] on 94, all five on 20), and the page's whole job is to
 *  show that honesty instead of rendering unmeasured zeros as scores. */
export interface CompositePlayer {
  player_guid: string;
  player_name: string;
  kills: number;
  tir: number;
  ci: number;
  kpi: number;
  sds: number;
  cp: number;
  details: {
    crossfire_kills: number;
    trade_kills: number;
    clutch_kills: number;
    gibbed_count: number;
    total_outcomes: number;
    avg_spawn_score: number;
    focus_escapes: number;
    times_focused: number;
  };
}

export interface CompositeCoverage {
  unmeasured_metrics: string[];
  partially_synthetic_metrics: string[];
  source_rows: {
    crossfire: number;
    crossfire_cache: number;
    trades: number;
    combat_positions: number;
    kill_outcomes: number;
    spawn_timing: number;
  };
}

export interface CompositeStats {
  status: string;
  session_date: string | null;
  gaming_session_id: number | null;
  players: CompositePlayer[];
  coverage: CompositeCoverage;
  meta: { metrics: Record<string, string> };
}

/** GET /api/stats/player/{player_name} — the identity half the profile
 *  endpoint does not carry: aliases, the Discord link, the sick-leave
 *  identity link (migration 073, null for most), achievements. A missing
 *  player is a real 404 here, not a status envelope. */
export interface PlayerIdentity {
  name: string;
  guid: string;
  stats: {
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
    last_seen: string | null;
    favorite_weapon: string | null;
    favorite_map: string | null;
    highest_dpm: number | null;
    lowest_dpm: number | null;
  };
  aliases: string[];
  discord_linked: boolean;
  /** Sick-leave attribution (migration 073) — a UNION by role, or null for
   *  the unlinked majority: an ALT points at its primary, a PRIMARY lists
   *  its alts. Typed from fetch_identity_links, not the sample (the sample
   *  is null). */
  identity_link: IdentityLink | null;
  /** A DICT with progress, not a list — the first blind guess here typed it
   *  as a name/description array and the live sample refuted both fields. */
  achievements: {
    unlocked: AchievementBadge[];
    next: AchievementNext[];
    total_unlocked: number;
    total_possible: number;
    progress: number;
  };
}

export interface AchievementBadge {
  type: string;
  threshold: number;
  emoji: string;
  title: string;
  color: string;
}

export interface AchievementNext {
  type: string;
  threshold: number;
  emoji: string;
  title: string;
  current: number;
  progress: number;
}

export type IdentityLink =
  | {
      role: 'alt';
      link_type: string;
      reason: string | null;
      primary_guid: string;
      primary_name: string;
      active: boolean;
      since: string | null;
    }
  | {
      role: 'primary';
      alts: {
        alt_guid: string;
        alt_name: string;
        link_type: string;
        reason: string | null;
        active: boolean;
        since: string | null;
      }[];
    };

/** GET /api/player/{player_name}/matches — round-level rows richer than the
 *  profile's recent_matches (gibs, damage_received, headshot_kills,
 *  revives_given, round_status, gaming_session_id). */
export interface PlayerMatchRound {
  round_id: number;
  round_date: string;
  map_name: string;
  round_number: number;
  kills: number;
  deaths: number;
  damage: number;
  time_played: number;
  /** Numeric team id (pcs.team is INTEGER; the fixture carries 1/2) — the
   *  first version typed it as a string from memory, not measurement. */
  team: number | null;
  xp: number;
  accuracy: number;
  dpm: number;
  kd: number;
  gibs: number;
  damage_received: number;
  headshot_kills: number;
  revives_given: number;
  round_status: string | null;
  gaming_session_id: number | null;
  /** FALSE with a completed status is a real state — the uncounted mark
   *  needs BOTH signals (Codex on #855, round six). */
  is_valid: boolean | null;
}

// ---------------------------------------------------------------------------
// Phase 5 — proximity. First slice: the ten-tab leaderboard section.

/** GET /api/proximity/leaderboards — one endpoint, nine categories (the
 *  tenth tab, comp_skill, is /api/skill/ssr: all-time and group-relative,
 *  it ignores range and scope by owner decision A4). Each handler branch
 *  returns its own fixed extras (typed from the handler, not the sample);
 *  the wire carries no discriminant on the ENTRY, so `entries` is honestly
 *  base + Partial extras — the response-level `category` field is what a
 *  caller narrows on, and the per-category interfaces below name what each
 *  branch actually sends (Copilot on #856: the first comment here claimed
 *  a discriminated union the type never was).
 *  An unknown category answers {status:'error'} inside a 200, the house
 *  convention. Legacy read `partner_name` off crossfire entries — a field
 *  only the teamplay duo boards have ever sent — so its crossfire board
 *  rendered "name + ?" forever; not carried. */
export interface LbEntryBase {
  guid: string;
  name: string;
  value: number;
}

export interface LbPowerEntry extends LbEntryBase {
  axes: { aggression: number; awareness: number; teamplay: number; timing: number };
  components?: Record<string, number>;
}

export interface LbSpawnEntry extends LbEntryBase {
  timed_kills: number;
  avg_denial_ms: number;
}

export interface LbCrossfireEntry extends LbEntryBase {
  avg_angle: number;
}

export interface LbTradesEntry extends LbEntryBase {
  avg_reaction_ms: number;
}

export interface LbReactionsEntry extends LbEntryBase {
  samples: number;
}

export interface LbSurvivorsEntry extends LbEntryBase {
  total_engagements: number;
  avg_duration_ms: number;
}

export interface LbMovementEntry extends LbEntryBase {
  sprint_pct: number;
  total_distance: number;
  tracks: number;
}

export interface LbFocusFireEntry extends LbEntryBase {
  times_focused: number;
  avg_attackers: number;
  avg_damage: number;
}

export interface LbKrogtEntry extends LbEntryBase {
  lives: number;
}

export type LbCategory =
  | 'power' | 'spawn' | 'crossfire' | 'trades' | 'reactions'
  | 'survivors' | 'movement' | 'focus_fire' | 'krogt';

export interface ProximityLeaderboard {
  status: string;
  category: string;
  /** power only — quoted, never restated. */
  formula_version?: string;
  /** power only: how many source rows were linkable — the board's own
   *  honesty block. */
  attribution?: {
    total_rows: number;
    linked_valid: number;
    linked_invalid_excluded?: number;
    unlinked_accepted?: number;
    attributable_coverage?: number;
    /** "compatibility" on the recorded fixture — a LABEL, not a count; the
     *  loose numeric index this block first had would have typed it away. */
    mode?: string;
  };
  entries: (LbEntryBase & Partial<LbPowerEntry & LbSpawnEntry & LbCrossfireEntry &
    LbTradesEntry & LbReactionsEntry & LbSurvivorsEntry & LbMovementEntry &
    LbFocusFireEntry & LbKrogtEntry>)[];
}

// ---------------------------------------------------------------------------
// Phase 5, slice 2 — the instruments (13 single-endpoint panels, 07 §B.2).
// All typed from the handlers' live answers on 2026-08-31 scope; every one
// speaks the 200-with-status convention except /quality, which has its own
// three-status header (overall/selected_scope/global_maintenance).

export interface ProxScope {
  session_date: string | null;
  map_name: string | null;
  round_number: number | null;
  round_start_unix: number | null;
  player_guid: string | null;
}

/** /proximity/quality — the data-completeness band (design 12 row 12). */
export interface ProxQualitySignal {
  table: string;
  row_count: number;
  /** The linkage columns are null for cache tables (storytelling_kill_impact). */
  linked_rows: number | null;
  linked_round_count: number | null;
  exact_link_ratio: number | null;
  latest_created_at: string | null;
  ready: boolean;
  status: string;
  required: boolean;
}

export interface ProxQuality {
  overall_status: string;
  selected_scope_status: string;
  global_maintenance_status: string;
  scope: ProxScope & { range_days?: number };
  signals: Record<string, ProxQualitySignal>;
  /** The HTTP-200 error shape (SQLite mode, any quality-check exception)
   *  carries only status+ready here — every count is OPTIONAL, and the
   *  first version crashed the whole route on `.toFixed()` of a missing
   *  number (Codex on #861, P1). */
  round_correlation: {
    status: string;
    ready: boolean;
    correlation_count?: number;
    complete_count?: number;
    avg_completeness_pct?: number;
  };
  linkage?: { scope: string; status: string; breach_count: number };
  /** RECORDS, not strings — joining them rendered "[object Object]" in the
   *  truth strip precisely when a warning existed (Codex on #861). */
  warnings: { code: string; level: string; message: string }[];
  generated_at?: string;
}

/** GET /api/proximity/scopes — the dates where the TRACKER captured data,
 *  which is the only honest source for the instrument chips: the sessions
 *  list names parsed evenings, and an evening can exist with no telemetry
 *  (Codex on #861, P1 — the recorded corpus had exactly that skew). */
export interface ProxScopes {
  status: string;
  ready: boolean;
  message: string | null;
  range_days: number;
  generated_at: string;
  sessions: {
    session_date: string;
    engagements: number;
    map_count: number;
    round_count: number;
    /** The full hierarchy — slice 5's map and round chips read it; slice 2
     *  only needed the dates and typed these away until the picker did. */
    maps: {
      map_name: string;
      engagements: number;
      round_count: number;
      rounds: { round_number: number; round_start_unix: number | null }[];
    }[];
  }[];
}

export interface ProxSpawnTiming {
  status: string;
  scope: ProxScope;
  total_events: number;
  leaders: { guid: string; name: string; avg_score: number; kills: number; avg_denial_ms: number }[];
  team_averages: { team: string; avg_score: number; total_kills: number }[];
}

export interface ProxAimLock {
  status: string;
  scope: ProxScope;
  total_events: number;
  leaders: {
    guid: string; name: string; locks: number; avg_lock_ms: number;
    total_lock_ms: number; avg_err_deg: number; avg_dist: number; targets: number;
  }[];
}

export interface ProxCohesion {
  status: string;
  scope: ProxScope;
  team_summary: {
    team: string; avg_dispersion: number; avg_max_spread: number;
    avg_stragglers: number; avg_alive: number; samples: number;
  }[];
  /** Measured 1,880 points for one evening — rendered as a thinned
   *  sparkline, never a table. */
  timeline: { time: number; team: string; dispersion: number; round_start_unix: number; round_time: number }[];
  buddy_pairs: { guids: string; times_paired: number; avg_distance: number }[];
}

export interface ProxCrossfireAngles {
  status: string;
  scope: ProxScope;
  total_opportunities: number;
  executed: number;
  utilization_rate_pct: number;
  avg_angle: number;
  avg_damage: number;
  angle_buckets: { bucket: string; count: number; executed: number }[];
  /** THE place partner_name actually lives — the field legacy tried to
   *  read off the leaderboards endpoint, which never sent it. */
  top_duos: {
    teammate1_guid: string; teammate2_guid: string;
    /** null when the scoped player_track lookup cannot resolve the guid —
     *  render the eight-char guid, never a blank " + " row. */
    name: string | null;
    partner_name: string | null; executions: number; avg_angle: number;
  }[];
}

export interface ProxPushes {
  status: string;
  scope: ProxScope;
  team_summary: {
    team: string; pushes: number; avg_quality: number; avg_alignment: number;
    avg_speed: number; avg_participants: number; objective_pushes: number;
  }[];
  quality_distribution: { tier: string; team: string; count: number }[];
}

export interface ProxLuaTrades {
  status: string;
  scope: ProxScope;
  leaders: { guid: string; name: string; trades: number; avg_reaction_ms: number; fastest_ms: number }[];
  recent_trades: { victim: string; killer: string; trader: string; delta_ms: number; map: string; date: string }[];
  speed_distribution: { tier: string; count: number }[];
}

export interface ProxRevives {
  status: string;
  summary: { total_revives: number; avg_enemy_distance: number; under_fire_pct: number };
  leaders: { guid: string; name: string; revives: number; under_fire_count: number; avg_enemy_dist: number }[];
}

export interface ProxFocusFire {
  status: string;
  summary: {
    total_events: number; avg_score: number; avg_attackers: number;
    avg_damage: number; avg_duration_ms: number;
  };
  targets: {
    guid: string; name: string; times_focused: number; avg_score: number;
    total_damage_taken: number; avg_attackers: number;
  }[];
  recent: {
    target_name: string; attacker_count: number; total_damage: number;
    duration: number; focus_score: number; map_name: string; session_date: string;
  }[];
}

export interface ProxSupportSummary {
  status: string;
  /** Deliberately `{}` when the support column has not been migrated —
   *  every field optional, and emptiness is judged on total_rounds being
   *  MISSING or zero, never formatted blind (Codex on #861, P1). */
  summary: { total_rounds?: number; avg_uptime_pct?: number; max_uptime_pct?: number; avg_coverage_pct?: number };
  by_map: {
    map_name: string; rounds: number; avg_uptime_pct: number; max_uptime_pct: number;
    total_support_samples: number; total_samples: number;
  }[];
  rounds: {
    map_name: string; round_number: number; support_uptime_pct: number;
    support_samples: number; total_samples: number; session_date: string;
  }[];
}

export interface ProxCombatPositions {
  status: string;
  /** Deliberately `{}` when the table/column has not been migrated — the
   *  same sparse species as support-summary (Codex on #861, round two). */
  summary: {
    total_kills?: number; avg_kill_distance?: number; median_kill_distance?: number;
    unique_attackers?: number; maps_tracked?: number;
  };
  by_class: { class: string; kills: number; avg_distance: number }[];
  by_map: { map_name: string; kills: number; avg_distance: number }[];
}

export interface ProxClasses {
  status: string;
  ready: boolean;
  message: string | null;
  range_days: number;
  generated_at: string;
  scope: ProxScope;
  /** The movement averages are nullable — a class whose tracked rows carry
   *  no sprint_percentage gets avg_sprint_pct: null (Codex on #861 r2). */
  classes: {
    player_class: string; tracks: number; players: number; avg_duration_ms: number | null;
    avg_distance: number | null; avg_sprint_pct: number | null; avg_spawn_reaction_ms: number | null;
  }[];
}

export interface ProxReactionRow {
  guid: string;
  name: string;
  player_class: string;
  reaction_ms: number;
  samples: number;
}

export interface ProxReactions {
  status: string;
  ready: boolean;
  message: string | null;
  range_days: number;
  generated_at: string;
  scope: ProxScope;
  limit: number;
  return_fire: ProxReactionRow[];
  dodge: ProxReactionRow[];
  support: ProxReactionRow[];
  /** A class can have dodge/support events and ZERO return-fire samples —
   *  the backend then sends avg_return_fire_ms: null (Codex on #861, P1). */
  class_summary: {
    player_class: string; events: number; return_samples: number; avg_return_fire_ms: number | null;
    dodge_samples: number; avg_dodge_reaction_ms: number | null;
    support_samples: number; avg_support_reaction_ms: number | null;
  }[];
}

// ---------------------------------------------------------------------------
// Phase 5, slice 3 — the competitive section (07 §B.2). Every panel quotes
// the wire's own `description` — the formula text lives server-side and the
// page repeats it, never paraphrases. wave-cycles is NOT here: it requires
// map_name + round_number and belongs to the round-scope slice.

export interface CompStagger {
  status: string;
  scope: ProxScope;
  threshold: number;
  description: string;
  players: {
    guid: string; name: string; team: string; kills: number;
    stagger_kills: number; stagger_rate: number; denied_s: number; avg_score: number;
  }[];
}

export interface CompFirstBlood {
  status: string;
  scope: ProxScope;
  rounds: number;
  decided_rounds: number;
  converted: number;
  conversion_pct: number;
  description: string;
  players: { guid: string; name: string; first_picks: number; first_deaths: number; fp_converted: number }[];
}

export interface CompPersonalBests {
  status: string;
  session_date: string;
  description: string;
  cards: {
    guid: string; name: string; metric: string; label: string;
    value: number; prev_best: number | null; prev_best_date: string | null;
    sessions_played: number;
  }[];
  scope_note: string;
}

export interface CompManAdvantage {
  status: string;
  scope: ProxScope;
  rounds: number;
  description: string;
  /** Keyed by team name; by_size keyed by "1" | "2" | "3+". */
  teams: Record<string, {
    windows: number;
    converted: number;
    by_size: Record<string, { windows: number; converted: number }>;
    conversion_pct: number;
  }>;
  total_windows: number;
  top_converters: { guid: string; name: string; conversions: number }[];
}

export interface CompClutch {
  status: string;
  scope: ProxScope;
  clock_protocol: string;
  rounds: number;
  skipped_rounds_no_clock: number;
  description: string;
  players: {
    guid: string; name: string; situations: number; wins: number; win_pct: number;
    best: { enemies: number; kills: number; survived: boolean } | null;
  }[];
}

export interface CompSideSplits {
  status: string;
  scope: ProxScope;
  description: string;
  /** Either side can be NULL — a player who only played one half of the
   *  evening has no row for the other (caught live on the single-round
   *  2026-09-01 scope: the recorded 08-31 fixture had both sides for
   *  everyone, so the fixture could not refute the non-null guess). */
  players: {
    guid: string; name: string;
    attack: { kills: number; stagger_kills: number; denied_s: number; minutes: number; kpm: number } | null;
    defense: { kills: number; stagger_kills: number; denied_s: number; minutes: number; kpm: number } | null;
  }[];
}

export interface V7Status {
  status: string;
  lua_version_draft: string;
  deployed: boolean;
  doc: string;
  capabilities: {
    key: string; title: string; what: string; api: string;
    rows: number; rounds: number; live: boolean;
  }[];
}

// ---------------------------------------------------------------------------
// Phase 5, slice 4 — carrier and objective intel (07 §B.2). The sparse
// species discipline is applied UP FRONT this time: summaries carry
// optional fields (the deliberate-{} pattern three earlier panels crashed
// on), and any name the backend resolves through a scoped lookup is
// nullable.

export interface CarrierEvents {
  status: string;
  /** NARROWER than ProxScope — this handler's scope carries only these
   *  three keys (the satisfies check on the recorded fixture said so the
   *  moment it existed; the full-scope guess was a lie of one family). */
  scope: { session_date: string | null; map_name: string | null; round_number: number | null };
  carriers: {
    guid: string; name: string | null; carries: number; secures: number;
    killed: number; dropped: number; total_distance: number;
    avg_efficiency: number; avg_duration_ms: number; secure_rate: number;
  }[];
  events: {
    carrier_name: string | null; carrier_team: string; flag_team: string;
    outcome: string; carry_distance: number; beeline_distance: number;
    efficiency: number; duration_ms: number; map_name: string;
    /** Empty string when nobody killed the carrier (drop/secure). */
    killer_name: string | null; pickup_time: number;
  }[];
  summary: {
    total_carries?: number; total_secures?: number; total_killed?: number;
    avg_distance?: number; avg_efficiency?: number; secure_rate?: number;
  };
}

export interface CarrierKills {
  status: string;
  killers: { guid: string; name: string | null; carrier_kills: number; avg_distance_stopped: number }[];
}

export interface CarrierReturns {
  status: string;
  scope: { range_days?: number; session_date: string | null; map_name: string | null };
  returners: { guid: string; name: string | null; returns: number; avg_delay_ms: number }[];
  events: {
    returner_name: string | null; returner_team: string; flag_team: string;
    original_carrier_guid: string; return_delay_ms: number; map_name: string;
    return_time: number;
  }[];
  /** avg_delay_ms arrives as NULL (not absent) on an empty scope —
   *  measured on 2026-09-01 and 2026-05-01. */
  summary: { total_returns?: number; avg_delay_ms?: number | null };
}

export interface VehicleProgress {
  status: string;
  vehicles: {
    vehicle_name: string; vehicle_type: string; map_name: string;
    session_date: string; round_number: number; total_distance: number;
    max_health: number; final_health: number; destroyed_count: number;
  }[];
}

export interface EscortCredits {
  status: string;
  escorts: {
    guid: string; name: string | null; total_credit_distance: number;
    total_mounted_ms: number; total_proximity_ms: number;
    total_escort_distance: number; total_samples: number;
  }[];
}

export interface ConstructionEvents {
  status: string;
  engineers: {
    guid: string; name: string | null; total_events: number; plants: number;
    defuses: number; destructions: number; constructions: number;
  }[];
  events: {
    event_type: string; player_name: string | null; player_team: string;
    track_name: string; map_name: string; session_date: string;
    round_number: number; event_time: number;
  }[];
}

export interface ObjectiveRuns {
  status: string;
  objective_runners: {
    engineer_guid: string; engineer_name: string | null; total_runs: number;
    successful_runs: number; denied_runs: number; solo_runs: number;
    assisted_runs: number; team_effort_runs: number; unopposed_runs: number;
    total_self_kills: number; total_team_kills: number;
    avg_path_efficiency: number | null;
  }[];
  recent_runs: {
    engineer_name: string | null; action_type: string; track_name: string;
    run_type: string; self_kills: number; team_kills: number;
    nearby_teammates: number; approach_time_ms: number;
    path_efficiency: number | null; map_name: string; session_date: string;
    killer_name: string | null;
  }[];
  summary: {
    total_runs?: number; total_denied?: number; total_solo?: number;
    total_assisted?: number; total_team_effort?: number; total_unopposed?: number;
    avg_path_efficiency?: number | null; most_active_objective?: string | null;
  };
}

export interface ObjectiveFocus {
  status: string;
  summary: {
    unique_players?: number; objectives_tracked?: number;
    avg_time_near_obj_s?: number; avg_distance?: number;
  };
  players: {
    guid: string; name: string | null; total_time_ms: number; avg_dist: number;
    objectives_played: number; total_samples: number; total_time_s: number;
  }[];
  objectives: {
    objective: string; map_name: string; players: number;
    avg_time_s: number; avg_dist: number;
  }[];
}

// ---------------------------------------------------------------------------
// Phase 5, slice 5 — the round scope and its canvases (07 §B.2: player
// journey, push-death heatmap, wave ledger). These instruments REQUIRE a
// map (heatmap) or map+round (journey, wave cycles) — the 422 is the wire
// saying "scope me", not an error state the page can reach once the picker
// gates the calls.

/** GET /api/proximity/players?session_date= — the backbone, called ONLY
 *  with a scope (measured 232 ms scoped vs 12.7 s unbounded — the page
 *  never issues the unbounded form). */
export interface ProxPlayers {
  status: string;
  scope: ProxScope;
  players: { guid: string; name: string | null }[];
}

export interface JourneyPathPoint {
  t: number;
  x: number;
  y: number;
  z: number;
  health: number;
  speed: number;
  stance: number;
  sprint: number;
  event: string | null;
}

export interface JourneyLife {
  life_index: number;
  player_class: string;
  spawn_time_ms: number;
  death_time_ms: number | null;
  duration_ms: number;
  total_distance: number;
  sprint_pct: number | null;
  death_type: string | null;
  path: JourneyPathPoint[];
  /** NO coordinates on the wire — kill and death records carry `time` and
   *  names/outcomes only (the first type GUESSED x/y and every marker was
   *  silently skipped by its own finite filter; both reviewers read the
   *  fixture and said so). Marker positions are DERIVED from the nearest
   *  path point by timestamp. */
  kills: {
    time: number; victim_name: string | null; outcome: string | null;
    denied_ms: number | null; spawn_timing_score: number | null;
    time_to_next_spawn: number | null;
  }[];
  death: {
    time: number; killer_name: string | null; outcome: string | null;
    reviver_name: string | null; gibber_name: string | null;
    victim_wait_ms: number | null;
  } | null;
  proximity_series: {
    t: number; nearest_teammate: number | null; nearest_enemy: number | null;
    teammates_500u: number; enemies_500u: number;
  }[];
  solo_pct: number | null;
  objective_events: { t: number; kind: string | null }[];
  narrative: string;
}

export interface PlayerJourney {
  status: string;
  scope: ProxScope;
  player: { guid: string; name: string | null; team: string } | null;
  lives: JourneyLife[];
  summary: { lives?: number };
  message?: string | null;
}

export interface PushHeatmap {
  status: string;
  map_name: string;
  grid_size: number;
  perspective: string;
  scope: ProxScope;
  push_deaths: number;
  carrier_deaths: number;
  unique_deaths: number;
  hotzones: { x: number; y: number; count: number }[];
}

/** The wave ledger — clock_validation per team carries the FIVE states
 *  (validated / unvalidated / failed / inconsistent / unavailable; design
 *  17 §4 explicitly says take five, not the contract's four). */
export interface WaveClockValidation {
  status: string;
  interval_ms: number | null;
  offset_ms: number | null;
  timing_observations: number;
  landing_clusters: number;
  spawn_callbacks: number;
  post_revive_spawn_callbacks: number;
  passing_landing_clusters: number;
  /** Always read with its numerator/denominator neighbours — a bare ratio
   *  hides how little it stands on. */
  pass_ratio: number | null;
}

export interface WaveCycles {
  status: string;
  scope: ProxScope;
  clock_protocol: string;
  clock_validation: Record<string, WaveClockValidation>;
  excluded_unlinked_kills: number;
  excluded_ineligible_linked_kills: number;
  round_len_ms: number;
  clocks: Record<string, { offset_ms: number | null; interval_ms: number | null }>;
  summary: { cycles?: number; axis_won?: number; allies_won?: number; contested?: number };
  cycles: {
    start_ms: number; end_ms: number; wave: number | null;
    kills_axis: number; kills_allies: number;
    denied_axis_s: number; denied_allies_s: number;
    first_blood: string | null; winner: string | null;
  }[];
}

// ---------------------------------------------------------------------------
// Phase 5, slice 6 — the engagement record: the events list, the per-event
// drill-down, and the dispersion buckets (07 §B.2's last A-class panels).
// Shapes read from proximity_events.py / proximity_combat.py, not guessed.

export interface ProxEventRow {
  id: number;
  date: string;
  round: number;
  map: string;
  target_name: string | null;
  target: string | null;
  attacker_name: string | null;
  target_team: string | null;
  attacker_team: string | null;
  outcome: string | null;
  reaction_ms: number | null;
  duration_ms: number | null;
  distance: number | null;
  distance_traveled: number | null;
  attackers: number | null;
  crossfire: boolean;
  round_id: number | null;
  round_date: string | null;
  round_time: string | null;
}

export interface ProxEvents {
  status: string;
  ready: boolean;
  message: string | null;
  range_days: number;
  generated_at: string | null;
  scope: ProxScope & { range_days?: number };
  limit: number;
  events: ProxEventRow[];
}

export interface ProxEventAttacker {
  guid: string | null;
  name: string | null;
  team: string | null;
  hits: number;
  damage: number;
  got_kill?: boolean;
  first_hit_ms?: number | null;
  last_hit_ms?: number | null;
  /** weaponId -> hits. Values are always numbers on the wire; undefined is
   *  in the type because a lookup of an absent weapon is undefined (and it
   *  lets the recorded two-attacker fixture, whose weapon keys differ,
   *  satisfy the type). */
  weapons: Record<string, number | undefined>;
}

export interface ProxStrafeMetrics {
  duration_ms: number;
  total_distance: number;
  avg_speed: number;
  turn_count: number;
  turn_rate: number;
  /** Turn events over the sliced track ({time, angle_deg, x, y}); empty
   *  when the track had under 3 usable points. */
  events: { time: number; angle_deg: number; x: number; y: number }[];
}

/**
 * ⚠️ The drill-down has TWO forms, a union, not optional fields
 * (one-session-corpus lesson). The handler parses `attackers` and computes
 * `strafe`/paths ONLY when start/end times are valid ("long form"); an
 * engagement with zero times ("short form") leaves `attackers` as the RAW
 * DB string and OMITS the strafe-branch keys entirely. `position_path` is
 * a JSON STRING inside the JSON when recorded, and `[]` when the column is
 * empty (`row or []` in the handler) — never null.
 */
export interface ProxEventDetail {
  id: number;
  session_date: string;
  round_number: number;
  round_start_unix: number | null;
  round_end_unix: number | null;
  map_name: string;
  target_guid: string | null;
  target_name: string | null;
  target_team: string | null;
  outcome: string | null;
  total_damage: number | null;
  start_time_ms: number | null;
  end_time_ms: number | null;
  duration_ms: number | null;
  num_attackers: number | null;
  is_crossfire: boolean;
  position_path: string | unknown[];
  attackers: string | ProxEventAttacker[];
  start_x: number | null;
  start_y: number | null;
  end_x: number | null;
  end_y: number | null;
  distance_traveled: number | null;
  round_id: number | null;
  round_date: string | null;
  round_time: string | null;
  // Long form only — ABSENT (not null) when times are invalid:
  attacker_guid?: string | null;
  attacker_name?: string | null;
  target_path?: unknown[];
  attacker_path?: unknown[];
  strafe?: { target: ProxStrafeMetrics; attacker: ProxStrafeMetrics } | null;
}

export interface ProxEngagements {
  status: string;
  ready: boolean;
  message: string | null;
  range_days: number;
  generated_at: string | null;
  scope: ProxScope & { range_days?: number };
  buckets: { date: string; engagements: number; crossfires: number }[];
}

// ---------------------------------------------------------------------------
// Phase 5 — the proximity player profile (class B routes: the old React tree
// was their only consumer). Shapes read from proximity_player.py /
// proximity_scoring.py / proximity_combat.py and recorded wire samples.

export interface ProxPlayerProfile {
  player_name: string;
  guid: string;
  /** ⚠️ An unknown guid answers 200 with every number 0 and player_name
   *  echoing the guid — 0 engagements means "nothing captured", never a
   *  real profile of zeros. */
  total_engagements: number;
  escapes: number;
  deaths: number;
  escape_rate: number;
  avg_duration_ms: number;
  total_kills: number;
  crossfire_count: number;
  avg_speed: number;
  sprint_pct: number;
  avg_distance_per_life: number;
  avg_return_fire_ms: number;
  avg_dodge_ms: number;
  avg_support_reaction_ms: number;
  spawn_avg_score: number;
  timed_kills: number;
  avg_denial_ms: number;
  trades_made: number;
}

export interface ProxPlayerRadar {
  axes: { label: string; value: number }[];
  /** All three are null on the degraded form (recorded live). */
  unscored: {
    mechanical: number | null;
    avg_return_fire_ms: number | null;
    avg_dodge_reaction_ms: number | null;
  };
  formula_version: string;
  axis_definitions_from: string;
  composite: number;
  teamplay_source: string;
  teamplay_observation_window_days: number;
  teamplay_formula_version: string | null;
  teamplay_degraded: boolean;
  // Present only on the degraded/fallback form (recorded both ways):
  teamplay_sample_count?: number;
  teamplay_fallback_reason?: string | null;
}

export interface ProxScoreRow {
  guid: string;
  name: string | null;
  rank: number;
  engagements: number;
  tracks: number;
  prox_combat: number;
  prox_team: number;
  prox_gamesense: number;
  prox_overall: number;
  prox_radar: { label: string; value: number }[];
}

export interface ProxScores {
  status: string;
  version: string;
  formula_version: string;
  quality: {
    ranking_available: boolean;
    successful_sources: number;
    total_sources: number;
    failed_sources: string[];
    metric_weight_coverage: number;
    below_coverage_dropped: number;
  };
  range_days: number;
  /** prox-scores' scope is its OWN shape -- a scoped flag, no player_guid
   *  (the shared ProxScope requires one; CI's satisfies caught the drift). */
  scope: {
    scoped: boolean;
    session_date: string | null;
    map_name: string | null;
    round_number: number | null;
    round_start_unix: number | null;
  };
  player_count: number;
  players: ProxScoreRow[];
}

export interface ProxKillOutcomePlayerStats {
  status: string;
  scope: ProxScope;
  kill_permanence_leaders: {
    guid: string; name: string | null; total_kills: number; gibs: number;
    revives_against: number; tapouts: number; kpr: number; avg_denied_ms: number;
  }[];
  revive_rate_leaders: {
    guid: string; name: string | null; times_killed: number; times_gibbed: number;
    times_revived: number; times_tapped: number; revive_rate: number;
    gib_rate: number; avg_wait_ms: number;
  }[];
}

export interface ProxHitRegions {
  status: string;
  scope: ProxScope;
  players: {
    guid: string; name: string | null; head: number; body: number;
    arms: number; legs: number; total_hits: number; total_damage: number;
    head_pct: number;
  }[];
}

export interface ProxHitRegionsByWeapon {
  status: string;
  scope: ProxScope;
  weapons: {
    weapon_id: number; head: number; body: number; arms: number; legs: number;
    total: number; headshot_pct: number; total_damage: number;
  }[];
}

export interface ProxMovementStats {
  status: string;
  scope: ProxScope;
  players: {
    guid: string; name: string | null; tracks: number; alive_sec: number;
    avg_peak_speed: number; max_peak_speed: number; avg_speed: number;
    total_distance: number; standing_sec: number; crouching_sec: number;
    prone_sec: number; standing_pct: number; crouching_pct: number;
    prone_pct: number; sprint_sec: number; avg_sprint_pct: number;
    avg_post_spawn_dist: number; avg_distance_per_sec: number;
  }[];
}

// ---------------------------------------------------------------------------
// Phase 5 — the round team comparison (class B: the old React tree was its
// only consumer). ⚠️ Every cohesion/pushes number is nullable — the wire
// CANNOT tell an uncaptured round from a nonexistent one: both answer 200
// with those all null (measured live on rounds 10472 and 99999999). The
// crossfire list is different: its rows are aggregates that exist only
// when counted, so absence is an EMPTY LIST and the members stay
// non-nullable.

export interface ProxTeamComparisonSide {
  avg_dispersion: number | null;
  avg_max_spread: number | null;
  avg_stragglers: number | null;
  samples: number | null;
}

export interface ProxTeamComparison {
  cohesion: { axis: ProxTeamComparisonSide; allies: ProxTeamComparisonSide };
  pushes: {
    axis: { push_count: number | null; avg_quality: number | null; avg_alignment: number | null };
    allies: { push_count: number | null; avg_quality: number | null; avg_alignment: number | null };
  };
  crossfire: {
    target_team: string;
    total_opportunities: number;
    executed: number;
    execution_rate: number;
  }[];
}

// ---------------------------------------------------------------------------
// Phase 5 — the round replay (routes proximity-replay; parity target the old
// React tree, whose page is timeline-centric: it fetched tracks "for stats
// only" and never drew a canvas). Timeline events are a DISCRIMINATED UNION
// of exactly the four types the emitter produces (proximity_round.py — the
// old page also defended a 'crossfire' type the wire no longer sends). A
// nonexistent round answers 404 on timeline; an uncaptured one answers 200
// with the round's metadata and an empty events list. Tracks answers 404
// for BOTH (indistinguishable there).

export interface ReplayEngagementEvent {
  type: 'engagement';
  id: number;
  time: number;
  victim_name: string | null;
  victim_team: string;
  outcome: string | null;
  damage: number;
  attackers: number;
  start_x: number | null;
  start_y: number | null;
  end_x: number | null;
  end_y: number | null;
}

export interface ReplaySpawnTimingEvent {
  type: 'spawn_timing_kill';
  time: number;
  attacker_name: string | null;
  victim_name: string | null;
  score: number;
}

export interface ReplayTradeKillEvent {
  type: 'trade_kill';
  time: number;
  trader_name: string | null;
  avenged_name: string | null;
  delta_ms: number;
}

export interface ReplayTeamPushEvent {
  type: 'team_push';
  time: number;
  team: string | null;
  quality: number;
  alignment: number;
  participants: number;
  duration_ms: number;
}

export type ReplayTimelineEvent =
  | ReplayEngagementEvent
  | ReplaySpawnTimingEvent
  | ReplayTradeKillEvent
  | ReplayTeamPushEvent;

export interface ProxRoundTimeline {
  round_id: number;
  map_name: string;
  round_number: number;
  round_date: string;
  duration_ms: number;
  events: ReplayTimelineEvent[];
}

export interface ProxRoundTracks {
  status: string;
  round_id: number;
  track_count: number;
  tracks: {
    guid: string;
    name: string | null;
    team: string | null;
    class: string | null;
    spawn_time: number;
    /** Never null on the wire — the emitter coerces a missing death to 0
     *  (int(r or 0)), so 0 is the survivor/unknown sentinel. */
    death_time: number;
    first_move_time: number | null;
    death_type: string | null;
    path: unknown[];
  }[];
}

// ---------------------------------------------------------------------------
// Phase 5 — the spider web (route spider-web, /spider-web/round/:roundId).
// GET /api/replay/round/{round_id}/web?t=<ms>[&pov=team:X] — the layer-1
// reconstruction at one moment. ⛔ The point of view is a QUERY PARAMETER:
// withholding happens on the SERVER (allowlist), and fetching the oracle
// once to filter locally would quietly undo the guarantee (#800). Under a
// team pov the enemy clock carries ONLY unknown_to_this_pov + reason + the
// public interval, and withheld_by_pov names every hidden guid.

/** The clock's known form: status is one of the emitter's five quality
 *  states (validated / internally_consistent_unvalidated /
 *  validation_failed / inconsistent / insufficient). */
export interface SpiderClockKnown {
  status: string;
  interval_ms: number;
  offset_ms: number;
  timing_observations: number;
  landing_clusters: number;
  spawn_callbacks: number;
  post_revive_spawn_callbacks: number;
  passing_landing_clusters: number;
  pass_ratio: number;
  phase_ms: number;
  time_to_next_wave_ms: number;
}

/** WITHHELD is a second axis, not a sixth quality state — it must branch
 *  before any quality switch. */
export interface SpiderClockWithheld {
  status: 'unknown_to_this_pov';
  interval_ms: number;
  reason: string;
}

/** The THIRD form (the pov fixture caught it): the holder's own HUD —
 *  interval and phase without observation counts, because the grade of
 *  the reconstruction is a full-round verdict and stays in the oracle
 *  view (spec §5.3, §6.3). */
export interface SpiderClockOwnHud {
  status: 'own_hud';
  interval_ms: number;
  offset_ms: number;
  phase_ms: number;
  time_to_next_wave_ms: number;
  reason: string;
}

export type SpiderClock = SpiderClockKnown | SpiderClockWithheld | SpiderClockOwnHud;

export function isClockWithheld(c: SpiderClock): c is SpiderClockWithheld {
  return c.status === 'unknown_to_this_pov';
}

export function isClockOwnHud(c: SpiderClock): c is SpiderClockOwnHud {
  return c.status === 'own_hud';
}

export interface SpiderPlayer {
  guid: string;
  name: string | null;
  team: string;
  class: string | null;
  x: number;
  y: number;
  z: number;
  health: number;
  weapon: number;
  stance: number;
  speed: number;
  alive: boolean;
  track_id: number;
  stale_ms: number;
  overlap_conflict: boolean;
  position_error: { p50: number; p90: number; well_sampled: boolean; basis: string } | null;
  vx: number | null;
  vy: number | null;
  vz: number | null;
  velocity_stale_ms: number | null;
  velocity_reason: string | null;
}

export interface SpiderEdge {
  a: string;
  b: string;
  kind: string;
  distance: number;
  recently_contested: boolean;
}

export interface SpiderWebSnapshot {
  round_id: number;
  t_ms: number;
  map_name: string;
  round_duration_ms: number;
  teams: string[];
  first_position_ms: number;
  velocity_max_dt_ms: number;
  player_count: number;
  overlap_conflicts: number;
  players: SpiderPlayer[];
  edges: SpiderEdge[];
  clock: Record<string, SpiderClock>;
  capture_policy: {
    mode: string;
    observation_interval_ms: number | null;
    source: string;
    manifest_version: string | null;
    /** Tri-state strings per capability (the manifest's own vocabulary). */
    capabilities: Record<string, string>;
    manifest_count: number;
    conflicting_flags: number;
  };
  withheld_by_pov: string[];
  notes: string[];
}

/** Flat triangle mesh under /assets/maps/geometry/<map>.json — static, and
 *  ABSENT for some maps (etl_supply has no BSP export): a missing mesh is
 *  named, never an empty stage. */
export interface MapMesh {
  map_name: string;
  vertices: number[];
  indexes: number[];
  floor_normal_z: number;
  bounds: unknown;
}

// ---------------------------------------------------------------------------
// Phase 5 — the outcome instruments (eight date-scope panels; legacy
// proximity.js loaders documented in 07 §B.2). Shapes read from
// proximity_scoring.py / proximity_combat.py / proximity_objectives.py.

export interface ProxKillOutcomes {
  status: string;
  scope: ProxScope;
  summary: {
    total_kills: number; gibbed: number; revived: number; tapped_out: number;
    expired: number; round_end: number; gib_rate: number; revive_rate: number;
    avg_delta_ms: number; avg_denied_ms: number;
  };
  outcomes: Record<string, { count: number; avg_delta_ms: number; avg_denied_ms?: number }>;
  events: unknown[];
}

export interface ProxHeadshotRates {
  status: string;
  scope: ProxScope;
  leaders: { guid: string; name: string | null; headshot_pct: number; head_hits: number; total_hits: number }[];
}

export interface ProxTeamplay {
  status: string;
  ready: boolean;
  message: string | null;
  range_days: number;
  generated_at: string | null;
  scope: ProxScope;
  limit: number;
  sampled_engagements: number;
  crossfire_kills: {
    guid: string; name: string | null; crossfire_kills: number;
    crossfire_participations: number; crossfire_final_blows: number;
    avg_delay_ms: number; times_focused: number; focus_escapes: number;
    kill_rate_pct: number;
  }[];
  sync: unknown[];
}

export interface ProxTradesSummary {
  status: string;
  ready: boolean;
  message: string | null;
  range_days: number;
  generated_at: string | null;
  scope: ProxScope;
  events: number;
  trade_opportunities: number;
  trade_attempts: number;
  trade_success: number;
  missed_trade_candidates: number;
  support_uptime_pct: number;
  isolation_deaths: number;
}

export interface ProxTradesEvents {
  status: string;
  ready: boolean;
  message: string | null;
  range_days: number;
  generated_at: string | null;
  scope: ProxScope;
  limit: number;
  events: {
    date: string; round: number; map: string; victim: string | null;
    killer: string | null; opportunities: number; attempts: number;
    success: number; missed: number; round_id: number | null;
    round_date: string | null; round_time: string | null; outcome: string | null;
  }[];
}

export interface ProxWeaponAccuracy {
  status: string;
  leaders: { guid: string; name: string | null; shots: number; hits: number; kills: number; headshots: number; accuracy: number }[];
  /** Populated only under a player_guid filter (emitter branch). */
  weapon_breakdown: { weapon_id: number; shots: number; hits: number; kills: number; headshots: number; accuracy: number }[];
}

/** ⚠️ Its own scope vocabulary: scope_applied + scope_note, not the shared
 *  ProxScope — read from the emitter, not assumed. */
export interface ProxObjectivePressure {
  status: string;
  session_date: string | null;
  maps_counted: number;
  top_fragger_guids: string[];
  players: { guid: string; name: string | null; pressure_seconds: number; kills: number }[];
  scope_applied: Record<string, string>;
  scope_note: string;
}

export interface ProxSummary {
  status: string;
  ready: boolean;
  message: string | null;
  range_days: number;
  generated_at: string | null;
  scope: ProxScope;
  total_engagements: number;
  avg_distance_m: number;
  crossfire_events: number;
  hotzones: number;
  avg_duration_ms: number;
  avg_attackers: number;
  escape_rate_pct: number;
  kill_rate_pct: number;
}

// ---------------------------------------------------------------------------
// Phase 5 — the player page additions (four paths). Shapes from
// proximity_competitive.py / proximity_combat.py / proximity_scoring.py.

export interface ProxPlayerCard {
  status: string;
  scope: ProxScope;
  player: { guid: string; name: string | null };
  range_days: number;
  timeline_range_days: number;
  stagger: { kills: number; stagger_kills: number; stagger_rate: number; denied_s: number; avg_score: number };
  sides: {
    attack: { kills: number; denied_s: number };
    defense: { kills: number; denied_s: number };
  };
  clutch: {
    situations: number;
    wins: number;
    best: { enemies: number; kills: number; survived: boolean } | null;
    win_pct: number;
  };
  man_advantage: { conversions: number };
}

export interface ProxDuos {
  status: string;
  ready: boolean;
  message: string | null;
  range_days: number;
  generated_at: string | null;
  /** ⚠️ scope.player_guid comes back TRUNCATED to 8 chars (the guid[:8]
   *  family) — display-only; the filter itself accepts the full guid. */
  scope: ProxScope;
  limit: number;
  duos: { player1: string | null; player2: string | null; crossfire_kills: number; crossfire_count: number; avg_delay_ms: number }[];
}

export interface ProxTradesPlayerStats {
  status: string;
  ready: boolean;
  message: string | null;
  range_days: number;
  generated_at: string | null;
  scope: ProxScope;
  players: {
    /** ⚠️ EIGHT-char guid on this wire (the guid[:8] family) — match by
     *  prefix, never by full-guid equality. */
    guid: string; name: string | null; trade_opps: number; trade_attempts: number;
    trade_success: number; trade_missed: number; isolation_deaths: number;
    avenged_count: number; avenger_attempt_events: number; avenger_attempt_damage: number;
  }[];
}

export interface ProxScoresFormula {
  status: string;
  version: string;
  min_engagements: number;
  category_weights: Record<string, number>;
  categories: Record<string, {
    label: string;
    description: string;
    weight_in_overall: number;
    metrics: Record<string, { label: string; weight: number; invert: boolean }>;
  }>;
}

// ---------------------------------------------------------------------------
// Phase 5 — the map overlays (the last seven pending paths). Shapes from
// proximity_positions.py / proximity_combat.py.

export interface ProxDangerZones {
  status: string;
  map_name: string;
  grid_size: number;
  /** class -> deaths; undefined is what a lookup of an absent class
   *  returns anyway (and it lets recorded zones with differing class keys
   *  satisfy the type — the weapons-map lesson). */
  zones: { x: number; y: number; deaths: number; classes: Record<string, number | undefined> }[];
}

export interface ProxCombatHeatmap {
  status: string;
  map_name: string;
  grid_size: number;
  perspective: string;
  hotzones: { x: number; y: number; count: number }[];
}

export interface ProxKillLines {
  status: string;
  map_name: string;
  lines: { ax: number; ay: number; vx: number; vy: number; weapon_id: number; attacker_team: string | null }[];
}

export interface ProxHotzones {
  status: string;
  ready: boolean;
  message: string | null;
  range_days: number;
  generated_at: string | null;
  scope: ProxScope;
  map_name: string;
  hotzones: { x: number; y: number; count: number; kills: number; deaths: number }[];
  grid_size: number;
  source: string;
}

export interface ProxMoversRow { guid: string; name: string | null; tracks: number }
export interface ProxMovers {
  status: string;
  ready: boolean;
  message: string | null;
  range_days: number;
  generated_at: string | null;
  scope: ProxScope;
  limit: number;
  distance: (ProxMoversRow & { total_distance: number })[];
  sprint: (ProxMoversRow & { sprint_pct: number })[];
  reaction: unknown[];
  survival: unknown[];
}

/** mode ∈ kills_from | victims_die | player_dies | presence | aim — the
 *  endpoint 400s without one (its own words, rendered verbatim). */
export interface ProxPlayerHeatmap {
  status: string;
  map_name: string;
  mode: string;
  grid_size: number;
  player_guid: string;
  player_name: string | null;
  hotzones: { x: number; y: number; count: number }[];
  total: number;
  sampled: boolean;
  scope: ProxScope;
}

export interface ProxPlayerAim {
  status: string;
  map_name: string;
  player_guid: string;
  player_name: string | null;
  grid_size: number;
  total: number;
  sampled: boolean;
  scope: ProxScope;
  hotzones: { x: number; y: number; count: number }[];
  yaw_buckets: number;
  yaw_bucket_width_deg: number;
  pitch_hist: { edges: number[]; counts: number[] };
}

// ---------------------------------------------------------------------------
// Phase 6 — availability (docs/design 07 §B.4; legacy availability.js).
// The surface has THREE auth tiers, all recorded: anonymous (401 on gated
// paths), authenticated-but-unlinked Discord (403 with its own words), and
// linked (200). 401/403 are STATES here, not failures.

export interface AvailabilityAccess {
  authenticated: boolean;
  linked_discord: boolean;
  can_submit: boolean;
  is_admin: boolean;
  can_promote: boolean;
  website_user_id: number | null;
}

export type AvailabilityStatus = 'LOOKING' | 'AVAILABLE' | 'MAYBE' | 'NOT_PLAYING';
// The week shape ALREADY lives above as AvailabilityOverview/AvailabilityDay
// (#830, with the documented my_status tri-state) — reused, not redeclared.

export interface PlanningToday {
  date: string;
  session_ready: { ready: boolean; looking_count: number; threshold: number };
  unlocked: boolean;
  participant_count: number;
  participants: { user_id: number; display_name: string | null; status: string }[];
  /** Dev backends serve mock planning rows and SAY so — rendered, not hidden. */
  is_mock?: boolean;
}

// Slice 2 — the shapes below are read off the HANDLERS (no response_model
// on any availability/bets route: openapi has no schema to pin them, so
// tests/unit/test_availability_slice2_fixtures.py replays each handler in
// its harness and diffs the committed fixture against what it returns).

/** bets_router._pool_split + _market_dict (bets_router.py:130-165). */
export interface BetsPoolSide { pool: number; bets: number }
export interface BetsPool { team_a: BetsPoolSide; team_b: BetsPoolSide; total_pool: number }
export interface BetsMyBet {
  /** 'team_a' | 'team_b' — a string on the wire (JSON fixtures infer string;
   *  the page narrows by comparison, never by cast). */
  choice: string;
  amount: number;
  /** NOT NULL DEFAULT 0 in parimutuel_bets — 0 until settlement pays. */
  payout: number;
  /** 'open' while the bet stands; 'won' | 'lost' | 'refunded' after settlement. */
  status: string;
}
export interface BetsMarket {
  id: number;
  gaming_session_id: number | null;
  session_date: string | null;
  team_a_label: string;
  team_b_label: string;
  /** 'open' accepts bets; 'closed' is locked; 'settled' carries `outcome`. */
  status: string;
  /** 'team_a' | 'team_b' | 'void' once settled; null before. */
  outcome: string | null;
  pool: BetsPool;
  /** null when the viewer is anonymous or has not bet on this market. */
  my_bet: BetsMyBet | null;
}

export interface BetsMarketCurrent {
  status: string;
  market: BetsMarket | null;
}

/** GET /api/bets/wallet (bets_router.py:166-174); 401 anonymous. */
export interface BetsWallet { status: string; balance: number; lifetime_earned: number }

/** POST /api/bets/market/{market_id}/bet (bets_router.py:320). */
export interface BetPlaceResponse {
  status: string;
  balance: number;
  choice: string;
  amount: number;
  pool: BetsPool;
}

/** availability.py:_campaign_payload (:1367-1435) — aggregate-only campaign
 *  metadata; the recipient snapshot never leaves the server. */
export interface PromotionCampaignJob {
  id: number;
  job_type: string;
  run_at: string | null;
  status: string;
  attempts: number;
  max_attempts: number;
  last_error: string | null;
  sent_at: string | null;
}
export interface PromotionCampaignPayload {
  id: number;
  campaign_date: string;
  target_timezone: string;
  target_start_time: string;
  initiated_by_user_id: number;
  initiated_by_discord_id: number;
  include_maybe: boolean;
  include_available: boolean;
  dry_run: boolean;
  status: string;
  recipient_count: number;
  channels_summary: Record<string, number>;
  created_at: string | null;
  updated_at: string | null;
  jobs: PromotionCampaignJob[];
}

export interface PromotionCampaign {
  campaign: PromotionCampaignPayload | null;
}

/** GET /api/availability/promotions/preview (availability.py:1547-1575);
 *  401 anonymous, 403 unlinked / not a promoter, each with its own words. */
export interface PromotionPreview {
  campaign_date: string;
  target_time_cet: string;
  reminder_time_cet: string;
  recipient_count: number;
  channels_summary: Record<string, number>;
  /** _public_campaign_recipients (:309): name, status, routed channel —
   *  the legacy modal threw this list away. */
  recipients_preview: { display_name: string; status: string; selected_channel: string }[];
}

/** POST /api/availability/promotions/campaigns (availability.py:1726-1741);
 *  409 when today's campaign already exists, with the backend's sentence. */
export interface CampaignCreateResponse {
  success: boolean;
  campaign_id: number;
  campaign_date: string;
  status: string;
  recipient_count: number;
  channels_summary: Record<string, number>;
  scheduled_times: { reminder_2045_cet: string; start_2100_cet: string; voice_check_after_start: string };
  dry_run: boolean;
}

/** availability.py:_fetch_subscriptions_map (:330-375): one row per channel
 *  in CHANNEL_TYPES order (discord, telegram, signal). Discord is always
 *  enabled+verified (it IS the identity); telegram/signal are verified only
 *  after the link-token round trip. */
export interface AvailabilitySubscription {
  /** 'discord' | 'telegram' | 'signal' (CHANNEL_TYPES); string on the wire. */
  channel_type: string;
  enabled: boolean;
  channel_address: string | null;
  verified: boolean;
  preferences: Record<string, unknown>;
}
export interface AvailabilitySubscriptions { user_id: number; subscriptions: AvailabilitySubscription[] }

/** availability.py:_settings_payload (:378-412). `get_ready_sound` mirrors
 *  `sound_enabled` (legacy field name kept on the wire). */
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
  subscriptions: AvailabilitySubscription[];
}

/** POST /api/availability/link-token (availability.py:1044-1108); 429 with
 *  "Link token was generated recently. Try again in Ns" inside the
 *  per-channel minimum interval. */
export interface LinkTokenResponse {
  success: boolean;
  channel_type: string;
  token: string;
  expires_at: string;
}

/** POST /api/availability/subscriptions (availability.py:923-994). */
export interface SubscriptionWriteResponse {
  success: boolean;
  user_id: number;
  channel_type: string;
  enabled: boolean;
  channel_address: string | null;
  preferences: Record<string, unknown>;
}

/** DELETE /api/availability/subscriptions/{channel_type} (:996-1042). */
export interface SubscriptionUnlinkResponse {
  success: boolean;
  user_id: number;
  channel_type: string;
  unlinked: boolean;
}

export interface PromotionPreferences {
  user_id: number;
  allow_promotions: boolean;
  preferred_channel: string;
  telegram_handle_masked: string | null;
  signal_handle_masked: string | null;
  quiet_hours: Record<string, unknown>;
  timezone: string;
  notify_threshold: number;
}

// ---------------------------------------------------------------------------
// Phase 6 — uploads (legacy uploads.js). uploader_discord_id travels as a
// STRING — an 18-digit snowflake loses its last digit as a JS number (the
// #850-era fix; the satisfies pin below is what keeps it fixed).

export interface UploadItem {
  id: string;
  title: string;
  filename: string;
  category: string;
  extension: string;
  file_size_bytes: number;
  /** Never null per the backend UploadListItem contract. */
  uploader_name: string;
  uploader_discord_id: string | null;
  /** Nullable per the contract even when every recording carries them. */
  download_count: number | null;
  created_at: string | null;
  description_preview: string | null;
  expires_at: string | null;
  share_url: string;
  poster_url: string | null;
}

export interface UploadsList {
  items: UploadItem[];
  total: number;
  limit: number;
  offset: number;
  sort: string;
}

export interface UploadDetail {
  id: string;
  title: string;
  filename: string;
  category: string;
  extension: string;
  file_size_bytes: number;
  /** Never null per the API schema (the drift checker is the arbiter). */
  uploader_name: string;
  uploader_discord_id: string | null;
  /** Nullable per the API schema even though every recording carries one —
   *  the reader guards, the sample does not decide (#830's lesson). */
  download_count: number | null;
  created_at: string | null;
  description: string | null;
  expires_at: string | null;
  tags: string[];
  mime_type: string | null;
  content_hash: string;
  is_playable: boolean;
  poster_url: string | null;
  download_url: string;
  share_url: string;
  can_delete: boolean;
}

// Slice 2 — the write shapes, read off the handlers (no response_model on
// any uploads write route: tests/unit/test_uploads_slice2_fixtures.py replays
// them and diffs the live-recorded fixtures).

/** POST /api/uploads and POST …/resumable/{id}/finalize share
 *  uploads.py:_persist_upload (:146-157). `failed_tags`/`warning` appear
 *  only when a tag insert failed. */
export interface UploadCreated {
  upload_id: string;
  filename: string;
  title: string;
  category: string;
  file_size_bytes: number;
  share_url: string;
  failed_tags?: string[];
  warning?: string;
}

/** POST /api/uploads/resumable (uploads.py:369). */
export interface ResumableInitResponse {
  session_id: string;
  offset: number;
  chunk_size: number;
  category: string;
}

/** DELETE /api/uploads/{upload_id} (uploads.py:937). */
export interface UploadDeleteResponse {
  success: boolean;
  message: string;
}

// ---------------------------------------------------------------------------
// Phase 6 — greatshot (legacy greatshot.js): per-user demo analysis. The
// whole surface is auth-gated (401 anonymous = a state). Shapes from a
// LIVE recording: a real demo uploaded and analyzed on this branch.

export interface GreatshotItem {
  id: string;
  filename: string;
  status: string;
  error: string | null;
  created_at: string | null;
  processing_started_at: string | null;
  processing_finished_at: string | null;
  map: string | null;
  duration_ms: number | null;
  mod: string | null;
  warnings: string[];
  highlight_count: number;
  render_job_count: number;
  rendered_count: number;
}

export interface GreatshotList { items: GreatshotItem[] }

export interface GreatshotStatus {
  status: string;
  error: string | null;
  processing_started_at: string | null;
  processing_finished_at: string | null;
  highlight_count: number;
  map: string | null;
}

export interface GreatshotHighlight {
  id: string;
  type: string;
  player: string | null;
  start_ms: number;
  end_ms: number;
  score: number | null;
  meta: Record<string, unknown>;
  explanation: string | null;
  clip_demo_path: string | null;
  clip_download: string | null;
  created_at: string | null;
}

export interface GreatshotDetail {
  id: string;
  filename: string;
  status: string;
  error: string | null;
  created_at: string | null;
  processing_started_at: string | null;
  processing_finished_at: string | null;
  warnings: string[];
  metadata: Record<string, unknown>;
  analysis: Record<string, unknown> | null;
  player_stats: Record<string, unknown>;
  highlights: GreatshotHighlight[];
  renders: unknown[];
  downloads: { json: string; txt: string };
}

// Phase 6 — the live surface (legacy live-state/status/ticker). The roster
// LINGERS through delivery gaps with roster_age_seconds so the UI can dim
// it instead of oscillating full↔empty (live_state.py's own contract).

export interface LiveFeed {
  status: string;
  /** Typed loosely on purpose: each event is {seq, type, received_at, …}
   *  with per-type payloads; the recorded quiet-server form has none, so
   *  renderable richness waits for a recording that carries them. */
  events: { seq: number; type: string; [k: string]: unknown }[];
  oldest_seq: number | null;
  last_seq: number;
  server_time: number;
}

export interface ActivityHistory {
  data_points: { timestamp: string; player_count: number; max_players: number; map: string | null; online: boolean }[];
  summary: { peak_players: number; peak_time: string | null; avg_players: number; uptime_percent: number; total_records: number };
}

export interface VoiceHistory {
  /** members is a JSON STRING inside the JSON (the position_path class). */
  data_points: { timestamp: string; member_count: number; channel_name: string | null; members: string }[];
  summary: { peak_members: number; peak_time: string | null; avg_members: number; total_sessions: number; total_records: number };
}

export interface MonitoringStatus {
  server: { count: number; last_recorded_at: string | null; age_seconds: number | null; is_stale: boolean; stale_threshold_seconds: number };
  voice: { count: number; last_recorded_at: string | null; age_seconds: number | null; is_stale: boolean; stale_threshold_seconds: number };
}

export interface ApiHealth {
  status: string;
  service: string;
  database: string;
}

// ── /api/diagnostics (admin) ────────────────────────────────────────────────
//
// A UNION, not the shape a healthy database happens to return. Every field
// below is a branch of get_diagnostics (website/backend/routers/
// diagnostics_router.py): a table check can succeed with a count or fail
// three different ways, the time block is `{}` when its query raised, a
// monitoring table can answer with an error instead of a timestamp, and the
// pool has three forms. Typing only the recorded branch would let the page
// render `undefined` the first time the dev database is anything but healthy.

/** ok — the count is present. The other three carry `error` instead. */
export type DiagnosticsTableStatus = 'ok' | 'permission_denied' | 'not_found' | 'error';

export interface DiagnosticsTable {
  name: string;
  status: DiagnosticsTableStatus;
  /** Present only on `ok`. Absent is not zero: a table nobody could read has
   *  no count, and rendering one would invent a fact. */
  row_count?: number;
  /** Present on every status but `ok`. */
  error?: string;
  required: boolean;
}

/** Empty object when the timing query raised — the handler leaves `time` as
 *  `{}` and pushes the reason into `warnings`. */
export interface DiagnosticsTime {
  raw_dead_seconds?: number;
  agg_dead_seconds?: number;
  cap_seconds?: number;
  cap_hits?: number;
  raw_denied_seconds?: number;
}

export interface DiagnosticsMonitoringTable {
  count: number;
  last_recorded_at: string | null;
  /** Set instead of a real reading when the query failed. */
  error?: string;
}

/** `connected` is on every branch on purpose (the handler says so in a
 *  comment): one key to switch on, not three shapes to sniff. */
export interface DiagnosticsPool {
  connected: boolean;
  reason?: string;
  error?: string;
  size?: number;
  idle?: number;
  in_use?: number;
  min_size?: number;
  max_size?: number;
  utilisation_pct?: number;
}

export interface Diagnostics {
  /** ok | warning (warnings only) | error (at least one issue). */
  status: string;
  timestamp: string | null;
  database: { status: string; tests?: unknown[]; error?: string };
  tables: DiagnosticsTable[];
  issues: string[];
  warnings: string[];
  time: DiagnosticsTime;
  monitoring: { server?: DiagnosticsMonitoringTable; voice?: DiagnosticsMonitoringTable };
  pool?: DiagnosticsPool;
}
