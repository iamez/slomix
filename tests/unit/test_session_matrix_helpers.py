"""Tests for SessionMatrixService pure helpers — row aggregation math.

These helpers underpin the Session Detail 2.0 player × map matrix
displayed by `/api/sessions/{gsid}` and the legacy JS render. A
regression silently:

- `_empty_cell` schema drift → downstream `_finalize_cell` divides
  by missing field → KeyError → 500.
- `_finalize_cell` division-by-zero on time_played=0 → endpoint 500
  on a player who DC'd with 0 seconds played (real edge case).
- `_finalize_cell` drops scratch fields (return_fire_count/sum) but
  does NOT carry through the rounded average → tooltip blank.
- `_sum_cells` averages return_fire incorrectly: a cell with
  return_fire_ms=None must be skipped (NOT counted as 0).
- `_aggregate_roster` totals not coerced to float for Decimal
  damage values → JSON encoder crashes.
- `_split_by_team` sort by dpm not stable → leaderboard rows shuffle
  on identical-DPM ties.
- `_split_by_team` includes the player GUID in the entry (not just
  team_name + guid in dict key) — pin so frontend can deep-link.
- `_build_maps_list` skips score lookup when scoring_payload
  available=False → frontend renders score "?" instead of crashing.

Pin the public helpers + their public schemas.
"""
from __future__ import annotations

from website.backend.services.session_matrix_service import (
    SessionMatrixService,
    _aggregate_roster,
    _empty_cell,
    _finalize_cell,
    _sum_cells,
)

# ---------------------------------------------------------------------------
# _empty_cell — schema contract
# ---------------------------------------------------------------------------


def test_empty_cell_has_all_required_summable_keys():
    """Pin the schema so a refactor that drops e.g. `weapon_hs` doesn't
    silently make hs_pct always 0 (the field becomes absent → .get()
    default 0 → division goes from 0/x to 0/x but breakdown shows 0)."""
    cell = _empty_cell(0)
    expected = {
        "map_index", "kills", "deaths", "damage", "time_played",
        "revives", "times_revived", "assists", "gibs",
        "hs_kills", "hits", "shots", "weapon_hs",
        "return_fire_sum", "return_fire_count",
        "played",
    }
    assert set(cell.keys()) == expected


def test_empty_cell_played_starts_false():
    """`played` flag starts False — flips True only when a row arrives.
    Pin so the matrix can show "—" for unplayed maps instead of "0"."""
    cell = _empty_cell(0)
    assert cell["played"] is False


def test_empty_cell_carries_map_index():
    """map_index is the column position. Pin so a refactor that drops
    it doesn't break the frontend's column placement."""
    cell = _empty_cell(3)
    assert cell["map_index"] == 3


def test_empty_cell_numeric_fields_zero():
    """All summable counters start at 0 (NOT None — would crash `+=`)."""
    cell = _empty_cell(0)
    for k in ["kills", "deaths", "damage", "time_played", "hits", "shots"]:
        assert cell[k] == 0
    assert cell["return_fire_sum"] == 0.0
    assert cell["return_fire_count"] == 0


# ---------------------------------------------------------------------------
# _finalize_cell — derived ratios + scratch field cleanup
# ---------------------------------------------------------------------------


def test_finalize_cell_computes_dpm():
    """DPM = damage * 60 / time_played_seconds. Pin so a swap to
    minutes (no *60) or division flip doesn't silently halve every
    DPM in the matrix."""
    cell = _empty_cell(0)
    cell["damage"] = 6000
    cell["time_played"] = 600  # 10 min
    _finalize_cell(cell)
    assert cell["dpm"] == 600.0  # 6000 * 60 / 600


def test_finalize_cell_dpm_zero_when_no_time():
    """time_played=0 → dpm=0.0 (NOT division-by-zero crash). Pin so
    a player who DC'd doesn't 500 the endpoint."""
    cell = _empty_cell(0)
    cell["damage"] = 100
    cell["time_played"] = 0
    _finalize_cell(cell)
    assert cell["dpm"] == 0.0


def test_finalize_cell_kd_uses_kills_when_deaths_zero():
    """deaths=0 → kd is float(kills) (raw kills, NOT inf or 0).
    Pin so a perfect K/D 5-0 round shows "5.0" not "inf" in the tooltip."""
    cell = _empty_cell(0)
    cell["kills"] = 5
    cell["deaths"] = 0
    _finalize_cell(cell)
    assert cell["kd"] == 5.0


def test_finalize_cell_kd_normal():
    cell = _empty_cell(0)
    cell["kills"] = 7
    cell["deaths"] = 3
    _finalize_cell(cell)
    assert cell["kd"] == 2.33  # round(7/3, 2)


def test_finalize_cell_accuracy_zero_when_no_shots():
    """No shots fired → accuracy=0.0 (no division-by-zero)."""
    cell = _empty_cell(0)
    cell["hits"] = 0
    cell["shots"] = 0
    _finalize_cell(cell)
    assert cell["accuracy"] == 0.0


def test_finalize_cell_accuracy_normal():
    """Accuracy = hits/shots * 100, rounded to 1 decimal."""
    cell = _empty_cell(0)
    cell["hits"] = 35
    cell["shots"] = 100
    _finalize_cell(cell)
    assert cell["accuracy"] == 35.0


def test_finalize_cell_hs_pct_zero_when_no_hits():
    """No hits → hs_pct=0.0 (no division-by-zero)."""
    cell = _empty_cell(0)
    cell["weapon_hs"] = 0
    cell["hits"] = 0
    _finalize_cell(cell)
    assert cell["hs_pct"] == 0.0


def test_finalize_cell_drops_scratch_fields():
    """`return_fire_sum` and `return_fire_count` are scratch — must be
    POPped from the cell. Pin so the JSON response stays compact and
    the frontend never sees these internal accumulators."""
    cell = _empty_cell(0)
    cell["return_fire_sum"] = 1500.0
    cell["return_fire_count"] = 3
    _finalize_cell(cell)
    assert "return_fire_sum" not in cell
    assert "return_fire_count" not in cell


def test_finalize_cell_return_fire_ms_averages():
    """Average return-fire ms over count. Pin so the rendered tooltip
    shows mean reaction time (NOT total)."""
    cell = _empty_cell(0)
    cell["return_fire_sum"] = 1500.0
    cell["return_fire_count"] = 3
    _finalize_cell(cell)
    assert cell["return_fire_ms"] == 500.0


def test_finalize_cell_return_fire_none_when_no_count():
    """No samples → return_fire_ms=None (NOT 0). Pin so frontend
    distinguishes "no data" from "instant reflexes"."""
    cell = _empty_cell(0)
    _finalize_cell(cell)
    assert cell["return_fire_ms"] is None


# ---------------------------------------------------------------------------
# _sum_cells — totals across maps for one player
# ---------------------------------------------------------------------------


def test_sum_cells_empty_list():
    """No cells → all-zero totals dict (NOT crash)."""
    out = _sum_cells([])
    assert out["kills"] == 0
    assert out["dpm"] == 0.0
    assert out["return_fire_ms"] is None


def test_sum_cells_aggregates_kills_and_damage():
    cells = [
        {"kills": 5, "deaths": 1, "damage": 1000, "time_played": 60,
         "revives": 0, "times_revived": 0, "assists": 0, "gibs": 0,
         "hs_kills": 0, "hits": 10, "shots": 20, "weapon_hs": 0,
         "return_fire_ms": None},
        {"kills": 3, "deaths": 2, "damage": 500, "time_played": 30,
         "revives": 0, "times_revived": 0, "assists": 0, "gibs": 0,
         "hs_kills": 0, "hits": 5, "shots": 10, "weapon_hs": 0,
         "return_fire_ms": None},
    ]
    out = _sum_cells(cells)
    assert out["kills"] == 8
    assert out["deaths"] == 3
    assert out["damage"] == 1500
    assert out["time_played"] == 90


def test_sum_cells_skips_none_return_fire():
    """Cells with return_fire_ms=None are NOT counted in the average.
    Pin so a single None doesn't drag the average toward 0."""
    cells = [
        {"kills": 0, "deaths": 0, "damage": 0, "time_played": 0,
         "revives": 0, "times_revived": 0, "assists": 0, "gibs": 0,
         "hs_kills": 0, "hits": 0, "shots": 0, "weapon_hs": 0,
         "return_fire_ms": 500.0},
        {"kills": 0, "deaths": 0, "damage": 0, "time_played": 0,
         "revives": 0, "times_revived": 0, "assists": 0, "gibs": 0,
         "hs_kills": 0, "hits": 0, "shots": 0, "weapon_hs": 0,
         "return_fire_ms": None},  # skipped
        {"kills": 0, "deaths": 0, "damage": 0, "time_played": 0,
         "revives": 0, "times_revived": 0, "assists": 0, "gibs": 0,
         "hs_kills": 0, "hits": 0, "shots": 0, "weapon_hs": 0,
         "return_fire_ms": 700.0},
    ]
    out = _sum_cells(cells)
    # Average of 500 and 700, NOT 1200/3
    assert out["return_fire_ms"] == 600.0


def test_sum_cells_kd_zero_deaths_uses_kill_count():
    """No deaths anywhere → kd = float(kills)."""
    cells = [{
        "kills": 4, "deaths": 0, "damage": 0, "time_played": 0,
        "revives": 0, "times_revived": 0, "assists": 0, "gibs": 0,
        "hs_kills": 0, "hits": 0, "shots": 0, "weapon_hs": 0,
        "return_fire_ms": None,
    }]
    out = _sum_cells(cells)
    assert out["kd"] == 4.0


# ---------------------------------------------------------------------------
# _aggregate_roster — team-wide totals
# ---------------------------------------------------------------------------


def test_aggregate_roster_empty_returns_zero_dict():
    """Empty roster → zero counters, dpm_avg=0.0, return_fire_avg=None."""
    out = _aggregate_roster([])
    assert out["kills"] == 0
    assert out["dpm_avg"] == 0.0
    assert out["return_fire_avg"] is None


def test_aggregate_roster_uses_avg_suffixes():
    """Output keys use _avg suffix (dpm_avg, kd_avg, accuracy_avg,
    hs_pct_avg, return_fire_avg) — distinguishes team-level from
    cell-level. Pin so frontend can render different headers."""
    roster = [{
        "totals": {
            "kills": 10, "deaths": 5, "damage": 2000, "time_played": 120,
            "revives": 0, "assists": 0, "gibs": 0, "hs_kills": 2,
            "hits": 50, "shots": 100, "weapon_hs": 5,
            "return_fire_ms": 600.0,
        },
    }]
    out = _aggregate_roster(roster)
    assert "dpm_avg" in out
    assert "kd_avg" in out
    assert "accuracy_avg" in out
    assert "hs_pct_avg" in out
    assert "return_fire_avg" in out


def test_aggregate_roster_skips_none_return_fire_in_avg():
    """Players with return_fire_ms=None excluded from the average."""
    roster = [
        {"totals": {"kills": 1, "deaths": 1, "damage": 100, "time_played": 60,
                    "revives": 0, "assists": 0, "gibs": 0, "hs_kills": 0,
                    "hits": 10, "shots": 20, "weapon_hs": 0,
                    "return_fire_ms": 400.0}},
        {"totals": {"kills": 1, "deaths": 1, "damage": 100, "time_played": 60,
                    "revives": 0, "assists": 0, "gibs": 0, "hs_kills": 0,
                    "hits": 10, "shots": 20, "weapon_hs": 0,
                    "return_fire_ms": None}},
        {"totals": {"kills": 1, "deaths": 1, "damage": 100, "time_played": 60,
                    "revives": 0, "assists": 0, "gibs": 0, "hs_kills": 0,
                    "hits": 10, "shots": 20, "weapon_hs": 0,
                    "return_fire_ms": 800.0}},
    ]
    out = _aggregate_roster(roster)
    assert out["return_fire_avg"] == 600.0


# ---------------------------------------------------------------------------
# SessionMatrixService._split_by_team — team partitioning + DPM sort
# ---------------------------------------------------------------------------


def _player_data(team_name, guid, name, dpm):
    return (team_name, guid), {
        "player_guid": guid,
        "player_name": name,
        "totals": {"dpm": dpm},
        "cells_by_map": [],
    }


def test_split_by_team_partitions_correctly():
    rosters = dict([
        _player_data("TeamA", "g1", "alice", 500.0),
        _player_data("TeamB", "g2", "bob",   300.0),
    ])
    a, b = SessionMatrixService._split_by_team(rosters, "TeamA", "TeamB")
    assert len(a) == 1
    assert a[0]["player_guid"] == "g1"
    assert b[0]["player_guid"] == "g2"


def test_split_by_team_drops_unrecognised_team():
    """A team not in (team_a_name, team_b_name) is silently dropped.
    Pin so a stale roster row from a previous session doesn't pollute
    the current matrix."""
    rosters = dict([
        _player_data("TeamA",   "g1", "alice", 500.0),
        _player_data("Unknown", "g2", "bob",   300.0),
    ])
    a, b = SessionMatrixService._split_by_team(rosters, "TeamA", "TeamB")
    assert len(a) == 1
    assert len(b) == 0


def test_split_by_team_sorts_by_dpm_descending():
    """Both rosters sorted by totals.dpm, highest first. Pin so leaderboard
    always shows top fragger first."""
    rosters = dict([
        _player_data("TeamA", "g1", "low",  100.0),
        _player_data("TeamA", "g2", "high", 700.0),
        _player_data("TeamA", "g3", "mid",  400.0),
    ])
    a, _ = SessionMatrixService._split_by_team(rosters, "TeamA", "TeamB")
    assert [p["player_name"] for p in a] == ["high", "mid", "low"]


def test_split_by_team_entry_carries_required_fields():
    """Each entry has player_guid, player_name, totals, cells. Pin
    schema so the frontend deep-link to player profile works."""
    rosters = dict([_player_data("TeamA", "g1", "alice", 500.0)])
    a, _ = SessionMatrixService._split_by_team(rosters, "TeamA", "TeamB")
    entry = a[0]
    assert set(entry.keys()) == {"player_guid", "player_name", "totals", "cells"}


# ---------------------------------------------------------------------------
# SessionMatrixService._build_maps_list — score wiring
# ---------------------------------------------------------------------------


def test_build_maps_list_uses_scoring_when_available():
    """scoring available=True → scores wired from `maps` array."""
    matches = [{"map_name": "oasis"}, {"map_name": "fueldump"}]
    payload = {
        "available": True,
        "maps": [
            {"team_a_points": 3, "team_b_points": 1},
            {"team_a_points": 2, "team_b_points": 4},
        ],
    }
    out = SessionMatrixService._build_maps_list(matches, payload)
    assert out[0]["map_name"] == "oasis"
    assert out[0]["team_a_score"] == 3
    assert out[0]["team_b_score"] == 1
    assert out[1]["team_a_score"] == 2


def test_build_maps_list_when_scoring_unavailable_returns_none_scores():
    """available=False → score lookup skipped → team_a_score/team_b_score
    are None (NOT crash). Pin so frontend can render "—" gracefully."""
    matches = [{"map_name": "oasis"}]
    payload = {"available": False, "maps": []}
    out = SessionMatrixService._build_maps_list(matches, payload)
    assert out[0]["map_name"] == "oasis"
    assert out[0]["team_a_score"] is None
    assert out[0]["team_b_score"] is None


def test_build_maps_list_handles_missing_scoring_index():
    """matches has more entries than scoring.maps → trailing maps get
    None scores (NOT IndexError). Pin so an incomplete scoring payload
    doesn't 500 the whole endpoint."""
    matches = [
        {"map_name": "m1"},
        {"map_name": "m2"},
        {"map_name": "m3"},
    ]
    payload = {
        "available": True,
        "maps": [{"team_a_points": 1, "team_b_points": 0}],
    }
    out = SessionMatrixService._build_maps_list(matches, payload)
    assert out[0]["team_a_score"] == 1
    assert out[1]["team_a_score"] is None
    assert out[2]["team_a_score"] is None


def test_build_maps_list_assigns_sequential_map_indices():
    """map_index is the position in the matches list — used by
    _empty_cell to lock cells into the right column."""
    matches = [{"map_name": "a"}, {"map_name": "b"}, {"map_name": "c"}]
    payload = {"available": False, "maps": []}
    out = SessionMatrixService._build_maps_list(matches, payload)
    assert [m["map_index"] for m in out] == [0, 1, 2]
