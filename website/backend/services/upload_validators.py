"""
Upload file validators - extension allowlists, content verification, size limits.
OWASP-compliant file upload security.
"""

import hashlib
import re
import unicodedata
from pathlib import Path
from typing import Optional, Tuple

# Category definitions
CATEGORY_CONFIG = "config"
CATEGORY_ARCHIVE = "archive"
CATEGORY_CLIP = "clip"

# Extension allowlists (STRICT - reject everything else)
ALLOWED_EXTENSIONS = {
    CATEGORY_CONFIG: {".cfg", ".hud"},
    CATEGORY_ARCHIVE: {".zip", ".rar"},
    CATEGORY_CLIP: {".mp4", ".avi", ".mkv"},
}

# Size limits in bytes
SIZE_LIMITS = {
    CATEGORY_CONFIG: 2 * 1024 * 1024,        # 2 MB
    CATEGORY_ARCHIVE: 50 * 1024 * 1024,      # 50 MB
    CATEGORY_CLIP: 500 * 1024 * 1024,        # 500 MB
}

# Magic bytes for content verification
MAGIC_BYTES = {
    ".zip": [(0, b"PK\x03\x04"), (0, b"PK\x05\x06"), (0, b"PK\x07\x08")],
    ".rar": [(0, b"Rar!\x1a\x07"), (0, b"Rar!\x1a")],
    ".mp4": [(4, b"ftyp")],  # ftyp at offset 4
    ".avi": [(0, b"RIFF")],  # Also check for "AVI " at offset 8
    ".mkv": [(0, b"\x1a\x45\xdf\xa3")],  # EBML header
}

# Safe content types (determined by US, not user)
CONTENT_TYPE_MAP = {
    ".cfg": "text/plain; charset=utf-8",
    ".hud": "text/plain; charset=utf-8",
    ".zip": "application/zip",
    ".rar": "application/x-rar-compressed",
    ".mp4": "video/mp4",
    ".avi": "video/x-msvideo",
    ".mkv": "video/x-matroska",
}


def validate_extension(filename: str, category: str) -> str:
    """
    Validate file extension against category allowlist.

    Args:
        filename: Original filename
        category: Upload category (config, archive, clip)

    Returns:
        Normalized extension (lowercase with dot)

    Raises:
        ValueError: If extension not allowed for category
    """
    if category not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Invalid category: {category}")

    ext = Path(filename).suffix.lower()
    if not ext:
        raise ValueError("File must have an extension")

    allowed = ALLOWED_EXTENSIONS[category]
    if ext not in allowed:
        raise ValueError(
            f"Extension '{ext}' not allowed for category '{category}'. "
            f"Allowed: {sorted(allowed)}"
        )

    return ext


def validate_file_size(size_bytes: int, category: str) -> None:
    """
    Validate file size against category limit.

    Args:
        size_bytes: File size in bytes
        category: Upload category

    Raises:
        ValueError: If file exceeds size limit
    """
    if category not in SIZE_LIMITS:
        raise ValueError(f"Invalid category: {category}")

    limit = SIZE_LIMITS[category]
    if size_bytes > limit:
        raise ValueError(
            f"File size {size_bytes} bytes exceeds limit of {limit} bytes "
            f"({limit / (1024 * 1024):.1f} MB) for category '{category}'"
        )


def validate_magic_bytes(header: bytes, extension: str) -> None:
    """
    Verify file content matches claimed extension using magic bytes.

    For text files (.cfg, .hud): validates UTF-8 decodable with no null bytes.
    For binary files: checks magic byte signatures.

    Args:
        header: First 512+ bytes of file
        extension: File extension (with dot, lowercase)

    Raises:
        ValueError: If content doesn't match extension
    """
    # Text files: validate UTF-8 and no null bytes
    if extension in {".cfg", ".hud"}:
        validate_text_content(header)
        return

    # Binary files: check magic bytes
    if extension not in MAGIC_BYTES:
        # No magic bytes defined for this extension (shouldn't happen if validators are in sync)
        return

    signatures = MAGIC_BYTES[extension]
    for offset, signature in signatures:
        if len(header) < offset + len(signature):
            continue
        if header[offset:offset + len(signature)] == signature:
            # Special case for AVI: also verify "AVI " at offset 8
            if extension == ".avi":
                if len(header) >= 12 and header[8:12] in (b"AVI ", b"AVIX"):
                    return
                # RIFF found but not AVI format - reject
                break
            return

    # No matching signature found
    raise ValueError(
        f"File content does not match {extension} format (magic bytes validation failed)"
    )


def validate_text_content(header: bytes) -> None:
    """
    Validate text file content (UTF-8 decodable, no null bytes).

    Args:
        header: First bytes of file to check

    Raises:
        ValueError: If content is not valid text
    """
    # Check for null bytes (binary data)
    if b'\x00' in header:
        raise ValueError("Text file contains null bytes (appears to be binary)")

    # Verify UTF-8 decodable
    try:
        header.decode('utf-8')
    except UnicodeDecodeError as e:
        raise ValueError(f"Text file is not valid UTF-8: {e}") from e


def sanitize_filename(filename: str, max_len: int = 200) -> str:
    """
    Sanitize filename for safe display and storage.

    Returns alphanumeric + ._- characters only, truncated to max_len.
    Unicode normalized to NFKC form first.

    Args:
        filename: Original filename
        max_len: Maximum length (default 200)

    Returns:
        Sanitized filename
    """
    # Normalize unicode
    filename = unicodedata.normalize('NFKC', filename)

    # Remove path separators
    filename = filename.replace('/', '_').replace('\\', '_')

    # Keep only safe characters: alphanumeric, dot, underscore, hyphen
    # Also preserve spaces for readability
    safe_chars = re.sub(r'[^\w\s.\-]', '', filename, flags=re.UNICODE)

    # Collapse multiple spaces/underscores
    safe_chars = re.sub(r'\s+', ' ', safe_chars)
    safe_chars = re.sub(r'_+', '_', safe_chars)

    # Trim whitespace
    safe_chars = safe_chars.strip()

    # Truncate if needed (preserve extension if possible)
    if len(safe_chars) > max_len:
        path = Path(safe_chars)
        ext = path.suffix
        stem = path.stem
        max_stem_len = max_len - len(ext)
        if max_stem_len > 10:  # Only preserve extension if we have reasonable space
            safe_chars = stem[:max_stem_len] + ext
        else:
            safe_chars = safe_chars[:max_len]

    # Fallback if empty after sanitization
    if not safe_chars:
        return "upload"

    return safe_chars


def get_content_type(extension: str) -> str:
    """
    Get safe content type for extension.

    Content types are determined by the server, not user input.

    Args:
        extension: File extension (with dot, lowercase)

    Returns:
        MIME type string

    Raises:
        ValueError: If extension not in content type map
    """
    if extension not in CONTENT_TYPE_MAP:
        raise ValueError(f"No content type mapping for extension: {extension}")

    return CONTENT_TYPE_MAP[extension]


def get_size_limit(category: str) -> int:
    """
    Get size limit for category.

    Args:
        category: Upload category

    Returns:
        Size limit in bytes

    Raises:
        ValueError: If category not found
    """
    if category not in SIZE_LIMITS:
        raise ValueError(f"Invalid category: {category}")

    return SIZE_LIMITS[category]


def detect_category(extension: str) -> Optional[str]:
    """
    Detect category from file extension.

    Args:
        extension: File extension (with dot, lowercase)

    Returns:
        Category name or None if extension not allowed
    """
    for category, extensions in ALLOWED_EXTENSIONS.items():
        if extension in extensions:
            return category

    return None
