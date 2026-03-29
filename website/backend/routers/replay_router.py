"""
Round Replay Timeline Router

GET /api/replay/round/{round_id}/timeline
GET /api/replay/round/{round_id}/positions?t={time_ms}
GET /api/replay/round/{round_id}/paths?from={from_ms}&to={to_ms}
"""
from fastapi import APIRouter, Depends, Query, Request

from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.logging_config import get_app_logger
from website.backend.rate_limit import limiter
from website.backend.services import replay_service

logger = get_app_logger("api.replay")
router = APIRouter()


@router.get("/replay/round/{round_id}/timeline")
@limiter.limit("10/minute")
async def get_round_timeline(
    round_id: int,
    request: Request,
    db: DatabaseAdapter = Depends(get_db),
):
    """Get chronological timeline of all events in a round."""
    logger.info(f"Timeline requested for round {round_id}")
    return await replay_service.get_round_timeline(db, round_id)


@router.get("/replay/round/{round_id}/positions")
@limiter.limit("10/minute")
async def get_player_positions(
    round_id: int,
    request: Request,
    t: int = Query(..., description="Time in milliseconds"),
    db: DatabaseAdapter = Depends(get_db),
):
    """Get all player positions at a specific time T."""
    return await replay_service.get_player_positions(db, round_id, t)


@router.get("/replay/round/{round_id}/paths")
@limiter.limit("10/minute")
async def get_player_paths(
    round_id: int,
    request: Request,
    from_ms: int = Query(..., alias="from", description="Start time in ms"),
    to_ms: int = Query(..., alias="to", description="End time in ms"),
    db: DatabaseAdapter = Depends(get_db),
):
    """Get player movement paths for a time window (for trail rendering)."""
    return await replay_service.get_player_paths(db, round_id, from_ms, to_ms)
