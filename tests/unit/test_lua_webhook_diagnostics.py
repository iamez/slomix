from __future__ import annotations

import pytest

from website.backend.routers.api import get_lua_webhook_diagnostics


class _FakeDB:
    async def fetch_val(self, query):
        q = " ".join(query.split()).lower()
        if "count(*) from lua_round_teams where round_id is null and captured_at >=" in q:
            return 1
        if "count(*) from lua_round_teams where captured_at >=" in q:
            return 3
        if "count(*) from lua_round_teams where round_id is null" in q:
            return 2
        if "count(*) from lua_round_teams" in q:
            return 5
        return 0

    async def fetch_one(self, query):
        q = " ".join(query.split()).lower()
        if "from lua_round_teams" in q and "limit 1" in q:
            return (
                99,              # id
                "supply",        # map_name
                2,               # round_number
                1770843143,      # round_start_unix
                1770843722,      # round_end_unix
                579,             # actual_duration_seconds
                0,               # total_pause_seconds
                "objective",     # end_reason
                None,            # captured_at
                9825,            # round_id
                "1.6.0",         # lua_version
            )
        return None

    async def fetch_all(self, query):
        q = " ".join(query.split()).lower()
        if "from lua_round_teams" in q and "limit 5" in q:
            return [
                (
                    98, "supply", 1, 1770843050, 563, 0, "objective", None, 9824
                )
            ]
        if "count(*) filter (where round_id is null) as unlinked_rows" in q:
            return [
                ("2026-02-11", 3, 1),
                ("2026-02-10", 0, 0),
            ]
        if "count(*) filter (where l.id is null) as rounds_without_lua" in q:
            return [
                ("2026-02-11", 12, 9),
                ("2026-02-10", 8, 8),
            ]
        return []


@pytest.mark.asyncio
async def test_lua_webhook_diagnostics_includes_trends():
    payload = await get_lua_webhook_diagnostics(db=_FakeDB())

    assert payload["status"] == "ok"
    assert payload["counts"]["total"] == 5
    assert payload["counts"]["unlinked_total"] == 2
    assert payload["counts"]["last_24h"] == 3
    assert payload["counts"]["unlinked_24h"] == 1

    assert payload["latest"]["map_name"] == "supply"
    assert payload["latest"]["round_number"] == 2
    assert payload["latest"]["round_id"] == 9825

    assert len(payload["recent"]) == 1
    assert payload["recent"][0]["round_number"] == 1

    lua_trends = payload["trends"]["lua_rows_by_day"]
    assert len(lua_trends) == 2
    assert lua_trends[0]["day"] == "2026-02-11"
    assert lua_trends[0]["lua_rows"] == 3
    assert lua_trends[0]["unlinked_rows"] == 1

    missing_trends = payload["trends"]["rounds_without_lua_by_day"]
    assert len(missing_trends) == 2
    assert missing_trends[0]["day"] == "2026-02-11"
    assert missing_trends[0]["rounds_total"] == 12
    assert missing_trends[0]["rounds_without_lua"] == 9
