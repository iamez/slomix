from __future__ import annotations

from types import SimpleNamespace

from bot.services.webhook_round_metadata_service import WebhookRoundMetadataService


def _normalize_round_number(raw):
    try:
        val = int(raw)
    except (TypeError, ValueError):
        return 0
    return 2 if val == 0 else val


def test_fields_to_metadata_map_accepts_objects_and_dicts():
    svc = WebhookRoundMetadataService()
    fields = [
        SimpleNamespace(name="Map", value="supply"),
        {"name": "Round", "value": "1"},
        {"name": "Winner", "value": 2},
    ]
    out = svc.fields_to_metadata_map(fields)
    assert out["map"] == "supply"
    assert out["round"] == "1"
    assert out["winner"] == "2"


def test_parse_spawn_stats_from_metadata_parses_escaped_json():
    svc = WebhookRoundMetadataService()
    metadata = {
        "lua_spawnstats_json": '[{\\"guid\\":\\"abc\\",\\"spawns\\":2,\\"deaths\\":1}]'
    }
    out = svc.parse_spawn_stats_from_metadata(metadata)
    assert isinstance(out, list)
    assert out[0]["guid"] == "abc"
    assert out[0]["spawns"] == 2


def test_build_round_metadata_from_map_parses_and_normalizes_core_fields():
    svc = WebhookRoundMetadataService()
    metadata = {
        "map": "supply",
        "round": "0",
        "winner": "allies",
        "defender": "axis",
        "lua_endreason": "objective",
        "lua_roundstart": "1770901200",
        "lua_roundend": "1770901800",
        "lua_playtime": "600 sec",
        "lua_timelimit": "20 min",
        "lua_pauses": "1 (15 sec)",
        "lua_warmup": "5 sec",
        "lua_warmupstart": "1770901195",
        "lua_axisscore": "1",
        "lua_alliesscore": "2",
        "axis_json": '[{"guid":"a1","name":"AxisOne"}]',
        "allies_json": '[{"guid":"b2","name":"AlliesTwo"}]',
    }

    out = svc.build_round_metadata_from_map(
        metadata,
        footer_text="Slomix Lua Webhook v1.6.1",
        normalize_round_number=_normalize_round_number,
    )

    assert out["map_name"] == "supply"
    assert out["round_number"] == 2
    assert out["winner_team"] == 2
    assert out["defender_team"] == 1
    assert out["end_reason"] == "NORMAL"
    assert out["actual_duration_seconds"] == 600
    assert out["pause_count"] == 1
    assert out["total_pause_seconds"] == 15
    assert out["axis_players"][0]["name"] == "AxisOne"
    assert out["allies_players"][0]["name"] == "AlliesTwo"
    assert out["lua_version"] == "1.6.1"
    assert out["round_stopwatch_state"]
    assert out["end_reason_display"]


def test_build_round_metadata_from_map_handles_invalid_team_json():
    svc = WebhookRoundMetadataService()
    metadata = {
        "map": "te_escape2",
        "round": "1",
        "winner": "1",
        "defender": "2",
        "lua_playtime": "200 sec",
        "lua_timelimit": "10 min",
        "axis_json": "[invalid",
        "allies_json": "[invalid",
    }

    out = svc.build_round_metadata_from_map(
        metadata,
        normalize_round_number=_normalize_round_number,
    )

    assert out["axis_players"] == []
    assert out["allies_players"] == []
