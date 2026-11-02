"""Bot-independent document decoding, legacy parity and honest presence."""

import copy
import json
import subprocess
import sys

import pytest

from bot.services.webhook_round_metadata_service import (
    WebhookRoundMetadataService,
    normalize_lua_round_number,
)


def document():
    return {"payload": {"embeds": [{"fields": [
        {"name": key, "value": value} for key, value in {
            "Map": "supply", "Round": "1", "Lua_RoundStart": "1700000000",
            "Lua_RoundEnd": "1700000610", "Lua_Playtime": "600 sec",
            "Lua_Pauses": "1 (10 sec)", "Lua_EndReason": "normal",
        }.items()
    ], "footer": {"text": "Slomix Lua Webhook v1.7.0"}}]},
        "meta": {"map": "supply", "round": 1, "round_end_unix": 1700000610,
                 "spawn_stats": [{"guid": "fixture", "spawns": 2}]}}


@pytest.mark.parametrize("encoded", [False, True])
def test_decode_without_bot_preserves_measurements_and_does_not_mutate_input(encoded):
    service = WebhookRoundMetadataService()
    source = document()
    if encoded:
        source["payload"] = json.dumps(source["payload"])
        source["meta"]["spawn_stats"] = json.dumps(source["meta"]["spawn_stats"])
    before = copy.deepcopy(source)
    fields, metadata, spawns = service.decode_gametime_document(source)
    assert source == before
    assert fields["map"] == metadata["map_name"] == "supply"
    assert metadata["round_number"] == 1
    assert metadata["round_start_unix"] == 1700000000
    assert metadata["actual_duration_seconds"] == 600
    assert metadata["total_pause_seconds"] == 10
    assert metadata["lua_version"] == "1.7.0"
    assert {"actual_duration_seconds", "total_pause_seconds", "round_end_unix"} <= set(metadata["_correction_present_fields"])
    assert spawns == [{"guid": "fixture", "spawns": 2}]


def test_meta_fallback_retains_legacy_missing_measurement_semantics():
    source = {"payload": {"embeds": [{"fields": []}]}, "meta": {
        "map": "supply", "round": 0, "round_end_unix": 1700000610,
        "round_start_unix": 1700000000, "actual_duration_seconds": 600,
    }}
    _, metadata, spawns = WebhookRoundMetadataService().decode_gametime_document(source)
    assert metadata["map_name"] == "supply" and metadata["round_number"] == 2
    assert metadata["round_end_unix"] == 1700000610
    # Legacy display defaults are NOT authoritative measurements. No new
    # meta-based start/duration fallback is introduced by this extraction.
    assert metadata["round_start_unix"] == metadata["actual_duration_seconds"] == 0
    assert metadata["_correction_present_fields"] == ["round_end_unix"]
    assert spawns == []


def test_embed_precedence_is_compatibility_not_conflict_resolution():
    source = document()
    source["meta"].update(map="oasis", round=2, round_end_unix=1800000000)
    _, metadata, _ = WebhookRoundMetadataService().decode_gametime_document(source)
    assert (metadata["map_name"], metadata["round_number"], metadata["round_end_unix"]) == ("supply", 1, 1700000610)


@pytest.mark.parametrize("source", [
    None, [], {}, {"payload": "not-json"}, {"payload": []},
    {"payload": {"embeds": []}}, {"payload": {"embeds": {}}},
    {"payload": {"embeds": [None]}},
    {"payload": {"embeds": [{"fields": {}}]}},
    {"payload": {"embeds": [{"fields": [1]}]}},
    {"payload": {"embeds": [{"footer": {"text": 1}}]}},
])
def test_bad_shapes_reject_without_side_effects(source):
    with pytest.raises(ValueError):
        WebhookRoundMetadataService().decode_gametime_document(source)


def test_invalid_field_container_cannot_be_hidden_by_valid_meta_fallback():
    source = document()
    source["payload"]["embeds"][0]["fields"] = {"map": "supply", "round": "1"}
    with pytest.raises(ValueError, match="fields must be a list"):
        WebhookRoundMetadataService().decode_gametime_document(source)


@pytest.mark.parametrize("meta", [[], "bad", 1])
def test_invalid_meta_container_is_rejected_even_with_valid_embed(meta):
    source = document()
    source["meta"] = meta
    with pytest.raises(ValueError, match="meta must be an object"):
        WebhookRoundMetadataService().decode_gametime_document(source)


@pytest.mark.parametrize("spawn", [None, {}, "invalid", "null", "{}"])
def test_unusable_spawn_rows_retain_empty_legacy_fallback(spawn):
    source = document()
    source["meta"]["spawn_stats"] = spawn
    assert WebhookRoundMetadataService().decode_gametime_document(source)[2] == []


@pytest.mark.parametrize("raw,expected", [(None, 0), ("", 0), (0, 2), ("+0", 2),
    ("-0", 2), ("00", 0), (1, 1), (2, 2), (-1, 0), (True, 0), ("invalid", 0)])
def test_shared_round_normalizer_preserves_legacy(raw, expected):
    assert normalize_lua_round_number(raw) == expected


def test_decoder_import_and_execution_do_not_load_discord_or_bot_runtime():
    code = """
import json, sys
from bot.services.webhook_round_metadata_service import WebhookRoundMetadataService
source = json.load(sys.stdin)
_, metadata, _ = WebhookRoundMetadataService().decode_gametime_document(source)
assert 'discord' not in sys.modules and 'bot.ultimate_bot' not in sys.modules
print(json.dumps({key: metadata[key] for key in ('map_name', 'round_number', 'actual_duration_seconds')}))
"""
    result = subprocess.run([sys.executable, "-c", code], input=json.dumps(document()),
                            text=True, capture_output=True, timeout=10, check=True)
    assert json.loads(result.stdout) == {"map_name": "supply", "round_number": 1,
                                      "actual_duration_seconds": 600}
    print("DECODER PROCESS PROOF: source -> supply/R1/600s; no Discord or bot runtime imported")
