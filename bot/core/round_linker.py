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
import time
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger("bot.core.round_linker")

# Sanity bounds on unix timestamps — reject values that are almost
# certainly a server clock misconfiguration. ET:Legacy round_start_unix
# values should always fall inside this window.
_MIN_PLAUSIBLE_UNIX_TS = 1577836800  # 2020-01-01 UTC
_MAX_FUTURE_DRIFT_SECONDS = 86400    # 1 day — allow minor clock skew


def _parse_round_datetime(round_date: str | None, round_time: str | None) -> datetime | None:
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
    target_dt: datetime | None = None,
    round_date: str | None = None,
    round_time: str | None = None,
    window_minutes: int = 45,
) -> int | None:
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
    target_dt: datetime | None = None,
    round_date: str | None = None,
    round_time: str | None = None,
    window_minutes: int = 45,
) -> tuple[int | None, dict[str, Any]]:
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
    diag: dict[str, Any] = {
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

    # Normalize tz-aware target_dt to naive-local at the entry. Every
    # `candidate_dt` built downstream comes from `datetime.fromtimestamp()`
    # / `strptime()` / `_parse_round_datetime()` — all naive-local — so
    # mixing a tz-aware target_dt would raise `TypeError` inside
    # `abs(candidate_dt - target_dt)`. The proximity-audit relinker fix
    # (PR #130, P3) started passing tz-aware UTC here; fix centralizes
    # the convention so every existing legacy caller keeps working.
    if target_dt is not None and target_dt.tzinfo is not None:
        target_dt = target_dt.astimezone().replace(tzinfo=None)

    if not target_dt and round_date and round_time:
        target_dt = _parse_round_datetime(round_date, round_time)
        if not target_dt:
            diag["reason_code"] = "time_parse_failed"
            logger.debug(
                "round_linker: reason=time_parse_failed map=%s rn=%d date=%s time=%s",
                map_name, round_number, round_date, round_time,
            )

    if not round_date and target_dt:
        round_date = target_dt.strftime("%Y-%m-%d")
        diag["round_date"] = round_date

    params: tuple = (map_name, round_number)
    base_query = """
        SELECT id, round_date, round_time, created_at, round_start_unix
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
            # Prefer round_start_unix proximity to target_dt — handles two real
            # production scenarios:
            #   (1) Midnight crossover: round_date='2026-04-19' but the round
            #       actually spans into 2026-04-20, so the DB row was recorded
            #       with round_date='2026-04-20'.
            #   (2) Race condition: the stats file that will insert THIS round
            #       hasn't been imported yet; if we just ORDER BY created_at
            #       DESC we will pick up stale rounds from weeks ago and
            #       report a misleading "25-day diff" match.
            # By adding a `round_start_unix BETWEEN target±window` filter we
            # correctly surface only rounds that could plausibly match, and
            # return zero rows (→ no_rows_for_map_round) when the round is
            # not yet persisted.
            if target_dt:
                window_seconds = max(1, window_minutes) * 60
                target_ts = int(target_dt.timestamp())
                date_free_rows = await db_adapter.fetch_all(
                    f"{base_query} AND round_start_unix BETWEEN ? AND ? "
                    "ORDER BY ABS(round_start_unix - ?) ASC LIMIT 10",
                    (
                        map_name,
                        round_number,
                        target_ts - window_seconds,
                        target_ts + window_seconds,
                        target_ts,
                    ),
                )
            else:
                date_free_rows = await db_adapter.fetch_all(
                    f"{base_query} ORDER BY created_at DESC LIMIT 10",
                    (map_name, round_number),
                )
            if date_free_rows:
                if target_dt:
                    rows = date_free_rows
                    diag["date_filter_relaxed"] = True
                    logger.debug(
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
                # Distinguish a live race (target_dt within the last hour — the
                # round just hasn't landed yet) from a stale orphan (target_dt
                # is hours or days old — the round never made it into rounds,
                # and the relinker cron has nothing to retry against).
                if target_dt:
                    # target_dt may be naive-local (legacy callers use
                    # datetime.fromtimestamp()) or tz-aware UTC (relinker
                    # P3 fix). Pick a matching `now` so the subtraction
                    # doesn't silently drift by the host's UTC offset.
                    if target_dt.tzinfo is not None:
                        now_ref = datetime.now(target_dt.tzinfo)
                    else:
                        now_ref = datetime.now()
                    age_seconds = int(
                        (now_ref - target_dt).total_seconds()
                    )
                    if age_seconds > 3600:
                        # Stale: more than an hour since the source event fired
                        logger.warning(
                            "round_linker: reason=no_rows_for_map_round map=%s rn=%d date=%s "
                            "(target_dt is %dh %dm old — stale orphan, no rounds row "
                            "was ever created; skip or manual import)",
                            map_name, round_number, round_date,
                            age_seconds // 3600,
                            (age_seconds % 3600) // 60,
                        )
                    else:
                        logger.warning(
                            "round_linker: reason=no_rows_for_map_round map=%s rn=%d date=%s "
                            "(no rounds within ±%dmin of target_dt — likely race "
                            "condition; relinker cron will retry)",
                            map_name, round_number, round_date, window_minutes,
                        )
                else:
                    logger.warning(
                        "round_linker: reason=no_rows_for_map_round map=%s rn=%d date=%s "
                        "(no target_dt supplied)",
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

    # Exact round_start_unix match takes priority over closest-timestamp
    # search. When the same (map, round_number) is played multiple times
    # in a session (common in scrim queues), closest-timestamp wrongly
    # attributes engagement/proximity rows to an earlier round because
    # the engagement's start-of-round timestamp falls between the prior
    # round's stats-file end time and the current round's stats-file end
    # time. If the caller's target_dt comes from the same Lua `round_start_unix`
    # that's stored on `rounds`, exact match is unambiguous.
    if target_dt:
        try:
            target_unix = int(target_dt.timestamp())
        except (OSError, OverflowError, ValueError):
            target_unix = 0
        if target_unix > 0:
            for row in rows:
                r_start_unix = row[4] if len(row) > 4 else None
                if r_start_unix is None:
                    continue
                try:
                    cand_unix = int(r_start_unix)
                except (ValueError, TypeError):
                    continue
                if cand_unix == target_unix:
                    round_id = row[0] if len(row) > 0 else None
                    if round_id is not None:
                        diag["reason_code"] = "resolved_exact_unix_match"
                        diag["best_diff_seconds"] = 0
                        diag["candidate_count"] = len(rows)
                        diag["parsed_candidate_count"] = len(rows)
                        logger.debug(
                            "round_linker: exact round_start_unix match map=%s rn=%d round_id=%d unix=%d",
                            map_name, round_number, round_id, target_unix,
                        )
                        return round_id, diag

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
        r_start_unix = row[4] if len(row) > 4 else None
        if round_id is None:
            continue

        # Prefer round_start_unix (most accurate for same-map disambiguation)
        candidate_dt = None
        if r_start_unix:
            try:
                ts = int(r_start_unix)
            except (ValueError, TypeError):
                ts = 0
            max_future_ts = int(time.time()) + _MAX_FUTURE_DRIFT_SECONDS
            if _MIN_PLAUSIBLE_UNIX_TS < ts <= max_future_ts:
                try:
                    # Use fromtimestamp() WITHOUT tz to get LOCAL naive datetime,
                    # matching target_dt which is also local naive (from filename
                    # round_date+round_time or from datetime.fromtimestamp(unix)
                    # in _resolve_round_id_for_metadata).
                    candidate_dt = datetime.fromtimestamp(ts)
                except (ValueError, TypeError, OSError):
                    candidate_dt = None
            elif ts > 0:
                # Out-of-bounds timestamp — server clock was misconfigured or
                # value is corrupted. Skip this candidate (fall through to the
                # round_date+round_time text fallback below).
                logger.debug(
                    "round_linker: skipping candidate round_id=%s with "
                    "out-of-bounds round_start_unix=%d", round_id, ts,
                )

        if not candidate_dt:
            candidate_dt = _parse_round_datetime(r_date, r_time)

        if not candidate_dt and created_at:
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                except ValueError:
                    created_at = None
            if created_at:
                # Convert aware UTC to local naive to match target_dt convention
                if getattr(created_at, "tzinfo", None):
                    candidate_dt = created_at.astimezone().replace(tzinfo=None)
                else:
                    candidate_dt = created_at

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
        logger.debug(
            "round_linker: reason=all_candidates_outside_window map=%s rn=%d "
            "window=%dmin best_diff=%ss parsed=%d/%d",
            map_name, round_number, window_minutes,
            diag["best_diff_seconds"], diag["parsed_candidate_count"], diag["candidate_count"],
        )
    return None, diag
