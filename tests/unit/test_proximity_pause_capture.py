"""Whole Lua writer / real file / parser proof; no live ET or database claims."""

import json
import shutil
import subprocess
from dataclasses import asdict
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from proximity.parser.capability_manifest import build_manifest, scan_file
from proximity.parser.parser import PathPoint, PlayerTrack, ProximityParserV4
from tests.unit.test_round_web_service import _SnapshotStubDb
from website.backend.services.round_web_service import derive_velocity, get_round_snapshot

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", ["resume", "paused_end", "unknown"])
async def test_whole_writer_pause_capture_reaches_parser_and_receipt(tmp_path, scenario):
    lua = shutil.which("lua5.4")
    assert lua, "lua5.4 is required for the capture contract"
    result = subprocess.run(
        [lua, "tests/lua/engine_clock_contract_harness.lua", str(tmp_path), scenario],
        cwd=ROOT, capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"PAUSE CAPTURE PROOF: {scenario}; real file closed" in result.stdout
    paths = list(tmp_path.glob("*_engagements.txt"))
    assert len(paths) == 1
    assert f"CAPTURE_FILE={paths[0]}" in result.stdout
    db = AsyncMock()
    parser = ProximityParserV4(db_adapter=db)
    assert parser.parse_file(str(paths[0]))
    manifest = parser.build_capability_manifest()
    assert manifest == build_manifest(**scan_file(str(paths[0])))
    assert manifest["capture_pauses"] == {
        "status": "declared", "policy": "observed_pause_gate_v1",
        "pause_observed": scenario != "unknown", "signal_unknown": scenario == "unknown",
    }
    assert manifest["event_time_basis"] == {"status": "declared", "value": "level_time_offset_v1"}
    assert len(parser.player_tracks) == 1
    track = parser.player_tracks[0]
    assert track.death_type == "round_end"
    assert track.total_distance == (10 if scenario == "paused_end" else 20)
    assert track.post_spawn_distance == 10
    assert sum(p.event == "capture_resume" for p in track.path) == (scenario != "paused_end")
    # Independent path calculation: never charge the incoming discontinuity.
    assert sum(abs(b.x - a.x) for a, b in zip(track.path, track.path[1:])
               if b.event != "capture_resume") == track.total_distance
    assert track.stance_standing_sec == pytest.approx(0.2 if scenario == "paused_end" else 0.4)
    assert parser._compute_support_uptime() is None  # noqa: SLF001 - derived contract
    parser._table_has_column = AsyncMock(return_value=True)  # noqa: SLF001 - no live DB
    await parser._mark_file_processed(paths[0].name, "2026-10-08")  # noqa: SLF001
    receipt = json.loads(db.execute.call_args.args[1][3])
    assert receipt["capture_pauses"] == manifest["capture_pauses"]
    if scenario != "paused_end":
        boundary = next(p for p in track.path if p.event == "capture_resume")
        snapshot_db = _SnapshotStubDb(tracks=[(
            track.guid, track.name, track.team, track.player_class,
            track.spawn_time, track.death_time, [asdict(p) for p in track.path], "supply", 1,
        )], capabilities=manifest)
        payload = await get_round_snapshot(snapshot_db, 1, boundary.time)
        assert payload["players"][0]["vx"] is None
        assert payload["players"][0]["velocity_reason"] == "capture_discontinuity"
        print("SNAPSHOT PROOF:", payload["players"][0]["velocity_reason"])
    print(result.stdout)


@pytest.mark.parametrize("values,declared", [
    ([], False), (["observed_pause_gate_v1:0:0"], True),
    (["observed_pause_gate_v1:0:0"] * 2, True),
    (["observed_pause_gate_v1:0:1"], True),
    (["observed_pause_gate_v1:1:1"], True),
    (["observed_pause_gate_v2:0:0"], False),
    (["observed_pause_gate_v1:0:0", "observed_pause_gate_v1:1:0"], False),
    (["broken", "observed_pause_gate_v1:0:0"], False),
    (["observed_pause_gate_v1:0:0", "broken", "observed_pause_gate_v1:0:0"], False),
])
def test_pause_quality_is_explicit_sticky_and_shared_by_readers(tmp_path, values, declared):
    path = tmp_path / "2026-10-08-120000-supply-round-1_engagements.txt"
    path.write_text("# PROXIMITY_TRACKER_V6\n# map=supply\n# round=1\n" +
                    "".join(f"# capture_pauses={value}\n" for value in values))
    parser = ProximityParserV4()
    assert parser.parse_file(str(path))
    manifest = parser.build_capability_manifest()
    assert manifest == build_manifest(**scan_file(str(path)))
    assert manifest["capture_pauses"]["status"] == ("declared" if declared else "unknown")
    # Reuse must not leak evidence from a previous file into historical data.
    path.write_text("# PROXIMITY_TRACKER_V6\n# map=supply\n# round=1\n")
    assert parser.parse_file(str(path))
    assert parser.build_capability_manifest()["capture_pauses"] == {"status": "unknown"}


def test_resume_marker_is_not_a_speed_stance_or_sprint_measurement():
    points = [
        PathPoint(0, 0, 0, 0, 100, 0, 8, 0, 0, "spawn"),
        PathPoint(200, 10, 0, 0, 100, 50, 8, 0, 1, "sample"),
        PathPoint(400, 1000, 0, 0, 100, 999, 8, 2, 1, "capture_resume"),
        PathPoint(600, 1010, 0, 0, 100, 60, 8, 1, 0, "sample"),
    ]
    track = PlayerTrack("g", "Player", "AXIS", "MEDIC", 0, 600, None, "round_end", 4, points)
    assert track.total_distance == 20
    assert track.post_spawn_distance == 10
    assert track.avg_speed == 55
    assert track.peak_speed == 60
    assert track.sprint_percentage == pytest.approx(100 / 3)
    assert track.stance_prone_sec == 0
    assert track.sprint_sec == pytest.approx(0.2)
    parser = ProximityParserV4()
    parser.player_tracks = [track]
    assert parser._compute_support_uptime() is None  # noqa: SLF001 - missing header guard
    track.path = [points[2]]
    assert track.avg_speed == track.peak_speed == track.sprint_percentage == 0
    track.path = points[2:]
    assert track.total_distance == 10
    assert track.post_spawn_distance == 0  # spawn point itself was unobserved


@pytest.mark.parametrize("duplicate", [False, True])
def test_spiderweb_velocity_cannot_bridge_explicit_short_pause(duplicate):
    path = [
        {"time": 0, "x": 0, "y": 0, "z": 0, "event": "sample"},
        {"time": 200, "x": 20, "y": 0, "z": 0, "event": "capture_resume"},
    ]
    if duplicate:
        path.append({**path[-1], "event": "sample"})
    assert derive_velocity(path, len(path) - 1, 400) == (
        None, None, None, None, "capture_discontinuity")
    path.append({"time": 400, "x": 30, "y": 0, "z": 0, "event": "sample"})
    assert derive_velocity(path, len(path) - 1, 400) == (50, 0, 0, 200, None)
