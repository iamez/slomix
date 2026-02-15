import pytest

from proximity.parser.parser import ProximityParserV4


class _FakeDB:
    def __init__(self):
        self.calls = []

    async def execute(self, query, params=None):
        self.calls.append((query, params))


@pytest.mark.asyncio
async def test_objective_focus_uses_round_start_conflict_key_when_supported():
    db = _FakeDB()
    parser = ProximityParserV4(db_adapter=db)

    parser.metadata["round_num"] = 2
    parser.metadata["map_name"] = "supply"
    parser.metadata["round_start_unix"] = 1739244000
    parser.metadata["round_end_unix"] = 1739244600
    parser.objective_focus = [
        {
            "guid": "AAA11111",
            "name": "PlayerOne",
            "team": "axis",
            "objective": "obj1",
            "avg_distance": 120.5,
            "time_within_radius_ms": 22000,
            "samples": 33,
        }
    ]

    async def _has_column(_table, _col):
        return True

    parser._table_has_column = _has_column  # type: ignore[method-assign]

    await parser._import_objective_focus("2026-02-11")

    assert len(db.calls) == 1
    query, _ = db.calls[0]
    assert "ON CONFLICT (session_date, round_number, round_start_unix, player_guid) DO UPDATE SET" in query
