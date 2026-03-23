from __future__ import annotations

import pytest

from website.backend.routers.diagnostics_router import get_round_linkage_diagnostics


class _FakeDB:
    async def fetch_one(self, query, params=None):
        q = " ".join(str(query).split()).lower()
        if "total_lua_rows" in q and "unlinked_lua_rows" in q:
            return (10, 0)
        if "match_id_mismatch_rows" in q and "map_name_mismatch_rows" in q:
            return (0, 0, 0)
        if "duplicate_lua_round_links" in q:
            return (0,)
        if "r1_mismatch_rows" in q and "complete_missing_core_rows" in q:
            return (0, 0, 0)
        return None

    async def fetch_all(self, query, params=None):
        return []


@pytest.mark.asyncio
async def test_round_linkage_diagnostics_endpoint_returns_ok_payload():
    payload = await get_round_linkage_diagnostics(sample_limit=5, db=_FakeDB())

    assert payload["status"] == "ok"
    assert payload["metrics"]["total_lua_rows"] == 10
    assert payload["metrics"]["unlinked_lua_rows"] == 0
    assert payload["breaches"] == []
