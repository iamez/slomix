"""Journal restart decisions on the canonical import transaction, opt-in only."""

import json
import os

from shared.runtime_events import event_stream_enabled


def status_events_enabled() -> bool:
    return event_stream_enabled() and os.getenv("ROUND_STATUS_EVENTS_ENABLED", "false").strip().lower() == "true"


async def mark_round_restart(conn, *, round_id: int, status: str, caused_by_round_id: int) -> bool:
    """Apply one completed-to-restart transition; caller must roll back errors.

    This helper is called only by the enabled producer. It never owns or commits
    a transaction and does not reinterpret the detector's restart heuristics.
    """
    if not conn.is_in_transaction():
        raise RuntimeError("Restart events require the canonical import transaction")
    if status not in ("cancelled", "substitution"):
        raise ValueError("Unsupported restart status")
    if round_id == caused_by_round_id:
        raise ValueError("A restart must be caused by a different round")
    row = await conn.fetchrow("""
        UPDATE rounds SET round_status = $1
        WHERE id = $2 AND round_status = 'completed' AND round_number IN (1, 2)
        RETURNING round_number, gaming_session_id
    """, status, round_id)
    if row is None:
        return False
    details = json.dumps({
        "source": "restart_detection", "old_status": "completed",
        "new_status": status, "caused_by_round_id": caused_by_round_id,
    })
    event_id = await conn.fetchval("""
        INSERT INTO runtime_events (
            event_type, schema_version, round_id, round_number,
            gaming_session_id, event_details
        ) VALUES ('round_status_changed', 1, $1, $2, $3, $4::jsonb)
        RETURNING id
    """, round_id, row["round_number"], row["gaming_session_id"], details)
    await conn.execute("SELECT pg_notify('round_events', $1)", str(event_id))
    return True
