"""save_poster — storing a client-captured clip thumbnail (uploads Faza 2).

The poster is decorative and fully untrusted (a browser-supplied JPEG blob), so
these pin the contract that keeps a bad poster from ever harming an upload:
valid JPEG in → stored next to the original; anything else (wrong magic bytes,
oversized, no upload dir) → None, and the card falls back to the category icon.
"""

from __future__ import annotations

import pytest

from website.backend.services.upload_store import (
    POSTER_MAX_BYTES,
    UploadStorageService,
)

_JPEG = b"\xff\xd8\xff"  # SOI + marker — the magic bytes save_poster requires


class _FakePoster:
    """Minimal UploadFile stand-in exposing the async read() save_poster uses."""

    def __init__(self, data: bytes) -> None:
        self._data = data

    async def read(self, n: int = -1) -> bytes:
        take = self._data[:n] if n is not None and n >= 0 else self._data
        self._data = self._data[len(take):]
        return take


@pytest.fixture
def svc(tmp_path):
    s = UploadStorageService(tmp_path)
    s.ensure_storage_tree()
    return s


def _upload_dir(tmp_path, category="clip", uid="abc123def456"):
    (tmp_path / category / uid).mkdir(parents=True)
    return uid


@pytest.mark.asyncio
async def test_stores_valid_jpeg_next_to_original(svc, tmp_path):
    uid = _upload_dir(tmp_path)
    jpeg = _JPEG + b"\x00" * 200
    rel = await svc.save_poster(uid, "clip", _FakePoster(jpeg))
    assert rel == f"clip/{uid}/poster.jpg"
    assert (tmp_path / rel).read_bytes() == jpeg


@pytest.mark.asyncio
async def test_rejects_non_jpeg(svc, tmp_path):
    uid = _upload_dir(tmp_path)
    # A ZIP magic, not JPEG — must be refused and nothing written.
    assert await svc.save_poster(uid, "clip", _FakePoster(b"PK\x03\x04data")) is None
    assert not (tmp_path / "clip" / uid / "poster.jpg").exists()


@pytest.mark.asyncio
async def test_rejects_oversized(svc, tmp_path):
    uid = _upload_dir(tmp_path)
    big = _JPEG + b"\x00" * (POSTER_MAX_BYTES + 10)
    assert await svc.save_poster(uid, "clip", _FakePoster(big)) is None


@pytest.mark.asyncio
async def test_none_when_upload_dir_missing(svc, tmp_path):
    # No upload dir → None; save_poster never writes outside a real upload's dir.
    assert await svc.save_poster("does-not-exist", "clip", _FakePoster(_JPEG + b"x")) is None


@pytest.mark.asyncio
async def test_empty_poster_is_none(svc, tmp_path):
    uid = _upload_dir(tmp_path)
    assert await svc.save_poster(uid, "clip", _FakePoster(b"")) is None
