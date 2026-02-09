"""Storage and persistence helpers for Greatshot upload/analysis artifacts."""

from __future__ import annotations

import hashlib
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, UploadFile

from greatshot.config import CONFIG
from greatshot.scanner.api import sniff_demo_header_bytes
from website.backend.logging_config import get_app_logger


logger = get_app_logger("greatshot.store")


@dataclass
class SavedGreatshotUpload:
    demo_id: str
    original_filename: str
    extension: str
    stored_path: str
    file_size_bytes: int
    content_hash_sha256: str


class GreatshotStorageService:
    def __init__(self, project_root: Path):
        root = CONFIG.storage_root
        if not root.is_absolute():
            root = (project_root / root).resolve()

        self.root = root
        self.max_upload_bytes = int(CONFIG.max_upload_bytes)
        self.allowed_extensions = set(ext.lower() for ext in CONFIG.allow_extensions)
        self.allowed_mime_types = {
            "application/octet-stream",
            "application/x-octet-stream",
            "application/x-et-demo",
            "",
            None,
        }

    def ensure_storage_tree(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.root, 0o750)
        except OSError:
            pass

    def demo_dir(self, demo_id: str) -> Path:
        return self.root / demo_id

    def originals_dir(self, demo_id: str) -> Path:
        return self.demo_dir(demo_id) / "original"

    def artifacts_dir(self, demo_id: str) -> Path:
        return self.demo_dir(demo_id) / "artifacts"

    def clips_dir(self, demo_id: str) -> Path:
        return self.demo_dir(demo_id) / "clips"

    def videos_dir(self, demo_id: str) -> Path:
        return self.demo_dir(demo_id) / "videos"

    def _assert_extension(self, filename: str) -> str:
        ext = Path(filename).suffix.lower()
        if ext not in self.allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file extension '{ext}'. Allowed: {sorted(self.allowed_extensions)}",
            )
        return ext

    def _check_disk_space(self, required_bytes: int = 1024 * 1024 * 100) -> None:
        """Check if sufficient disk space is available (default 100MB minimum).

        Raises HTTPException if disk space is insufficient.
        """
        try:
            import shutil
            stat = shutil.disk_usage(self.root)
            free_bytes = stat.free

            if free_bytes < required_bytes:
                logger.error(f"Insufficient disk space: {free_bytes / (1024**3):.2f}GB free, "
                           f"need at least {required_bytes / (1024**3):.2f}GB")
                raise HTTPException(
                    status_code=507,
                    detail="Insufficient disk space for this operation"
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Could not check disk space: {e}")
            # Don't fail uploads if disk check fails, just log warning

    async def save_upload(self, upload: UploadFile) -> SavedGreatshotUpload:
        self.ensure_storage_tree()

        # Check disk space before accepting upload
        self._check_disk_space(required_bytes=self.max_upload_bytes * 3)  # 3x for processing overhead

        unsafe_name = upload.filename or "upload.dm_84"
        original_filename = Path(unsafe_name).name
        extension = self._assert_extension(original_filename)

        content_type = (upload.content_type or "").lower()
        if content_type not in self.allowed_mime_types:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported MIME type '{content_type or 'unknown'}' for demo upload.",
            )

        demo_id = uuid.uuid4().hex
        originals_dir = self.originals_dir(demo_id)
        originals_dir.mkdir(parents=True, exist_ok=True)

        stored_path = originals_dir / f"original{extension}"

        digest = hashlib.sha256()
        total_bytes = 0
        header_bytes = b""

        with stored_path.open("wb") as handle:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > self.max_upload_bytes:
                    handle.close()
                    try:
                        stored_path.unlink(missing_ok=True)
                    except Exception:
                        pass
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            f"Upload too large ({total_bytes} bytes). "
                            f"Max allowed is {self.max_upload_bytes} bytes."
                        ),
                    )

                if len(header_bytes) < 64:
                    need = 64 - len(header_bytes)
                    header_bytes += chunk[:need]

                digest.update(chunk)
                handle.write(chunk)

        if total_bytes == 0:
            try:
                stored_path.unlink(missing_ok=True)
            except Exception:
                pass
            raise HTTPException(status_code=400, detail="Empty upload is not allowed.")

        try:
            sniff_demo_header_bytes(header_bytes)
        except Exception as exc:
            try:
                stored_path.unlink(missing_ok=True)
            except Exception:
                pass
            raise HTTPException(status_code=400, detail=f"Invalid demo header: {exc}") from exc

        return SavedGreatshotUpload(
            demo_id=demo_id,
            original_filename=original_filename,
            extension=extension,
            stored_path=str(stored_path.resolve()),
            file_size_bytes=total_bytes,
            content_hash_sha256=digest.hexdigest(),
        )

    def safe_relative(self, absolute_path: str | Path) -> Optional[str]:
        try:
            resolved = Path(absolute_path).resolve()
            relative = resolved.relative_to(self.root)
            return str(relative)
        except Exception:
            return None

    def resolve_checked_path(self, raw_path: str) -> Path:
        resolved = Path(raw_path).resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise HTTPException(status_code=403, detail="Invalid artifact path") from exc

        if not resolved.exists() or not resolved.is_file():
            raise HTTPException(status_code=404, detail="Artifact file not found")
        return resolved

    async def ensure_schema(self, db) -> None:
        try:
            await self._ensure_schema_inner(db)
        except Exception as e:
            if "InsufficientPrivilege" in type(e).__name__ or "permission" in str(e).lower() or "owner" in str(e).lower():
                logger.warning("⚠️ Greatshot schema DDL skipped due to insufficient privileges: %s", e)
                logger.warning("   Tables may already exist with correct schema. Continuing startup.")
                return
            raise

    async def _ensure_schema_inner(self, db) -> None:
        await db.execute(
            """
            DO $$
            BEGIN
                IF to_regclass('public.greatshot_demos') IS NULL AND to_regclass('public.demos') IS NOT NULL THEN
                    ALTER TABLE demos RENAME TO greatshot_demos;
                END IF;
                IF to_regclass('public.greatshot_analysis') IS NULL AND to_regclass('public.demo_analysis') IS NOT NULL THEN
                    ALTER TABLE demo_analysis RENAME TO greatshot_analysis;
                END IF;
                IF to_regclass('public.greatshot_highlights') IS NULL AND to_regclass('public.demo_highlights') IS NOT NULL THEN
                    ALTER TABLE demo_highlights RENAME TO greatshot_highlights;
                END IF;
                IF to_regclass('public.greatshot_renders') IS NULL AND to_regclass('public.demo_renders') IS NOT NULL THEN
                    ALTER TABLE demo_renders RENAME TO greatshot_renders;
                END IF;
            END
            $$;
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS greatshot_demos (
                id TEXT PRIMARY KEY,
                user_id BIGINT NOT NULL,
                original_filename TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                extension TEXT NOT NULL,
                file_size_bytes BIGINT NOT NULL,
                content_hash_sha256 TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'uploaded',
                error TEXT,
                metadata_json JSONB,
                warnings_json JSONB,
                analysis_json_path TEXT,
                report_txt_path TEXT,
                processing_started_at TIMESTAMP,
                processing_finished_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS greatshot_analysis (
                demo_id TEXT PRIMARY KEY REFERENCES greatshot_demos(id) ON DELETE CASCADE,
                metadata_json JSONB NOT NULL,
                stats_json JSONB NOT NULL,
                events_json JSONB NOT NULL,
                total_kills INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Migration: Add total_kills column if it doesn't exist
        try:
            await db.execute(
                """
                ALTER TABLE greatshot_analysis
                ADD COLUMN IF NOT EXISTS total_kills INTEGER DEFAULT 0
                """
            )
        except Exception:
            pass  # Column may already exist

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS greatshot_highlights (
                id TEXT PRIMARY KEY,
                demo_id TEXT NOT NULL REFERENCES greatshot_demos(id) ON DELETE CASCADE,
                type TEXT NOT NULL,
                player TEXT,
                start_ms INTEGER NOT NULL,
                end_ms INTEGER NOT NULL,
                score DOUBLE PRECISION NOT NULL,
                meta_json JSONB,
                clip_demo_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS greatshot_renders (
                id TEXT PRIMARY KEY,
                highlight_id TEXT NOT NULL REFERENCES greatshot_highlights(id) ON DELETE CASCADE,
                status TEXT NOT NULL DEFAULT 'queued',
                mp4_path TEXT,
                error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_greatshot_demos_user_created_at ON greatshot_demos(user_id, created_at DESC)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_greatshot_demos_status ON greatshot_demos(status)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_greatshot_highlights_demo_id ON greatshot_highlights(demo_id)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_greatshot_renders_highlight ON greatshot_renders(highlight_id)"
        )

        logger.info("✅ Greatshot schema ensured")


_storage: GreatshotStorageService | None = None


def get_greatshot_storage(project_root: Path) -> GreatshotStorageService:
    global _storage
    if _storage is None:
        _storage = GreatshotStorageService(project_root=project_root)
    return _storage
