from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable

logger = logging.getLogger('bot.services.webhook_round_metadata')

from bot.core.round_contract import (
    derive_end_reason_display,
    derive_stopwatch_contract,
    normalize_end_reason,
    normalize_side_value,
    score_confidence_state,
)


class WebhookRoundMetadataService:
    """Parse and normalize STATS_READY / gametime webhook metadata payloads."""

    def fields_to_metadata_map(self, fields: Any) -> dict[str, str]:
        metadata: dict[str, str] = {}
        for field in fields or []:
            name = getattr(field, "name", None)
            value = getattr(field, "value", None)
            if name is None and isinstance(field, dict):
                name = field.get("name")
                value = field.get("value")
            if not name:
                continue
            metadata[str(name).lower()] = "" if value is None else str(value)
        return metadata

    def parse_spawn_stats_from_metadata(self, metadata: dict[str, Any]) -> list[Any]:
        raw = (
            metadata.get("lua_spawnstats_json")
            or metadata.get("lua_spawn_stats_json")
            or metadata.get("spawn_stats")
        )
        if not raw:
            return []
        try:
            text = str(raw).replace('\\"', '"')
            return json.loads(text) if text else []
        except json.JSONDecodeError:
            logger.warning("Failed to parse spawn stats JSON (size=%d)", len(str(raw)))
            return []

    def parse_lua_version_from_footer(self, footer_text: str | None) -> str | None:
        if not footer_text:
            return None
        match = re.search(r"v(\d+\.\d+\.\d+)", footer_text)
        return match.group(1) if match else None

    def build_round_metadata_from_map(
        self,
        metadata: dict[str, Any],
        *,
        footer_text: str | None = None,
        normalize_round_number: Callable[[Any], int] | None = None,
        warn: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        winner_raw = metadata.get("winner", 0)
        defender_raw = metadata.get("defender", 0)
        winner_team = normalize_side_value(winner_raw, allow_unknown=True)
        defender_team = normalize_side_value(defender_raw, allow_unknown=True)
        side_reasons: list[str] = []
        if winner_team == 0:
            side_reasons.append("winner_missing_or_invalid")
        if defender_team == 0:
            side_reasons.append("defender_missing_or_invalid")

        end_reason_raw = metadata.get("lua_endreason", metadata.get("end reason", "unknown"))
        normalized_end_reason = normalize_end_reason(end_reason_raw)
        raw_round_number = metadata.get("round")
        if normalize_round_number:
            normalized_round_number = normalize_round_number(raw_round_number)
        else:
            try:
                normalized_round_number = int(raw_round_number or 0)
            except (TypeError, ValueError):
                normalized_round_number = 0

        round_metadata: dict[str, Any] = {
            "map_name": metadata.get("map", "unknown"),
            "round_number": normalized_round_number,
            "lua_round_number_raw": raw_round_number,
            "winner_team": winner_team,
            "defender_team": defender_team,
            "end_reason": normalized_end_reason,
            "end_reason_raw": end_reason_raw,
            "round_start_unix": int(metadata.get("lua_roundstart", metadata.get("start unix", 0)) or 0),
            "round_end_unix": int(metadata.get("lua_roundend", metadata.get("end unix", 0)) or 0),
            "side_parse_diagnostics": {
                "winner_team_raw": winner_raw,
                "defender_team_raw": defender_raw,
                "reasons": side_reasons,
            },
        }

        duration_str = metadata.get("lua_playtime", metadata.get("duration", "0 sec"))
        try:
            round_metadata["lua_playtime_seconds"] = int(str(duration_str).split()[0])
            round_metadata["actual_duration_seconds"] = round_metadata["lua_playtime_seconds"]
        except (ValueError, IndexError):
            round_metadata["lua_playtime_seconds"] = 0
            round_metadata["actual_duration_seconds"] = 0

        time_limit_str = metadata.get("lua_timelimit", metadata.get("time limit", "0 min"))
        try:
            round_metadata["lua_timelimit_minutes"] = int(str(time_limit_str).split()[0])
            round_metadata["time_limit_minutes"] = round_metadata["lua_timelimit_minutes"]
        except (ValueError, IndexError):
            round_metadata["lua_timelimit_minutes"] = 0
            round_metadata["time_limit_minutes"] = 0

        pauses_str = metadata.get("lua_pauses", metadata.get("pauses", "0 (0 sec)"))
        try:
            parts = str(pauses_str).split("(")
            round_metadata["lua_pause_count"] = int(parts[0].strip())
            round_metadata["pause_count"] = round_metadata["lua_pause_count"]
            if len(parts) > 1:
                round_metadata["lua_pause_seconds"] = int(parts[1].rstrip(" sec)"))
            else:
                round_metadata["lua_pause_seconds"] = 0
            round_metadata["total_pause_seconds"] = round_metadata["lua_pause_seconds"]
        except (ValueError, IndexError):
            round_metadata["lua_pause_count"] = 0
            round_metadata["lua_pause_seconds"] = 0
            round_metadata["pause_count"] = 0
            round_metadata["total_pause_seconds"] = 0

        warmup_str = metadata.get("lua_warmup", "0 sec")
        try:
            round_metadata["lua_warmup_seconds"] = int(str(warmup_str).split()[0])
        except (ValueError, IndexError):
            round_metadata["lua_warmup_seconds"] = 0

        round_metadata["lua_warmup_start_unix"] = int(metadata.get("lua_warmupstart", 0) or 0)
        round_metadata["lua_warmup_end_unix"] = int(
            metadata.get("lua_warmupend", metadata.get("lua_roundstart", 0)) or 0
        )

        pause_events_raw = metadata.get("lua_pauses_json", "[]")
        try:
            pause_events_json = str(pause_events_raw).replace('\\"', '"')
            round_metadata["lua_pause_events"] = (
                json.loads(pause_events_json) if pause_events_json != "[]" else []
            )
        except json.JSONDecodeError:
            round_metadata["lua_pause_events"] = []

        round_metadata["surrender_team"] = int(metadata.get("lua_surrenderteam", 0) or 0)
        round_metadata["surrender_caller_guid"] = metadata.get("lua_surrendercaller", "")
        round_metadata["surrender_caller_name"] = metadata.get("lua_surrendercallername", "")

        round_metadata["axis_score"] = int(metadata.get("lua_axisscore", 0) or 0)
        round_metadata["allies_score"] = int(metadata.get("lua_alliesscore", 0) or 0)

        axis_json_raw = metadata.get("axis_json", "[]")
        allies_json_raw = metadata.get("allies_json", "[]")

        try:
            axis_json = str(axis_json_raw).replace('\\"', '"')
            allies_json = str(allies_json_raw).replace('\\"', '"')
            round_metadata["axis_players"] = (
                json.loads(axis_json) if axis_json != "[]" else []
            )
            round_metadata["allies_players"] = (
                json.loads(allies_json) if allies_json != "[]" else []
            )
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse team JSON: %s", exc)
            if warn:
                warn(f"Failed to parse team JSON: {exc}")
            round_metadata["axis_players"] = []
            round_metadata["allies_players"] = []

        lua_version = self.parse_lua_version_from_footer(footer_text)
        if lua_version:
            round_metadata["lua_version"] = lua_version

        stopwatch_contract = derive_stopwatch_contract(
            round_metadata.get("round_number", 0),
            int(round_metadata.get("time_limit_minutes", 0) or 0) * 60,
            round_metadata.get("actual_duration_seconds", 0),
            round_metadata.get("end_reason"),
        )
        round_metadata["round_stopwatch_state"] = stopwatch_contract["round_stopwatch_state"]
        round_metadata["time_to_beat_seconds"] = stopwatch_contract["time_to_beat_seconds"]
        round_metadata["next_timelimit_minutes"] = stopwatch_contract["next_timelimit_minutes"]
        round_metadata["end_reason_display"] = derive_end_reason_display(
            round_metadata.get("end_reason"),
            round_stopwatch_state=round_metadata.get("round_stopwatch_state"),
        )
        round_metadata["score_confidence"] = score_confidence_state(
            round_metadata.get("defender_team"),
            round_metadata.get("winner_team"),
            reasons=side_reasons,
            fallback_used=False,
        )

        return round_metadata
