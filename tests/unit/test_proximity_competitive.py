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

    offsets = _implied_offsets(rows)

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
