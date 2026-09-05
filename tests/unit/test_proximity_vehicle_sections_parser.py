"""v6.14 vehicle sections (docs/design/20 slice 2): the two trailing
VEHICLE_PROGRESS fields and the new VEHICLE_DESTROYED section, parsed and
imported — and the 12-field pre-v6.14 line still parsing, because the
corpus is mostly that."""
# ruff: noqa: SLF001 — the parser's section handlers and importer are private by
# convention and exercised directly, as the sibling parser tests do.
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from proximity.parser.capability_manifest import SECTION_GATES
from proximity.parser.parser import ProximityParserV4


def _parser(tmp_path: Path, db=None) -> ProximityParserV4:
    return ProximityParserV4(output_dir=str(tmp_path), gametimes_dir=str(tmp_path), db_adapter=db)


def test_vehicle_progress_reads_the_two_trailing_fields_and_keeps_the_12_field_floor(tmp_path):
    p = _parser(tmp_path)
    p._parse_vehicle_progress_line("truck;script_mover;1;2;3;4;5;6;1234.5;800;0;1;61000;118500")
    p._parse_vehicle_progress_line("tank;script_mover;1;2;3;4;5;6;99.0;1200;1200;0\n")
    assert len(p.vehicle_progress) == 2
    new, old = p.vehicle_progress
    assert (new.first_move_time, new.last_move_time) == (61000, 118500)
    assert (old.first_move_time, old.last_move_time) == (None, None)
    # Lua writes 0 for "never moved": that is no time, not t=0.
    p._parse_vehicle_progress_line("tank;script_mover;1;2;3;4;5;6;0.0;1200;1200;0;0;0")
    assert (p.vehicle_progress[-1].first_move_time, p.vehicle_progress[-1].last_move_time) == (None, None)
    # Short and malformed lines are skipped, never raised.
    p._parse_vehicle_progress_line("truck;script_mover;1;2;3")
    p._parse_vehicle_progress_line("truck;script_mover;x;2;3;4;5;6;1;2;3;4")
    assert len(p.vehicle_progress) == 3


def test_vehicle_destroyed_rows_parse_with_an_empty_attacker_allowed(tmp_path):
    p = _parser(tmp_path)
    p._parse_vehicle_destroyed_line("truck;118900;GUID3ABCDEF;^1kanii;allies;5;800")
    p._parse_vehicle_destroyed_line("truck;200000;;;;0;350\n")
    p._parse_vehicle_destroyed_line("truck;bad;;;;0;1")
    assert [(d.time, d.attacker_guid, d.means_of_death, d.health_before) for d in p.vehicle_destroyed] == [
        (118900, "GUID3ABCDEF", 5, 800),
        (200000, "", 0, 350),
    ]


def test_the_section_is_dispatched_from_a_file_and_gated_on_vehicle_tracking(tmp_path):
    lines = [
        "# PROXIMITY_TRACKER_V4",
        "# map=supply",
        "# round=1",
        "# crossfire_window=2000",
        "# escape_time=3000",
        "# escape_distance=500",
        "# position_sample_interval=200",
        "# round_start_unix=1787770801",
        "# round_end_unix=1787771401",
        "# capabilities=vehicle_tracking:1",
        "",
        "# VEHICLE_PROGRESS",
        "# vehicle_name;vehicle_type;start_x;start_y;start_z;end_x;end_y;end_z;total_distance;max_health;final_health;destroyed_count;first_move_time;last_move_time",
        "truck;script_mover;1000;2000;10;1360;2000;10;360.0;800;0;1;1500;2500",
        "",
        "# VEHICLE_DESTROYED",
        "# vehicle_name;time;attacker_guid;attacker_name;attacker_team;means_of_death;health_before",
        "truck;4000;GUID3ABCDEF;bot3;allies;5;800",
        "",
    ]
    path = tmp_path / "2026-09-05-200000-supply-round-1_engagements.txt"
    path.write_text("\n".join(lines), encoding="utf-8")
    p = _parser(tmp_path)
    assert p.parse_file(str(path)) is True
    assert len(p.vehicle_progress) == 1 and p.vehicle_progress[0].first_move_time == 1500
    assert len(p.vehicle_destroyed) == 1 and p.vehicle_destroyed[0].attacker_guid == "GUID3ABCDEF"
    assert "VEHICLE_DESTROYED" in p.sections_with_rows
    assert SECTION_GATES["VEHICLE_DESTROYED"] == "vehicle_tracking"


class _FakeDB:
    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []

    async def execute(self, query, params=None):
        self.calls.append((query, params))


@pytest.mark.asyncio
async def test_import_writes_move_times_and_the_destruction_list_as_json_when_082_is_applied(tmp_path):
    db = _FakeDB()
    p = _parser(tmp_path, db)
    p.metadata = {"round_num": 1, "map_name": "supply", "round_start_unix": 1787770801, "round_end_unix": 1787771401}
    p._parse_vehicle_progress_line("truck;script_mover;1;2;3;4;5;6;360.0;800;0;1;1500;2500")
    p._parse_vehicle_destroyed_line("truck;4000;GUID3ABCDEF;bot3;allies;5;800")
    p._parse_vehicle_destroyed_line("tank;9000;;;;0;100")  # another vehicle: must not land on the truck

    async def _has_column(_table, _col):
        return True

    p._table_has_column = _has_column
    await p._import_vehicle_progress("2026-09-05")
    assert len(db.calls) == 1
    query, params = db.calls[0]
    assert "INSERT INTO proximity_vehicle_progress" in query
    assert "first_move_time" in query and "destroyed_events" in query
    assert 1500 in params and 2500 in params
    events = json.loads([v for v in params if isinstance(v, str) and v.startswith("[")][0])
    assert events == [{
        "time": 4000, "attacker_guid": "GUID3ABCDEF", "attacker_name": "bot3",
        "attacker_team": "allies", "means_of_death": 5, "health_before": 800,
    }]


@pytest.mark.asyncio
async def test_import_stays_on_the_old_column_set_before_082(tmp_path):
    db = _FakeDB()
    p = _parser(tmp_path, db)
    p.metadata = {"round_num": 1, "map_name": "supply", "round_start_unix": 1787770801, "round_end_unix": 1787771401}
    p._parse_vehicle_progress_line("truck;script_mover;1;2;3;4;5;6;360.0;800;0;1;1500;2500")

    async def _has_column(_table, col):
        return col not in ("first_move_time", "last_move_time", "destroyed_events")

    p._table_has_column = _has_column
    await p._import_vehicle_progress("2026-09-05")
    query, params = db.calls[0]
    assert "first_move_time" not in query and "destroyed_events" not in query
    assert 1500 not in params
