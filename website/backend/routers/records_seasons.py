"""Records sub-router: Season endpoints."""

from fastapi import APIRouter, Depends

from bot.core.season_manager import SeasonManager
from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.logging_config import get_app_logger
from website.backend.routers.api_helpers import resolve_display_name

router = APIRouter()
logger = get_app_logger("api.records.seasons")


@router.get("/seasons/current")
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


@router.get("/seasons/current/summary")
async def get_current_season_summary(db: DatabaseAdapter = Depends(get_db)):
    """
    Summary stats for the current season (totals + activity).
    """
    sm = SeasonManager()
    current_id = sm.get_current_season()
    start_date, end_date = sm.get_season_dates(current_id)
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    async def safe_val(query: str, params: tuple | None = None, default=0):
        try:
            return await db.fetch_val(query, params)
        except Exception as e:
            logger.error(f"[season_summary] query failed: {e}")
            return default

    async def safe_one(query: str, params: tuple | None = None):
        try:
            return await db.fetch_one(query, params)
        except Exception as e:
            logger.error(f"[season_summary] query failed: {e}")
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
            WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
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
            WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            """,
            (start_str, end_str),
        )
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
        )
        active_days = await safe_val(
            """
            SELECT COUNT(DISTINCT SUBSTR(CAST(round_date AS TEXT), 1, 10))
            FROM rounds
            WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            """,
            (start_str, end_str),
            default=None,
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
        )
        players_count = await safe_val(
            """
            SELECT COUNT(DISTINCT player_guid)
            FROM player_comprehensive_stats
            WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            """,
            (start_str, end_str),
        )
        kills_total = await safe_val(
            """
            SELECT COALESCE(SUM(kills), 0)
            FROM player_comprehensive_stats
            WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            """,
            (start_str, end_str),
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
    }


@router.get("/seasons/current/leaders")
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
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
        GROUP BY player_guid
        ORDER BY total_damage DESC
        LIMIT 1
    """
    dmg_recv_query = """
        SELECT player_guid, MAX(player_name) as player_name, SUM(damage_received) as total_damage
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
        GROUP BY player_guid
        ORDER BY total_damage DESC
        LIMIT 1
    """
    team_dmg_query = """
        SELECT player_guid, MAX(player_name) as player_name, SUM(team_damage_given) as total_team_damage
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
        GROUP BY player_guid
        ORDER BY total_team_damage DESC
        LIMIT 1
    """
    fallback_team_dmg = """
        SELECT player_guid, MAX(player_name) as player_name, SUM(team_damage_given) as total_team_damage
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
        GROUP BY player_guid
        ORDER BY total_team_damage DESC
        LIMIT 1
    """
    revives_query = """
        SELECT player_guid, MAX(player_name) as player_name, SUM(revives_given) as total_revives
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
        GROUP BY player_guid
        ORDER BY total_revives DESC
        LIMIT 1
    """
    deaths_query = """
        SELECT player_guid, MAX(player_name) as player_name, SUM(deaths) as total_deaths
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
        GROUP BY player_guid
        ORDER BY total_deaths DESC
        LIMIT 1
    """
    gibs_query = """
        SELECT player_guid, MAX(player_name) as player_name, SUM(gibs) as total_gibs
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
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
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
        GROUP BY player_guid
        ORDER BY total_objectives DESC
        LIMIT 1
    """
    xp_query = """
        SELECT player_guid, MAX(player_name) as player_name, SUM(xp) as total_xp
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
        GROUP BY player_guid
        ORDER BY total_xp DESC
        LIMIT 1
    """
    kills_query = """
        SELECT player_guid, MAX(player_name) as player_name, SUM(kills) as total_kills
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
        GROUP BY player_guid
        ORDER BY total_kills DESC
        LIMIT 1
    """
    dpm_query = """
        SELECT player_guid, MAX(player_name) as player_name,
               ROUND((SUM(damage_given)::numeric / NULLIF(SUM(time_played_seconds), 0) * 60), 1) as dpm
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
        GROUP BY player_guid
        HAVING SUM(time_played_seconds) > 600
        ORDER BY dpm DESC
        LIMIT 1
    """
    time_alive_query = """
        SELECT player_guid, MAX(player_name) as player_name,
               SUM(time_played_seconds) - SUM(COALESCE(time_dead_minutes, 0) * 60) as time_alive_seconds
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
        GROUP BY player_guid
        ORDER BY time_alive_seconds DESC
        LIMIT 1
    """
    fallback_time_alive = """
        SELECT player_guid, MAX(player_name) as player_name,
               SUM(time_played_seconds) as time_alive_seconds
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
        GROUP BY player_guid
        ORDER BY time_alive_seconds DESC
        LIMIT 1
    """
    time_dead_query = """
        SELECT player_guid, MAX(player_name) as player_name,
               SUM(COALESCE(time_dead_minutes, 0)) as time_dead_minutes
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
        GROUP BY player_guid
        ORDER BY time_dead_minutes DESC
        LIMIT 1
    """
    fallback_time_dead = """
        SELECT player_guid, MAX(player_name) as player_name,
               SUM(COALESCE(time_dead_minutes, 0)) as time_dead_minutes
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
        GROUP BY player_guid
        ORDER BY time_dead_minutes DESC
        LIMIT 1
    """
    session_query = """
        SELECT gaming_session_id, COUNT(*) as round_count, MIN(round_date) as session_date
        FROM rounds
        WHERE round_number IN (1, 2) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(round_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
        GROUP BY gaming_session_id
        ORDER BY round_count DESC
        LIMIT 1
    """

    def _swap_date_field(query: str, date_field: str) -> str:
        return query.replace("round_date", date_field)

    async def _fetch_one_with_field(query: str, date_field: str):
        try:
            return await db.fetch_one(
                _swap_date_field(query, date_field),
                (start_date_str, end_date_str),
            )
        except Exception:
            logger.debug("DB query failed for date_field=%s", date_field, exc_info=True)
            return None

    async def _fetch_one_with_fallback(query: str):
        return await _fetch_one_with_field(query, "round_date")

    async def fetch_leaders():
        dmg_given = await _fetch_one_with_fallback(dmg_given_query)
        dmg_recv = await _fetch_one_with_fallback(dmg_recv_query)
        team_dmg = await _fetch_one_with_fallback(team_dmg_query)
        if team_dmg is None:
            team_dmg = await _fetch_one_with_fallback(fallback_team_dmg)
        revives = await _fetch_one_with_fallback(revives_query)
        deaths = await _fetch_one_with_fallback(deaths_query)
        gibs = await _fetch_one_with_fallback(gibs_query)
        objectives = await _fetch_one_with_fallback(objectives_query)
        xp = await _fetch_one_with_fallback(xp_query)
        kills = await _fetch_one_with_fallback(kills_query)
        dpm = await _fetch_one_with_fallback(dpm_query)
        time_alive = await _fetch_one_with_fallback(time_alive_query)
        if time_alive is None:
            time_alive = await _fetch_one_with_fallback(fallback_time_alive)
        time_dead = await _fetch_one_with_fallback(time_dead_query)
        if time_dead is None:
            time_dead = await _fetch_one_with_fallback(fallback_time_dead)
        session = await _fetch_one_with_field(session_query, "round_date")
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
        }
    }
