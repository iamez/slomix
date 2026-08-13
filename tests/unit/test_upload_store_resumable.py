"""Resumable upload session protocol (uploads Faza 3b).

These pin the security-critical core of the chunked-upload protocol at the
storage layer, independent of the HTTP/auth wrapper: chunks must land in order,
never overflow the declared size, and a session is only finalised when complete
AND its assembled bytes pass the same magic-byte check the single-shot path
applies. A malformed session id must never form a filesystem path.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from website.backend.services.upload_store import UploadStorageService


@pytest.fixture
def svc(tmp_path):
    s = UploadStorageService(tmp_path)
    s.ensure_storage_tree()
    return s


def _mp4(size: int) -> bytes:
    """`size` bytes of a file whose magic bytes pass the .mp4 check (ftyp@4)."""
    head = b"\x00\x00\x00\x20ftypisom" + b"\x00" * 8
    body = head + b"\x00" * max(0, size - len(head))
    return body[:size]


def _open(svc, size, category="clip", filename="clip.mp4"):
    return svc.create_resumable_session(
        filename=filename, category=category, size=size, uploader_discord_id=42,
        title="", description="", tags="", retention_days=None,
    )


def test_full_lifecycle_in_order(svc, tmp_path):
    data = _mp4(300)
    s = _open(svc, len(data))
    assert s["offset"] == 0
    # two chunks
    off = svc.append_chunk(s["session_id"], 0, data[:120])
    assert off == 120
    off = svc.append_chunk(s["session_id"], 120, data[120:])
    assert off == len(data)
    saved, meta = svc.finalize_resumable(s["session_id"])
    assert saved.file_size_bytes == len(data)
    assert (tmp_path / saved.stored_path).read_bytes() == data
    # the incoming .part + .json are gone
    assert not list((tmp_path / "_incoming").glob("*.part"))


def test_offset_mismatch_rejected(svc):
    s = _open(svc, 100)
    svc.append_chunk(s["session_id"], 0, b"\x00" * 10)
    with pytest.raises(HTTPException) as ei:
        svc.append_chunk(s["session_id"], 0, b"\x00" * 10)  # server is at 10
    assert ei.value.status_code == 409
    assert ei.value.headers.get("Upload-Offset") == "10"


def test_chunk_cannot_exceed_declared_size(svc):
    s = _open(svc, 50)
    with pytest.raises(HTTPException) as ei:
        svc.append_chunk(s["session_id"], 0, b"\x00" * 51)
    assert ei.value.status_code == 413


def test_finalize_incomplete_rejected(svc):
    data = _mp4(100)
    s = _open(svc, len(data))
    svc.append_chunk(s["session_id"], 0, data[:40])
    with pytest.raises(HTTPException) as ei:
        svc.finalize_resumable(s["session_id"])
    assert ei.value.status_code == 409


def test_finalize_rejects_bad_magic_bytes(svc):
    # Complete the byte count, but with content that is not a real .mp4.
    bogus = b"NOTMP4" + b"\x00" * 94
    s = _open(svc, len(bogus))
    svc.append_chunk(s["session_id"], 0, bogus)
    with pytest.raises(HTTPException) as ei:
        svc.finalize_resumable(s["session_id"])
    assert ei.value.status_code == 400


def test_declared_size_over_limit_rejected(svc):
    with pytest.raises(HTTPException) as ei:
        _open(svc, 600 * 1024 * 1024)  # over the 500 MB clip limit
    assert ei.value.status_code == 400


def test_malformed_session_id_is_400(svc):
    with pytest.raises(HTTPException) as ei:
        svc.get_resumable_session("../etc/passwd")
    assert ei.value.status_code == 400


def test_unknown_session_is_none(svc):
    assert svc.get_resumable_session("a" * 32) is None


def test_append_to_unknown_session_404(svc):
    with pytest.raises(HTTPException) as ei:
        svc.append_chunk("b" * 32, 0, b"x")
    assert ei.value.status_code == 404


def test_abort_removes_session(svc, tmp_path):
    s = _open(svc, 100)
    svc.append_chunk(s["session_id"], 0, b"\x00" * 10)
    svc.abort_resumable(s["session_id"])
    assert svc.get_resumable_session(s["session_id"]) is None
    assert not list((tmp_path / "_incoming").glob("*"))


def test_sweep_reclaims_old_sessions(svc, tmp_path):
    import os
    import time
    s = _open(svc, 100)
    part = tmp_path / "_incoming" / f"{s['session_id']}.part"
    old = time.time() - 48 * 3600
    os.utime(part, (old, old))
    assert svc.sweep_stale_resumable(max_age_hours=24) == 1
    assert svc.get_resumable_session(s["session_id"]) is None
