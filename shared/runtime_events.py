"""Initial import journal; NOTIFY is a wake-up, never the durable source.

No consumers or update events yet. Sequence IDs do not imply commit order.
The caller owns the transaction and must propagate failures to roll it back.
"""

import os


def event_stream_enabled() -> bool:
    """Explicit opt-in, read after the application's environment loading."""
    return os.getenv("EVENT_STREAM_ENABLED", "false").strip().lower() == "true"


async def emit_round_stats_imported(
    conn, *, enabled: bool, round_id: int, source_filename: str,
    source_payload_sha256: str | None, validation_passed: bool,
) -> int | None:
    """Write at most one initial event per R1/R2, on the import connection.

    Disabled mode makes no database calls and needs no journal migration.
    Validation warnings retain the importer's existing save-with-warning
    semantics. A successful import is not proof of complete/final round data.
    """
    if not enabled:
        return None
    if not conn.is_in_transaction():
        raise RuntimeError("Runtime events require the canonical import transaction")
    row = await conn.fetchrow(
        "SELECT round_number, gaming_session_id FROM rounds WHERE id = $1",
        round_id,
    )
    if row is None:
        raise ValueError("Cannot journal a missing round")
    if row["round_number"] not in (1, 2):
        return None
    event_id = await conn.fetchval(
        """
        INSERT INTO runtime_events (
            event_type, schema_version, round_id, round_number,
            gaming_session_id, source_filename, source_payload_sha256,
            validation_passed
        ) VALUES ('round_stats_imported', 1, $1, $2, $3, $4, $5, $6)
        ON CONFLICT (round_id, event_type) DO NOTHING
        RETURNING id
        """,
        round_id, row["round_number"], row["gaming_session_id"],
        source_filename, source_payload_sha256, validation_passed,
    )
    if event_id is not None:
        await conn.execute("SELECT pg_notify('round_events', $1)", str(event_id))
    return event_id
