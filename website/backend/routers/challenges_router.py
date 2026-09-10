"""Challenge of the week (VISION_2026 Sprint S3 "VEČER").

A tiny admin-defined weekly challenge surfaced in the morning digest + home.
One challenge per ISO week (keyed by Monday's date). Public reads; admin-only
writes (require_admin from S2). The bot reads the current week's row for the
digest line.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request

from website.backend.dependencies import get_db, require_admin
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.middleware.auth_helpers import require_ajax_csrf_header

router = APIRouter()

_TITLE_MAX = 80
_DESC_MAX = 280


def _week_start(d: date) -> date:
    """Monday of the ISO week containing d."""
    return d - timedelta(days=d.weekday())


def _serialize(row) -> dict:
    return {
        "week_start_date": str(row[0]),
        "title": row[1],
        "description": row[2],
        "created_at": str(row[3]) if row[3] else None,
    }


@router.get("/challenges/current")
async def get_current_challenge(db: DatabaseAdapter = Depends(get_db)):
    """The challenge for the current ISO week (or null)."""
    monday = _week_start(datetime.now().date())  # noqa: DTZ005 local week boundary
    row = await db.fetch_one(
        "SELECT week_start_date, title, description, created_at "
        "FROM weekly_challenges WHERE week_start_date = ?",
        (monday,),
    )
    return {"status": "ok", "week_start_date": str(monday),
            "challenge": _serialize(row) if row else None}


@router.get("/challenges")
async def list_challenges(limit: int = 8, db: DatabaseAdapter = Depends(get_db)):
    """Recent weekly challenges (newest first)."""
    limit = max(1, min(limit, 52))
    rows = await db.fetch_all(
        "SELECT week_start_date, title, description, created_at "
        "FROM weekly_challenges ORDER BY week_start_date DESC LIMIT ?",
        (limit,),
    )
    return {"status": "ok", "challenges": [_serialize(r) for r in (rows or [])]}


@router.post("/challenges")
async def upsert_challenge(
    request: Request,
    payload: dict,
    user: dict = Depends(require_admin),
    db: DatabaseAdapter = Depends(get_db),
):
    """Define/replace a weekly challenge (admin only). Defaults to this week."""
    require_ajax_csrf_header(request)
    title = ((payload or {}).get("title") or "").strip()
    description = ((payload or {}).get("description") or "").strip() or None
    if not title or len(title) > _TITLE_MAX:
        raise HTTPException(status_code=400, detail=f"title required, max {_TITLE_MAX} chars")
    if description and len(description) > _DESC_MAX:
        raise HTTPException(status_code=400, detail=f"description max {_DESC_MAX} chars")

    week_raw = (payload or {}).get("week_start_date")
    if week_raw:
        try:
            base = datetime.strptime(str(week_raw)[:10], "%Y-%m-%d").date()  # noqa: DTZ007
        except ValueError:
            raise HTTPException(status_code=400, detail="week_start_date must be YYYY-MM-DD")
    else:
        base = datetime.now().date()  # noqa: DTZ005 local week boundary
    monday = _week_start(base)

    try:
        creator = int(user["id"])
    except (TypeError, ValueError):
        creator = None

    await db.execute(
        """
        INSERT INTO weekly_challenges (week_start_date, title, description, created_by_user_id)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (week_start_date) DO UPDATE
        SET title = EXCLUDED.title,
            description = EXCLUDED.description,
            updated_at = CURRENT_TIMESTAMP
        """,
        (monday, title, description, creator),
    )
    return {"status": "ok", "week_start_date": str(monday), "title": title}
