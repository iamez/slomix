"""Records sub-router: Overview + activity calendar endpoints."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends

from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.logging_config import get_app_logger
from website.backend.routers.api_helpers import resolve_display_name

router = APIRouter()
logger = get_app_logger("api.records.overview")


# Legal rounds = completed / substitution, plus pre-round_status rows.
# Applied to every `rounds` aggregation so the overview matches what the
# rest of the site counts as a valid round.
_ROUND_FILTER = """
    WHERE round_number IN (1, 2)
      AND (round_status IN ('completed', 'substitution') OR round_status IS NULL)
"""


async def _safe_val(
    db: DatabaseAdapter,
    query: str,
    params: tuple | None = None,
    default=0,
    metric: str = "",
):
    try:
        return await db.fetch_val(query, params)
    except Exception as e:
        # Copilot review on PR #123: without a metric label the
        # warning line doesn't say which aggregation failed — debugging
        # this endpoint under 6 back-to-back queries was ambiguous.
        label = metric or "unknown"
        logger.warning("[overview] query failed (%s): %s", label, e)
        return default


async def _safe_one(
    db: DatabaseAdapter,
    query: str,
    params: tuple | None = None,
    metric: str = "",
):
    try:
        return await db.fetch_one(query, params)
    except Exception as e:
        label = metric or "unknown"
        logger.warning("[overview] query failed (%s): %s", label, e)
        return None


async def _fetch_rounds_stats(db: DatabaseAdapter, start_date_str: str) -> dict:
    """Count rounds + distinct gaming sessions, overall and in the lookback.

    nosec B608 rationale: every `{_ROUND_FILTER}` interpolation is a
    module-level constant defined at import time; no user input reaches
    these queries. Date filters use $1 parameters.
    """
    rounds_count = await _safe_val(db, f"SELECT COUNT(*) FROM rounds {_ROUND_FILTER}", metric="rounds_count")  # nosec B608 - trusted module constant, not user input
    rounds_first = await _safe_val(
        db,
        f"SELECT MIN(SUBSTR(CAST(round_date AS TEXT), 1, 10)) FROM rounds {_ROUND_FILTER}",  # nosec B608 - trusted module constant, not user input
        default=None,
        metric="rounds_first",
    )
    rounds_latest = await _safe_val(
        db,
        f"SELECT MAX(SUBSTR(CAST(round_date AS TEXT), 1, 10)) FROM rounds {_ROUND_FILTER}",  # nosec B608 - trusted module constant, not user input
        default=None,
        metric="rounds_latest",
    )
    rounds_recent = await _safe_val(
        db,
        f"""
        SELECT COUNT(*)
        FROM rounds
        {_ROUND_FILTER}
          AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
        """,  # nosec B608 - trusted module constant, not user input
        (start_date_str,),
        metric="rounds_recent",
    )
    sessions_count = await _safe_val(
        db,
        f"""
        SELECT COUNT(DISTINCT gaming_session_id)
        FROM rounds
        {_ROUND_FILTER}
          AND gaming_session_id IS NOT NULL
        """,  # nosec B608 - trusted module constant, not user input
        metric="sessions_count",
    )
    sessions_recent = await _safe_val(
        db,
        f"""
        SELECT COUNT(DISTINCT gaming_session_id)
        FROM rounds
        {_ROUND_FILTER}
          AND gaming_session_id IS NOT NULL
          AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
        """,  # nosec B608 - trusted module constant, not user input
        (start_date_str,),
        metric="sessions_recent",
    )
    return {
        "rounds_count": rounds_count,
        "rounds_first": rounds_first,
        "rounds_latest": rounds_latest,
        "rounds_recent": rounds_recent,
        "sessions_count": sessions_count,
        "sessions_recent": sessions_recent,
    }


async def _fetch_player_stats(db: DatabaseAdapter, start_date_str: str) -> dict:
    """Distinct player counts and total kills, overall and in the lookback."""
    players_all_time = await _safe_val(
        db,
        """
        SELECT COUNT(DISTINCT player_guid)
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2)
          AND time_played_seconds > 0
        """,
        metric="players_all_time",
    )
    players_recent = await _safe_val(
        db,
        """
        SELECT COUNT(DISTINCT player_guid)
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2)
          AND time_played_seconds > 0
          AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
        """,
        (start_date_str,),
        metric="players_recent",
    )
    total_kills = await _safe_val(
        db,
        """
        SELECT COALESCE(SUM(kills), 0)
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2)
        """,
        metric="total_kills",
    )
    total_kills_recent = await _safe_val(
        db,
        """
        SELECT COALESCE(SUM(kills), 0)
        FROM player_comprehensive_stats
        WHERE round_number IN (1, 2)
          AND SUBSTR(CAST(round_date AS TEXT), 1, 10) >= CAST($1 AS TEXT)
        """,
        (start_date_str,),
        metric="total_kills_recent",
    )
    return {
        "players_all_time": players_all_time,
        "players_recent": players_recent,
        "total_kills": total_kills,
        "total_kills_recent": total_kills_recent,
    }


async def _fetch_most_active(db: DatabaseAdapter, start_date_str: str) -> tuple:
    """Top player by round count, overall and in the lookback."""
    active_overall = await _safe_one(
        db,
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
        """,
        metric="active_overall",
    )
    active_recent = await _safe_one(
        db,
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
        metric="active_recent",
    )
    return active_overall, active_recent


async def _resolve_active_payload(db: DatabaseAdapter, row) -> dict | None:
    if not row:
        return None
    return {
        "name": await resolve_display_name(db, row[0], row[1] or "Unknown"),
        "rounds": row[2],
    }


@router.get("/stats/overview")
async def get_stats_overview(db: DatabaseAdapter = Depends(get_db)):
    """Get homepage overview statistics."""
    lookback_days = 14
    start_date_str = (
        (datetime.now() - timedelta(days=lookback_days))
        .date()
        .strftime("%Y-%m-%d")
    )

    rounds_stats = await _fetch_rounds_stats(db, start_date_str)
    player_stats = await _fetch_player_stats(db, start_date_str)
    active_overall, active_recent = await _fetch_most_active(db, start_date_str)

    return {
        "rounds": rounds_stats["rounds_count"] or 0,
        "players": player_stats["players_recent"] or 0,
        "sessions": rounds_stats["sessions_count"] or 0,
        "total_kills": player_stats["total_kills"] or 0,
        "rounds_since": rounds_stats["rounds_first"],
        "rounds_latest": rounds_stats["rounds_latest"],
        "rounds_14d": rounds_stats["rounds_recent"] or 0,
        "players_all_time": player_stats["players_all_time"] or 0,
        "players_14d": player_stats["players_recent"] or 0,
        "sessions_14d": rounds_stats["sessions_recent"] or 0,
        "total_kills_14d": player_stats["total_kills_recent"] or 0,
        "most_active_overall": await _resolve_active_payload(db, active_overall),
        "most_active_14d": await _resolve_active_payload(db, active_recent),
        "window_days": lookback_days,
    }


@router.get("/stats/activity-calendar")
async def get_activity_calendar(
    days: int = 90,
    db: DatabaseAdapter = Depends(get_db),
):
    """Return a simple activity calendar (rounds per day) for the last N days."""
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
    except Exception as e:
        logger.warning("[activity-calendar] query failed: %s", e)
        return {"days": lookback_days, "activity": {}}

    activity = {str(row[0]): int(row[1]) for row in rows}
    return {"days": lookback_days, "activity": activity}
