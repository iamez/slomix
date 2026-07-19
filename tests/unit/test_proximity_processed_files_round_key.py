"""Parser writes migration-062 metadata to proximity_processed_files (IMP-004).

The 062 columns (tracker_version, round_key, capabilities) existed but nothing
wrote them, so the ET Performance v3 rating could never join files to rounds.
These tests pin the guarded write: when the columns exist the parser records
the tracker version and the canonical round key
(session_date|map|round|start_unix); when they don't (pre-migration DB), the
original filename-only insert still runs. `capabilities` stays NULL until the
Lua capability manifest lands (owner-gated) — the parser must not invent one.
"""
from __future__ import annotations

import pytest

from proximity.parser.parser import ProximityParserV4


class _FakeDB:
    def __init__(self):
        self.calls = []

    async def execute(self, query, params=None):
        self.calls.append((query, params))


def _parser_with_columns(db, present_columns):
    parser = ProximityParserV4(db_adapter=db)
    parser.metadata["map_name"] = "supply"
    parser.metadata["round_num"] = 2
    parser.metadata["round_start_unix"] = 1739244000
    parser.metadata["tracker_version"] = 6

    async def _has_column(_table, col):
        return col in present_columns

    parser._table_has_column = _has_column  # type: ignore[method-assign]  # noqa: SLF001
    return parser


@pytest.mark.asyncio
async def test_mark_file_processed_writes_round_key_when_supported():
    db = _FakeDB()
    parser = _parser_with_columns(db, {"filename", "round_key", "tracker_version"})

    await parser._mark_file_processed("proximity_x.txt", "2026-07-18")  # noqa: SLF001

    assert len(db.calls) == 1
    query, params = db.calls[0]
    assert "tracker_version" in query
    assert "round_key" in query
    assert "capabilities" not in query, "capabilities stays NULL pre-manifest"
    assert params == ("proximity_x.txt", "6", "2026-07-18|supply|2|1739244000")


@pytest.mark.asyncio
async def test_mark_file_processed_falls_back_without_062_columns():
    db = _FakeDB()
    parser = _parser_with_columns(db, {"filename"})

    await parser._mark_file_processed("proximity_x.txt", "2026-07-18")  # noqa: SLF001

    assert len(db.calls) == 1
    query, params = db.calls[0]
    assert "round_key" not in query
    assert params == ("proximity_x.txt",)


@pytest.mark.asyncio
async def test_mark_file_processed_without_session_date_uses_legacy_insert():
    """Callers that don't know the session date must not fabricate a round
    key — the legacy filename-only insert runs instead."""
    db = _FakeDB()
    parser = _parser_with_columns(db, {"filename", "round_key"})

    await parser._mark_file_processed("proximity_x.txt")  # noqa: SLF001

    assert len(db.calls) == 1
    query, params = db.calls[0]
    assert "round_key" not in query
    assert params == ("proximity_x.txt",)


@pytest.mark.asyncio
async def test_mark_file_processed_falls_back_when_tracker_version_missing():
    """A partially-migrated schema (round_key present, tracker_version absent)
    must use the legacy insert, not raise mid-upsert (Copilot on #519)."""
    db = _FakeDB()
    parser = _parser_with_columns(db, {"filename", "round_key"})

    await parser._mark_file_processed("proximity_x.txt", "2026-07-18")  # noqa: SLF001

    assert len(db.calls) == 1
    query, params = db.calls[0]
    assert "round_key" not in query
    assert params == ("proximity_x.txt",)
