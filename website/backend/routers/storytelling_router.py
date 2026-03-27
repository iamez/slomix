"""
Storytelling Stats API — Kill Impact Score (KIS) endpoints.
"""

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from starlette.requests import Request
from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.logging_config import get_app_logger
from website.backend.rate_limit import limiter
from website.backend.services.storytelling_service import (
    StorytellingService,
    _strip_et_colors,
    CARRIER_KILL_MULTIPLIER,
    CARRIER_CHAIN_MULTIPLIER,
    PUSH_QUALITY_THRESHOLD,
    CROSSFIRE_MULTIPLIER,
    SPAWN_TIMING_BONUS,
    OUTCOME_GIBBED,
    OUTCOME_REVIVED,
    OUTCOME_TAPPED,
    CLASS_WEIGHTS,
    DISTANCE_LONG_RANGE,
    DISTANCE_NORMAL,
    DISTANCE_MELEE,
    SYNERGY_WEIGHTS,
)

router = APIRouter()
logger = get_app_logger("api.storytelling")


def _parse_date(val: str) -> date:
    try:
        return datetime.strptime(val, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")


@router.get("/storytelling/moments")
@limiter.limit("10/minute")
async def get_moments(
    request: Request,
    session_date: str = Query(..., description="Session date (YYYY-MM-DD)"),
    limit: int = Query(default=10, le=50, ge=1),
    db: DatabaseAdapter = Depends(get_db),
):
    """Match Moments — highlight reel of a session."""
    sd = _parse_date(session_date)
    svc = StorytellingService(db)
    moments = await svc.detect_moments(sd, limit=limit)
    return {
        "status": "ok",
        "session_date": session_date,
        "moments": moments,
        "total": len(moments),
    }


@router.get("/storytelling/kill-impact")
@limiter.limit("10/minute")
async def get_kill_impact_leaderboard(
    request: Request,
    session_date: str = Query(..., description="Session date (YYYY-MM-DD)"),
    limit: int = Query(default=20, le=100, ge=1),
    db: DatabaseAdapter = Depends(get_db),
):
    """KIS leaderboard for a session. Lazy-computes if not cached."""
    sd = _parse_date(session_date)
    svc = StorytellingService(db)
    compute_result = await svc.compute_session_kis(sd)
    leaderboard = await svc.get_kis_leaderboard(sd, limit=limit)

    return {
        "status": "ok",
        "session_date": session_date,
        "compute": compute_result,
        "players": leaderboard,
        "entries": leaderboard,
        "total": len(leaderboard),
        "total_kills": sum(p.get("kills", 0) for p in leaderboard),
    }


@router.get("/storytelling/kill-impact/details")
@limiter.limit("10/minute")
async def get_kill_impact_details(
    request: Request,
    session_date: str = Query(..., description="Session date (YYYY-MM-DD)"),
    player_guid: str = Query(..., description="Player GUID"),
    db: DatabaseAdapter = Depends(get_db),
):
    """Per-kill KIS breakdown for a specific player in a session."""
    svc = StorytellingService(db)
    await svc.compute_session_kis(session_date)

    sd = _parse_date(session_date)
    rows = await db.fetch_all("""
        SELECT kill_outcome_id, round_number, round_start_unix, map_name,
               victim_guid, victim_name,
               base_impact, carrier_multiplier, push_multiplier, crossfire_multiplier,
               spawn_multiplier, outcome_multiplier, class_multiplier, distance_multiplier,
               total_impact, is_carrier_kill, is_during_push, is_crossfire,
               is_objective_area, kill_time_ms
        FROM storytelling_kill_impact
        WHERE session_date = $1 AND killer_guid = $2
        ORDER BY total_impact DESC
    """, (sd, player_guid))

    kills = []
    for r in (rows or []):
        kills.append({
            "kill_outcome_id": r[0],
            "round_number": r[1],
            "round_start_unix": r[2],
            "map_name": r[3],
            "victim_guid": r[4],
            "victim_name": _strip_et_colors(r[5] or r[4][:8]),
            "base_impact": float(r[6]),
            "carrier_multiplier": float(r[7]),
            "push_multiplier": float(r[8]),
            "crossfire_multiplier": float(r[9]),
            "spawn_multiplier": float(r[10]),
            "outcome_multiplier": float(r[11]),
            "class_multiplier": float(r[12]),
            "distance_multiplier": float(r[13]),
            "total_impact": float(r[14]),
            "is_carrier_kill": r[15],
            "is_during_push": r[16],
            "is_crossfire": r[17],
            "is_objective_area": r[18],
            "kill_time_ms": r[19],
        })

    # Summary stats
    total_kis = sum(k["total_impact"] for k in kills)
    avg_impact = total_kis / len(kills) if kills else 0

    # Get player name from first kill
    player_name = ""
    if kills:
        name_row = await db.fetch_one(
            "SELECT MAX(killer_name) FROM storytelling_kill_impact WHERE session_date = $1 AND killer_guid = $2",
            (sd, player_guid)
        )
        player_name = _strip_et_colors((name_row[0] if name_row else "") or player_guid[:8])

    return {
        "status": "ok",
        "session_date": session_date,
        "player_guid": player_guid,
        "player_name": player_name,
        "summary": {
            "total_kis": round(total_kis, 1),
            "kills": len(kills),
            "avg_impact": round(avg_impact, 2),
            "carrier_kills": sum(1 for k in kills if k["is_carrier_kill"]),
            "push_kills": sum(1 for k in kills if k["is_during_push"]),
            "crossfire_kills": sum(1 for k in kills if k["is_crossfire"]),
        },
        "kills": kills,
    }


@router.get("/storytelling/formula")
async def get_kis_formula():
    """Return KIS multiplier definitions (transparency endpoint)."""
    return {
        "status": "ok",
        "version": "1.0",
        "name": "Kill Impact Score (KIS)",
        "description": "Contextual kill impact scoring for competitive ET:Legacy. "
                       "Each kill starts at 1.0 base and is multiplied by context factors.",
        "multipliers": {
            "carrier_kill": {
                "value": CARRIER_KILL_MULTIPLIER,
                "description": "Killed flag/document carrier",
            },
            "carrier_chain": {
                "value": CARRIER_CHAIN_MULTIPLIER,
                "description": "Carrier kill + teammate returned objective within 10s",
            },
            "push": {
                "value": "1.0 + quality×0.5 (range 1.45-2.0, requires quality≥0.9 toward objective)",
                "threshold": PUSH_QUALITY_THRESHOLD,
                "description": "Kill during high-quality coordinated team push toward objective",
            },
            "crossfire": {
                "value": CROSSFIRE_MULTIPLIER,
                "description": "Kill as part of executed crossfire setup",
            },
            "spawn_timing": {
                "range": "1.0 - 2.0",
                "bonus": SPAWN_TIMING_BONUS,
                "description": "Bonus based on spawn wave denial (0.0=no denial, 1.0=max denial)",
            },
        },
        "outcome_multipliers": {
            "gibbed": {"value": OUTCOME_GIBBED, "description": "Permanent kill (no revive possible)"},
            "revived": {"value": OUTCOME_REVIVED, "description": "Kill undone by medic revive"},
            "tapped_out": {"value": OUTCOME_TAPPED, "description": "Normal death (tapped out)"},
        },
        "class_weights": {
            k: {"value": v, "description": f"Target was {k}"}
            for k, v in CLASS_WEIGHTS.items()
        },
        "distance_multipliers": {
            "long_range": {"value": DISTANCE_LONG_RANGE, "threshold": ">800u"},
            "normal": {"value": DISTANCE_NORMAL, "threshold": "100-800u"},
            "melee": {"value": DISTANCE_MELEE, "threshold": "<100u"},
        },
        "formula": "total_impact = base(1.0) × carrier × push × crossfire × spawn × outcome × class × distance",
    }


@router.get("/storytelling/synergy")
@limiter.limit("10/minute")
async def get_team_synergy(
    request: Request,
    session_date: str = Query(..., description="Session date (YYYY-MM-DD)"),
    db: DatabaseAdapter = Depends(get_db),
):
    """Team Synergy Score: 5-axis coordination metrics per faction."""
    sd = _parse_date(session_date)
    svc = StorytellingService(db)
    return await svc.compute_team_synergy(sd)


@router.get("/storytelling/win-contribution")
@limiter.limit("10/minute")
async def get_win_contribution(
    request: Request,
    session_date: str = Query(..., description="Session date (YYYY-MM-DD)"),
    db: DatabaseAdapter = Depends(get_db),
):
    """Player Win Contribution (PWC): per-round contribution + Win Impact Score."""
    _parse_date(session_date)  # validate
    svc = StorytellingService(db)
    result = await svc.compute_win_contribution(session_date)
    return {"status": "ok", **result}


@router.get("/storytelling/momentum")
@limiter.limit("10/minute")
async def get_momentum(
    request: Request,
    session_date: str = Query(..., description="Session date (YYYY-MM-DD)"),
    db: DatabaseAdapter = Depends(get_db),
):
    """Momentum chart: per-round team momentum in 30-second windows."""
    sd = _parse_date(session_date)
    svc = StorytellingService(db)
    return await svc.compute_momentum(sd)


@router.get("/storytelling/narrative")
@limiter.limit("10/minute")
async def get_narrative(
    request: Request,
    session_date: str = Query(..., description="Session date (YYYY-MM-DD)"),
    db: DatabaseAdapter = Depends(get_db),
):
    """Session narrative: human-readable summary paragraph."""
    sd = _parse_date(session_date)
    svc = StorytellingService(db)
    return await svc.generate_narrative(sd)
