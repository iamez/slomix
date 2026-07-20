"""Tests for the read-only wrong-round-linkage inventory (Codex SS-E follow-up, §L4).

`build_linkage_inventory` enumerates rows whose stored round_start_unix
disagrees with the round_start_unix of the round they're linked to via
round_id (L1's methodology), and classifies each wrong row by whether a
deterministic (round_start_unix, map_name, round_number) target exists in
`rounds`. This module makes NO writes — pin that every query is a SELECT
and that params/placeholders follow the bot's `?` convention.
"""
from __future__ import annotations

import pytest

from bot.services.linkage_inventory_service import (
    LINKAGE_INVENTORY_TABLES,
    build_linkage_inventory,
)


class _FakeDB:
    """Routes by the SQL comment tag each query carries
    (`linkage_inventory_counts:<table>` / `linkage_inventory_sample:<table>`).
    Only `combat_engagement` has data; every other table returns empty,
    matching a real "most tables are clean" report."""

    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []

    async def fetch_all(self, query, params=None):
        q = str(query)
        self.calls.append((q, tuple(params or ())))
        if "linkage_inventory_counts:combat_engagement" in q:
            return [
                ("2026-07-10", 3, 2, 1, 0),
                ("2026-07-11", 1, 0, 0, 1),
            ]
        if "linkage_inventory_sample:combat_engagement" in q:
            return [
                (501, "2026-07-10", "supply", 1, 1700000000, 42, 1699999999, 2, 43),
                (502, "2026-07-10", "supply", 1, 1700000000, 42, 1699999999, 2, 44),
                (503, "2026-07-11", "goldrush", 2, 1700005000, 50, 1699998000, 0, None),
            ]
        return []


class _ErrorDB:
    async def fetch_all(self, query, params=None):
        if "combat_engagement" in str(query):
            raise RuntimeError("boom")
        return []


@pytest.mark.asyncio
async def test_report_shape_and_totals():
    db = _FakeDB()
    report = await build_linkage_inventory(db, sample_limit=10)

    assert set(report["tables"].keys()) == set(LINKAGE_INVENTORY_TABLES)
    ce = report["tables"]["combat_engagement"]
    assert ce["status"] == "ok"
    assert ce["wrong_rows"] == 4
    assert ce["deterministic_target_available"] == 2
    assert ce["ambiguous_multiple_targets"] == 1
    assert ce["no_target_found"] == 1

    assert report["totals"]["wrong_rows"] == 4
    assert report["totals"]["deterministic_target_available"] == 2


@pytest.mark.asyncio
async def test_by_date_breakdown_preserved():
    db = _FakeDB()
    report = await build_linkage_inventory(db)
    by_date = report["tables"]["combat_engagement"]["by_date"]

    assert by_date == [
        {
            "session_date": "2026-07-10", "wrong_rows": 3,
            "deterministic_target_available": 2,
            "ambiguous_multiple_targets": 1, "no_target_found": 0,
        },
        {
            "session_date": "2026-07-11", "wrong_rows": 1,
            "deterministic_target_available": 0,
            "ambiguous_multiple_targets": 0, "no_target_found": 1,
        },
    ]


@pytest.mark.asyncio
async def test_sample_rows_include_candidate_target():
    db = _FakeDB()
    report = await build_linkage_inventory(db)
    samples = report["tables"]["combat_engagement"]["sample_rows"]

    assert len(samples) == 3
    first = samples[0]
    assert first["row_id"] == 501
    assert first["current_round_id"] == 42
    assert first["src_start_unix"] == 1700000000
    assert first["linked_start_unix"] == 1699999999
    assert first["candidate_count"] == 2
    assert first["candidate_round_id"] == 43


@pytest.mark.asyncio
async def test_sample_row_null_candidate_round_id_stays_none():
    """no_target_found rows have candidate_round_id=NULL — must stay None,
    not get coerced to 0 (which would look like a real round id)."""
    db = _FakeDB()
    report = await build_linkage_inventory(db)
    samples = report["tables"]["combat_engagement"]["sample_rows"]
    no_target_row = next(r for r in samples if r["row_id"] == 503)

    assert no_target_row["candidate_count"] == 0
    assert no_target_row["candidate_round_id"] is None


@pytest.mark.asyncio
async def test_clean_tables_have_empty_by_date_and_samples():
    db = _FakeDB()
    report = await build_linkage_inventory(db)

    for table in LINKAGE_INVENTORY_TABLES:
        if table == "combat_engagement":
            continue
        entry = report["tables"][table]
        assert entry["status"] == "ok"
        assert entry["wrong_rows"] == 0
        assert entry["by_date"] == []
        assert entry["sample_rows"] == []


@pytest.mark.asyncio
async def test_per_table_query_failure_does_not_kill_whole_report():
    db = _ErrorDB()
    report = await build_linkage_inventory(db)

    assert report["tables"]["combat_engagement"]["status"] == "error"
    # every other table still gets a clean "ok" entry
    for table in LINKAGE_INVENTORY_TABLES:
        if table == "combat_engagement":
            continue
        assert report["tables"][table]["status"] == "ok"


@pytest.mark.asyncio
async def test_tables_arg_restricts_scope():
    db = _FakeDB()
    report = await build_linkage_inventory(db, tables=("proximity_shot_fired",))

    assert set(report["tables"].keys()) == {"proximity_shot_fired"}
    assert report["totals"]["wrong_rows"] == 0


@pytest.mark.asyncio
async def test_date_range_uses_question_mark_placeholders_and_appends_params():
    """Bot-side queries use `?` (translated to $N by database_adapter), NOT
    `$1` — pin so this module doesn't accidentally use website-style
    placeholders that would silently mis-bind through the bot adapter."""
    db = _FakeDB()
    await build_linkage_inventory(
        db, since_date="2026-07-01", until_date="2026-07-31",
        tables=("combat_engagement",),
    )

    counts_call = next(c for c, _ in db.calls if "linkage_inventory_counts" in c)
    assert "?" in counts_call
    assert "$1" not in counts_call

    _, params = next(
        (q, p) for q, p in db.calls if "linkage_inventory_counts" in q)
    assert params == ("2026-07-01", "2026-07-31")


@pytest.mark.asyncio
async def test_no_date_range_omits_date_params():
    db = _FakeDB()
    await build_linkage_inventory(db, tables=("combat_engagement",))

    _, params = next(
        (q, p) for q, p in db.calls if "linkage_inventory_counts" in q)
    assert params == ()


@pytest.mark.asyncio
async def test_queries_are_select_only_no_writes():
    """This module is read-only inventory prep — pin that no query contains
    a mutating keyword, so a future edit can't sneak a write in here."""
    db = _FakeDB()
    await build_linkage_inventory(db, tables=("combat_engagement",))

    for q, _ in db.calls:
        upper = q.upper()
        assert "SELECT" in upper
        for forbidden in ("INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER ", "TRUNCATE "):
            assert forbidden not in upper


@pytest.mark.asyncio
async def test_sample_limit_passed_as_last_param():
    db = _FakeDB()
    await build_linkage_inventory(db, sample_limit=25, tables=("combat_engagement",))

    _, params = next(
        (q, p) for q, p in db.calls if "linkage_inventory_sample" in q)
    assert params[-1] == 25


@pytest.mark.asyncio
async def test_generated_at_and_scope_present():
    db = _FakeDB()
    report = await build_linkage_inventory(
        db, since_date="2026-07-01", until_date="2026-07-31", sample_limit=5)

    assert "generated_at" in report
    assert report["scope"] == {
        "since_date": "2026-07-01", "until_date": "2026-07-31", "sample_limit": 5,
    }
