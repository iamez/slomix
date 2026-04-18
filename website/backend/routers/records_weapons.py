"""Records sub-router: Weapon stats endpoints."""

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends

from bot.core.season_manager import SeasonManager
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

router = APIRouter()
logger = get_app_logger("api.records.weapons")


@router.get("/stats/weapons")
@handle_router_errors("Database error")
async def get_weapon_stats(
    period: str = "all",
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
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        where_clause += f" AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST(${param_idx} AS TEXT)"
        params.append(start_date)
        param_idx += 1
    elif period == "30d":
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
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

    query = f"""
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
    """
    params.append(limit)

    rows = await db.fetch_all(query, tuple(params))
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


@router.get("/stats/weapons/hall-of-fame")
async def get_weapon_hall_of_fame(
    period: str = "all", db: DatabaseAdapter = Depends(get_db)
):
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
    where_clause = "WHERE weapon_name IS NOT NULL"
    params = []
    param_idx = 1

    if period == "7d":
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        where_clause += f" AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST(${param_idx} AS TEXT)"
        params.append(start_date)
        param_idx += 1
    elif period == "30d":
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        where_clause += f" AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST(${param_idx} AS TEXT)"
        params.append(start_date)
        param_idx += 1
    elif period == "season":
        sm = SeasonManager()
        start_date = sm.get_season_dates()[0].strftime("%Y-%m-%d")
        where_clause += f" AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST(${param_idx} AS TEXT)"
        params.append(start_date)
        param_idx += 1

    weapon_placeholders = ",".join(
        f"${i}" for i in range(param_idx, param_idx + len(hall_weapons))
    )
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
        return {"period": period, "leaders": {}}

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

    return {"period": period, "leaders": leaders}


@router.get("/stats/weapons/by-player")
@router.get("/stats/weapons/by_player")
@handle_router_errors("Database error")
async def get_weapon_stats_by_player(
    period: str = "all",
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
    where_clause = "WHERE weapon_name IS NOT NULL"
    params: list[Any] = []
    param_idx = 1

    # Session-scoped: filter to rounds in the given gaming session
    if gaming_session_id is not None:
        where_clause += (
            f" AND round_id IN ("
            f"SELECT id FROM rounds WHERE gaming_session_id = ${param_idx}"
            f" AND round_number IN (1, 2))"
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
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        where_clause += f" AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST(${param_idx} AS TEXT)"
        params.append(start_date)
        param_idx += 1
    elif period == "30d":
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
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
