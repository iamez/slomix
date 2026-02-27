"""
Round linkage anomaly checks for correlation/linkage health.

This module is read-only: it runs diagnostics queries and returns anomaly
metrics, breaches against thresholds, and sample rows for investigation.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger('bot.services.round_linkage_anomaly')


DEFAULT_THRESHOLDS = {
    "max_unlinked_lua_ratio": 0.20,
    "max_match_id_mismatch_rows": 0,
    "max_map_name_mismatch_rows": 0,
    "max_round_number_mismatch_rows": 0,
    "max_duplicate_lua_round_links": 0,
    "max_correlation_round_mismatch_rows": 0,
    "max_complete_missing_core_rows": 0,
}


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _row_get(row: Any, index: int, key: str, default: Any = None) -> Any:
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key]  # asyncpg.Record mapping access
    except Exception:
        pass
    try:
        return row[index]  # tuple/list fallback
    except Exception:
        return default


def _normalize_thresholds(thresholds: Dict[str, Any] | None) -> Dict[str, Any]:
    merged = dict(DEFAULT_THRESHOLDS)
    if thresholds:
        for key, value in thresholds.items():
            if key in merged and value is not None:
                merged[key] = value

    merged["max_unlinked_lua_ratio"] = float(merged["max_unlinked_lua_ratio"] or 0.0)
    for key in (
        "max_match_id_mismatch_rows",
        "max_map_name_mismatch_rows",
        "max_round_number_mismatch_rows",
        "max_duplicate_lua_round_links",
        "max_correlation_round_mismatch_rows",
        "max_complete_missing_core_rows",
    ):
        merged[key] = max(0, _safe_int(merged[key]))
    return merged


def _build_breach(metric: str, value: Any, threshold: Any) -> Dict[str, Any]:
    return {
        "metric": metric,
        "value": value,
        "threshold": threshold,
    }


async def assess_round_linkage_anomalies(
    db,
    *,
    sample_limit: int = 20,
    thresholds: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    sample_limit = max(1, min(int(sample_limit or 20), 200))
    limits = _normalize_thresholds(thresholds)
    logger.debug("Anomaly detection started (sample_limit=%d)", sample_limit)

    payload: Dict[str, Any] = {
        "status": "ok",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "thresholds": limits,
        "metrics": {},
        "breaches": [],
        "samples": {
            "lua_link_mismatches": [],
            "correlation_link_mismatches": [],
        },
        "errors": [],
    }

    # 1) Lua linkage totals.
    try:
        row = await db.fetch_one(
            """
            SELECT
                COUNT(*) AS total_lua_rows,
                SUM(CASE WHEN round_id IS NULL THEN 1 ELSE 0 END) AS unlinked_lua_rows
            FROM lua_round_teams
            """
        )
        total_lua_rows = _safe_int(_row_get(row, 0, "total_lua_rows"))
        unlinked_lua_rows = _safe_int(_row_get(row, 1, "unlinked_lua_rows"))
        unlinked_lua_ratio = (
            float(unlinked_lua_rows) / float(total_lua_rows) if total_lua_rows > 0 else 0.0
        )
        payload["metrics"].update(
            {
                "total_lua_rows": total_lua_rows,
                "unlinked_lua_rows": unlinked_lua_rows,
                "unlinked_lua_ratio": round(unlinked_lua_ratio, 6),
            }
        )
    except Exception as e:
        payload["errors"].append(f"lua_totals_query_failed:{type(e).__name__}:{e}")

    # 2) Mismatch counts between lua_round_teams and rounds for linked rows.
    try:
        row = await db.fetch_one(
            """
            SELECT
                SUM(CASE WHEN COALESCE(l.match_id, '') <> COALESCE(r.match_id, '') THEN 1 ELSE 0 END)
                    AS match_id_mismatch_rows,
                SUM(CASE WHEN LOWER(COALESCE(l.map_name, '')) <> LOWER(COALESCE(r.map_name, '')) THEN 1 ELSE 0 END)
                    AS map_name_mismatch_rows,
                SUM(CASE WHEN COALESCE(l.round_number, -1) <> COALESCE(r.round_number, -1) THEN 1 ELSE 0 END)
                    AS round_number_mismatch_rows
            FROM lua_round_teams l
            JOIN rounds r ON l.round_id = r.id
            """
        )
        payload["metrics"].update(
            {
                "match_id_mismatch_rows": _safe_int(_row_get(row, 0, "match_id_mismatch_rows")),
                "map_name_mismatch_rows": _safe_int(_row_get(row, 1, "map_name_mismatch_rows")),
                "round_number_mismatch_rows": _safe_int(_row_get(row, 2, "round_number_mismatch_rows")),
            }
        )
    except Exception as e:
        payload["errors"].append(f"lua_rounds_mismatch_query_failed:{type(e).__name__}:{e}")

    # 3) Duplicate lua link targets.
    try:
        row = await db.fetch_one(
            """
            SELECT COUNT(*) AS duplicate_lua_round_links
            FROM (
                SELECT round_id
                FROM lua_round_teams
                WHERE round_id IS NOT NULL
                GROUP BY round_id
                HAVING COUNT(*) > 1
            ) t
            """
        )
        payload["metrics"]["duplicate_lua_round_links"] = _safe_int(
            _row_get(row, 0, "duplicate_lua_round_links")
        )
    except Exception as e:
        payload["errors"].append(f"duplicate_lua_links_query_failed:{type(e).__name__}:{e}")

    # 4) round_correlations linkage sanity.
    try:
        row = await db.fetch_one(
            """
            SELECT
                SUM(
                    CASE
                        WHEN c.r1_round_id IS NOT NULL
                             AND r1.id IS NOT NULL
                             AND (
                                 COALESCE(r1.match_id, '') <> COALESCE(c.match_id, '')
                                 OR LOWER(COALESCE(r1.map_name, '')) <> LOWER(COALESCE(c.map_name, ''))
                             )
                        THEN 1 ELSE 0
                    END
                ) AS r1_mismatch_rows,
                SUM(
                    CASE
                        WHEN c.r2_round_id IS NOT NULL
                             AND r2.id IS NOT NULL
                             AND (
                                 COALESCE(r2.match_id, '') <> COALESCE(c.match_id, '')
                                 OR LOWER(COALESCE(r2.map_name, '')) <> LOWER(COALESCE(c.map_name, ''))
                             )
                        THEN 1 ELSE 0
                    END
                ) AS r2_mismatch_rows,
                SUM(
                    CASE
                        WHEN c.status = 'complete' AND (c.r1_round_id IS NULL OR c.r2_round_id IS NULL)
                        THEN 1 ELSE 0
                    END
                ) AS complete_missing_core_rows
            FROM round_correlations c
            LEFT JOIN rounds r1 ON c.r1_round_id = r1.id
            LEFT JOIN rounds r2 ON c.r2_round_id = r2.id
            """
        )
        r1_mismatch_rows = _safe_int(_row_get(row, 0, "r1_mismatch_rows"))
        r2_mismatch_rows = _safe_int(_row_get(row, 1, "r2_mismatch_rows"))
        complete_missing_core_rows = _safe_int(_row_get(row, 2, "complete_missing_core_rows"))
        correlation_round_mismatch_rows = r1_mismatch_rows + r2_mismatch_rows
        payload["metrics"].update(
            {
                "r1_correlation_mismatch_rows": r1_mismatch_rows,
                "r2_correlation_mismatch_rows": r2_mismatch_rows,
                "correlation_round_mismatch_rows": correlation_round_mismatch_rows,
                "complete_missing_core_rows": complete_missing_core_rows,
            }
        )
    except Exception as e:
        payload["errors"].append(f"correlation_mismatch_query_failed:{type(e).__name__}:{e}")

    # 5) Samples: lua linked rows with mismatch.
    try:
        rows = await db.fetch_all(
            f"""
            SELECT
                l.id AS lua_row_id,
                l.round_id,
                l.match_id AS lua_match_id,
                r.match_id AS round_match_id,
                l.map_name AS lua_map_name,
                r.map_name AS round_map_name,
                l.round_number AS lua_round_number,
                r.round_number AS round_round_number
            FROM lua_round_teams l
            JOIN rounds r ON l.round_id = r.id
            WHERE
                COALESCE(l.match_id, '') <> COALESCE(r.match_id, '')
                OR LOWER(COALESCE(l.map_name, '')) <> LOWER(COALESCE(r.map_name, ''))
                OR COALESCE(l.round_number, -1) <> COALESCE(r.round_number, -1)
            ORDER BY l.id DESC
            LIMIT {sample_limit}
            """
        )
        for row in rows:
            payload["samples"]["lua_link_mismatches"].append(
                {
                    "lua_row_id": _safe_int(_row_get(row, 0, "lua_row_id")),
                    "round_id": _safe_int(_row_get(row, 1, "round_id")),
                    "lua_match_id": _row_get(row, 2, "lua_match_id"),
                    "round_match_id": _row_get(row, 3, "round_match_id"),
                    "lua_map_name": _row_get(row, 4, "lua_map_name"),
                    "round_map_name": _row_get(row, 5, "round_map_name"),
                    "lua_round_number": _safe_int(_row_get(row, 6, "lua_round_number")),
                    "round_round_number": _safe_int(_row_get(row, 7, "round_round_number")),
                }
            )
    except Exception as e:
        payload["errors"].append(f"lua_mismatch_samples_query_failed:{type(e).__name__}:{e}")

    # 6) Samples: correlation rows with mismatch.
    try:
        rows = await db.fetch_all(
            f"""
            SELECT
                c.correlation_id,
                c.match_id,
                c.map_name,
                c.r1_round_id,
                c.r2_round_id,
                r1.match_id AS r1_round_match_id,
                r2.match_id AS r2_round_match_id,
                r1.map_name AS r1_round_map_name,
                r2.map_name AS r2_round_map_name,
                c.status
            FROM round_correlations c
            LEFT JOIN rounds r1 ON c.r1_round_id = r1.id
            LEFT JOIN rounds r2 ON c.r2_round_id = r2.id
            WHERE
                (c.r1_round_id IS NOT NULL AND r1.id IS NOT NULL AND (
                    COALESCE(r1.match_id, '') <> COALESCE(c.match_id, '')
                    OR LOWER(COALESCE(r1.map_name, '')) <> LOWER(COALESCE(c.map_name, ''))
                ))
                OR
                (c.r2_round_id IS NOT NULL AND r2.id IS NOT NULL AND (
                    COALESCE(r2.match_id, '') <> COALESCE(c.match_id, '')
                    OR LOWER(COALESCE(r2.map_name, '')) <> LOWER(COALESCE(c.map_name, ''))
                ))
                OR
                (c.status = 'complete' AND (c.r1_round_id IS NULL OR c.r2_round_id IS NULL))
            ORDER BY c.created_at DESC
            LIMIT {sample_limit}
            """
        )
        for row in rows:
            payload["samples"]["correlation_link_mismatches"].append(
                {
                    "correlation_id": _row_get(row, 0, "correlation_id"),
                    "match_id": _row_get(row, 1, "match_id"),
                    "map_name": _row_get(row, 2, "map_name"),
                    "r1_round_id": _row_get(row, 3, "r1_round_id"),
                    "r2_round_id": _row_get(row, 4, "r2_round_id"),
                    "r1_round_match_id": _row_get(row, 5, "r1_round_match_id"),
                    "r2_round_match_id": _row_get(row, 6, "r2_round_match_id"),
                    "r1_round_map_name": _row_get(row, 7, "r1_round_map_name"),
                    "r2_round_map_name": _row_get(row, 8, "r2_round_map_name"),
                    "status": _row_get(row, 9, "status"),
                }
            )
    except Exception as e:
        payload["errors"].append(f"correlation_mismatch_samples_query_failed:{type(e).__name__}:{e}")

    metrics = payload["metrics"]
    breaches = payload["breaches"]

    unlinked_ratio = float(metrics.get("unlinked_lua_ratio", 0.0))
    if unlinked_ratio > limits["max_unlinked_lua_ratio"]:
        breaches.append(
            _build_breach("unlinked_lua_ratio", round(unlinked_ratio, 6), limits["max_unlinked_lua_ratio"])
        )

    for metric, threshold_key in (
        ("match_id_mismatch_rows", "max_match_id_mismatch_rows"),
        ("map_name_mismatch_rows", "max_map_name_mismatch_rows"),
        ("round_number_mismatch_rows", "max_round_number_mismatch_rows"),
        ("duplicate_lua_round_links", "max_duplicate_lua_round_links"),
        ("correlation_round_mismatch_rows", "max_correlation_round_mismatch_rows"),
        ("complete_missing_core_rows", "max_complete_missing_core_rows"),
    ):
        value = _safe_int(metrics.get(metric, 0))
        threshold = _safe_int(limits[threshold_key])
        if value > threshold:
            breaches.append(_build_breach(metric, value, threshold))

    if payload["errors"]:
        payload["status"] = "error"
        logger.warning("Anomaly detection completed with errors: %s", payload["errors"])
    elif breaches:
        payload["status"] = "warning"
        logger.warning("Anomaly detection found %d breach(es): %s",
                        len(breaches), [b["metric"] for b in breaches])
    else:
        logger.debug("Anomaly detection complete: no breaches")
    return payload
