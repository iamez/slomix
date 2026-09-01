"""Records sub-router: Season endpoints."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from shared.season_manager import SeasonManager
from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.logging_config import get_app_logger
from website.backend.routers.api_helpers import resolve_display_name

router = APIRouter()
logger = get_app_logger("api.records.seasons")


class CurrentSeason(BaseModel):
    """The current season and the one after it.

    ⚠️ MEASURED, NOT DESIGNED — read off a live response and cross-checked
    against the handler, which has a single return with eight literal keys.

    ⛔ `response_model` FILTERS: a field the handler returns and this model
    omits is dropped silently with a 200.
    """

    #: Season identifier in `YYYY-QN` form, e.g. "2026-Q3".
    id: str
    name: str
    #: Whole days remaining; 0 on the final day, never negative.
    days_left: int
    #: `YYYY-MM-DD`, not a datetime — the handler formats before returning.
    start_date: str
    end_date: str
    next_season_id: str
    next_season_name: str
    next_season_start: str



@router.get("/seasons/current", response_model=CurrentSeason)
async def get_current_season():
    sm = SeasonManager()
    current_id = sm.get_current_season()
    start_date, end_date = sm.get_season_dates(current_id)
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    year, quarter = current_id.split("-Q")
    quarter = int(quarter)
    next_quarter = quarter + 1
    next_year = int(year)
    if next_quarter > 4:
        next_quarter = 1
        next_year += 1
    next_id = f"{next_year}-Q{next_quarter}"
    next_start, _ = sm.get_season_dates(next_id)
    return {
        "id": current_id,
        "name": sm.get_season_name(current_id),
        "days_left": sm.get_days_until_season_end(),
        "start_date": start_str,
        "end_date": end_str,
        "next_season_id": next_id,
        "next_season_name": sm.get_season_name(next_id),
        "next_season_start": next_start.strftime("%Y-%m-%d"),
    }


class SeasonTotals(BaseModel):
    """Season counters. Every one is coalesced with `or 0` in the handler, so
    none of them is nullable — a season with nothing in it reports zeros, not
    nulls.

    ⚠️ `avg_rounds_per_day` is `int | float`, and the union is not laziness:
    `round(rounds / days, 1)` is a float, but the guard `if active_days else 0`
    yields an INT — and that branch is not hypothetical, it is the state of
    every season on its first day. Measured both ways against a live database:
    the current season answers `13.1`, a season pointed at 2030 answers `0`.
    Typing it `float` would rewrite that `0` as `0.0`.
    """

    rounds: int
    players: int
    sessions: int
    maps: int
    kills: int
    active_days: int
    avg_rounds_per_day: int | float


class SeasonTopMap(BaseModel):
    """The most-played map of the season.

    ⛔ `name` IS NULLABLE and the live response never shows it: the handler
    writes `top_map_row[0] if top_map_row else None`, so an empty season sends
    `{"name": null, "plays": 0}`. This endpoint takes NO parameters, so that
    branch cannot be reached by varying a query string — it was measured by
    pointing SeasonManager at a season with no rounds (2030-Q1). An endpoint
    without filters still has states; they just live in the data.
    """

    name: str | None
    plays: int


class SeasonSummary(BaseModel):
    """Totals and activity for the current season.

    ⚠️ `start_date` / `end_date` are `YYYY-MM-DD` HERE, but the sibling
    `/seasons/current/leaders` sends `str(datetime)` — "2026-07-01 00:00:00".
    Same two field names, same router, two formats. Neither is wrong; assuming
    they match is.

    ⛔ `response_model` FILTERS: a field the handler returns and this model
    omits is dropped silently with a 200.
    """

    #: `YYYY-QN`, e.g. "2026-Q3".
    season_id: str
    start_date: str
    end_date: str
    totals: SeasonTotals
    top_map: SeasonTopMap
    #: ⛔ DECLARED HERE OR DROPPED THERE. Every query in this handler goes
    #: through a helper that swallows its exception and returns 0/None, so with
    #: the database down the totals below were all zero and nothing said so —
    #: byte-identical to a season nobody has played yet. These three fields are
    #: how it says so, and `response_model` removes any key the model omits, so
    #: the first attempt at this fix on `/api/stats/overview` was eaten by its
    #: own model. "ok" when every query answered, "partial" when one did not.
    #: ⛔ REQUIRED, no default. A default would let `response_model` INVENT
    #: `status: "ok"` for a handler path that forgot to answer the question —
    #: the model quietly asserting success on the endpoint's behalf, which is
    #: the exact failure this field exists to end. Required means a path that
    #: forgets fails loudly instead.
    status: str
    note: str | None
    failed_metrics: list[str]


@router.get("/seasons/current/summary", response_model=SeasonSummary)
async def get_current_season_summary(db: DatabaseAdapter = Depends(get_db)):
    """
    Summary stats for the current season (totals + activity).
    """
    sm = SeasonManager()
    current_id = sm.get_current_season()
    start_date, end_date = sm.get_season_dates(current_id)
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    # ⛔ A SWALLOWED FAILURE HAS TO LEAVE A MARK ON THE ANSWER, not only in the
    # log. Every one of these defaults (0, None) is a value the caller cannot
    # tell from a real measurement, so without this list the endpoint answers
    # 200 with a blank season during a total outage.
    failures: list[str] = []

    async def safe_val(query: str, params: tuple | None = None, default=0,
                       metric: str = ""):
        try:
            return await db.fetch_val(query, params)
        except Exception as e:
            logger.error(f"[season_summary] query failed ({metric or '?'}): {e}")
            failures.append(metric or "unknown")
            return default

    async def safe_one(query: str, params: tuple | None = None, metric: str = ""):
        try:
            return await db.fetch_one(query, params)
        except Exception as e:
            logger.error(f"[season_summary] query failed ({metric or '?'}): {e}")
            failures.append(metric or "unknown")
            return None

    round_status_clause = "AND (round_status IN ('completed', 'substitution') OR round_status IS NULL)"

    try:
        rounds_count = await db.fetch_val(
            f"""
            SELECT COUNT(*)
            FROM rounds
            WHERE round_number IN (1, 2)
              {round_status_clause}
              AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            """,
            (start_str, end_str),
        )
        players_count = await db.fetch_val(
            """
            SELECT COUNT(DISTINCT player_guid)
            FROM player_comprehensive_stats
            WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT) AND player_name NOT LIKE '[BOT]%' AND (player_guid IS NULL OR player_guid NOT LIKE 'OMNIBOT%') AND NOT EXISTS (SELECT 1 FROM rounds _vr WHERE _vr.id = player_comprehensive_stats.round_id AND (_vr.is_valid IS FALSE OR _vr.is_bot_round IS TRUE OR (_vr.round_status IS NOT NULL AND _vr.round_status NOT IN ('completed', 'substitution'))))
            """,
            (start_str, end_str),
        )
        sessions_count = await db.fetch_val(
            f"""
            SELECT COUNT(DISTINCT gaming_session_id)
            FROM rounds
            WHERE gaming_session_id IS NOT NULL
              {round_status_clause}
              AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            """,
            (start_str, end_str),
        )
        maps_count = await db.fetch_val(
            f"""
            SELECT COUNT(DISTINCT map_name)
            FROM rounds
            WHERE map_name IS NOT NULL
              {round_status_clause}
              AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            """,
            (start_str, end_str),
        )
        kills_total = await db.fetch_val(
            """
            SELECT COALESCE(SUM(kills), 0)
            FROM player_comprehensive_stats
            WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT) AND player_name NOT LIKE '[BOT]%' AND (player_guid IS NULL OR player_guid NOT LIKE 'OMNIBOT%') AND NOT EXISTS (SELECT 1 FROM rounds _vr WHERE _vr.id = player_comprehensive_stats.round_id AND (_vr.is_valid IS FALSE OR _vr.is_bot_round IS TRUE OR (_vr.round_status IS NOT NULL AND _vr.round_status NOT IN ('completed', 'substitution'))))
            """,
            (start_str, end_str),
        )
        # No bot filter here: `rounds` has no player dimension — a pasted
        # player_name clause made this raise "column does not exist" and the
        # endpoint answered 200 with active_days silently null.
        active_days = await db.fetch_val(
            f"""
            SELECT COUNT(DISTINCT SUBSTR(CAST(round_date AS TEXT), 1, 10))
            FROM rounds
            WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
              {round_status_clause}
            """,
            (start_str, end_str),
        )
        top_map_row = await db.fetch_one(
            f"""
            SELECT map_name, COUNT(*) as plays
            FROM rounds
            WHERE map_name IS NOT NULL
              {round_status_clause}
              AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            GROUP BY map_name
            ORDER BY plays DESC
            LIMIT 1
            """,
            (start_str, end_str),
        )
    except Exception as e:
        logger.warning(f"[season_summary] round_status filter failed, retrying fallback: {e}")

        rounds_count = await safe_val(
            """
            SELECT COUNT(*)
            FROM rounds
            WHERE round_number IN (1, 2)
              AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            """,
            (start_str, end_str),
            default=None,
            metric="rounds_count"
        )
        sessions_count = await safe_val(
            """
            SELECT COUNT(DISTINCT gaming_session_id)
            FROM rounds
            WHERE gaming_session_id IS NOT NULL
              AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            """,
            (start_str, end_str),
            default=None,
            metric="sessions_count"
        )
        maps_count = await safe_val(
            """
            SELECT COUNT(DISTINCT map_name)
            FROM rounds
            WHERE map_name IS NOT NULL
              AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            """,
            (start_str, end_str),
            default=None,
            metric="maps_count"
        )
        # Same shape as the primary variant: rounds has no player columns,
        # so the bot filter never belonged on this query.
        active_days = await safe_val(
            """
            SELECT COUNT(DISTINCT SUBSTR(CAST(round_date AS TEXT), 1, 10))
            FROM rounds
            WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            """,
            (start_str, end_str),
            default=None,
            metric="active_days"
        )
        top_map_row = await safe_one(
            """
            SELECT map_name, COUNT(*) as plays
            FROM rounds
            WHERE map_name IS NOT NULL
              AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            GROUP BY map_name
            ORDER BY plays DESC
            LIMIT 1
            """,
            (start_str, end_str),
            metric="top_map_row"
        )
        players_count = await safe_val(
            """
            SELECT COUNT(DISTINCT player_guid)
            FROM player_comprehensive_stats
            WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT) AND player_name NOT LIKE '[BOT]%' AND (player_guid IS NULL OR player_guid NOT LIKE 'OMNIBOT%') AND NOT EXISTS (SELECT 1 FROM rounds _vr WHERE _vr.id = player_comprehensive_stats.round_id AND (_vr.is_valid IS FALSE OR _vr.is_bot_round IS TRUE OR (_vr.round_status IS NOT NULL AND _vr.round_status NOT IN ('completed', 'substitution'))))
            """,
            (start_str, end_str),
            metric="players_count"
        )
        kills_total = await safe_val(
            """
            SELECT COALESCE(SUM(kills), 0)
            FROM player_comprehensive_stats
            WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT) AND player_name NOT LIKE '[BOT]%' AND (player_guid IS NULL OR player_guid NOT LIKE 'OMNIBOT%') AND NOT EXISTS (SELECT 1 FROM rounds _vr WHERE _vr.id = player_comprehensive_stats.round_id AND (_vr.is_valid IS FALSE OR _vr.is_bot_round IS TRUE OR (_vr.round_status IS NOT NULL AND _vr.round_status NOT IN ('completed', 'substitution'))))
            """,
            (start_str, end_str),
            metric="kills_total"
        )

        # Legacy SQLite fallback removed — PostgreSQL-only (sessions table does not exist)

    active_days = active_days or 0
    rounds_count = rounds_count or 0
    avg_rounds = round(rounds_count / active_days, 1) if active_days else 0
    top_map = top_map_row[0] if top_map_row else None
    top_map_plays = top_map_row[1] if top_map_row else 0

    return {
        "season_id": current_id,
        "start_date": start_str,
        "end_date": end_str,
        "totals": {
            "rounds": rounds_count,
            "players": players_count or 0,
            "sessions": sessions_count or 0,
            "maps": maps_count or 0,
            "kills": kills_total or 0,
            "active_days": active_days,
            "avg_rounds_per_day": avg_rounds,
        },
        "top_map": {"name": top_map, "plays": top_map_plays},
        # ⛔ ZEROS THAT ARE MISSING, NOT MEASURED. Every figure above comes back
        # 0 when its query raised, and 0 is a perfectly ordinary season total —
        # so without these the reader cannot tell a dead database from a quiet
        # quarter. Derived from the failure LIST, never from the values: reading
        # it off the zeros would be circular, because a genuinely empty season
        # produces the same zeros.
        "status": "ok" if not failures else "partial",
        "note": None if not failures else (
            f"{len(failures)} of the season queries failed; the figures they "
            f"feed are missing, not zero"),
        "failed_metrics": failures,
    }


class SeasonLeader(BaseModel):
    """One category leader: who, and with what figure.

    `value` is `int | float` because `leader_payload` is called with a
    per-category cast: `float` for `dpm` and `time_dead`, `int` for the other
    ten. A bare `float` would rewrite every counter as `x.0`.
    """

    player: str
    value: int | float


class LongestSession(BaseModel):
    """The season's biggest gaming session.

    ⛔ TYPED FROM THE CODE, NOT FROM THE RUNNING SERVER — and that distinction
    decided the type. The dev server answers `"longest_session": null`, which
    reads like a broken query, and typing from it would have pinned this field
    to null forever. It is not broken: the same request through the code in the
    tree answers `{"rounds": 23, "date": "2026-07-18"}`. The server has been up
    since 2026-08-28 06:57 and the fix landed at 13:08 the same day, so the
    process is running a handler six hours older than the file.
    ⚠️ A live endpoint is evidence about a DEPLOYED BUILD, not about the code
    you are typing. Check the service start time against the file's git log
    before trusting a sample.
    """

    rounds: int
    #: `MIN(round_date)` of the session, `YYYY-MM-DD`.
    date: str


class SeasonLeaders(BaseModel):
    """The thirteen category leaders, plus the biggest session.

    ⭐ EVERY KEY IS ALWAYS PRESENT AND EVERY VALUE MAY BE NULL — the exact
    opposite of `StatsRecords` in this same release, where the keys disappear
    instead. Both endpoints answer "nothing to report" and they answer it in
    incompatible ways, so a consumer cannot carry one habit across: here you
    check the VALUE, there you check PRESENCE. Measured: pointed at a season
    with no rounds, all fourteen keys are present and all fourteen are null.

    ⛔ Consequently this route must NOT take `response_model_exclude_none`.
    Dropping the nulls would turn "no leader for this category" into "we did
    not mention it" and destroy the distinction the handler is drawing.
    """

    damage_given: SeasonLeader | None
    damage_received: SeasonLeader | None
    team_damage: SeasonLeader | None
    revives: SeasonLeader | None
    deaths: SeasonLeader | None
    gibs: SeasonLeader | None
    objectives: SeasonLeader | None
    xp: SeasonLeader | None
    kills: SeasonLeader | None
    dpm: SeasonLeader | None
    time_alive: SeasonLeader | None
    time_dead: SeasonLeader | None
    longest_session: LongestSession | None


class SeasonLeadersResponse(BaseModel):
    """⚠️ `start_date` / `end_date` are `str(datetime)` here —
    "2026-07-01 00:00:00" — while `/seasons/current/summary` sends
    "2026-07-01" for the same two names. Do not assume the pair matches."""

    start_date: str
    end_date: str
    leaders: SeasonLeaders
    #: Same contract as SeasonSummary. Thirteen separate lookups here, each
    #: swallowing its own exception and returning None — and a `null` leader is
    #: exactly what a category with no data looks like, so an outage produced
    #: thirteen plausible nulls and no sign at all.
    #: ⛔ REQUIRED, no default. A default would let `response_model` INVENT
    #: `status: "ok"` for a handler path that forgot to answer the question —
    #: the model quietly asserting success on the endpoint's behalf, which is
    #: the exact failure this field exists to end. Required means a path that
    #: forgets fails loudly instead.
    status: str
    note: str | None
    failed_metrics: list[str]


@router.get("/seasons/current/leaders", response_model=SeasonLeadersResponse)
async def get_season_leaders(db: DatabaseAdapter = Depends(get_db)):
    """
    Get season leaders for various categories.
    Returns top player in each category for the current season.
    """
    # Get current season date range from SeasonManager
    sm = SeasonManager()
    start_date, end_date = sm.get_season_dates()
    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")

    dmg_given_query = """
        SELECT player_guid, MAX(player_name) as player_name, SUM(damage_given) as total_damage
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT) AND player_name NOT LIKE '[BOT]%' AND (player_guid IS NULL OR player_guid NOT LIKE 'OMNIBOT%') AND NOT EXISTS (SELECT 1 FROM rounds _vr WHERE _vr.id = player_comprehensive_stats.round_id AND (_vr.is_valid IS FALSE OR _vr.is_bot_round IS TRUE OR (_vr.round_status IS NOT NULL AND _vr.round_status NOT IN ('completed', 'substitution'))))
        GROUP BY player_guid
        ORDER BY total_damage DESC
        LIMIT 1
    """
    dmg_recv_query = """
        SELECT player_guid, MAX(player_name) as player_name, SUM(damage_received) as total_damage
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT) AND player_name NOT LIKE '[BOT]%' AND (player_guid IS NULL OR player_guid NOT LIKE 'OMNIBOT%') AND NOT EXISTS (SELECT 1 FROM rounds _vr WHERE _vr.id = player_comprehensive_stats.round_id AND (_vr.is_valid IS FALSE OR _vr.is_bot_round IS TRUE OR (_vr.round_status IS NOT NULL AND _vr.round_status NOT IN ('completed', 'substitution'))))
        GROUP BY player_guid
        ORDER BY total_damage DESC
        LIMIT 1
    """
    team_dmg_query = """
        SELECT player_guid, MAX(player_name) as player_name, SUM(team_damage_given) as total_team_damage
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT) AND player_name NOT LIKE '[BOT]%' AND (player_guid IS NULL OR player_guid NOT LIKE 'OMNIBOT%') AND NOT EXISTS (SELECT 1 FROM rounds _vr WHERE _vr.id = player_comprehensive_stats.round_id AND (_vr.is_valid IS FALSE OR _vr.is_bot_round IS TRUE OR (_vr.round_status IS NOT NULL AND _vr.round_status NOT IN ('completed', 'substitution'))))
        GROUP BY player_guid
        ORDER BY total_team_damage DESC
        LIMIT 1
    """
    revives_query = """
        SELECT player_guid, MAX(player_name) as player_name, SUM(revives_given) as total_revives
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT) AND player_name NOT LIKE '[BOT]%' AND (player_guid IS NULL OR player_guid NOT LIKE 'OMNIBOT%') AND NOT EXISTS (SELECT 1 FROM rounds _vr WHERE _vr.id = player_comprehensive_stats.round_id AND (_vr.is_valid IS FALSE OR _vr.is_bot_round IS TRUE OR (_vr.round_status IS NOT NULL AND _vr.round_status NOT IN ('completed', 'substitution'))))
        GROUP BY player_guid
        ORDER BY total_revives DESC
        LIMIT 1
    """
    deaths_query = """
        SELECT player_guid, MAX(player_name) as player_name, SUM(deaths) as total_deaths
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT) AND player_name NOT LIKE '[BOT]%' AND (player_guid IS NULL OR player_guid NOT LIKE 'OMNIBOT%') AND NOT EXISTS (SELECT 1 FROM rounds _vr WHERE _vr.id = player_comprehensive_stats.round_id AND (_vr.is_valid IS FALSE OR _vr.is_bot_round IS TRUE OR (_vr.round_status IS NOT NULL AND _vr.round_status NOT IN ('completed', 'substitution'))))
        GROUP BY player_guid
        ORDER BY total_deaths DESC
        LIMIT 1
    """
    gibs_query = """
        SELECT player_guid, MAX(player_name) as player_name, SUM(gibs) as total_gibs
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT) AND player_name NOT LIKE '[BOT]%' AND (player_guid IS NULL OR player_guid NOT LIKE 'OMNIBOT%') AND NOT EXISTS (SELECT 1 FROM rounds _vr WHERE _vr.id = player_comprehensive_stats.round_id AND (_vr.is_valid IS FALSE OR _vr.is_bot_round IS TRUE OR (_vr.round_status IS NOT NULL AND _vr.round_status NOT IN ('completed', 'substitution'))))
        GROUP BY player_guid
        ORDER BY total_gibs DESC
        LIMIT 1
    """
    objectives_query = """
        SELECT player_guid, MAX(player_name) as player_name,
               SUM(
                    COALESCE(objectives_completed, 0) +
                    COALESCE(objectives_destroyed, 0) +
                    COALESCE(objectives_stolen, 0) +
                    COALESCE(objectives_returned, 0) +
                    COALESCE(dynamites_planted, 0) +
                    COALESCE(dynamites_defused, 0)
               ) as total_objectives
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT) AND player_name NOT LIKE '[BOT]%' AND (player_guid IS NULL OR player_guid NOT LIKE 'OMNIBOT%') AND NOT EXISTS (SELECT 1 FROM rounds _vr WHERE _vr.id = player_comprehensive_stats.round_id AND (_vr.is_valid IS FALSE OR _vr.is_bot_round IS TRUE OR (_vr.round_status IS NOT NULL AND _vr.round_status NOT IN ('completed', 'substitution'))))
        GROUP BY player_guid
        ORDER BY total_objectives DESC
        LIMIT 1
    """
    xp_query = """
        SELECT player_guid, MAX(player_name) as player_name, SUM(xp) as total_xp
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT) AND player_name NOT LIKE '[BOT]%' AND (player_guid IS NULL OR player_guid NOT LIKE 'OMNIBOT%') AND NOT EXISTS (SELECT 1 FROM rounds _vr WHERE _vr.id = player_comprehensive_stats.round_id AND (_vr.is_valid IS FALSE OR _vr.is_bot_round IS TRUE OR (_vr.round_status IS NOT NULL AND _vr.round_status NOT IN ('completed', 'substitution'))))
        GROUP BY player_guid
        ORDER BY total_xp DESC
        LIMIT 1
    """
    kills_query = """
        SELECT player_guid, MAX(player_name) as player_name, SUM(kills) as total_kills
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT) AND player_name NOT LIKE '[BOT]%' AND (player_guid IS NULL OR player_guid NOT LIKE 'OMNIBOT%') AND NOT EXISTS (SELECT 1 FROM rounds _vr WHERE _vr.id = player_comprehensive_stats.round_id AND (_vr.is_valid IS FALSE OR _vr.is_bot_round IS TRUE OR (_vr.round_status IS NOT NULL AND _vr.round_status NOT IN ('completed', 'substitution'))))
        GROUP BY player_guid
        ORDER BY total_kills DESC
        LIMIT 1
    """
    dpm_query = """
        SELECT player_guid, MAX(player_name) as player_name,
               ROUND((SUM(damage_given)::numeric / NULLIF(SUM(time_played_seconds), 0) * 60), 1) as dpm
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT) AND player_name NOT LIKE '[BOT]%' AND (player_guid IS NULL OR player_guid NOT LIKE 'OMNIBOT%') AND NOT EXISTS (SELECT 1 FROM rounds _vr WHERE _vr.id = player_comprehensive_stats.round_id AND (_vr.is_valid IS FALSE OR _vr.is_bot_round IS TRUE OR (_vr.round_status IS NOT NULL AND _vr.round_status NOT IN ('completed', 'substitution'))))
        GROUP BY player_guid
        HAVING SUM(time_played_seconds) > 600
        ORDER BY dpm DESC
        LIMIT 1
    """
    time_alive_query = """
        SELECT player_guid, MAX(player_name) as player_name,
               SUM(time_played_seconds) - SUM(LEAST(COALESCE(time_dead_minutes, 0) * 60, time_played_seconds)) as time_alive_seconds
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT) AND player_name NOT LIKE '[BOT]%' AND (player_guid IS NULL OR player_guid NOT LIKE 'OMNIBOT%') AND NOT EXISTS (SELECT 1 FROM rounds _vr WHERE _vr.id = player_comprehensive_stats.round_id AND (_vr.is_valid IS FALSE OR _vr.is_bot_round IS TRUE OR (_vr.round_status IS NOT NULL AND _vr.round_status NOT IN ('completed', 'substitution'))))
        GROUP BY player_guid
        ORDER BY time_alive_seconds DESC
        LIMIT 1
    """
    fallback_time_alive = """
        SELECT player_guid, MAX(player_name) as player_name,
               SUM(time_played_seconds) as time_alive_seconds
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT) AND player_name NOT LIKE '[BOT]%' AND (player_guid IS NULL OR player_guid NOT LIKE 'OMNIBOT%') AND NOT EXISTS (SELECT 1 FROM rounds _vr WHERE _vr.id = player_comprehensive_stats.round_id AND (_vr.is_valid IS FALSE OR _vr.is_bot_round IS TRUE OR (_vr.round_status IS NOT NULL AND _vr.round_status NOT IN ('completed', 'substitution'))))
        GROUP BY player_guid
        ORDER BY time_alive_seconds DESC
        LIMIT 1
    """
    time_dead_query = """
        SELECT player_guid, MAX(player_name) as player_name,
               SUM(LEAST(COALESCE(time_dead_minutes, 0) * 60, time_played_seconds)) / 60.0 as time_dead_minutes
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT) AND player_name NOT LIKE '[BOT]%' AND (player_guid IS NULL OR player_guid NOT LIKE 'OMNIBOT%') AND NOT EXISTS (SELECT 1 FROM rounds _vr WHERE _vr.id = player_comprehensive_stats.round_id AND (_vr.is_valid IS FALSE OR _vr.is_bot_round IS TRUE OR (_vr.round_status IS NOT NULL AND _vr.round_status NOT IN ('completed', 'substitution'))))
        GROUP BY player_guid
        ORDER BY time_dead_minutes DESC
        LIMIT 1
    """
    fallback_time_dead = """
        SELECT player_guid, MAX(player_name) as player_name,
               SUM(COALESCE(time_dead_minutes, 0)) as time_dead_minutes
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT) AND player_name NOT LIKE '[BOT]%' AND (player_guid IS NULL OR player_guid NOT LIKE 'OMNIBOT%') AND NOT EXISTS (SELECT 1 FROM rounds _vr WHERE _vr.id = player_comprehensive_stats.round_id AND (_vr.is_valid IS FALSE OR _vr.is_bot_round IS TRUE OR (_vr.round_status IS NOT NULL AND _vr.round_status NOT IN ('completed', 'substitution'))))
        GROUP BY player_guid
        ORDER BY time_dead_minutes DESC
        LIMIT 1
    """
    # ⛔ THIS QUERY COUNTS ROUNDS, NOT PLAYERS, so it may not carry the
    # per-player guard the others do. It used to: `player_name NOT LIKE
    # '[BOT]%'`, `player_guid NOT LIKE 'OMNIBOT%'` and a subquery correlating
    # on `player_comprehensive_stats.round_id` were all copied onto a
    # `FROM rounds` query. `rounds` has none of those columns, so asyncpg
    # raised UndefinedColumnError on EVERY call — and `_fetch_one_with_field`
    # catches Exception and returns None, so `longest_session` was silently
    # null for as long as the copy has been there. A failure that logs at
    # DEBUG and answers 200 is indistinguishable from "no data" to the reader.
    #
    # The validity guard belongs here and is expressed against `rounds`
    # directly; bot ROUNDS are excluded by `is_bot_round`, which is the
    # round-level equivalent of the player-level bot filters.
    session_query = """
        SELECT gaming_session_id, COUNT(*) as round_count, MIN(round_date) as session_date
        FROM rounds
        WHERE round_number IN (1, 2)
          AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
          AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
          AND gaming_session_id IS NOT NULL
          AND is_valid IS NOT FALSE
          AND (round_status IN ('completed', 'substitution') OR round_status IS NULL)
          AND NOT COALESCE(is_bot_round, FALSE)
        GROUP BY gaming_session_id
        ORDER BY round_count DESC
        LIMIT 1
    """

    def _swap_date_field(query: str, date_field: str) -> str:
        return query.replace("round_date", date_field)

    # Same contract as the summary endpoint above: a `null` leader is what a
    # category with no data looks like, so a failure has to be recorded or it
    # arrives as a plausible answer.
    leader_failures: list[str] = []

    async def _fetch_one_with_field(query: str, date_field: str,
                                    metric: str = ""):
        try:
            return await db.fetch_one(
                _swap_date_field(query, date_field),
                (start_date_str, end_date_str),
            )
        except Exception:
            # ⚠️ WARNING, not debug. At debug level a production outage here
            # left no trace at all: thirteen nulls in the response and nothing
            # in the log to say why.
            logger.warning("DB query failed for %s (date_field=%s)",
                           metric or "?", date_field, exc_info=True)
            # ⚠️ The CATEGORY, not the date column. All thirteen lookups use the
            # same `round_date`, so recording the column collapsed thirteen
            # failures into one entry and the note then said "1 leader queries
            # failed" during a total outage — an undercount that reads as a
            # single missing category.
            leader_failures.append(metric or "unknown")
            return None

    def _forget_failure(metric: str) -> None:
        """Undo one recorded failure after a retry answered.

        Removes a single occurrence rather than every one: if the same category
        failed twice for different reasons, only the attempt that was recovered
        is forgotten.
        """
        if metric in leader_failures:
            leader_failures.remove(metric)

    async def _fetch_one_with_fallback(query: str, metric: str = ""):
        return await _fetch_one_with_field(query, "round_date", metric)

    async def fetch_leaders():
        dmg_given = await _fetch_one_with_fallback(dmg_given_query, "dmg_given")
        dmg_recv = await _fetch_one_with_fallback(dmg_recv_query, "dmg_recv")
        team_dmg = await _fetch_one_with_fallback(team_dmg_query, "team_dmg")
        revives = await _fetch_one_with_fallback(revives_query, "revives")
        deaths = await _fetch_one_with_fallback(deaths_query, "deaths")
        gibs = await _fetch_one_with_fallback(gibs_query, "gibs")
        objectives = await _fetch_one_with_fallback(objectives_query, "objectives")
        xp = await _fetch_one_with_fallback(xp_query, "xp")
        kills = await _fetch_one_with_fallback(kills_query, "kills")
        dpm = await _fetch_one_with_fallback(dpm_query, "dpm")
        # ⛔ A RECOVERED VALUE IS NOT A FAILURE. The primary query raising and the
        # compatibility fallback succeeding is the schema-drift path working as
        # designed — but the first attempt had already named the category in
        # `leader_failures`, so the response carried usable data AND told every
        # consumer to suppress it. The marker is dropped when the retry answers.
        time_alive = await _fetch_one_with_fallback(time_alive_query, "time_alive")
        if time_alive is None:
            time_alive = await _fetch_one_with_fallback(fallback_time_alive, "time_alive")
            if time_alive is not None:
                _forget_failure("time_alive")
        time_dead = await _fetch_one_with_fallback(time_dead_query, "time_dead")
        if time_dead is None:
            time_dead = await _fetch_one_with_fallback(fallback_time_dead, "time_dead")
            if time_dead is not None:
                _forget_failure("time_dead")
        # ⚠️ `metric=` was missing here, so a longest-session failure was
        # recorded as "unknown" — the response said "partial" and refused to say
        # WHICH leader was gone, which is the one thing the field is for.
        session = await _fetch_one_with_field(session_query, "round_date",
                                              "longest_session")
        return {
            "damage_given": dmg_given,
            "damage_received": dmg_recv,
            "team_damage": team_dmg,
            "revives": revives,
            "deaths": deaths,
            "gibs": gibs,
            "objectives": objectives,
            "xp": xp,
            "kills": kills,
            "dpm": dpm,
            "time_alive": time_alive,
            "time_dead": time_dead,
            "session": session,
        }

    leaders_rows = await fetch_leaders()

    dmg_given = leaders_rows["damage_given"]
    dmg_recv = leaders_rows["damage_received"]
    team_dmg = leaders_rows["team_damage"]
    revives = leaders_rows["revives"]
    deaths = leaders_rows["deaths"]
    gibs = leaders_rows["gibs"]
    objectives = leaders_rows["objectives"]
    xp = leaders_rows["xp"]
    kills = leaders_rows["kills"]
    dpm = leaders_rows["dpm"]
    time_alive = leaders_rows["time_alive"]
    time_dead = leaders_rows["time_dead"]
    session = leaders_rows["session"]

    async def leader_payload(row, cast_fn):
        if not row:
            return None
        display_name = await resolve_display_name(db, row[0], row[1] or "Unknown")
        return {"player": display_name, "value": cast_fn(row[2])}

    def _leaders_status() -> dict:
        # Built after the leaders are resolved, because `leader_failures` is
        # appended to while they are being fetched.
        return {
            "status": "ok" if not leader_failures else "partial",
            "note": None if not leader_failures else (
                f"{len(leader_failures)} leader queries failed; the missing "
                f"categories are unknown, not empty"),
            "failed_metrics": leader_failures,
        }

    return {
        "start_date": str(start_date),
        "end_date": str(end_date),
        "leaders": {
            "damage_given": await leader_payload(dmg_given, int),
            "damage_received": await leader_payload(dmg_recv, int),
            "team_damage": await leader_payload(team_dmg, int),
            "revives": await leader_payload(revives, int),
            "deaths": await leader_payload(deaths, int),
            "gibs": await leader_payload(gibs, int),
            "objectives": await leader_payload(objectives, int),
            "xp": await leader_payload(xp, int),
            "kills": await leader_payload(kills, int),
            "dpm": await leader_payload(dpm, float),
            "time_alive": await leader_payload(time_alive, int),
            "time_dead": await leader_payload(time_dead, float),
            "longest_session": {
                "rounds": int(session[1]) if session else 0,
                "date": str(session[2]) if session else None
            } if session else None
        },
        # ⚠️ EVALUATED AFTER the dict above, which is the point: dict literals
        # are built left to right, and `leader_failures` is appended to while
        # those thirteen lookups run. Put this first and it would report the
        # failures of the PREVIOUS request — always "ok".
        **_leaders_status(),
    }
