"""
Test that get_diagnostics handles missing optional tables gracefully.

The diagnostics endpoint runs SELECT COUNT(*) directly on each table.
Missing tables raise exceptions with 'does not exist' in the message,
which the endpoint catches and marks as 'not_found'.
"""
from __future__ import annotations

import pytest

from website.backend.routers import diagnostics_router as api_router


def _normalize_sql(query: str) -> str:
    return " ".join(query.split()).lower()


class _DiagnosticsDB:
    """Fake DB: rounds and player_comprehensive_stats exist, others don't."""
    def __init__(self) -> None:
        self.count_queries: list[str] = []

    async def fetch_val(self, query: str, params=()):
        normalized = _normalize_sql(query)

        if normalized == "select count(*) from rounds":
            self.count_queries.append("rounds")
            return 128

        if normalized == "select count(*) from player_comprehensive_stats":
            self.count_queries.append("player_comprehensive_stats")
            return 768

        # All other tables "do not exist"
        raise Exception(f'relation "unknown_table" does not exist')

    async def fetch_one(self, query: str, params=()):
        normalized = _normalize_sql(query)
        if "raw_dead_seconds" in normalized:
            return (120, 100, 20, 3, 40)
        raise Exception('relation does not exist')


@pytest.mark.asyncio
async def test_diagnostics_skips_count_queries_for_missing_optional_tables():
    db = _DiagnosticsDB()

    payload = await api_router.get_diagnostics(db=db)

    table_states = {table["name"]: table for table in payload["tables"]}

    assert payload["database"]["status"] == "connected"
    assert table_states["rounds"]["status"] == "ok"
    assert table_states["player_comprehensive_stats"]["status"] == "ok"
    assert table_states["sessions"]["status"] == "not_found"
    assert table_states["players"]["status"] == "not_found"
    assert table_states["discord_users"]["status"] == "not_found"

    assert db.count_queries == ["rounds", "player_comprehensive_stats"]
    assert "Optional table sessions not found" in payload["warnings"]
    assert "Optional table players not found" in payload["warnings"]
    assert "Optional table discord_users not found" in payload["warnings"]
