"""Records sub-router: Player vs player stats endpoint."""

from fastapi import APIRouter, Depends, Query

from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.logging_config import get_app_logger

router = APIRouter()
logger = get_app_logger("api.records.player")


@router.get("/player/{guid}/vs-stats")
async def get_player_vs_stats(
    guid: str,
    scope: str = "all",
    round_id: int | None = None,
    session_id: int | None = None,
    limit: int = Query(default=10, le=50),
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Player vs player stats -- Easiest Preys and Worst Enemies.
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

    # Easiest Preys -- opponents this player killed most (player is the attacker)
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

    # Worst Enemies -- opponents who killed this player most (player is the subject/victim)
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
