"""Detector L — escort of a movable objective (docs/design/20 §4b): the first
moments detector to read proximity_vehicle_progress ⋈ proximity_escort_credit,
and the first with a test that runs its SQL against a stub and pins what the
SQL must carry (the round-key alias, the credit > 0 guard)."""
from __future__ import annotations

import asyncio
import json

import pytest

from website.backend.services.session_scope import GamingSessionScope
from website.backend.services.storytelling import moments as moments_module
from website.backend.services.storytelling.base import (
    ESCORT_MOVER_MIN_DISTANCE,
    ESCORT_MOVER_MIN_SHARE,
)
from website.backend.services.storytelling.moments import _TYPE_PRIORITY, _MomentsMixin

#: SELECT column order of the detector's query (17 columns):
#: session_date, round_number, round_start_unix, round_end_unix, map_name,
#: vehicle_name, vehicle_type, total_distance, destroyed_count, player_guid,
#: player_name, player_team, credit_distance, total_escort_distance,
#: mounted_time_ms, proximity_time_ms, samples
START = 1787858291
END = START + 612


def row(*, rn=1, start=START, end=END, map_name="supply", vehicle="truck", vtype="script_mover",
        total=12744.3, destroyed=0, guid="9F2B3930797D7D142795B1B6EE194722", name="^6[^2T^6W^2K^6]^2I^6mb3ci^2L",
        team="allies", credit=2799.5, total_escort=5095.1, mounted=0, prox=36000, samples=72,
        first_move=None, last_move=None, destroyed_events=None, first_escort=None, last_escort=None):
    # Columns 17-21 (v6.14 / migration 082) are appended so the first 17
    # keep their indices; None is what every pre-v6.14 row carries.
    return ("2026-08-27", rn, start, end, map_name, vehicle, vtype, total, destroyed,
            guid, name, team, credit, total_escort, mounted, prox, samples,
            first_move, last_move, destroyed_events, first_escort, last_escort)


class _StubDB:
    def __init__(self, rows):
        self.rows = rows
        self.queries: list[tuple[str, tuple]] = []

    async def fetch_all(self, query, params=None):
        q = " ".join(query.split())
        self.queries.append((q, params))
        if "FROM proximity_vehicle_progress vp" in q:
            # The stub honours the two SQL guards the detector relies on, so a
            # detector that dropped them would still SEE the rows — and the
            # tests below assert on the SQL text as well.
            min_dist = params[4]
            return [r for r in self.rows if r[7] >= min_dist and r[12] > 0]
        return []


def _scope() -> GamingSessionScope:
    return GamingSessionScope(
        gaming_session_id=154,
        dates=("2026-08-27",),
        round_keys=((START, "supply", 1), (START + 765, "supply", 2), (START + 2000, "etl_adlernest", 1)),
        accepted_round_count=3,
        distinct_map_names=("supply", "etl_adlernest"),
    )


def _run(rows):
    svc = _MomentsMixin.__new__(_MomentsMixin)
    svc.db = _StubDB(rows)
    detect = getattr(svc, "_detect_escort_mover")  # noqa: B009 — the detector under test is a private method by design
    return svc, asyncio.run(detect(_scope()))


def test_one_moment_per_vehicle_round_credited_to_the_top_escort_with_the_round_end_as_its_time():
    # 3 400 / 12 744 = 0.267 — just over the floor (the recording's real R1 top
    # escort sits at 0.22 and is NOT a moment; the tier test below proves it).
    rows = [
        row(credit=3400.0),
        row(guid="2B5938F5C5EA384863A3B2862DC61778", name="bronze", credit=2042.7),
        row(rn=2, start=START + 765, end=START + 765 + 700, total=15771.9,
            guid="3C0354D32C5BAFC775198C8A9EAD8087", name="^qIt's squAziii", credit=4714.3, prox=55500),
    ]
    svc, out = _run(rows)
    assert [m["round_number"] for m in out] == [1, 2]
    first = out[0]
    assert first["type"] == "escort_mover" and first["player"] == "[TWK]Imb3ciL"   # colours stripped
    assert first["map_name"] == "supply"
    assert first["time_ms"] == 612 * 1000 and first["detail"]["timestamp_source"] == "round_end"
    # Two distances, two meanings — both named.
    assert first["detail"]["credit_distance"] == 3400.0 and first["detail"]["total_escort_distance"] == 5095.1
    assert first["detail"]["credit_share"] == round(3400.0 / 12744.3, 3)
    assert first["impact_stars"] == 3
    assert [e["name"] for e in first["detail"]["escorts"]] == ["[TWK]Imb3ciL", "bronze"]
    assert "escorted the truck on supply" in first["narrative"]
    # The SQL carries the scope's round-key filter ALIASED to vp (a bare
    # column in a two-table join is ambiguous) and the credit > 0 guard.
    q, params = svc.db.queries[0]
    assert "_rk.rsu = vp.round_start_unix" in q and "ec.credit_distance > 0" in q
    assert params[4] == float(ESCORT_MOVER_MIN_DISTANCE)


def test_the_share_tiers_and_the_floor():
    # 2799.5 / 12744.3 is 0.22 — below the floor: the fixture's own R1 top
    # escort would NOT be a moment on the recording. Confirm the floor bites,
    # then walk the tiers.
    _, out = _run([row(credit=2799.5)])
    assert out == [], "a 22 % share is below ESCORT_MOVER_MIN_SHARE"
    for share, stars in ((0.25, 3), (0.49, 3), (0.5, 4), (0.74, 4), (0.75, 5), (0.84, 5)):
        _, out = _run([row(total=10000.0, credit=share * 10000.0)])
        assert len(out) == 1 and out[0]["impact_stars"] == stars, (share, out)
        assert out[0]["detail"]["credit_share"] == round(share, 3)
    assert ESCORT_MOVER_MIN_SHARE == 0.25


def test_a_tank_says_it_was_mounted_and_a_destroyed_vehicle_is_counted():
    _, out = _run([row(map_name="sw_goldrush_te", vehicle="tank", total=4000.0, credit=3000.0, mounted=19455, destroyed=2)])
    assert len(out) == 1
    assert "19s mounted" in out[0]["narrative"] and "destroyed 2×" in out[0]["narrative"]
    assert out[0]["detail"]["mounted_time_ms"] == 19455 and out[0]["detail"]["destroyed_count"] == 2


def test_a_vehicle_that_barely_moved_and_a_parked_truck_beside_a_medic_yield_nothing():
    # Under the distance floor: not a push.
    _, out = _run([row(total=ESCORT_MOVER_MIN_DISTANCE - 1, credit=900.0)])
    assert out == []
    # Proximity credit accrues only while the vehicle MOVES: a medic reviving
    # beside a parked truck has credit_distance 0 and never reaches the
    # detector (the SQL's `ec.credit_distance > 0`).
    _, out = _run([row(credit=0.0)])
    assert out == []


def test_a_missing_round_end_reads_as_unknown_not_as_zero_o_clock_confidence():
    _, out = _run([row(end=0, total=10000.0, credit=5000.0)])
    assert out[0]["time_ms"] == 0 and out[0]["detail"]["timestamp_source"] == "unknown"


def test_an_empty_database_is_an_empty_list():
    _, out = _run([])
    assert out == []


def test_the_detector_is_registered_and_ranked():
    assert "escort_mover" in _TYPE_PRIORITY
    # Rarer than a team wipe, less decisive than securing the objective.
    assert _TYPE_PRIORITY["team_wipe"] <= _TYPE_PRIORITY["escort_mover"] < _TYPE_PRIORITY["objective_secured"]
    src = open(moments_module.__file__, encoding="utf-8").read()
    start = src.index("detectors = [")
    assert "self._detect_escort_mover," in src[start:src.index("]", start)]


@pytest.mark.parametrize("share", [0.0, 0.1, 0.249])
def test_below_the_floor_is_not_a_moment_control(share):
    _, out = _run([row(total=10000.0, credit=share * 10000.0)]) if share > 0 else _run([row(total=10000.0, credit=0.0)])
    assert out == []


def test_a_v614_recording_places_the_moment_at_the_first_move_and_names_who_destroyed_the_mover():
    """Migration 082: first_move_time is the tracker's gameTime() (ms since
    round start) and needs NO conversion; destroyed_events is the JSONB list
    the v6.14 VEHICLE_DESTROYED section became."""
    events = json.dumps([
        {"time": 118900, "attacker_guid": "GUID3ABCDEF", "attacker_name": "^1kanii", "attacker_team": "axis",
         "means_of_death": 5, "health_before": 800},
        {"time": 300000, "attacker_guid": "", "attacker_name": "", "attacker_team": "", "means_of_death": 0,
         "health_before": 350},
    ])
    _svc, moments = _run([row(destroyed=2, credit=4000.0, first_move=600, last_move=118500,
                              first_escort=61000, last_escort=110000, destroyed_events=events)])
    assert len(moments) == 1
    m = moments[0]
    # The truck's own first move (600 ms, it drives itself off the line) is
    # not the escort; the escorted move is.
    assert m["time_ms"] == 61000 and m["detail"]["timestamp_source"] == "first_escort"
    assert m["detail"]["move_window_s"] == 117.9 and m["detail"]["escort_window_s"] == 49.0
    assert m["detail"]["destroyed_by"] == [
        {"name": "kanii", "team": "axis", "attacker_guid": "GUID3ABCDEF", "time_s": 118.9},
        {"name": "", "team": "", "attacker_guid": "", "time_s": 300.0},
    ]
    assert "destroyed 2× (by kanii)" in m["narrative"]


def test_a_pre_v614_recording_still_reads_round_end_and_no_destroyer():
    _svc, moments = _run([row(destroyed=1, credit=4000.0)])
    m = moments[0]
    assert m["detail"]["timestamp_source"] == "round_end" and m["time_ms"] == (END - START) * 1000
    assert m["detail"]["destroyed_by"] == [] and m["detail"]["move_window_s"] is None
    assert "(by" not in m["narrative"]


def test_a_zero_first_move_is_no_time_not_t0():
    # The Lua writes 0 for "never moved"; the parser turns it into NULL, but
    # a 0 that slipped through must not pin the moment to the round's start.
    _svc, moments = _run([row(credit=4000.0, first_move=0, last_move=0)])
    assert moments[0]["detail"]["timestamp_source"] == "round_end"


def test_a_recording_with_a_mover_that_moved_but_was_never_escorted_falls_back_to_the_first_move():
    _svc, moments = _run([row(credit=4000.0, first_move=600, last_move=30000)])
    m = moments[0]
    assert m["time_ms"] == 600 and m["detail"]["timestamp_source"] == "first_move"
    assert m["detail"]["escort_window_s"] is None
