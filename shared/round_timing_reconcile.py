"""R02a: bounded timing fill and journal in one caller-visible transaction.

Only R1/R2 with NULL duration and exactly one usable Lua source qualify.
This is not round finalization or a journal of all other metadata writers.
"""

import json
import os

from shared.runtime_events import event_stream_enabled


def timing_events_enabled() -> bool:
    return event_stream_enabled() and os.getenv("ROUND_TIMING_EVENTS_ENABLED", "false").strip().lower() == "true"


async def reconcile_missing_round_timing(adapter, *, enabled: bool) -> int:
    """Commit at most 100 fills; any event/NOTIFY/commit failure propagates.

    The next existing poll can retry rolled-back NULL durations. Concurrent
    calls skip locked rounds; repeat after a successful fill is a no-op.
    """
    if not enabled:
        return 0
    async with adapter.transaction() as conn:
        rows = await conn.fetch("""
            WITH candidates AS (
                SELECT r.id, lrt.id AS source_id
                FROM rounds r JOIN lua_round_teams lrt ON lrt.round_id = r.id
                WHERE r.actual_duration_seconds IS NULL
                  AND r.round_number IN (1, 2)
                  AND lrt.actual_duration_seconds IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM lua_round_teams other
                      WHERE other.round_id = r.id AND other.id <> lrt.id
                        AND other.actual_duration_seconds IS NOT NULL
                  )
                ORDER BY r.id LIMIT 100 FOR UPDATE OF r, lrt SKIP LOCKED
            )
            UPDATE rounds r SET
                actual_duration_seconds = lrt.actual_duration_seconds,
                round_start_unix = lrt.round_start_unix,
                round_end_unix = lrt.round_end_unix,
                end_reason = lrt.end_reason,
                total_pause_seconds = lrt.total_pause_seconds,
                pause_count = lrt.pause_count
            FROM candidates c JOIN lua_round_teams lrt ON lrt.id = c.source_id
            WHERE r.id = c.id AND r.actual_duration_seconds IS NULL
            RETURNING r.id, r.round_number, r.gaming_session_id, lrt.id AS source_id,
                      r.actual_duration_seconds, r.round_start_unix, r.round_end_unix,
                      r.end_reason, r.total_pause_seconds, r.pause_count
        """)
        for row in rows:
            # Only this batch: never sweep unrelated historical canonical IDs.
            await conn.execute(r"""
                UPDATE rounds SET round_canonical_id = SUBSTRING(
                    ENCODE(DIGEST(round_start_unix::text || ':' ||
                        LOWER(REGEXP_REPLACE(map_name, '\^[0-9A-Za-z]', '', 'g')) || ':' ||
                        round_number::text, 'sha256'), 'hex') FROM 1 FOR 16
                )
                WHERE id = $1 AND round_canonical_id IS NULL
                  AND round_start_unix > 0 AND map_name IS NOT NULL
            """, row["id"])
            details = {key: row[key] for key in (
                "source_id", "actual_duration_seconds", "round_start_unix",
                "round_end_unix", "end_reason", "total_pause_seconds", "pause_count",
            )}
            details["source"] = "lua_round_teams"
            event_id = await conn.fetchval("""
                INSERT INTO runtime_events (
                    event_type, schema_version, round_id, round_number,
                    gaming_session_id, event_details
                ) VALUES ('round_timing_reconciled', 1, $1, $2, $3, $4::jsonb)
                RETURNING id
            """, row["id"], row["round_number"], row["gaming_session_id"], json.dumps(details))
            await conn.execute("SELECT pg_notify('round_events', $1)", str(event_id))
    return len(rows)
