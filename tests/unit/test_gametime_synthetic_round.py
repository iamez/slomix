from __future__ import annotations

import json
from collections import defaultdict

import pytest

from bot.ultimate_bot import UltimateETLegacyBot


class _FakeBot:
    _fields_to_metadata_map = UltimateETLegacyBot._fields_to_metadata_map
    _parse_lua_version_from_footer = UltimateETLegacyBot._parse_lua_version_from_footer
    _build_round_metadata_from_map = UltimateETLegacyBot._build_round_metadata_from_map
    _normalize_lua_round_for_metadata_paths = UltimateETLegacyBot._normalize_lua_round_for_metadata_paths
    _normalize_metadata_map_name = UltimateETLegacyBot._normalize_metadata_map_name
    _pending_metadata_key = UltimateETLegacyBot._pending_metadata_key
    _prune_pending_round_metadata = UltimateETLegacyBot._prune_pending_round_metadata
    _queue_pending_metadata = UltimateETLegacyBot._queue_pending_metadata

    def __init__(self):
        self.ssh_enabled = False
        self.stored_rounds = []
        self.stored_spawn_batches = []
        self._pending_round_metadata = defaultdict(list)
        self._pending_metadata_ttl_seconds = 3 * 3600
        self._pending_metadata_max_per_key = 8

    async def _store_lua_round_teams(self, round_metadata: dict):
        self.stored_rounds.append(round_metadata)

    async def _store_lua_spawn_stats(self, round_metadata: dict, spawn_stats: list):
        self.stored_spawn_batches.append((round_metadata, spawn_stats))

    async def _fetch_latest_stats_file(self, _round_metadata: dict, _trigger_message):
        return None


@pytest.mark.asyncio
async def test_process_gametimes_file_with_synthetic_round_payload(tmp_path):
    bot = _FakeBot()

    payload_doc = {
        "payload": {
            "embeds": [
                {
                    "fields": [
                        {"name": "map", "value": "supply"},
                        {"name": "round", "value": "2"},
                        {"name": "winner", "value": "2"},
                        {"name": "defender", "value": "1"},
                        {"name": "lua_roundstart", "value": "1770843050"},
                        {"name": "lua_roundend", "value": "1770843722"},
                        {"name": "lua_playtime", "value": "579 sec"},
                        {"name": "lua_timelimit", "value": "12 min"},
                        {"name": "lua_pauses", "value": "1 (12 sec)"},
                        {"name": "axis_json", "value": '[{"guid":"A1","name":"AxisOne"}]'},
                        {"name": "allies_json", "value": '[{"guid":"B1","name":"AlliesOne"}]'},
                        {"name": "lua_axisscore", "value": "0"},
                        {"name": "lua_alliesscore", "value": "1"},
                    ],
                    "footer": {"text": "stats_discord_webhook v1.6.0"},
                }
            ]
        },
        "meta": {
            "map": "supply",
            "round": 2,
            "round_end_unix": 1770843722,
            "spawn_stats": json.dumps(
                [
                    {
                        "guid": "A1",
                        "name": "AxisOne",
                        "spawns": 8,
                        "deaths": 7,
                        "dead_seconds": 90,
                        "avg_respawn": 12,
                        "max_respawn": 20,
                    }
                ]
            ),
        },
    }

    gametime_path = tmp_path / "gametime-supply-R2-1770843722.json"
    gametime_path.write_text(json.dumps(payload_doc), encoding="utf-8")

    success = await UltimateETLegacyBot._process_gametimes_file(
        bot,
        str(gametime_path),
        gametime_path.name,
    )

    assert success is True
    assert len(bot.stored_rounds) == 1
    assert bot.stored_rounds[0]["map_name"] == "supply"
    assert bot.stored_rounds[0]["round_number"] == 2
    assert bot.stored_rounds[0]["end_reason"] == "NORMAL"
    assert bot.stored_rounds[0]["score_confidence"] == "verified_header"
    assert bot.stored_rounds[0]["round_stopwatch_state"] == "TIME_SET"
    assert bot.stored_rounds[0]["lua_version"] == "1.6.0"
    assert len(bot.stored_spawn_batches) == 1
    assert bot.stored_spawn_batches[0][1][0]["guid"] == "A1"
    pending_bucket = bot._pending_round_metadata["supply_R2"]
    if len(pending_bucket) != 1:
        pytest.fail("expected one pending metadata entry for supply_R2")
    pending_entry = pending_bucket[0]
    if pending_entry.get("source") != "gametime":
        pytest.fail("expected gametime source for queued metadata")
    if (pending_entry.get("metadata") or {}).get("round_end_unix") != 1770843722:
        pytest.fail("expected queued metadata round_end_unix to match payload")
