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
from typing import Any, Dict, Optional, Tuple

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

    This is the compatibility API used by existing callers.
    """
    round_id, _diag = await resolve_round_id_with_reason(
        db_adapter,
        map_name,
        round_number,
        target_dt=target_dt,
        round_date=round_date,
        round_time=round_time,
        window_minutes=window_minutes,
    )
    return round_id


async def resolve_round_id_with_reason(
    db_adapter,
    map_name: str,
    round_number: int,
    *,
    target_dt: Optional[datetime] = None,
    round_date: Optional[str] = None,
    round_time: Optional[str] = None,
    window_minutes: int = 45,
) -> Tuple[Optional[int], Dict[str, Any]]:
    """
    Resolve round_id and return structured diagnostics.

    Diagnostic payload keys:
    1. reason_code
    2. candidate_count
    3. parsed_candidate_count
    4. best_diff_seconds
    5. map_name
    6. round_number
    7. round_date
    8. round_time
    9. window_minutes
    """
    diag: Dict[str, Any] = {
        "reason_code": "unknown",
        "candidate_count": 0,
        "parsed_candidate_count": 0,
        "best_diff_seconds": None,
        "date_filter_relaxed": False,
        "map_name": map_name,
        "round_number": round_number,
        "round_date": round_date,
        "round_time": round_time,
        "window_minutes": window_minutes,
    }
    if not map_name or not round_number:
        diag["reason_code"] = "invalid_input"
        logger.warning("round_linker: reason=invalid_input map=%s rn=%s", map_name, round_number)
        return None, diag

    if not target_dt and round_date and round_time:
        target_dt = _parse_round_datetime(round_date, round_time)
        if not target_dt:
            diag["reason_code"] = "time_parse_failed"
            logger.warning(
                "round_linker: reason=time_parse_failed map=%s rn=%d date=%s time=%s",
                map_name, round_number, round_date, round_time,
            )

    if not round_date and target_dt:
        round_date = target_dt.strftime("%Y-%m-%d")
        diag["round_date"] = round_date

    params: Tuple = (map_name, round_number)
    base_query = """
        SELECT id, round_date, round_time, created_at
        FROM rounds
        WHERE map_name = ?
          AND round_number = ?
    """
    query = base_query

    if round_date:
        query += " AND round_date = ?"
        params = params + (round_date,)

    query += " ORDER BY created_at DESC LIMIT 10"

    rows = await db_adapter.fetch_all(query, params)
    if not rows:
        if round_date:
            date_free_rows = await db_adapter.fetch_all(
                f"{base_query} ORDER BY created_at DESC LIMIT 10",
                (map_name, round_number),
            )
            if date_free_rows:
                if target_dt:
                    rows = date_free_rows
                    diag["date_filter_relaxed"] = True
                    logger.warning(
                        "round_linker: reason=date_filter_relaxed map=%s rn=%d date=%s "
                        "(rows exist for map+rn on nearby dates; continuing with time window)",
                        map_name, round_number, round_date,
                    )
                else:
                    diag["reason_code"] = "date_filter_excluded_rows"
                    logger.warning(
                        "round_linker: reason=date_filter_excluded_rows map=%s rn=%d date=%s "
                        "(rows exist for map+rn but no target_dt to safely relax date filter)",
                        map_name, round_number, round_date,
                    )
                    return None, diag
            else:
                diag["reason_code"] = "no_rows_for_map_round"
                logger.warning(
                    "round_linker: reason=no_rows_for_map_round map=%s rn=%d date=%s",
                    map_name, round_number, round_date,
                )
                return None, diag
        else:
            diag["reason_code"] = "no_rows_for_map_round"
            logger.warning(
                "round_linker: reason=no_rows_for_map_round map=%s rn=%d date=%s",
                map_name, round_number, round_date,
            )
            return None, diag

    if not target_dt:
        diag["candidate_count"] = len(rows)
        diag["reason_code"] = "resolved"
        logger.debug(
            "round_linker: reason=resolved (no target_dt, first candidate) map=%s rn=%d round_id=%d",
            map_name, round_number, rows[0][0],
        )
        return rows[0][0], diag

    best_id = None
    best_diff = timedelta(days=1)
    max_diff = timedelta(minutes=window_minutes)
    parsed_diffs_seconds = []
    diag["candidate_count"] = len(rows)

    for row in rows:
        round_id = row[0] if len(row) > 0 else None
        r_date = row[1] if len(row) > 1 else None
        r_time = row[2] if len(row) > 2 else None
        created_at = row[3] if len(row) > 3 else None
        if round_id is None:
            continue
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

        diag["parsed_candidate_count"] += 1
        diff = abs(candidate_dt - target_dt)
        parsed_diffs_seconds.append(diff.total_seconds())
        if diff <= max_diff and diff < best_diff:
            best_diff = diff
            best_id = round_id

    if best_id is not None:
        diag["reason_code"] = "resolved"
        diag["best_diff_seconds"] = int(best_diff.total_seconds())
        logger.debug(
            "round_linker: reason=resolved map=%s rn=%d round_id=%d diff=%ds candidates=%d",
            map_name, round_number, best_id, diag["best_diff_seconds"], diag["candidate_count"],
        )
        return best_id, diag

    if diag["parsed_candidate_count"] == 0:
        if diag.get("date_filter_relaxed"):
            diag["reason_code"] = "date_filter_excluded_rows"
            logger.warning(
                "round_linker: reason=date_filter_excluded_rows map=%s rn=%d date=%s "
                "(date filter relaxed but candidates had no parseable timestamps)",
                map_name, round_number, round_date,
            )
        else:
            diag["reason_code"] = "time_parse_failed"
            logger.warning(
                "round_linker: reason=time_parse_failed (no parseable candidates) map=%s rn=%d candidates=%d",
                map_name, round_number, diag["candidate_count"],
            )
    else:
        diag["reason_code"] = "all_candidates_outside_window"
        if parsed_diffs_seconds:
            diag["best_diff_seconds"] = int(min(parsed_diffs_seconds))
        logger.warning(
            "round_linker: reason=all_candidates_outside_window map=%s rn=%d "
            "window=%dmin best_diff=%ss parsed=%d/%d",
            map_name, round_number, window_minutes,
            diag["best_diff_seconds"], diag["parsed_candidate_count"], diag["candidate_count"],
        )
    return None, diag
