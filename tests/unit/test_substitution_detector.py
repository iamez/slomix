"""Tests for SubstitutionDetector — pure logic methods.

This service detects mid-session player swaps (e.g., player A leaves
mid-match, player B takes their slot) so that team detection can
attribute B to the same team as A. A regression silently:

- PlayerActivity flags inverted → late joiners categorised as full
  session players → wrong team attribution.
- `_detect_roster_changes` swaps departure/addition direction →
  every "left" is reported as "joined" and vice versa.
- `_detect_substitutions` zip mismatch (uneven dep/add count) →
  silently drops one side → no substitution detected for half the
  swaps.
- `_generate_summary` truncation drops a >3 list silently → operator
  log shows partial picture.
- `adjust_team_detection_for_substitutions` unsafe key access →
  KeyError when `team_assignments` doesn't contain a substitute.

Pin every pure-logic branch.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from bot.core.substitution_detector import (
    PlayerActivity,
    RosterChange,
    SubstitutionDetector,
)

# ---------------------------------------------------------------------------
# PlayerActivity dataclass
# ---------------------------------------------------------------------------


def _make_activity(first_round=1, last_round=2, rounds_played=None, game_teams=None):
    return PlayerActivity(
        player_guid="g1",
        player_name="alice",
        first_round=first_round,
        last_round=last_round,
        rounds_played=rounds_played or {1, 2},
        game_teams=game_teams or {1: 1, 2: 1},
    )


def test_activity_is_full_session_when_first_round_is_1():
    """Pin: full session = started at round 1."""
    a = _make_activity(first_round=1)
    assert a.is_full_session is True
    assert a.is_late_joiner is False


def test_activity_is_late_joiner_when_first_round_above_1():
    """Pin: late joiner = first_round > 1 (didn't play round 1)."""
    a = _make_activity(first_round=2)
    assert a.is_late_joiner is True
    assert a.is_full_session is False


def test_activity_is_early_leaver_always_false():
    """Pin observed: is_early_leaver always returns False (caller
    determines this based on session-wide last round)."""
    a = _make_activity()
    assert a.is_early_leaver is False


# ---------------------------------------------------------------------------
# RosterChange dataclass + __str__
# ---------------------------------------------------------------------------


def test_roster_change_str_addition():
    """Addition → "Round N: <name> joined Team X"."""
    c = RosterChange(
        round_number=2,
        change_type="addition",
        game_team=1,
        player_in="alice",
        guid_in="g1",
    )
    out = str(c)
    assert "Round 2" in out
    assert "alice" in out
    assert "joined" in out
    assert "Team 1" in out


def test_roster_change_str_departure():
    """Departure → "Round N: <name> left Team X"."""
    c = RosterChange(
        round_number=3,
        change_type="departure",
        game_team=2,
        player_out="bob",
        guid_out="g2",
    )
    out = str(c)
    assert "Round 3" in out
    assert "bob" in out
    assert "left" in out
    assert "Team 2" in out


def test_roster_change_str_substitution():
    """Substitution → "Round N: <out> → <in> (Team X)"."""
    c = RosterChange(
        round_number=4,
        change_type="substitution",
        game_team=1,
        player_in="carol",
        player_out="alice",
        guid_in="g3",
        guid_out="g1",
    )
    out = str(c)
    assert "alice → carol" in out
    assert "Team 1" in out


def test_roster_change_str_unknown_falls_through():
    """Unknown change_type → "Unknown change" sentinel (no crash)."""
    c = RosterChange(round_number=1, change_type="weird", game_team=1)
    assert "Unknown change" in str(c)


# ---------------------------------------------------------------------------
# _detect_roster_changes
# ---------------------------------------------------------------------------


def _make_detector():
    return SubstitutionDetector(db_adapter=MagicMock())


def test_detect_changes_no_changes_when_rosters_identical():
    """Roster identical across rounds → no changes detected."""
    det = _make_detector()
    rosters = {
        1: {"team1": [{"guid": "g1"}, {"guid": "g2"}], "team2": [{"guid": "g3"}]},
        2: {"team1": [{"guid": "g1"}, {"guid": "g2"}], "team2": [{"guid": "g3"}]},
    }
    activity = {
        "g1": _make_activity(),
        "g2": _make_activity(),
        "g3": _make_activity(),
    }
    out = det._detect_roster_changes(rosters, activity)
    assert out == []


def test_detect_changes_addition_only():
    """A new GUID appears in next round → "addition" change."""
    det = _make_detector()
    rosters = {
        1: {"team1": [{"guid": "g1"}], "team2": [{"guid": "g3"}]},
        2: {"team1": [{"guid": "g1"}, {"guid": "g2"}], "team2": [{"guid": "g3"}]},
    }
    activity = {
        "g1": _make_activity(),
        "g2": PlayerActivity("g2", "bob", 2, 2, {2}, {2: 1}),
        "g3": _make_activity(),
    }
    changes = det._detect_roster_changes(rosters, activity)
    assert len(changes) == 1
    assert changes[0].change_type == "addition"
    assert changes[0].guid_in == "g2"
    assert changes[0].game_team == 1


def test_detect_changes_departure_only():
    """GUID disappears in next round → "departure" change."""
    det = _make_detector()
    rosters = {
        1: {"team1": [{"guid": "g1"}, {"guid": "g2"}], "team2": [{"guid": "g3"}]},
        2: {"team1": [{"guid": "g1"}], "team2": [{"guid": "g3"}]},
    }
    activity = {"g1": _make_activity(), "g2": _make_activity(), "g3": _make_activity()}
    changes = det._detect_roster_changes(rosters, activity)
    assert len(changes) == 1
    assert changes[0].change_type == "departure"
    assert changes[0].guid_out == "g2"


def test_detect_changes_separates_team1_and_team2():
    """Same round can have changes in BOTH teams. Pin per-team
    iteration so a regression that loops once doesn't miss team 2."""
    det = _make_detector()
    rosters = {
        1: {"team1": [{"guid": "g1"}], "team2": [{"guid": "g3"}]},
        2: {"team1": [{"guid": "g2"}], "team2": [{"guid": "g4"}]},
    }
    activity = {
        "g1": _make_activity(),
        "g2": _make_activity(),
        "g3": _make_activity(),
        "g4": _make_activity(),
    }
    changes = det._detect_roster_changes(rosters, activity)
    # 2 departures + 2 additions = 4 changes
    assert len(changes) == 4
    teams = {c.game_team for c in changes}
    assert teams == {1, 2}


# ---------------------------------------------------------------------------
# _detect_substitutions
# ---------------------------------------------------------------------------


def test_detect_subs_pairs_same_round_dep_with_add():
    """Same round + same team has 1 dep + 1 add → 1 substitution."""
    det = _make_detector()
    changes = [
        RosterChange(round_number=2, change_type="departure",
                     game_team=1, guid_out="g1", player_out="alice"),
        RosterChange(round_number=2, change_type="addition",
                     game_team=1, guid_in="g2", player_in="bob"),
    ]
    out = det._detect_substitutions(changes)
    assert out == [("g1", "g2", 2)]


def test_detect_subs_pairs_only_within_same_team():
    """Departure on team 1, addition on team 2 → NOT a substitution
    (different teams)."""
    det = _make_detector()
    changes = [
        RosterChange(round_number=2, change_type="departure",
                     game_team=1, guid_out="g1"),
        RosterChange(round_number=2, change_type="addition",
                     game_team=2, guid_in="g2"),
    ]
    out = det._detect_substitutions(changes)
    assert out == []


def test_detect_subs_pairs_only_within_same_round():
    """Departure round 2 + addition round 3 → NOT a substitution."""
    det = _make_detector()
    changes = [
        RosterChange(round_number=2, change_type="departure",
                     game_team=1, guid_out="g1"),
        RosterChange(round_number=3, change_type="addition",
                     game_team=1, guid_in="g2"),
    ]
    out = det._detect_substitutions(changes)
    assert out == []


def test_detect_subs_unequal_count_uses_zip():
    """2 departures + 1 addition → 1 sub (zip stops at shortest).
    Pin observed semantics — caller could later choose another
    pairing strategy, but must be a deliberate change."""
    det = _make_detector()
    changes = [
        RosterChange(round_number=2, change_type="departure",
                     game_team=1, guid_out="g1"),
        RosterChange(round_number=2, change_type="departure",
                     game_team=1, guid_out="g2"),
        RosterChange(round_number=2, change_type="addition",
                     game_team=1, guid_in="g3"),
    ]
    out = det._detect_substitutions(changes)
    assert len(out) == 1


def test_detect_subs_returns_empty_when_no_changes():
    det = _make_detector()
    assert det._detect_substitutions([]) == []


def test_detect_subs_no_match_when_only_departures():
    """Only departures → no subs (need both sides)."""
    det = _make_detector()
    changes = [
        RosterChange(round_number=2, change_type="departure",
                     game_team=1, guid_out="g1"),
    ]
    assert det._detect_substitutions(changes) == []


# ---------------------------------------------------------------------------
# _generate_summary
# ---------------------------------------------------------------------------


def test_summary_includes_total_and_full_session_counts():
    det = _make_detector()
    activity = {
        "g1": _make_activity(),
        "g2": _make_activity(),
        "g3": PlayerActivity("g3", "bob", 2, 3, {2, 3}, {2: 1}),
    }
    summary = det._generate_summary(
        activity, [], full_session=["g1", "g2"],
        late_joiners=[], early_leavers=[], substitutions=[],
    )
    assert "Total Players: 3" in summary
    assert "Full Session: 2" in summary


def test_summary_truncates_late_joiners_to_3():
    """>3 late joiners → first 3 listed + "...and N more"."""
    det = _make_detector()
    activity = {
        f"g{i}": PlayerActivity(f"g{i}", f"p{i}", 3, 5, {3, 4, 5}, {3: 1})
        for i in range(5)
    }
    summary = det._generate_summary(
        activity, [], [], late_joiners=list(activity.keys()),
        early_leavers=[], substitutions=[],
    )
    assert "Late Joiners: 5" in summary
    assert "...and 2 more" in summary  # 5 - 3 = 2


def test_summary_omits_late_joiners_when_empty():
    """No late joiners → that section absent (cleaner output)."""
    det = _make_detector()
    summary = det._generate_summary(
        {}, [], [], late_joiners=[], early_leavers=[], substitutions=[],
    )
    assert "Late Joiners" not in summary


def test_summary_includes_substitutions_count_when_present():
    det = _make_detector()
    summary = det._generate_summary(
        {}, [], [], late_joiners=[], early_leavers=[],
        substitutions=[("g1", "g2", 2), ("g3", "g4", 3)],
    )
    assert "Substitutions: 2" in summary


# ---------------------------------------------------------------------------
# adjust_team_detection_for_substitutions
# ---------------------------------------------------------------------------


def test_adjust_assigns_substitute_to_same_team():
    """Sub: g1 (team A) leaves, g2 enters → g2 attributed to team A."""
    det = _make_detector()
    team_assignments = {"g1": "A", "g2": "B"}
    sub_analysis = {"substitutions": [("g1", "g2", 2)]}
    out = det.adjust_team_detection_for_substitutions(team_assignments, sub_analysis)
    assert out["g2"] == "A"  # was B, now A (matches g1's team)


def test_adjust_does_not_modify_original_dict():
    """Pin: returns a new dict (caller's original untouched)."""
    det = _make_detector()
    team_assignments = {"g1": "A", "g2": "B"}
    sub_analysis = {"substitutions": [("g1", "g2", 2)]}
    det.adjust_team_detection_for_substitutions(team_assignments, sub_analysis)
    assert team_assignments == {"g1": "A", "g2": "B"}  # unchanged


def test_adjust_returns_input_when_no_substitutions_key():
    """No 'substitutions' key → return input unchanged."""
    det = _make_detector()
    team_assignments = {"g1": "A"}
    out = det.adjust_team_detection_for_substitutions(team_assignments, {})
    assert out == team_assignments


def test_adjust_returns_input_when_analysis_empty_dict():
    """Empty dict → return input unchanged."""
    det = _make_detector()
    team_assignments = {"g1": "A"}
    out = det.adjust_team_detection_for_substitutions(team_assignments, {})
    assert out == team_assignments


def test_adjust_skips_subs_with_unknown_guids():
    """If either guid_out or guid_in not in team_assignments → skip
    (no KeyError). Pin defensive default for partial sub data."""
    det = _make_detector()
    team_assignments = {"g1": "A"}  # only g1 known
    sub_analysis = {"substitutions": [("g1", "g_unknown", 2)]}
    out = det.adjust_team_detection_for_substitutions(team_assignments, sub_analysis)
    # g_unknown not added to result
    assert "g_unknown" not in out


def test_adjust_handles_multiple_subs():
    """Multiple subs → all applied."""
    det = _make_detector()
    team_assignments = {"g1": "A", "g2": "X", "g3": "B", "g4": "Y"}
    sub_analysis = {"substitutions": [
        ("g1", "g2", 2),
        ("g3", "g4", 3),
    ]}
    out = det.adjust_team_detection_for_substitutions(team_assignments, sub_analysis)
    assert out["g2"] == "A"
    assert out["g4"] == "B"
