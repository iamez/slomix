"""
Session-related endpoints: last-session, session lists, session details, graphs.

Extracted from api.py to reduce file size and improve maintainability.
"""

import math
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict

from shared.config import load_config
from shared.round_time import round_duration_sql
from shared.services.session_stats_aggregator import SessionStatsAggregator
from shared.services.stopwatch_scoring_service import StopwatchScoringService
from shared.utils import escape_like_pattern
from website.backend.dependencies import get_db, require_user
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.logging_config import get_app_logger
from website.backend.middleware.auth_helpers import require_ajax_csrf_header
from website.backend.routers.api_helpers import (
    normalize_map_name as _normalize_map_name,
)
from website.backend.routers.api_helpers import (
    resolve_alias_guid_map,
    resolve_name_guid_map,
)
from website.backend.services.session_awards_service import (
    computed_awards,
    group_by_category,
    roll_up,
)
from website.backend.services.session_matrix_service import SessionMatrixService
from website.backend.services.session_scope import resolve_gaming_session_scope
from website.backend.services.website_session_data_service import (
    WebsiteSessionDataService as SessionDataService,
)
from website.backend.utils.et_constants import strip_et_colors

router = APIRouter()


class SessionSummary(BaseModel):
    """One session in the list.

    ⛔ THE COLUMN'S NULLABILITY IS NOT THE FIELD'S. `session_results.
    team_1_score` and `winning_team` are NOT NULL in the schema — and null in
    84 of 137 responses, because the query LEFT JOINs the BOX table and a
    session without team attribution has no row to join. Reading
    `information_schema` alone would have typed all five team fields
    non-null and answered 500 on the majority of sessions.

    So the rule needs a third step after "schema, then handler": what the JOIN
    does to it. A LEFT JOIN manufactures nulls from columns that forbid them.
    """

    date: str
    session_id: int
    rounds: int
    maps: int
    players: int
    total_kills: int
    #: Split from a comma-joined string; empty when the column was null.
    maps_played: list[str]
    #: Map wins by SIDE — sides swap every map, so these are not team totals.
    allies_wins: int
    axis_wins: int
    draws: int
    #: All five are null together when the session has no BOX attribution.
    team_1_name: str | None
    team_2_name: str | None
    team_1_score: int | None
    team_2_score: int | None
    winning_team: int | None
    #: The five that #848 added to the handler after this model was frozen at
    #: the sibling's 13+2+2 (verifier's dry run measured every one COALESCE'd
    #: in the outer SELECT, so none is nullable; duration is bigint on the
    #: live base, no Decimal trap):
    total_deaths: int
    duration_seconds: int
    player_names: list[str]
    start_time: str
    end_time: str
    #: Rendered by the handler ("2 days ago", "Friday, August 28, 2026") —
    #: presentation the legacy pages already depend on, not raw data.
    time_ago: str
    formatted_date: str


class SessionLeaderRow(BaseModel):
    """One row of the session DPM leaderboard.

    ⛔ TYPED FROM THE SCHEMA AND THE AGGREGATE, NOT THE SAMPLE.

      name    `MAX(player_name)` over a NOT NULL column — never null.
      dpm     the CASE has an `ELSE 0`, and the handler wraps it in `int()`.
      kills   `SUM(kills)` over a NULLABLE column. SUM returns NULL when every
      deaths  summed value is NULL, and the handler passes the result through
              with no guard. Zero such rows exist today; the column and the
              aggregate both say it is reachable, and "zero rows today" is not
              a type — a stricter model would answer 500 the first time it
              happened rather than dropping a field.

    Requested by the session-detail workstream ahead of phase 4, so that page
    can be written against a schema instead of against a sample.
    """

    #: 1-based position, assigned by the handler after ordering by dpm.
    rank: int
    name: str
    dpm: int
    kills: int | None
    deaths: int | None


logger = get_app_logger("api.sessions")



#: The session's counted rounds — the SAME trio as the sessions list and the
#: weapons expansion (Codex on #855, round six), plus no bot rounds. Shared
#: by /detail, /basics and /awards so their totals cannot disagree.
SESSION_ROUNDS_SQL = """
        SELECT r.id, r.map_name, r.round_number, r.winner_team,
               r.round_date, r.round_time, r.actual_time, r.round_start_unix,
               r.actual_duration_seconds
        FROM rounds r
        WHERE r.gaming_session_id = $1
          AND r.round_number IN (1, 2)
          -- The SAME trio as the sessions list and the weapons expansion
          -- (Codex on #855, round six): the detail carried only the status
          -- gate, so its totals disagreed with both — sessions 151, 147,
          -- 146, 128 and 127 hold completed-but-invalid rounds that the
          -- list excluded and this endpoint counted.
          AND r.is_valid IS DISTINCT FROM FALSE
          AND r.is_bot_round IS DISTINCT FROM TRUE
          AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
        ORDER BY r.round_date, CAST(REPLACE(r.round_time, ':', '') AS INTEGER)
    """

#: Players who are not people. The detail keeps them (it always did); the
#: basics table and the awards drop them.
_BOT_PLAYER_FILTER = "AND UPPER(p.player_guid) NOT LIKE 'OMNIBOT%' AND p.player_name NOT LIKE '%[BOT]%'"


def session_player_sql(placeholders: str, *, exclude_bots: bool) -> str:
    """Per-player totals over the session's counted rounds. Column ORDER is a
    contract — /detail and /basics index the row positionally; new columns go
    at the end (useless_kills is #25)."""
    return f"""
        SELECT
            p.player_guid,
            MAX(p.player_name) as player_name,
            SUM(p.kills) as kills,
            SUM(p.deaths) as deaths,
            SUM(p.damage_given) as damage_given,
            SUM(p.damage_received) as damage_received,
            CASE
                WHEN SUM(p.time_played_seconds) > 0
                THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
                ELSE 0
            END as dpm,
            CASE
                WHEN SUM(p.deaths) > 0
                THEN ROUND(SUM(p.kills)::numeric / SUM(p.deaths), 2)
                ELSE SUM(p.kills)::numeric
            END as kd,
            SUM(p.headshot_kills) as headshot_kills,
            SUM(p.kills) as total_kills_for_hs,
            SUM(p.gibs) as gibs,
            SUM(p.self_kills) as self_kills,
            SUM(COALESCE(p.most_useful_kills, 0)) as useful_kills,
            SUM(COALESCE(p.full_selfkills, 0)) as full_selfkills,
            SUM(p.revives_given) as revives_given,
            SUM(p.times_revived) as times_revived,
            SUM(p.time_played_seconds) as time_played_seconds,
            SUM(p.kill_assists) as kill_assists,
            SUM(LEAST(COALESCE(p.time_dead_minutes, 0), p.time_played_seconds / 60.0)) as time_dead_minutes,
            SUM(p.denied_playtime) as denied_playtime,
            COALESCE(SUM(w.hits), 0) as total_hits,
            COALESCE(SUM(w.shots), 0) as total_shots,
            COALESCE(SUM(w.headshots), 0) as weapon_headshots,
            SUM(p.time_played_percent * p.time_played_seconds) as tpp_weighted_sum,
            SUM(CASE WHEN p.time_played_percent > 0 THEN p.time_played_seconds ELSE 0 END) as tpp_weight,
            SUM(COALESCE(p.useless_kills, 0)) as useless_kills
        FROM player_comprehensive_stats p
        LEFT JOIN (
            SELECT round_id, player_guid,
                SUM(hits) as hits, SUM(shots) as shots, SUM(headshots) as headshots
            FROM weapon_comprehensive_stats
            WHERE weapon_name NOT IN ('WS_GRENADE', 'WS_SYRINGE', 'WS_DYNAMITE',
                                      'WS_AIRSTRIKE', 'WS_ARTILLERY', 'WS_SATCHEL', 'WS_LANDMINE')
            GROUP BY round_id, player_guid
        ) w ON p.round_id = w.round_id AND p.player_guid = w.player_guid
        WHERE p.round_id IN ({placeholders})
        {_BOT_PLAYER_FILTER if exclude_bots else ""}
        GROUP BY p.player_guid
        ORDER BY dpm DESC
    """


async def build_session_scoring(
    session_date: str,
    session_ids: list | None,
    data_service: SessionDataService,
    scoring_service: StopwatchScoringService,
):
    """
    Build scoring payload with debug info and warnings.
    """
    scoring_payload = {
        "available": False,
        "reason": "No hardcoded teams available",
    }
    warnings = []
    debug = []

    if not session_ids:
        return scoring_payload, warnings, None

    hardcoded_teams = await data_service.get_hardcoded_teams(session_ids)
    if not hardcoded_teams or len(hardcoded_teams) < 2:
        return scoring_payload, warnings, hardcoded_teams

    team_rosters = {}
    for team_name, players in hardcoded_teams.items():
        if isinstance(players, dict):
            guids = players.get("guids", [])
        else:
            guids = []
            for p in players:
                if isinstance(p, dict) and "guid" in p:
                    guids.append(p["guid"])
                elif isinstance(p, str):
                    guids.append(p)
        team_rosters[team_name] = guids

    if len(team_rosters) < 2:
        return scoring_payload, warnings, hardcoded_teams

    scoring_result = await scoring_service.calculate_session_scores_with_teams(session_date, session_ids, team_rosters)
    if not scoring_result:
        scoring_payload = {
            "available": False,
            "reason": "Scoring not available for this session",
        }
        return scoring_payload, warnings, hardcoded_teams

    maps = scoring_result.get("maps", []) or []
    fallback_maps = []
    incomplete_maps = []
    for m in maps:
        source = m.get("scoring_source")
        if source == "time":
            fallback_maps.append(m.get("map"))
        if source in ("incomplete", "ambiguous"):
            incomplete_maps.append(m.get("map"))
        debug.append(
            {
                "map": m.get("map"),
                "winner_side": m.get("winner_side"),
                "r1_defender_side": m.get("r1_defender_side"),
                "team_a_r1_side": m.get("team_a_r1_side"),
                "team_a_r2_side": m.get("team_a_r2_side"),
                "scoring_source": source,
                "counted": m.get("counted", True),
                "note": m.get("note"),
            }
        )

    if fallback_maps:
        warnings.append(
            "Lua header winner missing: used time fallback for " + ", ".join([m for m in fallback_maps if m])
        )
    if incomplete_maps:
        warnings.append("Incomplete maps (R1 only / ambiguous): " + ", ".join([m for m in incomplete_maps if m]))

    scoring_payload = {
        "available": True,
        "team_a_name": scoring_result.get("team_a_name", "Team A"),
        "team_b_name": scoring_result.get("team_b_name", "Team B"),
        "team_a_score": scoring_result.get("team_a_maps", 0),
        "team_b_score": scoring_result.get("team_b_maps", 0),
        "maps": maps,
        "total_maps": scoring_result.get("total_maps", 0),
        "debug": debug,
    }

    return scoring_payload, warnings, hardcoded_teams


class SessionPlayerRow(BaseModel):
    """One player's totals for the session.

    ⭐ THIS ONE CLASS SERVES TWO FIELDS. `teams[].players[]` and
    `unassigned_players[]` are literally the same `player_payload` dict — the
    handler appends it to the team roster when the name resolves and to the
    unassigned list when it does not. Verified on a live response rather than
    inferred: both carry the same 25 keys with the same types, symmetric
    difference empty.

    `kd` is the only float; every other figure is `int(x or 0)` in the handler.
    """

    guid: str
    name: str
    kills: int
    deaths: int
    kd: float
    dpm: int
    damage_given: int
    damage_received: int
    gibs: int
    headshot_kills: int
    revives_given: int
    times_revived: int
    useful_kills: int
    kill_assists: int
    self_kills: int
    full_selfkills: int
    double_kills: int
    triple_kills: int
    quad_kills: int
    multi_kills: int
    mega_kills: int
    time_played_seconds: int
    time_dead_seconds: int
    time_dead_seconds_raw: int
    denied_playtime: int


class SessionTeam(BaseModel):
    name: str
    players: list[SessionPlayerRow]


class SessionMatchRow(BaseModel):
    """One round of the session, as the match list carries it."""

    id: int
    #: `rounds.map_name` is nullable and neither query filters on
    #: it — Codex on #830, second pass.
    map_name: str | None
    round_number: int
    #: `rounds.round_date` is nullable; an undated round in an otherwise
    #: dated session reaches this field unchanged.
    date: str | None
    #: NULL when neither `actual_duration_seconds` nor `actual_time`
    #: resolves — Codex on #830.
    duration: str | None
    winner: str
    #: `rounds.round_outcome` is nullable and passed through raw. 26 rows
    #: carry NULL today; none fell in the eight sampled sessions, which is
    #: exactly why sampling did not find this.
    outcome: str | None


class _ScoringMapCommon(BaseModel):
    """The fifteen fields every scoring map carries, whatever branch made it."""

    model_config = ConfigDict(extra="forbid")

    #: Nullable for the same reason as `SessionMatchRow.map_name`: the
    #: scoring service copies the round's map name through unchanged.
    map: str | None
    emoji: str
    description: str
    winner: str
    #: `int | None` — measured null on 8 of 48 rows across eight sessions.
    winner_side: int | None
    counted: bool
    scoring_source: str
    r1_defender_side: int | None
    #: None on the `incomplete` and `ambiguous` branches — Codex on #830.
    team_a_r1_side: int | None
    team_a_r2_side: int | None
    team_a_points: int
    team_b_points: int
    team_a_time: str
    team_b_time: str


class ScoringMapAmbiguous(_ScoringMapCommon):
    """A map whose roster changed mid-session: FIFTEEN keys, no bookkeeping.

    ⛔ THE SERVICE PRODUCES THREE SHAPES HERE AND I MODELLED ONE. Reading
    `calculate_session_scores_with_teams` for its `map_results.append` calls:
    18 keys (with `note`), 17 (without), and this 15-key branch, which omits
    `match_id`, `round_start_unix` AND `map_play_seq` because side attribution
    is genuinely unknown. Eight sampled sessions produced only the 17-key
    shape, so the model required three fields this branch never sends.

    ⚠️ AND `int | None` WITHOUT A DEFAULT IS STILL REQUIRED IN PYDANTIC V2 —
    nullable is not optional. Widening those three to `| None` would not have
    fixed it; only their ABSENCE from this member does (Codex on #830).
    """

    note: str


class ScoringMapRow(_ScoringMapCommon):
    """A normally paired map: seventeen keys."""

    match_id: str | None
    #: ⚠️ `rounds.round_start_unix` is nullable AND 2,185 of 3,176 rows are
    #: NULL right now — the most recent of them on 2026-08-27, the newest
    #: session day there is. The service writes `r1.get('round_start_unix')`
    #: with no filter. Eight sampled sessions passed only because their
    #: paired maps happened to have it.
    round_start_unix: int | None
    map_play_seq: int | None


class ScoringMapWithNote(ScoringMapRow):
    """…and eighteen when the branch attaches an explanation.

    A separate member rather than `note: str | None = None` on the row above,
    because a default would put `"note": null` on every one of the 48 sampled
    maps that does not carry one.
    """

    note: str


class ScoringDebugRow(BaseModel):
    """Per-map scoring trace. `note` was null on all 48 sampled rows."""

    map: str | None
    counted: bool
    scoring_source: str
    winner_side: int | None
    #: The R1-only and roster-change branches set this from
    #: `r1.get('defender_team')` WITHOUT the normalisation the paired branch
    #: applies, so a nullable column value arrives raw here even though
    #: `_ScoringMapCommon` already accepts it — Codex on #830.
    r1_defender_side: int | None
    team_a_r1_side: int | None
    team_a_r2_side: int | None
    note: str | None


class ScoringUnavailable(BaseModel):
    """Scoring could not be built: `{"available": false, "reason": "…"}`.

    ⛔ THE SHAPE SAMPLING NEVER SHOWS. All EIGHT sessions in the corpus —
    every session day there is — returned the other one, so a model built from
    measurement alone makes `maps` and `team_a_name` required and answers 500
    the first time a session takes an early return. There are FOUR of them in
    `build_session_scoring`: no session ids, fewer than two hardcoded teams,
    fewer than two rosters, no scoring result. Forcing the second confirms the
    shape: HTTP 200, two keys, and `unassigned_players` fills with the six
    players that could not be placed on a team.

    ⭐ A corpus that agrees with itself is not a contract. It is one branch
    that happened to win eight times.
    """

    available: bool
    reason: str


class ScoringAvailable(BaseModel):
    """Scoring was built: the eight-key shape with both teams and the maps."""

    available: bool
    maps: list[ScoringMapWithNote | ScoringMapRow | ScoringMapAmbiguous]
    debug: list[ScoringDebugRow]
    team_a_name: str
    team_b_name: str
    team_a_score: int
    team_b_score: int
    total_maps: int


class LastSession(BaseModel):
    """The most recent gaming session, as `/stats/last-session` returns it.

    ⚠️ `warnings`, `stats_checks` and `unassigned_players` were EMPTY in all
    eight sampled sessions, so none of their element shapes came from the
    sample. `warnings` and `stats_checks` are f-strings built in the handler;
    `unassigned_players` carries `SessionPlayerRow`, which was then confirmed
    by forcing the branch that fills it. An empty list tells you a field's
    name and nothing about its contents.

    `map_counts` is keyed by map name, so it is a dict, not a model.

    ⛔ `response_model` FILTERS: a field the handler returns and this model
    omits is dropped silently with a 200.
    """

    date: str
    player_count: int
    rounds: int
    #: ⚠️ `rounds.map_name` is nullable and `fetch_session_data()` does not
    #: exclude unresolved rounds, so an unnamed map reaches both this list and
    #: the KEYS of `map_counts` below. Measured: pydantic rejects `None` in a
    #: `list[str]` and rejects a `None` key in a `dict[str, int]` outright, so
    #: either one turns the whole last-session payload into a 500 (Codex on
    #: #830). Zero such rounds exist today; the column allows them.
    #:
    #: ⚠️ ONE MEASURED DIFFERENCE, ACCEPTED KNOWINGLY: a None KEY serialises as
    #: `"None"` through the model and as `"null"` through the bare
    #: jsonable_encoder. The state is unreachable today, and a cosmetic key
    #: spelling is a better outcome than a 500 — but it is a difference, so it
    #: is written down rather than left for someone to find.
    maps: list[str | None]
    map_counts: dict[str | None, int]
    matches: list[SessionMatchRow]
    scoring: ScoringAvailable | ScoringUnavailable
    warnings: list[str]
    teams: list[SessionTeam]
    unassigned_players: list[SessionPlayerRow]
    stats_checks: list[str]
    #: Null when the rounds carry no gaming session id.
    gaming_session_id: int | None


@router.get("/stats/last-session", response_model=LastSession)
async def get_last_session(db: DatabaseAdapter = Depends(get_db)):
    """Get the latest session data (similar to !last_session)"""
    config = load_config()
    db_path = config.sqlite_db_path if config.database_type == "sqlite" else None
    service = SessionDataService(db, db_path)
    scoring_service = StopwatchScoringService(db)

    latest_date = await service.get_latest_session_date()
    if not latest_date:
        raise HTTPException(status_code=404, detail="No sessions found")

    sessions, session_ids, session_ids_str, player_count = await service.fetch_session_data(latest_date)
    if not sessions:
        # Every round of the newest gaming session can be invalid (bot/test
        # rounds are quarantined with is_valid = FALSE) — that is "no last
        # session", not a server error.
        raise HTTPException(status_code=404, detail="No valid sessions found")
    stats_service = SessionStatsAggregator(db)

    gaming_session_id = None
    if session_ids:
        placeholders = ",".join("?" * len(session_ids))
        gaming_row = await db.fetch_one(
            f"""
            SELECT DISTINCT gaming_session_id
            FROM rounds
            WHERE id IN ({placeholders})
            LIMIT 1
            """,
            tuple(session_ids),
        )
        if gaming_row:
            gaming_session_id = gaming_row[0]

    # Calculate map counts
    map_counts = {}
    for _, map_name, _, _ in sessions:
        map_counts[map_name] = map_counts.get(map_name, 0) + 1

    # Since each map usually has 2 rounds, divide by 2 for
    # "matches" count, or just list unique maps
    unique_maps = list(map_counts.keys())

    # Get detailed matches for this session
    matches = await service.get_session_matches_by_round_ids(session_ids)

    scoring_payload, scoring_warnings, hardcoded_teams = await build_session_scoring(
        latest_date, session_ids, service, scoring_service
    )

    # Build team rosters with aggregated player stats for UI grouping
    teams_payload = []
    unassigned_players = []
    stats_checks = []
    if session_ids and session_ids_str:
        raw_dead_map = {}
        try:
            placeholders = ",".join("?" * len(session_ids))
            raw_rows = await db.fetch_all(
                f"""
                SELECT player_guid,
                       SUM(LEAST(COALESCE(time_dead_minutes, 0) * 60, time_played_seconds)) as raw_dead_seconds
                FROM player_comprehensive_stats
                WHERE round_id IN ({placeholders})
                GROUP BY player_guid
                """,
                tuple(session_ids),
            )
            raw_dead_map = {row[0]: int(row[1] or 0) for row in raw_rows if row and row[0]}
        except Exception:
            logger.warning(
                "Failed to fetch raw dead-time aggregates for session_ids=%s",
                session_ids,
                exc_info=True,
            )
            raw_dead_map = {}

        try:
            player_rows = await stats_service.aggregate_all_player_stats(session_ids, session_ids_str)
        except Exception:
            logger.error(
                "Failed to aggregate player stats for session_ids=%s — session will appear empty to the user",
                session_ids,
                exc_info=True,
            )
            player_rows = []

        guid_to_team = {}
        if hardcoded_teams:
            for team_name, team_data in hardcoded_teams.items():
                for guid in team_data.get("guids", []):
                    guid_to_team[guid] = team_name

        team_1_name = "Team A"
        team_2_name = "Team B"
        name_to_team = {}
        if hardcoded_teams and len(hardcoded_teams) >= 2:
            (
                team_1_name,
                team_2_name,
                _,
                _,
                name_to_team,
            ) = await service.build_team_mappings(session_ids, session_ids_str, hardcoded_teams)

        team_lookup = {
            team_1_name: [],
            team_2_name: [],
        }

        total_kills = 0
        total_deaths = 0

        for row in player_rows:
            (
                player_name,
                player_guid,
                kills,
                deaths,
                weighted_dpm,
                _total_hits,
                _total_shots,
                _total_headshots,
                headshot_kills,
                total_seconds,
                total_time_dead,
                total_denied,
                total_gibs,
                total_revives_given,
                total_times_revived,
                total_damage_received,
                total_damage_given,
                total_useful_kills,
                total_double_kills,
                total_triple_kills,
                total_quad_kills,
                total_multi_kills,
                total_mega_kills,
                total_self_kills,
                total_full_selfkills,
                *optional_tail,
            ) = row
            total_kill_assists = optional_tail[0] if optional_tail else 0

            total_kills += int(kills or 0)
            total_deaths += int(deaths or 0)

            kd = (kills / deaths) if deaths else float(kills or 0)
            team_name = name_to_team.get(player_name) or guid_to_team.get(player_guid)

            player_payload = {
                "name": player_name,
                "guid": player_guid,
                "kills": int(kills or 0),
                "deaths": int(deaths or 0),
                "kd": round(kd, 2),
                "dpm": int(weighted_dpm or 0),
                "headshot_kills": int(headshot_kills or 0),
                "time_played_seconds": int(total_seconds or 0),
                "time_dead_seconds": int(total_time_dead or 0),
                "time_dead_seconds_raw": int(raw_dead_map.get(player_guid, total_time_dead or 0)),
                "denied_playtime": int(total_denied or 0),
                "gibs": int(total_gibs or 0),
                "revives_given": int(total_revives_given or 0),
                "times_revived": int(total_times_revived or 0),
                "damage_given": int(total_damage_given or 0),
                "damage_received": int(total_damage_received or 0),
                "useful_kills": int(total_useful_kills or 0),
                "double_kills": int(total_double_kills or 0),
                "triple_kills": int(total_triple_kills or 0),
                "quad_kills": int(total_quad_kills or 0),
                "multi_kills": int(total_multi_kills or 0),
                "mega_kills": int(total_mega_kills or 0),
                "self_kills": int(total_self_kills or 0),
                "full_selfkills": int(total_full_selfkills or 0),
                "kill_assists": int(total_kill_assists or 0),
            }

            if team_name and team_name in team_lookup:
                team_lookup[team_name].append(player_payload)
            else:
                unassigned_players.append(player_payload)

        for team_name, players in team_lookup.items():
            players_sorted = sorted(players, key=lambda p: (-p["kills"], -p["dpm"]))
            teams_payload.append({"name": team_name, "players": players_sorted})

        if total_kills != total_deaths:
            stats_checks.append(f"Kill/death mismatch: {total_kills} kills vs {total_deaths} deaths")
        if unassigned_players:
            stats_checks.append(f"Unassigned players: {', '.join(p['name'] for p in unassigned_players)}")

    return {
        "date": latest_date,
        "player_count": player_count,
        "rounds": len(sessions),
        "maps": unique_maps,
        "map_counts": map_counts,
        "matches": matches,
        "scoring": scoring_payload,
        "warnings": scoring_warnings,
        "teams": teams_payload,
        "unassigned_players": unassigned_players,
        "stats_checks": stats_checks,
        "gaming_session_id": gaming_session_id,
    }


@router.get("/stats/session-leaderboard", response_model=list[SessionLeaderRow])
async def get_session_leaderboard(
    limit: int = 5,
    session_id: int | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """Get the leaderboard for a specific session (or latest if not specified)"""
    data_service = SessionDataService(db, None)
    stats_service = SessionStatsAggregator(db)

    if session_id is not None:
        # Fetch rounds for the specified gaming_session_id
        rounds = await db.fetch_all(
            """
            SELECT id FROM rounds
            WHERE gaming_session_id = $1
              AND round_number IN (1, 2)
              -- The same gates as every other session summary (Codex on
              -- #855, round two): an invalid or bot round can change the
              -- top-three ordering the aggregator computes from these ids.
              AND is_valid IS DISTINCT FROM FALSE
              AND is_bot_round IS DISTINCT FROM TRUE
              AND (round_status IN ('completed', 'substitution') OR round_status IS NULL)
            """,
            (session_id,),
        )
        if not rounds:
            return []
        session_ids = [r[0] for r in rounds]
        session_ids_str = ", ".join("?" * len(session_ids))
    else:
        latest_date = await data_service.get_latest_session_date()
        if not latest_date:
            return []
        sessions, session_ids, session_ids_str, _ = await data_service.fetch_session_data(latest_date)
        if not session_ids:
            return []

    leaderboard = await stats_service.get_dpm_leaderboard(session_ids, session_ids_str, limit)

    # Format for frontend
    result = []
    for i, (name, dpm, kills, deaths) in enumerate(leaderboard, 1):
        result.append({"rank": i, "name": name, "dpm": int(dpm), "kills": kills, "deaths": deaths})

    return result


@router.get("/stats/session-score/{date}")
async def get_session_score(date: str, db: DatabaseAdapter = Depends(get_db)):
    """
    Get stopwatch scoring payload for a specific session date.
    """
    config = load_config()
    db_path = config.sqlite_db_path if config.database_type == "sqlite" else None
    service = SessionDataService(db, db_path)
    scoring_service = StopwatchScoringService(db)

    sessions, session_ids, session_ids_str, player_count = await service.fetch_session_data_by_date(date)
    if not session_ids:
        raise HTTPException(status_code=404, detail="Session not found")

    scoring_payload, warnings, hardcoded_teams = await build_session_scoring(
        date, session_ids, service, scoring_service
    )

    teams_payload = []
    if hardcoded_teams and len(hardcoded_teams) >= 2:
        for team_name, team_data in hardcoded_teams.items():
            teams_payload.append(
                {
                    "name": team_name,
                    "guids": team_data.get("guids", []),
                    "names": team_data.get("names", []),
                }
            )
    elif session_ids and session_ids_str:
        try:
            (
                team_1_name,
                team_2_name,
                team_1_players,
                team_2_players,
                _,
            ) = await service.build_team_mappings(session_ids, session_ids_str, None)
            teams_payload = [
                {"name": team_1_name, "names": team_1_players, "guids": []},
                {"name": team_2_name, "names": team_2_players, "guids": []},
            ]
        except Exception:
            teams_payload = []

    return {
        "date": date,
        "player_count": player_count,
        "rounds": len(sessions or []),
        "scoring": scoring_payload,
        "warnings": warnings,
        "teams": teams_payload,
    }


@router.get("/stats/matches")
async def get_matches(limit: int = 5, db: DatabaseAdapter = Depends(get_db)):
    """Get recent matches"""
    data_service = SessionDataService(db, None)
    return await data_service.get_recent_matches(limit)


# ⛔ `limit` AND `offset` HAD NO BOUNDS, AND BOTH WERE LIVE 500s. Measured on
# dev before this change: `?limit=-5` -> 500, `?offset=-10` -> 500,
# `?limit=1000000` -> 200. The values went straight into the query, Postgres
# refused the negative ones, and the failure came back as a server fault — an
# input error reported as ours, which sends whoever reads it to the database
# instead of to the request. Same shape as `/api/predictions/recent`, and this
# one is on the endpoint the NEW SPA lists sessions from.
#
# ⭐ The ceiling is generous rather than tight, and the reason is measured:
# `SessionsList.tsx` opens with `limit=200` (PAGE) and raises it by 200 per
# "show older", so a ceiling near today's data would turn that button into a
# 422. Cost is not the constraint — limit=200, 500 and 1000 all return the
# same 54,526 bytes in ~3 ms, because the query runs out of sessions (137)
# long before it runs out of limit. 1000 removes the pathological request
# without putting a cliff anywhere a user can reach.
#
# ⚠️ It IS still a cliff, just a distant one: at 1000 sessions the page's
# growing limit hits the ceiling and answers 422. The durable fix is to page
# with `offset` instead of growing `limit` — named here so it is a decision
# rather than a surprise.
@router.get("/sessions", response_model=list[SessionSummary])
async def get_sessions_list(
    limit: int = Query(default=20, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    search: str = Query(default="", description="Filter by map name or player name."),
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Get list of all gaming sessions (like !sessions command).
    Returns sessions grouped by gaming_session_id to handle midnight-spanning sessions.
    """
    # Same filter, same escaping and the same two subqueries as
    # `/api/stats/sessions`: match on map name OR on a player who was there.
    # `escape_like_pattern` neutralises the LIKE wildcards so a search for
    # "100%" is a search and not a match-everything.
    search_filter = ""
    search_params: list = []
    if search.strip():
        safe_search = escape_like_pattern(search.strip())
        search_filter = """
            AND (
                sr.gaming_session_id IN (
                    SELECT r2.gaming_session_id FROM rounds r2
                    WHERE r2.gaming_session_id IS NOT NULL
                      AND r2.round_number IN (1, 2)
                      AND r2.is_valid IS DISTINCT FROM FALSE
                      AND r2.is_bot_round IS DISTINCT FROM TRUE
                      AND (r2.round_status IN ('completed', 'substitution')
                           OR r2.round_status IS NULL)
                      AND LOWER(r2.map_name) LIKE LOWER($3)
                )
                OR sr.gaming_session_id IN (
                    SELECT r3.gaming_session_id FROM rounds r3
                    INNER JOIN player_comprehensive_stats p2 ON p2.round_id = r3.id
                    WHERE r3.gaming_session_id IS NOT NULL
                      AND r3.round_number IN (1, 2)
                      AND r3.is_valid IS DISTINCT FROM FALSE
                      AND r3.is_bot_round IS DISTINCT FROM TRUE
                      AND (r3.round_status IN ('completed', 'substitution')
                           OR r3.round_status IS NULL)
                      AND LOWER(p2.player_name) LIKE LOWER($3)
                )
            )
        """
        search_params.append(f"%{safe_search}%")

    # ⚠️ The duration expression is interpolated, not concatenated by hand:
    # `round_duration_sql()` is a pure expression with no bind parameters
    # (that is its documented contract), so the placeholder style of the
    # adapter is irrelevant and nothing user-controlled reaches the SQL.
    # nosec B608 — the only interpolation is that fixed expression.
    query = f"""
        WITH session_rounds AS (
            SELECT
                r.gaming_session_id,
                MIN(SUBSTR(CAST(r.round_date AS TEXT), 1, 10)) as session_date,
                COUNT(r.id) as round_count,
                COUNT(DISTINCT r.map_name) as map_count,
                STRING_AGG(DISTINCT r.map_name, ', ' ORDER BY r.map_name) as maps_played,
                -- winner_team 1 = Axis, 2 = Allies (engine convention TEAM_AXIS=1;
                -- see lua TEAM_AXIS / parser). These aliases were previously inverted.
                COUNT(CASE WHEN r.round_number = 1 AND r.winner_team = 2 THEN 1 END) as allies_wins,
                COUNT(CASE WHEN r.round_number = 1 AND r.winner_team = 1 THEN 1 END) as axis_wins,
                COUNT(CASE WHEN r.round_number = 1 AND (r.winner_team NOT IN (1, 2) OR r.winner_team IS NULL) THEN 1 END) as draws,
                -- ⛔ THE DURATION COMES FROM THE CANONICAL EXPRESSION, not from
                -- lua_round_teams the way /stats/sessions builds it. That one
                -- sums lrt.actual_duration_seconds with NO fallback, and the
                -- webhook only covers part of the history: 877 of 2030 valid
                -- R1/R2 rounds have a Lua measurement, so 84 of 151 sessions
                -- come out with duration_seconds = 0 there — 56 % of them,
                -- reported as a number rather than as "not measured".
                -- round_duration_sql() falls back to the parsed actual_time
                -- and covers 2030 of 2030.
                SUM({round_duration_sql("r")}) as duration_seconds,
                -- Clock times of the first and last round, same derivation as
                -- /stats/sessions: order by date+time as text, then keep the
                -- time half.
                -- LPAD (Codex on #848): round_time is TEXT and MIN/MAX order the
                -- concatenation lexically, so an unpadded pre-10:00 value like
                -- '4918' would sort after '063000' and also fail the HH:MM
                -- formatter's len>=6 check downstream. Measured today: every
                -- round_time is exactly 6 chars, so this is a latent-shape guard,
                -- not a behaviour change.
                SUBSTRING(MIN(CAST(r.round_date AS TEXT) || LPAD(r.round_time, 6, '0')) FROM 11) as first_time,
                SUBSTRING(MAX(CAST(r.round_date AS TEXT) || LPAD(r.round_time, 6, '0')) FROM 11) as last_time
            FROM rounds r
            WHERE r.gaming_session_id IS NOT NULL
              AND r.round_number IN (1, 2)
              AND r.is_valid IS DISTINCT FROM FALSE
              AND r.is_bot_round IS DISTINCT FROM TRUE
              AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
            GROUP BY r.gaming_session_id
        ),
        session_players AS (
            SELECT
                r.gaming_session_id,
                COUNT(DISTINCT p.player_guid) as player_count,
                COALESCE(SUM(p.kills), 0) as total_kills,
                COALESCE(SUM(p.deaths), 0) as total_deaths,
                -- ARRAY_AGG, not STRING_AGG+split (Codex on #848): a player name
                -- containing ', ' would be split into two phantom names on the way
                -- out. 0 such names today — but names are user-controlled input,
                -- so the type follows what a name CAN be, not what the sample has.
                ARRAY_AGG(DISTINCT p.player_name ORDER BY p.player_name) as player_names
            FROM rounds r
            INNER JOIN player_comprehensive_stats p
                ON p.round_id = r.id
            WHERE r.gaming_session_id IS NOT NULL
              AND r.round_number IN (1, 2)
              AND r.is_valid IS DISTINCT FROM FALSE
              AND r.is_bot_round IS DISTINCT FROM TRUE
              -- Bot identity is a UNION of both forms on the ROW, not only
              -- the round flag: round_contract.py documents older imports
              -- that left bot rounds valid. Measured today: 0 rows escape —
              -- latent, which is the reason to close it (sister's handover
              -- on #848's thread, 1. 9.).
              AND p.player_guid NOT LIKE 'OMNIBOT%'
              AND COALESCE(p.player_name, '') NOT LIKE '[BOT]%'
              AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
            GROUP BY r.gaming_session_id
        ),
        -- BOX team score per session (see the /stats/sessions comment: the
        -- side tallies above are NOT a team score in stopwatch).
        session_box AS (
            SELECT DISTINCT ON (gaming_session_id)
                gaming_session_id,
                team_1_name,
                team_2_name,
                team_1_score,
                team_2_score,
                winning_team
            FROM session_results
            WHERE gaming_session_id IS NOT NULL
              AND map_name = 'ALL'
            ORDER BY gaming_session_id, id DESC
        )
        SELECT
            sr.session_date,
            sr.gaming_session_id,
            sr.round_count,
            sr.map_count,
            COALESCE(sp.player_count, 0) as player_count,
            COALESCE(sp.total_kills, 0) as total_kills,
            sr.maps_played,
            sr.allies_wins,
            sr.axis_wins,
            sr.draws,
            sb.team_1_name,
            sb.team_2_name,
            sb.team_1_score,
            sb.team_2_score,
            sb.winning_team,
            -- ⚠️ APPENDED, never inserted. The row is unpacked BY POSITION
            -- below (`row[10]`..`row[14]` are the BOX team fields), so a
            -- column added in the middle silently renames five existing
            -- ones. New columns go on the end.
            COALESCE(sp.total_deaths, 0) as total_deaths,
            COALESCE(sr.duration_seconds, 0) as duration_seconds,
            COALESCE(sp.player_names, ARRAY[]::text[]) as player_names,
            sr.first_time,
            sr.last_time
        FROM session_rounds sr
        LEFT JOIN session_players sp ON sr.gaming_session_id = sp.gaming_session_id
        LEFT JOIN session_box sb ON sr.gaming_session_id = sb.gaming_session_id
        WHERE 1 = 1{search_filter}
        ORDER BY sr.session_date DESC, sr.gaming_session_id DESC
        LIMIT $1 OFFSET $2
    """

    try:
        rows = await db.fetch_all(query, (limit, offset, *search_params))
    except Exception as e:
        logger.error(f"Error fetching sessions list: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    sessions = []
    for row in rows:
        round_date = row[0]
        # Format time_ago
        if isinstance(round_date, str):
            round_date = round_date[:10]
            dt = datetime.strptime(round_date, "%Y-%m-%d")  # noqa: DTZ007 date-only parsing, no time component used
        else:
            dt = datetime.combine(round_date, datetime.min.time())

        now = datetime.now()  # noqa: DTZ005 naive datetime for date-string arithmetic / SQL date filter / log timestamp display
        diff = now - dt
        days = diff.days

        if days == 0:
            time_ago = "Today"
        elif days == 1:
            time_ago = "Yesterday"
        elif days < 7:
            time_ago = f"{days} days ago"
        elif days < 30:
            weeks = days // 7
            time_ago = f"{weeks} week{'s' if weeks > 1 else ''} ago"
        else:
            time_ago = dt.strftime("%b %d, %Y")

        sessions.append(
            {
                "date": str(round_date),
                "session_id": row[1],
                "rounds": row[2],
                "maps": row[3],
                "players": row[4],
                "total_kills": row[5],
                "maps_played": row[6].split(", ") if row[6] else [],
                "allies_wins": row[7],
                "axis_wins": row[8],
                "draws": row[9],
                # BOX team score; None when the session has no team attribution.
                "team_1_name": row[10],
                "team_2_name": row[11],
                "team_1_score": row[12],
                "team_2_score": row[13],
                "winning_team": row[14],
                # The five the sibling `/api/stats/sessions` had and this one
                # did not. Same names, same shapes — `player_names` a list and
                # the clock times "HH:MM" strings — so the two endpoints speak
                # one vocabulary rather than two.
                "total_deaths": row[15],
                "duration_seconds": row[16],
                "player_names": list(row[17] or []),
                "start_time": (
                    f"{str(row[18]).replace(':', '')[:2]}:{str(row[18]).replace(':', '')[2:4]}"
                    if row[18] and len(str(row[18]).replace(":", "")) >= 6
                    else ""
                ),
                "end_time": (
                    f"{str(row[19]).replace(':', '')[:2]}:{str(row[19]).replace(':', '')[2:4]}"
                    if row[19] and len(str(row[19]).replace(":", "")) >= 6
                    else ""
                ),
                "time_ago": time_ago,
                "formatted_date": dt.strftime("%A, %B %d, %Y"),
            }
        )

    return sessions


@router.get("/sessions/{date}")
async def get_session_details(date: str, db: DatabaseAdapter = Depends(get_db)):
    """
    Get detailed info for a specific session by date.
    Returns matches/rounds within the session and top players.
    """
    data_service = SessionDataService(db, None)
    stats_service = SessionStatsAggregator(db)

    # Get session data (supports multiple sessions on the same date)
    sessions, session_ids, session_ids_str, player_count = await data_service.fetch_session_data_by_date(date)

    if not sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get matches for this session
    matches = await data_service.get_session_matches_by_round_ids(session_ids)

    # Get leaderboard (top players by DPM)
    leaderboard = []
    if session_ids:
        try:
            lb_data = await stats_service.get_dpm_leaderboard(session_ids, session_ids_str, 10)
            for i, (name, dpm, kills, deaths) in enumerate(lb_data, 1):
                kd = kills / deaths if deaths > 0 else kills
                leaderboard.append(
                    {
                        "rank": i,
                        "name": name,
                        "dpm": int(dpm),
                        "kills": kills,
                        "deaths": deaths,
                        "kd": round(kd, 2),
                    }
                )
        except Exception as e:
            logger.error(f"Error fetching session leaderboard: {e}")

    # Scoring + team rosters
    scoring_service = StopwatchScoringService(db)
    scoring_payload, warnings, hardcoded_teams = await build_session_scoring(
        date, session_ids, data_service, scoring_service
    )

    teams_payload = []
    if hardcoded_teams and len(hardcoded_teams) >= 2:
        for team_name, team_data in hardcoded_teams.items():
            teams_payload.append(
                {
                    "name": team_name,
                    "guids": team_data.get("guids", []),
                    "names": team_data.get("names", []),
                }
            )
    elif session_ids and session_ids_str:
        try:
            (
                team_1_name,
                team_2_name,
                team_1_players,
                team_2_players,
                _,
            ) = await data_service.build_team_mappings(session_ids, session_ids_str, None)
            teams_payload = [
                {"name": team_1_name, "names": team_1_players, "guids": []},
                {"name": team_2_name, "names": team_2_players, "guids": []},
            ]
        except Exception:
            teams_payload = []

    # Calculate map summary
    map_counts = {}
    for _, map_name, _, _ in sessions:
        map_counts[map_name] = map_counts.get(map_name, 0) + 1

    # Group matches by map (R1 + R2 = 1 map match)
    map_matches = {}
    for match in matches:
        map_name = match["map_name"]
        if map_name not in map_matches:
            map_matches[map_name] = {"rounds": [], "map_name": map_name}
        map_matches[map_name]["rounds"].append(match)

    # A date can hold more than one gaming session, and this endpoint merges
    # them on purpose so a session that crosses midnight is never shown cut in
    # half (fetch_session_data_by_date's docstring). Until now the payload gave
    # no way to tell that had happened, so session-detail.js rendered two
    # separate evenings as one "session detail" and could never resolve a
    # gaming_session_id from the date path at all.
    gaming_session_ids = await data_service.get_gaming_session_ids_for_date(date)

    # gaming_session_id is ALWAYS present, and null when the date holds more
    # than one session — deliberately, so the payload has one shape rather than
    # two. A conditionally absent key is the version that breaks clients, since
    # `resp.gaming_session_id` and `'gaming_session_id' in resp` then disagree.
    # Every caller in this repo tests truthiness, not presence (Copilot on #605).
    return {
        "date": date,
        "gaming_session_ids": gaming_session_ids,
        "gaming_session_id": gaming_session_ids[0] if len(gaming_session_ids) == 1 else None,
        "player_count": player_count,
        "total_rounds": len(sessions),
        "maps_played": list(map_counts.keys()),
        "map_counts": map_counts,
        "matches": list(map_matches.values()),
        "leaderboard": leaderboard,
        "scoring": scoring_payload,
        "warnings": warnings,
        "teams": teams_payload,
    }


@router.get("/sessions/{date}/graphs")
async def get_session_graph_stats(
    date: str,
    gaming_session_id: int | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Get aggregated session stats formatted for graph rendering.
    Returns data for:
    - Combat Stats (Offense): kills, deaths, damage, K/D, DPM
    - Combat Stats (Defense/Support): revives, gibs, headshots, time alive/dead
    - Advanced Metrics: FragPotential, Damage Efficiency, Time Denied, Survival Rate
    - Playstyle Analysis: Classification based on stats patterns
    - DPM Timeline: Per-round DPM values for each player
    """
    # Get all player stats for this session date
    # Use DISTINCT to avoid duplicates from the rounds join
    if gaming_session_id is not None:
        where_clause = "r.gaming_session_id = $1"
        params = (gaming_session_id,)
    else:
        # round_date is stored as a 10-char 'YYYY-MM-DD' string, so the old
        # SUBSTRING(...,1,10) wrapper was a no-op that also made the predicate
        # non-sargable. Plain equality is equivalent and sargable.
        where_clause = "p.round_date = $1"
        params = (date,)

    query = f"""
        SELECT DISTINCT
            p.player_guid,
            p.player_name,
            p.round_number,
            p.kills,
            p.deaths,
            p.damage_given,
            p.damage_received,
            p.time_played_seconds,
            p.revives_given,
            p.kill_assists,
            p.gibs,
            p.headshots,
            p.accuracy,
            p.team_kills,
            p.self_kills,
            p.times_revived,
            p.time_dead_minutes,
            p.denied_playtime,
            p.most_useful_kills,
            COALESCE(p.full_selfkills, 0),
            p.map_name,
            r.id as round_id,
            p.constructions,
            p.objectives_stolen,
            p.dynamites_planted,
            p.dynamites_defused,
            p.useless_kills,
            p.double_kills,
            p.triple_kills,
            p.quad_kills,
            p.mega_kills,
            p.bullets_fired,
            p.time_played_percent
        FROM player_comprehensive_stats p
        JOIN rounds r ON p.round_id = r.id
        WHERE {where_clause}
          AND r.round_number IN (1, 2)
          AND (r.round_status IN ('completed', 'cancelled', 'substitution') OR r.round_status IS NULL)
        ORDER BY p.player_name, r.id
    """

    try:
        rows = await db.fetch_all(query, params)
    except Exception as e:
        logger.error(f"Error fetching session graph stats: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    if not rows:
        raise HTTPException(status_code=404, detail="No stats found for this session")

    # Aggregate stats per player
    player_stats = {}
    dpm_timeline = {}  # player -> list of (map_round, dpm)

    for row in rows:
        guid = row[0]
        name = row[1]
        round_num = row[2]
        kills = row[3] or 0
        deaths = row[4] or 0
        damage_given = row[5] or 0
        damage_received = row[6] or 0
        time_played = row[7] or 0
        revives = row[8] or 0
        kill_assists = row[9] or 0
        gibs = row[10] or 0
        headshots = row[11] or 0
        accuracy = row[12] or 0
        team_kills = row[13] or 0
        self_kills = row[14] or 0
        times_revived = row[15] or 0
        time_dead_minutes = row[16] or 0
        denied_playtime = row[17] or 0
        useful_kills = row[18] or 0
        full_selfkills = row[19] or 0
        map_name = row[20]
        round_id = row[21]  # unique identifier for deduplication
        constructions = row[22] or 0
        objectives_stolen = row[23] or 0
        dynamites_planted = row[24] or 0
        dynamites_defused = row[25] or 0
        useless_kills = row[26] or 0
        double_kills = row[27] or 0
        triple_kills = row[28] or 0
        quad_kills = row[29] or 0
        mega_kills = row[30] or 0
        # row[31] = bullets_fired (reserved for accuracy calc)
        time_played_percent = float(row[32]) if row[32] else 0.0

        # Aggregate by player_guid (not player_name) to handle name changes mid-session
        agg_key = guid or name
        if agg_key not in player_stats:
            player_stats[agg_key] = {
                "player_guid": guid,
                "kills": 0,
                "deaths": 0,
                "damage_given": 0,
                "damage_received": 0,
                "time_played": 0,
                "revives": 0,
                "kill_assists": 0,
                "gibs": 0,
                "headshots": 0,
                "accuracy_sum": 0,
                "accuracy_count": 0,
                "tpp_weighted_sum": 0,
                "tpp_weight": 0,
                "team_kills": 0,
                "self_kills": 0,
                "times_revived": 0,
                "time_dead_minutes": 0,
                "denied_playtime": 0,
                "useful_kills": 0,
                "full_selfkills": 0,
                "rounds_played": 0,
                "seen_rounds": set(),  # Track unique round_ids
                "constructions": 0,
                "objectives_stolen": 0,
                "dynamites_planted": 0,
                "dynamites_defused": 0,
                "useless_kills": 0,
                "double_kills": 0,
                "triple_kills": 0,
                "quad_kills": 0,
                "mega_kills": 0,
            }
            dpm_timeline[agg_key] = []

        # Update display name to latest seen
        player_stats[agg_key]["display_name"] = name

        # Skip if we've already processed this round for this player
        if round_id in player_stats[agg_key]["seen_rounds"]:
            continue
        player_stats[agg_key]["seen_rounds"].add(round_id)

        ps = player_stats[agg_key]
        ps["kills"] += kills
        ps["deaths"] += deaths
        ps["damage_given"] += damage_given
        ps["damage_received"] += damage_received
        ps["time_played"] += time_played
        ps["revives"] += revives
        ps["kill_assists"] += kill_assists
        ps["gibs"] += gibs
        ps["headshots"] += headshots
        ps["accuracy_sum"] += accuracy
        ps["accuracy_count"] += 1
        if time_played_percent > 0:
            ps["tpp_weighted_sum"] += time_played_percent * time_played
            ps["tpp_weight"] += time_played
        ps["team_kills"] += team_kills
        ps["self_kills"] += self_kills
        ps["times_revived"] += times_revived
        # RCA-1: cap dead PER ROUND (time_played is seconds) before summing, so one
        # inflated Lua dead-time round can't consume the whole session's played time
        ps["time_dead_minutes"] += min(time_dead_minutes, time_played / 60.0)
        ps["denied_playtime"] += denied_playtime
        ps["useful_kills"] += useful_kills
        ps["full_selfkills"] += full_selfkills
        ps["constructions"] += constructions
        ps["objectives_stolen"] += objectives_stolen
        ps["dynamites_planted"] += dynamites_planted
        ps["dynamites_defused"] += dynamites_defused
        ps["useless_kills"] += useless_kills
        ps["double_kills"] += double_kills
        ps["triple_kills"] += triple_kills
        ps["quad_kills"] += quad_kills
        ps["mega_kills"] += mega_kills
        ps["rounds_played"] += 1

        # DPM for this round
        round_dpm = (damage_given / (time_played / 60)) if time_played > 0 else 0
        # Use shorter map name format for timeline
        short_map = map_name.split("_")[-1][:8] if "_" in map_name else map_name[:8]
        dpm_timeline[agg_key].append({"label": f"{short_map} R{round_num}", "dpm": round(round_dpm, 1)})

    # Calculate derived metrics and build response
    players_data = []
    for agg_key, stats in player_stats.items():
        name = stats.get("display_name", agg_key)
        time_minutes = stats["time_played"] / 60 if stats["time_played"] > 0 else 1

        # Basic ratios
        kd = stats["kills"] / stats["deaths"] if stats["deaths"] > 0 else stats["kills"]
        dpm = stats["damage_given"] / time_minutes

        # Damage Efficiency: ratio of damage given to received (>1 is good)
        damage_efficiency = stats["damage_given"] / max(1, stats["damage_received"])

        # Survival Rate: prefer engine alive% (TAB[8]), fallback to computed
        tpp_wsum = stats.get("tpp_weighted_sum", 0)
        tpp_w = stats.get("tpp_weight", 0)
        survival_rate_engine = round(tpp_wsum / tpp_w, 1) if tpp_w > 0 else None
        time_dead_min = stats.get("time_dead_minutes", 0)
        time_played_min = max(0.01, time_minutes)
        # RCA-1: cap dead at played (buggy Lua time can exceed it) + clamp 0..100
        survival_rate_computed = max(
            0.0, min(100.0, 100 - (min(time_dead_min, time_played_min) / time_played_min * 100))
        )
        survival_rate = survival_rate_engine if survival_rate_engine is not None else survival_rate_computed

        # Time Denied (use Lua denied_playtime when available; normalize per minute)
        time_denied_raw = stats.get("denied_playtime", 0)
        time_denied = (time_denied_raw / time_minutes) if time_minutes > 0 else 0
        time_dead_raw_seconds = stats.get("time_dead_minutes", 0) * 60

        # Simple average accuracy per round
        avg_accuracy = stats["accuracy_sum"] / stats["accuracy_count"] if stats["accuracy_count"] > 0 else 0

        # Playstyle classification (8 categories like Discord bot)
        playstyle = classify_playstyle(stats, dpm, kd, avg_accuracy, survival_rate)
        rounds_played = max(1, stats["rounds_played"])

        players_data.append(
            {
                "name": name,
                "guid": stats.get("player_guid", ""),
                "combat_offense": {
                    "kills": stats["kills"],
                    "deaths": stats["deaths"],
                    "damage_given": stats["damage_given"],
                    "kd": round(kd, 2),
                    "dpm": round(dpm, 1),
                },
                "combat_defense": {
                    "revives": stats["revives"],
                    "kill_assists": stats["kill_assists"],
                    "gibs": stats["gibs"],
                    "headshots": stats["headshots"],
                    "useful_kills": stats["useful_kills"],
                    "full_selfkills": stats["full_selfkills"],
                    "times_revived": stats["times_revived"],
                    "team_kills": stats["team_kills"],
                    "self_kills": stats["self_kills"],
                },
                "advanced_metrics": {
                    "frag_potential": round(
                        (stats["damage_given"] / max(1, stats["time_played"] - stats.get("time_dead_minutes", 0) * 60))
                        * 60,
                        1,
                    ),
                    "damage_efficiency": round(damage_efficiency, 1),
                    "survival_rate": round(survival_rate, 1),
                    "time_denied": round(time_denied, 1),
                    "time_denied_raw_seconds": int(time_denied_raw or 0),
                    "time_dead_raw_seconds": int(time_dead_raw_seconds or 0),
                    "useful_kills_per_round": round(stats["useful_kills"] / rounds_played, 2),
                    "deaths_per_round": round(stats["deaths"] / rounds_played, 2),
                    "rounds_played": rounds_played,
                },
                "playstyle": playstyle,
                "dpm_timeline": dpm_timeline.get(agg_key, []),
            }
        )

    _apply_session_aggression_model(players_data)

    # Sort by DPM for consistent ordering
    players_data.sort(key=lambda x: x["combat_offense"]["dpm"], reverse=True)

    return {"date": date, "player_count": len(players_data), "players": players_data}


def _clamp_percentage(value: float | None) -> float | None:
    if value is None:
        return None
    return round(max(0.0, min(100.0, float(value))), 1)


def _score_relative_metric(value: Any, values: list[Any], invert: bool = False, neutral: float = 50.0) -> float:
    """Score a value relative to a set using percentile rank.

    Percentile rank is outlier-resistant: one extreme value cannot
    compress all others toward 50. Each player's score reflects how
    many session-mates they beat, not their distance from min/max.
    """
    numeric_values: list[float] = []
    for item in values:
        try:
            number = float(item)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            numeric_values.append(number)

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return neutral

    if not math.isfinite(numeric_value) or not numeric_values:
        return neutral

    n = len(numeric_values)
    if n <= 1:
        return neutral

    count_below = sum(1 for v in numeric_values if v < numeric_value)
    scaled = (count_below / (n - 1)) * 100.0
    if invert:
        scaled = 100.0 - scaled
    return _clamp_percentage(scaled) or neutral


def _apply_session_aggression_model(players_data: list[dict[str, Any]]) -> None:
    if not players_data:
        return

    frag_values = []
    denied_values = []
    useful_values = []
    death_values = []
    dead_share_values = []
    efficiency_values = []
    survival_values = []

    for player in players_data:
        adv = player.get("advanced_metrics") or {}
        frag_values.append(float(adv.get("frag_potential") or 0.0))
        denied_values.append(float(adv.get("time_denied") or 0.0))
        useful_values.append(float(adv.get("useful_kills_per_round") or 0.0))
        death_values.append(float(adv.get("deaths_per_round") or 0.0))
        survival_rate = float(adv.get("survival_rate") or 0.0)
        dead_share_values.append(max(0.0, 100.0 - survival_rate))
        efficiency_values.append(float(adv.get("damage_efficiency") or 0.0))
        survival_values.append(survival_rate)

    for player in players_data:
        adv = player.get("advanced_metrics") or {}
        playstyle = player.setdefault("playstyle", {})

        survival_rate = float(adv.get("survival_rate") or 0.0)
        dead_time_share = max(0.0, 100.0 - survival_rate)

        frag_score = _score_relative_metric(adv.get("frag_potential"), frag_values, neutral=50.0)
        denied_score = _score_relative_metric(adv.get("time_denied"), denied_values, neutral=50.0)
        useful_score = _score_relative_metric(adv.get("useful_kills_per_round"), useful_values, neutral=50.0)
        death_score = _score_relative_metric(adv.get("deaths_per_round"), death_values, neutral=50.0)
        dead_share_score = _score_relative_metric(dead_time_share, dead_share_values, neutral=50.0)
        efficiency_score = _score_relative_metric(adv.get("damage_efficiency"), efficiency_values, neutral=50.0)
        survival_score = _score_relative_metric(survival_rate, survival_values, neutral=50.0)

        pressure_score = (frag_score * 0.50) + (denied_score * 0.25) + (useful_score * 0.25)
        risk_load = (death_score * 0.60) + (dead_share_score * 0.40)
        productivity = (pressure_score * 0.65) + (efficiency_score * 0.35)
        empty_death_burden = max(0.0, risk_load - productivity)

        aggression_score = (
            _clamp_percentage((pressure_score * 0.80) + (risk_load * 0.20) - (empty_death_burden * 0.50)) or 0.0
        )
        discipline_score = (
            _clamp_percentage(
                (survival_score * 0.45) + (efficiency_score * 0.35) + ((100.0 - empty_death_burden) * 0.20)
            )
            or 0.0
        )

        playstyle["aggression"] = aggression_score
        adv["aggression_score"] = aggression_score
        adv["pressure_score"] = round(pressure_score, 1)
        adv["risk_load"] = round(risk_load, 1)
        adv["empty_death_burden"] = round(empty_death_burden, 1)
        adv["discipline_score"] = discipline_score
        adv["dead_time_share"] = round(dead_time_share, 1)


def classify_playstyle(
    stats: dict,
    dpm: float,
    kd: float,
    accuracy: float,
    survival_rate: float,
) -> dict:
    """
    Classify player playstyle into 8 categories (0-100 scale).
    Based on Discord bot's SessionGraphGenerator logic.
    """
    rounds = stats["rounds_played"] or 1

    # Normalize stats per round for fair comparison
    revives_pr = stats["revives"] / rounds
    assists_pr = stats.get("kill_assists", 0) / rounds
    constructions_pr = stats.get("constructions", 0) / rounds
    obj_actions_pr = (
        stats.get("objectives_stolen", 0) + stats.get("dynamites_planted", 0) + stats.get("dynamites_defused", 0)
    ) / rounds

    # Calculate each playstyle dimension (0-100)
    precision = min(100, accuracy * 2)
    survivability = min(100, max(0, survival_rate))
    # ET:Legacy support = medic (revives) + teamwork (assists) +
    # engineer/fieldops (constructions, objectives, dynamites).
    # Weighted: revives 40%, assists 30%, constructions+objectives 30%
    support = min(
        100,
        (
            min(100, revives_pr * 20) * 0.40  # medic: caps at 5 rev/round
            + min(100, assists_pr * 15) * 0.30  # teamwork: caps at 6.7 assists/round
            + min(100, (constructions_pr + obj_actions_pr) * 30) * 0.30  # engi/obj: caps at 3.3/round
        ),
    )
    lethality = min(100, kd * 30)

    # Brutality = smart elimination power (industry-first composite):
    # - denied_playtime: man-advantage time created (hockey power-play model)
    # - gib_efficiency: finish rate, kills you complete (Apex "thirst" model)
    # - useful_kill_ratio: impactful kills (HLTV Round Swing model)
    # - multi_kill_bonus: domination moments (Quake "Excellent" model)
    # - useless_kill_penalty: wasted frags (PandaSkill "Worthless Death" model)
    denied_pr = stats["denied_playtime"] / rounds  # seconds of man-advantage per round
    total_kills = max(1, stats["kills"])
    gib_eff = (stats["gibs"] / total_kills) * 100  # % of kills finished
    useful = stats["useful_kills"]
    useless = stats.get("useless_kills", 0)
    useful_ratio = (useful / max(1, useful + useless)) * 100 if (useful + useless) > 0 else 50
    multi_raw = (
        stats.get("double_kills", 0)
        + stats.get("triple_kills", 0) * 2
        + stats.get("quad_kills", 0) * 3
        + stats.get("mega_kills", 0) * 4
    ) / rounds
    useless_ratio = (useless / total_kills) * 100

    brutality = min(
        100,
        max(
            0,
            (
                min(100, denied_pr * 2.5) * 0.35  # ~40s denied/round = 100 (one full spawn wave)
                + min(100, gib_eff) * 0.25  # 100% gib rate = 100
                + min(100, useful_ratio) * 0.20  # useful kill ratio
                + min(100, multi_raw * 25) * 0.10  # ~4 multi events/round = 100
                - min(100, useless_ratio) * 0.10  # penalty for wasted frags
            ),
        ),
    )

    efficiency = min(100, (stats["damage_given"] / max(1, stats["damage_received"])) * 25)

    # Consistency = well-roundedness across dimensions.
    # Low deviation across axes → high consistency. Replaces the old
    # `rounds * 10` formula which capped at 10 rounds and was always
    # 100 in any BO6+ session.
    dims = [precision, survivability, support, lethality, brutality, efficiency]
    dim_mean = sum(dims) / len(dims)
    dim_dev = (sum((d - dim_mean) ** 2 for d in dims) / len(dims)) ** 0.5
    consistency = min(100, max(0, 100 - dim_dev * 2))

    return {
        # Aggression is session-normalized later using productive pressure
        # signals. Keep the base classifier neutral on its own.
        "aggression": 50.0,
        "precision": precision,
        "survivability": survivability,
        "support": support,
        "lethality": lethality,
        "brutality": brutality,
        "consistency": consistency,
        "efficiency": efficiency,
    }


# ========================================
# GEMINI SESSIONS API (P0 Redesign)
# ========================================


@router.get("/stats/sessions")
async def get_stats_sessions(
    limit: int = Query(default=20, le=100, ge=1),
    offset: int = Query(default=0, ge=0),
    search: str = "",
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Get list of gaming sessions for the Gemini frontend.
    Supports search by map name or player name.
    Returns richer data than /sessions endpoint: timing, scores, duration.
    """
    search_filter = ""
    search_params: list = []
    param_idx = 1  # PostgreSQL $1, $2, ...

    if search.strip():
        safe_search = escape_like_pattern(search.strip())
        search_filter = f"""
            AND (
                sr.gaming_session_id IN (
                    SELECT r2.gaming_session_id FROM rounds r2
                    WHERE r2.gaming_session_id IS NOT NULL
                      AND r2.round_number IN (1, 2)
                      AND r2.is_valid IS DISTINCT FROM FALSE
                      AND r2.is_bot_round IS DISTINCT FROM TRUE
                      AND (r2.round_status IN ('completed', 'substitution') OR r2.round_status IS NULL)
                      AND LOWER(r2.map_name) LIKE LOWER(${param_idx})
                )
                OR sr.gaming_session_id IN (
                    SELECT r3.gaming_session_id FROM rounds r3
                    INNER JOIN player_comprehensive_stats p2 ON p2.round_id = r3.id
                    WHERE r3.gaming_session_id IS NOT NULL
                      AND r3.round_number IN (1, 2)
                      AND r3.is_valid IS DISTINCT FROM FALSE
                      AND r3.is_bot_round IS DISTINCT FROM TRUE
                      AND (r3.round_status IN ('completed', 'substitution') OR r3.round_status IS NULL)
                      AND LOWER(p2.player_name) LIKE LOWER(${param_idx})
                )
            )
        """
        search_params.append(f"%{safe_search}%")
        param_idx += 1

    limit_param = f"${param_idx}"
    offset_param = f"${param_idx + 1}"

    query = f"""
        WITH session_rounds AS (
            SELECT
                r.gaming_session_id,
                MIN(r.round_date) as first_date,
                MAX(r.round_date) as last_date,
                -- Take the time of the chronologically first/last ROUND, not
                -- the global MIN/MAX of the time-of-day column. A session
                -- crossing midnight (21:56 → 00:23) otherwise renders as
                -- "00:23 — 23:57". round_date::text (YYYY-MM-DD, 10 chars) ||
                -- round_time sorts chronologically; the time is chars 11+.
                SUBSTRING(MIN(r.round_date::text || LPAD(r.round_time, 6, '0')) FROM 11) as first_time,
                SUBSTRING(MAX(r.round_date::text || LPAD(r.round_time, 6, '0')) FROM 11) as last_time,
                COUNT(r.id) as round_count,
                STRING_AGG(DISTINCT r.map_name, ', ' ORDER BY r.map_name) as maps_played,
                -- winner_team 1 = Axis, 2 = Allies (TEAM_AXIS=1). Aliases were inverted.
                COUNT(CASE WHEN r.round_number = 1 AND r.winner_team = 2 THEN 1 END) as allies_wins,
                COUNT(CASE WHEN r.round_number = 1 AND r.winner_team = 1 THEN 1 END) as axis_wins
            FROM rounds r
            WHERE r.gaming_session_id IS NOT NULL
              AND r.round_number IN (1, 2)
              AND r.is_valid IS DISTINCT FROM FALSE
              AND r.is_bot_round IS DISTINCT FROM TRUE
              AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
            GROUP BY r.gaming_session_id
        ),
        session_players AS (
            SELECT
                r.gaming_session_id,
                COUNT(DISTINCT p.player_guid) as player_count,
                COALESCE(SUM(p.kills), 0) as total_kills,
                COALESCE(SUM(p.deaths), 0) as total_deaths
            FROM rounds r
            INNER JOIN player_comprehensive_stats p ON p.round_id = r.id
            WHERE r.gaming_session_id IS NOT NULL
              AND r.round_number IN (1, 2)
              AND r.is_valid IS DISTINCT FROM FALSE
              AND r.is_bot_round IS DISTINCT FROM TRUE
              -- Bot identity is a UNION of both forms on the ROW, not only
              -- the round flag: round_contract.py documents older imports
              -- that left bot rounds valid. Measured today: 0 rows escape —
              -- latent, which is the reason to close it (sister's handover
              -- on #848's thread, 1. 9.).
              AND p.player_guid NOT LIKE 'OMNIBOT%'
              AND COALESCE(p.player_name, '') NOT LIKE '[BOT]%'
              AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
            GROUP BY r.gaming_session_id
        ),
        session_duration AS (
            -- ⛔ THIS USED TO SUM lua_round_teams.actual_duration_seconds AND
            -- REPORT A PARTIAL SUM AS A TOTAL. The Lua webhook covers part of
            -- the history — 877 of 2030 valid R1/R2 rounds — and a LEFT JOIN
            -- contributes nothing for the rest, so a session with 16 rounds of
            -- which 10 were measured returned the length of those 10. Measured
            -- on dev: session 88 answered 5209 s against an actual 7260 s, and
            -- 46 of 100 sessions answered 0 seconds outright. Zero is not
            -- "unmeasured" on the wire, it is a duration, and the legacy
            -- session card renders it as one.
            --
            -- round_duration_sql() is the project's canonical expression
            -- (CLAUDE.md: take round duration from shared/round_time.py): the
            -- Lua measurement where it exists, the parsed actual_time where it
            -- does not. It covers 2030 of 2030.
            SELECT
                r.gaming_session_id,
                COALESCE(SUM({round_duration_sql("r")}), 0) as total_duration_seconds
            FROM rounds r
            WHERE r.gaming_session_id IS NOT NULL
              AND r.round_number IN (1, 2)
              AND r.is_valid IS DISTINCT FROM FALSE
              AND r.is_bot_round IS DISTINCT FROM TRUE
              AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
            GROUP BY r.gaming_session_id
        ),
        session_names AS (
            SELECT
                r.gaming_session_id,
                -- ARRAY_AGG, not STRING_AGG+split (Codex on #848): a player name
                -- containing ', ' would be split into two phantom names on the way
                -- out. 0 such names today — but names are user-controlled input,
                -- so the type follows what a name CAN be, not what the sample has.
                ARRAY_AGG(DISTINCT p.player_name ORDER BY p.player_name) as player_names
            FROM rounds r
            INNER JOIN player_comprehensive_stats p ON p.round_id = r.id
            WHERE r.gaming_session_id IS NOT NULL
              AND r.round_number IN (1, 2)
              AND r.is_valid IS DISTINCT FROM FALSE
              AND r.is_bot_round IS DISTINCT FROM TRUE
              -- Bot identity is a UNION of both forms on the ROW, not only
              -- the round flag: round_contract.py documents older imports
              -- that left bot rounds valid. Measured today: 0 rows escape —
              -- latent, which is the reason to close it (sister's handover
              -- on #848's thread, 1. 9.).
              AND p.player_guid NOT LIKE 'OMNIBOT%'
              AND COALESCE(p.player_name, '') NOT LIKE '[BOT]%'
              AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
            GROUP BY r.gaming_session_id
        ),
        -- Team result per session from BOX scoring (session_results is written
        -- by the bot's session scorer and ground-truth verified 2026-08-14).
        -- The allies_wins/axis_wins tallies above count round wins by SIDE —
        -- in stopwatch the teams swap sides every round, so a side tally is
        -- NOT a team score and must never be rendered as one. DISTINCT ON
        -- guards against a session ever being scored twice.
        session_box AS (
            SELECT DISTINCT ON (gaming_session_id)
                gaming_session_id,
                team_1_name,
                team_2_name,
                team_1_score,
                team_2_score,
                winning_team
            FROM session_results
            WHERE gaming_session_id IS NOT NULL
              AND map_name = 'ALL'
            ORDER BY gaming_session_id, id DESC
        )
        SELECT
            sr.gaming_session_id,
            sr.first_date,
            sr.last_date,
            sr.first_time,
            sr.last_time,
            sr.round_count,
            sr.maps_played,
            sr.allies_wins,
            sr.axis_wins,
            COALESCE(sp.player_count, 0) as player_count,
            COALESCE(sp.total_kills, 0) as total_kills,
            COALESCE(sp.total_deaths, 0) as total_deaths,
            COALESCE(sd.total_duration_seconds, 0) as duration_seconds,
            COALESCE(sn.player_names, ARRAY[]::text[]) as player_names,
            sb.team_1_name,
            sb.team_2_name,
            sb.team_1_score,
            sb.team_2_score,
            sb.winning_team
        FROM session_rounds sr
        LEFT JOIN session_players sp ON sr.gaming_session_id = sp.gaming_session_id
        LEFT JOIN session_duration sd ON sr.gaming_session_id = sd.gaming_session_id
        LEFT JOIN session_names sn ON sr.gaming_session_id = sn.gaming_session_id
        LEFT JOIN session_box sb ON sr.gaming_session_id = sb.gaming_session_id
        WHERE 1=1
        {search_filter}
        ORDER BY sr.gaming_session_id DESC
        LIMIT {limit_param} OFFSET {offset_param}
    """

    params = tuple(search_params + [limit, offset])

    try:
        rows = await db.fetch_all(query, params)
    except Exception as e:
        logger.error(f"Error fetching stats sessions: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    sessions = []
    for row in rows:
        session_id = row[0]
        first_date = row[1]
        first_time = str(row[3]) if row[3] else ""
        last_time = str(row[4]) if row[4] else ""
        round_count = row[5]
        maps_str = row[6]
        allies_wins = row[7]
        axis_wins = row[8]
        player_count = row[9]
        total_kills = row[10]
        total_deaths = row[11]
        duration_seconds = row[12]
        player_names_list = row[13] if len(row) > 13 else []
        team_1_name = row[14]
        team_2_name = row[15]
        team_1_score = row[16]
        team_2_score = row[17]
        winning_team = row[18]

        # Format date
        if isinstance(first_date, str):
            dt = datetime.strptime(first_date[:10], "%Y-%m-%d")  # noqa: DTZ007 date-only parsing, no time component used
        else:
            dt = datetime.combine(first_date, datetime.min.time())

        # Format start/end times
        start_time_str = ""
        end_time_str = ""
        if first_time and len(first_time) >= 6:
            ft = first_time.replace(":", "")[:6]
            start_time_str = f"{ft[:2]}:{ft[2:4]}"
        if last_time and len(last_time) >= 6:
            lt = last_time.replace(":", "")[:6]
            end_time_str = f"{lt[:2]}:{lt[2:4]}"

        # Time ago
        now = datetime.now()  # noqa: DTZ005 naive datetime for date-string arithmetic / SQL date filter / log timestamp display
        diff = now - dt
        days = diff.days
        if days == 0:
            time_ago = "Today"
        elif days == 1:
            time_ago = "Yesterday"
        elif days < 7:
            time_ago = f"{days} days ago"
        elif days < 30:
            weeks = days // 7
            time_ago = f"{weeks} week{'s' if weeks > 1 else ''} ago"
        else:
            time_ago = dt.strftime("%b %d, %Y")

        maps_played = [m.strip() for m in maps_str.split(",")] if maps_str else []
        player_names = list(player_names_list or [])

        sessions.append(
            {
                "session_id": session_id,
                "date": str(first_date),
                "formatted_date": dt.strftime("%A, %B %d, %Y"),
                "time_ago": time_ago,
                "start_time": start_time_str,
                "end_time": end_time_str,
                "round_count": round_count,
                "player_count": player_count,
                "maps_played": maps_played,
                "total_kills": total_kills,
                "total_deaths": total_deaths,
                "allies_wins": allies_wins,
                "axis_wins": axis_wins,
                # Team score from BOX scoring (session_results); None when the
                # session predates team attribution — the UI must NOT fall back
                # to the side tallies above, they are not a team score.
                "team_1_name": team_1_name,
                "team_2_name": team_2_name,
                "team_1_score": team_1_score,
                "team_2_score": team_2_score,
                "winning_team": winning_team,
                "duration_seconds": duration_seconds,
                "player_names": player_names,
            }
        )

    return sessions


@router.get("/stats/session/{gaming_session_id}/detail")
async def get_stats_session_detail(
    gaming_session_id: int,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Get full session detail by gaming_session_id.
    Returns matches (grouped R1+R2), per-player stats, round metadata.
    """
    # 1. Get all rounds for this session (R1 and R2 only, exclude R0 summaries)
    round_rows = await db.fetch_all(SESSION_ROUNDS_SQL, (gaming_session_id,))

    if not round_rows:
        raise HTTPException(status_code=404, detail="Session not found")

    round_ids = [r[0] for r in round_rows]
    placeholders = ", ".join(f"${i + 1}" for i in range(len(round_ids)))

    # 2. Get lua_round_teams data for scores and duration
    lua_query = f"""
        SELECT round_id, round_number, allies_score, axis_score,
               actual_duration_seconds, winner_team, map_name
        FROM lua_round_teams
        WHERE round_id IN ({placeholders})
    """
    lua_rows = await db.fetch_all(lua_query, tuple(round_ids))
    lua_by_round = {}
    for lr in lua_rows:
        lua_by_round[lr[0]] = {
            "round_number": lr[1],
            "allies_score": lr[2],
            "axis_score": lr[3],
            "duration_seconds": lr[4],
            "winner_team": lr[5],
        }

    # 3. Build matches (group rounds by map in order of play)
    matches = []
    current_map = None
    current_rounds = []

    for rr in round_rows:
        round_id = rr[0]
        map_name = _normalize_map_name(rr[1])
        round_number = rr[2]
        winner_team = rr[3]
        round_date = str(rr[4]) if rr[4] else None
        round_time = str(rr[5]) if rr[5] else None

        lua = lua_by_round.get(round_id, {})
        # Measured duration first (lua table, then the rounds mirror);
        # actual_time text is a LAST resort — it is the stopwatch target
        # and inflated on surrender rounds (RCA 2026-08-18).
        actual_time_raw = rr[6]
        actual_time_seconds = None
        if actual_time_raw:
            try:
                parts = str(actual_time_raw).split(":")
                if len(parts) == 2:
                    actual_time_seconds = int(parts[0]) * 60 + int(parts[1])
            except (ValueError, IndexError):
                pass  # actual_time format not M:SS — use default 0
        duration = lua.get("duration_seconds") or rr[8] or actual_time_seconds

        round_obj = {
            "round_id": round_id,
            "round_number": round_number,
            "map_name": map_name,
            "winner_team": winner_team,
            "allies_score": lua.get("allies_score"),
            "axis_score": lua.get("axis_score"),
            "duration_seconds": duration,
            "round_date": round_date,
            "round_time": round_time,
            "round_start_unix": rr[7] or 0,
        }

        # Group consecutive rounds on same map into a match
        # But R1 after R2 on same map = new match (replayed map)
        is_new_match = current_map != map_name or (
            round_number == 1 and current_rounds and current_rounds[-1]["round_number"] == 2
        )
        if not is_new_match:
            current_rounds.append(round_obj)
        else:
            if current_rounds:
                matches.append(
                    {
                        "map_name": current_map,
                        "rounds": current_rounds,
                    }
                )
            current_map = map_name
            current_rounds = [round_obj]

    if current_rounds:
        matches.append(
            {
                "map_name": current_map,
                "rounds": current_rounds,
            }
        )

    # 4. Get per-player stats aggregated across session
    player_rows = await db.fetch_all(session_player_sql(placeholders, exclude_bots=False), tuple(round_ids))

    # Use duration from matches (lua fallback to actual_time) for all rounds
    total_session_duration_seconds = sum(
        round_obj.get("duration_seconds") or 0 for match in matches for round_obj in match["rounds"]
    )

    players = []
    for pr in player_rows:
        kills = pr[2] or 0
        deaths = pr[3] or 0
        damage_given = pr[4] or 0
        damage_received = pr[5] or 0
        dpm = round(float(pr[6]), 1) if pr[6] else 0
        kd = float(pr[7]) if pr[7] else 0
        headshot_kills = pr[8] or 0
        # pr[9] = total_kills_for_hs (reserved for future headshot% calc)
        gibs = pr[10] or 0
        self_kills = pr[11] or 0
        useful_kills = pr[12] or 0
        full_selfkills = pr[13] or 0
        revives_given = pr[14] or 0
        times_revived = pr[15] or 0
        time_played_seconds = pr[16] or 0
        kill_assists = pr[17] or 0
        time_dead_minutes = float(pr[18]) if pr[18] else 0.0
        denied_playtime = pr[19] or 0
        total_hits = pr[20] or 0
        total_shots = pr[21] or 0
        weapon_headshots = pr[22] or 0
        tpp_weighted_sum = float(pr[23]) if pr[23] else 0.0
        tpp_weight = float(pr[24]) if pr[24] else 0.0

        hs_pct = round((weapon_headshots / total_hits * 100), 1) if total_hits > 0 else 0
        accuracy = round((total_hits / total_shots * 100), 1) if total_shots > 0 else 0
        efficiency = round((kills / (kills + deaths) * 100), 1) if (kills + deaths) > 0 else 0
        time_played_minutes = time_played_seconds / 60.0

        # Computed alive% (fallback — ignores limbo time, underestimates)
        alive_pct_computed = (
            round(
                max(
                    0.0, min(100.0, 100.0 - (min(time_dead_minutes, time_played_minutes) / time_played_minutes * 100.0))
                ),
                1,
            )
            if time_played_minutes > 0
            else None
        )

        # Engine alive% from TAB[8] (correct — excludes dead + limbo time)
        alive_pct_engine = round(tpp_weighted_sum / tpp_weight, 1) if tpp_weight > 0 else None

        # Primary: prefer engine value, fallback to computed
        alive_pct = alive_pct_engine if alive_pct_engine is not None else alive_pct_computed

        # Drift detection between sources
        alive_pct_diff = (
            round(abs(alive_pct_engine - alive_pct_computed), 1)
            if (alive_pct_engine is not None and alive_pct_computed is not None)
            else None
        )
        alive_pct_drift = alive_pct_diff is not None and alive_pct_diff > 2.0

        played_pct = (
            min(100.0, round((time_played_seconds / total_session_duration_seconds) * 100.0, 1))
            if total_session_duration_seconds > 0
            else None
        )

        players.append(
            {
                "player_guid": pr[0],
                "player_name": pr[1],
                "kills": kills,
                "deaths": deaths,
                "damage_given": damage_given,
                "damage_received": damage_received,
                "dpm": dpm,
                "kd": kd,
                "efficiency": efficiency,
                "headshot_kills": headshot_kills,
                "headshot_pct": hs_pct,
                "gibs": gibs,
                "self_kills": self_kills,
                "useful_kills": useful_kills,
                "full_selfkills": full_selfkills,
                "revives_given": revives_given,
                "times_revived": times_revived,
                "kill_assists": kill_assists,
                "accuracy": accuracy,
                "time_played_seconds": time_played_seconds,
                "time_dead_minutes": round(time_dead_minutes, 2),
                "denied_playtime": denied_playtime,
                "alive_pct": alive_pct,
                "alive_pct_lua": alive_pct_engine,
                "alive_pct_diff": alive_pct_diff,
                "alive_pct_drift": alive_pct_drift,
                "played_pct": played_pct,
                "played_pct_lua": played_pct,  # same source (engine time), kept for frontend compat
            }
        )

    # 5. Scoring — reuse StopwatchScoringService for team-aware map scoring
    first_date = round_rows[0][4] if round_rows else None
    scoring_payload = {"available": False}
    hardcoded_teams: dict | None = None
    scoring_service: StopwatchScoringService | None = None
    try:
        config = load_config()
        db_path = config.sqlite_db_path if config.database_type == "sqlite" else None
        service = SessionDataService(db, db_path)
        scoring_service = StopwatchScoringService(db)
        session_date = str(first_date) if first_date else None
        if session_date:
            scoring_payload, _, hardcoded_teams = await build_session_scoring(
                session_date, round_ids, service, scoring_service
            )
    except Exception as e:
        logger.warning(f"Scoring unavailable for session {gaming_session_id}: {e}")

    # 6. Team matrix — per-player x per-map stats split by round team assignment
    team_matrix_payload: dict = {"available": False, "reason": "no_teams"}
    if scoring_service is not None:
        try:
            team_matrix_payload = await SessionMatrixService(db, scoring_service).compute(
                round_ids,
                matches,
                scoring_payload,
                hardcoded_teams,
            )
        except Exception as e:
            logger.warning(f"Team matrix unavailable for session {gaming_session_id}: {e}")
            team_matrix_payload = {"available": False, "reason": "error"}

    return {
        "session_id": gaming_session_id,
        "date": str(first_date) if first_date else None,
        "player_count": len(players),
        "round_count": len(round_ids),
        "matches": matches,
        "players": players,
        "scoring": scoring_payload,
        "team_matrix": team_matrix_payload,
    }


# ---------------------------------------------------------------------------
# Stats 2.0 (docs/design/18 §E): the basics table and the session awards.
# ---------------------------------------------------------------------------


class SessionBasicsCoverage(BaseModel):
    """What the numbers below are computed over — so a page can say
    "KIS covers 61 of 503 kills" instead of printing a small number as if
    it were the whole night."""

    #: Rounds that pass the validity gate (round_number 1/2, valid, no bots,
    #: completed/substitution) and therefore feed every total.
    rounds_counted: int
    #: Every round the session holds, gate or not.
    rounds_total: int
    #: Kills over the counted rounds, from player_comprehensive_stats.
    total_kills: int
    #: Kills the Kill Impact Score has scored — the proximity-tracked subset.
    #: 0 means no KIS row exists for the session (98 of 151 sessions had no
    #: proximity capture at all when this was written).
    kis_kills: int
    #: True when at least one KIS row exists; kis_total/kis_per_min are null
    #: on every player otherwise (null = not measured, never 0).
    kis_covered: bool
    #: True when session_teams carries two rosters and the BOX scoring ran;
    #: `team` on every player is null otherwise.
    teams_attributed: bool
    #: Players whose denied_playtime exceeds twice their time played — a
    #: figure the definition cannot produce, so denied_pct is null for them.
    #: Measured 2026-09-03: 352 of 5 538 rows from the 2025 supastats backfill
    #: (Jan–May 2025, ~50 s denied per kill against ~8 s since Dec 2025); 8
    #: rows since. The rows are left as recorded; the page says "suspect".
    denied_suspect_players: int


class SessionBasicsTeam(BaseModel):
    key: str
    name: str
    #: BOX points: 2 per map won, 1–1 on a draw (the same figure /sessions shows).
    score: int


class SessionBasicsPlayer(BaseModel):
    """One row of the basics table (docs/design/18 §C plast 1). Every
    definition names its source; the tooltip on the page is this docstring."""

    guid: str
    name: str
    #: 'a' | 'b' from the session_teams roster; null when the session has no
    #: attributed teams or the player is on neither roster (a sub who joined
    #: after the roster was written).
    team: str | None
    #: pcs.time_played_seconds summed over the counted rounds.
    time_played_seconds: int
    #: pcs.denied_playtime (seconds the player kept enemies out of the game).
    denied_playtime_seconds: int
    #: denied / time played × 100 (1 dp); null when the player has no playtime
    #: or the figure is suspect (denied > 2 × played — see coverage).
    denied_pct: float | None
    #: damage_given × 60 / time_played_seconds — from the sums, never from
    #: pcs.dpm rows.
    dpm: float
    kills: int
    deaths: int
    damage_given: int
    damage_received: int
    #: damage_given / max(1, damage_received), 2 dp.
    dmr: float
    #: hits / shots over weapon_comprehensive_stats WITHOUT grenades, syringe,
    #: dynamite, airstrike, artillery, satchel, landmine (light weapons).
    #: null when nothing was fired.
    accuracy: float | None
    #: head HITS / hits over the same weapon set — never headshot kills / kills.
    #: null when nothing hit.
    headshot_pct: float | None
    gibs: int
    #: pcs.most_useful_kills (the legacy "Useful Kills" column; UK = useful,
    #: owner 2026-09-03). The writer's definition, c0rnp0rn8.lua:679: the
    #: victim's next wave was >= limbo time / 2 away — they lose at least half
    #: a spawn cycle. NOT "kills on armed enemies" as the legacy tooltip said;
    #: useful + useless != kills (the middle band is neither).
    useful_kills: int
    #: pcs.useless_kills: kills of an enemy whose next wave was < 5 s away.
    useless_kills: int
    self_kills: int
    #: pcs.full_selfkills: /kill at health > 0 with the full respawn ahead
    #: (the Lua's −2 s window — ~7 % of self kills; the threshold is an open
    #: owner decision, see KNOWN_ISSUES).
    full_selfkills: int
    revives_given: int
    times_revived: int
    #: Sum of storytelling_kill_impact.total_impact for kills this player
    #: made; null when the session has no KIS rows (coverage.kis_covered).
    kis_total: float | None
    #: kis_total / (time_played_seconds / 60), 2 dp; null with kis_total.
    kis_per_min: float | None
    #: time played / the sum of the counted rounds' durations × 100 (1 dp);
    #: null when no round has a duration.
    played_pct: float | None
    #: Engine TAB[8] alive share (excludes dead AND limbo), playtime-weighted;
    #: falls back to 100 − dead/played when the engine value is 0 (35 % of
    #: rows); null when neither exists.
    alive_pct: float | None
    #: True when engine and computed alive % disagree by more than 2 points.
    alive_pct_drift: bool


class SessionBasics(BaseModel):
    gaming_session_id: int
    #: The counted rounds' first date.
    date: str | None
    coverage: SessionBasicsCoverage
    teams: list[SessionBasicsTeam]
    #: Sorted by dpm, descending.
    players: list[SessionBasicsPlayer]


class SessionAwardEntry(BaseModel):
    #: The engine's own award string ("Most damage given"), or the computed
    #: award's name for the three the engine never hands out.
    engine_name: str
    nickname: str
    #: "The Damage Dealer award goes to X for most damage given — 17 139".
    sentence: str
    player: str
    #: null when round_awards carried no guid and no alias resolved.
    guid: str | None
    #: The figure as the page shows it (unit applied).
    value: str
    #: The figure the rank was decided on; null when the award carries no
    #: number at all.
    value_numeric: float | None
    unit: str
    #: Rounds in which this player won this award (0 for computed awards).
    rounds_won: int


class SessionAwardCategory(BaseModel):
    key: str
    label: str
    awards: list[SessionAwardEntry]


class SessionAwards(BaseModel):
    gaming_session_id: int
    rounds_counted: int
    #: Counted rounds that carry at least one engine award (~83 % since June).
    rounds_with_awards: int
    categories: list[SessionAwardCategory]


async def _session_duration_seconds(db: DatabaseAdapter, round_rows: list, round_ids: list[int]) -> int:
    """The denominator of played_pct, the way /detail derives it: the lua
    measured duration first, the rounds mirror second, actual_time LAST
    (it is the stopwatch target, inflated on surrender rounds)."""
    placeholders = ", ".join(f"${i + 1}" for i in range(len(round_ids)))
    lua_by_round: dict = {}
    try:
        lua_rows = await db.fetch_all(
            f"SELECT round_id, actual_duration_seconds FROM lua_round_teams WHERE round_id IN ({placeholders})",
            tuple(round_ids),
        )
        lua_by_round = {lr[0]: lr[1] for lr in lua_rows or []}
    except Exception as e:  # noqa: BLE001 — a missing lua table is a fallback case, not a 500 (Copilot on #898)
        logger.debug("lua_round_teams unavailable for duration: %s", e)
    total = 0
    for rr in round_rows:
        actual_time_seconds = None
        if rr[6]:
            parts = str(rr[6]).split(":")
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                actual_time_seconds = int(parts[0]) * 60 + int(parts[1])
        total += lua_by_round.get(rr[0]) or rr[8] or actual_time_seconds or 0
    return int(total)


def _team_rosters(hardcoded_teams: dict | None) -> dict[str, list[str]]:
    """{team_name: [8-char upper guid]} from get_hardcoded_teams' two shapes."""
    rosters: dict[str, list[str]] = {}
    for team_name, players in (hardcoded_teams or {}).items():
        guids: list[str] = []
        if isinstance(players, dict):
            guids = [str(g) for g in players.get("guids", []) or []]
        else:
            for p in players or []:
                if isinstance(p, dict) and "guid" in p:
                    guids.append(str(p["guid"]))
                elif isinstance(p, str):
                    guids.append(p)
        rosters[str(team_name)] = [g.strip().upper()[:8] for g in guids if g]
    return rosters


async def _session_kis_by_guid(db: DatabaseAdapter, gaming_session_id: int) -> dict[str, tuple[float, int]]:
    """{8-char guid: (total_impact, kills)} over the session's KIS rows; {}
    when the session has none or cannot be scoped (no accepted rounds)."""
    try:
        scope = await resolve_gaming_session_scope(db, gaming_session_id=gaming_session_id)
    except HTTPException:
        return {}
    from datetime import date as _date

    dates = [_date.fromisoformat(d) for d in scope.dates]
    starts, maps, rnums = scope.round_key_arrays()
    try:
        rows = await db.fetch_all(
            f"""
            SELECT killer_guid, SUM(total_impact), COUNT(*)
            FROM storytelling_kill_impact
            WHERE session_date = ANY($1) AND {scope.round_key_filter_sql(2)}
            GROUP BY killer_guid
            """,
            (dates, starts, maps, rnums),
        )
    except Exception as e:  # noqa: BLE001 — no KIS table is "not covered", not a 500
        logger.debug("storytelling_kill_impact unavailable: %s", e)
        return {}
    out: dict[str, tuple[float, int]] = {}
    for guid, impact, n in rows or []:
        key = str(guid or "").strip().upper()[:8]
        if not key:
            continue
        prev = out.get(key, (0.0, 0))
        out[key] = (prev[0] + float(impact or 0.0), prev[1] + int(n or 0))
    return out


@router.get("/stats/session/{gaming_session_id}/basics", response_model=SessionBasics)
async def get_session_basics(
    gaming_session_id: int,
    db: DatabaseAdapter = Depends(get_db),
):
    """The basics table of an evening — one row per human player over the
    counted rounds, with the coverage the numbers rest on. Same round gate
    and the same per-player SQL as /detail (session_player_sql), minus bots,
    plus what the stats 2.0 table needs: denied %, DMR, KIS, useless kills.
    """
    round_rows = await db.fetch_all(SESSION_ROUNDS_SQL, (gaming_session_id,))
    if not round_rows:
        raise HTTPException(status_code=404, detail="Session not found")
    round_ids = [r[0] for r in round_rows]
    placeholders = ", ".join(f"${i + 1}" for i in range(len(round_ids)))
    total_rounds_row = await db.fetch_one(
        "SELECT COUNT(*) FROM rounds WHERE gaming_session_id = $1", (gaming_session_id,)
    )
    rounds_total = int(total_rounds_row[0]) if total_rounds_row and total_rounds_row[0] is not None else len(round_ids)

    player_rows = await db.fetch_all(session_player_sql(placeholders, exclude_bots=True), tuple(round_ids))
    duration = await _session_duration_seconds(db, round_rows, round_ids)
    kis = await _session_kis_by_guid(db, gaming_session_id)
    kis_kills = sum(n for _, n in kis.values())

    # Teams: the BOX scoring's rosters and names (the figure /sessions shows).
    teams: list[dict[str, Any]] = []
    guid_team: dict[str, str] = {}
    first_date = round_rows[0][4] if round_rows else None
    try:
        config = load_config()
        db_path = config.sqlite_db_path if config.database_type == "sqlite" else None
        service = SessionDataService(db, db_path)
        scoring_service = StopwatchScoringService(db)
        if first_date:
            scoring_payload, _w, hardcoded = await build_session_scoring(str(first_date), round_ids, service, scoring_service)
            if scoring_payload.get("available"):
                names = {"a": scoring_payload.get("team_a_name", "Team A"), "b": scoring_payload.get("team_b_name", "Team B")}
                teams = [
                    {"key": "a", "name": names["a"], "score": int(scoring_payload.get("team_a_score") or 0)},
                    {"key": "b", "name": names["b"], "score": int(scoring_payload.get("team_b_score") or 0)},
                ]
                for team_name, guids in _team_rosters(hardcoded).items():
                    key = "a" if team_name == names["a"] else "b" if team_name == names["b"] else None
                    if key:
                        for g in guids:
                            guid_team[g] = key
    except Exception as e:  # noqa: BLE001 — teams are optional; the table is not
        logger.warning(f"Teams unavailable for session {gaming_session_id} basics: {e}")

    players: list[dict[str, Any]] = []
    total_kills = 0
    denied_suspect = 0
    for pr in player_rows:
        kills = int(pr[2] or 0)
        deaths = int(pr[3] or 0)
        damage_given = int(pr[4] or 0)
        damage_received = int(pr[5] or 0)
        time_played_seconds = int(pr[16] or 0)
        time_dead_minutes = float(pr[18]) if pr[18] else 0.0
        denied = int(pr[19] or 0)
        total_hits = int(pr[20] or 0)
        total_shots = int(pr[21] or 0)
        weapon_headshots = int(pr[22] or 0)
        tpp_weighted_sum = float(pr[23]) if pr[23] else 0.0
        tpp_weight = float(pr[24]) if pr[24] else 0.0
        useless = int(pr[25] or 0) if len(pr) > 25 else 0
        total_kills += kills

        played_min = time_played_seconds / 60.0
        dpm = round(damage_given * 60.0 / time_played_seconds, 1) if time_played_seconds > 0 else 0.0
        alive_computed = (
            round(max(0.0, min(100.0, 100.0 - (min(time_dead_minutes, played_min) / played_min * 100.0))), 1)
            if played_min > 0 else None
        )
        alive_engine = round(tpp_weighted_sum / tpp_weight, 1) if tpp_weight > 0 else None
        alive_pct = alive_engine if alive_engine is not None else alive_computed
        drift = alive_engine is not None and alive_computed is not None and abs(alive_engine - alive_computed) > 2.0
        # Denial the definition cannot produce: more than twice the player's
        # own playtime. The 2025 backfill rows carry it; say "suspect", not 900 %.
        denied_ok = time_played_seconds > 0 and denied <= 2 * time_played_seconds
        if time_played_seconds > 0 and not denied_ok:
            denied_suspect += 1
        guid8 = str(pr[0] or "").strip().upper()[:8]
        kis_row = kis.get(guid8)
        kis_total = round(kis_row[0], 1) if kis_row else None
        players.append(
            {
                "guid": pr[0],
                "name": strip_et_colors(pr[1] or ""),
                "team": guid_team.get(guid8),
                "time_played_seconds": time_played_seconds,
                "denied_playtime_seconds": denied,
                "denied_pct": round(denied / time_played_seconds * 100.0, 1) if denied_ok else None,
                "dpm": dpm,
                "kills": kills,
                "deaths": deaths,
                "damage_given": damage_given,
                "damage_received": damage_received,
                "dmr": round(damage_given / max(1, damage_received), 2),
                "accuracy": round(total_hits / total_shots * 100.0, 1) if total_shots > 0 else None,
                "headshot_pct": round(weapon_headshots / total_hits * 100.0, 1) if total_hits > 0 else None,
                "gibs": int(pr[10] or 0),
                "useful_kills": int(pr[12] or 0),
                "useless_kills": useless,
                "self_kills": int(pr[11] or 0),
                "full_selfkills": int(pr[13] or 0),
                "revives_given": int(pr[14] or 0),
                "times_revived": int(pr[15] or 0),
                "kis_total": kis_total,
                "kis_per_min": round(kis_row[0] / played_min, 2) if kis_row and played_min > 0 else None,
                "played_pct": min(100.0, round(time_played_seconds / duration * 100.0, 1)) if duration > 0 else None,
                "alive_pct": alive_pct,
                "alive_pct_drift": bool(drift),
            }
        )
    players.sort(key=lambda p: -p["dpm"])
    return {
        "gaming_session_id": gaming_session_id,
        "date": str(first_date) if first_date else None,
        "coverage": {
            "rounds_counted": len(round_ids),
            "rounds_total": rounds_total,
            "total_kills": total_kills,
            "kis_kills": kis_kills,
            "kis_covered": kis_kills > 0,
            "teams_attributed": bool(teams),
            "denied_suspect_players": denied_suspect,
        },
        "teams": teams,
        "players": players,
    }


@router.get("/stats/session/{gaming_session_id}/awards", response_model=SessionAwards)
async def get_session_awards(
    gaming_session_id: int,
    db: DatabaseAdapter = Depends(get_db),
):
    """The evening's awards, one winner each, gibhub-style: the engine's
    per-round awards rolled up by the rule each award carries
    (session_awards_service.AWARD_RULES — sum, best, or lowest; never a
    summed ratio), plus the three the engine does not hand out (Top Fragger,
    iPod, Playtime), computed from the same rows the basics table shows.
    """
    round_rows = await db.fetch_all(SESSION_ROUNDS_SQL, (gaming_session_id,))
    if not round_rows:
        raise HTTPException(status_code=404, detail="Session not found")
    round_ids = [r[0] for r in round_rows]
    placeholders = ", ".join(f"${i + 1}" for i in range(len(round_ids)))
    try:
        award_rows = await db.fetch_all(
            f"""
            SELECT ra.award_name, ra.player_name, ra.player_guid, ra.award_value, ra.award_value_numeric, ra.round_id
            FROM round_awards ra
            WHERE ra.round_id IN ({placeholders})
              AND (ra.player_guid IS NULL OR UPPER(ra.player_guid) NOT LIKE 'OMNIBOT%')
              AND ra.player_name NOT LIKE '%[BOT]%'
            ORDER BY ra.round_id, ra.id
            """,
            tuple(round_ids),
        ) or []
    except Exception as e:  # noqa: BLE001 — no awards table: the computed three still answer
        logger.debug("round_awards unavailable: %s", e)
        award_rows = []
    rounds_with_awards = len({
        r[5] for r in award_rows
        if not (str(r[2] or "").upper().startswith("OMNIBOT") or "[BOT]" in str(r[1] or ""))
    })

    # GUID for the name-only rows (504 historical rows): aliases, then names.
    nameless = sorted({str(r[1]) for r in award_rows if not r[2] and r[1]})
    alias_map: dict[str, str] = {}
    if nameless:
        alias_map = await resolve_alias_guid_map(db, nameless) or {}
        missing = [n for n in nameless if n.lower() not in alias_map]
        if missing:
            alias_map.update(await resolve_name_guid_map(db, missing) or {})
    rows = []
    for award_name, player_name, guid, value, numeric, _rid in award_rows:
        # The SQL already excludes bots; this guard keeps the promise even if
        # a caller hands the roll-up rows from elsewhere (the stub DB does).
        if str(guid or "").upper().startswith("OMNIBOT") or "[BOT]" in str(player_name or ""):
            continue
        clean = strip_et_colors(player_name or "")
        effective = guid or alias_map.get(str(player_name or "").lower())
        rows.append((award_name, clean, effective, value, numeric))
    engine = roll_up(rows)

    # Computed awards from the basics rows (same gate, same numbers).
    player_rows = await db.fetch_all(session_player_sql(placeholders, exclude_bots=True), tuple(round_ids))
    duration = await _session_duration_seconds(db, round_rows, round_ids)
    basics = [
        {
            "guid": pr[0],
            "name": strip_et_colors(pr[1] or ""),
            "kills": int(pr[2] or 0),
            "deaths": int(pr[3] or 0),
            "played_pct": min(100.0, round(int(pr[16] or 0) / duration * 100.0, 1)) if duration > 0 else None,
        }
        for pr in player_rows
    ]
    awards = computed_awards(basics) + engine
    return {
        "gaming_session_id": gaming_session_id,
        "rounds_counted": len(round_ids),
        "rounds_with_awards": rounds_with_awards,
        "categories": group_by_category(awards),
    }


@router.get("/stats/session/{gaming_session_id}/good-night")
async def get_session_good_night(
    gaming_session_id: int,
    db: DatabaseAdapter = Depends(get_db),
):
    """Good Night Index — rate the EVENING, not the players (plan family 1,
    Phase 1). One 0-100 score + friendship-safe reason chips; computed on
    read from existing tables, no schema."""
    from website.backend.services.good_night_service import GoodNightService

    result = await GoodNightService(db).compute(gaming_session_id)
    if result is None:
        return {"status": "ok", "available": False, "gaming_session_id": gaming_session_id}
    return {"status": "ok", "available": True, **result}


@router.get("/stats/session/{gaming_session_id}/verdicts")
async def get_session_verdicts(
    gaming_session_id: int,
    db: DatabaseAdapter = Depends(get_db),
):
    """Per-player 'how was your night' verdicts for one session (S1.4).

    Verdict = percentile of tonight's DPM within the player's OWN previous
    sessions (rank-vs-self, VISION_2026 anti-goals) — complete data for every
    player, unlike lazily-computed KIS. Labels follow the Leetify bands.
    Players with no history are flagged first_night instead of judged.
    """
    rows = await db.fetch_all(
        """
        SELECT pcs.player_guid,
               MAX(pcs.player_name) AS player_name,
               r.gaming_session_id,
               SUM(pcs.kills) AS kills,
               SUM(pcs.damage_given)::float
                   / NULLIF(SUM(pcs.time_played_seconds) / 60.0, 0) AS dpm
        FROM player_comprehensive_stats pcs
        JOIN rounds r ON r.id = pcs.round_id
        WHERE r.gaming_session_id IS NOT NULL
          AND r.gaming_session_id <= $1
          AND r.is_valid IS DISTINCT FROM FALSE
          AND pcs.time_played_seconds > 0
          AND pcs.player_guid IN (
              SELECT DISTINCT pcs2.player_guid
              FROM player_comprehensive_stats pcs2
              JOIN rounds r2 ON r2.id = pcs2.round_id
              WHERE r2.gaming_session_id = $1
                AND r2.is_valid IS DISTINCT FROM FALSE
                AND pcs2.time_played_seconds > 0
          )
        GROUP BY pcs.player_guid, r.gaming_session_id
        """,
        (gaming_session_id,),
    )
    if not rows:
        return {"status": "ok", "gaming_session_id": gaming_session_id, "players": []}

    current: dict[str, dict] = {}
    history: dict[str, list[float]] = {}
    for guid, name, sid, kills, dpm in rows:
        if int(sid) == gaming_session_id:
            current[guid] = {"name": name, "kills": int(kills or 0), "dpm": float(dpm or 0)}
        else:
            history.setdefault(guid, []).append(float(dpm or 0))

    def _label(pct: float) -> str:
        if pct >= 80:
            return "Great"
        if pct >= 55:
            return "Good"
        if pct >= 30:
            return "Average"
        return "Subpar"

    players = []
    for guid, cur in current.items():
        hist = history.get(guid, [])
        if len(hist) < 3:
            players.append(
                {
                    "guid": guid,
                    "name": cur["name"],
                    "dpm": round(cur["dpm"], 1),
                    "kills": cur["kills"],
                    "first_night": True,
                    "percentile": None,
                    "label": "New",
                    "sessions_in_baseline": len(hist),
                }
            )
            continue
        below = sum(1 for h in hist if h < cur["dpm"])
        pct = round(below / len(hist) * 100)
        avg = sum(hist) / len(hist)
        players.append(
            {
                "guid": guid,
                "name": cur["name"],
                "dpm": round(cur["dpm"], 1),
                "avg_dpm": round(avg, 1),
                "kills": cur["kills"],
                "first_night": False,
                "percentile": pct,
                "label": _label(pct),
                "sessions_in_baseline": len(hist),
            }
        )
    players.sort(key=lambda p: (p["percentile"] is None, -(p["percentile"] or 0)))
    return {
        "status": "ok",
        "gaming_session_id": gaming_session_id,
        "baseline": "own previous sessions, DPM percentile",
        "players": players,
    }


# ============================================================================
# MVP voting (VISION_2026 S3) — peer recognition for a finished session.
# ============================================================================


async def _session_player_pool(db, gaming_session_id: int) -> list[dict]:
    """Players who actually played the session (valid rounds only)."""
    rows = await db.fetch_all(
        """
        SELECT pcs.player_guid, MAX(pcs.player_name) AS name,
               SUM(pcs.kills) AS kills,
               SUM(pcs.damage_given)::float
                   / NULLIF(SUM(pcs.time_played_seconds) / 60.0, 0) AS dpm
        FROM player_comprehensive_stats pcs
        JOIN rounds r ON r.id = pcs.round_id
        WHERE r.gaming_session_id = ?
          AND r.is_valid IS DISTINCT FROM FALSE
          AND pcs.time_played_seconds > 0
          AND pcs.player_guid NOT LIKE 'OMNIBOT%'
          AND pcs.player_name NOT LIKE '[BOT]%'
        GROUP BY pcs.player_guid
        ORDER BY kills DESC
        """,
        (gaming_session_id,),
    )
    return [
        {"guid": r[0], "name": r[1] or (r[0] or "")[:8], "kills": int(r[2] or 0), "dpm": round(float(r[3] or 0), 1)}
        for r in (rows or [])
    ]


async def _mvp_tally(db, gaming_session_id: int) -> dict[str, int]:
    rows = await db.fetch_all(
        "SELECT nominated_guid, COUNT(*) FROM session_mvp_votes WHERE gaming_session_id = ? GROUP BY nominated_guid",
        (gaming_session_id,),
    )
    return {r[0]: int(r[1]) for r in (rows or [])}


@router.get("/stats/session/{gaming_session_id}/mvp")
async def get_session_mvp(
    request: Request,
    gaming_session_id: int,
    db: DatabaseAdapter = Depends(get_db),
):
    """MVP candidates + current tally + 'most underrated' (votes vs KIS rank)."""
    pool = await _session_player_pool(db, gaming_session_id)
    if not pool:
        return {"status": "ok", "gaming_session_id": gaming_session_id, "candidates": []}

    tally = await _mvp_tally(db, gaming_session_id)
    total_votes = sum(tally.values())

    # KIS rank for the session (lower index = higher impact). Scope is the
    # session DATE; bot/testmode names are filtered out of the rank.
    sdate = await db.fetch_val(
        "SELECT MIN(round_date) FROM rounds WHERE gaming_session_id = ?",
        (gaming_session_id,),
    )
    kis_rank: dict[str, int] = {}
    sdate_obj = None
    if sdate is not None:
        try:
            sdate_obj = datetime.strptime(str(sdate)[:10], "%Y-%m-%d").date()  # noqa: DTZ007
        except ValueError:
            sdate_obj = None
    if sdate_obj is not None:
        kis_rows = await db.fetch_all(
            """
            SELECT killer_guid, SUM(total_impact) AS kis
            FROM storytelling_kill_impact
            WHERE session_date = ?
              AND killer_guid NOT LIKE 'OMNIBOT%'
              AND killer_name NOT LIKE '[BOT]%'
            GROUP BY killer_guid
            ORDER BY kis DESC
            """,
            (sdate_obj,),  # session_date is a DATE column — bind a date object
        )
        for i, kr in enumerate(kis_rows or []):
            kis_rank[kr[0]] = i

    # Resolve viewer's existing vote (if logged in) — best-effort, no auth required to read.
    my_vote = None
    user = request.session.get("user") if hasattr(request, "session") else None
    if user and user.get("id") is not None:
        try:
            row = await db.fetch_one(
                "SELECT nominated_guid FROM session_mvp_votes WHERE gaming_session_id = ? AND voter_user_id = ?",
                (gaming_session_id, int(user["id"])),
            )
            my_vote = row[0] if row else None
        except (TypeError, ValueError):
            my_vote = None

    candidates = []
    for p in pool:
        votes = tally.get(p["guid"], 0)
        candidates.append(
            {
                **p,
                "votes": votes,
                "vote_pct": round(votes / total_votes * 100, 1) if total_votes else 0.0,
                "kis_rank": kis_rank.get(p["guid"]),
            }
        )
    candidates.sort(key=lambda c: (-c["votes"], -c["kills"]))

    # "Most underrated": got votes but ranks low on KIS (peers saw value the
    # scoreboard didn't). Only meaningful once votes exist and KIS rank known.
    underrated = None
    rated = [c for c in candidates if c["votes"] > 0 and c["kis_rank"] is not None]
    if rated:
        pick = max(rated, key=lambda c: (c["votes"], c["kis_rank"]))
        if pick["kis_rank"] >= max(2, len(pool) // 2):
            underrated = pick["guid"]

    return {
        "status": "ok",
        "gaming_session_id": gaming_session_id,
        "total_votes": total_votes,
        "my_vote": my_vote,
        "most_underrated_guid": underrated,
        "candidates": candidates,
    }


@router.post("/stats/session/{gaming_session_id}/mvp")
async def post_session_mvp(
    request: Request,
    gaming_session_id: int,
    payload: dict,
    user: dict = Depends(require_user),
    db: DatabaseAdapter = Depends(get_db),
):
    """Cast or change the viewer's MVP vote (one per session, peer-voted)."""
    require_ajax_csrf_header(request)
    try:
        voter_id = int(user["id"])
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Malformed user session")

    nominated = ((payload or {}).get("nominated_guid") or "").strip()
    if not nominated:
        raise HTTPException(status_code=400, detail="nominated_guid required")

    pool = await _session_player_pool(db, gaming_session_id)
    if not pool:
        raise HTTPException(status_code=404, detail="No players for this session")
    if nominated not in {p["guid"] for p in pool}:
        raise HTTPException(status_code=400, detail="Nominee did not play this session")

    # One changeable vote per (session, voter): atomic upsert (no UNIQUE-
    # violation window under rapid double-submits).
    await db.execute(
        """
        INSERT INTO session_mvp_votes (gaming_session_id, voter_user_id, nominated_guid)
        VALUES (?, ?, ?)
        ON CONFLICT (gaming_session_id, voter_user_id) DO UPDATE
        SET nominated_guid = EXCLUDED.nominated_guid,
            updated_at = CURRENT_TIMESTAMP
        """,
        (gaming_session_id, voter_id, nominated),
    )
    tally = await _mvp_tally(db, gaming_session_id)
    return {
        "status": "ok",
        "gaming_session_id": gaming_session_id,
        "my_vote": nominated,
        "votes_for_pick": tally.get(nominated, 0),
        "total_votes": sum(tally.values()),
    }


# ── Session lineups ──────────────────────────────────────────────────────────
# Owner request 2026-08-27: the site shows every advanced stat but never the
# BASIC one — who played with whom. This endpoint derives it from
# lua_round_teams (cumulative rosters since v1.7.3, healed by the bot for
# older rounds): the two persistent teams of a session, and every membership
# change between consecutive rounds, including who replaced whom.


class LineupPlayer(BaseModel):
    guid: str  # 8-char prefix — the site's public player identity
    name: str


class LineupSwap(BaseModel):
    out: LineupPlayer
    incoming: LineupPlayer


class LineupChange(BaseModel):
    """Membership delta of ONE team between two consecutive rounds."""

    map_name: str
    round_number: int
    round_id: int
    team: str  # 'a' | 'b'
    joined: list[LineupPlayer]
    left: list[LineupPlayer]
    #: When exactly one player left and one joined the same team in the same
    #: round, that is a substitution and named as such.
    swaps: list[LineupSwap]


class TeamLineup(BaseModel):
    key: str  # 'a' | 'b'
    #: session_teams name when the bot recorded one, else Team A/Team B.
    name: str
    #: The STARTING lineup (first measured round); later arrivals and
    #: switches are narrated by `changes`, never folded in here.
    players: list[LineupPlayer]


class SessionLineups(BaseModel):
    gaming_session_id: int
    teams: list[TeamLineup]
    changes: list[LineupChange]
    #: Rounds that had no lua roster (pre-webhook history) — named so an
    #: incomplete timeline reads as "unmeasured", never as "no changes".
    rounds_without_roster: int


def _lineup_players(raw) -> list[dict]:
    import json as _json

    if isinstance(raw, str):
        try:
            raw = _json.loads(raw)
        except (ValueError, TypeError):
            return []
    out = []
    for p in raw or []:
        if not isinstance(p, dict):
            continue
        guid = str(p.get("guid") or "")[:8].upper()
        name = str(p.get("name") or "").strip()
        # Bots out, same convention as the roster healer (#819): the local
        # test server (docs/LOCAL_ET_SERVER.md) fills evenings with OMNIBOT
        # rosters, and without this filter the two bot->human turnovers in
        # history were the only full-overlap ties the team mapping ever hit.
        if name.upper().startswith("[BOT]") or guid.startswith("OMNIBOT"):
            continue
        if guid or name:
            out.append({"guid": guid, "name": name})
    return out


@router.get(
    "/stats/session/{gaming_session_id}/lineups",
    response_model=SessionLineups,
)
async def get_session_lineups(gaming_session_id: int, db: DatabaseAdapter = Depends(get_db)):
    rows = await db.fetch_all(
        """
        SELECT r.id, r.map_name, r.round_number,
               l.axis_players, l.allies_players
        FROM rounds r
        LEFT JOIN lua_round_teams l ON l.round_id = r.id
        WHERE r.gaming_session_id = ?
          AND r.round_number IN (1, 2)
          AND (r.round_status IN ('completed', 'substitution')
               OR r.round_status IS NULL)
        ORDER BY r.round_date, CAST(REPLACE(r.round_time, ':', '') AS INTEGER)
        """,
        (gaming_session_id,),
    )
    if not rows:
        exists = await db.fetch_val(
            "SELECT COUNT(*) FROM rounds WHERE gaming_session_id = ?",
            (gaming_session_id,),
        )
        if not exists:
            raise HTTPException(status_code=404, detail="Session not found")
        # The session exists but every round is cancelled/filler — an
        # unmeasured evening, not a missing one.
        return {
            "gaming_session_id": gaming_session_id,
            "teams": [],
            "changes": [],
            "rounds_without_roster": 0,
        }

    # Anchor the two persistent teams on the first round that has a roster;
    # every later round maps its axis/allies onto them by guid overlap (the
    # sides swap every stopwatch round, so the side label is never the team).
    team_sets: dict[str, set] = {"a": set(), "b": set()}
    players_seen: dict[str, dict] = {}
    order: dict[str, list] = {"a": [], "b": []}
    membership_prev: dict[str, set] | None = None
    changes: list[dict] = []
    rounds_without_roster = 0

    for rid, map_name, round_number, axis_raw, allies_raw in rows:
        axis = _lineup_players(axis_raw)
        allies = _lineup_players(allies_raw)
        if not axis and not allies:
            rounds_without_roster += 1
            continue
        for p in axis + allies:
            players_seen.setdefault(p["guid"] or p["name"], p)

        axis_g = {p["guid"] or p["name"] for p in axis}
        allies_g = {p["guid"] or p["name"] for p in allies}
        if not team_sets["a"] and not team_sets["b"]:
            assign = {"a": axis_g, "b": allies_g}
        else:
            # Larger overlap wins; ties keep axis->a so a fully swapped
            # roster still produces a deterministic mapping.
            a_axis = len(team_sets["a"] & axis_g)
            a_allies = len(team_sets["a"] & allies_g)
            if a_axis >= a_allies:
                assign = {"a": axis_g, "b": allies_g}
            else:
                assign = {"a": allies_g, "b": axis_g}

        current = {"a": assign["a"], "b": assign["b"]}
        if membership_prev is not None:
            for key in ("a", "b"):
                joined = sorted(current[key] - membership_prev[key])
                left = sorted(membership_prev[key] - current[key])
                # A player who moved BETWEEN teams is a move, not a swap pair.
                moved = {g for g in joined if g in membership_prev["a"] | membership_prev["b"]}
                swap_in = [g for g in joined if g not in moved]
                swap_left = [g for g in left if g not in current["a"] | current["b"]]
                swaps = []
                if len(swap_in) == 1 and len(swap_left) == 1:
                    swaps.append(
                        {
                            "out": players_seen[swap_left[0]],
                            "incoming": players_seen[swap_in[0]],
                        }
                    )
                if joined or left:
                    changes.append(
                        {
                            "map_name": map_name,
                            "round_number": round_number,
                            "round_id": rid,
                            "team": key,
                            "joined": [players_seen[g] for g in joined],
                            "left": [players_seen[g] for g in left],
                            "swaps": swaps,
                        }
                    )
        membership_prev = current
        for key in ("a", "b"):
            if not order[key]:
                # The STARTING lineup — "what were the teams" means the
                # first measured round; everything after is told by
                # `changes`, so a mid-evening switch does not inflate a
                # 3v3 into apparent 4v4 rosters.
                order[key] = sorted(current[key])
            team_sets[key] |= current[key]

    if not team_sets["a"] and not team_sets["b"]:
        # Every round predates the lua webhook — an unmeasured session.
        return {
            "gaming_session_id": gaming_session_id,
            "teams": [],
            "changes": [],
            "rounds_without_roster": rounds_without_roster,
        }

    # Best-effort display names, same convention as _tonight_team_names in
    # players_router: session_teams stores 8-char guids.
    names = {"a": "Team A", "b": "Team B"}
    try:
        team_rows = await db.fetch_all(
            "SELECT team_name, player_guids FROM session_teams WHERE gaming_session_id = ?",
            (gaming_session_id,),
        )
        import json as _json

        for team_name, guids_raw in team_rows or []:
            guids = guids_raw
            if isinstance(guids, str):
                try:
                    guids = _json.loads(guids)
                except (ValueError, TypeError):
                    continue
            gset = {str(g)[:8].upper() for g in guids or []}
            overlap_a = len(gset & team_sets["a"])
            overlap_b = len(gset & team_sets["b"])
            if overlap_a > overlap_b and team_name:
                names["a"] = str(team_name)
            elif overlap_b > overlap_a and team_name:
                names["b"] = str(team_name)
    except Exception:  # nosec B110 — cosmetic names; rosters are the identity
        logger.debug("session_teams name lookup failed", exc_info=True)

    return {
        "gaming_session_id": gaming_session_id,
        "teams": [
            {
                "key": key,
                "name": names[key],
                "players": [players_seen[g] for g in order[key]],
            }
            for key in ("a", "b")
        ],
        "changes": changes,
        "rounds_without_roster": rounds_without_roster,
    }


# --- One session, round by round ---------------------------------------------
#
# ⛔ WHY THIS EXISTS RATHER THAN 18 CALLS TO /rounds/{id}/viz.
# A session is 10-20 rounds. Asking per round is 18 round-trips for data one
# query answers in 1.2 ms, and it gives the client no way to show a round it
# was never told about — which is how `round_status = 'cancelled'` rounds
# became invisible: `/stats/session/{id}/detail` filters them out and says
# nothing, so a player who played one has nowhere to learn why it is missing.
#
# This endpoint returns EVERY round of the session, cancelled ones included and
# labelled, and leaves counting to the caller.


class RoundPlayerRow(BaseModel):
    """One player's line in one round, as the round recorded it.

    ⚠️ MEASURED, NOT DESIGNED. `player_comprehensive_stats` carries 39
    populated numeric fields per round; this is the subset a person reads,
    including the three the rest of the site never surfaces per round —
    `time_played_seconds`, `gibs`, `damage_received`.
    """

    player_guid: str
    player_name: str
    team: int
    time_played_seconds: int
    gibs: int
    damage_received: int
    damage_given: int
    kills: int
    deaths: int
    headshots: int
    headshot_kills: int
    revives_given: int
    times_revived: int
    xp: float


class SessionRound(BaseModel):
    """One round, with its full roster.

    `duration_seconds` comes from `shared/round_time.py` — the MEASURED clock.
    `rounds.actual_time` is the stopwatch TARGET and overstates ~15% of rounds
    (RCA 2026-08-18), so it is not what a player is shown.
    """

    round_id: int
    map_name: str
    round_number: int
    played_at: str
    #: Null when neither the Lua mirror nor a parseable clock survived.
    duration_seconds: int | None
    end_reason: str | None
    #: 'completed' | 'substitution' | 'cancelled' | ... — shown, never hidden.
    round_status: str | None
    #: False for a cancelled round: the client must be able to show it AND
    #: leave it out of totals, which one flag cannot do if it is missing.
    counts_toward_totals: bool
    match_id: str | None
    players: list[RoundPlayerRow]


class SessionRounds(BaseModel):
    gaming_session_id: int
    session_date: str | None
    #: Rounds whose `counts_toward_totals` is true.
    counted_rounds: int
    #: Every round returned, including the ones that do not count.
    total_rounds: int
    rounds: list[SessionRound]


#: The statuses a round must be in to reach session totals. Everything else —
#: 'cancelled', 'orphan_r2', 'warmup', anything future — does not count.
#:
#: ⛔ AN ALLOWLIST, NOT A DENYLIST. The first version listed the two statuses it
#: knew to exclude, which marked as counting: an invalid completed round, a bot
#: round, and any status invented later. Measured on this database: 88 rounds
#: are `completed` AND (invalid or bot). A consumer trusting the flag would
#: have included data the rest of the site excludes — the flag would have been
#: worse than no flag, because it looks authoritative.
#:
#: Mirrors the session-total gate at sessions_router.py:1258-1300.
COUNTING_ROUND_STATUSES = frozenset({"completed", "substitution"})


def _counts_toward_totals(status: str | None, is_valid, is_bot_round) -> bool:
    """The same three conditions the session-total queries apply."""
    if is_valid is False:
        return False
    if is_bot_round:
        return False
    return status is None or status in COUNTING_ROUND_STATUSES


_SESSION_ROUNDS_SQL = (
    """
    -- ⛔ NOT created_at. That column is the INGESTION time: the importer
    -- supplies round_date and round_time and leaves created_at at its default,
    -- so for historical imports and reprocessed stats it says when the row was
    -- written, not when the round was played. Measured: 907 rounds have a
    -- created_at on a different DAY than their round_date. Showing a player an
    -- import date as "when this happened" is not a rounding error, it is the
    -- wrong fact.
    -- Dual-form time expression (the round_time family's sixth entry, and
    -- the lesson is now mechanical): strip colons FIRST, lpad SECOND.
    -- lpad-first truncates '23:41:53' to '23:41:' (all 3,209 rows are
    -- digit-form today, so the colon branch is latent — which is the reason
    -- to handle it, not an argument against). Proven expression lifted from
    -- validation_family.py's calendar gate.
    SELECT r.id, r.map_name, r.round_number,
           COALESCE(
             (r.round_date::text || ' ' ||
              regexp_replace(
                lpad(regexp_replace(r.round_time,
                                    '^([0-9]{1,2}):([0-9]{2}):([0-9]{2})$',
                                    '\\1\\2\\3'), 6, '0'),
                '^(..)(..)(..)$', '\\1:\\2:\\3'))::timestamp,
             r.created_at) AS played_at,
           """
    + round_duration_sql("r")
    + """ AS duration_seconds,
           r.end_reason, r.round_status, r.match_id,
           r.is_valid, COALESCE(r.is_bot_round, FALSE) AS is_bot_round
    FROM rounds r
    WHERE r.gaming_session_id = $1 AND r.round_number IN (1, 2)
    -- ⛔ ORDER BY the PLAY time, not created_at: the SELECT already computed
    -- played_at for display while the ordering quietly used ingestion time —
    -- measured today, 14 rounds across 2 sessions sat in the wrong order,
    -- and session_date derives from the first (misordered) row. r.id breaks
    -- ties deterministically.
    -- The ALIAS, not a position: 'ORDER BY 4' silently reorders if a
    -- column lands before played_at in the SELECT (Copilot on #871).
    ORDER BY played_at, r.id
"""
)

_SESSION_PLAYERS_SQL = """
    SELECT p.round_id, p.player_guid, p.player_name, p.team,
           p.time_played_seconds, p.gibs, p.damage_received, p.damage_given,
           p.kills, p.deaths, p.headshots, p.headshot_kills,
           p.revives_given, p.times_revived, p.xp
    FROM player_comprehensive_stats p
    JOIN rounds r ON r.id = p.round_id
    WHERE r.gaming_session_id = $1 AND p.round_number IN (1, 2)
      AND p.team IN (1, 2)
      AND p.player_guid NOT LIKE 'OMNIBOT%'
      AND COALESCE(p.player_name, '') NOT LIKE '[BOT]%'
    ORDER BY p.round_id, p.damage_given DESC
"""


@router.get("/stats/session/{gaming_session_id}/rounds", response_model=SessionRounds)
async def get_session_rounds(
    gaming_session_id: int,
    db: DatabaseAdapter = Depends(get_db),
):
    """Every round of one session, each with its full roster."""
    round_rows = await db.fetch_all(_SESSION_ROUNDS_SQL, (gaming_session_id,))
    if not round_rows:
        raise HTTPException(status_code=404, detail="Session not found")

    player_rows = await db.fetch_all(_SESSION_PLAYERS_SQL, (gaming_session_id,))
    by_round: dict[int, list[RoundPlayerRow]] = {}
    for row in player_rows:
        by_round.setdefault(row[0], []).append(
            RoundPlayerRow(
                player_guid=row[1],
                player_name=strip_et_colors(row[2] or ""),
                team=row[3],
                time_played_seconds=row[4] or 0,
                gibs=row[5] or 0,
                damage_received=row[6] or 0,
                damage_given=row[7] or 0,
                kills=row[8] or 0,
                deaths=row[9] or 0,
                headshots=row[10] or 0,
                headshot_kills=row[11] or 0,
                revives_given=row[12] or 0,
                times_revived=row[13] or 0,
                xp=float(row[14] or 0),
            )
        )

    rounds: list[SessionRound] = []
    for row in round_rows:
        status = row[6]
        rounds.append(
            SessionRound(
                round_id=row[0],
                map_name=row[1],
                round_number=row[2],
                played_at=str(row[3]),
                duration_seconds=row[4],
                end_reason=row[5],
                round_status=status,
                counts_toward_totals=_counts_toward_totals(status, row[8], row[9]),
                match_id=row[7],
                players=by_round.get(row[0], []),
            )
        )

    return SessionRounds(
        gaming_session_id=gaming_session_id,
        session_date=str(round_rows[0][3])[:10] if round_rows else None,
        counted_rounds=sum(1 for r in rounds if r.counts_toward_totals),
        total_rounds=len(rounds),
        rounds=rounds,
    )
