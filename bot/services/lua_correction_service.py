"""Opt-in atomic post-import corrections; not an import retry mechanism."""

import json
import math
import os
from collections import Counter

from bot.core.round_canonical import compute_canonical_id
from shared.runtime_events import event_stream_enabled

FIELDS = (
    "winner_team", "actual_duration_seconds", "total_pause_seconds", "pause_count",
    "end_reason", "round_start_unix", "round_end_unix", "round_canonical_id",
)


def lua_correction_events_enabled() -> bool:
    return event_stream_enabled() and os.getenv("LUA_CORRECTION_EVENTS_ENABLED", "false").strip().lower() == "true"


def _player_state(rows):
    return Counter(tuple(
        ("float", "NaN") if isinstance(value, float) and math.isnan(value) else value
        for value in row
    ) for row in rows)


async def apply_atomic_lua_correction(adapter, round_id, metadata, *, initializing_exact_start=False):
    """Return whether target was accepted; exceptions roll correction back.

    Initial import is already committed. Lua linking and durable retry are
    separate operations. Caller invokes this only when the feature is enabled.
    """
    raw_start = metadata.get("round_start_unix")
    if isinstance(raw_start, bool) or (
        isinstance(raw_start, float) and (not math.isfinite(raw_start) or not raw_start.is_integer())
    ):
        raise ValueError("Invalid Lua correction start timestamp")
    source_start = int(raw_start) if raw_start not in (None, "") else None
    source_round = None
    if source_start is not None and source_start > 0:
        raw_round = metadata.get("round_number") or metadata.get("round") or 0
        if isinstance(raw_round, bool) or (
            isinstance(raw_round, float) and (not math.isfinite(raw_round) or not raw_round.is_integer())
        ):
            raise ValueError("Invalid Lua correction round number")
        source_round = int(raw_round)
    duration = metadata.get("actual_duration_seconds")
    if duration is not None and (
        isinstance(duration, bool) or not isinstance(duration, (int, float))
        or not math.isfinite(duration) or duration < 0
        or (isinstance(duration, float) and not duration.is_integer())
    ):
        raise ValueError("Invalid Lua correction duration")
    if duration is not None:
        duration = int(duration)
    async with adapter.transaction() as conn:
        before = await conn.fetchrow(
            "SELECT id, map_name, round_number, gaming_session_id, "
            + ", ".join(FIELDS) + " FROM rounds WHERE id=$1 FOR UPDATE", round_id,
        )
        if before is None or before["round_number"] not in (1, 2):
            return False
        if source_start is not None and source_start > 0:
            source_map = str(metadata.get("map_name") or metadata.get("map") or "").strip().lower()
            if (str(before["map_name"] or "").strip().lower() != source_map
                    or before["round_number"] != source_round):
                return False
            current_start = before["round_start_unix"]
            if initializing_exact_start:
                if current_start is not None and current_start > 0:
                    return False
            elif current_start != source_start:
                return False

        updates = {key: metadata[key] for key in FIELDS[1:-1] if key in metadata}
        if "actual_duration_seconds" in updates:
            updates["actual_duration_seconds"] = duration
        if "round_start_unix" in updates and source_start is not None:
            updates["round_start_unix"] = source_start
        if metadata.get("winner_team"):
            updates["winner_team"] = metadata["winner_team"]
        if not updates:
            return True
        next_start = updates.get("round_start_unix", before["round_start_unix"])
        canonical_id = compute_canonical_id(next_start, before["map_name"], before["round_number"])
        if before["round_canonical_id"] and before["round_canonical_id"] != canonical_id:
            raise ValueError("Lua correction conflicts with existing canonical identity")
        if canonical_id and not before["round_canonical_id"]:
            updates["round_canonical_id"] = canonical_id

        player_query = """
            SELECT player_guid, time_played_seconds, time_played_minutes, dpm
            FROM player_comprehensive_stats WHERE round_id=$1
        """
        players_before = _player_state(await conn.fetch(player_query + " FOR UPDATE", round_id))
        values = list(updates.values())
        assignments = ", ".join(f"{key}=${index}" for index, key in enumerate(updates, 1))
        await conn.execute(
            f"UPDATE rounds SET {assignments} WHERE id=${len(values) + 1}", *values, round_id,
        )
        if duration is not None and duration > 0:
            await conn.execute("""
                UPDATE player_comprehensive_stats
                SET time_played_seconds=$1, time_played_minutes=$1 / 60.0,
                    dpm=CASE WHEN $1 > 0 THEN (damage_given * 60.0) / $1 ELSE 0 END
                WHERE round_id=$2 AND time_played_seconds > $1 * 1.5
            """, duration, round_id)
        after = await conn.fetchrow(
            "SELECT " + ", ".join(FIELDS) + " FROM rounds WHERE id=$1", round_id,
        )
        changed_fields = [key for key in FIELDS if before[key] != after[key]]
        players_changed = players_before != _player_state(await conn.fetch(player_query, round_id))
        if changed_fields or players_changed:
            event_id = await conn.fetchval("""
                INSERT INTO runtime_events (
                    event_type, schema_version, round_id, round_number,
                    gaming_session_id, event_details
                ) VALUES ('round_lua_corrected', 1, $1, $2, $3, $4::jsonb) RETURNING id
            """, round_id, before["round_number"], before["gaming_session_id"], json.dumps({
                "source": "lua_metadata_override", "round_fields_changed": changed_fields,
                "player_timing_changed": players_changed,
            }))
            await conn.execute("SELECT pg_notify('round_events', $1)", str(event_id))
    return True
