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
  leaders: Record<string, { player: string; value: number } | null>;
}

/** GET /api/seasons/current/summary — corpus: api_seasons_current_summary.json */
export interface SeasonSummary {
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
   *  the endpoint still answered 200). Optional because the field arrives
   *  with #830 — until then it is absent and the emptiness heuristic below
   *  is all there is. `note` carries the reason when the state is not ok. */
  status?: string;
  note?: string;
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
  guid: string;
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
  /** Same three states as the activity calendar (#830): `ok`, `no_data`,
   *  `unavailable`. Absent until that lands; present afterwards, and then
   *  it — not the emptiness of `leaders` — decides whether this is an
   *  outage rather than a quiet season. */
  status?: string;
  note?: string;
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
  map_name: string;
  /** Nullable in the handler — `str(row[2]) if row[2] else None`, the same
   *  expression as /rounds/recent. Neither of us has ever seen a null here;
   *  the branch exists, so the type says so and the page prints "unknown"
   *  rather than a blank cell (#830). */
  round_date: string | null;
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
 *  is that much less measured, which the page has to say out loud. */
export interface StorySynergy {
  status: string;
  groups: { group_a: StorySynergyGroup; group_b: StorySynergyGroup };
  weights: Record<string, number>;
  defaulted_players_count: number;
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
 *  it ignores range and scope by owner decision A4). Entries are a
 *  DISCRIMINATED family by request category — each branch of the handler
 *  returns its own fixed extras (typed from the handler, not the sample).
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
