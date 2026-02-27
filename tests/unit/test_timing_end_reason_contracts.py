from __future__ import annotations

import pytest

from bot.core.round_contract import (
    derive_end_reason_display,
    derive_stopwatch_contract,
    normalize_end_reason,
)
from bot.services.webhook_round_metadata_service import WebhookRoundMetadataService
from scripts.backfill_gametimes import (
    _build_round_metadata_from_map as build_backfill_round_metadata,
)
from scripts.backfill_gametimes import (
    _normalize_lua_round_for_metadata_paths as normalize_lua_round,
)


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("", "NORMAL"),
        ("unknown", "NORMAL"),
        ("objective", "NORMAL"),
        ("time_expired", "NORMAL"),
        ("timelimit", "NORMAL"),
        ("time limit", "NORMAL"),
        ("surrender", "SURRENDER"),
        ("forfeit", "SURRENDER"),
        ("map change", "MAP_CHANGE"),
        ("mapchange", "MAP_CHANGE"),
        ("map_restart", "MAP_RESTART"),
        ("maprestart", "MAP_RESTART"),
        ("server restart", "SERVER_RESTART"),
        ("serverrestart", "SERVER_RESTART"),
        ("unexpected_value", "NORMAL"),
    ],
)
def test_end_reason_alias_contract(raw_value, expected):
    assert normalize_end_reason(raw_value) == expected


@pytest.mark.parametrize(
    ("actual_time", "expected_state"),
    [
        ("19:29", "TIME_SET"),
        ("19:30", "FULL_HOLD"),
        ("20:00", "FULL_HOLD"),
    ],
)
def test_stopwatch_contract_round1_hold_threshold_boundary(actual_time, expected_state):
    contract = derive_stopwatch_contract(
        round_number=1,
        time_limit_value="20:00",
        actual_time_value=actual_time,
        end_reason="NORMAL",
    )
    assert contract["round_stopwatch_state"] == expected_state


def test_stopwatch_contract_non_normal_end_reason_disables_stopwatch_state():
    contract = derive_stopwatch_contract(
        round_number=1,
        time_limit_value="20:00",
        actual_time_value="19:55",
        end_reason="SURRENDER",
    )
    assert contract["round_stopwatch_state"] is None
    assert contract["time_to_beat_seconds"] is None
    assert contract["next_timelimit_minutes"] is None


@pytest.mark.parametrize(
    ("raw_end_reason", "stopwatch_state", "expected_display"),
    [
        ("surrender", "FULL_HOLD", "SURRENDER_END"),
        ("map_change", "TIME_SET", "MAP_CHANGE_END"),
        ("map_restart", "FULL_HOLD", "MAP_RESTART_END"),
        ("server_restart", "TIME_SET", "SERVER_RESTART_END"),
    ],
)
def test_end_reason_display_prioritizes_terminal_end_reason(
    raw_end_reason,
    stopwatch_state,
    expected_display,
):
    assert (
        derive_end_reason_display(
            end_reason=raw_end_reason,
            round_stopwatch_state=stopwatch_state,
        )
        == expected_display
    )


@pytest.mark.parametrize(
    ("winner_raw", "defender_raw", "end_reason_raw", "expected_winner", "expected_defender", "expected_end"),
    [
        ("allies", "axis", "objective", 2, 1, "NORMAL"),
        ("9", "n/a", "mapchange", 0, 0, "MAP_CHANGE"),
        ("2", "1", "forfeit", 2, 1, "SURRENDER"),
        ("unknown", "unknown", "unexpected_value", 0, 0, "NORMAL"),
    ],
)
def test_webhook_and_backfill_metadata_normalization_parity(
    winner_raw,
    defender_raw,
    end_reason_raw,
    expected_winner,
    expected_defender,
    expected_end,
):
    metadata = {
        "map": "supply",
        "round": "0",
        "winner": winner_raw,
        "defender": defender_raw,
        "lua_endreason": end_reason_raw,
        "lua_roundstart": "1770901200",
        "lua_roundend": "1770901800",
        "lua_playtime": "600 sec",
        "lua_timelimit": "20 min",
    }

    backfill = build_backfill_round_metadata(metadata)

    svc = WebhookRoundMetadataService()
    live = svc.build_round_metadata_from_map(
        metadata,
        normalize_round_number=normalize_lua_round,
    )

    assert backfill["winner_team"] == expected_winner
    assert backfill["defender_team"] == expected_defender
    assert backfill["end_reason"] == expected_end
    assert backfill["round_number"] == 2

    assert live["winner_team"] == expected_winner
    assert live["defender_team"] == expected_defender
    assert live["end_reason"] == expected_end
    assert live["round_number"] == 2

