"""Camp profile (docs/design/22 slice 2): the episode math and the service
method, on synthetic tracks where every answer is known.

The thresholds were chosen from a corpus measurement (2026-09-05, players
with >= 25 sessions on three maps): "hold" = within 96 u of one spot for
>= 4 s (10–24 % of alive time, Spearman between session halves +0.6..+0.8),
"still" = speed < 10 for >= 3 s (0.8–6.4 %, +0.76..+0.93). These tests pin
the DEFINITIONS; the numbers they produce on the corpus live in the design
doc, not here.
"""
# ruff: noqa: SLF001 — the episode math and the worker are module-private on
# purpose (only the service calls them); the tests pin their definitions.
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.services.session_scope import GamingSessionScope
from website.backend.services.storytelling import advanced_metrics as am
from website.backend.services.storytelling_service import StorytellingService

GUID32 = "EDBB5DA97C9F52151865C5F223F9B951"
OTHER32 = "FDA127DF5246F28D7355490F749DD894"
SCOPE = GamingSessionScope(
    gaming_session_id=99,
    dates=("2026-05-01",),
    round_keys=((1781000000, "supply", 1),),
    accepted_round_count=1,
    distinct_map_names=("supply",),
)


def pts(spec: list[tuple[float, float, float, float]]) -> list[tuple[int, float, float, float]]:
    """(seconds, x, y, speed) → sampled every 200 ms up to the next entry's
    time (the last waypoint yields one sample at its own time — the player
    is still there), so a 'life' is written as a few waypoints instead of
    hundreds of samples."""
    out: list[tuple[int, float, float, float]] = []
    for k, (t, x, y, sp) in enumerate(spec):
        t_end = spec[k + 1][0] if k + 1 < len(spec) else t + 0.2
        ms = int(round(t * 1000))
        while ms < int(round(t_end * 1000)):
            out.append((ms, x, y, sp))
            ms += 200
    return out


def moving(t0: float, t1: float, speed: float = 250.0) -> list[tuple[int, float, float, float]]:
    """Runs from (0,0) at `speed` u/s — every sample leaves every radius."""
    out = []
    ms = int(t0 * 1000)
    while ms < int(t1 * 1000):
        d = speed * (ms - int(t0 * 1000)) / 1000
        out.append((ms, 10_000 + d, 10_000 + d, speed))
        ms += 200
    return out


# ── episode math ───────────────────────────────────────────────────────────

def test_hold_needs_four_seconds_within_the_radius():
    # Parked from 0 to 4.2 s (span 4200 ms) → one hold; 0 to 3.8 s → none
    # (the window is closed by the sample that leaves the radius).
    held = pts([(0, 0, 0, 0)]) + moving(0.2, 0.4)
    assert am._camp_episodes(held)[0] == 0
    long = pts([(0, 100, 100, 0), (4.2, 100, 100, 0)]) + moving(4.2, 6)
    hold_ms, _, _ = am._camp_episodes(long)
    assert hold_ms == 4200  # span between first and last sample inside
    short = pts([(0, 100, 100, 0), (3.8, 100, 100, 0)]) + moving(3.8, 6)
    assert am._camp_episodes(short)[0] == 0


def test_strafing_inside_the_radius_still_holds_but_wider_does_not():
    # The window is anchored at its FIRST sample, so the radius bounds the
    # whole swing: strafing ±40 u (80 u swing) for 6 s holds, ±60 u (120 u
    # swing, > 96) does not — even though every sample is "near" the middle.
    peek = [(ms, 500 + (40 if (ms // 400) % 2 else -40), 500, 150.0) for ms in range(0, 6000, 200)]
    assert am._camp_episodes(peek)[0] == 5800
    wide = [(ms, 500 + (60 if (ms // 400) % 2 else -60), 500, 150.0) for ms in range(0, 6000, 200)]
    assert am._camp_episodes(wide)[0] == 0


def test_still_needs_three_seconds_of_speed_under_ten_and_counts_time_not_samples():
    slow = pts([(0, 0, 0, 5.0), (3.2, 0, 0, 5.0)]) + moving(3.2, 5)
    _, still_ms, _ = am._camp_episodes(slow)
    assert still_ms == 3200
    brief = pts([(0, 0, 0, 5.0), (2.8, 0, 0, 5.0)]) + moving(2.8, 5)
    assert am._camp_episodes(brief)[1] == 0
    # Standing still at 9.9 counts, 10.0 does not (strict <).
    edge = pts([(0, 0, 0, 9.9), (4, 0, 0, 9.9)]) + moving(4, 5)
    assert am._camp_episodes(edge)[1] > 0
    edge10 = pts([(0, 0, 0, 10.0), (4, 0, 0, 10.0)]) + moving(4, 5)
    assert am._camp_episodes(edge10)[1] == 0


def test_spawn_wait_is_kept_in_the_share_but_left_out_of_the_spots():
    # Parked at spawn 0–5 s (starts inside the first 3 s of the life), then
    # a camp at (2000, 2000) 8–13 s → cell (3, 3). Both count as hold time;
    # only the camp is a spot.
    life = pts([(0, 100, 100, 0), (5, 100, 100, 0)]) + moving(5, 8) + pts([(8, 2000, 2000, 0), (13, 2000, 2000, 0)])
    hold_ms, _, cells = am._camp_episodes(life)
    assert hold_ms == 5000 + 5000
    assert cells == {(3, 3): 5000}


def test_empty_track_is_all_zeros():
    assert am._camp_episodes([]) == (0, 0, {})


# ── the worker ─────────────────────────────────────────────────────────────

def path_json(points: list[tuple[int, float, float, float]]) -> str:
    return json.dumps([{"time": t, "x": x, "y": y, "speed": s} for t, x, y, s in points])


def test_worker_aggregates_per_player_and_skips_unreadable_paths():
    camp = pts([(0, 100, 100, 0), (10, 100, 100, 0)])  # 10 s hold, 10 s still
    rows = [
        (GUID32, "^6S^2uper^6B^2oyy", "AXIS", 1781000000, 0, 10000, 10000, path_json(camp)),
        (GUID32, "^6S^2uper^6B^2oyy", "AXIS", 1781000000, 0, 10000, 10000, path_json(moving(0, 10))),
        (OTHER32, "^3w^7ise", "AXIS", 1781000000, 0, 5000, 5000, "[]"),
        (OTHER32, "^3w^7ise", "AXIS", 1781000000, 0, 5000, 5000, "{corrupt"),
        (OTHER32, "^3w^7ise", "AXIS", 1781000000, 0, 5000, 5000, '[{"time": 0, "speed": 0}]'),  # no x/y
    ]
    stats, names = am._compute_camp_profile(rows)
    assert names == {GUID32[:8]: "SuperBoyy"}
    s = stats[GUID32[:8]]
    assert s["tracks"] == 2 and s["hold_ms"] == 10000 and s["still_ms"] == 10000
    assert s["alive_ms"] == 10000 + 9800  # moving(0, 10) ends at 9.8 s
    assert OTHER32[:8] not in stats


# ── the service method ─────────────────────────────────────────────────────

def _camper_rows(alive_s: float, guid: str = GUID32, name: str = "camper"):
    """One life: parked at (5000, 5000) for `alive_s`."""
    return [(guid, name, "AXIS", 1781000000, 0, int(alive_s * 1000), int(alive_s * 1000),
             path_json(pts([(0, 5000, 5000, 0), (alive_s, 5000, 5000, 0)])))]


@pytest.mark.asyncio
async def test_camp_profile_shares_coverage_and_null_for_thin_players():
    svc = StorytellingService(db=AsyncMock())
    # Life 2 of the camper: a 4 s run from spawn, then 30 s parked at
    # (5000, 5000) — THAT is a spot; the 90 s park from spawn in life 1 is
    # hold time but not a spot (it starts inside the first 3 s of the life).
    life2 = moving(0, 4) + pts([(4, 5000, 5000, 0), (34, 5000, 5000, 0)])
    rows = (
        _camper_rows(90)
        + [(GUID32, "camper", "AXIS", 1781000000, 0, 34000, 34000, path_json(life2))]
        + [(OTHER32, "runner", "ALLIES", 1781000000, 0, 90000, 90000, path_json(moving(0, 90)))]
        + _camper_rows(20, guid="AB12CD34EF56AB12CD34EF56AB12CD34", name="brief")
        + [(OTHER32, "runner", "ALLIES", 1781000000, 0, 5000, 5000, "{corrupt")]
    )
    svc.db.fetch_all = AsyncMock(return_value=rows)

    result = await svc.compute_camp_profile(SCOPE)

    assert result["status"] == "ok" and result["metric"] == "camp_profile"
    assert result["coverage"] == {"tracks_fetched": 5, "tracks_used": 4, "tracks_skipped": 1}
    by = {p["guid_short"]: p for p in result["players"]}
    # (90 000 + 30 000) / (90 000 + 34 000) alive ms
    assert by[GUID32[:8]]["hold_pct"] == 96.8 and by[GUID32[:8]]["still_pct"] == 96.8
    assert by[GUID32[:8]]["coverage"] == "ok" and by[GUID32[:8]]["top_cells"] == [[9, 9, 30.0]]
    assert by[GUID32[:8]]["hold_time_s"] == 120.0 and by[GUID32[:8]]["tracks"] == 2
    assert by[OTHER32[:8]]["hold_pct"] == 0.0 and by[OTHER32[:8]]["top_cells"] == []
    # 20 s alive is below min_alive_s: the share is unknown, not zero.
    assert by["AB12CD34"]["hold_pct"] is None and by["AB12CD34"]["still_pct"] is None
    assert by["AB12CD34"]["coverage"] == "thin" and by["AB12CD34"]["hold_time_s"] == 20.0
    # Order: highest hold share first, unknown last (not sorted in as zeros).
    assert [p["guid_short"] for p in result["players"]] == [GUID32[:8], OTHER32[:8], "AB12CD34"]
    assert result["thresholds"]["min_alive_s"] == 60.0 and result["thresholds"]["hold_radius_u"] == 96.0
    # The SQL keeps the lurker guards: rows without a real round start would
    # merge unrelated rounds' tracks.
    sql = svc.db.fetch_all.call_args.args[0]
    assert "round_start_unix > 0" in sql and "path IS NOT NULL" in sql


@pytest.mark.asyncio
async def test_camp_profile_without_tracks_is_an_empty_ok_not_a_500():
    svc = StorytellingService(db=AsyncMock())
    svc.db.fetch_all = AsyncMock(return_value=[])
    result = await svc.compute_camp_profile(SCOPE)
    assert result["players"] == [] and result["coverage"]["tracks_fetched"] == 0
    assert result["status"] == "ok" and "thresholds" in result
