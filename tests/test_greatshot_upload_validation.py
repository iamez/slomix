from __future__ import annotations

from pathlib import Path
from tempfile import SpooledTemporaryFile

import pytest
from fastapi import HTTPException
from starlette.datastructures import Headers, UploadFile

from website.backend.services.greatshot_store import GreatshotStorageService


def _valid_demo_bytes() -> bytes:
    header = (1).to_bytes(4, "little", signed=True) + (64).to_bytes(4, "little", signed=True)
    return header + (b"\x00" * 128)


def _upload(filename: str, payload: bytes, content_type: str = "application/octet-stream") -> UploadFile:
    handle = SpooledTemporaryFile(max_size=1024 * 1024)
    handle.write(payload)
    handle.seek(0)
    return UploadFile(
        file=handle,
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


@pytest.mark.asyncio
async def test_upload_rejects_wrong_extension(tmp_path: Path):
    service = GreatshotStorageService(project_root=tmp_path)
    with pytest.raises(HTTPException) as exc_info:
        await service.save_upload(_upload("not-a-demo.txt", _valid_demo_bytes()))

    assert exc_info.value.status_code == 400
    assert "Unsupported file extension" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_upload_rejects_oversize(tmp_path: Path):
    service = GreatshotStorageService(project_root=tmp_path)
    service.max_upload_bytes = 64

    with pytest.raises(HTTPException) as exc_info:
        await service.save_upload(_upload("big.dm_84", _valid_demo_bytes()))

    assert exc_info.value.status_code == 413


@pytest.mark.asyncio
async def test_upload_rejects_odd_mime(tmp_path: Path):
    service = GreatshotStorageService(project_root=tmp_path)

    with pytest.raises(HTTPException) as exc_info:
        await service.save_upload(_upload("odd.dm_84", _valid_demo_bytes(), content_type="text/plain"))

    assert exc_info.value.status_code == 400
    assert "Unsupported MIME type" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_upload_accepts_valid_dm84(tmp_path: Path):
    service = GreatshotStorageService(project_root=tmp_path)
    saved = await service.save_upload(_upload("good.dm_84", _valid_demo_bytes()))

    assert saved.extension == ".dm_84"
    assert saved.file_size_bytes > 0
    assert len(saved.content_hash_sha256) == 64
    stored_path = Path(saved.stored_path)
    assert stored_path.exists()
    assert stored_path.suffix == ".dm_84"
