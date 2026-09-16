"""Logical persisted endstats rows for change detection, not delivery status."""

import json
import math
import os
from collections import Counter
from contextlib import asynccontextmanager

from shared.runtime_events import event_stream_enabled


def endstats_events_enabled() -> bool:
    return event_stream_enabled() and os.getenv("ENDSTATS_EVENTS_ENABLED", "false").strip().lower() == "true"


@asynccontextmanager
async def journal_endstats_storage(conn, *, round_id: int):
    """Serialize canonical storage and journal changes, never Discord delivery.

    Must nest inside the adapter transaction, before any quality/success reads.
    Other maintenance writers are not covered by this canonical-path contract.
    """
    if not endstats_events_enabled():
        yield
        return
    if not conn.is_in_transaction():
        raise RuntimeError("Endstats events require a storage transaction")
    row = await conn.fetchrow(
        "SELECT round_number, gaming_session_id FROM rounds WHERE id=$1 FOR UPDATE",
        round_id,
    )
    if row is None:
        raise ValueError("Cannot journal endstats for a missing round")
    if row["round_number"] not in (1, 2):
        yield
        return
    before = await capture_endstats_snapshot(conn, round_id)
    yield
    after = await capture_endstats_snapshot(conn, round_id)
    if before == after:
        return
    details = json.dumps({
        "source": "canonical_endstats_storage",
        "before_awards": sum(before[0].values()), "after_awards": sum(after[0].values()),
        "before_vs_rows": sum(before[1].values()), "after_vs_rows": sum(after[1].values()),
    })
    event_id = await conn.fetchval("""
        INSERT INTO runtime_events (
            event_type, schema_version, round_id, round_number,
            gaming_session_id, event_details
        ) VALUES ('round_endstats_changed', 1, $1, $2, $3, $4::jsonb)
        RETURNING id
    """, round_id, row["round_number"], row["gaming_session_id"], details)
    await conn.execute("SELECT pg_notify('round_events', $1)", str(event_id))


def _multiset(rows):
    # PostgreSQL considers NaN equal to NaN; Python float equality does not.
    return Counter(tuple(
        ("float", "NaN") if isinstance(value, float) and math.isnan(value) else value
        for value in row
    ) for row in rows)


async def capture_endstats_snapshot(conn, round_id: int):
    """Read all logical columns, preserving multiplicity but not insertion order.

    The caller owns the transaction AND must serialize writers for this round
    before the first capture. This helper neither locks nor commits. Generated
    IDs and created_at clocks are deliberately excluded. No payload is logged.
    """
    if not conn.is_in_transaction():
        raise RuntimeError("Endstats snapshots require a storage transaction")
    awards = await conn.fetch("""
        SELECT round_id, round_date, map_name, round_number, award_name,
               player_name, player_guid, award_value, award_value_numeric
        FROM round_awards WHERE round_id = $1
    """, round_id)
    versus = await conn.fetch("""
        SELECT round_id, round_date, map_name, round_number, player_name,
               player_guid, kills, deaths, subject_name, subject_guid
        FROM round_vs_stats WHERE round_id = $1
    """, round_id)
    return _multiset(awards), _multiset(versus)
