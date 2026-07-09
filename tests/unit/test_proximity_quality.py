from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from website.backend.routers.proximity_quality import get_proximity_quality


def _normalize_sql(query: str) -> str:
    return " ".join(str(query).split()).lower()


class _QualityFakeDB:
    def __init__(self) -> None:
        base = datetime(2026, 7, 9, 10, 0, 0, tzinfo=timezone.utc)
        self.signal_rows: dict[str, tuple[Any, ...]] = {
            "combat_engagement": (20, 20, 2, base),
            "player_track": (40, 40, 2, base),
            "proximity_kill_outcome": (18, 18, 2, base),
            "proximity_spawn_timing": (18, 18, 2, base),
            "proximity_team_push": (4, 4, 2, base),
            "proximity_crossfire_opportunity": (6, 6, 2, base),
            "proximity_reaction_metric": (18, 18, 2, base),
            "proximity_shot_fired": (120, 120, 2, base),
            "proximity_hit_region": (90, 90, 2, base),
            "storytelling_kill_impact": (
                18,
                None,
                None,
                datetime(2026, 7, 9, 10, 5, 0, tzinfo=timezone.utc),
            ),
        }
        self.round_correlation_row: tuple[Any, ...] = (
            1,
            1,
            1,
            1,
            0,
            100.0,
            base,
        )
        self.anomalous = False
        self.write_calls: list[tuple[str, Any]] = []

    async def fetch_one(self, query: str, params=None):
        q = _normalize_sql(query)
        if "/* proximity_quality_signal:" in q:
            key = q.split("/* proximity_quality_signal:", 1)[1].split(" */", 1)[0]
            return self.signal_rows[key]
        if "/* proximity_quality_round_correlation */" in q:
            return self.round_correlation_row
        if "total_lua_rows" in q and "unlinked_lua_rows" in q:
            return (100, 35) if self.anomalous else (100, 0)
        if "match_id_mismatch_rows" in q and "map_name_mismatch_rows" in q:
            return (4, 3, 2) if self.anomalous else (0, 0, 0)
        if "duplicate_lua_round_links" in q:
            return (2,) if self.anomalous else (0,)
        if "r1_mismatch_rows" in q and "complete_missing_core_rows" in q:
            return (1, 2, 1) if self.anomalous else (0, 0, 0)
        raise AssertionError(f"Unexpected fetch_one query: {q}")

    async def fetch_all(self, query: str, params=None):
        q = _normalize_sql(query)
        if "from lua_round_teams l join rounds r" in q and "lua_row_id" in q:
            if self.anomalous:
                return [(900, 9800, "m1", "m2", "supply", "radar", 1, 2)]
            return []
        if "from round_correlations c" in q and "correlation_id" in q:
            if self.anomalous:
                return [("cid", "m1", "supply", 9800, 9801, "m1", "m2", "supply", "radar", "partial")]
            return []
        return []

    async def execute(self, query: str, params=None):
        self.write_calls.append((query, params))
        raise AssertionError("quality endpoint must not write")

    async def execute_many(self, query: str, params=None):
        self.write_calls.append((query, params))
        raise AssertionError("quality endpoint must not write")


class _SQLiteQualityFakeDB:
    db_path = "/tmp/local.sqlite3"

    async def fetch_one(self, query: str, params=None):
        raise AssertionError("sqlite fallback must not execute PostgreSQL quality SQL")

    async def fetch_all(self, query: str, params=None):
        raise AssertionError("sqlite fallback must not execute PostgreSQL quality SQL")


@pytest.mark.asyncio
async def test_proximity_quality_healthy_scope_returns_ready():
    db = _QualityFakeDB()

    payload = await get_proximity_quality(range_days=30, db=db)

    assert payload["overall_status"] == "ready"
    assert payload["cache_freshness"]["status"] == "ok"
    assert payload["cache_freshness"]["latest_context_created_at"].endswith("+00:00")
    assert payload["signals"]["combat_engagement"]["latest_created_at"].endswith("+00:00")
    assert payload["signals"]["combat_engagement"]["ready"] is True
    assert payload["round_correlation"]["ready"] is True
    assert payload["linkage"]["scope"] == "global"
    assert payload["warnings"] == []


@pytest.mark.asyncio
async def test_proximity_quality_missing_signal_downgrades_status():
    db = _QualityFakeDB()
    db.signal_rows["proximity_reaction_metric"] = (0, 0, 0, None)

    payload = await get_proximity_quality(range_days=30, db=db)

    assert payload["overall_status"] == "partial"
    assert payload["signals"]["proximity_reaction_metric"]["status"] == "missing"
    assert "SIGNAL_MISSING" in {warning["code"] for warning in payload["warnings"]}


@pytest.mark.asyncio
async def test_proximity_quality_core_missing_is_insufficient():
    db = _QualityFakeDB()
    db.signal_rows["combat_engagement"] = (0, 0, 0, None)

    payload = await get_proximity_quality(range_days=30, db=db)

    assert payload["overall_status"] == "insufficient"
    assert payload["signals"]["combat_engagement"]["status"] == "missing"


@pytest.mark.asyncio
async def test_proximity_quality_anomaly_breaches_are_sanitized_without_samples():
    db = _QualityFakeDB()
    db.anomalous = True

    payload = await get_proximity_quality(range_days=30, db=db)

    assert payload["overall_status"] == "partial"
    assert payload["linkage"]["scope"] == "global"
    assert payload["linkage"]["status"] == "warning"
    assert payload["linkage"]["breach_count"] > 0
    assert "samples" not in payload["linkage"]
    assert "LINKAGE_ANOMALY_BREACH" in {warning["code"] for warning in payload["warnings"]}


@pytest.mark.asyncio
async def test_proximity_quality_round_correlation_flags_affect_readiness():
    db = _QualityFakeDB()
    db.round_correlation_row = (
        1,
        1,
        1,
        0,
        1,
        95.0,
        datetime(2026, 7, 9, 10, 0, 0, tzinfo=timezone.utc),
    )

    payload = await get_proximity_quality(range_days=30, db=db)

    assert payload["overall_status"] == "partial"
    assert payload["round_correlation"]["status"] == "proximity_flags_incomplete"
    assert "ROUND_CORRELATION_PROXIMITY_INCOMPLETE" in {
        warning["code"] for warning in payload["warnings"]
    }


@pytest.mark.asyncio
async def test_proximity_quality_stale_kis_cache_is_reported_from_fake_timestamps():
    db = _QualityFakeDB()
    db.signal_rows["proximity_kill_outcome"] = (
        18,
        18,
        2,
        datetime(2026, 7, 9, 11, 0, 0, tzinfo=timezone.utc),
    )
    db.signal_rows["storytelling_kill_impact"] = (
        18,
        None,
        None,
        datetime(2026, 7, 9, 10, 0, 0, tzinfo=timezone.utc),
    )

    payload = await get_proximity_quality(range_days=30, db=db)

    assert payload["overall_status"] == "partial"
    assert payload["cache_freshness"]["status"] == "stale"
    assert "KIS_CACHE_STALE" in {warning["code"] for warning in payload["warnings"]}


@pytest.mark.asyncio
async def test_proximity_quality_post_recompute_kis_cache_is_ok():
    db = _QualityFakeDB()
    db.signal_rows["proximity_kill_outcome"] = (
        18,
        18,
        2,
        datetime(2026, 7, 9, 10, 0, 0, tzinfo=timezone.utc),
    )
    db.signal_rows["storytelling_kill_impact"] = (
        18,
        None,
        None,
        datetime(2026, 7, 9, 10, 1, 0, tzinfo=timezone.utc),
    )

    payload = await get_proximity_quality(range_days=30, db=db)

    assert payload["overall_status"] == "ready"
    assert payload["cache_freshness"]["status"] == "ok"


@pytest.mark.asyncio
async def test_proximity_quality_does_not_call_write_methods():
    db = _QualityFakeDB()

    await get_proximity_quality(range_days=30, db=db)

    assert db.write_calls == []


@pytest.mark.asyncio
async def test_proximity_quality_sqlite_returns_clear_unsupported_payload_without_queries():
    payload = await get_proximity_quality(range_days=30, db=_SQLiteQualityFakeDB())

    assert payload["overall_status"] == "error"
    assert payload["round_correlation"]["status"] == "unsupported"
    assert payload["cache_freshness"]["status"] == "unknown"
    assert payload["warnings"] == [
        {
            "code": "PROXIMITY_QUALITY_SQLITE_UNSUPPORTED",
            "level": "warning",
            "message": "Proximity quality checks require PostgreSQL and are unavailable in local SQLite mode.",
        }
    ]
