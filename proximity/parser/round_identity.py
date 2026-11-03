"""Prefer physical source-start identity without changing legacy fallback clocks."""

import time

from bot.core.round_linker import fallback_source_start_conflict, resolve_round_id_with_reason


async def resolve_proximity_round_id(
    adapter, map_name, round_number, *, source_start_unix, **fallback_options,
):
    """Use a unique exact physical start, otherwise preserve the legacy linker.

    Proximity end time is useful for legacy filename-based matching, but must
    not beat a known start identity by being nearer another round's start.
    Duplicate exact identities are ambiguous, not permission to choose one.
    Bounds mirror the linker's plausible game-clock range. Missing/implausible
    starts retain existing fallback behavior; fallback candidates with a different
    known start are deferred. Query failures
    propagate; the parser records unavailable linkage instead of guessing.
    """
    plausible_start = (type(source_start_unix) is int
                       and 1577836800 < source_start_unix <= int(time.time()) + 86400)
    if plausible_start:
        rows = await adapter.fetch_all(
            'SELECT id FROM rounds WHERE LOWER(BTRIM(map_name)) = LOWER(BTRIM(?)) AND round_number = ? '
            'AND round_start_unix = ? ORDER BY id LIMIT 2',
            (map_name, round_number, source_start_unix),
        )
        if rows:
            unique = len(rows) == 1
            return (rows[0][0] if unique else None), {
                'reason_code': 'resolved_source_start' if unique else 'ambiguous_source_start',
                'candidate_count': len(rows),
                'parsed_candidate_count': len(rows),
                'best_diff_seconds': 0,
            }
    round_id, diag = await resolve_round_id_with_reason(
        adapter, map_name, round_number, **fallback_options,
    )
    if plausible_start and round_id is not None:
        # A nearby filename/end clock cannot override a different physical start.
        # NULL starts remain eligible for legacy linkage; they are not conflicts.
        conflict = await fallback_source_start_conflict(
            adapter, round_id, map_name, round_number, source_start_unix,
        )
        if conflict:
            return None, {**diag, 'reason_code': conflict}
    return round_id, diag
