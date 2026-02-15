from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from fastapi.dependencies import utils as fastapi_dep_utils

# Greatshot router registers upload endpoints at import time, which triggers
# FastAPI's multipart dependency check. We bypass that check in unit tests.
fastapi_dep_utils.ensure_multipart_is_installed = lambda: None

from website.backend.routers import greatshot as greatshot_router


class _FakeDB:
    def __init__(self, metadata_json: str):
        self._metadata_json = metadata_json

    async def fetch_one(self, query: str, params=None):
        q = " ".join(query.split())
        params = params or ()
        if q.startswith("SELECT metadata_json FROM greatshot_demos WHERE id = $1 AND user_id = $2"):
            return (self._metadata_json,)
        if q.startswith("SELECT analysis_json_path FROM greatshot_demos WHERE id = $1"):
            return (None,)
        return None


@pytest.mark.asyncio
async def test_get_crossref_returns_200_payload_when_no_match(monkeypatch):
    request = SimpleNamespace(session={"user": {"id": "999"}})
    db = _FakeDB(metadata_json=json.dumps({"map": "supply", "filename": "demo.dm_84"}))

    async def _no_match(*_args, **_kwargs):
        return None

    monkeypatch.setattr(greatshot_router, "find_matching_round", _no_match)

    payload = await greatshot_router.get_crossref("demo-1", request, db=db)
    assert payload["matched"] is False
    assert "No matching round found" in payload["reason"]


@pytest.mark.asyncio
async def test_get_crossref_returns_200_payload_when_match_exists(monkeypatch):
    request = SimpleNamespace(session={"user": {"id": "999"}})
    db = _FakeDB(metadata_json=json.dumps({"map": "supply", "filename": "demo.dm_84"}))

    async def _match(*_args, **_kwargs):
        return {
            "round_id": 9841,
            "map_name": "supply",
            "round_number": 2,
            "confidence": 90.0,
        }

    async def _enrich(*_args, **_kwargs):
        return {"PlayerOne": {"kills": 20, "deaths": 10}}

    async def _comparison(*_args, **_kwargs):
        return [{"demo_name": "PlayerOne", "db_name": "PlayerOne", "matched": True}]

    monkeypatch.setattr(greatshot_router, "find_matching_round", _match)
    monkeypatch.setattr(greatshot_router, "enrich_with_db_stats", _enrich)
    monkeypatch.setattr(greatshot_router, "build_comparison", _comparison)

    payload = await greatshot_router.get_crossref("demo-2", request, db=db)
    assert payload["matched"] is True
    assert payload["round"]["round_id"] == 9841
    assert "db_player_stats" in payload
    assert "comparison" in payload
