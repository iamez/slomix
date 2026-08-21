"""
Round Replay Timeline Router

GET /api/replay/round/{round_id}/timeline
GET /api/replay/round/{round_id}/positions?t={time_ms}
GET /api/replay/round/{round_id}/paths?from={from_ms}&to={to_ms}
GET /api/replay/round/{round_id}/web?t={time_ms}
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.logging_config import get_app_logger
from website.backend.rate_limit import limiter
from website.backend.services import replay_service, round_web_service

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


@router.get("/replay/round/{round_id}/web")
@limiter.limit("10/minute")
async def get_round_web(
    round_id: int,
    request: Request,
    # ge=0 on both: a negative `t` cannot select a sample, and a negative
    # `max_stale_ms` excludes every state with non-negative staleness — i.e. all
    # of them — which looks like an empty round rather than a bad argument
    # (CodeRabbit, PR #792).
    t: int = Query(..., ge=0, description="Time in milliseconds"),
    max_stale_ms: int | None = Query(
        None, ge=0,
        description="Exclude states older than this; omit to get everything "
                    "with its staleness stated"),
    db: DatabaseAdapter = Depends(get_db),
):
    """Layer 1: the relational reconstruction of one moment.

    Distinct from `/positions`, which serves the replay slider. This one picks
    the LATEST overlapping life rather than the earliest, never answers with a
    sample from after `t`, and carries `stale_ms`, `overlap_conflict` and
    `velocity_reason` alongside the values they qualify.

    ⛔ Reconstruction only — no score, no ranking (spec §4.6). Line-of-sight is
    deliberately absent: it stays unvalidated until W6.
    """
    # A round that does not exist is 404; a round that exists but has no linked
    # tracks is 200 with `unavailable` set. Collapsing the two would tell a
    # caller "no such round" when the round is real and the data is thin — a
    # different problem with a different fix (CodeRabbit, PR #792).
    exists = await db.fetch_all("SELECT 1 FROM rounds WHERE id = $1", (round_id,))
    if not exists:
        raise HTTPException(status_code=404, detail=f"round {round_id} not found")
    return await round_web_service.get_round_snapshot(
        db, round_id, t, max_stale_ms=max_stale_ms
    )
