# Shim: backfill_gametimes was consolidated into tools/slomix_backfill.py.
# This module re-exports existing functions from the archived original and
# provides new helper functions that were specced in unit tests but not yet
# implemented in the archived version.

from datetime import datetime

from scripts.archive.backfill_gametimes import (
    _build_round_metadata_from_map as _build_round_metadata_from_map_archive,
    _fields_to_metadata_map,
    _has_round_id,
    _parse_lua_version_from_footer,
)
from bot.core.round_linker import resolve_round_id_with_reason  # noqa: F401 (monkeypatched in tests)

def _build_round_metadata_from_map(metadata: dict, footer_text=None) -> dict:
    """Wrapper around the archive version that normalizes round 0 → 2."""
    result = _build_round_metadata_from_map_archive(metadata, footer_text)
    result["round_number"] = _normalize_lua_round_for_metadata_paths(result.get("round_number", 0))
    return result


__all__ = [
    "_build_round_metadata_from_map",
    "_fields_to_metadata_map",
    "_has_round_id",
    "_normalize_lua_round_for_metadata_paths",
    "_parse_lua_version_from_footer",
    "_store_lua_round",
    "resolve_round_id_with_reason",
]


def _normalize_lua_round_for_metadata_paths(val) -> int:
    """Normalize a Lua round number to a metadata path round number.

    Lua uses 0 to mean the second half of a match (round 2 in the schema).
    Negative values indicate invalid/unknown and are normalized to 0.
    """
    try:
        n = int(val)
    except (TypeError, ValueError):
        return 0
    if n < 0:
        return 0
    if n == 0:
        return 2
    return n


async def _store_lua_round(
    db_adapter,
    round_metadata: dict,
    has_round_id: bool,
    dry_run: bool = False,
    window_minutes: int = 45,
) -> dict:
    """Store a Lua round record into lua_round_teams.

    Args:
        db_adapter: Async database adapter.
        round_metadata: Parsed round metadata dict.
        has_round_id: Whether the lua_round_teams table has a round_id column.
        dry_run: If True, resolve the round ID but do not write to the database.
        window_minutes: Matching window (minutes) passed to resolve_round_id_with_reason.

    Returns:
        dict with keys: status ("stored" | "dry_run" | "skipped"),
                        round_id (int | None),
                        reason_code (str | None).
    """
    import json

    round_end = int(round_metadata.get("round_end_unix", 0) or 0)
    map_name = round_metadata.get("map_name", "unknown")
    round_number = int(round_metadata.get("round_number", 0) or 0)

    if not round_end or not map_name or not round_number:
        return {"status": "skipped", "round_id": None, "reason_code": "missing_required_fields"}

    target_dt = datetime.fromtimestamp(round_end)

    round_id, reason = await resolve_round_id_with_reason(
        db_adapter,
        map_name,
        round_number,
        target_dt=target_dt,
        window_minutes=window_minutes,
    )

    reason_code = reason.get("reason_code") if reason else None

    if dry_run:
        return {"status": "dry_run", "round_id": round_id, "reason_code": reason_code}

    # Build INSERT params (mirrors archive version)
    timestamp = datetime.fromtimestamp(round_end)
    match_id = timestamp.strftime("%Y-%m-%d-%H%M%S")
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
                $6, $7, $8, $9, $10, $11,
                $12, $13, $14, $15, $16, $17,
                $18::jsonb,
                $19, $20, $21, $22, $23, $24
            )
            ON CONFLICT (match_id, round_number) DO UPDATE SET
                round_id = COALESCE(EXCLUDED.round_id, lua_round_teams.round_id),
                captured_at = CURRENT_TIMESTAMP
        """
        params = (
            match_id, round_number, round_id,
            json.dumps(axis_players), json.dumps(allies_players),
            round_metadata.get("round_start_unix"), round_metadata.get("round_end_unix"),
            round_metadata.get("actual_duration_seconds"),
            round_metadata.get("total_pause_seconds", 0), round_metadata.get("pause_count", 0),
            round_metadata.get("end_reason"),
            round_metadata.get("winner_team"), round_metadata.get("defender_team"),
            map_name, round_metadata.get("time_limit_minutes"),
            round_metadata.get("lua_warmup_seconds", 0), round_metadata.get("lua_warmup_start_unix", 0),
            json.dumps(pause_events),
            round_metadata.get("surrender_team", 0),
            round_metadata.get("surrender_caller_guid", ""),
            round_metadata.get("surrender_caller_name", ""),
            round_metadata.get("axis_score", 0), round_metadata.get("allies_score", 0),
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
                $5, $6, $7, $8, $9, $10,
                $11, $12, $13, $14, $15, $16,
                $17::jsonb,
                $18, $19, $20, $21, $22, $23
            )
            ON CONFLICT (match_id, round_number) DO UPDATE SET
                captured_at = CURRENT_TIMESTAMP
        """
        params = (
            match_id, round_number,
            json.dumps(axis_players), json.dumps(allies_players),
            round_metadata.get("round_start_unix"), round_metadata.get("round_end_unix"),
            round_metadata.get("actual_duration_seconds"),
            round_metadata.get("total_pause_seconds", 0), round_metadata.get("pause_count", 0),
            round_metadata.get("end_reason"),
            round_metadata.get("winner_team"), round_metadata.get("defender_team"),
            map_name, round_metadata.get("time_limit_minutes"),
            round_metadata.get("lua_warmup_seconds", 0), round_metadata.get("lua_warmup_start_unix", 0),
            json.dumps(pause_events),
            round_metadata.get("surrender_team", 0),
            round_metadata.get("surrender_caller_guid", ""),
            round_metadata.get("surrender_caller_name", ""),
            round_metadata.get("axis_score", 0), round_metadata.get("allies_score", 0),
            lua_version,
        )

    await db_adapter.execute(query, params)
    return {"status": "stored", "round_id": round_id, "reason_code": reason_code}
