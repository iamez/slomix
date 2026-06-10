"""Unit tests for /proximity/competitive/* (proximity_competitive.py).

Covers: stagger classification threshold, first-blood -> round conversion
math, implied wave-clock derivation (offset voting), wave-cycle segmentation
and scoring, and personal-best card detection vs history.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.routers.proximity_competitive import (
    _implied_offsets,
    get_first_blood_conversion,
    get_personal_bests,
    get_wave_cycles,
)

A1, A2 = "AXISGUID1" + "0" * 23, "AXISGUID2" + "0" * 23
B1, B2 = "ALLYGUID1" + "0" * 23, "ALLYGUID2" + "0" * 23


def _st(kill_time, killer, killer_team, victim, victim_team, interval, ttn):
    """Row shape used by get_wave_cycles / _implied_offsets."""
    return (killer, f"n_{killer[:4]}", killer_team, victim_team,
            victim, f"n_{victim[:4]}", kill_time, interval, ttn)


def test_implied_offsets_votes_modal_value() -> None:
    # ALLIES interval 25000, offset 14000: ttn = interval - ((offset+t) % interval)
    rows = []
    for t in (12975, 31550, 60125):
        ttn = 25000 - ((14000 + t) % 25000)
        rows.append(_st(t, A1, "AXIS", B1, "ALLIES", 25000, ttn))
    # AXIS interval 30000, offset 6000
    for t in (20000, 47000):
        ttn = 30000 - ((6000 + t) % 30000)
        rows.append(_st(t, B1, "ALLIES", A1, "AXIS", 30000, ttn))

    offsets = _implied_offsets([(r[3], r[6], r[7], r[8]) for r in rows])

    assert offsets["ALLIES"] == (14000, 25000)
    assert offsets["AXIS"] == (6000, 30000)


@pytest.mark.asyncio
async def test_wave_cycles_segmentation_and_scoring() -> None:
    db = AsyncMock()
    # One team's clock only (ALLIES interval 10000, offset 0 -> waves at 10s, 20s...).
    # ttn for an ALLIES victim killed at t: 10000 - (t % 10000).
    rows = [
        _st(2000, A1, "AXIS", B1, "ALLIES", 10000, 8000),   # cycle 0-10s
        _st(4000, A1, "AXIS", B2, "ALLIES", 10000, 6000),   # cycle 0-10s
        _st(12000, A2, "AXIS", B1, "ALLIES", 10000, 8000),  # cycle 10-20s
    ]
    db.fetch_all = AsyncMock(return_value=rows)

    res = await get_wave_cycles(
        session_date="2026-06-09", map_name="m", round_number=1,
        round_start_unix=None, db=db,
    )

    assert res["clocks"]["ALLIES"] == {"offset_ms": 0, "interval_ms": 10000}
    first = res["cycles"][0]
    assert (first["start_ms"], first["end_ms"]) == (0, 10000)
    assert first["kills_axis"] == 2 and first["kills_allies"] == 0
    assert first["winner"] == "AXIS"
    assert first["first_blood"] == "AXIS"
    assert res["summary"]["axis_won"] == len(
        [c for c in res["cycles"] if c["winner"] == "AXIS"]
    )


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
