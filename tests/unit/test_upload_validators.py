"""Tests for website/backend/services/upload_validators.py.

OWASP-compliant file upload security: extension allowlists, magic-byte
content verification, size limits, filename sanitisation. The whole
file accepts user-controlled input — every public function is a
security boundary.

Untested until now. Pin the contracts so a future "convenience"
expansion of the allowlist (e.g. adding .exe to ALLOWED_EXTENSIONS)
or a regex regression in sanitize_filename can't silently expose the
upload pipeline.
"""
from __future__ import annotations

import pytest

from website.backend.services.upload_validators import (
    ALLOWED_EXTENSIONS,
    CATEGORY_ARCHIVE,
    CATEGORY_CLIP,
    CATEGORY_CONFIG,
    SIZE_LIMITS,
    detect_category,
    get_content_type,
    get_size_limit,
    sanitize_filename,
    validate_extension,
    validate_file_size,
    validate_magic_bytes,
    validate_text_content,
)


# ---------------------------------------------------------------------------
# validate_extension
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("filename, category, expected", [
    ("config.cfg",       CATEGORY_CONFIG,  ".cfg"),
    ("MyHud.HUD",        CATEGORY_CONFIG,  ".hud"),       # case-insensitive
    ("archive.zip",      CATEGORY_ARCHIVE, ".zip"),
    ("archive.RAR",      CATEGORY_ARCHIVE, ".rar"),
    ("clip.mp4",         CATEGORY_CLIP,    ".mp4"),
    ("clip.AVI",         CATEGORY_CLIP,    ".avi"),
    ("clip.MKV",         CATEGORY_CLIP,    ".mkv"),
])
def test_validate_extension_accepts_allowed(filename, category, expected):
    assert validate_extension(filename, category) == expected


@pytest.mark.parametrize("filename, category", [
    ("malware.exe",  CATEGORY_CONFIG),
    ("malware.exe",  CATEGORY_ARCHIVE),
    ("malware.exe",  CATEGORY_CLIP),
    ("script.sh",    CATEGORY_ARCHIVE),
    ("config.cfg",   CATEGORY_ARCHIVE),  # right ext, wrong category
    ("clip.mp4",     CATEGORY_CONFIG),   # right ext, wrong category
])
def test_validate_extension_rejects_disallowed(filename, category):
    with pytest.raises(ValueError):
        validate_extension(filename, category)


def test_validate_extension_rejects_no_extension():
    with pytest.raises(ValueError, match="must have an extension"):
        validate_extension("noext", CATEGORY_CONFIG)


def test_validate_extension_rejects_unknown_category():
    with pytest.raises(ValueError, match="Invalid category"):
        validate_extension("a.cfg", "made_up_category")


def test_validate_extension_rejects_double_extension_attack():
    """`.tar.exe` → suffix is `.exe`, not allowed."""
    with pytest.raises(ValueError):
        validate_extension("backup.tar.exe", CATEGORY_ARCHIVE)


# ---------------------------------------------------------------------------
# validate_file_size
# ---------------------------------------------------------------------------


def test_validate_file_size_accepts_within_limit():
    """2 MB exactly is accepted (limit is inclusive — `>` not `>=`)."""
    validate_file_size(SIZE_LIMITS[CATEGORY_CONFIG], CATEGORY_CONFIG)


def test_validate_file_size_rejects_above_limit():
    over = SIZE_LIMITS[CATEGORY_CONFIG] + 1
    with pytest.raises(ValueError, match="exceeds limit"):
        validate_file_size(over, CATEGORY_CONFIG)


def test_validate_file_size_zero_bytes_allowed():
    """0-byte files pass size validation (other validators catch them)."""
    validate_file_size(0, CATEGORY_ARCHIVE)


def test_validate_file_size_rejects_unknown_category():
    with pytest.raises(ValueError, match="Invalid category"):
        validate_file_size(100, "made_up_category")


# ---------------------------------------------------------------------------
# validate_magic_bytes
# ---------------------------------------------------------------------------


def test_magic_bytes_accepts_zip_pk_header():
    validate_magic_bytes(b"PK\x03\x04somecontent", ".zip")


def test_magic_bytes_accepts_zip_pk_empty_archive():
    """Empty ZIP archives use a slightly different signature."""
    validate_magic_bytes(b"PK\x05\x06" + b"\x00" * 18, ".zip")


def test_magic_bytes_rejects_zip_with_exe_header():
    """`.zip` upload that's actually an MZ executable → reject."""
    with pytest.raises(ValueError, match="magic bytes"):
        validate_magic_bytes(b"MZ\x90\x00fakearchive", ".zip")


def test_magic_bytes_accepts_rar5_header():
    validate_magic_bytes(b"Rar!\x1a\x07\x01\x00fakecontent", ".rar")


def test_magic_bytes_accepts_avi_riff_with_marker():
    """RIFF + AVI marker at offset 8 must both be present."""
    header = b"RIFF\x00\x00\x00\x00AVI " + b"\x00" * 100
    validate_magic_bytes(header, ".avi")


def test_magic_bytes_rejects_riff_wave_disguised_as_avi():
    """RIFF header alone isn't enough; must have AVI marker.

    A RIFF/WAVE audio file masquerading as .avi must be caught."""
    header = b"RIFF\x00\x00\x00\x00WAVE" + b"\x00" * 100
    with pytest.raises(ValueError, match="magic bytes"):
        validate_magic_bytes(header, ".avi")


def test_magic_bytes_accepts_mp4_ftyp_at_offset_4():
    header = b"\x00\x00\x00\x20ftypisom" + b"\x00" * 100
    validate_magic_bytes(header, ".mp4")


def test_magic_bytes_rejects_short_header():
    """Less than expected magic byte length → reject."""
    with pytest.raises(ValueError, match="magic bytes"):
        validate_magic_bytes(b"PK", ".zip")  # truncated


def test_magic_bytes_text_file_routes_through_text_validator():
    """`.cfg` gets routed to validate_text_content (no magic bytes)."""
    validate_magic_bytes(b"// some config\nbind w +forward", ".cfg")


def test_magic_bytes_text_file_rejects_null_bytes():
    with pytest.raises(ValueError, match="null bytes"):
        validate_magic_bytes(b"some\x00binary", ".cfg")


def test_magic_bytes_text_file_rejects_invalid_utf8():
    with pytest.raises(ValueError, match="UTF-8"):
        validate_magic_bytes(b"\xc3\x28invalid", ".hud")


# ---------------------------------------------------------------------------
# validate_text_content
# ---------------------------------------------------------------------------


def test_validate_text_content_accepts_ascii():
    validate_text_content(b"plain ascii content")


def test_validate_text_content_accepts_utf8():
    """Slovenian + Czech + Cyrillic → all valid UTF-8."""
    validate_text_content("config — žš čř слова".encode("utf-8"))


def test_validate_text_content_rejects_null_byte():
    with pytest.raises(ValueError, match="null bytes"):
        validate_text_content(b"text\x00with null")


def test_validate_text_content_rejects_invalid_utf8():
    with pytest.raises(ValueError, match="UTF-8"):
        validate_text_content(b"\xff\xfe invalid utf-8")


# ---------------------------------------------------------------------------
# sanitize_filename — security-critical
# ---------------------------------------------------------------------------


def test_sanitize_strips_path_separators():
    """Forward slash AND backslash → underscore. No path traversal."""
    out = sanitize_filename("../../etc/passwd")
    assert "/" not in out
    assert "\\" not in out


def test_sanitize_strips_windows_path():
    out = sanitize_filename(r"C:\Windows\System32\evil.exe")
    assert "\\" not in out


def test_sanitize_strips_dangerous_special_chars():
    """Quotes, semicolons, shell metacharacters dropped."""
    out = sanitize_filename(r"file;rm -rf /\".cfg")
    assert ";" not in out
    assert '"' not in out


def test_sanitize_preserves_unicode_normalised():
    """Pre-composed unicode normalised via NFKC, kept in output."""
    out = sanitize_filename("filé.cfg")
    # Either the composed or decomposed form is fine; both pass `\w` regex
    assert ".cfg" in out


def test_sanitize_collapses_repeated_underscores():
    out = sanitize_filename("a___b___c")
    assert "___" not in out


def test_sanitize_truncates_to_max_len_preserving_extension():
    """A 1000-char filename ending in .cfg should keep the .cfg suffix."""
    long = "x" * 1000 + ".cfg"
    out = sanitize_filename(long, max_len=50)
    assert len(out) <= 50
    assert out.endswith(".cfg")


def test_sanitize_falls_back_to_upload_on_empty_result():
    """A string that becomes empty AFTER sanitisation gets a default 'upload'.

    Path-separator-only strings collapse to a single underscore (path
    separators are replaced with `_`, not stripped), so they do NOT
    trigger the empty fallback. To verify the fallback path, we need
    input made of characters the regex actively strips (e.g. `@`).
    """
    # Pure special-char names → stripped to empty → "upload" fallback fires
    assert sanitize_filename("@@@@") == "upload"
    assert sanitize_filename("(((") == "upload"
    assert sanitize_filename("&&&") == "upload"


def test_sanitize_path_separator_only_collapses_to_underscore():
    """Path separators replace with `_`, so `///` survives as `_`
    (collapsed). This is intentional and not the empty-fallback path."""
    assert sanitize_filename("///") == "_"
    assert sanitize_filename("\\\\\\") == "_"


def test_sanitize_strips_leading_trailing_whitespace():
    assert sanitize_filename("   spaced   .cfg") == "spaced .cfg"


# ---------------------------------------------------------------------------
# get_content_type
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ext, expected_prefix", [
    (".cfg", "text/plain"),
    (".hud", "text/plain"),
    (".zip", "application/zip"),
    (".rar", "application/x-rar-compressed"),
    (".mp4", "video/mp4"),
    (".avi", "video/x-msvideo"),
    (".mkv", "video/x-matroska"),
])
def test_get_content_type_known_extensions(ext, expected_prefix):
    assert get_content_type(ext).startswith(expected_prefix)


def test_get_content_type_rejects_unknown_extension():
    with pytest.raises(ValueError):
        get_content_type(".unknown")


# ---------------------------------------------------------------------------
# get_size_limit + detect_category
# ---------------------------------------------------------------------------


def test_get_size_limit_for_each_category():
    assert get_size_limit(CATEGORY_CONFIG) == 2 * 1024 * 1024
    assert get_size_limit(CATEGORY_ARCHIVE) == 50 * 1024 * 1024
    assert get_size_limit(CATEGORY_CLIP) == 500 * 1024 * 1024


def test_get_size_limit_rejects_unknown_category():
    with pytest.raises(ValueError):
        get_size_limit("alien")


def test_detect_category_finds_each_extension():
    assert detect_category(".cfg") == CATEGORY_CONFIG
    assert detect_category(".hud") == CATEGORY_CONFIG
    assert detect_category(".zip") == CATEGORY_ARCHIVE
    assert detect_category(".rar") == CATEGORY_ARCHIVE
    assert detect_category(".mp4") == CATEGORY_CLIP
    assert detect_category(".mkv") == CATEGORY_CLIP


def test_detect_category_returns_none_for_unknown():
    assert detect_category(".exe") is None
    assert detect_category(".sh") is None


# ---------------------------------------------------------------------------
# Schema invariants — pin the allowlist itself
# ---------------------------------------------------------------------------


def test_no_executable_extensions_in_allowlist():
    """Critical regression guard: `.exe`, `.sh`, `.bat`, `.ps1`, `.dll`
    must NEVER appear in any category. A future "convenience" addition
    here exposes the entire upload pipeline."""
    forbidden = {".exe", ".sh", ".bat", ".ps1", ".dll", ".so", ".js", ".php"}
    for category, exts in ALLOWED_EXTENSIONS.items():
        intersection = exts & forbidden
        assert not intersection, (
            f"category={category} has forbidden extension(s): {intersection}"
        )


def test_size_limits_categories_match_allowed_extensions():
    """Every category in ALLOWED_EXTENSIONS must have a SIZE_LIMITS entry."""
    assert set(SIZE_LIMITS.keys()) == set(ALLOWED_EXTENSIONS.keys())
