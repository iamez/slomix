"""Filename clocks remain lookup hints, never physical source identity."""

# ruff: noqa: SLF001 -- exercise actual internal import/relink boundary
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from proximity.parser import ProximityParserV4
from tests.unit.test_relinker_fuzzy_fallback import _relinker


async def test_parser_persists_filename_origin_without_changing_identity():
    parser = ProximityParserV4()
    parser.metadata.update(round_start_unix=12345, round_start_is_fallback=True)
    parser._round_link_context = {"round_id": None, "round_link_source": "unresolved"}
    parser._table_has_column = AsyncMock(return_value=True)
    columns, values = [], []
    await parser._append_round_link_columns("player_track", columns, values)
    assert dict(zip(columns, values))["round_link_source"] == "filename_clock_v1"
    assert parser.metadata["round_start_unix"] == 12345


async def test_filename_rows_bypass_physical_identity_and_do_not_fanout_to_lua():
    clock = int(datetime.now(timezone.utc).timestamp())
    day = datetime.now(timezone.utc).date()

    class DB:
        execute = AsyncMock()

        async def fetch_all(self, query, params=None):
            if "information_schema.columns" in query:
                return [("player_track",)]
            if "filename_clock_v1" in query and "SELECT" in query and "table_name" in query:
                return [("player_track", "fixture", 1, clock, day)]
            return []

    db = DB()
    resolver = AsyncMock(return_value=42)
    with patch("bot.core.round_linker.resolve_round_id", resolver):
        await _relinker(db)._relink_null_round_ids()
    resolver.assert_awaited_once()
    assert resolver.call_args.kwargs["target_dt"].timestamp() == clock
    db.execute.assert_awaited_once()
    sql, params = db.execute.call_args.args
    assert "UPDATE player_track" in sql and "round_link_source = 'filename_clock_v1'" in sql
    assert "round_id IS NULL" in sql and params == (42, "fixture", 1, day, clock)


async def test_no_candidate_does_not_write_filename_rows():
    clock = int(datetime.now(timezone.utc).timestamp())

    class DB:
        execute = AsyncMock()

        async def fetch_all(self, query, params=None):
            if "information_schema.columns" in query:
                return [("player_track",)]
            if "filename_clock_v1" in query and "SELECT" in query and "table_name" in query:
                return [("player_track", "fixture", 1, clock, datetime.now(timezone.utc).date())]
            return []

    db = DB()
    resolver = AsyncMock(return_value=None)
    with patch("bot.core.round_linker.resolve_round_id", resolver):
        await _relinker(db)._relink_null_round_ids()
    resolver.assert_awaited_once()
    db.execute.assert_not_awaited()
