"""Forward clock provenance; never infer history from a version or feature flag."""
import json

import pytest

from proximity.parser.capability_manifest import build_manifest, scan_file
from proximity.parser.parser import ProximityParserV4
from tests.unit.test_capability_manifest import _run_declaration
from tests.unit.test_parser_capability_manifest import TRACK_ROW

HEADER = "# PROXIMITY_TRACKER_V6\n# map=supply\n# round=1\n"
KNOWN = "level_time_offset_v1"


@pytest.mark.parametrize("values,status", [
    ([], "missing"), ([KNOWN], "declared"), ([KNOWN, KNOWN], "declared"),
    ([""], "unsupported"), (["active_time_v2"], "unsupported"),
    ([KNOWN, "active_time_v2", KNOWN], "conflicting"),
    (["active_time_v2", KNOWN], "conflicting"),
    (["active_time_v2", "active_time_v2"], "conflicting"),
])
def test_parser_and_scanner_agree_without_changing_event_data(tmp_path, values, status):
    path = tmp_path / "2026-10-06-120000-supply-round-1_engagements.txt"
    path.write_text(HEADER + "# capabilities=shot_fired:1\n" + "".join(
        f"# event_time_basis={value}\n" for value in values) + TRACK_ROW)
    parser = ProximityParserV4()
    assert parser.parse_file(str(path))
    manifest = parser.build_capability_manifest()
    assert manifest == build_manifest(**scan_file(str(path)))
    basis = manifest["event_time_basis"]
    assert basis == {"status": status, "value": KNOWN if status == "declared" else None}
    baseline = ProximityParserV4()
    old_path = tmp_path / "2026-10-06-120001-supply-round-1_engagements.txt"
    old_path.write_text(HEADER + TRACK_ROW)
    assert baseline.parse_file(str(old_path))
    assert parser.player_tracks == baseline.player_tracks


def test_parser_reuse_does_not_inherit_previous_clock(tmp_path):
    parser = ProximityParserV4()
    for index, suffix in enumerate([f"# event_time_basis={KNOWN}\n", ""]):
        path = tmp_path / f"2026-10-06-12000{index}-supply-round-1_engagements.txt"
        path.write_text(HEADER + suffix)
        assert parser.parse_file(str(path))
        assert parser.build_capability_manifest()["event_time_basis"]["status"] == (
            "declared" if index == 0 else "missing")


@pytest.mark.asyncio
async def test_executed_lua_declaration_reaches_receipt_json(tmp_path):
    from unittest.mock import AsyncMock

    emitted = _run_declaration(test_mode=False, features={})
    assert f"# event_time_basis={KNOWN}\n" in emitted
    path = tmp_path / "2026-10-06-120000-supply-round-1_engagements.txt"
    path.write_text(HEADER + emitted)
    db = AsyncMock()
    parser = ProximityParserV4(db_adapter=db)
    assert parser.parse_file(str(path))
    parser._table_has_column = AsyncMock(return_value=True)  # noqa: SLF001
    await parser._mark_file_processed(path.name, "2026-10-06")  # noqa: SLF001
    payload = json.loads(db.execute.call_args.args[1][3])
    assert payload["event_time_basis"] == {"status": "declared", "value": KNOWN}
    assert parser.build_capability_manifest() == build_manifest(**scan_file(str(path)))


@pytest.mark.parametrize("scenario", ["resume", "paused_end", "unknown"])
async def test_whole_lua_capture_quality_reaches_parser_and_receipt(tmp_path, scenario):
    """Run the shipped producer and check persisted quality and metric boundaries."""
    import shutil
    import subprocess
    from pathlib import Path
    from unittest.mock import AsyncMock

    lua = shutil.which("lua5.4")
    assert lua, "Lua5.4 required for actual capture contract"
    result = subprocess.run(
        [lua, "tests/lua/engine_clock_contract_harness.lua", str(tmp_path), scenario],
        cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"PAUSE CAPTURE PROOF: {scenario}; real file closed" in result.stdout
    files = list(tmp_path.glob("*_engagements.txt"))
    assert len(files) == 1
    db = AsyncMock()
    parser = ProximityParserV4(db_adapter=db)
    assert parser.parse_file(str(files[0]))
    manifest = parser.build_capability_manifest()
    assert manifest == build_manifest(**scan_file(str(files[0])))
    assert manifest["capture_pauses"] == {
        "status": "declared", "policy": "observed_pause_gate_v1",
        "pause_observed": scenario != "unknown", "signal_unknown": scenario == "unknown",
    }
    track, = parser.player_tracks
    assert track.total_distance == (10 if scenario == "paused_end" else 20)
    assert track.post_spawn_distance == 10
    assert sum(abs(b.x - a.x) for a, b in zip(track.path, track.path[1:])
               if b.event != "capture_resume") == track.total_distance
    assert track.stance_standing_sec == pytest.approx(0.2 if scenario == "paused_end" else 0.4)
    assert parser._compute_support_uptime() is None  # noqa: SLF001 -- quality must reach derived metrics
    parser._table_has_column = AsyncMock(return_value=True)  # noqa: SLF001 -- no database claim
    await parser._mark_file_processed(files[0].name, "2026-10-08")  # noqa: SLF001
    receipt = json.loads(db.execute.call_args.args[1][3])
    assert receipt["capture_pauses"] == manifest["capture_pauses"]
    print(result.stdout)
