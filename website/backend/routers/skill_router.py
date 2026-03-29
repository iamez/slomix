"""
Skill Rating API endpoints (experimental).

Completely isolated from existing routers - new /api/skill/* prefix.
"""

import json

from fastapi import APIRouter, Depends

from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.logging_config import get_app_logger
from website.backend.services.skill_rating_service import (
    CONSTANT,
    MIN_ROUNDS,
    WEIGHTS,
    compute_and_store_ratings,
    compute_session_map_ratings,
    compute_session_ratings,
    get_player_session_history,
    get_tier,
)

router = APIRouter()
logger = get_app_logger("api.skill")


def _parse_components(raw) -> dict:
    """Parse components from DB (JSONB or string)."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (ValueError, json.JSONDecodeError):
            pass
    return {}


async def _resolve_guid(db: DatabaseAdapter, identifier: str) -> str | None:
    """Resolve player identifier to GUID (try GUID first, then name)."""
    row = await db.fetch_one(
        "SELECT player_guid FROM player_skill_ratings WHERE player_guid = $1",
        (identifier,),
    )
    if row:
        return row[0]
    row = await db.fetch_one(
        "SELECT player_guid FROM player_skill_ratings WHERE LOWER(display_name) = LOWER($1)",
        (identifier,),
    )
    return row[0] if row else None


@router.get("/skill/leaderboard")
async def get_skill_leaderboard(
    limit: int = 50,
    db: DatabaseAdapter = Depends(get_db),
):
    """Skill rating leaderboard. Auto-refreshes if stale (>1 hour since last compute)."""

    rows = await db.fetch_all(
        """SELECT player_guid, display_name, et_rating, games_rated,
                  last_rated_at, components
           FROM player_skill_ratings
           ORDER BY et_rating DESC
           LIMIT $1""",
        (limit,),
    )

    # Auto-refresh if empty or stale (last computed >1 hour ago)
    needs_refresh = not rows
    if rows and not needs_refresh:
        staleness = await db.fetch_val(
            "SELECT EXTRACT(EPOCH FROM (NOW() - MAX(last_rated_at))) FROM player_skill_ratings"
        )
        needs_refresh = staleness is not None and float(staleness) > 3600

    if needs_refresh:
        count = await compute_and_store_ratings(db)
        if count == 0 and not rows:
            return {"status": "ok", "players": [], "meta": {"total": 0, "min_rounds": MIN_ROUNDS}}

        rows = await db.fetch_all(
            """SELECT player_guid, display_name, et_rating, games_rated,
                      last_rated_at, components
               FROM player_skill_ratings
               ORDER BY et_rating DESC
               LIMIT $1""",
            (limit,),
        )

    players = []
    for i, r in enumerate(rows):
        players.append({
            "rank": i + 1,
            "player_guid": r[0],
            "display_name": r[1] or "Unknown",
            "et_rating": float(r[2]),
            "games_rated": int(r[3]),
            "last_rated_at": str(r[4]) if r[4] else None,
            "components": _parse_components(r[5]),
            "confidence": round(min(1.0, int(r[3]) / 30), 2),
            "tier": get_tier(float(r[2])),
        })

    return {
        "status": "ok",
        "players": players,
        "meta": {
            "total": len(players),
            "min_rounds": MIN_ROUNDS,
            "weights": WEIGHTS,
            "constant": CONSTANT,
            "version": "1.0",
        },
    }


@router.get("/skill/player/{identifier}")
async def get_player_skill(
    identifier: str,
    db: DatabaseAdapter = Depends(get_db),
):
    """Get skill rating for a specific player (by GUID or name)."""
    row = await db.fetch_one(
        """SELECT player_guid, display_name, et_rating, games_rated,
                  last_rated_at, components
           FROM player_skill_ratings WHERE player_guid = $1""",
        (identifier,),
    )

    if not row:
        row = await db.fetch_one(
            """SELECT player_guid, display_name, et_rating, games_rated,
                      last_rated_at, components
               FROM player_skill_ratings WHERE LOWER(display_name) = LOWER($1)""",
            (identifier,),
        )

    if not row:
        return {"status": "error", "detail": f"Player '{identifier}' not found or not rated (need {MIN_ROUNDS}+ rounds)"}

    rank_row = await db.fetch_one(
        """SELECT rank, total FROM (
            SELECT player_guid,
                   ROW_NUMBER() OVER (ORDER BY et_rating DESC) as rank,
                   COUNT(*) OVER () as total
            FROM player_skill_ratings
        ) sub WHERE player_guid = $1""",
        (row[0],),
    )

    return {
        "status": "ok",
        "player": {
            "player_guid": row[0],
            "display_name": row[1] or "Unknown",
            "et_rating": float(row[2]),
            "games_rated": int(row[3]),
            "last_rated_at": str(row[4]) if row[4] else None,
            "rank": int(rank_row[0]) if rank_row else 0,
            "total_rated": int(rank_row[1]) if rank_row else 0,
            "components": _parse_components(row[5]),
            "confidence": round(min(1.0, int(row[3]) / 30), 2),
            "tier": get_tier(float(row[2])),
        },
    }


# ---------------------------------------------------------------------------
# History endpoints — session/map scoped
# ---------------------------------------------------------------------------

@router.get("/skill/player/{identifier}/history")
async def get_player_skill_history(
    identifier: str,
    range_days: int = 30,
    session_date: str | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    """
    Rating history for a player.

    Without session_date: returns per-session ratings over time (FACEIT-style sparkline data).
      Each entry has: session_date, session_rating, cumulative_rating, delta, rounds, maps.

    With session_date: drill-down into a specific session showing per-map breakdown.
      Each entry has: map_name, map_rating, rounds, components.

    Query params:
      - range_days: 7, 30, 90, 365, 3650 (default: 30)
      - session_date: ISO date (e.g. 2026-03-25) for map drill-down
    """
    safe_range = max(1, min(range_days, 3650))

    guid = await _resolve_guid(db, identifier)
    if not guid:
        return {"status": "error", "detail": f"Player '{identifier}' not found"}

    # Drill-down: specific session → per-map breakdown
    if session_date:
        session_result = await compute_session_ratings(db, guid, session_date)
        maps = await compute_session_map_ratings(db, guid, session_date)

        return {
            "status": "ok",
            "player_guid": guid,
            "session_date": session_date,
            "session_summary": session_result,
            "maps": maps,
        }

    # Overview: per-session ratings over time range
    sessions = await get_player_session_history(db, guid, safe_range)

    return {
        "status": "ok",
        "player_guid": guid,
        "range_days": safe_range,
        "sessions": sessions,
        "total_sessions": len(sessions),
    }


@router.get("/skill/formula")
async def get_skill_formula():
    """Return the current rating formula details (transparency)."""
    return {
        "status": "ok",
        "version": "1.0",
        "name": "ET Rating (Option C)",
        "description": "Individual performance rating inspired by HLTV 2.0, Valorant ACS, and PandaSkill research",
        "formula": "ET_Rating = constant + sum(weight_i * percentile(metric_i))",
        "constant": CONSTANT,
        "weights": WEIGHTS,
        "min_rounds": MIN_ROUNDS,
        "metrics": {
            "dpm": "Damage per minute (alive time)",
            "kpr": "Kills per round",
            "dpr": "Deaths per round (penalty - negative weight)",
            "revive_rate": "Revives given per round (medic value)",
            "objective_rate": "Objectives completed per round (engineer value)",
            "survival_rate": "Fraction of round time spent alive",
            "useful_kill_rate": "Useful kills / total kills",
            "denied_playtime_pm": "Enemy playtime denied per minute",
            "accuracy": "Weapon accuracy",
        },
        "normalization": "Percentile rank (0.0 = worst, 1.0 = best) against all rated players",
        "range": "0.00 (theoretical min) to ~1.15 (exceptional), avg ~0.55",
    }
