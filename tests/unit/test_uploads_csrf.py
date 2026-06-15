"""Audit remediation (2026-06-15 H2): upload/delete now require the CSRF header."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.routers import uploads as U


def _req(with_csrf: bool):
    r = MagicMock()
    r.headers = {"x-requested-with": "XMLHttpRequest"} if with_csrf else {}
    r.session = {"user": {"id": 7, "username": "x"}}
    return r


@pytest.mark.asyncio
async def test_upload_rejected_without_csrf_header():
    with pytest.raises(HTTPException) as e:
        await U.upload_file(_req(False), file=MagicMock(), db=AsyncMock())
    assert e.value.status_code == 403


@pytest.mark.asyncio
async def test_delete_rejected_without_csrf_header():
    with pytest.raises(HTTPException) as e:
        await U.delete_upload("abc", _req(False), db=AsyncMock())
    assert e.value.status_code == 403
