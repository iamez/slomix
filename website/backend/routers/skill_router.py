"""
Skill Rating API endpoints (experimental).

Completely isolated from existing routers - new /api/skill/* prefix.
"""

from fastapi import APIRouter, Depends
from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.logging_config import get_app_logger
from website.backend.services.skill_rating_service import (
    compute_and_store_ratings,
    WEIGHTS,
    CONSTANT,
    MIN_ROUNDS,
)

router = APIRouter()
logger = get_app_logger("api.skill")


@router.get("/skill/leaderboard")
async def get_skill_leaderboard(
    limit: int = 50,
    db: DatabaseAdapter = Depends(get_db),
):
    """Skill rating leaderboard. Auto-computes once if table is empty."""

    rows = await db.fetch_all(
        """SELECT player_guid, display_name, et_rating, games_rated,
                  last_rated_at, components
           FROM player_skill_ratings
           ORDER BY et_rating DESC
           LIMIT $1""",
        (limit,),
    )

    if not rows:
        # Auto-compute on first visit
        count = await compute_and_store_ratings(db)
        if count == 0:
            return {"status": "ok", "players": [], "meta": {"total": 0, "min_rounds": MIN_ROUNDS}}

        rows = await db.fetch_all(
            """SELECT player_guid, display_name, et_rating, games_rated,
                      last_rated_at, components
               FROM player_skill_ratings
               ORDER BY et_rating DESC
               LIMIT $1""",
            (limit,),
        )

    import json
    players = []
    for i, r in enumerate(rows):
        components = r[5]
        try:
            if isinstance(components, str):
                components = json.loads(components)
        except (ValueError, json.JSONDecodeError):
            components = {}

        players.append({
            "rank": i + 1,
            "player_guid": r[0],
            "display_name": r[1] or "Unknown",
            "et_rating": float(r[2]),
            "games_rated": int(r[3]),
            "last_rated_at": str(r[4]) if r[4] else None,
            "components": components or {},
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
    # Try GUID first
    row = await db.fetch_one(
        """SELECT player_guid, display_name, et_rating, games_rated,
                  last_rated_at, components
           FROM player_skill_ratings WHERE player_guid = $1""",
        (identifier,),
    )

    # Try name match
    if not row:
        row = await db.fetch_one(
            """SELECT player_guid, display_name, et_rating, games_rated,
                      last_rated_at, components
               FROM player_skill_ratings WHERE LOWER(display_name) = LOWER($1)""",
            (identifier,),
        )

    if not row:
        return {"status": "error", "detail": f"Player '{identifier}' not found or not rated (need {MIN_ROUNDS}+ rounds)"}

    import json
    components = row[5]
    if isinstance(components, str):
        components = json.loads(components)

    # Get rank + total in one query
    rank_row = await db.fetch_one(
        """SELECT rank, total FROM (
            SELECT player_guid,
                   ROW_NUMBER() OVER (ORDER BY et_rating DESC) as rank,
                   COUNT(*) OVER () as total
            FROM player_skill_ratings
        ) sub WHERE player_guid = $1""",
        (row[0],),
    )
    rank = int(rank_row[0]) if rank_row else 0
    total = int(rank_row[1]) if rank_row else 0

    return {
        "status": "ok",
        "player": {
            "player_guid": row[0],
            "display_name": row[1] or "Unknown",
            "et_rating": float(row[2]),
            "games_rated": int(row[3]),
            "last_rated_at": str(row[4]) if row[4] else None,
            "rank": rank,
            "total_rated": total,
            "components": components or {},
        },
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
