"""Upload Library API endpoints - configs, HUDs, archives, and clips."""

from __future__ import annotations

import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from website.backend.dependencies import _configured_admin_ids, get_db, require_admin_user
from website.backend.logging_config import get_app_logger
from website.backend.middleware.auth_helpers import require_ajax_csrf_header

logger = get_app_logger("uploads.api")

router = APIRouter()

# ---------------------------------------------------------------------------
# Rate limiter (in-memory, resets on restart -- sufficient for single-process)
# ---------------------------------------------------------------------------

_rate_window: dict[int, list[float]] = defaultdict(list)
_last_rate_cleanup: float = 0.0
RATE_LIMIT_PER_HOUR = 10


# An upload is visible only while it is active AND has not lapsed. NULL
# expires_at means "keep forever", which is the default and what every row
# uploaded before migration 070 carries — so this clause is a no-op for them.
#
# Kept as one string rather than repeated inline: it appears in five queries,
# and a filter that is right in four places out of five is worse than no filter,
# because the library and the download endpoint would then disagree.
_LIVE = "status = 'active' AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)"
_LIVE_U = _LIVE.replace("status", "u.status").replace("expires_at", "u.expires_at")

# What the upload form offers. Lifetime is the default and is expressed as NULL,
# not as a very large number of days — "forever" and "expires in 100 years" are
# different promises and only one of them is true.
_RETENTION_DAYS = {7, 30, 90}

# Upload ids are uuid4().hex — exactly 32 lowercase hex chars. Validate before
# touching the DB so a malformed id is a clean 400, not a 404 after a pointless
# query (repo convention for router identifiers).
_UPLOAD_ID_RE = re.compile(r"[0-9a-f]{32}\Z")


def _require_valid_upload_id(upload_id: str) -> None:
    if not _UPLOAD_ID_RE.match(upload_id or ""):
        raise HTTPException(status_code=400, detail="Invalid upload id")


def _may_delete(request: Request, uploader_discord_id: int | None) -> bool:
    """Whether the current session may delete this upload: uploader, or admin.

    Same rule the DELETE endpoint enforces. Kept next to it so the button the
    user sees and the answer they get cannot drift apart.
    """
    user = request.session.get("user") or {}
    try:
        viewer = int(user.get("id"))
    except (TypeError, ValueError):
        return False
    return viewer == uploader_discord_id or viewer in _configured_admin_ids()


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

def _require_user(request: Request) -> dict[str, Any]:
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if "id" not in user:
        raise HTTPException(status_code=401, detail="Invalid session user")
    return user


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
    # Optional client-captured JPEG poster (first frame of a clip). Decorative —
    # a missing/invalid poster never fails the upload (Faza 2).
    poster: UploadFile | None = File(None),
    # Form(...), not bare defaults. A plain scalar on a POST is a QUERY
    # parameter to FastAPI, while the upload form sends multipart/form-data —
    # so these never arrived. Measured before the fix: of 5 uploads in the dev
    # database, 0 had a title different from the filename, 0 had a description,
    # and upload_tags held 0 rows. The Title / Description / Tags inputs had
    # never done anything, and retention_days would have been silently dropped
    # the same way.
    title: str = Form(""),
    description: str = Form(""),
    tags: str = Form(""),
    category: str = Form(""),
    retention_days: int | None = Form(None),
    db=Depends(get_db),
):
    """Upload a config, HUD, archive, or clip file.

    retention_days: 7, 30 or 90 to have the upload lapse automatically.
    Omit it (or send nothing) for the default, which is to keep it forever.
    """
    require_ajax_csrf_header(request)  # CSRF: state-changing, requires X-Requested-With
    user = _require_user(request)
    discord_id = int(user["id"])
    username = user.get("username", "Unknown")

    _check_rate_limit(discord_id)

    # Input validation comes AFTER the CSRF and session gates, not before: an
    # unauthenticated caller should be turned away by 403, not told which
    # retention values this endpoint accepts. Putting it first also broke
    # test_uploads_csrf, which asserts a missing CSRF header is what fails.
    if retention_days is not None and retention_days not in _RETENTION_DAYS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid retention_days. Allowed: {sorted(_RETENTION_DAYS)}, or omit for lifetime",
        )

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

    # Store the poster only for browser-playable clips (.mp4); best-effort, so a
    # bad poster leaves poster_path NULL and the card falls back to the icon.
    poster_rel = None
    if poster is not None and saved.extension == ".mp4":
        poster_rel = await storage.save_poster(saved.upload_id, saved.category, poster)

    # Insert metadata into DB
    try:
        await db.execute(
            """
            INSERT INTO uploads
                (id, uploader_discord_id, uploader_name, category, title, description,
                 original_filename, stored_path, extension, file_size_bytes,
                 content_hash_sha256, mime_type, poster_path, status, expires_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$14,'active',
                    CASE WHEN $13::int IS NULL THEN NULL
                         ELSE CURRENT_TIMESTAMP + ($13::int * INTERVAL '1 day') END)
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
                retention_days,
                poster_rel,
            ),
        )
    except Exception as e:
        # Rollback files on DB failure. Delete the poster FIRST: delete_upload()
        # rmdir's the upload directory after removing the original, which a
        # leftover poster.jpg would block — orphaning the whole directory.
        if poster_rel:
            try:
                storage.delete_upload(poster_rel)
            except Exception as poster_err:
                logger.warning("⚠️ Poster rollback failed (orphaned poster): %s", poster_err)
        try:
            storage.delete_upload(saved.stored_path)
        except Exception as cleanup_err:
            logger.warning("⚠️ File rollback also failed (orphaned file): %s", cleanup_err)
        logger.error("Upload DB insert failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save upload metadata") from e

    # Insert tags (normalize unicode, strip non-alphanumeric)
    failed_tags: list[str] = []
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
                logger.warning(
                    "Tag insert failed for upload %s, tag '%s': %s",
                    saved.upload_id, tag, e,
                )
                failed_tags.append(tag)

    if failed_tags:
        logger.warning(
            "Upload %s: %d/%d tags failed to save: %s",
            saved.upload_id, len(failed_tags), len(tag_list), failed_tags,
        )

    logger.info(
        "File uploaded: id=%s user=%s category=%s size=%d",
        saved.upload_id, discord_id, saved.category, saved.file_size_bytes,
    )

    response = {
        "upload_id": saved.upload_id,
        "filename": saved.original_filename,
        "title": safe_title,
        "category": saved.category,
        "file_size_bytes": saved.file_size_bytes,
        "share_url": f"/share/{saved.upload_id}",
    }

    if failed_tags:
        response["failed_tags"] = failed_tags
        response["warning"] = f"{len(failed_tags)} tag(s) failed to save: {', '.join(failed_tags)}"

    return response


# ---------------------------------------------------------------------------
# GET /api/uploads  —  Browse/search uploads (public)
# ---------------------------------------------------------------------------

# sort key -> ORDER BY clause (whitelist — never interpolate user input).
_UPLOAD_SORTS = {
    "newest": "u.created_at DESC",
    "oldest": "u.created_at ASC",
    "downloads": "u.download_count DESC, u.created_at DESC",
    "size": "u.file_size_bytes DESC, u.created_at DESC",
    "title": "LOWER(u.title) ASC",
}


@router.get("")
async def list_uploads(
    category: str | None = Query(None, max_length=20),
    tag: str | None = Query(None, max_length=50),
    search: str | None = Query(None, max_length=100),
    uploader: int | None = None,
    sort: str = Query(default="newest", max_length=12),
    limit: int = Query(default=50, le=100, ge=1),
    offset: int = Query(default=0, ge=0),
    db=Depends(get_db),
):
    """Browse public uploads with optional filters."""
    if sort not in _UPLOAD_SORTS:
        raise HTTPException(status_code=400, detail=f"Invalid sort. Allowed: {sorted(_UPLOAD_SORTS)}")
    conditions = [_LIVE_U]
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
               u.download_count, u.created_at, LEFT(COALESCE(u.description, ''), 160),
               u.expires_at, u.poster_path
        FROM uploads u
        WHERE {where}
        ORDER BY {_UPLOAD_SORTS[sort]}
        LIMIT ${idx} OFFSET ${idx + 1}
    """  # nosec B608 - where built from whitelisted clauses, sort from _UPLOAD_SORTS literal map; all values $N-bound

    rows = await db.fetch_all(data_q, tuple(params))

    items = [
        {
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
            "description_preview": r[10] or None,
            # NULL means the uploader chose to keep it forever, which is the
            # default; a value is the deadline after which it stops appearing.
            "expires_at": str(r[11]) if r[11] else None,
            "share_url": f"/share/{r[0]}",
            # Poster thumbnail URL when one was captured; None → card shows the
            # category icon (older uploads, non-clips).
            "poster_url": f"/api/uploads/{r[0]}/poster" if r[12] else None,
        }
        for r in rows
    ]

    return {"items": items, "total": total or 0, "limit": limit, "offset": offset, "sort": sort}


# ---------------------------------------------------------------------------
# GET /api/uploads/{upload_id}  —  Get upload details
# ---------------------------------------------------------------------------

@router.get("/{upload_id}")
async def get_upload(upload_id: str, request: Request, db=Depends(get_db)):
    """Get details for a specific upload.

    Includes `can_delete` for the CURRENT session, so the client renders the
    delete affordance from the server's answer instead of re-deriving it. The
    admin list stays server-side — the browser is told what this user may do
    with this upload, not who the admins are. Read-only; nothing is written.
    """
    row = await db.fetch_one(
        f"""
        SELECT id, title, description, original_filename, category, extension,
               file_size_bytes, mime_type, uploader_name, uploader_discord_id,
               download_count, content_hash_sha256, created_at, expires_at,
               poster_path
        FROM uploads
        WHERE id = $1 AND {_LIVE}
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
        "expires_at": str(row[13]) if row[13] else None,
        "can_delete": _may_delete(request, row[9]),
        "tags": tags,
        "share_url": f"/share/{row[0]}",
        "download_url": f"/api/uploads/{row[0]}/download",
        "is_playable": row[5] == ".mp4",
        "poster_url": f"/api/uploads/{row[0]}/poster" if row[14] else None,
    }


# ---------------------------------------------------------------------------
# GET /api/uploads/{upload_id}/download  —  Download file
# ---------------------------------------------------------------------------

@router.get("/{upload_id}/download")
async def download_upload(
    upload_id: str,
    force_download: bool = False,
    db=Depends(get_db),
    range: str | None = Header(None),
):
    """Download an uploaded file with safe headers. Supports Range requests for video seeking."""
    row = await db.fetch_one(
        f"SELECT stored_path, original_filename, mime_type, extension FROM uploads WHERE id = $1 AND {_LIVE}",
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
            logger.debug("Failed to increment download count for upload_id=%s", upload_id, exc_info=True)

    # For MP4, allow inline playback with Range request support for seeking
    if extension.lower() == ".mp4" and not force_download:
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
# GET /api/uploads/{upload_id}/poster  —  Serve the clip's poster thumbnail
# ---------------------------------------------------------------------------

@router.get("/{upload_id}/poster")
async def get_upload_poster(upload_id: str, db=Depends(get_db)):
    """Serve the client-captured JPEG poster for a clip (Faza 2).

    404 when the upload has no poster; the card then falls back to the category
    icon. The image is content-addressed by upload id and never changes, so it
    is served with a long immutable cache.
    """
    _require_valid_upload_id(upload_id)
    row = await db.fetch_one(
        f"SELECT poster_path FROM uploads WHERE id = $1 AND {_LIVE}",
        (upload_id,),
    )
    if not row or not row[0]:
        raise HTTPException(status_code=404, detail="No poster for this upload")

    storage = _get_storage()
    try:
        resolved = storage.resolve_download_path(row[0])
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=404, detail="Poster not found on disk")

    return FileResponse(
        path=str(resolved),
        media_type="image/jpeg",
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; img-src 'self';",
        },
    )


# ---------------------------------------------------------------------------
# DELETE /api/uploads/{upload_id}  —  Delete upload (uploader or admin)
# ---------------------------------------------------------------------------

@router.delete("/{upload_id}")
async def delete_upload(upload_id: str, request: Request, db=Depends(get_db)):
    """Soft-delete an upload. Allowed for the uploader, or for an admin."""
    require_ajax_csrf_header(request)  # CSRF: state-changing, requires X-Requested-With
    user = _require_user(request)
    discord_id = int(user["id"])

    row = await db.fetch_one(
        f"SELECT uploader_discord_id, stored_path, expires_at FROM uploads WHERE id = $1 AND {_LIVE}",
        (upload_id,),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Upload not found")

    # Uploader OR admin. Until now only the uploader could remove a file, which
    # left the library with no way to take anything down — the owner asked for
    # exactly this. Admin identity comes from the same helper the rest of the
    # site uses (WEBSITE_ADMIN_DISCORD_IDS / ADMIN_DISCORD_IDS / OWNER_USER_ID),
    # so there is one definition of "admin" and not a second one here.
    is_admin = discord_id in _configured_admin_ids()
    if row[0] != discord_id and not is_admin:
        logger.warning("Unauthorized delete attempt: upload_id=%s by user=%s (owner=%s)", upload_id, discord_id, row[0])
        raise HTTPException(status_code=403, detail="Not authorized to delete this upload")

    await db.execute(
        "UPDATE uploads SET status = 'deleted', updated_at = CURRENT_TIMESTAMP WHERE id = $1",
        (upload_id,),
    )

    logger.info(
        "Upload deleted: id=%s by user=%s (as %s)",
        upload_id, discord_id, "admin" if row[0] != discord_id else "uploader",
    )
    return {"success": True, "message": "Upload deleted"}


# ---------------------------------------------------------------------------
# POST /api/uploads/sweep-expired  —  remove files whose retention has lapsed
# ---------------------------------------------------------------------------

@router.post("/sweep-expired")
async def sweep_expired_uploads(request: Request, db=Depends(get_db)):
    """Soft-delete lapsed uploads and remove their files. Admin only.

    Expiry is already effective without this: every read filters on
    expires_at, so a lapsed upload leaves the library the moment it lapses.
    This is the step that reclaims the disk.

    Deliberately a POST behind an admin gate rather than a side effect of a
    GET — public read endpoints in this codebase must not write.
    """
    require_ajax_csrf_header(request)
    admin = require_admin_user(request)

    rows = await db.fetch_all(
        "SELECT id, stored_path FROM uploads "
        "WHERE status = 'active' AND expires_at IS NOT NULL AND expires_at <= CURRENT_TIMESTAMP",
        (),
    )
    if not rows:
        return {"success": True, "swept": 0, "file_errors": 0}

    storage = _get_storage()
    swept, file_errors = 0, 0
    for upload_id, stored_path in ((r[0], r[1]) for r in rows):
        # Remove the file FIRST, and only mark the row deleted if that worked.
        #
        # The other order looks safer and is not: marking first means a failed
        # unlink leaves a row the next sweep will never select again, because
        # the sweep looks for status = 'active'. The file would then sit on disk
        # forever with nothing tracking it (CodeRabbit on #615).
        #
        # Leaving the row active on failure is safe here precisely because it
        # has already lapsed: _LIVE hides expired rows from every read, so it
        # cannot be listed or downloaded — it is invisible AND retryable, which
        # is what we want.
        try:
            storage.delete_upload(stored_path)
        except Exception:
            file_errors += 1
            logger.warning(
                "sweep-expired: could not remove file for %s, leaving it active for the next sweep",
                upload_id, exc_info=True,
            )
            continue
        await db.execute(
            "UPDATE uploads SET status = 'deleted', updated_at = CURRENT_TIMESTAMP WHERE id = $1",
            (upload_id,),
        )
        swept += 1

    logger.info(
        "sweep-expired: %s uploads swept, %s file errors, by admin=%s",
        swept, file_errors, admin.get("id"),
    )
    return {"success": True, "swept": swept, "file_errors": file_errors}


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
        f"""
        SELECT t.tag, COUNT(*) as cnt
        FROM upload_tags t
        JOIN uploads u ON u.id = t.upload_id AND {_LIVE_U}
        GROUP BY t.tag
        ORDER BY cnt DESC
        LIMIT $1
        """,
        (limit,),
    )
    return [{"tag": r[0], "count": r[1]} for r in rows]
