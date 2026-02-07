"""
Round linker - resolves round_id for external metadata.

Purpose:
- Provide a single matching algorithm for linking Lua webhook data,
  endstats, and future proximity metadata to rounds.
- Avoid false "missing" issues caused by timestamp mismatch.

Matching strategy:
1) Filter by map_name + round_number (required).
2) Prefer exact round_date when available.
3) Choose the closest round_time to target_dt within a time window.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

logger = logging.getLogger("bot.core.round_linker")


def _parse_round_datetime(round_date: Optional[str], round_time: Optional[str]) -> Optional[datetime]:
    if not round_date or not round_time:
        return None

    clean_time = round_time.replace(":", "")
    if len(clean_time) != 6:
        return None

    try:
        return datetime.strptime(f"{round_date} {clean_time}", "%Y-%m-%d %H%M%S")
    except ValueError:
        return None


async def resolve_round_id(
    db_adapter,
    map_name: str,
    round_number: int,
    *,
    target_dt: Optional[datetime] = None,
    round_date: Optional[str] = None,
    round_time: Optional[str] = None,
    window_minutes: int = 45,
) -> Optional[int]:
    """
    Resolve round_id using map + round_number + nearest time.

    Args:
        db_adapter: Database adapter (PostgreSQLAdapter)
        map_name: Map name (required)
        round_number: Round number (required)
        target_dt: Preferred datetime for proximity matching
        round_date: Optional round_date filter (YYYY-MM-DD)
        round_time: Optional round_time string (HHMMSS or HH:MM:SS)
        window_minutes: Max time delta for matching (minutes)
    """
    if not map_name or not round_number:
        return None

    if not target_dt and round_date and round_time:
        target_dt = _parse_round_datetime(round_date, round_time)

    if not round_date and target_dt:
        round_date = target_dt.strftime("%Y-%m-%d")

    params: Tuple = (map_name, round_number)
    query = """
        SELECT id, round_date, round_time, created_at
        FROM rounds
        WHERE map_name = ?
          AND round_number = ?
    """

    if round_date:
        query += " AND round_date = ?"
        params = params + (round_date,)

    query += " ORDER BY created_at DESC LIMIT 10"

    rows = await db_adapter.fetch_all(query, params)
    if not rows:
        return None

    if not target_dt:
        return rows[0][0]

    best_id = None
    best_diff = timedelta(days=1)
    max_diff = timedelta(minutes=window_minutes)

    for row in rows:
        round_id, r_date, r_time, created_at = row
        candidate_dt = _parse_round_datetime(r_date, r_time)

        if not candidate_dt and created_at:
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                except ValueError:
                    created_at = None
            if created_at:
                candidate_dt = created_at.replace(tzinfo=None) if getattr(created_at, "tzinfo", None) else created_at

        if not candidate_dt:
            continue

        diff = abs(candidate_dt - target_dt)
        if diff <= max_diff and diff < best_diff:
            best_diff = diff
            best_id = round_id

    return best_id
