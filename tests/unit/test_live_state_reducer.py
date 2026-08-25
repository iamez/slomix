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


def test_flag_pickup_attributed_to_roster_player():
    """A4: FLAG_PICKUP carries a slot, so the reducer names the actor from the
    current roster — 'vid grabbed <flag>' rather than an anonymous team line."""
    now = time.time()
    r = LiveStateReducer()
    r.apply(_ev("TEAM_CHANGE", now, slot=3, name="vid", team=1))
    r.apply(_ev("FLAG_PICKUP", now, slot=3, flag="Gold Documents"))
    objs = r.snapshot()["recent_objectives"]
    assert len(objs) == 1
    assert objs[0]["type"] == "flag"
    assert objs[0]["player"] == "vid"
    assert objs[0]["verb"] == "grabbed"
    assert objs[0]["objective"] == "Gold Documents"


def test_dynamite_attributed_and_unknown_slot_is_none():
    """A4: DYNAMITE plant/defuse is named from the roster; a slot with no
    CONNECT yet resolves to player=None instead of crashing."""
    now = time.time()
    r = LiveStateReducer()
    r.apply(_ev("TEAM_CHANGE", now, slot=5, name=".lgz", team=2))
    r.apply(_ev("DYNAMITE", now, slot=5, action="plant", objective="Main Entrance"))
    r.apply(_ev("DYNAMITE", now, slot=9, action="defuse", objective="Side Wall"))
    objs = r.snapshot()["recent_objectives"]
    assert objs[0]["player"] == ".lgz"
    assert objs[0]["verb"] == "plant"
    assert objs[1]["player"] is None  # slot 9 never connected
    assert objs[1]["verb"] == "defuse"


def test_idle_snapshot_clears_stale_roster():
    """A server restart sends no DISCONNECTs, so the roster would freeze the
    final line-up. Once the stream goes quiet (is_live False), the snapshot
    must show no players — not the stale line-up as if a match were still on."""
    old = time.time() - 3600  # an hour ago → well past the live window
    r = LiveStateReducer()
    r.apply(_ev("TEAM_CHANGE", old, slot=1, name="[BOT]vid", team=1))
    r.apply(_ev("TEAM_CHANGE", old, slot=2, name="[BOT]lgz", team=2))
    snap = r.snapshot()
    assert snap["is_live"] is False
    assert snap["game_state"] == "idle"
    assert snap["roster"]["axis"] == []
    assert snap["roster"]["allies"] == []
    assert snap["roster"]["player_count"] == 0
    assert snap["roster"]["has_bots"] is False
    assert snap["session_start_seconds"] is None


def test_resume_after_idle_gap_resets_internal_roster():
    """The snapshot clear alone leaves self._roster populated, so a reused slot
    after a restart would be ignored and the stale player could reappear once
    is_live flips true. The first event after an idle gap must reset the roster
    so the new session starts clean."""
    now = time.time()
    r = LiveStateReducer()
    # Old session, then a long quiet gap.
    r.apply(_ev("TEAM_CHANGE", now - 3600, slot=1, name="[BOT]old_vid", team=1))
    r.apply(_ev("TEAM_CHANGE", now - 3600, slot=2, name="[BOT]old_lgz", team=2))
    # New session reuses slot 1 for a different, real player.
    r.apply(_ev("TEAM_CHANGE", now, slot=1, name="realvid", team=2))
    snap = r.snapshot()
    assert snap["is_live"] is True
    names = [m["name"] for m in snap["roster"]["allies"]]
    assert names == ["realvid"]          # the reused slot took the new name
    assert snap["roster"]["axis"] == []  # old_vid did not survive the gap
    assert snap["roster"]["player_count"] == 1


# -- A3: roster-change (substitution) log ----------------------------------


def test_roster_changes_log_join_switch_and_leave():
    now = time.time()
    r = LiveStateReducer()
    r.apply(_ev("TEAM_CHANGE", now, slot=1, name="vid", team=1))       # joined Axis
    r.apply(_ev("TEAM_CHANGE", now, slot=2, name="ownator", team=2))   # joined Allies
    r.apply(_ev("TEAM_CHANGE", now, slot=1, team=2))                   # vid → Allies (switch)
    r.apply(_ev("DISCONNECT", now, slot=2))                           # ownator left
    changes = r.snapshot()["recent_roster_changes"]
    assert [(c["name"], c["action"], c["side"]) for c in changes] == [
        ("vid", "joined", "Axis"),
        ("ownator", "joined", "Allies"),
        ("vid", "switched", "Allies"),
        ("ownator", "left", "Allies"),
    ]
    assert all(c["age_seconds"] >= 0 for c in changes)


def test_roster_changes_ignore_unnamed_slots_and_spectators():
    now = time.time()
    r = LiveStateReducer()
    r.apply(_ev("CONNECT", now, slot=5))       # bare slot, no name/side
    r.apply(_ev("DISCONNECT", now, slot=5))    # not a named "left"
    r.apply(_ev("TEAM_CHANGE", now, slot=6, name="ref", team=3))  # spectator, no "joined"
    r.apply(_ev("TEAM_CHANGE", now, slot=7, name="", team=1))     # empty name → no "slot 7 joined"
    r.apply(_ev("TEAM_CHANGE", now, slot=8, team=2))             # missing name → no join
    assert r.snapshot()["recent_roster_changes"] == []


def test_roster_changes_cleared_on_idle_reset():
    now = time.time()
    r = LiveStateReducer()
    r.apply(_ev("TEAM_CHANGE", now - 3600, slot=1, name="vid", team=1))
    r.apply(_ev("TEAM_CHANGE", now, slot=2, name="new", team=1))  # long gap → reset first
    changes = r.snapshot()["recent_roster_changes"]
    assert [c["name"] for c in changes] == ["new"]  # pre-gap join did not survive


def test_map_flipback_pingpong_is_damped():
    """Dueling sources (legacy3 MAP vs LIVEX LIVE_MAP): a lagging source
    re-asserting the PREVIOUS map right after a change must not flip the
    state back (each hop wiped round_number/objectives — 2026-08-18)."""
    now = time.time()
    r = LiveStateReducer()
    r.apply({"type": "MAP", "map_name": "supply", "received_at": now})
    r.apply({"type": "MAP", "map_name": "etl_adlernest", "received_at": now + 10})
    # stale source still believes supply
    r.apply({"type": "LIVE_MAP", "map_name": "supply", "received_at": now + 15})
    assert r.snapshot()["current_map"] == "etl_adlernest"
    # a genuine later change back is honoured once the damper window passes
    r.apply({"type": "MAP", "map_name": "supply", "received_at": now + 120})
    assert r.snapshot()["current_map"] == "supply"


def test_roster_lingers_through_delivery_gap():
    """A tailer delivery gap (CF 403/530) must dim the roster, not blank it —
    the card used to flap full<->empty across the is_live edge."""
    now = time.time()
    r = LiveStateReducer()
    r.apply({"type": "TEAM_CHANGE", "slot": 1, "name": "vid", "team": 2,
             "received_at": now - 300})  # last event 5 min ago
    snap = r.snapshot()
    assert snap["is_live"] is False
    assert [m["name"] for m in snap["roster"]["allies"]] == ["vid"]
    assert snap["roster"]["roster_age_seconds"] >= 299


def test_third_round_start_wraps_to_r1():
    """Stopwatch has only R1/R2 — a third ROUND_START without a MAP means
    the MAP event was dropped; treat it as the next map's R1, not 'R3'."""
    now = time.time()
    r = LiveStateReducer()
    for i in range(3):
        r.apply({"type": "ROUND_START", "received_at": now + i})
    assert r.snapshot()["round_number"] == 1


def test_live_ladder_folds_aggregate_deltas_and_alive():
    """Val A: LIVE_AGGREGATE deltas sum per round, LIVE_KILL flips the victim
    dead, LIVE_MOVEMENT revives, ROUND_START resets the ladder."""
    now = time.time()
    r = LiveStateReducer()
    r.apply({"type": "TEAM_CHANGE", "slot": 3, "name": "vid", "team": 2,
             "received_at": now - 120})
    r.apply({"type": "ROUND_START", "received_at": now - 100})
    r.apply({"type": "LIVE_AGGREGATE", "slot": 3, "kills": 2, "deaths": 1,
             "damage_given": 600, "damage_received": 100, "received_at": now - 60})
    r.apply({"type": "LIVE_AGGREGATE", "slot": 3, "kills": 1, "deaths": 0,
             "damage_given": 400, "damage_received": 0, "received_at": now - 30})
    r.apply({"type": "LIVE_KILL", "killer_slot": 5, "victim_slot": 3,
             "received_at": now - 10})
    snap = r.snapshot()
    live = snap["roster"]["allies"][0]["live"]
    assert live["kills"] == 3 and live["deaths"] == 1
    assert live["alive"] is False
    assert live["dpm"] is not None and live["dpm"] > 0

    # movement marks him alive again; a new round wipes the tallies
    r.apply({"type": "LIVE_MOVEMENT",
             "players": [{"slot": 3, "x": 1, "y": 2}], "received_at": now - 5})
    assert r.snapshot()["roster"]["allies"][0]["live"]["alive"] is True
    r.apply({"type": "ROUND_START", "received_at": now})
    assert "live" not in (r.snapshot()["roster"]["allies"][0])


class TestTheMapCarriesItsOwnEvidence:
    """⛔ A map that survived a session boundary looked brand new.

    The idle reset clears the roster, the objectives and the round — but not
    the map, and not the game state. After a long gap the first event is
    usually a CONNECT rather than a MAP, so `is_live` flipped back to true
    and `last_event_age_seconds` read seconds while `current_map` still held
    the PREVIOUS session's map, with no field a client could use to doubt it
    (Codex on PR #806, via Fable).

    ⭐ The map is not cleared. A restarted server usually returns on the same
    map, so blanking it trades a stale answer for no answer. What is cleared
    is the ASSERTION — the map keeps its value and loses its evidence.
    """

    def _played(self, now):
        r = LiveStateReducer()
        r.apply(_ev("MAP", now, map_name="supply"))
        r.apply(_ev("TEAM_CHANGE", now + 1, slot=1, name="ciril", team=1))
        return r

    def test_a_map_confirmed_by_an_event_says_so(self):
        now = time.time()
        snap = self._played(now).snapshot()
        assert snap["current_map"] == "supply"
        assert snap["map_confirmed"] is True
        assert snap["map_age_seconds"] is not None

    def test_a_session_gap_leaves_the_map_unconfirmed(self):
        now = time.time()
        r = self._played(now - 6000)
        r.apply(_ev("CONNECT", now, slot=7, name="nekdo"))
        snap = r.snapshot()

        # The trap in full: live again, seconds old, wrong map.
        assert snap["is_live"] is True
        assert snap["last_event_age_seconds"] < 60
        assert snap["current_map"] == "supply"
        # …and now it admits it.
        assert snap["map_confirmed"] is False
        assert snap["map_age_seconds"] is None

    def test_the_stale_game_state_goes_with_it(self):
        """`game_state` survived too, so the previous session's `mapchange`
        or `live` was served beside the stale map."""
        now = time.time()
        r = self._played(now - 6000)
        r.apply(_ev("LIVE", now - 5999))
        r.apply(_ev("CONNECT", now, slot=7, name="nekdo"))
        assert r.snapshot()["game_state"] == "unknown"

    def test_a_map_event_confirms_it_again(self):
        now = time.time()
        r = self._played(now - 6000)
        r.apply(_ev("CONNECT", now - 30, slot=7, name="nekdo"))
        r.apply(_ev("MAP", now, map_name="te_escape2"))
        snap = r.snapshot()
        assert snap["current_map"] == "te_escape2"
        assert snap["map_confirmed"] is True

    def test_an_event_naming_the_SAME_map_is_a_confirmation(self):
        """⭐ CHANGED and ASSERTED are different questions. The map handler
        returns early when the name has not changed, so a re-assertion used to
        leave no trace — and `_map_changed_at` would have reported the age of
        the last CHANGE, which on a long map is hours."""
        now = time.time()
        r = self._played(now - 6000)
        r.apply(_ev("CONNECT", now - 30, slot=7, name="nekdo"))
        assert r.snapshot()["map_confirmed"] is False

        r.apply(_ev("MAP", now, map_name="supply"))       # same map as before
        snap = r.snapshot()
        assert snap["map_confirmed"] is True
        assert snap["map_age_seconds"] < 60

    def test_a_rejected_ping_pong_event_is_not_evidence_for_the_map_we_hold(self):
        """⚠️ Two sources report the map (legacy3 `MAP`, LIVEX `LIVE_MAP`) and
        the lagging one flips straight back to the PREVIOUS map. That event is
        rejected as a change — and must not count as evidence for the map we
        kept either, because it did not name it (Codex, PR #808).

        ⭐ THE CONSEQUENCE IS BOUNDED, and saying so is part of the finding.
        The rejection only fires within `_MAP_FLIPBACK_SECONDS` of the last
        change, so the wrongly-refreshed assertion can overstate the map's
        freshness by at most that window. It can NEVER manufacture a
        `map_confirmed: True` after a session gap, because a gap is ten times
        longer than the flip-back window and no rejection can happen inside
        one. Real, small, and worth fixing where it is cheap.
        """
        now = time.time()
        r = LiveStateReducer()
        r.apply(_ev("MAP", now - 100, map_name="supply"))
        r.apply(_ev("MAP", now - 40, map_name="te_escape2"))     # real change
        # The lagging source re-asserts the OLD map 30 s later — inside the
        # flip-back window, so the handler rejects it.
        r.apply(_ev("LIVE_MAP", now - 10, map_name="supply"))

        snap = r.snapshot()
        assert snap["current_map"] == "te_escape2", "the flip-back was accepted"
        # Evidence dates from the CHANGE (40 s ago), not from the rejected
        # event (10 s ago).
        assert snap["map_age_seconds"] >= 39
