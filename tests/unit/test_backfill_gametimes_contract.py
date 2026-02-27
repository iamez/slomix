import pytest

import scripts.backfill_gametimes as backfill_gametimes
from scripts.backfill_gametimes import (
    _build_round_metadata_from_map,
    _normalize_lua_round_for_metadata_paths,
)


def test_build_round_metadata_normalizes_side_and_end_reason():
    metadata = {
        "map": "supply",
        "round": "1",
        "winner": "allies",
        "defender": "axis",
        "lua_endreason": "objective",
        "lua_roundstart": "1770901200",
        "lua_roundend": "1770901800",
    }

    round_metadata = _build_round_metadata_from_map(metadata)

    assert round_metadata["winner_team"] == 2
    assert round_metadata["defender_team"] == 1
    assert round_metadata["end_reason"] == "NORMAL"


def test_build_round_metadata_normalizes_invalid_values_to_unknown():
    metadata = {
        "map": "supply",
        "round": "2",
        "winner": "9",
        "defender": "n/a",
        "lua_endreason": "mapchange",
        "lua_roundstart": "1770901800",
        "lua_roundend": "1770902400",
    }

    round_metadata = _build_round_metadata_from_map(metadata)

    assert round_metadata["winner_team"] == 0
    assert round_metadata["defender_team"] == 0
    assert round_metadata["end_reason"] == "MAP_CHANGE"


def test_normalize_lua_round_for_metadata_paths_maps_round_zero_to_two():
    assert _normalize_lua_round_for_metadata_paths("0") == 2
    assert _normalize_lua_round_for_metadata_paths(0) == 2
    assert _normalize_lua_round_for_metadata_paths("2") == 2
    assert _normalize_lua_round_for_metadata_paths("-1") == 0


def test_build_round_metadata_normalizes_round_zero_to_two():
    metadata = {
        "map": "supply",
        "round": "0",
        "winner": "allies",
        "defender": "axis",
        "lua_endreason": "objective",
        "lua_roundstart": "1770901200",
        "lua_roundend": "1770901800",
    }

    round_metadata = _build_round_metadata_from_map(metadata)
    assert round_metadata["round_number"] == 2


class _FakeDB:
    def __init__(self):
        self.executed = []

    async def execute(self, query, params):
        self.executed.append((query, params))


@pytest.mark.asyncio
async def test_store_lua_round_dry_run_reports_reason_without_writing(monkeypatch):
    captured = {}

    async def _fake_resolve_round_id_with_reason(
        _db_adapter,
        _map_name,
        _round_number,
        *,
        target_dt=None,
        round_date=None,
        round_time=None,
        window_minutes=45,
    ):
        captured["window_minutes"] = window_minutes
        captured["target_dt"] = target_dt
        captured["round_date"] = round_date
        captured["round_time"] = round_time
        return None, {"reason_code": "no_rows_for_map_round"}

    monkeypatch.setattr(
        backfill_gametimes,
        "resolve_round_id_with_reason",
        _fake_resolve_round_id_with_reason,
    )

    db = _FakeDB()
    round_metadata = {
        "map_name": "supply",
        "round_number": 2,
        "round_start_unix": 1770901200,
        "round_end_unix": 1770901800,
        "actual_duration_seconds": 600,
        "total_pause_seconds": 0,
        "pause_count": 0,
        "end_reason": "NORMAL",
        "winner_team": 2,
        "defender_team": 1,
        "time_limit_minutes": 20,
        "lua_warmup_seconds": 0,
        "lua_warmup_start_unix": 0,
        "lua_pause_events": [],
        "surrender_team": 0,
        "surrender_caller_guid": "",
        "surrender_caller_name": "",
        "axis_score": 0,
        "allies_score": 0,
        "axis_players": [],
        "allies_players": [],
    }

    result = await backfill_gametimes._store_lua_round(
        db,
        round_metadata,
        has_round_id=True,
        dry_run=True,
        window_minutes=12,
    )

    assert result["status"] == "dry_run"
    assert result["round_id"] is None
    assert result["reason_code"] == "no_rows_for_map_round"
    assert captured["window_minutes"] == 12
    assert db.executed == []
