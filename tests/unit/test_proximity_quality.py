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
        # (row_count, linked_rows, linked_round_count, comparable_start_rows,
        #  exact_start_rows, latest_created_at) — exact_start_rows ==
        #  comparable_start_rows means every comparable row points at the
        #  CORRECT round (healthy default fixture).
        self.signal_rows: dict[str, tuple[Any, ...]] = {
            "combat_engagement": (20, 20, 2, 20, 20, base),
            "player_track": (40, 40, 2, 40, 40, base),
            "proximity_kill_outcome": (18, 18, 2, 18, 18, base),
            "proximity_spawn_timing": (18, 18, 2, 18, 18, base),
            "proximity_team_push": (4, 4, 2, 4, 4, base),
            "proximity_crossfire_opportunity": (6, 6, 2, 6, 6, base),
            "proximity_reaction_metric": (18, 18, 2, 18, 18, base),
            "proximity_shot_fired": (120, 120, 2, 120, 120, base),
            "proximity_hit_region": (90, 90, 2, 90, 90, base),
            "storytelling_kill_impact": (
                18,
                None,
                None,
                None,
                None,
                datetime(2026, 7, 9, 10, 5, 0, tzinfo=timezone.utc),
            ),
        }
        # (correlation_count, complete_count, r1_expected_sides,
        #  r1_proximity_present, r2_expected_sides, r2_proximity_present,
        #  avg_completeness_pct, latest_created_at)
        self.round_correlation_row: tuple[Any, ...] = (
            1,
            1,
            1,
            1,
            1,
            1,
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
        if "wrong_start_lua_rows" in q and "map_name_mismatch_rows" in q:
            return (4, 3, 2) if self.anomalous else (0, 0, 0)
        if "duplicate_lua_round_links" in q:
            return (2,) if self.anomalous else (0,)
        if "r1_map_mismatch_rows" in q and "complete_missing_core_rows" in q:
            return (1, 2, 1) if self.anomalous else (0, 0, 0)
        raise AssertionError(f"Unexpected fetch_one query: {q}")

    async def fetch_all(self, query: str, params=None):
        q = _normalize_sql(query)
        if "from lua_round_teams l join rounds r" in q and "lua_row_id" in q:
            if self.anomalous:
                return [(900, 9800, 1740605200, 1740609200, "supply", "radar", 1, 2)]
            return []
        if "from round_correlations c" in q and "correlation_id" in q:
            if self.anomalous:
                return [("cid", "m1", "supply", 9800, 9801, "supply", "radar", "partial")]
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
    assert payload["selected_scope_status"] == "ready"
    assert payload["global_maintenance_status"] == "ok"
    assert payload["cache_freshness"]["status"] == "ok"
    assert payload["cache_freshness"]["latest_context_created_at"].endswith("+00:00")
    assert payload["signals"]["combat_engagement"]["latest_created_at"].endswith("+00:00")
    assert payload["signals"]["combat_engagement"]["ready"] is True
    assert payload["signals"]["combat_engagement"]["exact_link_ratio"] == pytest.approx(1.0)
    assert payload["signals"]["combat_engagement"]["wrong_start_rows"] == 0
    assert payload["round_correlation"]["ready"] is True
    assert payload["linkage"]["scope"] == "global"
    assert payload["warnings"] == []


@pytest.mark.asyncio
async def test_proximity_quality_missing_signal_downgrades_status():
    db = _QualityFakeDB()
    db.signal_rows["proximity_reaction_metric"] = (0, 0, 0, 0, 0, None)

    payload = await get_proximity_quality(range_days=30, db=db)

    assert payload["overall_status"] == "partial"
    assert payload["selected_scope_status"] == "partial"
    assert payload["signals"]["proximity_reaction_metric"]["status"] == "missing"
    assert "SIGNAL_MISSING" in {warning["code"] for warning in payload["warnings"]}


@pytest.mark.asyncio
async def test_proximity_quality_core_missing_is_insufficient():
    db = _QualityFakeDB()
    db.signal_rows["combat_engagement"] = (0, 0, 0, 0, 0, None)

    payload = await get_proximity_quality(range_days=30, db=db)

    assert payload["overall_status"] == "insufficient"
    assert payload["selected_scope_status"] == "insufficient"
    assert payload["signals"]["combat_engagement"]["status"] == "missing"


@pytest.mark.asyncio
async def test_proximity_quality_wrong_start_rows_flags_wrong_round_linkage():
    """Codex §18.6: a non-NULL round_id proves a row points at SOME round,
    never the CORRECT one. A row whose round_id target has a DIFFERENT
    round_start_unix is a genuine mislink (the back-to-back replay race) and
    must surface as wrong_round_linkage, not a healthy 100%-linked signal."""
    db = _QualityFakeDB()
    # 20 rows, all linked, all comparable, but 3 point at the wrong round.
    db.signal_rows["combat_engagement"] = (20, 20, 2, 20, 17, datetime(2026, 7, 9, 10, 0, 0, tzinfo=timezone.utc))

    payload = await get_proximity_quality(range_days=30, db=db)

    signal = payload["signals"]["combat_engagement"]
    assert signal["wrong_start_rows"] == 3
    assert signal["exact_link_ratio"] == pytest.approx(17 / 20)
    assert signal["status"] == "wrong_round_linkage"
    assert signal["ready"] is False
    assert payload["overall_status"] == "partial"
    assert payload["selected_scope_status"] == "partial"
    assert "SIGNAL_WRONG_ROUND_LINKAGE" in {w["code"] for w in payload["warnings"]}


@pytest.mark.asyncio
async def test_proximity_quality_low_exact_ratio_without_wrong_start_is_partial():
    """A row with NO comparable start (e.g. the round row itself lacks
    round_start_unix) is honestly unproven, not wrong — but it still drags
    the ratio down since it can't count as exact either."""
    db = _QualityFakeDB()
    # 20 rows, 20 linked, only 10 comparable, all 10 comparable ones exact.
    # exact_link_ratio = 10/20 = 0.5 < 0.90 threshold, but wrong_start_rows=0.
    db.signal_rows["proximity_hit_region"] = (20, 20, 2, 10, 10, datetime(2026, 7, 9, 10, 0, 0, tzinfo=timezone.utc))

    payload = await get_proximity_quality(range_days=30, db=db)

    signal = payload["signals"]["proximity_hit_region"]
    assert signal["wrong_start_rows"] == 0
    assert signal["exact_link_ratio"] == pytest.approx(0.5)
    assert signal["status"] == "round_linkage_partial"
    assert "SIGNAL_ROUND_LINKAGE_PARTIAL" in {w["code"] for w in payload["warnings"]}


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
async def test_proximity_quality_partial_match_without_r2_round_is_not_flagged():
    """Codex §18.3 false-positive fix: a genuinely partial match (R1 played,
    no R2 — e.g. a stopwatch round that ended the match) has r2_round_id
    NULL. There is no R2 round for R2 Proximity to attach to, so this must
    NOT be reported as missing telemetry."""
    db = _QualityFakeDB()
    # r1_expected=1/r1_present=1 (healthy), r2_expected=0 (no R2 round at all).
    db.round_correlation_row = (
        1,
        0,  # not "complete" — a partial match
        1,
        1,
        0,
        0,
        50.0,
        datetime(2026, 7, 9, 10, 0, 0, tzinfo=timezone.utc),
    )

    payload = await get_proximity_quality(range_days=30, db=db)

    rc = payload["round_correlation"]
    assert rc["expected_round_sides"] == 1
    assert rc["present_proximity_sides"] == 1
    assert rc["missing_existing_round_sides"] == 0
    assert rc["unpaired_round_sides"] == 1  # informational — the absent R2 side
    assert rc["status"] == "ok"
    assert rc["ready"] is True
    assert "ROUND_CORRELATION_PROXIMITY_INCOMPLETE" not in {
        warning["code"] for warning in payload["warnings"]
    }


@pytest.mark.asyncio
async def test_proximity_quality_existing_round_missing_proximity_is_flagged():
    """The REAL defect this endpoint must still catch: an R2 round EXISTS
    (r2_round_id present) but its Proximity flag is false — that is an
    actual telemetry gap, not a partial-match artifact."""
    db = _QualityFakeDB()
    # r1 healthy; r2_expected=1 (round exists) but r2_present=0 (missing).
    db.round_correlation_row = (
        1,
        1,
        1,
        1,
        1,
        0,
        95.0,
        datetime(2026, 7, 9, 10, 0, 0, tzinfo=timezone.utc),
    )

    payload = await get_proximity_quality(range_days=30, db=db)

    rc = payload["round_correlation"]
    assert rc["expected_round_sides"] == 2
    assert rc["present_proximity_sides"] == 1
    assert rc["missing_existing_round_sides"] == 1
    assert rc["unpaired_round_sides"] == 0
    assert payload["overall_status"] == "partial"
    assert rc["status"] == "proximity_flags_incomplete"
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
        18,
        18,
        datetime(2026, 7, 9, 11, 0, 0, tzinfo=timezone.utc),
    )
    db.signal_rows["storytelling_kill_impact"] = (
        18,
        None,
        None,
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
        18,
        18,
        datetime(2026, 7, 9, 10, 0, 0, tzinfo=timezone.utc),
    )
    db.signal_rows["storytelling_kill_impact"] = (
        18,
        None,
        None,
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
