from pathlib import Path

import pytest

from proximity.parser.parser import ProximityParserV4


class _FakeDB:
    def __init__(self):
        self.calls = []

    async def execute(self, query, params=None):
        self.calls.append((query, params))


def _write_reaction_fixture(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "# PROXIMITY_TRACKER_V4",
                "# map=supply",
                "# round=1",
                "# crossfire_window=1000",
                "# escape_time=5000",
                "# escape_distance=300",
                "# position_sample_interval=200",
                "# round_start_unix=1770900000",
                "# round_end_unix=1770900600",
                "# ENGAGEMENTS",
                "# id;start_time;end_time;duration;target_guid;target_name;target_team;outcome;total_damage;killer_guid;killer_name;num_attackers;is_crossfire;crossfire_delay;crossfire_participants;start_x;start_y;start_z;end_x;end_y;end_z;distance_traveled;positions;attackers",
                "# PLAYER_TRACKS",
                "# guid;name;team;class;spawn_time;death_time;first_move_time;death_type;samples;path",
                "# KILL_HEATMAP",
                "# grid_x;grid_y;axis_kills;allies_kills",
                "# MOVEMENT_HEATMAP",
                "# grid_x;grid_y;traversal;combat;escape",
                "# REACTION_METRICS",
                "# engagement_id;target_guid;target_name;target_team;target_class;outcome;num_attackers;return_fire_ms;dodge_reaction_ms;support_reaction_ms;start_time;end_time;duration",
                "1;GUIDAXIS001;Axis Medic;AXIS;MEDIC;killed;2;410;620;950;1000;2200;1200",
                "2;GUIDALLY001;Allied Eng;ALLIES;ENGINEER;escaped;3;;;780;3000;5200;2200",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_parse_file_extracts_reaction_metrics(tmp_path):
    file_path = tmp_path / "2026-02-19-170000-supply-round-1_engagements.txt"
    _write_reaction_fixture(file_path)

    parser = ProximityParserV4(output_dir=str(tmp_path), gametimes_dir=str(tmp_path))
    assert parser.parse_file(str(file_path)) is True

    assert len(parser.reaction_metrics) == 2
    first = parser.reaction_metrics[0]
    second = parser.reaction_metrics[1]

    assert first.target_class == "MEDIC"
    assert first.return_fire_ms == 410
    assert first.dodge_reaction_ms == 620
    assert first.support_reaction_ms == 950

    assert second.target_class == "ENGINEER"
    assert second.return_fire_ms is None
    assert second.dodge_reaction_ms is None
    assert second.support_reaction_ms == 780


@pytest.mark.asyncio
async def test_import_reaction_metrics_writes_target_class_and_timings(tmp_path):
    file_path = tmp_path / "2026-02-19-170000-supply-round-1_engagements.txt"
    _write_reaction_fixture(file_path)

    db = _FakeDB()
    parser = ProximityParserV4(db_adapter=db, output_dir=str(tmp_path), gametimes_dir=str(tmp_path))
    assert parser.parse_file(str(file_path)) is True

    async def _has_column(_table, _col):
        return True

    parser._table_has_column = _has_column  # type: ignore[method-assign]
    await parser._import_reaction_metrics("2026-02-19")

    assert len(db.calls) == 2
    query, params = db.calls[0]
    assert "INSERT INTO proximity_reaction_metric" in query
    assert "target_class" in query
    assert "ON CONFLICT (session_date, round_number, round_start_unix, engagement_id, target_guid)" in query
    assert "MEDIC" in params
    assert 410 in params
    assert 620 in params
    assert 950 in params

