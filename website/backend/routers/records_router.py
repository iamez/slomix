"""
Records, awards, maps, weapons, overview, seasons, trends, and other reference data endpoints.

Extracted from api.py to reduce file size and improve maintainability.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from bot.core.season_manager import SeasonManager
from bot.core.utils import escape_like_pattern
from website.backend.logging_config import get_app_logger
from website.backend.routers.api_helpers import (
    normalize_weapon_key as _normalize_weapon_key,
    clean_weapon_name as _clean_weapon_name,
    normalize_map_name as _normalize_map_name,
    resolve_player_guid,
    resolve_display_name,
    resolve_alias_guid_map,
    resolve_name_guid_map,
)

router = APIRouter()
logger = get_app_logger("api.records")


@router.get("/stats/overview")
async def get_stats_overview(db: DatabaseAdapter = Depends(get_db)):
    """Get homepage overview statistics"""
    lookback_days = 14
    start_date_str = (
        (datetime.now() - timedelta(days=lookback_days))
        .date()
        .strftime("%Y-%m-%d")
    )

    async def safe_val(query: str, params: Optional[tuple] = None, default=0):
        try:
            return await db.fetch_val(query, params)
        except Exception as e:
            logger.warning("[overview] query failed: %s", e)
            return default

    async def safe_one(query: str, params: Optional[tuple] = None):
        try:
            return await db.fetch_one(query, params)
        except Exception as e:
            logger.warning("[overview] query failed: %s", e)
            return None

    # Use only legal rounds (completed or pre-status rows) and only R1/R2
    round_filter = """
        WHERE round_number IN (1, 2)
          AND (round_status IN ('completed', 'substitution') OR round_status IS NULL)
    """
    round_filter_fallback = """
        WHERE round_number IN (1, 2)
    """

    rounds_table_exists = await safe_val(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_name = 'rounds'
        )
        """,
        default=False,
    )
    sessions_table_exists = await safe_val(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_name = 'gaming_sessions'
        )
        """,
        default=False,
    )

    if rounds_table_exists:
        # Round-based metrics (try with round_status first, fallback without)
        try:
            rounds_count = await db.fetch_val(
                f"SELECT COUNT(*) FROM rounds {round_filter}"
            )
            rounds_first = await db.fetch_val(
                f"SELECT MIN(SUBSTR(CAST(round_date AS TEXT), 1, 10)) FROM rounds {round_filter}"
            )
            rounds_latest = await db.fetch_val(
                f"SELECT MAX(SUBSTR(CAST(round_date AS TEXT), 1, 10)) FROM rounds {round_filter}"
            )
            rounds_recent = await db.fetch_val(
                f"""
                SELECT COUNT(*)
                FROM rounds
                {round_filter}
                  AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
                """,
                (start_date_str,),
            )
            sessions_count = await db.fetch_val(
                f"""
                SELECT COUNT(DISTINCT gaming_session_id)
                FROM rounds
                {round_filter}
                  AND gaming_session_id IS NOT NULL
                """
            )
            sessions_recent = await db.fetch_val(
                f"""
                SELECT COUNT(DISTINCT gaming_session_id)
                FROM rounds
                {round_filter}
                  AND gaming_session_id IS NOT NULL
                  AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
                """,
                (start_date_str,),
            )
        except Exception as e:
            logger.warning("round_status filter failed, retrying fallback: %s", e)
            rounds_count = await safe_val(
                f"SELECT COUNT(*) FROM rounds {round_filter_fallback}"
            )
            rounds_first = await safe_val(
                f"SELECT MIN(SUBSTR(CAST(round_date AS TEXT), 1, 10)) FROM rounds {round_filter_fallback}",
                default=None,
            )
            rounds_latest = await safe_val(
                f"SELECT MAX(SUBSTR(CAST(round_date AS TEXT), 1, 10)) FROM rounds {round_filter_fallback}",
                default=None,
            )
            rounds_recent = await safe_val(
                f"""
                SELECT COUNT(*)
                FROM rounds
                {round_filter_fallback}
                  AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
                """,
                (start_date_str,),
            )
            sessions_count = await safe_val(
                f"""
                SELECT COUNT(DISTINCT gaming_session_id)
                FROM rounds
                {round_filter_fallback}
                  AND gaming_session_id IS NOT NULL
                """
            )
            sessions_recent = await safe_val(
                f"""
                SELECT COUNT(DISTINCT gaming_session_id)
                FROM rounds
                {round_filter_fallback}
                  AND gaming_session_id IS NOT NULL
                  AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
                """,
                (start_date_str,),
            )
    if (rounds_count or 0) == 0 and sessions_table_exists:
        # If rounds table exists but is empty, fall back to sessions table
        rounds_count = await safe_val(
            """
            SELECT COUNT(*)
            FROM sessions
            WHERE round_number IN (1, 2)
            """
        )
        rounds_first = await safe_val(
            """
            SELECT MIN(SUBSTR(CAST(session_date AS TEXT), 1, 10))
            FROM sessions
            WHERE round_number IN (1, 2)
            """,
            default=None,
        )
        rounds_latest = await safe_val(
            """
            SELECT MAX(SUBSTR(CAST(session_date AS TEXT), 1, 10))
            FROM sessions
            WHERE round_number IN (1, 2)
            """,
            default=None,
        )
        rounds_recent = await safe_val(
            """
            SELECT COUNT(*)
            FROM sessions
            WHERE round_number IN (1, 2)
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
            """,
            (start_date_str,),
        )
        try:
            sessions_count = await db.fetch_val(
                """
                SELECT COUNT(DISTINCT session_id)
                FROM sessions
                WHERE session_id IS NOT NULL
                """
            )
        except Exception:
            sessions_count = await safe_val(
                """
                SELECT COUNT(DISTINCT match_id)
                FROM sessions
                WHERE match_id IS NOT NULL
                """
            )
        try:
            sessions_recent = await db.fetch_val(
                """
                SELECT COUNT(DISTINCT session_id)
                FROM sessions
                WHERE session_id IS NOT NULL
                  AND SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
                """,
                (start_date_str,),
            )
        except Exception:
            sessions_recent = await safe_val(
                """
                SELECT COUNT(DISTINCT match_id)
                FROM sessions
                WHERE match_id IS NOT NULL
                  AND SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
                """,
                (start_date_str,),
            )
    elif not rounds_table_exists:
        rounds_count = await safe_val(
            """
            SELECT COUNT(*)
            FROM sessions
            WHERE round_number IN (1, 2)
            """
        )
        rounds_first = await safe_val(
            """
            SELECT MIN(SUBSTR(CAST(session_date AS TEXT), 1, 10))
            FROM sessions
            WHERE round_number IN (1, 2)
            """,
            default=None,
        )
        rounds_latest = await safe_val(
            """
            SELECT MAX(SUBSTR(CAST(session_date AS TEXT), 1, 10))
            FROM sessions
            WHERE round_number IN (1, 2)
            """,
            default=None,
        )
        rounds_recent = await safe_val(
            """
            SELECT COUNT(*)
            FROM sessions
            WHERE round_number IN (1, 2)
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
            """,
            (start_date_str,),
        )
        try:
            sessions_count = await db.fetch_val(
                """
                SELECT COUNT(DISTINCT session_id)
                FROM sessions
                WHERE session_id IS NOT NULL
                """
            )
        except Exception:
            sessions_count = await safe_val(
                """
                SELECT COUNT(DISTINCT match_id)
                FROM sessions
                WHERE match_id IS NOT NULL
                """
            )
        try:
            sessions_recent = await db.fetch_val(
                """
                SELECT COUNT(DISTINCT session_id)
                FROM sessions
                WHERE session_id IS NOT NULL
                  AND SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
                """,
                (start_date_str,),
            )
        except Exception:
            sessions_recent = await safe_val(
                """
                SELECT COUNT(DISTINCT match_id)
                FROM sessions
                WHERE match_id IS NOT NULL
                  AND SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
                """,
                (start_date_str,),
            )

    # Player + kill metrics from stats table
    players_all_time = await safe_val(
        """
        SELECT COUNT(DISTINCT player_guid)
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2)
          AND time_played_seconds > 0
        """
    )
    try:
        players_recent = await db.fetch_val(
            """
            SELECT COUNT(DISTINCT player_guid)
            FROM player_comprehensive_stats
            WHERE round_number IN (1, 2)
              AND time_played_seconds > 0
              AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
            """,
            (start_date_str,),
        )
    except Exception:
        players_recent = await safe_val(
            """
            SELECT COUNT(DISTINCT player_guid)
            FROM player_comprehensive_stats
            WHERE round_number IN (1, 2)
              AND time_played_seconds > 0
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
            """,
            (start_date_str,),
        )
    if players_recent == 0:
        players_recent = await safe_val(
            """
            SELECT COUNT(DISTINCT player_guid)
            FROM player_comprehensive_stats
            WHERE round_number IN (1, 2)
              AND time_played_seconds > 0
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
            """,
            (start_date_str,),
        )
    total_kills = await safe_val(
        """
        SELECT COALESCE(SUM(kills), 0)
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2)
        """
    )
    try:
        total_kills_recent = await db.fetch_val(
            """
            SELECT COALESCE(SUM(kills), 0)
            FROM player_comprehensive_stats
            WHERE round_number IN (1, 2)
              AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
            """,
            (start_date_str,),
        )
    except Exception:
        total_kills_recent = await safe_val(
            """
            SELECT COALESCE(SUM(kills), 0)
            FROM player_comprehensive_stats
            WHERE round_number IN (1, 2)
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
            """,
            (start_date_str,),
        )
    if total_kills_recent == 0:
        total_kills_recent = await safe_val(
            """
            SELECT COALESCE(SUM(kills), 0)
            FROM player_comprehensive_stats
            WHERE round_number IN (1, 2)
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
            """,
            (start_date_str,),
        )

    # Most active players (by rounds played)
    active_overall = await safe_one(
        """
        SELECT player_guid,
               MAX(player_name) as player_name,
               COUNT(DISTINCT round_id) as rounds_played
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2)
          AND time_played_seconds > 0
        GROUP BY player_guid
        ORDER BY rounds_played DESC
        LIMIT 1
        """
    )
    if active_overall is None:
        active_overall = await safe_one(
            """
            SELECT player_guid,
                   MAX(player_name) as player_name,
                   COUNT(*) as rounds_played
            FROM player_comprehensive_stats
            WHERE round_number IN (1, 2)
              AND time_played_seconds > 0
            GROUP BY player_guid
            ORDER BY rounds_played DESC
            LIMIT 1
            """
        )

    try:
        active_recent = await db.fetch_one(
            """
            SELECT player_guid,
                   MAX(player_name) as player_name,
                   COUNT(DISTINCT round_id) as rounds_played
            FROM player_comprehensive_stats
            WHERE round_number IN (1, 2)
              AND time_played_seconds > 0
              AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
            GROUP BY player_guid
            ORDER BY rounds_played DESC
            LIMIT 1
            """,
            (start_date_str,),
        )
    except Exception:
        active_recent = await safe_one(
            """
            SELECT player_guid,
                   MAX(player_name) as player_name,
                   COUNT(DISTINCT round_id) as rounds_played
            FROM player_comprehensive_stats
            WHERE round_number IN (1, 2)
              AND time_played_seconds > 0
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
            GROUP BY player_guid
            ORDER BY rounds_played DESC
            LIMIT 1
            """,
            (start_date_str,),
        )
    if active_recent is None:
        active_recent = await safe_one(
            """
            SELECT player_guid,
                   MAX(player_name) as player_name,
                   COUNT(*) as rounds_played
            FROM player_comprehensive_stats
            WHERE round_number IN (1, 2)
              AND time_played_seconds > 0
              AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
            GROUP BY player_guid
            ORDER BY rounds_played DESC
            LIMIT 1
            """,
            (start_date_str,),
        )
    if active_recent is None:
        active_recent = await safe_one(
            """
            SELECT player_guid,
                   MAX(player_name) as player_name,
                   COUNT(*) as rounds_played
            FROM player_comprehensive_stats
            WHERE round_number IN (1, 2)
              AND time_played_seconds > 0
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
            GROUP BY player_guid
            ORDER BY rounds_played DESC
            LIMIT 1
            """,
            (start_date_str,),
        )
    if active_recent is None:
        active_recent = await safe_one(
            """
            SELECT player_guid,
                   MAX(player_name) as player_name,
                   COUNT(*) as rounds_played
            FROM player_comprehensive_stats
            WHERE round_number IN (1, 2)
              AND time_played_seconds > 0
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
            GROUP BY player_guid
            ORDER BY rounds_played DESC
            LIMIT 1
            """,
            (start_date_str,),
        )

    active_overall_payload = None
    if active_overall:
        active_overall_payload = {
            "name": await resolve_display_name(db, active_overall[0], active_overall[1] or "Unknown"),
            "rounds": active_overall[2],
        }
    active_recent_payload = None
    if active_recent:
        active_recent_payload = {
            "name": await resolve_display_name(db, active_recent[0], active_recent[1] or "Unknown"),
            "rounds": active_recent[2],
        }

    return {
        "rounds": rounds_count or 0,
        "players": players_recent or 0,
        "sessions": sessions_count or 0,
        "total_kills": total_kills or 0,
        "rounds_since": rounds_first,
        "rounds_latest": rounds_latest,
        "rounds_14d": rounds_recent or 0,
        "players_all_time": players_all_time or 0,
        "players_14d": players_recent or 0,
        "sessions_14d": sessions_recent or 0,
        "total_kills_14d": total_kills_recent or 0,
        "most_active_overall": active_overall_payload,
        "most_active_14d": active_recent_payload,
        "window_days": lookback_days,
    }


@router.get("/stats/activity-calendar")
async def get_activity_calendar(
    days: int = 90,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Return a simple activity calendar (rounds per day) for the last N days.
    """
    lookback_days = max(1, min(days, 365))
    start_date = (datetime.now() - timedelta(days=lookback_days)).date().strftime(
        "%Y-%m-%d"
    )

    query = """
        SELECT SUBSTR(CAST(round_date AS TEXT), 1, 10) as day, COUNT(*) as rounds
        FROM rounds
        WHERE round_number IN (1, 2)
          AND (round_status IN ('completed', 'substitution') OR round_status IS NULL)
          AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
        GROUP BY SUBSTR(CAST(round_date AS TEXT), 1, 10)
        ORDER BY day
    """

    try:
        rows = await db.fetch_all(query, (start_date,))
    except Exception:
        rows = []

    if not rows:
        # Fallback for legacy SQLite schema (sessions table)
        fallback = """
            SELECT SUBSTR(CAST(session_date AS TEXT), 1, 10) as day, COUNT(*) as rounds
            FROM sessions
            WHERE round_number IN (1, 2)
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
            GROUP BY SUBSTR(CAST(session_date AS TEXT), 1, 10)
            ORDER BY day
        """
        try:
            rows = await db.fetch_all(fallback, (start_date,))
        except Exception:
            # If legacy table doesn't exist, return empty activity
            return {"days": lookback_days, "activity": {}}

    activity = {str(row[0]): int(row[1]) for row in rows}
    return {"days": lookback_days, "activity": activity}


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

    async def safe_val(query: str, params: Optional[tuple] = None, default=0):
        try:
            return await db.fetch_val(query, params)
        except Exception as e:
            logger.error(f"[season_summary] query failed: {e}")
            return default

    async def safe_one(query: str, params: Optional[tuple] = None):
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

        if rounds_count is None and sessions_count is None:
            # Fallback for legacy SQLite schema (sessions table)
            rounds_count = await safe_val(
                """
                SELECT COUNT(*)
                FROM sessions
                WHERE round_number IN (1, 2)
                  AND SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(session_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
                """,
                (start_str, end_str),
            )
            players_count = await safe_val(
                """
                SELECT COUNT(DISTINCT player_guid)
                FROM player_comprehensive_stats
                WHERE SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(session_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
                """,
                (start_str, end_str),
            )
            sessions_count = await safe_val(
                """
                SELECT COUNT(DISTINCT session_id)
                FROM sessions
                WHERE SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(session_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
                """,
                (start_str, end_str),
            )
            maps_count = await safe_val(
                """
                SELECT COUNT(DISTINCT map_name)
                FROM sessions
                WHERE map_name IS NOT NULL
                  AND SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(session_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
                """,
                (start_str, end_str),
            )
            kills_total = await safe_val(
                """
                SELECT COALESCE(SUM(kills), 0)
                FROM player_comprehensive_stats
                WHERE SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(session_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
                """,
                (start_str, end_str),
            )
            active_days = await safe_val(
                """
                SELECT COUNT(DISTINCT SUBSTR(CAST(session_date AS TEXT), 1, 10))
                FROM sessions
                WHERE SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(session_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
                """,
                (start_str, end_str),
            )
            top_map_row = await safe_one(
                """
                SELECT map_name, COUNT(*) as plays
                FROM sessions
                WHERE map_name IS NOT NULL
                  AND SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT) AND SUBSTR(CAST(session_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
                GROUP BY map_name
                ORDER BY plays DESC
                LIMIT 1
                """,
                (start_str, end_str),
            )

    # If rounds exist but player stats use session_date, retry with session_date
    if rounds_count and (players_count is None or players_count == 0):
        players_count = await safe_val(
            """
            SELECT COUNT(DISTINCT player_guid)
            FROM player_comprehensive_stats
            WHERE SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            """,
            (start_str, end_str),
        )

    if rounds_count and (kills_total is None or kills_total == 0):
        kills_total = await safe_val(
            """
            SELECT COALESCE(SUM(kills), 0)
            FROM player_comprehensive_stats
            WHERE SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            """,
            (start_str, end_str),
        )

    # If rounds data is empty, try sessions table as a last resort
    if (rounds_count or 0) == 0 and (sessions_count or 0) == 0:
        rounds_count = await safe_val(
            """
            SELECT COUNT(*)
            FROM sessions
            WHERE round_number IN (1, 2)
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            """,
            (start_str, end_str),
        )
        players_count = await safe_val(
            """
            SELECT COUNT(DISTINCT player_guid)
            FROM player_comprehensive_stats
            WHERE SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            """,
            (start_str, end_str),
        )
        sessions_count = await safe_val(
            """
            SELECT COUNT(DISTINCT session_id)
            FROM sessions
            WHERE SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            """,
            (start_str, end_str),
        )
        maps_count = await safe_val(
            """
            SELECT COUNT(DISTINCT map_name)
            FROM sessions
            WHERE map_name IS NOT NULL
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            """,
            (start_str, end_str),
        )
        kills_total = await safe_val(
            """
            SELECT COALESCE(SUM(kills), 0)
            FROM player_comprehensive_stats
            WHERE SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            """,
            (start_str, end_str),
        )
        active_days = await safe_val(
            """
            SELECT COUNT(DISTINCT SUBSTR(CAST(session_date AS TEXT), 1, 10))
            FROM sessions
            WHERE SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            """,
            (start_str, end_str),
        )
        top_map_row = await safe_one(
            """
            SELECT map_name, COUNT(*) as plays
            FROM sessions
            WHERE map_name IS NOT NULL
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
              AND SUBSTR(CAST(session_date AS TEXT), 1, 10) <= CAST($2 AS TEXT)
            GROUP BY map_name
            ORDER BY plays DESC
            LIMIT 1
            """,
            (start_str, end_str),
        )

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


@router.get("/stats/maps")
async def get_maps(db: DatabaseAdapter = Depends(get_db)):
    """
    Get comprehensive statistics for all maps.
    Returns times played, win rates, kill stats, etc.
    Note: In stopwatch mode, 2 rounds = 1 match.
    """
    query = """
        WITH map_stats AS (
            SELECT
                r.map_name,
                COUNT(*) as total_rounds,
                COUNT(*) / 2 as matches_played,
                SUM(CASE WHEN r.winner_team = 1 THEN 1 ELSE 0 END) as allies_wins,
                SUM(CASE WHEN r.winner_team = 2 THEN 1 ELSE 0 END) as axis_wins,
                MAX(SUBSTR(CAST(r.round_date AS TEXT), 1, 10)) as last_played,
                -- Parse M:SS format to seconds, then avg/min/max
                AVG(
                    CASE
                        WHEN r.actual_time ~ '^[0-9]+:[0-9]+$' THEN
                            SPLIT_PART(r.actual_time, ':', 1)::int * 60 +
                            SPLIT_PART(r.actual_time, ':', 2)::int
                        ELSE NULL
                    END
                ) as avg_duration,
                MIN(
                    CASE
                        WHEN r.actual_time ~ '^[0-9]+:[0-9]+$' THEN
                            SPLIT_PART(r.actual_time, ':', 1)::int * 60 +
                            SPLIT_PART(r.actual_time, ':', 2)::int
                        ELSE NULL
                    END
                ) as min_duration,
                MAX(
                    CASE
                        WHEN r.actual_time ~ '^[0-9]+:[0-9]+$' THEN
                            SPLIT_PART(r.actual_time, ':', 1)::int * 60 +
                            SPLIT_PART(r.actual_time, ':', 2)::int
                        ELSE NULL
                    END
                ) as max_duration
            FROM rounds r
            WHERE r.map_name IS NOT NULL
              AND r.round_number IN (1, 2)
            GROUP BY r.map_name
        ),
        player_stats AS (
            SELECT
                p.map_name,
                SUM(p.kills) as total_kills,
                SUM(p.deaths) as total_deaths,
                AVG(p.dpm) as avg_dpm,
                COUNT(DISTINCT p.player_guid) as unique_players
            FROM player_comprehensive_stats p
            WHERE p.map_name IS NOT NULL AND p.time_played_seconds > 0
              AND p.round_number IN (1, 2)
            GROUP BY p.map_name
        ),
        weapon_stats AS (
            SELECT
                w.map_name,
                SUM(CASE WHEN LOWER(w.weapon_name) LIKE '%grenade%' AND LOWER(w.weapon_name) NOT LIKE '%smoke%' THEN w.kills ELSE 0 END) as grenade_kills,
                SUM(CASE WHEN LOWER(w.weapon_name) LIKE '%panzer%' THEN w.kills ELSE 0 END) as panzer_kills,
                SUM(CASE WHEN LOWER(w.weapon_name) LIKE '%mortar%' THEN w.kills ELSE 0 END) as mortar_kills
            FROM weapon_comprehensive_stats w
            WHERE w.map_name IS NOT NULL
              AND w.round_number IN (1, 2)
            GROUP BY w.map_name
        )
        SELECT
            m.map_name,
            m.total_rounds,
            m.matches_played,
            m.allies_wins,
            m.axis_wins,
            m.avg_duration,
            m.min_duration,
            m.max_duration,
            m.last_played,
            p.total_kills,
            p.total_deaths,
            p.avg_dpm,
            p.unique_players,
            w.grenade_kills,
            w.panzer_kills,
            w.mortar_kills
        FROM map_stats m
        LEFT JOIN player_stats p ON m.map_name = p.map_name
        LEFT JOIN weapon_stats w ON m.map_name = w.map_name
        ORDER BY m.matches_played DESC
    """
    try:
        rows = await db.fetch_all(query)

        maps = []
        for row in rows:
            total_rounds = row[1] or 0
            allies_wins = row[3] or 0
            axis_wins = row[4] or 0
            total_games = allies_wins + axis_wins

            allies_win_rate = (
                round((allies_wins / total_games * 100), 1) if total_games > 0 else 50
            )
            axis_win_rate = (
                round((axis_wins / total_games * 100), 1) if total_games > 0 else 50
            )

            maps.append(
                {
                    "name": row[0],
                    "total_rounds": total_rounds,
                    "matches_played": row[2] or total_rounds // 2,
                    "allies_wins": allies_wins,
                    "axis_wins": axis_wins,
                    "allies_win_rate": allies_win_rate,
                    "axis_win_rate": axis_win_rate,
                    "avg_duration": int(row[5]) if row[5] else 0,
                    "min_duration": int(row[6]) if row[6] else 0,
                    "max_duration": int(row[7]) if row[7] else 0,
                    "last_played": row[8],
                    "total_kills": row[9] or 0,
                    "total_deaths": row[10] or 0,
                    "avg_dpm": round(row[11], 1) if row[11] else 0,
                    "unique_players": row[12] or 0,
                    "grenade_kills": row[13] or 0,
                    "panzer_kills": row[14] or 0,
                    "mortar_kills": row[15] or 0,
                }
            )

        return maps
    except Exception as e:
        logger.error(f"Error fetching map stats: {e}")
        return []


@router.get("/stats/weapons")
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
            AVG(accuracy) as avg_accuracy
        FROM weapon_comprehensive_stats
        {where_clause}
        GROUP BY weapon_name
        ORDER BY total_kills DESC
        LIMIT ${param_idx}
    """
    params.append(limit)

    try:
        rows = await db.fetch_all(query, tuple(params))
    except Exception as e:
        logger.error(f"Error fetching weapon stats: {e}")
        raise HTTPException(status_code=500, detail="Database error")

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
            AVG(accuracy) as avg_accuracy
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
async def get_weapon_stats_by_player(
    period: str = "all",
    player_limit: int = 25,
    weapon_limit: int = 5,
    player_guid: Optional[str] = None,
    gaming_session_id: Optional[int] = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Return per-player weapon stats keyed by player GUID.
    Useful for comprehensive weapon mastery views.
    """
    where_clause = "WHERE weapon_name IS NOT NULL"
    params: List[Any] = []
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
        where_clause += f" AND player_guid = ${param_idx}"
        params.append(player_guid)
        param_idx += 1

    query = f"""
        SELECT
            player_guid,
            MAX(player_name) AS player_name,
            weapon_name,
            SUM(kills) AS total_kills,
            SUM(headshots) AS total_headshots,
            SUM(shots) AS total_shots,
            SUM(hits) AS total_hits,
            AVG(accuracy) AS avg_accuracy
        FROM weapon_comprehensive_stats
        {where_clause}
        GROUP BY player_guid, weapon_name
        HAVING SUM(kills) > 0 OR SUM(hits) > 0
        ORDER BY player_guid, total_kills DESC, total_hits DESC
    """

    try:
        rows = await db.fetch_all(query, tuple(params))
    except Exception as e:
        logger.error(f"Error fetching weapon stats by player: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    players: Dict[str, Dict[str, Any]] = {}
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
        headshots = int(row[4] or 0)
        shots = int(row[5] or 0)
        hits = int(row[6] or 0)
        avg_accuracy = float(row[7] or 0)
        # Player-level headshot accuracy: headshots / hits * 100
        # headshots in weapon_comprehensive_stats are headshot HITS, not kills.
        hs_rate = round((headshots / hits) * 100, 1) if hits > 0 else 0.0

        players[guid]["total_kills"] += kills
        players[guid]["weapons"].append(
            {
                "name": _clean_weapon_name(row[2]),
                "weapon_key": _normalize_weapon_key(row[2]),
                "kills": kills,
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


@router.get("/stats/matches/{match_id}")
async def get_match_details(match_id: str, db: DatabaseAdapter = Depends(get_db)):
    """
    Get detailed stats for a specific match/round.
    match_id can be: round ID (numeric) or round_date string
    """
    # First, get the round info
    if match_id.isdigit():
        # It's a round ID
        round_query = """
            SELECT id, map_name, round_number, round_date, winner_team,
                   actual_time, round_outcome, gaming_session_id, time_limit
            FROM rounds
            WHERE id = $1
        """
        round_row = await db.fetch_one(round_query, (int(match_id),))
    else:
        # It's a date - get latest round for that date
        round_query = """
            SELECT id, map_name, round_number, round_date, winner_team,
                   actual_time, round_outcome, gaming_session_id, time_limit
            FROM rounds
            WHERE round_date = $1
            ORDER BY CAST(REPLACE(round_time, ':', '') AS INTEGER) DESC
            LIMIT 1
        """
        round_row = await db.fetch_one(round_query, (match_id,))

    if not round_row:
        raise HTTPException(status_code=404, detail="Match not found")

    round_id = round_row[0]
    map_name = round_row[1]
    round_number = round_row[2]
    round_date = round_row[3]
    winner_team = round_row[4]
    actual_time = round_row[5]
    round_outcome = round_row[6]
    gaming_session_id = round_row[7]
    time_limit = round_row[8] if len(round_row) > 8 else None

    # Convert winner_team int to string
    winner = "Allies" if winner_team == 1 else "Axis" if winner_team == 2 else "Draw"

    # Get player stats for this specific round
    # Use DISTINCT ON to deduplicate players (in case of multiple entries per player)
    # Picks the row with highest damage_given per player, then orders by team
    query = """
        SELECT * FROM (
            SELECT DISTINCT ON (player_name)
                player_name,
                kills,
                deaths,
                damage_given,
                damage_received,
                time_played_seconds,
                team,
                xp,
                headshots,
                revives_given,
                accuracy,
                gibs,
                self_kills,
                team_kills,
                times_revived,
                most_useful_kills,
                bullets_fired,
                time_dead_minutes,
                denied_playtime,
                double_kills,
                triple_kills,
                quad_kills,
                multi_kills,
                mega_kills,
                player_guid
            FROM player_comprehensive_stats
            WHERE round_date = $1
              AND map_name = $2
              AND round_number = $3
            ORDER BY player_name, damage_given DESC
        ) AS deduplicated
        ORDER BY team, damage_given DESC
    """

    try:
        rows = await db.fetch_all(query, (round_date, map_name, round_number))
    except Exception as e:
        logger.error(f"Error fetching match details: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    if not rows:
        raise HTTPException(status_code=404, detail="No player stats found")

    # Group players by team
    team1_players = []
    team2_players = []

    for row in rows:
        time_played = row[5] or 0
        dpm = (row[3] / (time_played / 60)) if time_played > 0 else 0
        kd = row[1] / row[2] if row[2] > 0 else float(row[1])

        # Calculate hits from accuracy and bullets_fired
        bullets_fired = row[16] or 0
        accuracy_pct = row[10] or 0
        hits = round(bullets_fired * accuracy_pct / 100) if accuracy_pct > 0 else 0

        player = {
            "name": row[0],
            "kills": row[1] or 0,
            "deaths": row[2] or 0,
            "damage_given": row[3] or 0,
            "damage_received": row[4] or 0,
            "time_played": time_played,
            "team": row[6],
            "xp": row[7] or 0,
            "headshots": row[8] or 0,
            "revives_given": row[9] or 0,
            "accuracy": round(accuracy_pct, 1),
            "gibs": row[11] or 0,
            "selfkills": row[12] or 0,
            "teamkills": row[13] or 0,
            "times_revived": row[14] or 0,
            "useful_kills": row[15] or 0,
            "shots": bullets_fired,
            "hits": hits,
            "time_dead": round((row[17] or 0) * 60),  # Convert minutes to seconds
            "time_denied": row[18] or 0,
            "double_kills": row[19] or 0,
            "triple_kills": row[20] or 0,
            "quad_kills": row[21] or 0,
            "multi_kills": row[22] or 0,
            "mega_kills": row[23] or 0,
            "player_guid": row[24],
            "dpm": round(dpm, 1),
            "kd": round(kd, 2),
        }

        if row[6] == 1:
            team1_players.append(player)
        else:
            team2_players.append(player)

    # Check if teams are imbalanced (difference > 2 players)
    team_diff = abs(len(team1_players) - len(team2_players))
    if team_diff > 2 and len(team1_players) + len(team2_players) >= 4:
        # Teams are imbalanced - redistribute evenly
        # This happens when team detection failed
        all_players = team1_players + team2_players
        # Sort by damage to keep best players distributed
        all_players.sort(key=lambda p: p["damage_given"], reverse=True)
        mid_point = len(all_players) // 2
        team1_players = all_players[:mid_point]
        team2_players = all_players[mid_point:]

    # Calculate team totals
    def team_totals(players):
        return {
            "kills": sum(p["kills"] for p in players),
            "deaths": sum(p["deaths"] for p in players),
            "damage": sum(p["damage_given"] for p in players),
        }

    return {
        "match": {
            "id": round_id,
            "map_name": map_name,
            "round_number": round_number,
            "round_date": str(round_date),
            "winner": winner,
            "duration": actual_time,
            "outcome": round_outcome,
            "time_limit": time_limit,
            "gaming_session_id": gaming_session_id,
        },
        "team1": {
            "name": "Allies",
            "players": team1_players,
            "totals": team_totals(team1_players),
            "is_winner": winner_team == 1,
        },
        "team2": {
            "name": "Axis",
            "players": team2_players,
            "totals": team_totals(team2_players),
            "is_winner": winner_team == 2,
        },
        "player_count": len(rows),
    }


@router.get("/stats/records")
async def get_records(
    map_name: str = None, limit: int = 1, db: DatabaseAdapter = Depends(get_db)
):
    """
    Get all-time records (Hall of Fame).
    If map_name is provided, returns records for that map only.
    """
    # Categories to fetch
    categories = {
        "kills": {"col": "kills", "label": "Most Kills"},
        "damage": {"col": "damage_given", "label": "Most Damage"},
        "revives": {"col": "revives_given", "label": "Most Revives"},
        "gibs": {"col": "gibs", "label": "Most Gibs"},
        "headshots": {"col": "headshots", "label": "Most Headshots"},
        "xp": {"col": "xp", "label": "Most XP"},
        "accuracy": {
            "col": "accuracy",
            "label": "Best Accuracy",
            "filter": "bullets_fired > 50",
        },
        "revived": {"col": "times_revived", "label": "Most Times Revived"},
        "useful_kills": {"col": "most_useful_kills", "label": "Most Useful Kills"},
        "obj_stolen": {"col": "objectives_stolen", "label": "Objectives Stolen"},
        "obj_returned": {"col": "objectives_returned", "label": "Objectives Returned"},
        "dyna_planted": {"col": "dynamites_planted", "label": "Dynamites Planted"},
        "dyna_defused": {"col": "dynamites_defused", "label": "Dynamites Defused"},
    }

    results = {}

    base_where = "WHERE round_number IN (1, 2) AND time_played_seconds > 0"
    params = []

    if map_name:
        base_where += " AND map_name = $1"
        params.append(map_name)

    for key, config in categories.items():
        col = config["col"]
        extra_filter = f" AND {config['filter']}" if "filter" in config else ""

        query = f"""
            SELECT
                player_name,
                {col} as value,
                map_name,
                round_date
            FROM player_comprehensive_stats
            {base_where} {extra_filter}
            ORDER BY {col} DESC
            LIMIT $2
        """

        # Adjust param index for limit
        if map_name:
            q_params = (map_name, limit)
            query = query.replace("$2", "$2")
        else:
            q_params = (limit,)
            query = query.replace("$2", "$1")

        try:
            rows = await db.fetch_all(query, q_params)
            if rows:
                results[key] = [
                    {"player": row[0], "value": row[1], "map": row[2], "date": row[3]}
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Error fetching record for {key}: {e}")
            results[key] = []

    return results


# ========================================
# ENDSTATS / AWARDS ENDPOINTS
# ========================================

# Award categories for display (mirrors bot/endstats_parser.py)
AWARD_CATEGORIES = {
    "combat": {
        "emoji": "⚔️",
        "name": "Combat",
        "awards": [
            "Most damage given",
            "Most damage received",
            "Most kills per minute",
            "Most damage per minute",
            "Best K/D ratio",
            "Tank/Meatshield (Refuses to die)",
        ],
    },
    "deaths": {
        "emoji": "💀",
        "name": "Deaths & Mayhem",
        "awards": [
            "Most deaths",
            "Most selfkills",
            "Most teamkills",
            "Longest death spree",
            "Most panzer deaths",
            "Most mortar deaths",
            "Most MG42 deaths",
            "Mortarmagnet",
        ],
    },
    "skills": {
        "emoji": "🎯",
        "name": "Skills",
        "awards": [
            "Most headshot kills",
            "Most headshots",
            "Highest light weapons accuracy",
            "Highest headshot accuracy",
            "Most light weapon kills",
            "Most pistol kills",
            "Most rifle kills",
            "Most sniper kills",
            "Most knife kills",
            "Longest killing spree",
            "Most multikills",
            "Most doublekills",
            "Quickest multikill w/ light weapons",
            "Most bullets fired",
        ],
    },
    "weapons": {
        "emoji": "🔫",
        "name": "Weapons",
        "awards": [
            "Most grenade kills",
            "Most panzer kills",
            "Most mortar kills",
            "Most mine kills",
            "Most air support kills",
            "Most riflenade kills",
            "Farthest riflenade kill",
            "Most MG42 kills",
        ],
    },
    "teamwork": {
        "emoji": "🤝",
        "name": "Teamwork",
        "awards": [
            "Most revives",
            "Most revived",
            "Most kill assists",
            "Most killsteals",
            "Most team damage given",
            "Most team damage received",
        ],
    },
    "objectives": {
        "emoji": "🎯",
        "name": "Objectives",
        "awards": [
            "Most dynamites planted",
            "Most dynamites defused",
            "Most objectives stolen",
            "Most objectives returned",
            "Most corpse gibs",
        ],
    },
    "timing": {
        "emoji": "⏱️",
        "name": "Timing",
        "awards": [
            "Most useful kills (>Half respawn time left)",
            "Most useless kills",
            "Full respawn king",
            "Most playtime denied",
            "Least time dead (What spawn?)",
        ],
    },
}


def categorize_award(award_name: str) -> tuple:
    """Return (category_key, emoji, category_name) for an award."""
    for cat_key, cat_data in AWARD_CATEGORIES.items():
        if award_name in cat_data["awards"]:
            return (cat_key, cat_data["emoji"], cat_data["name"])
    return ("other", "📋", "Other")


@router.get("/rounds/{round_id}/awards")
async def get_round_awards(round_id: int, db: DatabaseAdapter = Depends(get_db)):
    """
    Get awards for a specific round, grouped by category.
    """
    # Get round info
    round_query = "SELECT map_name, round_number, round_date FROM rounds WHERE id = $1"
    round_row = await db.fetch_one(round_query, (round_id,))

    if not round_row:
        raise HTTPException(status_code=404, detail="Round not found")

    # Get awards
    awards_query = """
        SELECT award_name, player_name, player_guid, award_value, award_value_numeric
        FROM round_awards
        WHERE round_id = $1
        ORDER BY id
    """
    awards_rows = await db.fetch_all(awards_query, (round_id,))

    unknown_names = [row[1] for row in awards_rows if row[2] is None and row[1]]
    alias_map = await resolve_alias_guid_map(db, unknown_names)
    name_map = await resolve_name_guid_map(db, unknown_names)

    # Group by category
    categories = {}
    for row in awards_rows:
        award_name, player, player_guid, value, numeric = row
        effective_guid = (
            player_guid
            or alias_map.get(player.lower() if player else "")
            or name_map.get(player.lower() if player else "")
        )
        cat_key, emoji, cat_name = categorize_award(award_name)

        if cat_key not in categories:
            categories[cat_key] = {"emoji": emoji, "name": cat_name, "awards": []}

        display_name = (
            await resolve_display_name(db, effective_guid, player or "Unknown")
            if effective_guid
            else (player or "Unknown")
        )
        categories[cat_key]["awards"].append(
            {
                "award": award_name,
                "player": display_name,
                "guid": effective_guid,
                "value": value,
                "numeric": numeric,
            }
        )

    return {
        "round_id": round_id,
        "map_name": round_row[0],
        "round_number": round_row[1],
        "round_date": round_row[2],
        "categories": categories,
    }


@router.get("/rounds/{round_id}/vs-stats")
async def get_round_vs_stats(round_id: int, db: DatabaseAdapter = Depends(get_db)):
    """
    Get VS stats (player K/D) for a specific round.
    """
    query = """
        SELECT player_name, player_guid, kills, deaths
        FROM round_vs_stats
        WHERE round_id = $1
        ORDER BY kills DESC, deaths ASC
    """
    rows = await db.fetch_all(query, (round_id,))

    unknown_names = [row[0] for row in rows if row[1] is None and row[0]]
    alias_map = await resolve_alias_guid_map(db, unknown_names)
    name_map = await resolve_name_guid_map(db, unknown_names)

    return {
        "round_id": round_id,
        "stats": [
            {
                "player": (
                    await resolve_display_name(
                        db,
                        row[1]
                        or alias_map.get(row[0].lower() if row[0] else "")
                        or name_map.get(row[0].lower() if row[0] else ""),
                        row[0] or "Unknown",
                    )
                    if (
                        row[1]
                        or alias_map.get(row[0].lower() if row[0] else "")
                        or name_map.get(row[0].lower() if row[0] else "")
                    )
                    else (row[0] or "Unknown")
                ),
                "guid": row[1] or alias_map.get(row[0].lower() if row[0] else "") or name_map.get(row[0].lower() if row[0] else ""),
                "kills": row[2],
                "deaths": row[3],
            }
            for row in rows
        ],
    }


@router.get("/player/{guid}/vs-stats")
async def get_player_vs_stats(
    guid: str,
    scope: str = "all",
    round_id: Optional[int] = None,
    session_id: Optional[int] = None,
    limit: int = Query(default=10, le=50),
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Player vs player stats — Easiest Preys and Worst Enemies.
    Scope: 'round' (single round), 'session' (gaming session), 'all' (all-time).
    """
    safe_limit = max(1, min(limit, 50))

    # Normalize GUID length: stats uses 8-char, endstats may use 32-char
    # Match using LEFT(guid, 8) for compatibility across both formats
    guid_short = guid[:8] if len(guid) > 8 else guid

    # Build round filter based on scope
    if scope == "round" and round_id:
        round_filter = "AND v.round_id = $2"
        params_base: tuple = (guid_short, round_id)
    elif scope == "session" and session_id:
        round_filter = "AND v.round_id IN (SELECT id FROM rounds WHERE gaming_session_id = $2)"
        params_base = (guid_short, session_id)
    else:
        round_filter = ""
        params_base = (guid_short,)

    limit_param = f"${len(params_base) + 1}"

    # Easiest Preys — opponents this player killed most (player is the attacker)
    preys_query = f"""
        SELECT
            COALESCE(LEFT(v.subject_guid, 8), v.subject_name) AS opponent_key,
            MAX(v.subject_name) AS opponent_name,
            LEFT(v.subject_guid, 8) AS opponent_guid,
            SUM(v.kills) AS total_kills,
            SUM(v.deaths) AS total_deaths
        FROM round_vs_stats v
        WHERE LEFT(v.player_guid, 8) = $1 {round_filter}
          AND v.player_guid IS NOT NULL
          AND v.subject_guid IS NOT NULL AND v.subject_guid != ''
        GROUP BY opponent_key, LEFT(v.subject_guid, 8)
        ORDER BY total_kills DESC, total_deaths ASC
        LIMIT {limit_param}
    """
    preys_rows = await db.fetch_all(preys_query, params_base + (safe_limit,))

    # Worst Enemies — opponents who killed this player most (player is the subject/victim)
    enemies_query = f"""
        SELECT
            COALESCE(LEFT(v.player_guid, 8), v.player_name) AS opponent_key,
            MAX(v.player_name) AS opponent_name,
            LEFT(v.player_guid, 8) AS opponent_guid,
            SUM(v.kills) AS total_kills,
            SUM(v.deaths) AS total_deaths
        FROM round_vs_stats v
        WHERE LEFT(v.subject_guid, 8) = $1 {round_filter}
          AND v.subject_guid IS NOT NULL
        GROUP BY opponent_key, LEFT(v.player_guid, 8)
        ORDER BY total_kills DESC, total_deaths ASC
        LIMIT {limit_param}
    """
    enemies_rows = await db.fetch_all(enemies_query, params_base + (safe_limit,))

    def build_entry(row):
        kills = int(row[3] or 0)
        deaths = int(row[4] or 0)
        return {
            "opponent_name": row[1],
            "opponent_guid": row[2],
            "kills": kills,
            "deaths": deaths,
            "kd": round(kills / max(deaths, 1), 2),
        }

    return {
        "guid": guid,
        "scope": scope,
        "round_id": round_id if scope == "round" else None,
        "session_id": session_id if scope == "session" else None,
        "easiest_preys": [build_entry(r) for r in (preys_rows or [])],
        "worst_enemies": [build_entry(r) for r in (enemies_rows or [])],
    }


@router.get("/awards/leaderboard")
async def get_awards_leaderboard(
    limit: int = 20,
    days: int = 0,
    award_type: str = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Get leaderboard of players by total awards won.

    Args:
        limit: Number of players to return
        days: Filter to last N days (0 = all time)
        award_type: Filter to specific award type
    """
    params = []
    where_clauses = []
    param_idx = 1

    if days > 0:
        where_clauses.append(
            f"ra.created_at >= NOW() - (${param_idx} * INTERVAL '1 day')"
        )
        params.append(days)
        param_idx += 1

    if award_type:
        where_clauses.append(f"ra.award_name = ${param_idx}")
        params.append(award_type)
        param_idx += 1

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    # Get player award counts with their most won award (GUID-aware)
    query = f"""
        WITH alias_map AS (
            SELECT DISTINCT ON (alias) alias, guid
            FROM player_aliases
            ORDER BY alias, last_seen DESC
        ),
        name_map AS (
            SELECT DISTINCT ON (LOWER(player_name))
                LOWER(player_name) as name_key,
                player_guid
            FROM player_comprehensive_stats
            ORDER BY LOWER(player_name), round_date DESC
        ),
        player_counts AS (
            SELECT
                COALESCE(ra.player_guid, am.guid, nm.player_guid, ra.player_name) as player_key,
                COALESCE(ra.player_guid, am.guid, nm.player_guid) as player_guid,
                MAX(ra.player_name) as player_name,
                ra.award_name,
                COUNT(*) as award_specific_count
            FROM round_awards ra
            LEFT JOIN alias_map am ON LOWER(ra.player_name) = LOWER(am.alias)
            LEFT JOIN name_map nm ON LOWER(ra.player_name) = nm.name_key
            {where_sql}
            GROUP BY player_key, player_guid, ra.award_name
        ),
        player_totals AS (
            SELECT
                player_key,
                MAX(player_guid) as player_guid,
                MAX(player_name) as player_name,
                SUM(award_specific_count) as total_awards
            FROM player_counts
            GROUP BY player_key
        ),
        top_awards AS (
            SELECT DISTINCT ON (player_key)
                player_key,
                award_name as top_award,
                award_specific_count as top_award_count
            FROM player_counts
            ORDER BY player_key, award_specific_count DESC
        )
        SELECT
            pt.player_guid,
            pt.player_name,
            pt.total_awards,
            ta.top_award,
            ta.top_award_count
        FROM player_totals pt
        JOIN top_awards ta ON pt.player_key = ta.player_key
        ORDER BY pt.total_awards DESC
        LIMIT ${param_idx}
    """
    params.append(limit)

    try:
        rows = await db.fetch_all(query, tuple(params))
    except Exception:
        fallback_query = f"""
            WITH player_counts AS (
                SELECT
                    player_name,
                    COUNT(*) as award_count,
                    award_name,
                    COUNT(*) as award_specific_count
                FROM round_awards ra
                {where_sql}
                GROUP BY player_name, award_name
            ),
            player_totals AS (
                SELECT
                    player_name,
                    SUM(award_specific_count) as total_awards
                FROM player_counts
                GROUP BY player_name
            ),
            top_awards AS (
                SELECT DISTINCT ON (player_name)
                    player_name,
                    award_name as top_award,
                    award_specific_count as top_award_count
                FROM player_counts
                ORDER BY player_name, award_specific_count DESC
            )
            SELECT
                pt.player_name,
                pt.total_awards,
                ta.top_award,
                ta.top_award_count
            FROM player_totals pt
            JOIN top_awards ta ON pt.player_name = ta.player_name
            ORDER BY pt.total_awards DESC
            LIMIT ${param_idx}
        """
        rows = await db.fetch_all(fallback_query, tuple(params))

    # Build GUID enrichment map for any name-only rows
    name_pool = []
    for row in rows:
        if len(row) == 4:
            name_pool.append(row[0])
        else:
            name_pool.append(row[1])
    alias_map = await resolve_alias_guid_map(db, name_pool)
    name_map = await resolve_name_guid_map(db, name_pool)

    leaderboard = []
    for idx, row in enumerate(rows):
        if len(row) == 4:
            player_guid = None
            player_name, total_awards, top_award, top_award_count = row
        else:
            player_guid, player_name, total_awards, top_award, top_award_count = row
        if not player_guid and player_name:
            key = player_name.lower()
            player_guid = alias_map.get(key) or name_map.get(key)
        display_name = (
            await resolve_display_name(db, player_guid, player_name or "Unknown")
            if player_guid
            else (player_name or "Unknown")
        )
        leaderboard.append(
            {
                "rank": idx + 1,
                "player": display_name,
                "guid": player_guid,
                "award_count": total_awards,
                "top_award": top_award,
                "top_award_count": top_award_count,
            }
        )

    return {
        "leaderboard": leaderboard,
        "filters": {"days": days, "award_type": award_type},
    }


@router.get("/players/{identifier}/awards")
async def get_player_awards(
    identifier: str, limit: int = 10, db: DatabaseAdapter = Depends(get_db)
):
    """
    Get awards won by a specific player.

    Args:
        identifier: Player name or GUID
        limit: Number of recent awards to return
    """
    resolved_guid = await resolve_player_guid(db, identifier)
    display_name = (
        await resolve_display_name(db, resolved_guid, identifier)
        if resolved_guid
        else identifier
    )

    if resolved_guid:
        count_query = """
            WITH alias_map AS (
                SELECT DISTINCT ON (alias) alias, guid
                FROM player_aliases
                ORDER BY alias, last_seen DESC
            ),
            name_map AS (
                SELECT DISTINCT ON (LOWER(player_name))
                    LOWER(player_name) as name_key,
                    player_guid
                FROM player_comprehensive_stats
                ORDER BY LOWER(player_name), round_date DESC
            )
            SELECT ra.award_name, COUNT(*) as count
            FROM round_awards ra
            LEFT JOIN alias_map am ON LOWER(ra.player_name) = LOWER(am.alias)
            LEFT JOIN name_map nm ON LOWER(ra.player_name) = nm.name_key
            WHERE COALESCE(ra.player_guid, am.guid, nm.player_guid) = $1
            GROUP BY ra.award_name
            ORDER BY count DESC
        """
        recent_query = """
            WITH alias_map AS (
                SELECT DISTINCT ON (alias) alias, guid
                FROM player_aliases
                ORDER BY alias, last_seen DESC
            ),
            name_map AS (
                SELECT DISTINCT ON (LOWER(player_name))
                    LOWER(player_name) as name_key,
                    player_guid
                FROM player_comprehensive_stats
                ORDER BY LOWER(player_name), round_date DESC
            )
            SELECT ra.award_name, ra.award_value, ra.round_date, ra.map_name, ra.round_number
            FROM round_awards ra
            LEFT JOIN alias_map am ON LOWER(ra.player_name) = LOWER(am.alias)
            LEFT JOIN name_map nm ON LOWER(ra.player_name) = nm.name_key
            WHERE COALESCE(ra.player_guid, am.guid, nm.player_guid) = $1
            ORDER BY ra.created_at DESC
            LIMIT $2
        """
        try:
            count_rows = await db.fetch_all(count_query, (resolved_guid,))
            recent_rows = await db.fetch_all(recent_query, (resolved_guid, limit))
        except Exception:
            fallback_count = """
                SELECT award_name, COUNT(*) as count
                FROM round_awards
                WHERE player_guid = $1
                GROUP BY award_name
                ORDER BY count DESC
            """
            fallback_recent = """
                SELECT award_name, award_value, round_date, map_name, round_number
                FROM round_awards
                WHERE player_guid = $1
                ORDER BY created_at DESC
                LIMIT $2
            """
            count_rows = await db.fetch_all(fallback_count, (resolved_guid,))
            recent_rows = await db.fetch_all(fallback_recent, (resolved_guid, limit))
    else:
        # Fallback: name-based lookup
        count_query = """
            SELECT award_name, COUNT(*) as count
            FROM round_awards
            WHERE player_name ILIKE $1
            GROUP BY award_name
            ORDER BY count DESC
        """
        recent_query = """
            SELECT ra.award_name, ra.award_value, ra.round_date, ra.map_name, ra.round_number
            FROM round_awards ra
            WHERE ra.player_name ILIKE $1
            ORDER BY ra.created_at DESC
            LIMIT $2
        """
        count_rows = await db.fetch_all(count_query, (identifier,))
        recent_rows = await db.fetch_all(recent_query, (identifier, limit))

    total = sum(row[1] for row in count_rows)

    return {
        "player": display_name,
        "guid": resolved_guid,
        "total_awards": total,
        "by_type": {row[0]: row[1] for row in count_rows},
        "recent": [
            {
                "award": row[0],
                "value": row[1],
                "date": row[2],
                "map": row[3],
                "round": row[4],
            }
            for row in recent_rows
        ],
    }


@router.get("/awards")
async def list_awards(
    limit: int = 50,
    offset: int = 0,
    player: str = None,
    award_type: str = None,
    days: int = 0,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    List all awards with pagination and filters.

    Args:
        limit: Number of awards per page
        offset: Pagination offset
        player: Filter by player name
        award_type: Filter by award type
        days: Filter to last N days
    """
    params = []
    where_clauses = []
    param_idx = 1

    resolved_player_guid = None
    if player:
        resolved_player_guid = await resolve_player_guid(db, player)
        if resolved_player_guid:
            where_clauses.append(
                f"COALESCE(ra.player_guid, am.guid) = ${param_idx}"
            )
            params.append(resolved_player_guid)
            param_idx += 1
        else:
            where_clauses.append(f"ra.player_name ILIKE ${param_idx}")
            params.append(f"%{escape_like_pattern(player)}%")
            param_idx += 1

    if award_type:
        where_clauses.append(f"ra.award_name = ${param_idx}")
        params.append(award_type)
        param_idx += 1

    if days > 0:
        where_clauses.append(f"ra.created_at >= NOW() - (${param_idx} * INTERVAL '1 day')")
        params.append(days)
        param_idx += 1

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    # Get total count + awards (GUID-aware)
    count_query = f"""
        WITH alias_map AS (
            SELECT DISTINCT ON (alias) alias, guid
            FROM player_aliases
            ORDER BY alias, last_seen DESC
        ),
        name_map AS (
            SELECT DISTINCT ON (LOWER(player_name))
                LOWER(player_name) as name_key,
                player_guid
            FROM player_comprehensive_stats
            ORDER BY LOWER(player_name), round_date DESC
        )
        SELECT COUNT(*)
        FROM round_awards ra
        LEFT JOIN alias_map am ON LOWER(ra.player_name) = LOWER(am.alias)
        LEFT JOIN name_map nm ON LOWER(ra.player_name) = nm.name_key
        {where_sql}
    """
    query = f"""
        WITH alias_map AS (
            SELECT DISTINCT ON (alias) alias, guid
            FROM player_aliases
            ORDER BY alias, last_seen DESC
        ),
        name_map AS (
            SELECT DISTINCT ON (LOWER(player_name))
                LOWER(player_name) as name_key,
                player_guid
            FROM player_comprehensive_stats
            ORDER BY LOWER(player_name), round_date DESC
        )
        SELECT ra.award_name,
               ra.player_name,
               COALESCE(ra.player_guid, am.guid, nm.player_guid) as player_guid,
               ra.award_value,
               ra.round_date,
               ra.map_name,
               ra.round_number,
               ra.round_id
        FROM round_awards ra
        LEFT JOIN alias_map am ON LOWER(ra.player_name) = LOWER(am.alias)
        LEFT JOIN name_map nm ON LOWER(ra.player_name) = nm.name_key
        {where_sql}
        ORDER BY ra.created_at DESC
        LIMIT ${param_idx} OFFSET ${param_idx + 1}
    """
    params.extend([limit, offset])

    try:
        count_row = await db.fetch_one(count_query, tuple(params[:-2]))
        total = count_row[0] if count_row else 0
        rows = await db.fetch_all(query, tuple(params))
    except Exception:
        # Fallback if alias table missing
        fallback_where_sql = where_sql.replace("COALESCE(ra.player_guid, am.guid, nm.player_guid)", "ra.player_guid")
        fallback_where_sql = fallback_where_sql.replace("COALESCE(ra.player_guid, am.guid)", "ra.player_guid")
        fallback_count = f"SELECT COUNT(*) FROM round_awards ra {fallback_where_sql}"
        count_row = await db.fetch_one(fallback_count, tuple(params[:-2]))
        total = count_row[0] if count_row else 0
        fallback_query = f"""
            SELECT ra.award_name, ra.player_name, ra.player_guid, ra.award_value,
                   ra.round_date, ra.map_name, ra.round_number, ra.round_id
            FROM round_awards ra
            {fallback_where_sql}
            ORDER BY ra.created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        rows = await db.fetch_all(fallback_query, tuple(params))

    return {
        "awards": [
            {
                "award": row[0],
                "player": (
                    await resolve_display_name(db, row[2], row[1] or "Unknown")
                    if row[2]
                    else (row[1] or "Unknown")
                ),
                "guid": row[2],
                "value": row[3],
                "date": row[4],
                "map": row[5],
                "round_number": row[6],
                "round_id": row[7],
            }
            for row in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
        "filters": {"player": player, "award_type": award_type, "days": days},
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
        SELECT player_guid, MAX(player_name) as player_name, SUM(team_damage) as total_team_damage
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
            return None

    async def _fetch_one_with_fallback(query: str):
        row = await _fetch_one_with_field(query, "round_date")
        if row is None:
            row = await _fetch_one_with_field(query, "session_date")
        return row

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
# ========================================
# HALL OF FAME
# ========================================


@router.get("/hall-of-fame")
async def get_hall_of_fame(
    period: str = "all_time",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    season_id: Optional[int] = None,
    limit: int = 10,
    db: DatabaseAdapter = Depends(get_db),
):
    """Hall of Fame: top players across multiple stat categories."""
    limit = max(1, min(limit, 100))

    # Build date filter
    date_filter = ""
    params: list = []
    param_idx = 1

    if period == "season" or season_id is not None:
        sm = SeasonManager()
        season_start, season_end = sm.get_season_dates(season_id)
        date_filter = f"AND pcs.round_date >= ${param_idx} AND pcs.round_date <= ${param_idx + 1}"
        params.extend([season_start.strftime("%Y-%m-%d"), season_end.strftime("%Y-%m-%d")])
        param_idx += 2
    elif period == "custom" and start_date and end_date:
        try:
            datetime.strptime(start_date, "%Y-%m-%d")
            datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
        date_filter = f"AND pcs.round_date >= ${param_idx} AND pcs.round_date <= ${param_idx + 1}"
        params.extend([start_date, end_date])
        param_idx += 2
    elif period == "7d":
        cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        date_filter = f"AND pcs.round_date >= ${param_idx}"
        params.append(cutoff)
        param_idx += 1
    elif period == "14d":
        cutoff = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
        date_filter = f"AND pcs.round_date >= ${param_idx}"
        params.append(cutoff)
        param_idx += 1
    elif period == "30d":
        cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        date_filter = f"AND pcs.round_date >= ${param_idx}"
        params.append(cutoff)
        param_idx += 1
    elif period == "90d":
        cutoff = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        date_filter = f"AND pcs.round_date >= ${param_idx}"
        params.append(cutoff)
        param_idx += 1
    # else: all_time - no date filter

    limit_param = f"${param_idx}"
    params.append(limit)

    try:
        categories = {}

        # --- Simple aggregation categories ---
        simple_cats = {
            "most_active": ("COUNT(*)", "rounds"),
            "most_damage": ("SUM(pcs.damage_given)", "damage"),
            "most_kills": ("SUM(pcs.kills)", "kills"),
            "most_revives": ("SUM(pcs.revives_given)", "revives"),
            "most_xp": ("SUM(pcs.xp)", "xp"),
            "most_assists": ("SUM(pcs.kill_assists)", "assists"),
            "most_deaths": ("SUM(pcs.deaths)", "deaths"),
            "most_selfkills": ("SUM(pcs.self_kills)", "selfkills"),
            "most_full_selfkills": ("SUM(pcs.full_selfkills)", "full_selfkills"),
        }

        for cat_name, (agg_expr, unit) in simple_cats.items():
            # nosec B608 - agg_expr and date_filter are static/controlled strings
            query = f"""
                SELECT pcs.player_guid, MAX(pcs.player_name) as player_name,
                       {agg_expr} as value
                FROM player_comprehensive_stats pcs
                WHERE pcs.round_number IN (1, 2) AND pcs.time_played_seconds > 0 {date_filter}
                GROUP BY pcs.player_guid
                ORDER BY value DESC
                LIMIT {limit_param}
            """
            rows = await db.fetch_all(query, tuple(params))
            entries = []
            for rank, row in enumerate(rows, 1):
                name = await resolve_display_name(db, row[0], row[1] or "Unknown")
                entries.append({
                    "rank": rank,
                    "player_guid": row[0],
                    "player_name": name,
                    "value": int(row[2]) if row[2] is not None else 0,
                    "unit": unit,
                })
            categories[cat_name] = entries

        # --- most_wins: join with rounds to check winner_team ---
        wins_query = f"""
            SELECT pcs.player_guid, MAX(pcs.player_name) as player_name,
                   COUNT(*) as value
            FROM player_comprehensive_stats pcs
            JOIN rounds r ON pcs.round_id = r.id
            WHERE pcs.round_number IN (1, 2) AND pcs.time_played_seconds > 0
              AND r.winner_team != 0
              AND pcs.team = r.winner_team
              {date_filter}
            GROUP BY pcs.player_guid
            ORDER BY value DESC
            LIMIT {limit_param}
        """
        rows = await db.fetch_all(wins_query, tuple(params))
        entries = []
        for rank, row in enumerate(rows, 1):
            name = await resolve_display_name(db, row[0], row[1] or "Unknown")
            entries.append({
                "rank": rank,
                "player_guid": row[0],
                "player_name": name,
                "value": int(row[2]) if row[2] is not None else 0,
                "unit": "wins",
            })
        categories["most_wins"] = entries

        # --- most_dpm: damage per minute with min 10 rounds ---
        dpm_min_rounds_param = f"${param_idx + 1}"
        dpm_params = list(params) + [10]
        dpm_query = f"""
            SELECT pcs.player_guid, MAX(pcs.player_name) as player_name,
                   ROUND((SUM(pcs.damage_given)::numeric / NULLIF(SUM(pcs.time_played_seconds) / 60.0, 0)), 2) as value,
                   COUNT(*) as rounds_played
            FROM player_comprehensive_stats pcs
            WHERE pcs.round_number IN (1, 2) AND pcs.time_played_seconds > 0 {date_filter}
            GROUP BY pcs.player_guid
            HAVING COUNT(*) >= {dpm_min_rounds_param}
            ORDER BY value DESC
            LIMIT {limit_param}
        """
        rows = await db.fetch_all(dpm_query, tuple(dpm_params))
        entries = []
        for rank, row in enumerate(rows, 1):
            name = await resolve_display_name(db, row[0], row[1] or "Unknown")
            entries.append({
                "rank": rank,
                "player_guid": row[0],
                "player_name": name,
                "value": float(row[2]) if row[2] is not None else 0.0,
                "unit": "dpm",
            })
        categories["most_dpm"] = entries

        # --- most_consecutive_games: consecutive gaming sessions ---
        # gaming_session_id lives on rounds, not player_comprehensive_stats
        consec_query = f"""
            WITH player_sessions AS (
                SELECT pcs.player_guid, MAX(pcs.player_name) as player_name,
                       r.gaming_session_id
                FROM player_comprehensive_stats pcs
                JOIN rounds r ON pcs.round_id = r.id
                WHERE pcs.time_played_seconds > 0
                  AND r.gaming_session_id IS NOT NULL
                  {date_filter}
                GROUP BY pcs.player_guid, r.gaming_session_id
            ),
            all_sessions AS (
                SELECT DISTINCT r2.gaming_session_id
                FROM rounds r2
                JOIN player_comprehensive_stats pcs2 ON pcs2.round_id = r2.id
                WHERE r2.gaming_session_id IS NOT NULL
                  AND pcs2.time_played_seconds > 0
                  {date_filter.replace('pcs.', 'pcs2.')}
                ORDER BY r2.gaming_session_id
            ),
            numbered AS (
                SELECT ps.player_guid, ps.player_name, ps.gaming_session_id,
                       ROW_NUMBER() OVER (ORDER BY a.gaming_session_id) as global_rank,
                       ROW_NUMBER() OVER (PARTITION BY ps.player_guid ORDER BY ps.gaming_session_id) as player_rank
                FROM player_sessions ps
                JOIN all_sessions a ON ps.gaming_session_id = a.gaming_session_id
            ),
            streaks AS (
                SELECT player_guid, MAX(player_name) as player_name,
                       COUNT(*) as streak_len
                FROM numbered
                GROUP BY player_guid, (global_rank - player_rank)
            )
            SELECT player_guid, MAX(player_name) as player_name,
                   MAX(streak_len) as value
            FROM streaks
            GROUP BY player_guid
            ORDER BY value DESC
            LIMIT {limit_param}
        """
        rows = await db.fetch_all(consec_query, tuple(params))
        entries = []
        for rank, row in enumerate(rows, 1):
            name = await resolve_display_name(db, row[0], row[1] or "Unknown")
            entries.append({
                "rank": rank,
                "player_guid": row[0],
                "player_name": name,
                "value": int(row[2]) if row[2] is not None else 0,
                "unit": "sessions",
            })
        categories["most_consecutive_games"] = entries

        return {
            "categories": categories,
            "period": period,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Hall of Fame query failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate Hall of Fame data")


# ========================================
# STATS TRENDS
# ========================================


@router.get("/stats/trends")
async def get_stats_trends(
    days: int = 14,
    metrics: str = "rounds,active_players,kills,maps",
    db: DatabaseAdapter = Depends(get_db),
):
    """Time-series trends for activity metrics."""
    days = max(1, min(days, 90))
    requested = {m.strip().lower() for m in metrics.split(",") if m.strip()}

    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")

    try:
        # Generate full date range
        date_list = []
        current = datetime.now() - timedelta(days=days)
        while current.date() <= datetime.now().date():
            date_list.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)

        result: Dict[str, Any] = {"dates": date_list}

        if "rounds" in requested or "active_players" in requested or "kills" in requested:
            query = """
                SELECT SUBSTR(CAST(r.round_date AS TEXT), 1, 10) as day,
                       COUNT(DISTINCT r.id) as round_count,
                       COUNT(DISTINCT pcs.player_guid) as player_count,
                       COALESCE(SUM(pcs.kills), 0) as total_kills
                FROM rounds r
                LEFT JOIN player_comprehensive_stats pcs ON pcs.round_id = r.id
                WHERE SUBSTR(CAST(r.round_date AS TEXT), 1, 10) >= $1
                  AND SUBSTR(CAST(r.round_date AS TEXT), 1, 10) <= $2
                  AND r.round_number IN (1, 2)
                GROUP BY day
                ORDER BY day
            """
            rows = await db.fetch_all(query, (start_date, end_date))

            day_data = {}
            for row in rows:
                day_data[row[0]] = {
                    "rounds": int(row[1]),
                    "active_players": int(row[2]),
                    "kills": int(row[3]),
                }

            if "rounds" in requested:
                result["rounds"] = [day_data.get(d, {}).get("rounds", 0) for d in date_list]
            if "active_players" in requested:
                result["active_players"] = [day_data.get(d, {}).get("active_players", 0) for d in date_list]
            if "kills" in requested:
                result["kills"] = [day_data.get(d, {}).get("kills", 0) for d in date_list]

        if "maps" in requested:
            map_query = """
                SELECT r.map_name, COUNT(*) as play_count
                FROM rounds r
                WHERE SUBSTR(CAST(r.round_date AS TEXT), 1, 10) >= $1
                  AND SUBSTR(CAST(r.round_date AS TEXT), 1, 10) <= $2
                  AND r.round_number IN (1, 2)
                  AND r.map_name IS NOT NULL
                  AND TRIM(CAST(r.map_name AS TEXT)) <> ''
                GROUP BY r.map_name
                ORDER BY play_count DESC
            """
            map_rows = await db.fetch_all(map_query, (start_date, end_date))
            map_distribution: Dict[str, int] = {}
            for row in map_rows:
                normalized_map_name = _normalize_map_name(row[0])
                if not normalized_map_name:
                    continue

                play_count = int(row[1]) if row[1] is not None else 0
                if play_count <= 0:
                    continue

                map_distribution[normalized_map_name] = (
                    map_distribution.get(normalized_map_name, 0) + play_count
                )

            result["map_distribution"] = dict(
                sorted(
                    map_distribution.items(),
                    key=lambda item: item[1],
                    reverse=True,
                )
            )

        return result

    except Exception as e:
        logger.error(f"Stats trends query failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate trends data")


# ========================================
# RETRO-VIZ GALLERY
# ========================================


@router.get("/retro-viz/gallery")
async def get_retro_viz_gallery():
    """List PNG files in the retro-viz output directory."""
    gallery_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "retro-viz")
    gallery_dir = os.path.normpath(gallery_dir)

    if not os.path.isdir(gallery_dir):
        return {"images": []}

    images = []
    try:
        for fname in sorted(os.listdir(gallery_dir)):
            if not fname.lower().endswith(".png"):
                continue
            fpath = os.path.join(gallery_dir, fname)
            if not os.path.isfile(fpath):
                continue
            # Prevent symlink traversal outside gallery directory
            if not os.path.realpath(fpath).startswith(os.path.realpath(gallery_dir)):
                continue
            stat = os.stat(fpath)
            images.append({
                "filename": fname,
                "url": f"/data/retro-viz/{fname}",
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            })
    except Exception as e:
        logger.error(f"Retro-viz gallery listing failed: {e}")

    return {"images": images}


# ========================================
# ROUND VISUALIZATION
# ========================================


def _serialize_round_label(round_number: Any) -> str:
    """Convert round numbers to UI-safe labels."""
    if round_number is None:
        return "R?"
    try:
        normalized = int(round_number)
    except (TypeError, ValueError):
        return "R?"
    if normalized == 0:
        return "Match Summary"
    return f"R{normalized}"


@router.get("/rounds/recent")
async def get_recent_rounds(
    limit: int = 20,
    db: DatabaseAdapter = Depends(get_db),
):
    """Return recent rounds for the round picker dropdown."""
    if limit < 1 or limit > 100:
        limit = 20

    rows = await db.fetch_all(
        """
        SELECT r.id, r.map_name, r.round_date, r.round_number,
               COUNT(pcs.id) AS player_count
        FROM rounds r
        JOIN player_comprehensive_stats pcs ON pcs.round_id = r.id
        WHERE r.round_number > 0
        GROUP BY r.id, r.map_name, r.round_date, r.round_number
        ORDER BY r.id DESC
        LIMIT $1
        """,
        (limit,),
    )

    return [
        {
            "id": row[0],
            "map_name": row[1],
            "round_date": str(row[2]) if row[2] else None,
            "round_number": row[3],
            "round_label": _serialize_round_label(row[3]),
            "player_count": row[4],
        }
        for row in rows
    ]


@router.get("/rounds/{round_id}/viz")
async def get_round_viz(
    round_id: int,
    db: DatabaseAdapter = Depends(get_db),
):
    """Return all player data for a single round, shaped for the 6 chart components."""

    # Get round info
    round_row = await db.fetch_one(
        """
        SELECT id, map_name, round_date, round_number, winner_team,
               actual_duration_seconds
        FROM rounds WHERE id = $1
        """,
        (round_id,),
    )
    if not round_row:
        raise HTTPException(status_code=404, detail="Round not found")

    # Get all player stats for this round
    rows = await db.fetch_all(
        """
        SELECT player_name, player_guid, kills, deaths,
               damage_given, damage_received, team_damage_given,
               team_damage_received, time_played_seconds,
               ROUND(COALESCE(time_dead_minutes, 0) * 60)::int AS time_dead_seconds,
               COALESCE(revives_given, 0) AS revives_given,
               COALESCE(gibs, 0) AS gibs,
               COALESCE(self_kills, 0) AS self_kills,
               COALESCE(denied_playtime, 0) AS denied_playtime,
               COALESCE(xp, 0) AS xp,
               COALESCE(kill_assists, 0) AS kill_assists,
               COALESCE(efficiency, 0) AS efficiency,
               COALESCE(dpm, 0) AS dpm
        FROM player_comprehensive_stats
        WHERE round_id = $1
        ORDER BY kills DESC
        """,
        (round_id,),
    )

    players = []
    for r in rows:
        players.append({
            "name": r[0],
            "guid": r[1],
            "kills": r[2] or 0,
            "deaths": r[3] or 0,
            "damage_given": r[4] or 0,
            "damage_received": r[5] or 0,
            "team_damage_given": r[6] or 0,
            "team_damage_received": r[7] or 0,
            "time_played_seconds": r[8] or 0,
            "time_dead_seconds": r[9] or 0,
            "revives_given": r[10],
            "gibs": r[11],
            "self_kills": r[12],
            "denied_playtime": r[13],
            "xp": r[14],
            "kill_assists": r[15],
            "efficiency": float(r[16]),
            "dpm": float(r[17]),
        })

    # Compute highlights
    highlights = {}
    if players:
        mvp = max(players, key=lambda p: p["dpm"])
        highlights["mvp"] = {"name": mvp["name"], "dpm": mvp["dpm"]}
        top_kills = max(players, key=lambda p: p["kills"])
        highlights["most_kills"] = {"name": top_kills["name"], "kills": top_kills["kills"]}
        top_dmg = max(players, key=lambda p: p["damage_given"])
        highlights["most_damage"] = {"name": top_dmg["name"], "damage_given": top_dmg["damage_given"]}

    return {
        "round_id": round_row[0],
        "map_name": round_row[1],
        "round_date": str(round_row[2]) if round_row[2] else None,
        "round_number": round_row[3],
        "round_label": _serialize_round_label(round_row[3]),
        "winner_team": round_row[4],
        "duration_seconds": round_row[5],
        "player_count": len(players),
        "players": players,
        "highlights": highlights,
    }
