"""Records sub-router: Overview + activity calendar endpoints."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends

from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.logging_config import get_app_logger
from website.backend.routers.api_helpers import resolve_display_name

router = APIRouter()
logger = get_app_logger("api.records.overview")


@router.get("/stats/overview")
async def get_stats_overview(db: DatabaseAdapter = Depends(get_db)):
    """Get homepage overview statistics"""
    lookback_days = 14
    start_date_str = (
        (datetime.now() - timedelta(days=lookback_days))
        .date()
        .strftime("%Y-%m-%d")
    )

    async def safe_val(query: str, params: tuple | None = None, default=0):
        try:
            return await db.fetch_val(query, params)
        except Exception as e:
            logger.warning("[overview] query failed: %s", e)
            return default

    async def safe_one(query: str, params: tuple | None = None):
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
