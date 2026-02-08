"""Greatshot upload/analysis API endpoints."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from greatshot.config import CONFIG
from website.backend.dependencies import get_db
from website.backend.logging_config import get_app_logger
from website.backend.services.greatshot_jobs import get_greatshot_job_service
from website.backend.services.greatshot_store import get_greatshot_storage


router = APIRouter()
logger = get_app_logger("greatshot.api")
PROJECT_ROOT = Path(__file__).resolve().parents[3]
storage = get_greatshot_storage(PROJECT_ROOT)


class RenderRequest(BaseModel):
    highlight_id: str


def _require_user(request: Request) -> Dict[str, Any]:
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if "id" not in user:
        raise HTTPException(status_code=401, detail="Invalid session user")
    return user


def _parse_json_field(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return None
    return None


@router.post("/greatshot/upload")
async def upload_greatshot(
    request: Request,
    file: UploadFile = File(...),
    db=Depends(get_db),
):
    user = _require_user(request)
    user_id = int(user["id"])

    try:
        saved = await storage.save_upload(file)
    finally:
        await file.close()

    await db.execute(
        """
        INSERT INTO greatshot_demos (
            id,
            user_id,
            original_filename,
            stored_path,
            extension,
            file_size_bytes,
            content_hash_sha256,
            status,
            created_at,
            updated_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, 'uploaded', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (
            saved.demo_id,
            user_id,
            saved.original_filename,
            saved.stored_path,
            saved.extension,
            saved.file_size_bytes,
            saved.content_hash_sha256,
        ),
    )

    await get_greatshot_job_service().enqueue_analysis(saved.demo_id)

    logger.info("Greatshot demo uploaded by user_id=%s demo_id=%s", user_id, saved.demo_id)

    return {
        "demo_id": saved.demo_id,
        "status": "uploaded",
        "max_upload_bytes": CONFIG.max_upload_bytes,
    }


@router.get("/greatshot")
async def list_greatshot(request: Request, db=Depends(get_db)):
    user = _require_user(request)
    user_id = int(user["id"])

    rows = await db.fetch_all(
        """
        SELECT
            id,
            original_filename,
            status,
            error,
            created_at,
            metadata_json,
            warnings_json,
            processing_started_at,
            processing_finished_at,
            (
                SELECT COUNT(*)
                FROM greatshot_highlights h
                WHERE h.demo_id = d.id
            ) AS highlight_count,
            (
                SELECT COUNT(*)
                FROM greatshot_renders r
                JOIN greatshot_highlights h ON h.id = r.highlight_id
                WHERE h.demo_id = d.id
            ) AS render_job_count,
            (
                SELECT COUNT(*)
                FROM greatshot_renders r
                JOIN greatshot_highlights h ON h.id = r.highlight_id
                WHERE h.demo_id = d.id AND r.status = 'rendered'
            ) AS rendered_count
        FROM greatshot_demos d
        WHERE user_id = $1
        ORDER BY created_at DESC
        LIMIT 50
        """,
        (user_id,),
    )

    items: List[Dict[str, Any]] = []
    for row in rows:
        (
            demo_id,
            original_filename,
            status,
            error,
            created_at,
            metadata_json,
            warnings_json,
            started_at,
            finished_at,
            highlight_count,
            render_job_count,
            rendered_count,
        ) = row

        metadata = _parse_json_field(metadata_json) or {}
        warnings = _parse_json_field(warnings_json) or []

        items.append(
            {
                "id": demo_id,
                "filename": original_filename,
                "status": status,
                "error": error,
                "created_at": str(created_at) if created_at else None,
                "processing_started_at": str(started_at) if started_at else None,
                "processing_finished_at": str(finished_at) if finished_at else None,
                "map": metadata.get("map"),
                "duration_ms": metadata.get("duration_ms"),
                "mod": metadata.get("mod"),
                "warnings": warnings,
                "highlight_count": int(highlight_count or 0),
                "render_job_count": int(render_job_count or 0),
                "rendered_count": int(rendered_count or 0),
            }
        )

    return {"items": items}


@router.get("/greatshot/{demo_id}")
async def get_greatshot_detail(demo_id: str, request: Request, db=Depends(get_db)):
    user = _require_user(request)
    user_id = int(user["id"])

    greatshot_row = await db.fetch_one(
        """
        SELECT
            id,
            original_filename,
            status,
            error,
            created_at,
            metadata_json,
            warnings_json,
            analysis_json_path,
            report_txt_path,
            processing_started_at,
            processing_finished_at
        FROM greatshot_demos
        WHERE id = $1 AND user_id = $2
        """,
        (demo_id, user_id),
    )

    if not greatshot_row:
        raise HTTPException(status_code=404, detail="Greatshot entry not found")

    (
        _id,
        original_filename,
        status,
        error,
        created_at,
        metadata_json,
        warnings_json,
        analysis_json_path,
        report_txt_path,
        started_at,
        finished_at,
    ) = greatshot_row

    analysis_row = await db.fetch_one(
        """
        SELECT metadata_json, stats_json, events_json, created_at
        FROM greatshot_analysis
        WHERE demo_id = $1
        """,
        (demo_id,),
    )

    metadata = _parse_json_field(metadata_json) or {}
    warnings = _parse_json_field(warnings_json) or []

    analysis_payload = None
    if analysis_row:
        events = _parse_json_field(analysis_row[2]) or []
        analysis_payload = {
            "metadata": _parse_json_field(analysis_row[0]) or {},
            "stats": _parse_json_field(analysis_row[1]) or {},
            "events": events[:500],
            "events_total": len(events),
            "created_at": str(analysis_row[3]) if analysis_row[3] else None,
        }

    highlight_rows = await db.fetch_all(
        """
        SELECT id, type, player, start_ms, end_ms, score, meta_json, clip_demo_path, created_at
        FROM greatshot_highlights
        WHERE demo_id = $1
        ORDER BY score DESC, start_ms ASC
        """,
        (demo_id,),
    )

    render_rows = await db.fetch_all(
        """
        SELECT r.id, r.highlight_id, r.status, r.mp4_path, r.error, r.created_at, r.updated_at
        FROM greatshot_renders r
        JOIN greatshot_highlights h ON h.id = r.highlight_id
        WHERE h.demo_id = $1
        ORDER BY r.created_at DESC
        """,
        (demo_id,),
    )

    highlights = []
    for row in highlight_rows:
        meta = _parse_json_field(row[6]) or {}
        clip_available = bool(row[7])
        highlights.append(
            {
                "id": row[0],
                "type": row[1],
                "player": row[2],
                "start_ms": row[3],
                "end_ms": row[4],
                "score": row[5],
                "meta": meta,
                "explanation": meta.get("explanation"),
                "clip_demo_path": storage.safe_relative(row[7]) if row[7] else None,
                "clip_download": (
                    f"/api/greatshot/{demo_id}/highlights/{row[0]}/clip"
                    if clip_available
                    else None
                ),
                "created_at": str(row[8]) if row[8] else None,
            }
        )

    renders = [
        {
            "id": row[0],
            "highlight_id": row[1],
            "status": row[2],
            "mp4_path": storage.safe_relative(row[3]) if row[3] else None,
            "video_download": (
                f"/api/greatshot/{demo_id}/renders/{row[0]}/video"
                if row[3]
                else None
            ),
            "error": row[4],
            "created_at": str(row[5]) if row[5] else None,
            "updated_at": str(row[6]) if row[6] else None,
        }
        for row in render_rows
    ]

    return {
        "id": demo_id,
        "filename": original_filename,
        "status": status,
        "error": error,
        "created_at": str(created_at) if created_at else None,
        "processing_started_at": str(started_at) if started_at else None,
        "processing_finished_at": str(finished_at) if finished_at else None,
        "metadata": metadata,
        "warnings": warnings,
        "analysis": analysis_payload,
        "highlights": highlights,
        "renders": renders,
        "downloads": {
            "json": f"/api/greatshot/{demo_id}/report.json" if analysis_json_path else None,
            "txt": f"/api/greatshot/{demo_id}/report.txt" if report_txt_path else None,
        },
    }


async def _artifact_for_user(db, demo_id: str, user_id: int, field_name: str) -> str:
    row = await db.fetch_one(
        f"SELECT {field_name} FROM greatshot_demos WHERE id = $1 AND user_id = $2",
        (demo_id, user_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Greatshot entry not found")
    artifact = row[0]
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not available")
    return artifact


@router.get("/greatshot/{demo_id}/report.json")
async def download_report_json(demo_id: str, request: Request, db=Depends(get_db)):
    user = _require_user(request)
    user_id = int(user["id"])
    artifact_path = await _artifact_for_user(db, demo_id, user_id, "analysis_json_path")
    safe_path = storage.resolve_checked_path(artifact_path)
    return FileResponse(
        str(safe_path),
        media_type="application/json",
        filename=f"{demo_id}.analysis.json",
    )


@router.get("/greatshot/{demo_id}/report.txt")
async def download_report_txt(demo_id: str, request: Request, db=Depends(get_db)):
    user = _require_user(request)
    user_id = int(user["id"])
    artifact_path = await _artifact_for_user(db, demo_id, user_id, "report_txt_path")
    safe_path = storage.resolve_checked_path(artifact_path)
    return FileResponse(
        str(safe_path),
        media_type="text/plain; charset=utf-8",
        filename=f"{demo_id}.report.txt",
    )


@router.post("/greatshot/{demo_id}/highlights/render")
async def queue_highlight_render(
    demo_id: str,
    payload: RenderRequest,
    request: Request,
    db=Depends(get_db),
):
    user = _require_user(request)
    user_id = int(user["id"])

    greatshot_exists = await db.fetch_one(
        "SELECT id FROM greatshot_demos WHERE id = $1 AND user_id = $2",
        (demo_id, user_id),
    )
    if not greatshot_exists:
        raise HTTPException(status_code=404, detail="Greatshot entry not found")

    highlight = await db.fetch_one(
        "SELECT id FROM greatshot_highlights WHERE id = $1 AND demo_id = $2",
        (payload.highlight_id, demo_id),
    )
    if not highlight:
        raise HTTPException(status_code=404, detail="Highlight not found")

    render_id = uuid.uuid4().hex
    await db.execute(
        """
        INSERT INTO greatshot_renders (id, highlight_id, status, mp4_path, error, created_at, updated_at)
        VALUES ($1, $2, 'queued', NULL, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (render_id, payload.highlight_id),
    )

    await get_greatshot_job_service().enqueue_render(render_id)

    return {"render_id": render_id, "status": "queued"}


async def _highlight_clip_for_user(db, demo_id: str, highlight_id: str, user_id: int) -> str:
    row = await db.fetch_one(
        """
        SELECT h.clip_demo_path
        FROM greatshot_highlights h
        JOIN greatshot_demos d ON d.id = h.demo_id
        WHERE h.id = $1 AND h.demo_id = $2 AND d.user_id = $3
        """,
        (highlight_id, demo_id, user_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Highlight not found")
    if not row[0]:
        raise HTTPException(status_code=404, detail="Clip demo not available")
    return str(row[0])


async def _render_video_for_user(db, demo_id: str, render_id: str, user_id: int) -> str:
    row = await db.fetch_one(
        """
        SELECT r.mp4_path
        FROM greatshot_renders r
        JOIN greatshot_highlights h ON h.id = r.highlight_id
        JOIN greatshot_demos d ON d.id = h.demo_id
        WHERE r.id = $1 AND h.demo_id = $2 AND d.user_id = $3
        """,
        (render_id, demo_id, user_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Render job not found")
    if not row[0]:
        raise HTTPException(status_code=404, detail="Rendered video not available")
    return str(row[0])


@router.get("/greatshot/{demo_id}/highlights/{highlight_id}/clip")
async def download_highlight_clip(
    demo_id: str,
    highlight_id: str,
    request: Request,
    db=Depends(get_db),
):
    user = _require_user(request)
    user_id = int(user["id"])
    clip_path = await _highlight_clip_for_user(db, demo_id, highlight_id, user_id)
    safe_path = storage.resolve_checked_path(clip_path)
    return FileResponse(
        str(safe_path),
        media_type="application/octet-stream",
        filename=safe_path.name,
    )


@router.get("/greatshot/{demo_id}/renders/{render_id}/video")
async def download_render_video(
    demo_id: str,
    render_id: str,
    request: Request,
    db=Depends(get_db),
):
    user = _require_user(request)
    user_id = int(user["id"])
    video_path = await _render_video_for_user(db, demo_id, render_id, user_id)
    safe_path = storage.resolve_checked_path(video_path)
    return FileResponse(
        str(safe_path),
        media_type="video/mp4",
        filename=safe_path.name,
    )
