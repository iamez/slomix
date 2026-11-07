"""Cross-reader adversarial boundary proof; synthetic records, no live DB/ET."""

import copy
import json
import shutil
import subprocess
from dataclasses import asdict
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from proximity.parser.parser import PathPoint, PlayerTrack, ProximityParserV4
from shared.proximity_paths import capture_segments
from tests.unit.test_proximity_pause_readers import ReaderDb
from website.backend.dependencies import get_db
from website.backend.routers import replay_router

ROOT = Path(__file__).resolve().parents[2]


def boundary_track(marker_index=1, initial=False):
    prefix = [] if initial else [
        PathPoint(0, 0, 0, 0, 100, 0, 8, 0, 0, "spawn"),
        PathPoint(200, 10, 0, 0, 100, 50, 8, 0, 1, "sample"),
    ]
    boundary = [
        PathPoint(400, 990, 0, 0, 100, 999, 8, 2, 1, "sample"),
        PathPoint(400, 995, 0, 0, 100, 999, 8, 2, 1, "sample"),
        PathPoint(400, 1000, 0, 0, 100, 999, 8, 2, 1, "sample"),
    ]
    boundary[marker_index].event = "capture_resume"
    path = prefix + boundary + [PathPoint(600, 1010, 0, 0, 100, 60, 8, 1, 0, "sample")]
    return PlayerTrack("g", "Player", "AXIS", "MEDIC", 0, 600, None, "round_end", len(path), path)


@pytest.mark.parametrize("marker_index", [0, 1, 2])
@pytest.mark.parametrize("initial", [False, True])
def test_all_metrics_exclude_entire_boundary_group(marker_index, initial):
    track = boundary_track(marker_index, initial)
    before = copy.deepcopy(track)
    assert track.total_distance == (10 if initial else 20)
    assert track.post_spawn_distance == (0 if initial else 10)
    assert track.avg_speed == (60 if initial else 55)
    assert track.peak_speed == 60
    assert track.sprint_percentage == pytest.approx(0 if initial else 100 / 3)
    assert track.stance_standing_sec == (0 if initial else 0.2)
    assert track.stance_crouching_sec == 0.2
    assert track.stance_prone_sec == 0
    assert track.sprint_sec == (0 if initial else 0.2)
    assert track == before  # no destructive deduplication or cached mutable path


def test_mutating_path_does_not_reuse_old_boundary_eligibility():
    track = boundary_track()
    assert track.peak_speed == 60
    for p in track.path:
        if p.event == "capture_resume":
            p.event = "sample"
    assert track.peak_speed == 999  # unmarked historical behaviour stays unchanged
    assert track.total_distance == 1010


@pytest.mark.parametrize("marker_index", range(1, 5))
def test_distance_matches_segment_geometry_for_every_marker_order(marker_index):
    track = boundary_track()
    track.path = [PathPoint(t, x, 2*x, 3*x, 100, 0, 8, 0, 0, "sample")
                  for t, x in [(0, 0), (200, 3), (200, 5), (200, 9), (200, 12), (400, 15)]]
    track.path[marker_index].event = "capture_resume"
    segments = capture_segments([asdict(p) for p in track.path])
    expected = 3 * (14 ** 0.5)  # ONLY outgoing (12,24,36) -> (15,30,45)
    independent = sum(sum((b[k] - a[k]) ** 2 for k in ("x", "y", "z")) ** 0.5
                      for s in segments for a, b in zip(s, s[1:]))
    assert track.total_distance == pytest.approx(expected)
    assert independent == pytest.approx(expected)


@pytest.fixture(params=["paused_death", "resume_death"])
def emitted_death(tmp_path, request):
    lua = shutil.which("lua5.4")
    if not lua:
        raise RuntimeError("lua5.4 required for real writer proof")
    result = subprocess.run(
        [lua, "tests/lua/engine_clock_contract_harness.lua", str(tmp_path), request.param],
        cwd=ROOT, capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stdout + result.stderr)
    files = list(tmp_path.glob("*_engagements.txt"))
    if len(files) != 1:
        raise RuntimeError(f"expected one closed file, got {files}")
    parser = ProximityParserV4(db_adapter=AsyncMock())
    if not parser.parse_file(str(files[0])) or len(parser.player_tracks) != 1:
        raise RuntimeError("full writer file must parse exactly one track")
    track = parser.player_tracks[0]
    if track.death_type != "world" or track.path[-1].event != (
        "sample" if request.param == "paused_death" else "capture_resume"
    ):
        raise RuntimeError("source/parser lifecycle proof changed; re-audit before updating xfail")
    print(f"LIFECYCLE PROOF: {request.param}; source/file/parser=world; last_point={track.path[-1].event}")
    return parser


@pytest.mark.asyncio
async def test_desired_import_preserves_independent_lifecycle(emitted_death):
    # Source/harness errors occur in the fixture, outside the desired-contract
    # assertion. A failing Lua run must not be mistaken for this known DB gap.
    parser = emitted_death
    parser._table_has_column = AsyncMock(return_value=True)  # noqa: SLF001
    parser._append_round_link_columns = AsyncMock()  # noqa: SLF001
    await parser._import_player_tracks("2099-01-01")  # noqa: SLF001
    sql, values = parser.db_adapter.execute.call_args.args
    columns = [name.strip() for name in sql.split("(", 1)[1].split(")", 1)[0].split(",")]
    stored = dict(zip(columns, values))
    assert stored.get("death_type") == "world", "player_track INSERT discarded parent death_type"


@pytest.mark.asyncio
async def test_imported_metrics_agree_with_actual_replay_endpoint():
    track = boundary_track()
    parser = ProximityParserV4(db_adapter=AsyncMock())
    parser.player_tracks = [track]
    parser.metadata.update(round_num=1, map_name="supply", round_start_unix=1000)
    parser._table_has_column = AsyncMock(return_value=False)  # noqa: SLF001
    parser._append_round_link_columns = AsyncMock()  # noqa: SLF001
    await parser._import_player_tracks("2099-01-01")  # noqa: SLF001 - actual importer
    sql, values = parser.db_adapter.execute.call_args.args
    columns = [name.strip() for name in sql.split("(", 1)[1].split(")", 1)[0].split(",")]
    stored = dict(zip(columns, values))
    assert stored["total_distance"] == 20
    assert stored["post_spawn_distance"] == 10
    assert stored["peak_speed"] == 60
    assert stored["stance_prone_sec"] == 0
    assert json.loads(stored["path"]) == [asdict(p) for p in track.path]

    db = ReaderDb(json.loads(stored["path"]))
    app = FastAPI()
    app.include_router(replay_router.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: db
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/replay/round/1/paths", params={"from": 0, "to": 1000})
    assert response.status_code == 200, response.text
    payload = response.json()
    distance = sum(abs(b["x"] - a["x"]) for path in payload["paths"]
                   for a, b in zip(path["samples"], path["samples"][1:]))
    assert distance == stored["total_distance"] == 20
    print(f"BOUNDARY IMPORT/ASGI PROOF: parser={stored['total_distance']}, replay={distance}; synthetic DB")
