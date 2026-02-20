"""Upload Library API endpoints - configs, HUDs, archives, and clips."""

from __future__ import annotations

import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from website.backend.dependencies import get_db
from website.backend.logging_config import get_app_logger

logger = get_app_logger("uploads.api")

router = APIRouter()

# ---------------------------------------------------------------------------
# Rate limiter (in-memory, resets on restart -- sufficient for single-process)
# ---------------------------------------------------------------------------

_rate_window: Dict[int, List[float]] = defaultdict(list)
_last_rate_cleanup: float = 0.0
RATE_LIMIT_PER_HOUR = 10


def _check_rate_limit(discord_id: int) -> None:
    global _last_rate_cleanup
    now = time.time()
    cutoff = now - 3600

    # Periodic cleanup of stale entries to prevent memory leak
    if now - _last_rate_cleanup > 3600:
        for uid in list(_rate_window.keys()):
            _rate_window[uid] = [t for t in _rate_window[uid] if t > cutoff]
            if not _rate_window[uid]:
                del _rate_window[uid]
        _last_rate_cleanup = now

    recent = [t for t in _rate_window[discord_id] if t > cutoff]
    _rate_window[discord_id] = recent
    if len(recent) >= RATE_LIMIT_PER_HOUR:
        raise HTTPException(status_code=429, detail="Upload rate limit exceeded (10/hour)")
    recent.append(now)


# ---------------------------------------------------------------------------
# Auth helper (mirrors greatshot pattern)
# ---------------------------------------------------------------------------

def _require_user(request: Request) -> Dict[str, Any]:
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if "id" not in user:
        raise HTTPException(status_code=401, detail="Invalid session user")
    return user


def _optional_user(request: Request) -> Optional[Dict[str, Any]]:
    user = request.session.get("user")
    if user and "id" in user:
        return user
    return None


# ---------------------------------------------------------------------------
# Lazy storage import (avoid import-time side effects)
# ---------------------------------------------------------------------------

def _get_storage():
    from website.backend.services.upload_store import get_upload_storage
    return get_upload_storage()


def _get_validators():
    from website.backend.services import upload_validators as v
    return v


# ---------------------------------------------------------------------------
# POST /api/uploads  —  Upload a file
# ---------------------------------------------------------------------------

@router.post("")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    title: str = "",
    description: str = "",
    tags: str = "",
    category: str = "",
    db=Depends(get_db),
):
    """Upload a config, HUD, archive, or clip file."""
    user = _require_user(request)
    discord_id = int(user["id"])
    username = user.get("username", "Unknown")

    _check_rate_limit(discord_id)

    v = _get_validators()
    storage = _get_storage()

    # Auto-detect category from extension if not provided
    if not category:
        ext = Path(file.filename or "").suffix.lower()
        category = v.detect_category(ext)
        if not category:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type '{ext}'. Allowed: .cfg .hud .zip .rar .mp4 .avi .mkv",
            )

    # Save file (validates extension, size, magic bytes internally)
    try:
        saved = await storage.save_upload(file, category)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Upload save failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Upload failed") from e

    safe_title = (title.strip() or v.sanitize_filename(saved.original_filename, max_len=100))[:200]
    safe_desc = (description.strip())[:2000] if description else None

    # Insert metadata into DB
    try:
        await db.execute(
            """
            INSERT INTO uploads
                (id, uploader_discord_id, uploader_name, category, title, description,
                 original_filename, stored_path, extension, file_size_bytes,
                 content_hash_sha256, mime_type, status)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,'active')
            """,
            (
                saved.upload_id,
                discord_id,
                username,
                saved.category,
                safe_title,
                safe_desc,
                saved.original_filename,
                saved.stored_path,
                saved.extension,
                saved.file_size_bytes,
                saved.content_hash_sha256,
                v.get_content_type(saved.extension),
            ),
        )
    except Exception as e:
        # Rollback file on DB failure
        try:
            storage.delete_upload(saved.stored_path)
        except Exception:
            pass
        logger.error("Upload DB insert failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save upload metadata") from e

    # Insert tags (normalize unicode, strip non-alphanumeric)
    if tags.strip():
        import re
        import unicodedata
        raw_tags = [t.strip().lower() for t in tags.split(",") if t.strip()]
        tag_list = []
        for t in raw_tags:
            t = unicodedata.normalize('NFKC', t)
            t = re.sub(r'[^\w\-\s]', '', t).strip()[:50]
            if t and t not in tag_list:
                tag_list.append(t)
            if len(tag_list) >= 10:
                break
        for tag in tag_list:
            try:
                await db.execute(
                    "INSERT INTO upload_tags (upload_id, tag) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                    (saved.upload_id, tag),
                )
            except Exception as e:
                logger.warning("Tag insert failed for %s: %s", tag, e)

    logger.info(
        "File uploaded: id=%s user=%s category=%s size=%d",
        saved.upload_id, discord_id, saved.category, saved.file_size_bytes,
    )

    return {
        "upload_id": saved.upload_id,
        "filename": saved.original_filename,
        "title": safe_title,
        "category": saved.category,
        "file_size_bytes": saved.file_size_bytes,
        "share_url": f"/share/{saved.upload_id}",
    }


# ---------------------------------------------------------------------------
# GET /api/uploads  —  Browse/search uploads (public)
# ---------------------------------------------------------------------------

@router.get("")
async def list_uploads(
    category: Optional[str] = Query(None, max_length=20),
    tag: Optional[str] = Query(None, max_length=50),
    search: Optional[str] = Query(None, max_length=100),
    uploader: Optional[int] = None,
    limit: int = Query(default=50, le=100, ge=1),
    offset: int = Query(default=0, ge=0),
    db=Depends(get_db),
):
    """Browse public uploads with optional filters."""
    conditions = ["u.status = 'active'"]
    params: list = []
    idx = 1

    if category:
        valid_categories = {"config", "hud", "archive", "clip"}
        if category not in valid_categories:
            raise HTTPException(status_code=400, detail=f"Invalid category. Allowed: {sorted(valid_categories)}")
        conditions.append(f"u.category = ${idx}")
        params.append(category)
        idx += 1

    if uploader:
        conditions.append(f"u.uploader_discord_id = ${idx}")
        params.append(uploader)
        idx += 1

    if search:
        safe_search = search.replace("%", "\\%").replace("_", "\\_")
        conditions.append(f"(LOWER(u.title) LIKE LOWER(${idx}) OR LOWER(u.original_filename) LIKE LOWER(${idx}))")
        params.append(f"%{safe_search}%")
        idx += 1

    if tag:
        conditions.append(f"EXISTS (SELECT 1 FROM upload_tags t WHERE t.upload_id = u.id AND t.tag = ${idx})")
        params.append(tag.strip().lower())
        idx += 1

    where = " AND ".join(conditions)

    count_q = f"SELECT COUNT(*) FROM uploads u WHERE {where}"
    total = await db.fetch_val(count_q, tuple(params))

    params.extend([limit, offset])
    data_q = f"""
        SELECT u.id, u.title, u.original_filename, u.category, u.extension,
               u.file_size_bytes, u.uploader_name, u.uploader_discord_id,
               u.download_count, u.created_at
        FROM uploads u
        WHERE {where}
        ORDER BY u.created_at DESC
        LIMIT ${idx} OFFSET ${idx + 1}
    """

    rows = await db.fetch_all(data_q, tuple(params))

    items = []
    for r in rows:
        items.append({
            "id": r[0],
            "title": r[1],
            "filename": r[2],
            "category": r[3],
            "extension": r[4],
            "file_size_bytes": r[5],
            "uploader_name": r[6],
            "uploader_discord_id": r[7],
            "download_count": r[8],
            "created_at": str(r[9]) if r[9] else None,
            "share_url": f"/share/{r[0]}",
        })

    return {"items": items, "total": total or 0, "limit": limit, "offset": offset}


# ---------------------------------------------------------------------------
# GET /api/uploads/{upload_id}  —  Get upload details
# ---------------------------------------------------------------------------

@router.get("/{upload_id}")
async def get_upload(upload_id: str, db=Depends(get_db)):
    """Get details for a specific upload."""
    row = await db.fetch_one(
        """
        SELECT id, title, description, original_filename, category, extension,
               file_size_bytes, mime_type, uploader_name, uploader_discord_id,
               download_count, content_hash_sha256, created_at
        FROM uploads
        WHERE id = $1 AND status = 'active'
        """,
        (upload_id,),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Upload not found")

    # Fetch tags
    tag_rows = await db.fetch_all(
        "SELECT tag FROM upload_tags WHERE upload_id = $1",
        (upload_id,),
    )
    tags = [t[0] for t in tag_rows] if tag_rows else []

    return {
        "id": row[0],
        "title": row[1],
        "description": row[2],
        "filename": row[3],
        "category": row[4],
        "extension": row[5],
        "file_size_bytes": row[6],
        "mime_type": row[7],
        "uploader_name": row[8],
        "uploader_discord_id": row[9],
        "download_count": row[10],
        "content_hash": row[11],
        "created_at": str(row[12]) if row[12] else None,
        "tags": tags,
        "share_url": f"/share/{row[0]}",
        "download_url": f"/api/uploads/{row[0]}/download",
        "is_playable": row[5] in (".mp4",),
    }


# ---------------------------------------------------------------------------
# GET /api/uploads/{upload_id}/download  —  Download file
# ---------------------------------------------------------------------------

@router.get("/{upload_id}/download")
async def download_upload(
    upload_id: str,
    db=Depends(get_db),
    range: Optional[str] = Header(None),
):
    """Download an uploaded file with safe headers. Supports Range requests for video seeking."""
    row = await db.fetch_one(
        "SELECT stored_path, original_filename, mime_type, extension FROM uploads WHERE id = $1 AND status = 'active'",
        (upload_id,),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Upload not found")

    stored_path, original_filename, mime_type, extension = row[0], row[1], row[2], row[3]

    storage = _get_storage()
    try:
        resolved = storage.resolve_download_path(stored_path)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=404, detail="File not found on disk")

    v = _get_validators()
    safe_name = v.sanitize_filename(original_filename)

    # Increment download count (fire-and-forget, only on full requests not range)
    if not range:
        try:
            await db.execute(
                "UPDATE uploads SET download_count = download_count + 1 WHERE id = $1",
                (upload_id,),
            )
        except Exception:
            pass

    # For MP4, allow inline playback with Range request support for seeking
    if extension.lower() == ".mp4":
        file_size = resolved.stat().st_size

        base_headers = {
            "Accept-Ranges": "bytes",
            "Content-Disposition": f'inline; filename="{safe_name}"',
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; media-src 'self';",
        }

        # Handle Range requests (video seeking)
        if range and range.startswith("bytes="):
            range_spec = range[6:]
            parts = range_spec.split("-", 1)
            try:
                start = int(parts[0]) if parts[0] else 0
                end = int(parts[1]) if parts[1] else file_size - 1
            except ValueError:
                raise HTTPException(status_code=416, detail="Invalid range")

            if start >= file_size or end >= file_size or start > end:
                raise HTTPException(
                    status_code=416,
                    detail="Range not satisfiable",
                    headers={"Content-Range": f"bytes */{file_size}"},
                )

            content_length = end - start + 1

            def iter_range():
                with open(resolved, "rb") as f:
                    f.seek(start)
                    remaining = content_length
                    while remaining > 0:
                        chunk = f.read(min(65536, remaining))
                        if not chunk:
                            break
                        remaining -= len(chunk)
                        yield chunk

            return StreamingResponse(
                iter_range(),
                status_code=206,
                media_type="video/mp4",
                headers={
                    **base_headers,
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Content-Length": str(content_length),
                },
            )

        # Full file response
        return FileResponse(
            path=str(resolved),
            media_type="video/mp4",
            filename=safe_name,
            headers={
                **base_headers,
                "Content-Length": str(file_size),
            },
        )

    # For everything else, force download
    return FileResponse(
        path=str(resolved),
        media_type=mime_type or "application/octet-stream",
        filename=safe_name,
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'",
            "X-Frame-Options": "DENY",
        },
    )


# ---------------------------------------------------------------------------
# DELETE /api/uploads/{upload_id}  —  Delete upload (owner only)
# ---------------------------------------------------------------------------

@router.delete("/{upload_id}")
async def delete_upload(upload_id: str, request: Request, db=Depends(get_db)):
    """Soft-delete an upload (owner only)."""
    user = _require_user(request)
    discord_id = int(user["id"])

    row = await db.fetch_one(
        "SELECT uploader_discord_id, stored_path FROM uploads WHERE id = $1 AND status = 'active'",
        (upload_id,),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Upload not found")

    if row[0] != discord_id:
        logger.warning("Unauthorized delete attempt: upload_id=%s by user=%s (owner=%s)", upload_id, discord_id, row[0])
        raise HTTPException(status_code=403, detail="Not authorized to delete this upload")

    await db.execute(
        "UPDATE uploads SET status = 'deleted', updated_at = CURRENT_TIMESTAMP WHERE id = $1",
        (upload_id,),
    )

    logger.info("Upload deleted: id=%s by user=%s", upload_id, discord_id)
    return {"success": True, "message": "Upload deleted"}


# ---------------------------------------------------------------------------
# GET /api/uploads/tags/popular  —  Popular tags
# ---------------------------------------------------------------------------

@router.get("/tags/popular")
async def popular_tags(
    limit: int = Query(default=20, le=50),
    db=Depends(get_db),
):
    """Get most popular upload tags."""
    rows = await db.fetch_all(
        """
        SELECT t.tag, COUNT(*) as cnt
        FROM upload_tags t
        JOIN uploads u ON u.id = t.upload_id AND u.status = 'active'
        GROUP BY t.tag
        ORDER BY cnt DESC
        LIMIT $1
        """,
        (limit,),
    )
    return [{"tag": r[0], "count": r[1]} for r in rows]
