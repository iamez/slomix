"""Records sub-router: Weapon stats endpoints."""

from datetime import datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from shared.season_manager import SeasonManager
from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.logging_config import get_app_logger
from website.backend.routers.api_helpers import (
    clean_weapon_name as _clean_weapon_name,
)
from website.backend.routers.api_helpers import (
    handle_router_errors,
    resolve_display_name,
)
from website.backend.routers.api_helpers import (
    normalize_weapon_key as _normalize_weapon_key,
)
from website.backend.services.weapon_stats_mv_refresh import (
    use_weapon_stats_mv_enabled,
)

router = APIRouter()
logger = get_app_logger("api.records.weapons")


class WeaponAggregate(BaseModel):
    """One weapon's line in the overall table.

    ⚠️ Named apart from `WeaponRow` (the per-player row in the same file) on
    purpose: they share five field names and differ in two, and a single class
    covering both would have to widen every field that only one of them has.

    All six are guarded at the source — `int(...)` casts and a `hs_rate` whose
    branch has `else 0.0` — so none is nullable. `weapon_comprehensive_stats`
    declares `weapon_name` NOT NULL, and the handler derives `name` and
    `weapon_key` from it.
    """

    name: str
    weapon_key: str
    kills: int
    #: Headshot HITS, not kills — the column means hits in this table.
    headshots: int
    #: headshots / hits * 100, capped at 100; 0.0 when there were no hits.
    hs_rate: float
    accuracy: float


class WeaponLeader(BaseModel):
    """The top player for one weapon.

    `player_guid` and `player_name` are NOT NULL columns, so they stay
    required — widening them would invite callers to handle a case the schema
    forbids.
    """

    weapon: str
    weapon_key: str
    player_guid: str
    player_name: str
    kills: int
    headshots: int
    accuracy: float


class WeaponsHallOfFame(BaseModel):
    """⛔ THREE STATES: the handler swallows its own exception and answers 200.

    Before this, a failed query and a period with no weapon data both returned
    `{"period": p, "leaders": {}}` — so a client reading `Object.keys(leaders)`
    could not tell a measured emptiness from an unmeasured one. Same shape as
    `/records/maps/segments` and `/stats/activity-calendar`, agreed with the
    workstream that renders them.
    """

    period: str
    #: weapon_key -> its leader. Empty when there is nothing to show; check
    #: `status` to learn which kind of empty.
    leaders: dict[str, WeaponLeader]
    #: 'ok' | 'no_data' | 'unavailable'
    status: str
    #: One short sentence when the state is not `ok`; null otherwise.
    note: str | None = None


class WeaponRow(BaseModel):
    """One weapon's line for one player.

    Types are the union over 125 weapon rows of a live response: `hs_rate` and
    `accuracy` are fractional percentages, the rest are counts. Typing the two
    percentages `int` would truncate them — a schema can corrupt a number as
    easily as it can drop a field.
    """

    name: str
    weapon_key: str
    kills: int
    deaths: int
    headshots: int
    #: Percent, one decimal, already computed by the handler.
    hs_rate: float
    shots: int
    hits: int
    accuracy: float


class PlayerWeapons(BaseModel):
    player_guid: str
    player_name: str
    total_kills: int
    weapons: list[WeaponRow]


class WeaponsByPlayer(BaseModel):
    period: str
    player_count: int
    players: list[PlayerWeapons]


def _looks_like_missing_mv(exc: Exception) -> bool:
    """Detect ``weapon_stats_mv does not exist`` without importing asyncpg."""
    msg = str(exc).lower()
    return "weapon_stats_mv" in msg and ("does not exist" in msg or "undefinedtable" in msg)


# The four values both frontends can produce: the legacy pages
# (data-weapon-period in website/js/) and the SPA (PERIODS in
# WeaponsPage.tsx) offer exactly this set, and "all" is the default in
# both. Before this was a Literal, `period` was a bare `str`: the
# handlers below branch on "7d"/"30d"/"season" and let *everything else*
# fall through to the no-date-filter branch, so `period=nonsense`
# answered 200 with all-time numbers and echoed "nonsense" back as
# though it had been honoured. An ignored parameter is a wrong answer
# that looks like a right one; FastAPI now rejects it with a 422 before
# the handler runs.
WeaponPeriod = Annotated[
    Literal["all", "7d", "30d", "season"],
    Query(description="Time window: all time, last 7/30 days, or the current season."),
]

# ⛔ THE FIFTH SPELLING, and only on /by-player//by_player (Codex P1 on #848).
# The closed set above was measured against both frontends' period pickers —
# and missed a caller that is not a picker: the OLD React session detail
# (whose built bundle IS served) sends `period=session` alongside
# `gaming_session_id`, and this handler itself ASSIGNS `period = "session"`
# whenever a session scope is present and then RETURNS it in the body. So the
# route both accepted and emitted a value its own declared set forbade: the
# request 422'd, and had it not, the response would have carried an
# undeclared value. "session" is a LABEL for a scope given by
# gaming_session_id/session_date, not a time window — sent on its own it
# used to fall through to all-time while echoing "session" back, so the
# handler now refuses that corner instead of lying about it.
WeaponPeriodWithSession = Annotated[
    Literal["all", "7d", "30d", "season", "session"],
    Query(
        description=(
            "Time window, or 'session' — valid only together with "
            "gaming_session_id or session_date, which define the scope."
        )
    ),
]


@router.get("/stats/weapons", response_model=list[WeaponAggregate])
@handle_router_errors("Database error")
async def get_weapon_stats(
    period: WeaponPeriod = "all",
    limit: int = 20,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Get aggregated weapon statistics across all players.
    Returns weapon usage, kills, and accuracy data from weapon_comprehensive_stats table.
    """
    # Calculate start date based on period
    where_clause = "WHERE 1=1"
    params = []
    param_idx = 1

    if period == "7d":
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")  # noqa: DTZ005 naive datetime for date-string arithmetic / SQL date filter / log timestamp display
        where_clause += f" AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST(${param_idx} AS TEXT)"
        params.append(start_date)
        param_idx += 1
    elif period == "30d":
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")  # noqa: DTZ005 naive datetime for date-string arithmetic / SQL date filter / log timestamp display
        where_clause += f" AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST(${param_idx} AS TEXT)"
        params.append(start_date)
        param_idx += 1
    elif period == "season":
        sm = SeasonManager()
        start_date = sm.get_season_dates()[0].strftime("%Y-%m-%d")
        where_clause += f" AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST(${param_idx} AS TEXT)"
        params.append(start_date)
        param_idx += 1
    # else: all time, no date filter

    # nosec B608 — where_clause is built from a fixed period whitelist
    # ("7d"/"30d"/"season" → adds a date filter; anything else → no
    # date filter / "all"). Uses $N parameter placeholders for the only
    # user-derived value (a date string already passed via the params
    # tuple). param_idx is an integer counter for PG positional
    # placeholders, not user input.
    live_query = f"""
        SELECT
            weapon_name,
            SUM(kills) as total_kills,
            SUM(headshots) as total_headshots,
            SUM(shots) as total_shots,
            SUM(hits) as total_hits,
            ROUND((SUM(hits)::numeric / NULLIF(SUM(shots), 0)) * 100, 1) as avg_accuracy
        FROM weapon_comprehensive_stats
        {where_clause}
        GROUP BY weapon_name
        ORDER BY total_kills DESC
        LIMIT ${param_idx}
    """  # nosec B608
    params.append(limit)

    # A8 optimization: serve from the weapon_stats_mv materialized view when
    # the feature flag is on. The MV is grouped by (weapon_name, round_date)
    # so the same date filters apply. Fall back to the live query when the
    # MV is missing (migration 053 not applied yet) or on any error.
    # nosec B608 — same rationale as live_query above.
    mv_query = f"""
        SELECT
            weapon_name,
            SUM(total_kills) as total_kills,
            SUM(total_headshots) as total_headshots,
            SUM(total_shots) as total_shots,
            SUM(total_hits) as total_hits,
            ROUND((SUM(total_hits)::numeric / NULLIF(SUM(total_shots), 0)) * 100, 1) as avg_accuracy
        FROM weapon_stats_mv
        {where_clause}
        GROUP BY weapon_name
        ORDER BY total_kills DESC
        LIMIT ${param_idx}
    """  # nosec B608

    rows = None
    used_mv = False
    if use_weapon_stats_mv_enabled():
        try:
            rows = await db.fetch_all(mv_query, tuple(params))
            used_mv = True
            logger.debug("get_weapon_stats served from weapon_stats_mv")
        except Exception as exc:
            if _looks_like_missing_mv(exc):
                logger.info("weapon_stats_mv not present — falling back to live query")
            else:
                logger.warning(
                    "weapon_stats_mv query failed (%s) — falling back to live query",
                    exc,
                )
            rows = None
    if rows is None:
        rows = await db.fetch_all(live_query, tuple(params))
        if not used_mv:
            logger.debug("get_weapon_stats served from live weapon_comprehensive_stats")
    if not rows:
        return []

    weapons = []
    for row in rows:
        weapon_name = row[0] or "Unknown"
        total_kills = row[1] or 0
        total_headshots = row[2] or 0
        total_hits = row[4] or 0
        avg_accuracy = row[5] or 0

        if total_kills <= 0:
            continue

        # Weapon-level headshot accuracy: headshots / hits * 100
        # headshots in weapon_comprehensive_stats are headshot HITS, not kills.
        hs_rate = min(100, round((total_headshots / total_hits * 100), 1)) if total_hits > 0 else 0.0
        weapons.append(
            {
                "name": _clean_weapon_name(weapon_name),
                "weapon_key": _normalize_weapon_key(weapon_name),
                "kills": int(total_kills),
                "headshots": int(total_headshots),
                "hs_rate": hs_rate,
                "accuracy": round(avg_accuracy, 1),
            }
        )

    return weapons


@router.get("/stats/weapons/hall-of-fame", response_model=WeaponsHallOfFame)
async def get_weapon_hall_of_fame(period: WeaponPeriod = "all", db: DatabaseAdapter = Depends(get_db)):
    """
    Get top player per weapon for Hall of Fame.
    Focuses on iconic weapons (pistols, smgs, rifles, heavy, explosives).
    """
    hall_weapons = [
        "luger",
        "colt",
        "mp40",
        "thompson",
        "sten",
        "fg42",
        "garand",
        "k43",
        "kar98",
        "panzerfaust",
        "mortar",
        "grenade",
    ]

    weapon_key_expr = "REPLACE(REPLACE(LOWER(weapon_name), 'ws_', ''), ' ', '')"
    # Exclude bots (OMNIBOT* guids / [BOT] names) — test artifacts must not hold
    # weapon records or appear in per-player weapon stats (audit 2026-08-13).
    where_clause = (
        "WHERE weapon_name IS NOT NULL AND UPPER(player_guid) NOT LIKE 'OMNIBOT%' AND player_name NOT LIKE '%[BOT]%'"
    )
    params = []
    param_idx = 1

    if period == "7d":
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")  # noqa: DTZ005 naive datetime for date-string arithmetic / SQL date filter / log timestamp display
        where_clause += f" AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST(${param_idx} AS TEXT)"
        params.append(start_date)
        param_idx += 1
    elif period == "30d":
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")  # noqa: DTZ005 naive datetime for date-string arithmetic / SQL date filter / log timestamp display
        where_clause += f" AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST(${param_idx} AS TEXT)"
        params.append(start_date)
        param_idx += 1
    elif period == "season":
        sm = SeasonManager()
        start_date = sm.get_season_dates()[0].strftime("%Y-%m-%d")
        where_clause += f" AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST(${param_idx} AS TEXT)"
        params.append(start_date)
        param_idx += 1

    weapon_placeholders = ",".join(f"${i}" for i in range(param_idx, param_idx + len(hall_weapons)))
    where_clause += f" AND {weapon_key_expr} IN ({weapon_placeholders})"
    params.extend(hall_weapons)

    query = f"""
        SELECT
            {weapon_key_expr} as weapon_key,
            MAX(weapon_name) as weapon_name,
            player_guid,
            MAX(player_name) as player_name,
            SUM(kills) as kills,
            SUM(headshots) as headshots,
            SUM(shots) as shots,
            SUM(hits) as hits,
            ROUND((SUM(hits)::numeric / NULLIF(SUM(shots), 0)) * 100, 1) as avg_accuracy
        FROM weapon_comprehensive_stats
        {where_clause}
        GROUP BY weapon_key, player_guid
    """

    try:
        rows = await db.fetch_all(query, tuple(params))
    except Exception as e:
        logger.error(f"Error fetching weapon hall of fame: {e}")
        return {
            "period": period,
            "leaders": {},
            "status": "unavailable",
            "note": "the hall-of-fame query failed; this is not an empty set",
        }

    leaders = {}
    for row in rows:
        weapon_key = row[0]
        weapon_name = row[1] or weapon_key
        player_guid = row[2]
        fallback_name = row[3] or "Unknown"
        player_name = await resolve_display_name(db, player_guid, fallback_name)
        kills = row[4] or 0
        headshots = row[5] or 0
        shots = row[6] or 0
        hits = row[7] or 0
        accuracy = (hits / shots * 100) if shots else (row[8] or 0)

        current = leaders.get(weapon_key)
        if not current or kills > current["kills"]:
            leaders[weapon_key] = {
                "weapon": _clean_weapon_name(weapon_name),
                "weapon_key": weapon_key,
                "player_guid": player_guid,
                "player_name": player_name,
                "kills": kills,
                "headshots": headshots,
                "accuracy": round(accuracy, 1),
            }

    return {
        "period": period,
        "leaders": leaders,
        "status": "ok" if leaders else "no_data",
        "note": None if leaders else "no weapon data for this period",
    }


# One handler, two spellings, and until now two contracts: the
# underscore route was typed and the hyphen route was not, which meant
# the response_model guarded the path that legacy matches.js calls
# *first* and left the one session-detail.js and the old React client
# call unguarded. Both spellings have live callers (matches.js:379 uses
# the underscore as primary and the hyphen as its fallback), so neither
# can be removed — but a handler may only have one contract, so both
# carry the same model. Measured before the change: the two paths
# already returned byte-identical bodies.
@router.get(
    "/stats/weapons/by-player",
    response_model=WeaponsByPlayer,
    # ⛔ Explicit, because FastAPI derives the id from the function name
    # plus the path and normalises "-" to "_" — so both spellings of
    # this one handler produced the SAME operationId. The spec requires
    # it to be unique, and the generated TypeScript declared the same
    # interface member twice: before both routes carried this model the
    # two declarations DIFFERED (`unknown` against `WeaponsByPlayer`)
    # and the compiler silently kept one of them, so a caller could be
    # typed by the route it was not calling.
    operation_id="get_weapon_stats_by_player_hyphen_alias",
)
@router.get("/stats/weapons/by_player", response_model=WeaponsByPlayer)
@handle_router_errors("Database error")
async def get_weapon_stats_by_player(
    period: WeaponPeriodWithSession = "all",
    player_limit: int = 25,
    weapon_limit: int = 5,
    player_guid: str | None = None,
    gaming_session_id: int | None = None,
    session_date: str | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Return per-player weapon stats keyed by player GUID.
    Useful for comprehensive weapon mastery views.
    """
    if period == "session" and gaming_session_id is None and not session_date:
        # Without a scope there is no session to label: this exact shape used
        # to fall through to the all-time branch and echo "session" back — an
        # answer wearing the name of a scope nobody supplied.
        raise HTTPException(
            status_code=422,
            detail="period=session needs gaming_session_id or session_date",
        )
    # Exclude bots (OMNIBOT* guids / [BOT] names) — test artifacts must not hold
    # weapon records or appear in per-player weapon stats (audit 2026-08-13).
    where_clause = (
        "WHERE weapon_name IS NOT NULL AND UPPER(player_guid) NOT LIKE 'OMNIBOT%' AND player_name NOT LIKE '%[BOT]%'"
    )
    params: list[Any] = []
    param_idx = 1

    # Session-scoped: filter to rounds in the given gaming session
    if gaming_session_id is not None:
        # The same counted-round predicate as the session detail's totals
        # (sessions_router): a cancelled round's weapon events must not show
        # up under a player whose totals row excludes them (Codex on #855).
        where_clause += (
            f" AND round_id IN ("
            f"SELECT id FROM rounds WHERE gaming_session_id = ${param_idx}"
            f" AND round_number IN (1, 2)"
            f" AND is_valid IS DISTINCT FROM FALSE"
            f" AND is_bot_round IS DISTINCT FROM TRUE"
            f" AND (round_status IN ('completed', 'substitution')"
            f" OR round_status IS NULL))"
        )
        params.append(gaming_session_id)
        param_idx += 1
        period = "session"
    elif session_date:
        where_clause += f" AND CAST(round_date AS TEXT) = ${param_idx}"
        params.append(session_date)
        param_idx += 1
        period = "session"
    elif period == "7d":
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")  # noqa: DTZ005 naive datetime for date-string arithmetic / SQL date filter / log timestamp display
        where_clause += f" AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST(${param_idx} AS TEXT)"
        params.append(start_date)
        param_idx += 1
    elif period == "30d":
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")  # noqa: DTZ005 naive datetime for date-string arithmetic / SQL date filter / log timestamp display
        where_clause += f" AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST(${param_idx} AS TEXT)"
        params.append(start_date)
        param_idx += 1
    elif period == "season":
        sm = SeasonManager()
        start_date = sm.get_season_dates()[0].strftime("%Y-%m-%d")
        where_clause += f" AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST(${param_idx} AS TEXT)"
        params.append(start_date)
        param_idx += 1

    if player_guid:
        # Match both 8-char (legacy) and 32-char (canonical) GUIDs via prefix
        guid_prefix = player_guid.strip()[:8]
        where_clause += f" AND LEFT(player_guid, 8) = ${param_idx}"
        params.append(guid_prefix)
        param_idx += 1

    query = f"""
        SELECT
            player_guid,
            MAX(player_name) AS player_name,
            weapon_name,
            SUM(kills) AS total_kills,
            SUM(deaths) AS total_deaths,
            SUM(headshots) AS total_headshots,
            SUM(shots) AS total_shots,
            SUM(hits) AS total_hits,
            ROUND((SUM(hits)::numeric / NULLIF(SUM(shots), 0)) * 100, 1) AS avg_accuracy
        FROM weapon_comprehensive_stats
        {where_clause}
        GROUP BY player_guid, weapon_name
        HAVING SUM(kills) > 0 OR SUM(hits) > 0 OR SUM(deaths) > 0
        ORDER BY player_guid, total_kills DESC, total_hits DESC
    """

    rows = await db.fetch_all(query, tuple(params))
    players: dict[str, dict[str, Any]] = {}
    for row in rows:
        guid = row[0]
        if not guid:
            continue
        if guid not in players:
            players[guid] = {
                "player_guid": guid,
                "player_name": row[1] or "Unknown",
                "total_kills": 0,
                "weapons": [],
            }

        kills = int(row[3] or 0)
        deaths = int(row[4] or 0)
        headshots = int(row[5] or 0)
        shots = int(row[6] or 0)
        hits = int(row[7] or 0)
        avg_accuracy = float(row[8] or 0)
        hs_rate = round((headshots / hits) * 100, 1) if hits > 0 else 0.0

        players[guid]["total_kills"] += kills
        players[guid]["weapons"].append(
            {
                "name": _clean_weapon_name(row[2]),
                "weapon_key": _normalize_weapon_key(row[2]),
                "kills": kills,
                "deaths": deaths,
                "headshots": headshots,
                "hs_rate": min(100.0, hs_rate),
                "shots": shots,
                "hits": hits,
                "accuracy": round(avg_accuracy, 1),
            }
        )

    ranked_players = sorted(
        players.values(),
        key=lambda p: p["total_kills"],
        reverse=True,
    )

    if player_limit > 0:
        ranked_players = ranked_players[:player_limit]
    for player in ranked_players:
        player["weapons"] = player["weapons"][: max(1, weapon_limit)]

    return {
        "period": period,
        "player_count": len(ranked_players),
        "players": ranked_players,
    }
