import pytest

from website.backend.services.greatshot_crossref import (
    _match_single_round,
    _normalize_winner,
    enrich_with_db_stats,
)


class _FakeDB:
    async def fetch_all(self, query, params):
        return [
            (
                123,                     # round_id
                "2026-02-11-120000",     # match_id
                1,                       # round_number
                "2026-02-11",            # round_date
                "12:00:00",              # round_time
                "supply",                # map_name
                60,                      # actual_duration_seconds
                2,                       # winner_team (numeric in DB)
                88,                      # gaming_session_id
                10,                      # human_player_count
                1,                       # axis_score
                0,                       # allies_score
            )
        ]


class _FakeStatsDB:
    async def fetch_all(self, query, params):
        return [
            (
                "Alpha",
                "GUID-1",
                11,
                6,
                2500,
                1900,
                41.2,
                5,
                4,
                2,
                450,
                "allies",
                64.7,
                1.83,
                32.1,
                333.3,
            )
        ]


class _SchemaAwareFakeStatsDB:
    def __init__(self):
        self.last_query = ""

    async def fetch_one(self, query, params):
        column = params[0]
        if column == "dpm":
            return (1,)
        return None

    async def fetch_all(self, query, params):
        self.last_query = query
        return [
            (
                "Bravo",
                "GUID-2",
                7,
                5,
                1800,
                1700,
                36.8,
                2,
                2,
                1,
                360,
                "axis",
                58.1,
                None,   # kdr projected as NULL
                None,   # skill_rating projected as NULL
                240.0,  # dpm present
            )
        ]


def test_normalize_winner_handles_mixed_types():
    assert _normalize_winner("allies") == "allies"
    assert _normalize_winner("axis") == "axis"
    assert _normalize_winner(2) == "allies"
    assert _normalize_winner("2") == "allies"
    assert _normalize_winner(1) == "axis"
    assert _normalize_winner("1") == "axis"
    assert _normalize_winner(None) is None


@pytest.mark.asyncio
async def test_match_single_round_handles_numeric_db_winner():
    db = _FakeDB()

    result = await _match_single_round(
        demo_map="supply",
        demo_round_data={
            "duration_ms": 60000,
            "winner": "allies",
            "first_place_score": 1,
            "second_place_score": 0,
        },
        demo_filename="demo.dm_84",
        demo_player_names=[],
        demo_player_stats={},
        db=db,
    )

    assert result is not None
    assert result["round_id"] == 123
    assert "winner" in result["match_details"]


@pytest.mark.asyncio
async def test_enrich_with_db_stats_includes_tpm_and_time_minutes():
    db = _FakeStatsDB()

    players = await enrich_with_db_stats(round_id=123, db=db)
    alpha = players["Alpha"]

    assert alpha["time_played_seconds"] == 450
    assert alpha["time_played_minutes"] == 7.5
    assert alpha["tpm"] == 7.5


@pytest.mark.asyncio
async def test_enrich_with_db_stats_handles_missing_optional_columns():
    db = _SchemaAwareFakeStatsDB()

    players = await enrich_with_db_stats(round_id=456, db=db)
    bravo = players["Bravo"]

    assert "NULL AS kdr" in db.last_query
    assert "NULL AS skill_rating" in db.last_query
    assert "dpm" in db.last_query
    assert bravo["kdr"] is None
    assert bravo["skill_rating"] is None
    assert bravo["dpm"] == 240.0
