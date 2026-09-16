"""Logical persisted endstats rows for change detection, not delivery status."""

import math
from collections import Counter


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
