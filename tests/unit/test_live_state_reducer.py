"""Live-view A0: current-state reducer contract.

Pins the snapshot semantics that fix the stale-feed problem: the roster
reflects CURRENT membership (disconnects drop out), sides are split by
engine team, timers count from connect/side-change, and a quiet stream
reads idle so an old state never renders as live.
"""

from __future__ import annotations

import time

from website.backend.services.live_state import LiveStateReducer


def _ev(t, at, **f):
    return {"type": t, "received_at": at, **f}


def test_roster_split_by_side_and_current_membership():
    now = time.time()
    r = LiveStateReducer()
    r.apply(_ev("TEAM_CHANGE", now, slot=1, name="vid", team=1))
    r.apply(_ev("TEAM_CHANGE", now, slot=2, name=".lgz", team=2))
    r.apply(_ev("TEAM_CHANGE", now, slot=3, name="ref", team=3))
    r.apply(_ev("TEAM_CHANGE", now, slot=4, name="leaver", team=1))
    r.apply(_ev("DISCONNECT", now, slot=4))  # left → must not appear
    snap = r.snapshot()
    assert [m["name"] for m in snap["roster"]["axis"]] == ["vid"]
    assert [m["name"] for m in snap["roster"]["allies"]] == [".lgz"]
    assert [m["name"] for m in snap["roster"]["spectators"]] == ["ref"]
    assert snap["roster"]["player_count"] == 2  # spectators excluded
    assert snap["is_live"] is True


def test_side_switch_resets_side_timer_not_server_timer():
    now = time.time()
    r = LiveStateReducer()
    r.apply(_ev("TEAM_CHANGE", now - 600, slot=1, name="vid", team=1))
    r.apply(_ev("TEAM_CHANGE", now - 60, slot=1, name="vid", team=2))
    m = r.snapshot()["roster"]["allies"][0]
    assert m["on_server_seconds"] >= 590      # connected 10 min ago
    assert 50 <= m["on_side_seconds"] <= 70   # switched side 1 min ago


def test_map_transition_tracks_previous_and_marks_mapchange():
    now = time.time()
    r = LiveStateReducer()
    r.apply(_ev("MAP", now, map_name="adlernest"))
    r.apply(_ev("MAP", now, map_name="supply"))
    snap = r.snapshot()
    assert snap["current_map"] == "supply"
    assert snap["previous_map"] == "adlernest"


def test_game_state_machine():
    now = time.time()
    r = LiveStateReducer()
    r.apply(_ev("INIT_GAME", now))
    assert r.snapshot()["game_state"] == "warmup"
    r.apply(_ev("ROUND_START", now))
    s = r.snapshot()
    assert s["game_state"] == "live" and s["round_number"] == 1
    assert s["round_elapsed_seconds"] is not None
    r.apply(_ev("ROUND_END", now))
    assert r.snapshot()["game_state"] == "between"


def test_quiet_stream_reads_idle_not_stale():
    old = time.time() - 3600
    r = LiveStateReducer()
    r.apply(_ev("ROUND_START", old))
    r.apply(_ev("TEAM_CHANGE", old, slot=1, name="vid", team=1))
    snap = r.snapshot()
    # Roster persists (who was last seen), but the session reads idle so the
    # UI won't present an hour-old state as "live".
    assert snap["is_live"] is False
    assert snap["game_state"] == "idle"
    assert snap["round_number"] is None
    assert snap["recent_objectives"] == []


def test_bot_flag_and_objectives():
    now = time.time()
    r = LiveStateReducer()
    r.apply(_ev("TEAM_CHANGE", now, slot=1, name="[BOT]vid", team=1))
    r.apply(_ev("POPUP", now, team="allies", verb="stole", objective="Gold"))
    snap = r.snapshot()
    assert snap["roster"]["has_bots"] is True
    assert snap["recent_objectives"][-1]["objective"] == "Gold"
