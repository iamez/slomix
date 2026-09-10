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


async def _resolve_guid32(db: DatabaseAdapter, guid: str) -> str | None:
    """The 32-character proximity GUID these tables are keyed by.

    Every link in this product carries the 8-character canonical GUID —
    profiles, leaderboards, the record book, the bot's Discord messages. The
    proximity tables are keyed by the full 32, so an 8-character id passed
    straight through matched nothing and the endpoint answered `{nemesis:
    null, all_pairs: [], total_opponents: 0}`: a perfectly well-formed way of
    saying "this player has no rivals", about a player with fourteen of them.

    Measured 2026-08-28 on dev: vid as `D8423F90` returned 0 opponents, and
    as `D8423F90F045D9D3E2C0550811C5A899` returned 14.

    Returning None here is what lets the caller tell "no rows for this
    player" apart from "wrong shape of id", which the empty answer could not.
    """
    if len(guid) >= 32:
        # A full-length id still has to EXIST. Returning it unchecked made a
        # nonexistent 32-character GUID answer `resolved: true` with an empty
        # list — the same lie this function was written to end, wearing the
        # other id length (Codex on #834).
        row = await db.fetch_one(
            "SELECT killer_guid FROM proximity_kill_outcome WHERE killer_guid = $1 LIMIT 1",
            (guid,),
        )
        if row and row[0]:
            return row[0]
        row = await db.fetch_one(
            "SELECT victim_guid FROM proximity_kill_outcome WHERE victim_guid = $1 LIMIT 1",
            (guid,),
        )
        return row[0] if row and row[0] else None

    row = await db.fetch_one(
        "SELECT MAX(killer_guid) FROM proximity_kill_outcome WHERE killer_guid_canonical = $1",
        (guid,),
    )
    if row and row[0]:
        return row[0]
    # substr(), not LEFT(): the local quick-start runs DATABASE_TYPE=sqlite,
    # which has no LEFT() at all, so a victim-only short GUID raised there
    # while working on PostgreSQL (Codex on #834). substr(x, 1, 8) is the one
    # spelling both accept.
    row = await db.fetch_one(
        "SELECT MAX(victim_guid) FROM proximity_kill_outcome WHERE substr(victim_guid, 1, 8) = $1",
        (guid,),
    )
    return row[0] if row and row[0] else None


@router.get("/rivalries/player/{guid}")
@limiter.limit("10/minute")
async def get_player_rivalries(
    request: Request,
    guid: str,
    db: DatabaseAdapter = Depends(get_db),
):
    """Get nemesis, prey, rival and all H2H pairs for a player.

    Accepts either GUID length. `resolved: false` means no proximity rows
    were ever recorded under this id — which is a different fact from a
    player who was tracked and simply has no rival, and the page says so.
    """
    if not guid or len(guid) < 8:
        raise HTTPException(status_code=400, detail="Invalid GUID format")

    guid32 = await _resolve_guid32(db, guid)
    if not guid32:
        return {
            "status": "ok",
            "resolved": False,
            "player_guid": guid,
            "player_name": None,
            "nemesis": None,
            "prey": None,
            "rival": None,
            "all_pairs": [],
            "total_opponents": 0,
        }

    svc = RivalriesService(db)
    result = await svc.get_player_rivalries(guid32)
    return {"status": "ok", "resolved": True, **result}


@router.get("/rivalries/h2h/{guid1}/{guid2}")
@limiter.limit("10/minute")
async def get_head_to_head(
    request: Request,
    guid1: str,
    guid2: str,
    db: DatabaseAdapter = Depends(get_db),
):
    """Full H2H breakdown between two players. Either GUID length works."""
    if not guid1 or not guid2 or len(guid1) < 8 or len(guid2) < 8:
        raise HTTPException(status_code=400, detail="Invalid GUID format")

    resolved1 = await _resolve_guid32(db, guid1)
    resolved2 = await _resolve_guid32(db, guid2)
    if not resolved1 or not resolved2:
        # Naming WHICH side could not be resolved: "no data" for a pair is
        # useless when one of the two is simply an id this table never saw.
        return {
            "status": "ok",
            "resolved": False,
            "unresolved": [
                g for g, r in ((guid1, resolved1), (guid2, resolved2)) if not r
            ],
            "guid1": guid1,
            "guid2": guid2,
            "p1_name": None,
            "p2_name": None,
            "p1_kills": 0,
            "p2_kills": 0,
            "total": 0,
            "win_rate": 0.0,
            "classification": None,
            "p1_weapons": [],
            "p2_weapons": [],
        }

    svc = RivalriesService(db)
    result = await svc.get_head_to_head(resolved1, resolved2)
    return {"status": "ok", "resolved": True, **result}


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
