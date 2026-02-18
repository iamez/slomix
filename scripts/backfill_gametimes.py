#!/usr/bin/env python3
"""
Backfill Lua gametimes JSON files into lua_round_teams.

Usage:
    python scripts/backfill_gametimes.py --path local_gametimes
    python scripts/backfill_gametimes.py  # uses config LOCAL_GAMETIMES_PATH
"""
import argparse
import asyncio
import json
import os
import re
from datetime import datetime

from bot.config import load_config
from bot.core.database_adapter import create_adapter
from bot.core.round_contract import normalize_end_reason, normalize_side_value
from bot.core.round_linker import resolve_round_id


def _fields_to_metadata_map(fields) -> dict:
    metadata = {}
    for field in fields or []:
        name = field.get("name") if isinstance(field, dict) else None
        value = field.get("value") if isinstance(field, dict) else None
        if not name:
            continue
        metadata[str(name).lower()] = "" if value is None else str(value)
    return metadata


def _parse_lua_version_from_footer(footer_text: str | None) -> str | None:
    if not footer_text:
        return None
    match = re.search(r"v(\d+\.\d+\.\d+)", footer_text)
    return match.group(1) if match else None


def _build_round_metadata_from_map(metadata: dict, footer_text: str | None = None) -> dict:
    raw_winner = metadata.get("winner", 0)
    raw_defender = metadata.get("defender", 0)
    raw_end_reason = metadata.get("lua_endreason", metadata.get("end reason", "unknown"))

    round_metadata = {
        "map_name": metadata.get("map", "unknown"),
        "round_number": int(metadata.get("round", 0) or 0),
        "winner_team": normalize_side_value(raw_winner, allow_unknown=True),
        "defender_team": normalize_side_value(raw_defender, allow_unknown=True),
        "end_reason": normalize_end_reason(raw_end_reason),
        "round_start_unix": int(metadata.get("lua_roundstart", metadata.get("start unix", 0)) or 0),
        "round_end_unix": int(metadata.get("lua_roundend", metadata.get("end unix", 0)) or 0),
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
    except json.JSONDecodeError:
        round_metadata["axis_players"] = []
        round_metadata["allies_players"] = []

    lua_version = _parse_lua_version_from_footer(footer_text)
    if lua_version:
        round_metadata["lua_version"] = lua_version

    return round_metadata


async def _has_round_id(db_adapter) -> bool:
    try:
        result = await db_adapter.fetch_one(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'lua_round_teams' AND column_name = 'round_id'"
        )
        return bool(result)
    except Exception:
        return False


async def _store_lua_round(db_adapter, round_metadata: dict, has_round_id: bool) -> None:
    round_end = int(round_metadata.get("round_end_unix", 0) or 0)
    map_name = round_metadata.get("map_name", "unknown")
    round_number = int(round_metadata.get("round_number", 0) or 0)
    if not round_end or not map_name or not round_number:
        return

    timestamp = datetime.fromtimestamp(round_end)
    match_id = timestamp.strftime("%Y-%m-%d-%H%M%S")

    target_dt = datetime.fromtimestamp(round_end)
    round_id = await resolve_round_id(
        db_adapter,
        map_name,
        round_number,
        target_dt=target_dt,
        window_minutes=45,
    )

    axis_players = round_metadata.get("axis_players", [])
    allies_players = round_metadata.get("allies_players", [])
    pause_events = round_metadata.get("lua_pause_events", [])
    lua_version = round_metadata.get("lua_version", "unknown")

    if has_round_id:
        query = """
            INSERT INTO lua_round_teams (
                match_id, round_number, round_id, axis_players, allies_players,
                round_start_unix, round_end_unix, actual_duration_seconds,
                total_pause_seconds, pause_count, end_reason,
                winner_team, defender_team, map_name, time_limit_minutes,
                lua_warmup_seconds, lua_warmup_start_unix,
                lua_pause_events,
                surrender_team, surrender_caller_guid, surrender_caller_name,
                axis_score, allies_score,
                lua_version
            ) VALUES (
                $1, $2, $3, $4::jsonb, $5::jsonb,
                $6, $7, $8,
                $9, $10, $11,
                $12, $13, $14, $15,
                $16, $17,
                $18::jsonb,
                $19, $20, $21,
                $22, $23,
                $24
            )
            ON CONFLICT (match_id, round_number) DO UPDATE SET
                axis_players = EXCLUDED.axis_players,
                allies_players = EXCLUDED.allies_players,
                round_id = COALESCE(EXCLUDED.round_id, lua_round_teams.round_id),
                round_start_unix = EXCLUDED.round_start_unix,
                round_end_unix = EXCLUDED.round_end_unix,
                actual_duration_seconds = EXCLUDED.actual_duration_seconds,
                total_pause_seconds = EXCLUDED.total_pause_seconds,
                pause_count = EXCLUDED.pause_count,
                end_reason = EXCLUDED.end_reason,
                winner_team = EXCLUDED.winner_team,
                defender_team = EXCLUDED.defender_team,
                map_name = EXCLUDED.map_name,
                time_limit_minutes = EXCLUDED.time_limit_minutes,
                lua_warmup_seconds = EXCLUDED.lua_warmup_seconds,
                lua_warmup_start_unix = EXCLUDED.lua_warmup_start_unix,
                lua_pause_events = EXCLUDED.lua_pause_events,
                surrender_team = EXCLUDED.surrender_team,
                surrender_caller_guid = EXCLUDED.surrender_caller_guid,
                surrender_caller_name = EXCLUDED.surrender_caller_name,
                axis_score = EXCLUDED.axis_score,
                allies_score = EXCLUDED.allies_score,
                lua_version = EXCLUDED.lua_version,
                captured_at = CURRENT_TIMESTAMP
        """
        params = (
            match_id,
            round_number,
            round_id,
            json.dumps(axis_players),
            json.dumps(allies_players),
            round_metadata.get("round_start_unix"),
            round_metadata.get("round_end_unix"),
            round_metadata.get("actual_duration_seconds"),
            round_metadata.get("total_pause_seconds", 0),
            round_metadata.get("pause_count", 0),
            round_metadata.get("end_reason"),
            round_metadata.get("winner_team"),
            round_metadata.get("defender_team"),
            map_name,
            round_metadata.get("time_limit_minutes"),
            round_metadata.get("lua_warmup_seconds", 0),
            round_metadata.get("lua_warmup_start_unix", 0),
            json.dumps(pause_events),
            round_metadata.get("surrender_team", 0),
            round_metadata.get("surrender_caller_guid", ""),
            round_metadata.get("surrender_caller_name", ""),
            round_metadata.get("axis_score", 0),
            round_metadata.get("allies_score", 0),
            lua_version,
        )
    else:
        query = """
            INSERT INTO lua_round_teams (
                match_id, round_number, axis_players, allies_players,
                round_start_unix, round_end_unix, actual_duration_seconds,
                total_pause_seconds, pause_count, end_reason,
                winner_team, defender_team, map_name, time_limit_minutes,
                lua_warmup_seconds, lua_warmup_start_unix,
                lua_pause_events,
                surrender_team, surrender_caller_guid, surrender_caller_name,
                axis_score, allies_score,
                lua_version
            ) VALUES (
                $1, $2, $3::jsonb, $4::jsonb,
                $5, $6, $7,
                $8, $9, $10,
                $11, $12, $13, $14,
                $15, $16,
                $17::jsonb,
                $18, $19, $20,
                $21, $22,
                $23
            )
            ON CONFLICT (match_id, round_number) DO UPDATE SET
                axis_players = EXCLUDED.axis_players,
                allies_players = EXCLUDED.allies_players,
                round_start_unix = EXCLUDED.round_start_unix,
                round_end_unix = EXCLUDED.round_end_unix,
                actual_duration_seconds = EXCLUDED.actual_duration_seconds,
                total_pause_seconds = EXCLUDED.total_pause_seconds,
                pause_count = EXCLUDED.pause_count,
                end_reason = EXCLUDED.end_reason,
                winner_team = EXCLUDED.winner_team,
                defender_team = EXCLUDED.defender_team,
                map_name = EXCLUDED.map_name,
                time_limit_minutes = EXCLUDED.time_limit_minutes,
                lua_warmup_seconds = EXCLUDED.lua_warmup_seconds,
                lua_warmup_start_unix = EXCLUDED.lua_warmup_start_unix,
                lua_pause_events = EXCLUDED.lua_pause_events,
                surrender_team = EXCLUDED.surrender_team,
                surrender_caller_guid = EXCLUDED.surrender_caller_guid,
                surrender_caller_name = EXCLUDED.surrender_caller_name,
                axis_score = EXCLUDED.axis_score,
                allies_score = EXCLUDED.allies_score,
                lua_version = EXCLUDED.lua_version,
                captured_at = CURRENT_TIMESTAMP
        """
        params = (
            match_id,
            round_number,
            json.dumps(axis_players),
            json.dumps(allies_players),
            round_metadata.get("round_start_unix"),
            round_metadata.get("round_end_unix"),
            round_metadata.get("actual_duration_seconds"),
            round_metadata.get("total_pause_seconds", 0),
            round_metadata.get("pause_count", 0),
            round_metadata.get("end_reason"),
            round_metadata.get("winner_team"),
            round_metadata.get("defender_team"),
            map_name,
            round_metadata.get("time_limit_minutes"),
            round_metadata.get("lua_warmup_seconds", 0),
            round_metadata.get("lua_warmup_start_unix", 0),
            json.dumps(pause_events),
            round_metadata.get("surrender_team", 0),
            round_metadata.get("surrender_caller_guid", ""),
            round_metadata.get("surrender_caller_name", ""),
            round_metadata.get("axis_score", 0),
            round_metadata.get("allies_score", 0),
            lua_version,
        )

    await db_adapter.execute(query, params)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", default=None, help="Local gametimes directory")
    args = parser.parse_args()

    config = load_config()
    local_dir = args.path or config.gametimes_local_path or "local_gametimes"

    if not os.path.isdir(local_dir):
        print(f"[backfill] Directory not found: {local_dir}")
        return

    adapter_kwargs = config.get_database_adapter_kwargs()
    db_adapter = create_adapter(**adapter_kwargs)
    await db_adapter.connect()
    has_round_id = await _has_round_id(db_adapter)

    files = sorted(
        f for f in os.listdir(local_dir)
        if f.startswith("gametime-") and f.endswith(".json")
    )

    if not files:
        print(f"[backfill] No gametime files in {local_dir}")
        await db_adapter.close()
        return

    processed = 0
    skipped = 0
    for filename in files:
        path = os.path.join(local_dir, filename)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                gametime_data = json.load(handle)
        except Exception as e:
            print(f"[backfill] Failed to read {filename}: {e}")
            skipped += 1
            continue

        payload = gametime_data.get("payload")
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError as e:
                print(f"[backfill] Invalid payload in {filename}: {e}")
                skipped += 1
                continue

        if not isinstance(payload, dict):
            print(f"[backfill] Missing payload in {filename}")
            skipped += 1
            continue

        embeds = payload.get("embeds") or []
        if not embeds:
            print(f"[backfill] No embeds in {filename}")
            skipped += 1
            continue

        embed = embeds[0]
        metadata = _fields_to_metadata_map(embed.get("fields", []))
        footer_text = None
        if isinstance(embed.get("footer"), dict):
            footer_text = embed["footer"].get("text")

        round_metadata = _build_round_metadata_from_map(metadata, footer_text)

        meta = gametime_data.get("meta") or {}
        if round_metadata.get("map_name") == "unknown" and meta.get("map"):
            round_metadata["map_name"] = meta.get("map")
        if round_metadata.get("round_number", 0) == 0 and meta.get("round"):
            round_metadata["round_number"] = int(meta.get("round"))
        if round_metadata.get("round_end_unix", 0) == 0 and meta.get("round_end_unix"):
            round_metadata["round_end_unix"] = int(meta.get("round_end_unix"))

        if round_metadata.get("map_name") == "unknown" or round_metadata.get("round_number", 0) == 0:
            print(f"[backfill] Missing map/round metadata in {filename}")
            skipped += 1
            continue

        if not round_metadata.get("round_end_unix"):
            print(f"[backfill] Missing round_end_unix in {filename}")
            skipped += 1
            continue

        await _store_lua_round(db_adapter, round_metadata, has_round_id)
        processed += 1

    await db_adapter.close()
    print(f"[backfill] Done. processed={processed} skipped={skipped}")


if __name__ == "__main__":
    asyncio.run(main())
