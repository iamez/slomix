"""
Player Rivalries API — Nemesis, Prey, Rival detection and H2H analysis.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from starlette.requests import Request

from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.logging_config import get_app_logger
from website.backend.rate_limit import limiter
from website.backend.services.rivalries_service import RivalriesService

router = APIRouter()
logger = get_app_logger("api.rivalries")


@router.get("/rivalries/player/{guid}")
@limiter.limit("10/minute")
async def get_player_rivalries(
    request: Request,
    guid: str,
    db: DatabaseAdapter = Depends(get_db),
):
    """Get nemesis, prey, rival and all H2H pairs for a player."""
    if not guid or len(guid) < 8:
        raise HTTPException(status_code=400, detail="Invalid GUID format")

    svc = RivalriesService(db)
    result = await svc.get_player_rivalries(guid)
    return {"status": "ok", **result}


@router.get("/rivalries/h2h/{guid1}/{guid2}")
@limiter.limit("10/minute")
async def get_head_to_head(
    request: Request,
    guid1: str,
    guid2: str,
    db: DatabaseAdapter = Depends(get_db),
):
    """Full H2H breakdown between two players."""
    if not guid1 or not guid2 or len(guid1) < 8 or len(guid2) < 8:
        raise HTTPException(status_code=400, detail="Invalid GUID format")

    svc = RivalriesService(db)
    result = await svc.get_head_to_head(guid1, guid2)
    return {"status": "ok", **result}


@router.get("/rivalries/leaderboard")
@limiter.limit("10/minute")
async def get_rivalry_leaderboard(
    request: Request,
    limit: int = Query(default=20, le=100, ge=1),
    db: DatabaseAdapter = Depends(get_db),
):
    """Top rivalry pairs by total encounters."""
    svc = RivalriesService(db)
    pairs = await svc.get_rivalry_leaderboard(limit=limit)
    return {"status": "ok", "pairs": pairs, "total": len(pairs)}
