"""Edge-case tests for WebhookRoundMetadataService.

The existing suite (test_webhook_round_metadata_service.py) covers
happy paths and one invalid-JSON case. This module fills in the
common production-traffic edge cases that have caused real incidents:

- Missing/empty fields lists (Discord embed without expected fields)
- Malformed numeric fields ("not a number" in lua_playtime, etc.)
- Missing lua_pauses_json or trailing-paren format quirks
- Side-value diagnostics when winner/defender are missing
- parse_lua_version_from_footer with various footer shapes
- Spawn stats key fallback (lua_spawnstats_json → lua_spawn_stats_json
  → spawn_stats)
- Surrender field defaults

These are the parsers that turn raw Discord webhook fields into the
metadata dict every downstream consumer trusts. A silent "0 instead
of N" regression here corrupts every round.
"""
from __future__ import annotations

import pytest

from bot.services.webhook_round_metadata_service import WebhookRoundMetadataService


@pytest.fixture
def svc():
    return WebhookRoundMetadataService()


# ---------------------------------------------------------------------------
# fields_to_metadata_map
# ---------------------------------------------------------------------------


def test_fields_map_handles_none_input(svc):
    """Some Discord embeds arrive without `.fields` populated."""
    assert svc.fields_to_metadata_map(None) == {}


def test_fields_map_handles_empty_list(svc):
    assert svc.fields_to_metadata_map([]) == {}


def test_fields_map_skips_field_with_no_name(svc):
    """A nameless dict/SimpleNamespace must be silently skipped, not crash."""
    out = svc.fields_to_metadata_map([
        {"name": None, "value": "ignored"},
        {"name": "", "value": "also_ignored"},
        {"name": "Map", "value": "supply"},
    ])
    assert out == {"map": "supply"}


def test_fields_map_lowercases_field_names(svc):
    """Production downstream keys all lowercase; pin that contract."""
    out = svc.fields_to_metadata_map([
        {"name": "MAP", "value": "supply"},
        {"name": "Lua_RoundStart", "value": "1700"},
    ])
    assert "map" in out
    assert "lua_roundstart" in out
    assert "MAP" not in out


def test_fields_map_normalises_none_value_to_empty_string(svc):
    """An expected-but-empty field must NOT be missing from the dict —
    downstream `metadata.get("foo", default)` would silently take the
    default and bury the actual signal."""
    out = svc.fields_to_metadata_map([{"name": "Map", "value": None}])
    assert out == {"map": ""}


def test_fields_map_coerces_non_string_value_to_str(svc):
    out = svc.fields_to_metadata_map([{"name": "Round", "value": 1}])
    assert out["round"] == "1"


# ---------------------------------------------------------------------------
# parse_spawn_stats_from_metadata
# ---------------------------------------------------------------------------


def test_spawn_stats_returns_empty_when_no_key(svc):
    assert svc.parse_spawn_stats_from_metadata({}) == []


def test_spawn_stats_returns_empty_for_blank_value(svc):
    assert svc.parse_spawn_stats_from_metadata({"lua_spawnstats_json": ""}) == []


def test_spawn_stats_falls_back_to_alternate_keys(svc):
    """Lua versions have shipped 3 different keys for this payload —
    the parser must accept all three."""
    payload = '[{"guid":"x","spawns":1}]'
    a = svc.parse_spawn_stats_from_metadata({"lua_spawnstats_json": payload})
    b = svc.parse_spawn_stats_from_metadata({"lua_spawn_stats_json": payload})
    c = svc.parse_spawn_stats_from_metadata({"spawn_stats": payload})
    assert a == b == c
    assert a[0]["guid"] == "x"


def test_spawn_stats_handles_malformed_json(svc):
    """Malformed payload → return empty list (no crash, no exception)."""
    assert svc.parse_spawn_stats_from_metadata(
        {"lua_spawnstats_json": "[ truncated"},
    ) == []


# ---------------------------------------------------------------------------
# parse_lua_version_from_footer
# ---------------------------------------------------------------------------


def test_lua_version_returns_none_when_footer_is_none(svc):
    assert svc.parse_lua_version_from_footer(None) is None


def test_lua_version_returns_none_when_footer_empty(svc):
    assert svc.parse_lua_version_from_footer("") is None


def test_lua_version_extracts_three_part_version(svc):
    assert svc.parse_lua_version_from_footer("Slomix Lua Webhook v1.6.4") == "1.6.4"


def test_lua_version_extracts_when_embedded(svc):
    """Version may appear anywhere in the footer (newer versions add suffix)."""
    assert svc.parse_lua_version_from_footer("[v1.7.0] Slomix Lua") == "1.7.0"


def test_lua_version_returns_none_when_no_version_string(svc):
    """A footer without a version pattern is acceptable input — must return None,
    not crash."""
    assert svc.parse_lua_version_from_footer("Slomix Lua Webhook") is None


def test_lua_version_ignores_two_part_version(svc):
    """Regex requires three numeric parts (semver). 'v1.6' does not match."""
    assert svc.parse_lua_version_from_footer("Slomix Lua v1.6") is None


# ---------------------------------------------------------------------------
# build_round_metadata_from_map: numeric parsing edge cases
# ---------------------------------------------------------------------------


def test_build_metadata_defaults_all_zero_for_empty_map(svc):
    out = svc.build_round_metadata_from_map({})
    assert out["round_start_unix"] == 0
    assert out["round_end_unix"] == 0
    assert out["lua_playtime_seconds"] == 0
    assert out["lua_timelimit_minutes"] == 0
    assert out["lua_pause_count"] == 0
    assert out["lua_pause_seconds"] == 0
    assert out["lua_warmup_seconds"] == 0
    assert out["surrender_team"] == 0
    assert out["axis_score"] == 0
    assert out["allies_score"] == 0


def test_build_metadata_handles_malformed_playtime(svc):
    """If lua_playtime is garbage ('foo bar'), default to 0 — must not raise."""
    out = svc.build_round_metadata_from_map({"lua_playtime": "garbage"})
    assert out["lua_playtime_seconds"] == 0
    assert out["actual_duration_seconds"] == 0


def test_build_metadata_handles_pauses_without_paren(svc):
    """Older Lua versions emit '0' alone instead of '0 (0 sec)'.
    Parser must split safely and default the seconds half to 0."""
    out = svc.build_round_metadata_from_map({"lua_pauses": "0"})
    assert out["lua_pause_count"] == 0
    assert out["lua_pause_seconds"] == 0


def test_build_metadata_parses_pauses_full_format(svc):
    out = svc.build_round_metadata_from_map({"lua_pauses": "3 (45 sec)"})
    assert out["lua_pause_count"] == 3
    assert out["lua_pause_seconds"] == 45


def test_build_metadata_handles_garbage_pauses(svc):
    out = svc.build_round_metadata_from_map({"lua_pauses": "totally broken"})
    assert out["lua_pause_count"] == 0
    assert out["lua_pause_seconds"] == 0


def test_build_metadata_handles_malformed_timelimit(svc):
    out = svc.build_round_metadata_from_map({"lua_timelimit": "??? min"})
    assert out["lua_timelimit_minutes"] == 0


def test_build_metadata_handles_malformed_warmup(svc):
    out = svc.build_round_metadata_from_map({"lua_warmup": "???"})
    assert out["lua_warmup_seconds"] == 0


def test_build_metadata_warmup_end_falls_back_to_roundstart(svc):
    """If lua_warmupend is missing, the parser falls back to lua_roundstart
    so warmup-end-vs-round-start invariant downstream stays valid."""
    out = svc.build_round_metadata_from_map({"lua_roundstart": "1700"})
    assert out["lua_warmup_end_unix"] == 1700


# ---------------------------------------------------------------------------
# build_round_metadata: side / endreason / diagnostics
# ---------------------------------------------------------------------------


def test_build_metadata_records_diagnostics_for_missing_winner(svc):
    """winner=missing → diagnostics surface 'winner_missing_or_invalid'."""
    out = svc.build_round_metadata_from_map({"defender": "axis"})
    reasons = out["side_parse_diagnostics"]["reasons"]
    assert "winner_missing_or_invalid" in reasons


def test_build_metadata_records_diagnostics_for_missing_defender(svc):
    out = svc.build_round_metadata_from_map({"winner": "axis"})
    reasons = out["side_parse_diagnostics"]["reasons"]
    assert "defender_missing_or_invalid" in reasons


def test_build_metadata_no_diagnostics_when_both_sides_valid(svc):
    out = svc.build_round_metadata_from_map(
        {"winner": "axis", "defender": "allies"},
    )
    assert out["side_parse_diagnostics"]["reasons"] == []


# ---------------------------------------------------------------------------
# build_round_metadata: pause_events JSON
# ---------------------------------------------------------------------------


def test_build_metadata_default_empty_pause_events(svc):
    out = svc.build_round_metadata_from_map({})
    assert out["lua_pause_events"] == []


def test_build_metadata_parses_pause_events_json(svc):
    out = svc.build_round_metadata_from_map(
        {"lua_pauses_json": '[{"start":100,"duration":30}]'},
    )
    assert out["lua_pause_events"] == [{"start": 100, "duration": 30}]


def test_build_metadata_handles_malformed_pause_events_json(svc):
    """Malformed JSON → empty list (parser swallows JSONDecodeError)."""
    out = svc.build_round_metadata_from_map({"lua_pauses_json": "[ truncated"})
    assert out["lua_pause_events"] == []


# ---------------------------------------------------------------------------
# build_round_metadata: surrender fields
# ---------------------------------------------------------------------------


def test_build_metadata_default_surrender_fields(svc):
    out = svc.build_round_metadata_from_map({})
    assert out["surrender_team"] == 0
    assert out["surrender_caller_guid"] == ""
    assert out["surrender_caller_name"] == ""


def test_build_metadata_parses_surrender_fields(svc):
    out = svc.build_round_metadata_from_map({
        "lua_surrenderteam": "1",
        "lua_surrendercaller": "abc-guid",
        "lua_surrendercallername": "PlayerOne",
    })
    assert out["surrender_team"] == 1
    assert out["surrender_caller_guid"] == "abc-guid"
    assert out["surrender_caller_name"] == "PlayerOne"


# ---------------------------------------------------------------------------
# build_round_metadata: warn callback for invalid team JSON
# ---------------------------------------------------------------------------


def test_build_metadata_invokes_warn_callback_on_team_json_error(svc):
    warns: list[str] = []
    svc.build_round_metadata_from_map(
        {"axis_json": "[broken"},
        warn=warns.append,
    )
    assert any("Failed to parse team JSON" in w for w in warns)


def test_build_metadata_no_warn_when_team_json_is_valid(svc):
    warns: list[str] = []
    svc.build_round_metadata_from_map(
        {"axis_json": "[]", "allies_json": "[]"},
        warn=warns.append,
    )
    assert warns == []
