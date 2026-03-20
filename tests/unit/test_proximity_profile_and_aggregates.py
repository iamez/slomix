from __future__ import annotations

import pytest

from proximity.parser.parser import Attacker, Engagement, ProximityParserV4
from website.backend.routers import api as api_router


def _normalize_sql(query: str) -> str:
    return " ".join(query.split()).lower()


class _ProfileDB:
    def __init__(self) -> None:
        self.kill_query = ""

    async def fetch_one(self, query: str, params=()):
        normalized = _normalize_sql(query)
        if "count(*) as total_engagements" in normalized:
            return (12, 4, 8, 1400, 90, 220, 3)
        if "count(*) as total_kills" in normalized:
            self.kill_query = query
            return (5,)
        if "from proximity_spawn_timing" in normalized:
            return (0.61, 5, 730)
        if "from proximity_reaction_metric" in normalized:
            return (410, 620, 800, 9)
        if "from player_track" in normalized and "avg_speed" in normalized:
            return (123.4, 42.5, 880, 14)
        if "from proximity_lua_trade_kill" in normalized:
            return (2,)
        if "select player_name from player_track" in normalized:
            return ("Alpha",)
        raise AssertionError(f"Unexpected fetch_one query: {normalized}")


class _CaptureDB:
    def __init__(self) -> None:
        self.calls = []
        self.fetch_one_responses: dict = {}

    async def execute(self, query, params=None):
        self.calls.append((query, params))

    async def fetch_one(self, query, params=None):
        normalized = _normalize_sql(query)
        for key, value in self.fetch_one_responses.items():
            if key in normalized:
                return value
        return None


def _build_crossfire_engagement() -> Engagement:
    attackers = {
        "ATTACKER1": Attacker(
            guid="ATTACKER1",
            name="Axis One",
            team="AXIS",
            damage=45,
            hits=4,
            first_hit=1000,
            last_hit=1180,
            got_kill=True,
            weapons={8: 4},
        ),
        "ATTACKER2": Attacker(
            guid="ATTACKER2",
            name="Axis Two",
            team="AXIS",
            damage=30,
            hits=2,
            first_hit=1090,
            last_hit=1200,
            got_kill=False,
            weapons={8: 2},
        ),
    }
    return Engagement(
        id=7,
        start_time=1000,
        end_time=1800,
        duration=800,
        target_guid="TARGET1",
        target_name="Allied Target",
        target_team="ALLIES",
        outcome="killed",
        total_damage=75,
        killer_guid="ATTACKER1",
        killer_name="Axis One",
        num_attackers=2,
        is_crossfire=True,
        crossfire_delay=90,
        crossfire_participants=["ATTACKER1", "ATTACKER2"],
        start_x=0.0,
        start_y=0.0,
        start_z=0.0,
        end_x=64.0,
        end_y=32.0,
        end_z=0.0,
        distance_traveled=88.0,
        position_path=[],
        attackers=attackers,
    )


@pytest.mark.asyncio
async def test_get_proximity_player_profile_counts_only_real_final_blows():
    db = _ProfileDB()

    payload = await api_router.get_proximity_player_profile("ATTACKER1", range_days=30, db=db)

    normalized_query = _normalize_sql(db.kill_query)
    assert "jsonb_array_elements" in normalized_query
    assert "attacker->>'guid' = $1" in normalized_query
    assert "got_kill" in normalized_query
    assert "attackers::text like" not in normalized_query
    assert payload["player_name"] == "Alpha"
    assert payload["total_kills"] == 5


@pytest.mark.asyncio
async def test_player_teamplay_upsert_recomputes_averages_on_conflict():
    db = _CaptureDB()
    parser = ProximityParserV4(db_adapter=db)
    parser.engagements = [_build_crossfire_engagement()]

    await parser._update_player_stats()

    assert db.calls
    query, _ = db.calls[0]
    normalized_query = _normalize_sql(query)
    assert "insert into player_teamplay_stats" in normalized_query
    assert "avg_crossfire_delay_ms = case" in normalized_query
    assert "avg_escape_distance = case" in normalized_query
    assert "avg_engagement_duration_ms = case" in normalized_query


@pytest.mark.asyncio
async def test_crossfire_pair_upsert_recomputes_avg_delay_on_conflict():
    db = _CaptureDB()
    parser = ProximityParserV4(db_adapter=db)
    parser.engagements = [_build_crossfire_engagement()]

    await parser._update_crossfire_pairs()

    assert len(db.calls) == 1
    query, params = db.calls[0]
    normalized_query = _normalize_sql(query)
    assert "insert into crossfire_pairs" in normalized_query
    assert "avg_delay_ms = case" in normalized_query
    assert params[7] == 90.0


def test_parse_focus_fire_line():
    """FOCUS_FIRE section line should be parsed into FocusFireEvent."""
    parser = ProximityParserV4()
    line = "42;DEADBEEF01234567;TestPlayer;3;GUID1,GUID2,GUID3;180;1200;0.745"
    parser._parse_focus_fire_line(line)

    assert len(parser.focus_fire_events) == 1
    ff = parser.focus_fire_events[0]
    assert ff.engagement_id == 42
    assert ff.target_guid == "DEADBEEF01234567"
    assert ff.target_name == "TestPlayer"
    assert ff.attacker_count == 3
    assert ff.attacker_guids == "GUID1,GUID2,GUID3"
    assert ff.total_damage == 180
    assert ff.duration == 1200
    assert abs(ff.focus_score - 0.745) < 1e-6


def test_parse_focus_fire_line_too_few_fields():
    """Lines with <8 fields should be silently skipped."""
    parser = ProximityParserV4()
    parser._parse_focus_fire_line("42;GUID;Name;3;GUIDS;180;1200")
    assert len(parser.focus_fire_events) == 0


def test_focus_fire_section_detection():
    """parse_file should detect # FOCUS_FIRE section and parse its lines."""
    import tempfile, os
    content = """# map=oasis
# round=1
# round_start_unix=1700000000
# round_end_unix=1700001800
# FOCUS_FIRE
1;AABB;Player1;2;G1,G2;120;800;0.650
2;CCDD;Player2;3;G3,G4,G5;200;1500;0.880
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='_engagements.txt', delete=False) as f:
        f.write(content)
        f.flush()
        path = f.name

    try:
        parser = ProximityParserV4()
        result = parser.parse_file(path)
        assert result is True
        assert len(parser.focus_fire_events) == 2
        assert parser.focus_fire_events[0].focus_score == 0.650
        assert parser.focus_fire_events[1].attacker_count == 3
    finally:
        os.unlink(path)


@pytest.mark.asyncio
async def test_reimport_skips_aggregates_on_second_import():
    """Double-importing the same file must not double aggregate stats."""
    db = _CaptureDB()
    # Simulate table existence checks
    db.fetch_one_responses = {
        "information_schema.columns": (1,),  # all tables exist
        "proximity_processed_files": None,    # first import: not processed yet
    }
    parser = ProximityParserV4(db_adapter=db)
    parser.engagements = [_build_crossfire_engagement()]

    # First import: aggregates should run
    first_already = await parser._check_processed_file("test_file.txt")
    assert first_already is False  # file not yet in processed table

    # Simulate second import: file was processed
    db.fetch_one_responses["proximity_processed_files"] = (True,)  # aggregates_applied=True
    second_already = await parser._check_processed_file("test_file.txt")
    assert second_already is True  # should skip aggregates
