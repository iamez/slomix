"""Unit tests for GET /proximity/player-journey (proximity_journey.py).

Covers: life bucketing of kills/deaths, the 1s nearest-teammate/enemy series
(synthetic 2-player paths with known distances), NULL/empty path handling,
path downsampling, and spawn-timing enrichment.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.routers.proximity_journey import (
    _downsample_path,
    get_player_journey,
)

SUBJECT = "EDBB5DA97C9F52151865C5F223F9B951"
MATE = "FDA127DF5246F28D7355490F749DD894"
ENEMY = "5D9891600C7948FF85709360E669D5A4"


def _path(points: list[tuple[int, float, float]]) -> str:
    return json.dumps([
        {"time": t, "x": x, "y": y, "z": 0, "health": 100,
         "speed": 0, "stance": 0, "sprint": 0, "event": "sample"}
        for t, x, y in points
    ])


def _track(guid, name, team, cls, spawn, death, path_points):
    duration = (death - spawn) if death else None
    return (guid, name, team, cls, spawn, death, duration,
            _path(path_points), 100.0, 10.0)


async def _call(db, **overrides):
    kwargs = dict(
        session_date="2026-06-09", map_name="etl_frostbite", round_number=1,
        player_guid=SUBJECT, round_start_unix=1781039014,
        downsample_ms=400, db=db,
    )
    kwargs.update(overrides)
    return await get_player_journey(**kwargs)


@pytest.mark.asyncio
async def test_no_tracks_returns_empty() -> None:
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[])
    res = await _call(db)
    assert res["status"] == "ok"
    assert res["lives"] == []
    assert res["summary"]["lives"] == 0


@pytest.mark.asyncio
async def test_kills_bucket_into_correct_life() -> None:
    db = AsyncMock()
    tracks = [
        _track(SUBJECT, "Subject", "AXIS", "MEDIC", 0, 10000,
               [(0, 0, 0), (5000, 100, 0), (10000, 200, 0)]),
        _track(SUBJECT, "Subject", "AXIS", "MEDIC", 15000, 30000,
               [(15000, 0, 0), (22000, 50, 0), (30000, 100, 0)]),
    ]
    kills = [
        # kill in life 1 window
        (5000, SUBJECT, "Subject", ENEMY, "Enemy", "gibbed", 12000, "", ""),
        # subject dies at the end of life 2
        (30000, ENEMY, "Enemy", SUBJECT, "Subject", "tapped_out", 0, "", ""),
        # kill in the gap between lives — must not bucket anywhere
        (12000, SUBJECT, "Subject", ENEMY, "Enemy", "gibbed", 0, "", ""),
    ]
    st = [
        (5000, SUBJECT, ENEMY, 30000, 12000, 0.4),
        (30000, ENEMY, SUBJECT, 25000, 20000, 0.8),
    ]
    db.fetch_all = AsyncMock(side_effect=[tracks, kills, st, [], [], []])

    res = await _call(db)

    assert res["summary"] == {
        "lives": 2, "kills": 1, "deaths": 1,
        "avg_life_s": 12.5, "objective_events": 0,
    }
    life1, life2 = res["lives"]
    assert len(life1["kills"]) == 1
    assert life1["kills"][0]["spawn_timing_score"] == 0.4
    assert life1["kills"][0]["time_to_next_spawn"] == 12000
    assert life1["death"] is None
    assert life2["kills"] == []
    assert life2["death"]["killer_name"] == "Enemy"
    assert life2["death"]["victim_wait_ms"] == 20000


@pytest.mark.asyncio
async def test_proximity_series_nearest_math_and_solo() -> None:
    db = AsyncMock()
    # Subject stands still at (0,0); teammate at (300,0) = inside 500u;
    # enemy at (1000,0). All alive 0..10s.
    tracks = [
        _track(SUBJECT, "Subject", "AXIS", "MEDIC", 0, 10000,
               [(t * 1000, 0, 0) for t in range(11)]),
        _track(MATE, "Mate", "AXIS", "ENGINEER", 0, 10000,
               [(t * 1000, 300, 0) for t in range(11)]),
        _track(ENEMY, "Enemy", "ALLIES", "MEDIC", 0, 10000,
               [(t * 1000, 1000, 0) for t in range(11)]),
    ]
    db.fetch_all = AsyncMock(side_effect=[tracks, [], [], [], [], []])

    res = await _call(db)

    life = res["lives"][0]
    sample = life["proximity_series"][5]
    assert sample["nearest_teammate"] == 300.0
    assert sample["nearest_enemy"] == 1000.0
    assert sample["teammates_500u"] == 1
    assert sample["enemies_500u"] == 0
    assert life["solo_pct"] == 0.0  # teammate always within 500u


@pytest.mark.asyncio
async def test_solo_when_no_teammate_nearby() -> None:
    db = AsyncMock()
    tracks = [
        _track(SUBJECT, "Subject", "AXIS", "COVERTOPS", 0, 10000,
               [(t * 1000, 0, 0) for t in range(11)]),
        _track(MATE, "Mate", "AXIS", "MEDIC", 0, 10000,
               [(t * 1000, 5000, 0) for t in range(11)]),  # 5000u away
    ]
    db.fetch_all = AsyncMock(side_effect=[tracks, [], [], [], [], []])

    res = await _call(db)

    assert res["lives"][0]["solo_pct"] == 100.0


@pytest.mark.asyncio
async def test_empty_path_track_still_returns_life() -> None:
    db = AsyncMock()
    tracks = [
        (SUBJECT, "Subject", "AXIS", "MEDIC", 0, 5000, 5000, "[]", 0.0, 0.0),
    ]
    db.fetch_all = AsyncMock(side_effect=[tracks, [], [], [], [], []])

    res = await _call(db)

    life = res["lives"][0]
    assert life["path"] == []
    assert life["proximity_series"] == []
    assert life["solo_pct"] is None


def test_downsample_path_halves_200ms_to_400ms() -> None:
    path = [
        {"time": t, "x": float(t), "y": 0, "z": 0,
         "health": 100, "speed": 0, "stance": 0, "sprint": 0, "event": "sample"}
        for t in range(0, 2001, 200)  # 11 points
    ]
    out = _downsample_path(path, 400)
    assert [p["t"] for p in out] == [0, 400, 800, 1200, 1600, 2000]
    assert out[0]["health"] == 100  # rich fields preserved
