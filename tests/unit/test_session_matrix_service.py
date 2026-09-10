"""Unit tests for SessionMatrixService.compute.

Covers the critical matrix-building paths without a live database:
- Empty / degenerate inputs returning ``available: False`` with reasons
- ET color code stripping on player_name
- Tri-format side normalization (int / string / faction name)
- Stopwatch side swap across R1/R2 (same team, opposite side)
- Mid-session substitution (same GUID on both teams)
- Division-by-zero guards (time_played=0, deaths=0, shots=0)
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from bot.services.stopwatch_scoring_service import StopwatchScoringService
from website.backend.services.session_matrix_service import (
    SessionMatrixService,
    extract_team_rosters,
)


# ---------------------------------------------------------------------------
# Fake adapters: record queries, return canned rows per call.
# ---------------------------------------------------------------------------

class FakeDB:
    """Minimal async DB that returns canned results in order of calls."""

    def __init__(self, fetch_all_results=None):
        self._fetch_all_queue = list(fetch_all_results or [])
        self.fetch_all_calls = []

    async def fetch_all(self, query, params=None):
        self.fetch_all_calls.append((query, params))
        if self._fetch_all_queue:
            return self._fetch_all_queue.pop(0)
        return []


def _matches(map_names, round_ids_per_map):
    """Helper to build the ``matches`` list the service expects."""
    out = []
    for name, rids in zip(map_names, round_ids_per_map, strict=True):
        out.append({
            "map_name": name,
            "rounds": [{"round_id": rid, "round_number": i + 1} for i, rid in enumerate(rids)],
        })
    return out


def _scoring_payload(team_a="Allies", team_b="Axis", scores=None):
    maps = scores or []
    return {
        "available": bool(maps),
        "team_a_name": team_a,
        "team_b_name": team_b,
        "maps": maps,
    }


# ---------------------------------------------------------------------------
# extract_team_rosters — shape normalization
# ---------------------------------------------------------------------------

def test_extract_team_rosters_none_returns_empty():
    assert extract_team_rosters(None) == {}


def test_extract_team_rosters_dict_with_guids():
    teams = {
        "Allies": {"guids": ["g1", "g2"]},
        "Axis": {"guids": ["g3"]},
    }
    assert extract_team_rosters(teams) == {
        "Allies": ["g1", "g2"],
        "Axis": ["g3"],
    }


def test_extract_team_rosters_list_of_dicts():
    teams = {
        "Allies": [{"guid": "g1"}, {"guid": "g2"}],
        "Axis": [{"guid": "g3"}],
    }
    assert extract_team_rosters(teams) == {
        "Allies": ["g1", "g2"],
        "Axis": ["g3"],
    }


def test_extract_team_rosters_list_of_strings():
    teams = {"Allies": ["g1", "g2"], "Axis": ["g3"]}
    assert extract_team_rosters(teams) == {
        "Allies": ["g1", "g2"],
        "Axis": ["g3"],
    }


# ---------------------------------------------------------------------------
# compute() — degenerate inputs
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compute_empty_rounds_returns_no_rounds():
    svc = SessionMatrixService(FakeDB(), StopwatchScoringService(FakeDB()))
    out = await svc.compute([], [], _scoring_payload(), {"Allies": {"guids": ["g1"]}})
    assert out == {"available": False, "reason": "no_rounds"}


@pytest.mark.asyncio
async def test_compute_no_teams_returns_no_teams():
    svc = SessionMatrixService(FakeDB(), StopwatchScoringService(FakeDB()))
    out = await svc.compute(
        [100], _matches(["battery"], [[100]]), _scoring_payload(), None,
    )
    assert out == {"available": False, "reason": "no_teams"}


@pytest.mark.asyncio
async def test_compute_single_team_returns_no_teams():
    svc = SessionMatrixService(FakeDB(), StopwatchScoringService(FakeDB()))
    out = await svc.compute(
        [100], _matches(["battery"], [[100]]), _scoring_payload(),
        {"Allies": {"guids": ["g1"]}},
    )
    assert out == {"available": False, "reason": "no_teams"}


# ---------------------------------------------------------------------------
# compute() — happy path with substitution + stopwatch swap
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compute_stopwatch_swap_and_substitution():
    """
    Scenario: 1 map with 2 rounds (stopwatch).
    - R1 (round_id=100): side=1 is Allies roster, side=2 is Axis roster
    - R2 (round_id=200): sides swap — side=1 is Axis roster, side=2 is Allies
    - Player g_sub plays for Allies in R1, substitutes into Axis in R2
    - Player g_fixed plays for Allies in both rounds

    Expected: substitute appears in BOTH rosters (once per team); g_fixed only in Allies.
    """
    # Side→team mapping query: rows for 2 rounds, 4 players
    side_mapping_rows = [
        (100, "g_ally1", 1),
        (100, "g_ally2", 1),
        (100, "g_sub", 1),
        (100, "g_axis1", 2),
        (100, "g_axis2", 2),
        # R2 swap: side=1 is now Axis roster
        (200, "g_axis1", 1),
        (200, "g_axis2", 1),
        (200, "g_sub", 1),  # substituted to Axis
        (200, "g_ally1", 2),
        (200, "g_ally2", 2),
    ]

    # Main stats query: (round_id, player_guid, name, side, kills, deaths, damage,
    # time_played, revives, times_revived, assists, gibs, hs_kills,
    # hits, shots, weapon_hs, return_fire_ms)
    stats_rows = [
        # R1 — Allies side=1
        (100, "g_ally1", "^1Allie1", 1, 10, 5, 1200, 300, 2, 1, 3, 0, 4, 100, 400, 30, 250.0),
        (100, "g_sub",    "Sub",      1,  5, 3,  800, 300, 1, 0, 1, 0, 1,  50, 200,  5, None),
        # R1 — Axis side=2
        (100, "g_axis1",  "Axis1",    2,  8, 6,  900, 300, 0, 0, 2, 1, 3,  80, 300, 20, 300.0),
        # R2 — Axis side=1 (swap)
        (200, "g_axis1",  "Axis1",    1, 12, 4, 1500, 300, 0, 0, 2, 0, 5,  90, 300, 40, 280.0),
        (200, "g_sub",    "Sub",      1,  3, 8,  500, 300, 0, 0, 0, 0, 0,  30, 200,  2, None),
        # R2 — Allies side=2
        (200, "g_ally1",  "^1Allie1", 2,  6, 7,  700, 300, 1, 1, 2, 0, 1,  60, 300, 10, 200.0),
    ]

    hardcoded = {
        "Allies": {"guids": ["g_ally1", "g_ally2", "g_sub"]},
        "Axis":   {"guids": ["g_axis1", "g_axis2"]},
    }
    matches = _matches(["battery"], [[100, 200]])
    payload = _scoring_payload(team_a="Allies", team_b="Axis", scores=[
        {"team_a_points": 1, "team_b_points": 0},
    ])

    # StopwatchScoringService.build_round_side_to_team_mapping consumes side_mapping_rows;
    # SessionMatrixService._fetch_stats consumes stats_rows.
    db = FakeDB(fetch_all_results=[side_mapping_rows, stats_rows])
    svc = SessionMatrixService(db, StopwatchScoringService(db))
    out = await svc.compute([100, 200], matches, payload, hardcoded)

    assert out["available"] is True
    assert out["team_a_name"] == "Allies"
    assert out["team_b_name"] == "Axis"
    assert len(out["maps"]) == 1

    allies_guids = {p["player_guid"] for p in out["rosters"]["team_a"]}
    axis_guids = {p["player_guid"] for p in out["rosters"]["team_b"]}
    assert allies_guids == {"g_ally1", "g_sub"}
    assert axis_guids == {"g_axis1", "g_sub"}
    # Substitute appears under BOTH teams.
    assert "g_sub" in allies_guids and "g_sub" in axis_guids


@pytest.mark.asyncio
async def test_compute_strips_color_codes_from_names():
    """player_name with ^1...^7 codes must be sanitized on the backend."""
    side_mapping_rows = [
        (100, "g1", 1),
        (100, "g2", 2),
    ]
    stats_rows = [
        (100, "g1", "^1Dmon^7",       1, 10, 5, 1000, 300, 1, 0, 0, 0, 0, 80, 300, 20, None),
        (100, "g2", "^3rik^6mojster", 2,  5, 8,  600, 300, 0, 0, 0, 0, 0, 50, 250, 10, None),
    ]
    hardcoded = {"A": {"guids": ["g1"]}, "B": {"guids": ["g2"]}}
    matches = _matches(["oasis"], [[100]])
    db = FakeDB([side_mapping_rows, stats_rows])
    svc = SessionMatrixService(db, StopwatchScoringService(db))
    out = await svc.compute(
        [100], matches, _scoring_payload(team_a="A", team_b="B"), hardcoded,
    )

    team_a = out["rosters"]["team_a"][0]
    team_b = out["rosters"]["team_b"][0]
    assert team_a["player_name"] == "Dmon"
    assert team_b["player_name"] == "rikmojster"


@pytest.mark.asyncio
async def test_compute_handles_string_side_encoding():
    """Legacy rows may store side as '1'/'2' strings; must normalize, not drop."""
    side_mapping_rows = [
        (100, "g1", "1"),  # string "1" → side 1
        (100, "g2", "2"),
    ]
    stats_rows = [
        (100, "g1", "Alpha", "1", 10, 5, 1000, 300, 0, 0, 0, 0, 0, 80, 300, 20, None),
        (100, "g2", "Beta",  "2",  4, 6,  500, 300, 0, 0, 0, 0, 0, 40, 200, 10, None),
    ]
    hardcoded = {"A": {"guids": ["g1"]}, "B": {"guids": ["g2"]}}
    matches = _matches(["supply"], [[100]])
    db = FakeDB([side_mapping_rows, stats_rows])
    svc = SessionMatrixService(db, StopwatchScoringService(db))
    out = await svc.compute(
        [100], matches, _scoring_payload(team_a="A", team_b="B"), hardcoded,
    )

    assert out["available"] is True
    assert len(out["rosters"]["team_a"]) == 1
    assert len(out["rosters"]["team_b"]) == 1


@pytest.mark.asyncio
async def test_compute_divides_safely_on_zero_stats():
    """time_played=0 / deaths=0 / shots=0 must not raise ZeroDivisionError."""
    side_mapping_rows = [(100, "g1", 1), (100, "g2", 2)]
    stats_rows = [
        # All-zero player — no time, no deaths, no shots
        (100, "g1", "Zero", 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, None),
        (100, "g2", "Other", 2, 3, 0, 200, 60, 0, 0, 0, 0, 0, 20, 0, 0, None),
    ]
    hardcoded = {"A": {"guids": ["g1"]}, "B": {"guids": ["g2"]}}
    matches = _matches(["radar"], [[100]])
    db = FakeDB([side_mapping_rows, stats_rows])
    svc = SessionMatrixService(db, StopwatchScoringService(db))

    out = await svc.compute(
        [100], matches, _scoring_payload(team_a="A", team_b="B"), hardcoded,
    )

    zero_player = out["rosters"]["team_a"][0]
    assert zero_player["totals"]["dpm"] == 0.0
    assert zero_player["totals"]["kd"] == 0.0  # 0 kills, 0 deaths → float(0)
    assert zero_player["totals"]["accuracy"] == 0.0
    assert zero_player["totals"]["hs_pct"] == 0.0

    other = out["rosters"]["team_b"][0]
    # 3 kills / 0 deaths → plain kills count (3.0), not inf
    assert other["totals"]["kd"] == 3.0
    # 0 shots → 0% accuracy (no inf)
    assert other["totals"]["accuracy"] == 0.0


@pytest.mark.asyncio
async def test_compute_returns_side_mapping_failed_on_empty_mapping():
    """If no rows pass side normalization, the matrix should flag the reason."""
    side_mapping_rows = [(100, "g1", "unknown"), (100, "g2", "mystery")]
    stats_rows: list = []
    hardcoded = {"A": {"guids": ["g1"]}, "B": {"guids": ["g2"]}}
    matches = _matches(["fueldump"], [[100]])
    db = FakeDB([side_mapping_rows, stats_rows])
    svc = SessionMatrixService(db, StopwatchScoringService(db))
    out = await svc.compute(
        [100], matches, _scoring_payload(team_a="A", team_b="B"), hardcoded,
    )
    assert out == {"available": False, "reason": "side_mapping_failed"}
