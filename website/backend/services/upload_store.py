"""
Upload Library Storage Service
Handles file storage, retrieval, and metadata for community uploads.
Follows the GreatshotStorageService pattern.
"""

import hashlib
import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, UploadFile

from website.backend.logging_config import get_app_logger
from website.backend.services.upload_validators import (
    CATEGORY_CONFIG,
    SIZE_LIMITS,
    detect_category,
    get_content_type,
    get_size_limit,
    sanitize_filename,
    validate_extension,
    validate_file_size,
    validate_magic_bytes,
)

logger = get_app_logger("upload.store")

UPLOAD_STORAGE_ROOT_DEFAULT = "data/uploads"
UPLOAD_CHUNK_SIZE = 1024 * 1024  # 1MB chunks


@dataclass
class SavedUpload:
    """Metadata for a successfully saved upload."""
    upload_id: str
    original_filename: str
    extension: str
    stored_path: str  # Relative to storage root
    file_size_bytes: int
    content_hash_sha256: str
    category: str


class UploadStorageService:
    """
    Storage service for community uploads.

    Handles file persistence, validation, and retrieval for configs, HUDs,
    archives, and clips. Files are stored in UUID-based directories outside
    the web root with strict security validation.
    """

    def __init__(self, storage_root: Path):
        """
        Initialize storage service.

        Args:
            storage_root: Root directory for upload storage
        """
        if not storage_root.is_absolute():
            storage_root = storage_root.resolve()

        self.root = storage_root
        logger.info(f"Upload storage root: {self.root}")

    def ensure_storage_tree(self) -> None:
        """
        Ensure storage directory exists with secure permissions.

        Creates root directory with 0o700 permissions (owner read/write/execute only).
        """
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.root, 0o700)
        except OSError as e:
            logger.warning(f"Could not set storage root permissions: {e}")

    def upload_dir(self, upload_id: str) -> Path:
        """
        Get directory path for a specific upload.

        Args:
            upload_id: UUID hex string

        Returns:
            Path to upload directory
        """
        # Structure: {root}/{category}/{upload_id}/
        # But we don't know category here, so we need to search or pass it
        # Actually, looking at the pattern, let me check greatshot_store again...
        # It has demo_dir(demo_id) that returns root / demo_id
        # So we should probably return the base upload dir without category
        return self.root / upload_id

    def _check_disk_space(self, required_bytes: int) -> None:
        """
        Check if sufficient disk space is available.

        Requires 2x the file size to be free (space for file + processing overhead).

        Args:
            required_bytes: Minimum bytes required

        Raises:
            HTTPException: If disk space is insufficient (507 Insufficient Storage)
        """
        try:
            stat = shutil.disk_usage(self.root)
            free_bytes = stat.free

            if free_bytes < required_bytes:
                logger.error(
                    f"Insufficient disk space: {free_bytes / (1024**3):.2f}GB free, "
                    f"need at least {required_bytes / (1024**3):.2f}GB"
                )
                raise HTTPException(
                    status_code=507,
                    detail="Insufficient disk space for this operation"
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Could not check disk space: {e}")
            # Don't fail uploads if disk check fails, just log warning

    async def save_upload(self, upload: UploadFile, category: str) -> SavedUpload:
        """
        Save uploaded file with security validation.

        Process:
        1. Validate extension for category
        2. Generate UUID upload_id
        3. Create directory structure: {root}/{category}/{upload_id}/
        4. Stream file to {root}/{category}/{upload_id}/original{ext}
        5. Track total bytes and enforce size limit
        6. Collect first 512 bytes for magic byte verification
        7. Calculate SHA256 during streaming
        8. After write complete, validate magic bytes
        9. If ANY validation fails, delete the file and raise HTTPException
        10. Return SavedUpload dataclass

        Args:
            upload: FastAPI UploadFile object
            category: Upload category (config, archive, clip)

        Returns:
            SavedUpload dataclass with metadata

        Raises:
            HTTPException: On validation failure or storage error
        """
        self.ensure_storage_tree()

        # Get original filename
        unsafe_name = upload.filename or "upload"
        original_filename = Path(unsafe_name).name

        # Validate extension for category
        try:
            extension = validate_extension(original_filename, category)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        # Check disk space before accepting upload (require 2x file size)
        size_limit = get_size_limit(category)
        self._check_disk_space(required_bytes=size_limit * 2)

        # Generate UUID and create directory structure
        upload_id = uuid.uuid4().hex
        upload_dir = self.root / category / upload_id
        upload_dir.mkdir(parents=True, exist_ok=True)

        stored_path = upload_dir / f"original{extension}"
        relative_path = f"{category}/{upload_id}/original{extension}"

        digest = hashlib.sha256()
        total_bytes = 0
        header_bytes = b""

        # Stream file to disk
        try:
            with stored_path.open("wb") as handle:
                while True:
                    chunk = await upload.read(UPLOAD_CHUNK_SIZE)
                    if not chunk:
                        break

                    total_bytes += len(chunk)

                    # Enforce size limit during streaming
                    if total_bytes > size_limit:
                        handle.close()
                        self._cleanup_failed_upload(stored_path)
                        raise HTTPException(
                            status_code=413,
                            detail=(
                                f"Upload too large ({total_bytes} bytes). "
                                f"Max allowed is {size_limit} bytes "
                                f"({size_limit / (1024 * 1024):.1f} MB) for category '{category}'."
                            ),
                        )

                    # Collect header bytes for magic byte validation (first 512 bytes)
                    if len(header_bytes) < 512:
                        need = 512 - len(header_bytes)
                        header_bytes += chunk[:need]

                    digest.update(chunk)
                    handle.write(chunk)

        except HTTPException:
            raise
        except Exception as e:
            self._cleanup_failed_upload(stored_path)
            logger.error(f"Failed to write upload: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save upload: {e}"
            ) from e

        # Validate non-empty file
        if total_bytes == 0:
            self._cleanup_failed_upload(stored_path)
            raise HTTPException(status_code=400, detail="Empty upload is not allowed.")

        # Validate file size against category limit
        try:
            validate_file_size(total_bytes, category)
        except ValueError as e:
            self._cleanup_failed_upload(stored_path)
            raise HTTPException(status_code=413, detail=str(e)) from e

        # Validate content matches claimed extension (magic bytes)
        try:
            validate_magic_bytes(header_bytes, extension)
        except ValueError as e:
            self._cleanup_failed_upload(stored_path)
            raise HTTPException(
                status_code=400,
                detail=f"File content validation failed: {e}"
            ) from e

        # Success! Return metadata
        content_hash = digest.hexdigest()
        logger.info(
            f"Upload saved: {upload_id} ({category}) - "
            f"{original_filename} ({total_bytes} bytes, SHA256: {content_hash[:16]}...)"
        )

        return SavedUpload(
            upload_id=upload_id,
            original_filename=sanitize_filename(original_filename),
            extension=extension,
            stored_path=relative_path,
            file_size_bytes=total_bytes,
            content_hash_sha256=content_hash,
            category=category,
        )

    def _cleanup_failed_upload(self, file_path: Path) -> None:
        """
        Clean up file and parent directory after failed upload.

        Args:
            file_path: Path to file to delete
        """
        try:
            file_path.unlink(missing_ok=True)
            # Try to remove parent directory if empty
            try:
                file_path.parent.rmdir()
            except OSError:
                pass  # Directory not empty or already deleted
        except OSError as e:
            logger.debug(f"Could not clean up file after error: {e}")

    def resolve_download_path(self, stored_path: str) -> Path:
        """
        Resolve and validate download path.

        Ensures path is within storage root to prevent directory traversal attacks.

        Args:
            stored_path: Relative path from storage root (e.g., "config/abc123/original.cfg")

        Returns:
            Absolute resolved path

        Raises:
            HTTPException: If path is invalid or outside storage root (403/404)
        """
        try:
            # Resolve path relative to storage root
            resolved = (self.root / stored_path).resolve()

            # Ensure path is within storage root (prevent traversal)
            resolved.relative_to(self.root)
        except ValueError as exc:
            logger.warning(f"Path traversal attempt detected: {stored_path}")
            raise HTTPException(
                status_code=403,
                detail="Invalid file path"
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail="Invalid file path"
            ) from exc

        # Reject symlinks to prevent TOCTOU attacks
        if resolved.is_symlink():
            logger.warning(f"Symlink detected in upload path: {stored_path}")
            raise HTTPException(
                status_code=403,
                detail="Invalid file path"
            )

        # Verify file exists
        if not resolved.exists() or not resolved.is_file():
            raise HTTPException(
                status_code=404,
                detail="File not found"
            )

        return resolved

    def delete_upload(self, stored_path: str) -> bool:
        """
        Delete upload file from disk.

        Args:
            stored_path: Relative path from storage root

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            resolved = self.resolve_download_path(stored_path)
            resolved.unlink()

            # Try to clean up empty parent directories
            try:
                resolved.parent.rmdir()  # upload_id directory
                resolved.parent.parent.rmdir()  # category directory (if empty)
            except OSError:
                pass  # Directories not empty

            logger.info(f"Deleted upload: {stored_path}")
            return True

        except HTTPException:
            logger.warning(f"Could not delete upload (not found): {stored_path}")
            return False
        except Exception as e:
            logger.error(f"Failed to delete upload {stored_path}: {e}")
            return False


# Module-level singleton
_storage: Optional[UploadStorageService] = None


def get_upload_storage() -> UploadStorageService:
    """
    Get global upload storage service singleton.

    Storage root is configured via UPLOAD_STORAGE_ROOT environment variable,
    or defaults to 'data/uploads'.

    Returns:
        UploadStorageService instance
    """
    global _storage
    if _storage is None:
        root = Path(os.getenv("UPLOAD_STORAGE_ROOT", UPLOAD_STORAGE_ROOT_DEFAULT))
        _storage = UploadStorageService(storage_root=root)
    return _storage
