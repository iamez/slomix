"""Tests for filler-map detection + roster-change ('ambiguous sides') scoring.

- is_filler_map: the config-driven blocklist used to flag rounds.is_valid=FALSE.
- StopwatchScoringService: when a mid-session substitution reshuffles teams so a
  map can't be attributed to the detected rosters, the scorer must now show the
  map winner BY TIME + a "roster changed" note instead of a blank "Unscored".
"""
from __future__ import annotations

import pytest

from bot.core.round_contract import is_filler_map
from bot.services.stopwatch_scoring_service import StopwatchScoringService


# --------------------------------------------------------------------------- #
# is_filler_map
# --------------------------------------------------------------------------- #
def test_is_filler_map_blocklist():
    excluded = {"mp_sillyctf"}
    assert is_filler_map("mp_sillyctf", excluded) is True
    assert is_filler_map("MP_SillyCTF", excluded) is True  # case-insensitive
    assert is_filler_map("  mp_sillyctf  ", excluded) is True  # trimmed
    assert is_filler_map("etl_adlernest", excluded) is False
    assert is_filler_map(None, excluded) is False
    assert is_filler_map("mp_sillyctf", set()) is False  # empty blocklist


def test_is_filler_map_multiple_maps():
    excluded = {"mp_sillyctf", "fun_beach"}
    assert is_filler_map("fun_beach", excluded) is True
    assert is_filler_map("supply", excluded) is False


# --------------------------------------------------------------------------- #
# Roster-change ('ambiguous sides') scoring
# --------------------------------------------------------------------------- #
class _FakeDB:
    """Minimal async db_adapter stub for StopwatchScoringService.

    Dispatches fetch_all by query content: the rounds query returns one
    complete map (R1+R2); the player-side sample query returns players whose
    GUIDs are NOT in either roster (so both teams tie at 0 → ambiguous sides).
    """

    def __init__(self, rounds_rows, player_rows):
        self._rounds = rounds_rows
        self._players = player_rows

    async def fetch_all(self, query, params=()):
        if "FROM player_comprehensive_stats" in query:
            return self._players
        return self._rounds


def _rounds_one_map():
    # (id, map_name, gaming_session_id, round_number, defender_team,
    #  winner_team, time_limit, actual_time, round_date, round_time, match_id)
    return [
        (1, "etl_adlernest", 99, 1, 2, 1, "0", "10:00", "2026-06-08", "230738", "m-adler-1"),
        (2, "etl_adlernest", 99, 2, 1, 2, "0", "1:54", "2026-06-08", "231011", "m-adler-1"),
    ]


@pytest.mark.asyncio
async def test_roster_change_shows_winner_by_time_not_blank():
    # Players in the round are subs whose GUIDs are in NEITHER roster → the
    # scorer can't map sides to teams → 'ambiguous'. It must still report the
    # map winner by time, not a blank "Unscored".
    db = _FakeDB(_rounds_one_map(), player_rows=[("SUB1", 1), ("SUB2", 2)])
    svc = StopwatchScoringService(db)

    res = await svc.calculate_session_scores_with_teams(
        "2026-06-08",
        [1, 2],
        {"Team A": ["AAA"], "Team B": ["BBB"]},
    )
    assert res is not None
    maps = res["maps"]
    assert len(maps) == 1
    m = maps[0]

    # No longer the old blank message.
    assert "Unscored: team sides ambiguous" not in (m.get("note") or "")
    # Shows the map winner by time (R2 attackers completed 1:54, R1 fullhold 10:00).
    assert "roster changed" in m["note"].lower()
    assert "R2 attackers won" in m["note"]
    assert "1:54" in m["note"]
    # Keep 'ambiguous' so downstream (sessions_router) still flags it incomplete.
    assert m["scoring_source"] == "ambiguous"
    # ⚠ (not ⚪) distinguishes roster-changed from a plain tie for emoji-only consumers.
    assert m["emoji"] == "⚠"
    # winner_side unknown (ambiguous) — not the stale Lua header value.
    assert m["winner_side"] is None
    # Not attributed to a persistent team → not added to the tally.
    assert m["counted"] is False
    assert res["team_a_maps"] == 0
    assert res["team_b_maps"] == 0


@pytest.mark.asyncio
async def test_clean_rosters_still_attribute_normally():
    # Sanity: when the round players DO match the rosters, scoring attributes
    # to a team as before (no roster-changed note).
    db = _FakeDB(_rounds_one_map(), player_rows=[("AAA", 1), ("BBB", 2)])
    svc = StopwatchScoringService(db)

    res = await svc.calculate_session_scores_with_teams(
        "2026-06-08",
        [1, 2],
        {"Team A": ["AAA"], "Team B": ["BBB"]},
    )
    assert res is not None
    m = res["maps"][0]
    assert m["counted"] is True
    assert "roster changed" not in (m.get("note") or "").lower()
    # One team should have won the map (R2 attackers faster).
    assert res["team_a_maps"] + res["team_b_maps"] == 2  # BOX scale: every map is worth 2 points


# ---------------------------------------------------------------------------
# round_has_bots — bot detection independent of bot_player_count (session-123)
# ---------------------------------------------------------------------------
from bot.core.round_contract import round_has_bots  # noqa: E402


def test_round_has_bots_by_is_bot_flag():
    assert round_has_bots([{"name": "real", "is_bot": False},
                           {"name": "x", "is_bot": True}]) is True


def test_round_has_bots_by_omnibot_guid():
    # The session-123 case: is_bot flag missing, count would be 0,
    # but the guid betrays the Omni-bot.
    assert round_has_bots([{"name": "[BOT]vid", "guid": "OMNIBOT06c000"}]) is True
    assert round_has_bots([{"name": "vid", "guid": "omnibot06c"}]) is True  # case-insensitive


def test_round_has_bots_by_name_prefix():
    assert round_has_bots([{"name": "[BOT]wajs", "guid": ""}]) is True


def test_round_has_bots_all_humans():
    assert round_has_bots([{"name": "vid", "guid": "D8423F90"},
                           {"name": "olz", "guid": "5D989160"}]) is False


def test_round_has_bots_empty_or_none():
    assert round_has_bots([]) is False
    assert round_has_bots(None) is False
