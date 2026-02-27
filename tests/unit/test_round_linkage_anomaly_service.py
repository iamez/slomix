from __future__ import annotations

import pytest

from bot.services.round_linkage_anomaly_service import assess_round_linkage_anomalies


class _FakeDB:
    def __init__(self):
        self.mode = "clean"

    async def fetch_one(self, query, params=None):
        q = " ".join(str(query).split()).lower()
        if "total_lua_rows" in q and "unlinked_lua_rows" in q:
            if self.mode == "anomalous":
                return (100, 35)
            return (100, 5)
        if "match_id_mismatch_rows" in q and "map_name_mismatch_rows" in q:
            if self.mode == "anomalous":
                return (4, 3, 2)
            return (0, 0, 0)
        if "duplicate_lua_round_links" in q:
            if self.mode == "anomalous":
                return (2,)
            return (0,)
        if "r1_mismatch_rows" in q and "complete_missing_core_rows" in q:
            if self.mode == "anomalous":
                return (1, 2, 1)
            return (0, 0, 0)
        return None

    async def fetch_all(self, query, params=None):
        q = " ".join(str(query).split()).lower()
        if "from lua_round_teams l join rounds r" in q and "lua_row_id" in q:
            if self.mode == "anomalous":
                return [
                    (900, 9800, "2026-02-26-210000", "2026-02-26-220000", "supply", "radar", 1, 2),
                ]
            return []
        if "from round_correlations c" in q and "correlation_id" in q:
            if self.mode == "anomalous":
                return [
                    (
                        "2026-02-26-210000:supply",
                        "2026-02-26-210000",
                        "supply",
                        9800,
                        9801,
                        "2026-02-26-210000",
                        "2026-02-26-220000",
                        "supply",
                        "radar",
                        "partial",
                    )
                ]
            return []
        return []


@pytest.mark.asyncio
async def test_assess_round_linkage_anomalies_clean_status_ok():
    db = _FakeDB()
    db.mode = "clean"

    payload = await assess_round_linkage_anomalies(db)

    assert payload["status"] == "ok"
    assert payload["breaches"] == []
    assert payload["metrics"]["unlinked_lua_rows"] == 5
    assert payload["metrics"]["match_id_mismatch_rows"] == 0
    assert payload["metrics"]["correlation_round_mismatch_rows"] == 0


@pytest.mark.asyncio
async def test_assess_round_linkage_anomalies_flags_breaches_and_samples():
    db = _FakeDB()
    db.mode = "anomalous"

    payload = await assess_round_linkage_anomalies(
        db,
        thresholds={
            "max_unlinked_lua_ratio": 0.10,
            "max_match_id_mismatch_rows": 0,
            "max_map_name_mismatch_rows": 0,
            "max_round_number_mismatch_rows": 0,
            "max_duplicate_lua_round_links": 0,
            "max_correlation_round_mismatch_rows": 0,
            "max_complete_missing_core_rows": 0,
        },
    )

    assert payload["status"] == "warning"
    breached_metrics = {b["metric"] for b in payload["breaches"]}
    assert "unlinked_lua_ratio" in breached_metrics
    assert "match_id_mismatch_rows" in breached_metrics
    assert "map_name_mismatch_rows" in breached_metrics
    assert "round_number_mismatch_rows" in breached_metrics
    assert "duplicate_lua_round_links" in breached_metrics
    assert "correlation_round_mismatch_rows" in breached_metrics
    assert "complete_missing_core_rows" in breached_metrics
    assert payload["samples"]["lua_link_mismatches"]
    assert payload["samples"]["correlation_link_mismatches"]
