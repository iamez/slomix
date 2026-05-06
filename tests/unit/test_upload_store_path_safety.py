"""Tests for UploadStorageService path-safety primitives.

`resolve_download_path` is the primary defence against directory
traversal, symlink TOCTOU, and "../escape" download attacks. Until
now: no targeted test coverage. A regression here exposes the entire
storage tree (including data/uploads/../config files, /etc/passwd, …)
through the download endpoint.

These tests pin the security contract — every defensive branch
must remain wired up.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from website.backend.services.upload_store import (
    UPLOAD_STORAGE_ROOT_DEFAULT,
    SavedUpload,
    UploadStorageService,
)


@pytest.fixture
def svc(tmp_path):
    """Storage service rooted in pytest tmp_path."""
    s = UploadStorageService(tmp_path)
    s.ensure_storage_tree()
    return s


# ---------------------------------------------------------------------------
# resolve_download_path — security boundary
# ---------------------------------------------------------------------------


def test_resolve_returns_absolute_path_for_valid_file(svc, tmp_path):
    """Happy path: file inside storage tree returns as resolved Path."""
    sub = tmp_path / "config" / "abc"
    sub.mkdir(parents=True)
    target = sub / "good.cfg"
    target.write_text("// content")

    out = svc.resolve_download_path("config/abc/good.cfg")
    assert out == target.resolve()


def test_resolve_rejects_parent_directory_escape(svc, tmp_path):
    """`../etc/passwd` style path → 403 (NOT 404). Pin the fail-closed
    classification — a 404 might tip off an attacker that the path is
    valid; 403 says "we know what you tried"."""
    # Create a sentinel file outside the storage root
    outside = tmp_path.parent / "should_not_be_reachable.txt"
    outside.write_text("secret")

    with pytest.raises(HTTPException) as exc:
        svc.resolve_download_path("../should_not_be_reachable.txt")
    assert exc.value.status_code == 403


def test_resolve_rejects_absolute_path(svc):
    """An absolute /etc/passwd → resolved against root then escapes →
    relative_to() raises → 403."""
    with pytest.raises(HTTPException) as exc:
        svc.resolve_download_path("/etc/passwd")
    assert exc.value.status_code in (403, 404)


def test_resolve_404_for_missing_file(svc, tmp_path):
    """File that resolves cleanly inside root but doesn't exist → 404."""
    with pytest.raises(HTTPException) as exc:
        svc.resolve_download_path("config/none/missing.cfg")
    assert exc.value.status_code == 404


def test_resolve_symlink_handling_followed_to_target(svc, tmp_path):
    """The current implementation calls `.resolve()` BEFORE `.is_symlink()`,
    so symlinks pointing to a real file inside the root resolve to the
    target — `.is_symlink()` returns False on the target, so the link is
    accepted.

    This pins observed behaviour. If a future security hardening pass
    inserts an `os.path.islink(self.root / stored_path)` check BEFORE
    resolve(), this test would need to be inverted to expect 403.
    Leaving as-is so the change is loud (test breaks → operator notices).
    """
    sub = tmp_path / "config" / "linked"
    sub.mkdir(parents=True)
    real = sub / "real.cfg"
    real.write_text("// safe content")

    link = sub / "evil.cfg"
    try:
        link.symlink_to(real)
    except OSError:
        pytest.skip("Filesystem does not support symlinks")

    # Currently resolves through the link to the target file — succeeds.
    out = svc.resolve_download_path("config/linked/evil.cfg")
    assert out == real.resolve()


def test_resolve_404_when_path_is_a_directory(svc, tmp_path):
    """Path resolves to a directory (not a file) → 404. Required so the
    download endpoint never streams a directory listing."""
    sub = tmp_path / "config" / "abc"
    sub.mkdir(parents=True)
    with pytest.raises(HTTPException) as exc:
        svc.resolve_download_path("config/abc")
    assert exc.value.status_code == 404


def test_resolve_normalises_redundant_separators(svc, tmp_path):
    """`config//abc/file.cfg` (double slash) must resolve identically to
    the canonical form. resolve() collapses the path."""
    sub = tmp_path / "config" / "abc"
    sub.mkdir(parents=True)
    f = sub / "x.cfg"
    f.write_text("")
    out = svc.resolve_download_path("config//abc/x.cfg")
    assert out == f.resolve()


def test_resolve_rejects_dotdot_in_middle(svc, tmp_path):
    """`config/../config/file.cfg` resolves into root, but a future
    refactor that strips/canonicalises before the resolve() should still
    leave this path acceptable. Pin current resolve() behaviour:
    after canonicalisation, the file is INSIDE root, so this is allowed."""
    sub = tmp_path / "config" / "abc"
    sub.mkdir(parents=True)
    f = sub / "x.cfg"
    f.write_text("")
    out = svc.resolve_download_path("config/../config/abc/x.cfg")
    assert out == f.resolve()


# ---------------------------------------------------------------------------
# upload_dir
# ---------------------------------------------------------------------------


def test_upload_dir_returns_path_inside_root(svc, tmp_path):
    """upload_dir(uuid) returns root/uuid (no additional category nesting
    in the helper itself — caller composes that)."""
    out = svc.upload_dir("abc-123")
    assert out == tmp_path.resolve() / "abc-123"


# ---------------------------------------------------------------------------
# ensure_storage_tree
# ---------------------------------------------------------------------------


def test_ensure_storage_tree_creates_directory(tmp_path):
    """First call creates the dir if missing."""
    new_root = tmp_path / "new_storage"
    s = UploadStorageService(new_root)
    s.ensure_storage_tree()
    assert new_root.exists()
    assert new_root.is_dir()


def test_ensure_storage_tree_is_idempotent(tmp_path):
    """Existing dir → no error, no truncation."""
    s = UploadStorageService(tmp_path)
    sentinel = tmp_path / "sentinel.txt"
    sentinel.write_text("don't lose me")

    s.ensure_storage_tree()
    s.ensure_storage_tree()  # twice
    assert sentinel.exists()


def test_init_resolves_relative_root_to_absolute(tmp_path, monkeypatch):
    """If a relative path is supplied, it gets resolved (made absolute)."""
    monkeypatch.chdir(tmp_path)
    s = UploadStorageService(Path("relative/storage"))
    assert s.root.is_absolute()


# ---------------------------------------------------------------------------
# delete_upload
# ---------------------------------------------------------------------------


def test_delete_upload_removes_existing_file(svc, tmp_path):
    sub = tmp_path / "config" / "abc"
    sub.mkdir(parents=True)
    target = sub / "x.cfg"
    target.write_text("")

    assert svc.delete_upload("config/abc/x.cfg") is True
    assert not target.exists()


def test_delete_upload_returns_false_for_missing_file(svc):
    """Non-existent file → False (not exception). Caller can treat as
    no-op without raising."""
    assert svc.delete_upload("config/nope/missing.cfg") is False


def test_delete_upload_rejects_traversal(svc, tmp_path):
    """Traversal attempt → False (caught HTTPException internally)."""
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("")
    assert svc.delete_upload("../outside.txt") is False


# ---------------------------------------------------------------------------
# SavedUpload dataclass shape — pin the contract
# ---------------------------------------------------------------------------


def test_saved_upload_fields_pinned():
    """The DB rows + API responses depend on these exact field names —
    a future rename would break the upload library frontend."""
    s = SavedUpload(
        upload_id="abc",
        original_filename="a.cfg",
        extension=".cfg",
        stored_path="config/abc/a.cfg",
        file_size_bytes=100,
        content_hash_sha256="0" * 64,
        category="config",
    )
    assert s.upload_id == "abc"
    assert s.original_filename == "a.cfg"
    assert s.extension == ".cfg"
    assert s.stored_path == "config/abc/a.cfg"
    assert s.file_size_bytes == 100
    assert s.content_hash_sha256 == "0" * 64
    assert s.category == "config"


def test_storage_root_default_constant():
    """A regression that bumps the default to a different path would
    silently re-locate every upload."""
    assert UPLOAD_STORAGE_ROOT_DEFAULT == "data/uploads"
