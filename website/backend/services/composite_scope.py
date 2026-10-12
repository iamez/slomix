"""Canonical, quality-filtered identity for composite metrics and coverage."""
from __future__ import annotations

from fastapi import HTTPException

from website.backend.services.session_scope import GamingSessionScope, resolve_gaming_session_scope


async def resolve_composite_scope(db, *, gaming_session_id=None, session_date=None):
    """Resolve a date unambiguously, then exclude bot rounds from the scope.

    The shared resolver supplies the canonical session identity and its 409
    behavior. Composite additionally excludes bot rounds; do not weaken the
    common resolver or silently merge two sessions that share a date.
    """
    scope = await resolve_gaming_session_scope(
        db, gaming_session_id=gaming_session_id,
        session_date=session_date if gaming_session_id is None else None,
    )
    rows = await db.fetch_all("""
        SELECT round_start_unix, map_name, round_number,
               SUBSTR(CAST(round_date AS TEXT), 1, 10) AS rdate
        FROM rounds
        WHERE gaming_session_id = $1
          AND round_number IN (1, 2)
          AND is_valid IS DISTINCT FROM FALSE
          AND is_bot_round IS DISTINCT FROM TRUE
          AND (round_status IN ('completed', 'substitution') OR round_status IS NULL)
        ORDER BY round_start_unix NULLS LAST, round_number
    """, (scope.gaming_session_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="No accepted non-bot rounds in this gaming session.")
    return GamingSessionScope(
        gaming_session_id=scope.gaming_session_id,
        dates=tuple(sorted({r[3] for r in rows if r[3]})),
        round_keys=tuple(sorted({(int(r[0] or 0), r[1] or '', int(r[2])) for r in rows})),
        accepted_round_count=len(rows),
        distinct_map_names=tuple(sorted({r[1] for r in rows if r[1]})),
    )
