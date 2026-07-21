"""Unit tests for compute_momentum_session (stopwatch-aware team stitching)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.services.session_scope import GamingSessionScope
from website.backend.services.storytelling.service import StorytellingService

A1, A2 = "AAAA1111" + "0" * 24, "AAAA2222" + "0" * 24
B1, B2 = "BBBB1111" + "0" * 24, "BBBB2222" + "0" * 24

_SCOPE = GamingSessionScope(
    gaming_session_id=55,
    dates=("2026-06-09",),
    round_keys=((1000, "supply", 1), (2000, "supply", 2)),
    accepted_round_count=2,
    distinct_map_names=("supply",),
)


def _service_with(internal_rounds, groups, label_rows):
    svc = StorytellingService(AsyncMock())
    svc._momentum_rounds = AsyncMock(return_value=internal_rounds)
    svc._build_player_groups = AsyncMock(return_value=groups)
    svc.db.fetch_all = AsyncMock(return_value=label_rows)  # _team_labels query
    return svc


def _round(rn, rsu, map_name, points):
    return {"round_number": rn, "map_name": map_name, "round_start_unix": rsu,
            "points": points}


GROUPS = {
    "group_a_players": ["olz", "wise"],
    "group_b_players": ["SuperBoyy", "vid"],
    "round_map": {
        # R1: A=AXIS; R2 (stopwatch swap): A=ALLIES
        (1000, "AXIS"): "group_a", (1000, "ALLIES"): "group_b",
        (2000, "AXIS"): "group_b", (2000, "ALLIES"): "group_a",
    },
    "guid_to_group": {A1[:8]: "group_a", A2[:8]: "group_a",
                      B1[:8]: "group_b", B2[:8]: "group_b"},
    "defaulted_players_count": 0,
}

LABEL_ROWS = [
    (A1[:8], "olz", 50), (B1[:8], "SuperBoyy", 45),
    (A2[:8], "wise", 30), (B2[:8], "vid", 20),
]


@pytest.mark.asyncio
async def test_session_stitch_keeps_logical_team_across_swap():
    # R1: axis (group_a) dominates at 80; R2 after swap the SAME logical team
    # is allies — allies at 80 must still land in team_a.
    rounds = [
        _round(1, 1000, "supply", [{"t_ms": 0, "axis": 80.0, "allies": 20.0}]),
        _round(2, 2000, "supply", [{"t_ms": 0, "axis": 20.0, "allies": 80.0}]),
    ]
    svc = _service_with(rounds, GROUPS, LABEL_ROWS)
    res = await svc.compute_momentum_session(_SCOPE)

    assert res["status"] == "ok"
    assert [p["team_a"] for p in res["points"]] == [80.0, 80.0]
    assert [p["team_b"] for p in res["points"]] == [20.0, 20.0]


@pytest.mark.asyncio
async def test_boundaries_and_cumulative_timeline():
    rounds = [
        _round(1, 1000, "supply", [{"t_ms": 0, "axis": 50, "allies": 50},
                                   {"t_ms": 30_000, "axis": 60, "allies": 40}]),
        _round(2, 2000, "supply", [{"t_ms": 0, "axis": 50, "allies": 50}]),
    ]
    svc = _service_with(rounds, GROUPS, LABEL_ROWS)
    res = await svc.compute_momentum_session(_SCOPE)

    # R1 duration = last t_ms + window (30s) = 60s; R2 starts at 60_000.
    assert [b["x_ms"] for b in res["round_boundaries"]] == [0, 60_000]
    assert res["points"][-1]["t_ms"] == 60_000
    assert res["meta"]["rounds"] == 2 and res["meta"]["unmapped_rounds"] == 0


@pytest.mark.asyncio
async def test_unmapped_round_skipped_and_reported():
    rounds = [
        _round(1, 1000, "supply", [{"t_ms": 0, "axis": 50, "allies": 50}]),
        _round(1, 9999, "orphan_map", [{"t_ms": 0, "axis": 50, "allies": 50}]),
    ]
    svc = _service_with(rounds, GROUPS, LABEL_ROWS)
    res = await svc.compute_momentum_session(_SCOPE)

    assert res["meta"]["rounds"] == 1
    assert res["meta"]["unmapped_rounds"] == 1


@pytest.mark.asyncio
async def test_team_labels_top_two_killers():
    rounds = [_round(1, 1000, "supply", [{"t_ms": 0, "axis": 50, "allies": 50}])]
    svc = _service_with(rounds, GROUPS, LABEL_ROWS)
    res = await svc.compute_momentum_session(_SCOPE)

    assert res["teams"]["team_a"]["label"] == "olz & wise"
    assert res["teams"]["team_b"]["label"] == "SuperBoyy & vid"
    assert res["teams"]["team_a"]["players"] == ["olz", "wise"]


@pytest.mark.asyncio
async def test_partial_groups_yield_no_team_data():
    rounds = [_round(1, 1000, "supply", [{"t_ms": 0, "axis": 50, "allies": 50}])]
    svc = _service_with(rounds, {"_status": "partial_data", "_reason": "no_r1_data"}, [])
    res = await svc.compute_momentum_session(_SCOPE)

    assert res["status"] == "no_team_data"
    assert res["reason"] == "no_r1_data"
