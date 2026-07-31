"""Unit tests for /proximity/competitive/* (proximity_competitive.py).

Covers: stagger classification threshold, first-blood -> round conversion
math, validated wave-cycle segmentation and scoring, and personal-best card
detection vs history.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.routers.proximity_competitive import (
    get_first_blood_conversion,
    get_personal_bests,
    get_wave_cycles,
)

A1, A2 = "AXISGUID1" + "0" * 23, "AXISGUID2" + "0" * 23
B1, B2 = "ALLYGUID1" + "0" * 23, "ALLYGUID2" + "0" * 23


def _st(kill_time, killer, killer_team, victim, victim_team, interval, ttn):
    """Row shape used by get_wave_cycles."""
    return (killer, f"n_{killer[:4]}", killer_team, victim_team,
            victim, f"n_{victim[:4]}", kill_time, interval, ttn, 101, 0.5, True)


@pytest.mark.asyncio
async def test_wave_cycles_segmentation_and_scoring() -> None:
    db = AsyncMock()
    # One team's clock only (ALLIES interval 10000, offset 0 -> waves at 10s, 20s...).
    # ttn for an ALLIES victim killed at t: 10000 - (t % 10000).
    rows = [
        _st(2000, A1, "AXIS", B1, "ALLIES", 10000, 8000),   # cycle 0-10s
        _st(4000, A1, "AXIS", B2, "ALLIES", 10000, 6000),   # cycle 0-10s
        _st(12000, A2, "AXIS", B1, "ALLIES", 10000, 8000),  # cycle 10-20s
        _st(3000, B1, "ALLIES", A1, "AXIS", 10000, 7000),
        _st(13000, B1, "ALLIES", A1, "AXIS", 10000, 7000),
        _st(23000, B1, "ALLIES", A1, "AXIS", 10000, 7000),
        # These must be reported, but neither may affect validation or scoring.
        (*_st(5000, B1, "ALLIES", A1, "AXIS", 10000, 5000)[:9], None, 0.5, False),
        (*_st(6000, B1, "ALLIES", A1, "AXIS", 10000, 4000)[:9], 102, 0.5, False),
    ]
    track_rows = []
    row_id = 0
    for guid, team in ((A1, "AXIS"), (B1, "ALLIES")):
        for spawn in (0, 10000, 20000, 30000):
            row_id += 1
            track_rows.append(
                (
                    row_id,
                    guid,
                    f"n_{guid[:4]}",
                    team,
                    spawn,
                    spawn + 1000 if spawn < 30000 else None,
                    "killed" if spawn < 30000 else None,
                )
            )
    db.fetch_all = AsyncMock(side_effect=[rows, track_rows, []])

    res = await get_wave_cycles(
        session_date="2026-06-09", map_name="m", round_number=1,
        round_start_unix=None, db=db,
    )

    assert res["clocks"]["ALLIES"] == {"offset_ms": 0, "interval_ms": 10000}
    assert res["clocks"]["AXIS"] == {"offset_ms": 0, "interval_ms": 10000}
    assert res["clock_validation"]["ALLIES"]["status"] == "validated"
    assert res["excluded_unlinked_kills"] == 1
    assert res["excluded_ineligible_linked_kills"] == 1
    assert res["round_len_ms"] == 30000
    first = res["cycles"][0]
    assert (first["start_ms"], first["end_ms"]) == (0, 10000)
    assert first["kills_axis"] == 2 and first["kills_allies"] == 1
    assert first["winner"] == "AXIS"
    assert first["first_blood"] == "AXIS"
    assert res["summary"]["axis_won"] == len(
        [c for c in res["cycles"] if c["winner"] == "AXIS"]
    )
    assert max(cycle["end_ms"] for cycle in res["cycles"]) == res["round_len_ms"]


@pytest.mark.asyncio
async def test_wave_cycles_rejects_modal_clock_with_one_conflicting_row() -> None:
    db = AsyncMock()
    rows = [
        _st(1000, A1, "AXIS", B1, "ALLIES", 10000, 9000),
        _st(2000, A1, "AXIS", B1, "ALLIES", 10000, 8000),
        _st(3000, A1, "AXIS", B1, "ALLIES", 10000, 6000),
        _st(1000, B1, "ALLIES", A1, "AXIS", 10000, 9000),
        _st(2000, B1, "ALLIES", A1, "AXIS", 10000, 8000),
        _st(3000, B1, "ALLIES", A1, "AXIS", 10000, 7000),
    ]
    track_rows = [
        (1, A1, "A", "AXIS", 0, 1000, "killed"),
        (2, A1, "A", "AXIS", 10000, 11000, "killed"),
        (3, A1, "A", "AXIS", 20000, 21000, "killed"),
        (4, A1, "A", "AXIS", 30000, None, None),
        (5, B1, "B", "ALLIES", 0, 1000, "killed"),
        (6, B1, "B", "ALLIES", 10000, 11000, "killed"),
        (7, B1, "B", "ALLIES", 20000, 21000, "killed"),
        (8, B1, "B", "ALLIES", 30000, None, None),
    ]
    db.fetch_all = AsyncMock(side_effect=[rows, track_rows, []])

    result = await get_wave_cycles(
        session_date="2026-06-09",
        map_name="m",
        round_number=1,
        round_start_unix=None,
        db=db,
    )

    assert result["status"] == "unavailable"
    assert result["cycles"] == []
    assert result["clock_validation"]["ALLIES"]["status"] == "inconsistent"
    assert result["clock_validation"]["ALLIES"]["offset_ms"] is None


@pytest.mark.asyncio
async def test_wave_cycles_uses_selfkill_for_clock_but_not_combat_score() -> None:
    db = AsyncMock()
    rows = [
        _st(1000, A1, "AXIS", B1, "ALLIES", 10000, 9000),
        _st(2000, B1, "ALLIES", B1, "ALLIES", 10000, 8000),
        _st(3000, A1, "AXIS", B1, "ALLIES", 10000, 7000),
        _st(1000, B1, "ALLIES", A1, "AXIS", 10000, 9000),
        _st(2000, A1, "AXIS", A1, "AXIS", 10000, 8000),
        _st(3000, B1, "ALLIES", A1, "AXIS", 10000, 7000),
    ]
    track_rows = [
        (1, A1, "A", "AXIS", 0, 1000, "killed"),
        (2, A1, "A", "AXIS", 10000, 11000, "killed"),
        (3, A1, "A", "AXIS", 20000, 21000, "killed"),
        (4, A1, "A", "AXIS", 30000, None, None),
        (5, B1, "B", "ALLIES", 0, 1000, "killed"),
        (6, B1, "B", "ALLIES", 10000, 11000, "killed"),
        (7, B1, "B", "ALLIES", 20000, 21000, "killed"),
        (8, B1, "B", "ALLIES", 30000, None, None),
    ]
    db.fetch_all = AsyncMock(side_effect=[rows, track_rows, []])

    result = await get_wave_cycles(
        session_date="2026-06-09",
        map_name="m",
        round_number=1,
        round_start_unix=None,
        db=db,
    )

    assert result["status"] == "ok"
    assert result["clock_validation"]["AXIS"]["timing_observations"] == 3
    assert result["clock_validation"]["ALLIES"]["timing_observations"] == 3
    assert sum(cycle["kills_axis"] for cycle in result["cycles"]) == 2
    assert sum(cycle["kills_allies"] for cycle in result["cycles"]) == 2


@pytest.mark.asyncio
async def test_first_blood_conversion_math() -> None:
    db = AsyncMock()
    # 3 rounds: A draws first blood and wins 2, loses 1.
    fb_rows = [
        (1000, A1, "Aone", "AXIS", B1, "Bone", 5000),
        (2000, A1, "Aone", "AXIS", B2, "Btwo", 7000),
        (3000, B1, "Bone", "ALLIES", A2, "Atwo", 4000),
    ]
    win_rows = [
        (1000, 1),  # AXIS wins -> converted (fb AXIS)
        (2000, 2),  # ALLIES wins -> not converted
        (3000, 1),  # AXIS wins -> fb ALLIES not converted
    ]
    db.fetch_all = AsyncMock(side_effect=[fb_rows, win_rows])

    res = await get_first_blood_conversion(session_date="2026-06-09", db=db)

    assert res["rounds"] == 3
    assert res["decided_rounds"] == 3
    assert res["converted"] == 1
    assert res["conversion_pct"] == 33.3
    by_guid = {p["guid"]: p for p in res["players"]}
    assert by_guid[A1]["first_picks"] == 2
    assert by_guid[A1]["fp_converted"] == 1
    assert by_guid[B1]["first_picks"] == 1
    assert by_guid[B1]["first_deaths"] == 1


@pytest.mark.asyncio
async def test_personal_bests_only_on_improvement_with_history() -> None:
    db = AsyncMock()
    # Row: (killer_guid, name, session_date, kills, stagger, denied_ms, best_denial_ms)
    rows = [
        (A1, "Aone", date(2026, 6, 9), 50, 10, 900_000, 28_000),  # current
        (A1, "Aone", date(2026, 5, 1), 40, 12, 800_000, 29_000),  # history
        (B1, "Bone", date(2026, 6, 9), 30, 5, 500_000, 20_000),   # current, NO history
    ]
    db.fetch_all = AsyncMock(return_value=rows)

    res = await get_personal_bests(session_date="2026-06-09", db=db)

    metrics = {(c["guid"], c["metric"]) for c in res["cards"]}
    # kills 50>40 and denied 900s>800s are PBs; stagger 10<12 and
    # best_denial 28<29 are not; B1 has no history -> no cards at all.
    assert (A1, "kills") in metrics
    assert (A1, "denied_s") in metrics
    assert (A1, "stagger_kills") not in metrics
    assert (A1, "best_denial_s") not in metrics
    assert not any(g == B1 for g, _ in metrics)
    kills_card = next(c for c in res["cards"] if c["metric"] == "kills")
    assert kills_card["prev_best"] == 40
    assert kills_card["prev_best_date"] == "2026-05-01"


# ===== Wave 2: man-advantage / clutch =====

from website.backend.routers.proximity_competitive import (  # noqa: E402
    _advantage_windows,
    _detect_clutches,
    _fetch_round_lives_and_kills,
)


def _kill(t, killer_team, killer="K" + "0" * 31, victim_team="ALLIES"):
    return (t, killer_team, killer, f"n_{killer[:3]}", victim_team)


class TestAdvantageWindows:
    def test_window_opens_converts_and_closes(self):
        # 2v2; ALLIES death at 10s -> AXIS +1; AXIS kills again at 15s
        # (converted); ALLIES respawn at 20s evens it out.
        lives = [
            (A1, "AXIS", 0, None), (A2, "AXIS", 0, None),
            (B1, "ALLIES", 1000, 10000), (B2, "ALLIES", 1000, 15000),
            (B1, "ALLIES", 20000, None), (B2, "ALLIES", 20000, None),
        ]
        kills = [
            _kill(10000, "AXIS"),
            _kill(15000, "AXIS"),
        ]
        windows = _advantage_windows(lives, kills, 30000)
        assert len(windows) == 1
        w = windows[0]
        assert w["team"] == "AXIS"
        assert w["start"] == 10000 and w["end"] == 20000
        assert w["max_size"] == 2  # second death deepened the edge
        assert w["converted"] is True

    def test_opening_kill_is_not_a_conversion(self):
        lives = [
            (A1, "AXIS", 0, None),
            (B1, "ALLIES", 0, 10000), (B1, "ALLIES", 20000, None),
        ]
        # Only the kill that created the window — no further kill.
        windows = _advantage_windows(lives, [_kill(10000, "AXIS")], 30000)
        assert len(windows) == 1
        assert windows[0]["converted"] is False

    def test_pre_ready_staggered_spawns_ignored(self):
        # AXIS spawns at 0, ALLIES only at 5s: no phantom window before 5s.
        lives = [(A1, "AXIS", 0, None), (B1, "ALLIES", 5000, None)]
        assert _advantage_windows(lives, [], 30000) == []

    def test_boundary_kill_at_window_end_not_a_conversion(self):
        # Window is half-open [start, end): the respawn at 20s closes the
        # edge, so an advantaged-team kill at exactly 20s must not convert.
        lives = [
            (A1, "AXIS", 0, None),
            (B1, "ALLIES", 0, 10000), (B1, "ALLIES", 20000, None),
        ]
        kills = [_kill(10000, "AXIS"), _kill(20000, "AXIS")]
        windows = _advantage_windows(lives, kills, 30000)
        assert len(windows) == 1
        assert (windows[0]["start"], windows[0]["end"]) == (10000, 20000)
        assert windows[0]["converted"] is False


class TestDetectClutches:
    def test_won_by_surviving_with_kill(self):
        # A1 alone vs 2 from t=10s; friendly wave at 30s (interval 30000,
        # offset 0); gets a kill at 12s and survives -> won.
        lives = [
            (A1, "AXIS", 0, None), (A2, "AXIS", 0, 10000),
            (B1, "ALLIES", 0, None), (B2, "ALLIES", 0, None),
        ]
        kills = [(12000, "AXIS", A1, "n_A1", "ALLIES")]
        sits = _detect_clutches(lives, kills, {"AXIS": (0, 30000)}, 60000)
        assert len(sits) == 1
        s = sits[0]
        assert s["guid"] == A1 and s["enemies"] == 2
        assert s["kills"] == 1 and s["survived"] and s["won"]

    def test_lost_when_dying_without_trading_up(self):
        lives = [
            (A1, "AXIS", 0, 15000), (A2, "AXIS", 0, 10000),
            (B1, "ALLIES", 0, None), (B2, "ALLIES", 0, None),
        ]
        sits = _detect_clutches(lives, [], {"AXIS": (0, 30000)}, 60000)
        assert len(sits) == 1
        assert sits[0]["won"] is False and sits[0]["survived"] is False

    def test_skipped_when_wave_too_close(self):
        # Wave lands at 12s, situation starts at 10s -> <5s wait, not a clutch.
        lives = [
            (A1, "AXIS", 0, None), (A2, "AXIS", 0, 10000),
            (B1, "ALLIES", 0, None), (B2, "ALLIES", 0, None),
        ]
        sits = _detect_clutches(lives, [], {"AXIS": (0, 12000)}, 60000)
        assert sits == []


@pytest.mark.asyncio
async def test_timeline_fetch_preserves_unlinked_rows_without_reading_paths() -> None:
    db = AsyncMock()
    track_rows = [
        (None, date(2026, 7, 1), "supply", 1, 0, A1, "AXIS", 0, 10_000),
    ]
    kill_rows = [
        (
            None,
            date(2026, 7, 1),
            "supply",
            1,
            0,
            5_000,
            "AXIS",
            A1,
            "A",
            "ALLIES",
            20_000,
            15_000,
            B1,
            "B",
            0.5,
        ),
    ]
    db.fetch_all = AsyncMock(side_effect=[track_rows, kill_rows])

    rounds = await _fetch_round_lives_and_kills(db, "WHERE TRUE", [])

    assert len(rounds) == 1
    data = next(iter(rounds.values()))
    assert data["lives"] == [(A1, "AXIS", 0, 10_000)]
    assert len(data["kills"]) == 1
    assert db.fetch_all.await_count == 2
    assert "path ->" not in db.fetch_all.await_args_list[0].args[0]


@pytest.mark.asyncio
async def test_timeline_fetch_builds_clocks_from_separate_exact_track_query() -> None:
    db = AsyncMock()
    base_tracks = []
    clock_tracks = []
    row_id = 0
    for guid, name, team in ((A1, "A", "AXIS"), (B1, "B", "ALLIES")):
        for spawn in (0, 10_000, 20_000, 30_000):
            row_id += 1
            death = spawn + 1_000 if spawn < 30_000 else None
            event = "killed" if spawn < 30_000 else None
            base_tracks.append(
                (101, date(2026, 7, 1), "supply", 1, 123, guid, team, spawn, death)
            )
            clock_tracks.append(
                (101, row_id, guid, name, team, spawn, death, event)
            )
    base_kills = []
    for kill_time, killer_team, killer, victim_team, victim in (
        (1_000, "ALLIES", B1, "AXIS", A1),
        (2_000, "AXIS", A1, "ALLIES", B1),
        (11_000, "ALLIES", B1, "AXIS", A1),
        (12_000, "AXIS", A1, "ALLIES", B1),
        (21_000, "ALLIES", B1, "AXIS", A1),
        (22_000, "AXIS", A1, "ALLIES", B1),
    ):
        interval = 10_000
        base_kills.append(
            (
                101,
                date(2026, 7, 1),
                "supply",
                1,
                123,
                kill_time,
                killer_team,
                killer,
                "killer",
                victim_team,
                interval,
                interval - (kill_time % interval),
                victim,
                "victim",
                0.5,
            )
        )
    db.fetch_all = AsyncMock(side_effect=[base_tracks, base_kills, clock_tracks, []])

    rounds = await _fetch_round_lives_and_kills(
        db,
        "WHERE TRUE",
        [],
        include_clocks=True,
    )

    data = rounds[("round_id", 101)]
    assert data["clocks"] == {"ALLIES": (0, 10_000), "AXIS": (0, 10_000)}
    assert db.fetch_all.await_count == 4
    assert "path ->" not in db.fetch_all.await_args_list[0].args[0]
    assert "path ->" in db.fetch_all.await_args_list[2].args[0]
