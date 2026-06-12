"""Unit tests for S2 account endpoints + role-gating dependencies."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.dependencies import require_tier, require_user
from website.backend.routers.auth import get_my_aliases, set_my_display_name


def _request(user=None):
    req = MagicMock()
    req.session = {"user": user} if user else {}
    return req


USER = {"id": "42", "username": "ez"}


@pytest.mark.asyncio
async def test_aliases_unlinked_user():
    db = AsyncMock()
    db.fetch_one = AsyncMock(return_value=None)
    res = await get_my_aliases(_request(USER), db=db)
    assert res == {"status": "ok", "linked": False, "aliases": []}


@pytest.mark.asyncio
async def test_aliases_linked_user():
    db = AsyncMock()
    db.fetch_one = AsyncMock(return_value=("ABCD1234", "ezz", "EZ-custom", "custom"))
    db.fetch_all = AsyncMock(return_value=[("ezz", 120, "2026-06-01"), ("eZmiX", 14, "2025-01-01")])
    res = await get_my_aliases(_request(USER), db=db)
    assert res["linked"] is True
    assert res["current_display_name"] == "EZ-custom"
    assert [a["alias"] for a in res["aliases"]] == ["ezz", "eZmiX"]


@pytest.mark.asyncio
@patch("website.backend.routers.auth._audit_link_event", new_callable=AsyncMock)
async def test_display_name_custom_and_reset(mock_audit):
    db = AsyncMock()
    db.fetch_one = AsyncMock(return_value=("ABCD1234",))
    res = await set_my_display_name(_request(USER), {"action": "custom", "name": " Snek "}, db=db)
    assert res == {"status": "ok", "display_name": "Snek", "source": "custom"}
    update_args = db.execute.call_args[0]
    assert update_args[1] == ("Snek", "custom", 42)

    res2 = await set_my_display_name(_request(USER), {"action": "reset"}, db=db)
    assert res2["display_name"] is None and res2["source"] == "auto"
    assert mock_audit.await_count == 2


@pytest.mark.asyncio
@patch("website.backend.routers.auth._audit_link_event", new_callable=AsyncMock)
async def test_display_name_alias_must_be_owned(mock_audit):
    db = AsyncMock()
    db.fetch_one = AsyncMock(side_effect=[("ABCD1234",), None])  # link, then no alias
    with pytest.raises(HTTPException) as e:
        await set_my_display_name(_request(USER), {"action": "alias", "name": "stranger"}, db=db)
    assert e.value.status_code == 400


@pytest.mark.asyncio
async def test_display_name_validation():
    db = AsyncMock()
    db.fetch_one = AsyncMock(return_value=("ABCD1234",))
    with pytest.raises(HTTPException):
        await set_my_display_name(_request(USER), {"action": "custom", "name": ""}, db=db)
    with pytest.raises(HTTPException):
        await set_my_display_name(_request(USER), {"action": "custom", "name": "x" * 33}, db=db)
    with pytest.raises(HTTPException):
        await set_my_display_name(_request(USER), {"action": "nope"}, db=db)


@pytest.mark.asyncio
async def test_require_user_401_without_session():
    with pytest.raises(HTTPException) as e:
        await require_user(_request(None))
    assert e.value.status_code == 401


@pytest.mark.asyncio
async def test_require_tier_enforces_rank():
    dep = require_tier("admin")
    db = AsyncMock()
    with patch("website.backend.dependencies.get_db_pool", return_value=db):
        db.fetch_one = AsyncMock(return_value=("moderator",))
        with pytest.raises(HTTPException) as e:
            await dep(_request(USER))
        assert e.value.status_code == 403

        db.fetch_one = AsyncMock(return_value=("root",))
        user = await dep(_request(USER))
        assert user["permission_tier"] == "root"

        db.fetch_one = AsyncMock(return_value=None)
        with pytest.raises(HTTPException):
            await dep(_request(USER))
