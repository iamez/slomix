"""Phase 6, uploads slice 2 — the handlers are the arbiter of the write shapes.

The five write fixtures under src/app/pages/__fixtures__ were RECORDED from a
live round trip on the dev server as the e2e sentinel (init → PATCH →
finalize → GET detail as owner → DELETE; single-shot POST → DELETE). No
uploads write route declares a response_model, so this file replays each
handler with its storage/DB faked and checks that the recorded body has
exactly the handler's keys and value types — a recording and a replay cannot
disagree about a field silently.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from website.backend.routers import uploads as uploads_router
from website.backend.services.upload_store import RESUMABLE_CHUNK_SIZE, SavedUpload

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "website" / "frontend" / "src" / "app" / "pages" / "__fixtures__"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _req(user_id: int = -1) -> MagicMock:
    r = MagicMock()
    r.headers = {"x-requested-with": "XMLHttpRequest"}
    r.session = {"user": {"id": str(user_id), "username": "e2e-owner"}}
    return r


def _same_shape(recorded: dict, replayed: dict) -> None:
    assert set(recorded) == set(replayed), f"keys differ: {set(recorded) ^ set(replayed)}"
    for key, value in replayed.items():
        assert type(recorded[key]) is type(value), f"{key}: recorded {type(recorded[key]).__name__}, handler {type(value).__name__}"


@pytest.mark.asyncio
async def test_resumable_init_fixture(monkeypatch):
    storage = MagicMock()
    storage.create_resumable_session.return_value = {"session_id": "a" * 32}
    monkeypatch.setattr(uploads_router, "_get_storage", lambda: storage)
    monkeypatch.setattr(uploads_router, "_check_rate_limit", lambda _uid: None)
    payload = uploads_router.ResumableInit(filename="sentinel.cfg", size=83, title="t")
    body = await uploads_router.init_resumable_upload(_req(), payload)
    assert body["chunk_size"] == RESUMABLE_CHUNK_SIZE
    recorded = _fixture("api_uploads_resumable.json")
    _same_shape(recorded, body)
    assert recorded["chunk_size"] == RESUMABLE_CHUNK_SIZE, "the live server's chunk size drifted from the constant"
    assert recorded["offset"] == 0


@pytest.mark.asyncio
async def test_finalize_and_single_shot_share_the_persist_shape(monkeypatch):
    saved = SavedUpload(
        upload_id="b" * 32, original_filename="sentinel.cfg", extension=".cfg",
        stored_path="config/bbbb/original.cfg", file_size_bytes=83, content_hash_sha256="c" * 64, category="config",
    )
    storage = MagicMock()
    storage.finalize_resumable.return_value = (saved, {"title": "e2e sentinel cfg", "description": "", "tags": "", "retention_days": None})
    storage.get_resumable_session.return_value = {"uploader_discord_id": -1}
    monkeypatch.setattr(uploads_router, "_get_storage", lambda: storage)
    db = AsyncMock()
    body = await uploads_router.finalize_resumable_upload("a" * 32, _req(), db)
    for name in ("api_uploads_resumable_session_id_finalize.json", "api_uploads_post.json"):
        _same_shape(_fixture(name), body)
        assert _fixture(name)["share_url"].startswith("/share/")


@pytest.mark.asyncio
async def test_delete_fixture_and_the_owner_detail_says_can_delete():
    db = AsyncMock()
    db.fetch_one = AsyncMock(return_value=(-1, "config/x/original.cfg", None))
    body = await uploads_router.delete_upload("b" * 32, _req(), db)
    _same_shape(_fixture("api_uploads_upload_id_delete.json"), body)

    owner = _fixture("api_uploads_upload_id_owner.json")
    anon = _fixture("api_uploads_upload_id.json")
    assert owner["can_delete"] is True and anon["can_delete"] is False
    assert set(owner) == set(anon), "the owner recording is the same detail shape, one flag apart"
    assert owner["uploader_discord_id"] == "-1", "snowflake stays a string on the wire, sentinel included"
