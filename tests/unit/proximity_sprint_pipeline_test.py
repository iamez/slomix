from pathlib import Path

import pytest

from proximity.parser.parser import ProximityParserV4


class _FakeDB:
    def __init__(self):
        self.calls = []

    async def execute(self, query, params=None):
        self.calls.append((query, params))

    async def fetch_one(self, query, params=None):
        return (1,)


def _write_sprint_fixture(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "# PROXIMITY_TRACKER_V4",
                "# map=supply",
                "# round=1",
                "# crossfire_window=1000",
                "# escape_time=5000",
                "# escape_distance=300",
                "# position_sample_interval=500",
                "# round_start_unix=1770900000",
                "# round_end_unix=1770900600",
                "# ENGAGEMENTS",
                "# id;start_time;end_time;duration;target_guid;target_name;target_team;outcome;total_damage;killer_guid;killer_name;num_attackers;is_crossfire;crossfire_delay;crossfire_participants;start_x;start_y;start_z;end_x;end_y;end_z;distance_traveled;positions;attackers",
                "# PLAYER_TRACKS",
                "# guid;name;team;class;spawn_time;death_time;first_move_time;death_type;samples;path",
                "# path format: time,x,y,z,health,speed,weapon,stance,sprint,event separated by |",
                "# stance: 0=standing, 1=crouching, 2=prone | sprint: 0=no, 1=yes",
                (
                    "GUIDAXIS001;Axis Runner;AXIS;MEDIC;1000;0;1500;round_end;6;"
                    "1000,0.0,0.0,0.0,100,0.0,8,0,0,spawn|"
                    "1500,20.0,0.0,0.0,100,120.0,8,0,1,sample|"
                    "2000,40.0,0.0,0.0,100,130.0,8,0,1,sample|"
                    "2500,60.0,0.0,0.0,100,125.0,8,0,1,sample|"
                    "3000,70.0,0.0,0.0,100,40.0,8,0,0,sample|"
                    "3500,80.0,0.0,0.0,100,30.0,8,0,0,round_end"
                ),
                (
                    "GUIDALLY001;Ally Walker;ALLIES;ENGINEER;1000;0;0;round_end;6;"
                    "1000,10.0,10.0,0.0,100,0.0,8,0,0,spawn|"
                    "1500,11.0,10.0,0.0,100,20.0,8,0,0,sample|"
                    "2000,12.0,10.0,0.0,100,15.0,8,0,0,sample|"
                    "2500,13.0,10.0,0.0,100,18.0,8,0,0,sample|"
                    "3000,14.0,10.0,0.0,100,25.0,8,0,0,sample|"
                    "3500,15.0,10.0,0.0,100,22.0,8,0,0,round_end"
                ),
                "# KILL_HEATMAP",
                "# grid_x;grid_y;axis_kills;allies_kills",
                "# MOVEMENT_HEATMAP",
                "# grid_x;grid_y;traversal;combat;escape",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_sprint_percentage_propagates_to_player_track_insert(tmp_path):
    file_path = tmp_path / "2026-02-12-235959-supply-round-1_engagements.txt"
    _write_sprint_fixture(file_path)

    db = _FakeDB()
    parser = ProximityParserV4(db_adapter=db, output_dir=str(tmp_path), gametimes_dir=str(tmp_path))
    ok = await parser.import_file(str(file_path), "2026-02-12")

    assert ok is True
    assert len(parser.player_tracks) == 2

    by_guid = {track.guid: track for track in parser.player_tracks}
    assert by_guid["GUIDAXIS001"].sprint_percentage == 50.0
    assert by_guid["GUIDALLY001"].sprint_percentage == 0.0

    track_inserts = [(q, p) for q, p in db.calls if "INSERT INTO player_track" in q]
    assert len(track_inserts) == 2

    sprint_values = sorted(float(params[-1]) for _, params in track_inserts)
    assert sprint_values == [0.0, 50.0]

    axis_insert = next(params for _, params in track_inserts if "GUIDAXIS001" in params)
    axis_path_json = next(
        value for value in axis_insert if isinstance(value, str) and value.startswith("[")
    )
    assert '"sprint": 1' in axis_path_json
