"""Season awards endpoints (VISION_2026 Sprint S4 "TEKMA").

Public reads of engraved season awards; admin recompute + manual insert.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from shared.season_manager import SeasonManager
from website.backend.dependencies import get_db, require_admin
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.middleware.auth_helpers import require_ajax_csrf_header
from website.backend.services import season_awards_service

router = APIRouter()

_AWARD_LABELS = {
    "mvp": "Season MVP",
    "iron_man": "Iron Man",
    "most_improved": "Most Improved",
    "oracle": "Oracle",
}


def _serialize(row) -> dict:
    return {
        "award_key": row[0],
        "label": _AWARD_LABELS.get(row[0], row[0].replace("_", " ").title()),
        "player_guid": row[1],
        "player_name": row[2],
        "value_text": row[3],
        "value_num": row[4],
    }


@router.get("/seasons/{season_id}/awards")
async def get_season_awards(season_id: str, db: DatabaseAdapter = Depends(get_db)):
    """Engraved awards for a season ('current' resolves to the live season)."""
    sid = SeasonManager().get_current_season() if season_id == "current" else season_id
    rows = await db.fetch_all(
        "SELECT award_key, player_guid, player_name, value_text, value_num "
        "FROM season_awards WHERE season_id = ? ORDER BY award_key",
        (sid,),
    )
    return {"status": "ok", "season_id": sid,
            "season_name": SeasonManager().get_season_name(sid),
            "awards": [_serialize(r) for r in (rows or [])]}


@router.post("/seasons/awards/recompute")
async def recompute_season_awards(
    request: Request,
    payload: dict | None = None,
    user: dict = Depends(require_admin),
    db: DatabaseAdapter = Depends(get_db),
):
    """Recompute the season's automatic awards (admin)."""
    require_ajax_csrf_header(request)
    season_id = (payload or {}).get("season_id")
    try:
        created_by = int(user["id"])
    except (TypeError, ValueError):
        created_by = None
    result = await season_awards_service.compute_and_store(db, season_id, created_by)
    return {"status": "ok", **result}


@router.post("/seasons/awards")
async def add_manual_award(
    request: Request,
    payload: dict,
    user: dict = Depends(require_admin),
    db: DatabaseAdapter = Depends(get_db),
):
    """Manually engrave a custom award (admin) — e.g. the wooden spoon."""
    require_ajax_csrf_header(request)
    p = payload or {}
    season_id = (p.get("season_id") or SeasonManager().get_current_season()).strip()
    award_key = (p.get("award_key") or "").strip().lower().replace(" ", "_")
    player_guid = (p.get("player_guid") or "").strip()
    player_name = (p.get("player_name") or "").strip() or None
    value_text = (p.get("value_text") or "").strip() or None
    if not award_key or not player_guid:
        raise HTTPException(status_code=400, detail="award_key and player_guid required")
    if award_key in season_awards_service.AWARD_KEYS:
        raise HTTPException(status_code=400, detail="award_key reserved for auto awards")
    try:
        created_by = int(user["id"])
    except (TypeError, ValueError):
        created_by = None
    await db.execute(
        """
        INSERT INTO season_awards
            (season_id, award_key, player_guid, player_name, value_text, created_by_user_id)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT (season_id, award_key, player_guid) DO UPDATE
        SET player_name = EXCLUDED.player_name, value_text = EXCLUDED.value_text
        """,
        (season_id, award_key, player_guid, player_name, value_text, created_by),
    )
    return {"status": "ok", "season_id": season_id, "award_key": award_key}
