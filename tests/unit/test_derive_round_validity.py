"""Unit tests for round_contract.derive_round_validity.

Added with the fix for the production import path
(PostgreSQLDatabaseManager) historically omitting the bot/filler/orphan
validity columns from its rounds INSERT — the 2026-08-11 Omni-bot test
proved live that is_bot_round had never been true and no bot round was
ever auto-invalidated in either database's history.
"""

from bot.core.round_contract import derive_round_validity


def _bot(name="[BOT]endekk", guid="OMNIBOT0f23b545ac317f49ffd18af43"):
    return {"name": name, "guid": guid, "is_bot": True}


def _human(name="vid", guid="ABCDEF1234567890ABCDEF1234567890"):
    return {"name": name, "guid": guid, "is_bot": False}


def test_all_bot_round_is_flagged_and_invalid():
    parsed = {
        "players": [_bot() for _ in range(6)],
        "bot_player_count": 6,
        "human_player_count": 0,
        "is_bot_round": True,
    }
    v = derive_round_validity(parsed, "sw_goldrush_te", {"mp_sillyctf"})
    assert v["is_bot_round"] is True
    assert v["is_valid"] is False
    assert v["bot_player_count"] == 6


def test_one_human_with_bot_majority_is_bot_round_and_invalid():
    # The owner-test-session shape: 1 human + N omni-bots (majority rule).
    parsed = {
        "players": [_human()] + [_bot() for _ in range(6)],
        "bot_player_count": 6,
        "human_player_count": 1,
        # Parser field deliberately absent — majority must be recomputed.
    }
    v = derive_round_validity(parsed, "supply", set())
    assert v["is_bot_round"] is True
    assert v["is_valid"] is False


def test_counts_absent_recomputed_from_player_flags():
    parsed = {"players": [_bot(), _bot(), _human()]}
    v = derive_round_validity(parsed, "supply", set())
    assert v["bot_player_count"] == 2
    assert v["human_player_count"] == 1
    assert v["is_bot_round"] is True  # 2 > 1 strict majority
    assert v["is_valid"] is False


def test_single_bot_minority_invalidates_but_not_bot_round():
    # ANY bot participation invalidates (owner intent), but a bot minority
    # is not a "bot round" under the majority rule.
    parsed = {
        "players": [_human(), _human(), _human(), _bot()],
        "bot_player_count": 1,
        "human_player_count": 3,
    }
    v = derive_round_validity(parsed, "supply", set())
    assert v["is_bot_round"] is False
    assert v["is_valid"] is False


def test_guid_only_bot_detection_invalidates():
    # Defensive path: no is_bot flags, no counts — OMNIBOT guid prefix and
    # [BOT] name still mark the round invalid via round_has_bots.
    parsed = {
        "players": [
            {"name": "[BOT]lagger", "guid": "OMNIBOT0b4a883c4d3532f3f6d099b94"}
        ]
    }
    v = derive_round_validity(parsed, "supply", set())
    assert v["is_valid"] is False


def test_filler_map_invalidates_clean_human_round():
    parsed = {
        "players": [_human() for _ in range(6)],
        "bot_player_count": 0,
        "human_player_count": 6,
    }
    v = derive_round_validity(parsed, "mp_sillyctf", {"mp_sillyctf"})
    assert v["is_bot_round"] is False
    assert v["is_valid"] is False


def test_orphan_r2_invalidates_and_reports_flag():
    parsed = {
        "players": [_human() for _ in range(6)],
        "bot_player_count": 0,
        "human_player_count": 6,
        "is_orphan_r2": True,
    }
    v = derive_round_validity(parsed, "te_escape2", set())
    assert v["is_orphan_r2"] is True
    assert v["is_valid"] is False


def test_clean_human_round_is_valid():
    parsed = {
        "players": [_human(name=f"p{i}", guid=f"{i:032d}") for i in range(6)],
        "bot_player_count": 0,
        "human_player_count": 6,
    }
    v = derive_round_validity(parsed, "etl_adlernest", {"mp_sillyctf"})
    assert v["is_bot_round"] is False
    assert v["is_valid"] is True
    assert v["is_orphan_r2"] is False


def test_empty_players_defaults_to_valid_nonbot():
    v = derive_round_validity({}, "supply", set())
    assert v["is_bot_round"] is False
    assert v["is_valid"] is True
