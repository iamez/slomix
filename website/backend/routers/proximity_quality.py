"""Read-only proximity data quality endpoint."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from shared.services.round_linkage_anomaly_service import assess_round_linkage_anomalies
from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.logging_config import get_app_logger
from website.backend.routers.proximity_helpers import (
    _build_proximity_where_clause,
    _parse_iso_date,
)

router = APIRouter()
logger = get_app_logger("api.proximity.quality")


_SIGNAL_SOURCES: tuple[dict[str, Any], ...] = (
    {
        "key": "combat_engagement",
        "table": "combat_engagement",
        "has_round_id": True,
        "required": True,
        "core": True,
        "min_rows": 1,
    },
    {
        "key": "player_track",
        "table": "player_track",
        "has_round_id": True,
        "required": True,
        "core": True,
        "min_rows": 1,
    },
    {
        "key": "proximity_kill_outcome",
        "table": "proximity_kill_outcome",
        "has_round_id": True,
        "required": True,
        "core": True,
        "min_rows": 1,
    },
    {
        "key": "proximity_spawn_timing",
        "table": "proximity_spawn_timing",
        "has_round_id": True,
        "required": True,
        "core": False,
        "min_rows": 1,
    },
    {
        "key": "proximity_team_push",
        "table": "proximity_team_push",
        "has_round_id": True,
        "required": True,
        "core": False,
        "min_rows": 1,
    },
    {
        "key": "proximity_crossfire_opportunity",
        "table": "proximity_crossfire_opportunity",
        "has_round_id": True,
        "required": True,
        "core": False,
        "min_rows": 1,
    },
    {
        "key": "proximity_reaction_metric",
        "table": "proximity_reaction_metric",
        "has_round_id": True,
        "required": True,
        "core": False,
        "min_rows": 1,
    },
    {
        "key": "proximity_shot_fired",
        "table": "proximity_shot_fired",
        "has_round_id": True,
        "required": False,
        "experimental": True,
        "core": False,
        "min_rows": 1,
    },
    {
        "key": "proximity_hit_region",
        "table": "proximity_hit_region",
        "has_round_id": True,
        "required": True,
        "core": False,
        "min_rows": 1,
    },
    {
        "key": "storytelling_kill_impact",
        "table": "storytelling_kill_impact",
        "has_round_id": False,
        "required": True,
        "core": False,
        "min_rows": 1,
    },
)

_KIS_CONTEXT_SIGNAL_KEYS = {
    source["key"]
    for source in _SIGNAL_SOURCES
    if source["key"] != "storytelling_kill_impact" and not source.get("experimental")
}


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _row_get(row: Any, index: int, key: str, default: Any = None) -> Any:
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        pass
    try:
        return row[index]
    except (IndexError, TypeError):
        return default


def _to_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        dt = datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)
    elif isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        iso_value = f"{raw[:-1]}+00:00" if raw.endswith("Z") else raw
        try:
            dt = datetime.fromisoformat(iso_value)
        except ValueError:
            return None
    else:
        return None

    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _isoformat(value: Any) -> str | None:
    dt = _to_datetime(value)
    if not dt:
        return None
    return dt.isoformat()


def _warning(code: str, message: str, level: str = "warning") -> dict[str, str]:
    return {"code": code, "level": level, "message": message}


def _is_sqlite_adapter(db: DatabaseAdapter) -> bool:
    adapter_name = db.__class__.__name__.lower()
    return adapter_name.startswith("sqlite") or hasattr(db, "db_path")


def _sqlite_unsupported_payload(scope: dict[str, Any]) -> dict[str, Any]:
    return {
        "overall_status": "error",
        "selected_scope_status": "error",
        "global_maintenance_status": "unknown",
        "scope": scope,
        "signals": {},
        "round_correlation": {
            "status": "unsupported",
            "ready": False,
            "error": "sqlite_unsupported",
        },
        "linkage": {
            "scope": "global",
            "status": "unknown",
            "metrics": {},
            "breach_count": 0,
            "breaches": [],
            "errors": [],
        },
        "cache_freshness": {"status": "unknown"},
        "warnings": [
            _warning(
                "PROXIMITY_QUALITY_SQLITE_UNSUPPORTED",
                "Proximity quality checks require PostgreSQL and are unavailable in local SQLite mode.",
            )
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


_EXACT_LINK_RATIO_THRESHOLD = 0.90


async def _collect_signal(
    db: DatabaseAdapter,
    source: dict[str, Any],
    *,
    range_days: int,
    session_date: str | None,
    map_name: str | None,
    round_number: int | None,
    round_start_unix: int | None,
) -> dict[str, Any]:
    key = source["key"]
    table = source["table"]
    has_round_id = bool(source.get("has_round_id"))

    if has_round_id:
        # Aliased + LEFT JOIN rounds so "linked" can be checked against the
        # ONE thing a foreign key can't lie about without the join: whether
        # the linked round's own round_start_unix agrees with the source
        # row's round_start_unix. A non-NULL round_id proves a row points at
        # *some* round — never that it points at the CORRECT one (Codex
        # §18.6: back-to-back replays of the same map get nearest-neighbour
        # linked to the wrong instance while round_id stays non-NULL).
        where_sql, params, _scope = _build_proximity_where_clause(
            range_days, session_date, map_name, round_number, round_start_unix,
            alias="src",
        )
        query = f"""
            /* proximity_quality_signal:{key} */
            SELECT
                COUNT(*) AS row_count,
                COUNT(*) FILTER (WHERE src.round_id IS NOT NULL) AS linked_rows,
                COUNT(DISTINCT src.round_id) FILTER (WHERE src.round_id IS NOT NULL) AS linked_round_count,
                COUNT(*) FILTER (
                    WHERE src.round_id IS NOT NULL
                      AND src.round_start_unix IS NOT NULL
                      AND r.round_start_unix IS NOT NULL
                ) AS comparable_start_rows,
                COUNT(*) FILTER (
                    WHERE src.round_id IS NOT NULL
                      AND src.round_start_unix IS NOT NULL
                      AND r.round_start_unix IS NOT NULL
                      AND src.round_start_unix = r.round_start_unix
                ) AS exact_start_rows,
                MAX(src.created_at) AS latest_created_at
            FROM {table} src
            LEFT JOIN rounds r ON src.round_id = r.id
            {where_sql}
        """  # nosec B608 - table/key are hardcoded constants in _SIGNAL_SOURCES.
    else:
        where_sql, params, _scope = _build_proximity_where_clause(
            range_days, session_date, map_name, round_number, round_start_unix,
        )
        query = f"""
            /* proximity_quality_signal:{key} */
            SELECT
                COUNT(*) AS row_count,
                NULL::integer AS linked_rows,
                NULL::integer AS linked_round_count,
                NULL::integer AS comparable_start_rows,
                NULL::integer AS exact_start_rows,
                MAX(created_at) AS latest_created_at
            FROM {table}
            {where_sql}
        """  # nosec B608 - table/key are hardcoded constants in _SIGNAL_SOURCES.

    try:
        row = await db.fetch_one(query, tuple(params))
    except Exception as exc:
        logger.warning("proximity quality signal query failed for %s: %s", key, exc)
        return {
            "table": table,
            "row_count": 0,
            "linked_rows": None,
            "linked_round_count": None,
            "comparable_start_rows": None,
            "exact_start_rows": None,
            "wrong_start_rows": None,
            "exact_link_ratio": None,
            "latest_created_at": None,
            "ready": False,
            "status": "error",
            "error": "query_failed",
            "required": bool(source.get("required")),
            "experimental": bool(source.get("experimental")),
            "core": bool(source.get("core")),
            "min_rows": _safe_int(source.get("min_rows", 1)),
        }

    row_count = _safe_int(_row_get(row, 0, "row_count"))
    linked_rows_raw = _row_get(row, 1, "linked_rows")
    linked_rows = _safe_int(linked_rows_raw) if linked_rows_raw is not None else None
    linked_round_count_raw = _row_get(row, 2, "linked_round_count")
    linked_round_count = (
        _safe_int(linked_round_count_raw) if linked_round_count_raw is not None else None
    )
    comparable_start_rows_raw = _row_get(row, 3, "comparable_start_rows")
    comparable_start_rows = (
        _safe_int(comparable_start_rows_raw) if comparable_start_rows_raw is not None else None
    )
    exact_start_rows_raw = _row_get(row, 4, "exact_start_rows")
    exact_start_rows = (
        _safe_int(exact_start_rows_raw) if exact_start_rows_raw is not None else None
    )
    latest_created_at = _row_get(row, 5, "latest_created_at")
    min_rows = max(1, _safe_int(source.get("min_rows", 1)))
    required = bool(source.get("required"))

    wrong_start_rows = (
        comparable_start_rows - exact_start_rows
        if comparable_start_rows is not None and exact_start_rows is not None
        else None
    )
    # exact_link_ratio is denominated over ALL rows (not just comparable
    # ones): a row with no comparable start is honestly NOT proven correct,
    # so it must count against the ratio the same way a wrong-start row does
    # (Codex §18.6 — the old linked_ratio counted it as healthy).
    exact_link_ratio = (
        round(float(exact_start_rows) / float(row_count), 6)
        if has_round_id and exact_start_rows is not None and row_count > 0
        else None
    )

    status = "ok"
    ready = True
    if row_count <= 0:
        status = "missing"
        ready = not required
    elif row_count < min_rows:
        status = "low_count"
        ready = not required
    elif wrong_start_rows is not None and wrong_start_rows > 0:
        status = "wrong_round_linkage"
        ready = not required
    elif exact_link_ratio is not None and exact_link_ratio < _EXACT_LINK_RATIO_THRESHOLD:
        status = "round_linkage_partial"
        ready = not required

    return {
        "table": table,
        "row_count": row_count,
        "linked_rows": linked_rows,
        "linked_round_count": linked_round_count,
        "comparable_start_rows": comparable_start_rows,
        "exact_start_rows": exact_start_rows,
        "wrong_start_rows": wrong_start_rows,
        "exact_link_ratio": exact_link_ratio,
        "latest_created_at": _isoformat(latest_created_at),
        "ready": ready,
        "status": status,
        "required": required,
        "experimental": bool(source.get("experimental")),
        "core": bool(source.get("core")),
        "min_rows": min_rows,
    }


async def _collect_signals(
    db: DatabaseAdapter,
    *,
    range_days: int,
    session_date: str | None,
    map_name: str | None,
    round_number: int | None,
    round_start_unix: int | None,
) -> dict[str, dict[str, Any]]:
    signal_rows = await asyncio.gather(
        *(
            _collect_signal(
                db,
                source,
                range_days=range_days,
                session_date=session_date,
                map_name=map_name,
                round_number=round_number,
                round_start_unix=round_start_unix,
            )
            for source in _SIGNAL_SOURCES
        )
    )
    return {
        source["key"]: signal
        for source, signal in zip(_SIGNAL_SOURCES, signal_rows, strict=True)
    }


def _build_correlation_scope(
    *,
    range_days: int,
    session_date: str | None,
    map_name: str | None,
    round_number: int | None,
    round_start_unix: int | None,
) -> tuple[str, tuple[Any, ...]]:
    params: list[Any] = []
    clauses: list[str] = []

    parsed_session_date = _parse_iso_date(session_date)
    normalized_map = (map_name or "").strip() or None
    if parsed_session_date is not None:
        params.append(parsed_session_date.isoformat())
        param_idx = len(params)
        clauses.append(
            f"(r1.round_date = ${param_idx} OR r2.round_date = ${param_idx})"
        )
    else:
        safe_range = max(1, min(int(range_days or 30), 3650))
        since_str = (
            datetime.now(timezone.utc).date() - timedelta(days=safe_range)
        ).isoformat()
        params.append(since_str)
        param_idx = len(params)
        clauses.append(
            f"(r1.round_date >= ${param_idx} OR r2.round_date >= ${param_idx} OR rc.created_at::date >= ${param_idx}::date)"
        )

    if normalized_map is not None:
        params.append(normalized_map)
        clauses.append(f"rc.map_name = ${len(params)}")
    if round_number is not None:
        params.append(int(round_number))
        param_idx = len(params)
        clauses.append(
            f"(r1.round_number = ${param_idx} OR r2.round_number = ${param_idx})"
        )
    if round_start_unix is not None and int(round_start_unix) > 0:
        params.append(int(round_start_unix))
        param_idx = len(params)
        clauses.append(
            f"(r1.round_start_unix = ${param_idx} OR r2.round_start_unix = ${param_idx})"
        )

    return "WHERE " + " AND ".join(clauses), tuple(params)


async def _collect_round_correlation(
    db: DatabaseAdapter,
    *,
    range_days: int,
    session_date: str | None,
    map_name: str | None,
    round_number: int | None,
    round_start_unix: int | None,
) -> dict[str, Any]:
    where_sql, params = _build_correlation_scope(
        range_days=range_days,
        session_date=session_date,
        map_name=map_name,
        round_number=round_number,
        round_start_unix=round_start_unix,
    )
    try:
        row = await db.fetch_one(
            f"""
            /* proximity_quality_round_correlation */
            SELECT
                COUNT(*) AS correlation_count,
                COUNT(*) FILTER (WHERE rc.status = 'complete') AS complete_count,
                COUNT(*) FILTER (WHERE rc.r1_round_id IS NOT NULL) AS r1_expected_sides,
                COUNT(*) FILTER (
                    WHERE rc.r1_round_id IS NOT NULL AND COALESCE(rc.has_r1_proximity, FALSE)
                ) AS r1_proximity_present,
                COUNT(*) FILTER (WHERE rc.r2_round_id IS NOT NULL) AS r2_expected_sides,
                COUNT(*) FILTER (
                    WHERE rc.r2_round_id IS NOT NULL AND COALESCE(rc.has_r2_proximity, FALSE)
                ) AS r2_proximity_present,
                COALESCE(ROUND(AVG(COALESCE(rc.completeness_pct, 0))::numeric, 2), 0) AS avg_completeness_pct,
                MAX(rc.created_at) AS latest_created_at
            FROM round_correlations rc
            LEFT JOIN rounds r1 ON rc.r1_round_id = r1.id
            LEFT JOIN rounds r2 ON rc.r2_round_id = r2.id
            {where_sql}
            """,  # nosec B608 - where_sql is built only from hardcoded clauses.
            params,
        )
    except Exception as exc:
        logger.warning("proximity quality round correlation query failed: %s", exc)
        return {
            "status": "error",
            "ready": False,
            "correlation_count": 0,
            "complete_count": 0,
            "expected_round_sides": 0,
            "present_proximity_sides": 0,
            "missing_existing_round_sides": 0,
            "unpaired_round_sides": 0,
            "avg_completeness_pct": 0.0,
            "latest_created_at": None,
            "error": "query_failed",
        }

    correlation_count = _safe_int(_row_get(row, 0, "correlation_count"))
    complete_count = _safe_int(_row_get(row, 1, "complete_count"))
    r1_expected_sides = _safe_int(_row_get(row, 2, "r1_expected_sides"))
    r1_proximity_present = _safe_int(_row_get(row, 3, "r1_proximity_present"))
    r2_expected_sides = _safe_int(_row_get(row, 4, "r2_expected_sides"))
    r2_proximity_present = _safe_int(_row_get(row, 5, "r2_proximity_present"))

    # §18.3 fix: a side that has NO round (r1_round_id/r2_round_id IS NULL —
    # e.g. a genuinely partial R1-only match with no R2 to attach Proximity
    # to) must NEVER be counted as missing telemetry. Only an EXISTING round
    # side that lacks its proximity flag is a real completeness gap.
    expected_round_sides = r1_expected_sides + r2_expected_sides
    present_proximity_sides = r1_proximity_present + r2_proximity_present
    missing_existing_round_sides = expected_round_sides - present_proximity_sides
    # Informational only (not a telemetry failure): sides where the round
    # itself was never paired (correlation_count*2 total possible sides).
    unpaired_round_sides = (correlation_count * 2) - expected_round_sides

    status = "ok"
    ready = True
    if correlation_count <= 0:
        status = "missing"
        ready = False
    elif missing_existing_round_sides > 0:
        status = "proximity_flags_incomplete"
        ready = False

    return {
        "status": status,
        "ready": ready,
        "correlation_count": correlation_count,
        "complete_count": complete_count,
        "expected_round_sides": expected_round_sides,
        "present_proximity_sides": present_proximity_sides,
        "missing_existing_round_sides": missing_existing_round_sides,
        "unpaired_round_sides": unpaired_round_sides,
        "avg_completeness_pct": _safe_float(_row_get(row, 6, "avg_completeness_pct")),
        "latest_created_at": _isoformat(_row_get(row, 7, "latest_created_at")),
    }


def _sanitize_linkage(payload: dict[str, Any]) -> dict[str, Any]:
    breaches = []
    for breach in payload.get("breaches", []) or []:
        if not isinstance(breach, dict):
            continue
        breaches.append(
            {
                "metric": breach.get("metric"),
                "value": breach.get("value"),
                "threshold": breach.get("threshold"),
            }
        )
    return {
        "scope": "global",
        "status": payload.get("status", "unknown"),
        "metrics": dict(payload.get("metrics", {}) or {}),
        "breach_count": len(breaches),
        "breaches": breaches,
        "errors": list(payload.get("errors", []) or []),
    }


def _evaluate_cache_freshness(signals: dict[str, dict[str, Any]]) -> dict[str, Any]:
    context_latest: datetime | None = None
    for key, signal in signals.items():
        if key not in _KIS_CONTEXT_SIGNAL_KEYS:
            continue
        candidate = _to_datetime(signal.get("latest_created_at"))
        if candidate and (context_latest is None or candidate > context_latest):
            context_latest = candidate

    kis_latest = _to_datetime(
        signals.get("storytelling_kill_impact", {}).get("latest_created_at")
    )
    if context_latest is None:
        status = "unknown"
    elif kis_latest is None:
        status = "missing"
    elif kis_latest < context_latest:
        status = "stale"
    else:
        status = "ok"

    return {
        "status": status,
        "latest_context_created_at": context_latest.isoformat() if context_latest else None,
        "latest_kis_created_at": kis_latest.isoformat() if kis_latest else None,
    }


def _build_warnings(
    signals: dict[str, dict[str, Any]],
    round_correlation: dict[str, Any],
    linkage: dict[str, Any],
    cache_freshness: dict[str, Any],
) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    for key, signal in signals.items():
        status = signal.get("status")
        if status == "ok":
            continue
        if status == "error":
            warnings.append(
                _warning("SIGNAL_QUERY_FAILED", f"{key} quality signal is unavailable.")
            )
        elif status == "missing":
            code = (
                "EXPERIMENTAL_SIGNAL_MISSING"
                if signal.get("experimental")
                else "SIGNAL_MISSING"
            )
            level = "info" if signal.get("experimental") else "warning"
            warnings.append(_warning(code, f"{key} has no rows in the selected scope.", level))
        elif status == "low_count":
            warnings.append(
                _warning(
                    "SIGNAL_LOW_COUNT",
                    f"{key} has fewer rows than the minimum expected for the selected scope.",
                )
            )
        elif status == "round_linkage_partial":
            warnings.append(
                _warning(
                    "SIGNAL_ROUND_LINKAGE_PARTIAL",
                    f"{key} has rows without round_id linkage in the selected scope.",
                )
            )

    if round_correlation.get("status") == "error":
        warnings.append(
            _warning(
                "ROUND_CORRELATION_QUERY_FAILED",
                "Round correlation readiness is unavailable.",
            )
        )
    elif round_correlation.get("status") == "missing":
        warnings.append(
            _warning(
                "ROUND_CORRELATION_MISSING",
                "No round correlation row matches the selected scope.",
            )
        )
    elif round_correlation.get("status") == "proximity_flags_incomplete":
        warnings.append(
            _warning(
                "ROUND_CORRELATION_PROXIMITY_INCOMPLETE",
                "Round correlation proximity flags are incomplete for the selected scope.",
            )
        )

    if linkage.get("status") == "error":
        warnings.append(
            _warning(
                "LINKAGE_ANOMALY_CHECK_FAILED",
                "Round linkage anomaly checks returned errors.",
            )
        )
    elif linkage.get("breach_count", 0) > 0:
        warnings.append(
            _warning(
                "LINKAGE_ANOMALY_BREACH",
                "Round linkage anomaly thresholds were breached.",
            )
        )

    cache_status = cache_freshness.get("status")
    if cache_status == "missing":
        warnings.append(
            _warning("KIS_CACHE_MISSING", "Kill impact cache is missing for the selected scope.")
        )
    elif cache_status == "stale":
        warnings.append(
            _warning(
                "KIS_CACHE_STALE",
                "Kill impact cache is older than the latest proximity context.",
            )
        )
    elif cache_status == "unknown":
        warnings.append(
            _warning(
                "KIS_CACHE_UNKNOWN",
                "Kill impact cache freshness could not be determined.",
                "info",
            )
        )

    return warnings


def _selected_scope_status(
    signals: dict[str, dict[str, Any]],
    round_correlation: dict[str, Any],
    cache_freshness: dict[str, Any],
) -> str:
    """Quality of the data for the SCOPE the caller actually selected —
    signals + round correlation + cache freshness. Deliberately excludes
    `linkage`, which `_sanitize_linkage` always scopes globally: a caller
    looking at one date must not see "partial" caused entirely by unrelated
    historical linkage debt elsewhere in the database (Codex §18.7 — the
    response must separate selected-scope health from global maintenance
    debt, which previously appeared "beneath the selected date" but was
    conflated into one status)."""
    if (
        any(signal.get("status") == "error" for signal in signals.values())
        or round_correlation.get("status") == "error"
    ):
        return "error"

    if any(
        signal.get("core")
        and signal.get("required")
        and signal.get("status") in {"missing", "low_count"}
        for signal in signals.values()
    ):
        return "insufficient"

    partial_signal = any(
        signal.get("required") and not signal.get("ready")
        for signal in signals.values()
    )
    if (
        partial_signal
        or not round_correlation.get("ready", False)
        or cache_freshness.get("status") in {"missing", "stale"}
    ):
        return "partial"

    if any(
        signal.get("experimental") and signal.get("status") != "ok"
        for signal in signals.values()
    ):
        return "experimental"

    return "ready"


def _global_maintenance_status(linkage: dict[str, Any]) -> str:
    """Health of the GLOBAL, all-history round-linkage anomaly checks — never
    scoped to the caller's selected date/round (Codex §18.7)."""
    if linkage.get("status") == "error":
        return "error"
    if linkage.get("breach_count", 0) > 0:
        return "warning"
    return "ok"


def _overall_status(
    signals: dict[str, dict[str, Any]],
    round_correlation: dict[str, Any],
    linkage: dict[str, Any],
    cache_freshness: dict[str, Any],
) -> str:
    """Backward-compatible combined status (existing consumers read this
    field). New callers should prefer `selected_scope_status` +
    `global_maintenance_status`, which this is derived from."""
    selected = _selected_scope_status(signals, round_correlation, cache_freshness)
    if selected == "error" or linkage.get("status") == "error":
        return "error"
    if selected == "insufficient":
        return "insufficient"
    if selected == "partial" or linkage.get("breach_count", 0) > 0:
        return "partial"
    return selected


@router.get("/proximity/quality")
async def get_proximity_quality(
    range_days: Annotated[int, Query(ge=1, le=3650)] = 30,
    session_date: Annotated[str | None, Query()] = None,
    map_name: Annotated[str | None, Query()] = None,
    round_number: Annotated[int | None, Query(ge=0)] = None,
    round_start_unix: Annotated[int | None, Query(ge=0)] = None,
    db: DatabaseAdapter = Depends(get_db),
) -> dict[str, Any]:
    """Aggregate read-only proximity trust/readiness status."""
    _where_sql, _params, scope = _build_proximity_where_clause(
        range_days,
        session_date,
        map_name,
        round_number,
        round_start_unix,
    )
    scope = {"range_days": int(range_days), **scope}
    if _is_sqlite_adapter(db):
        return _sqlite_unsupported_payload(scope)

    try:
        signals = await _collect_signals(
            db,
            range_days=range_days,
            session_date=session_date,
            map_name=map_name,
            round_number=round_number,
            round_start_unix=round_start_unix,
        )
        round_correlation = await _collect_round_correlation(
            db,
            range_days=range_days,
            session_date=session_date,
            map_name=map_name,
            round_number=round_number,
            round_start_unix=round_start_unix,
        )
        linkage = _sanitize_linkage(await assess_round_linkage_anomalies(db, sample_limit=1))
        cache_freshness = _evaluate_cache_freshness(signals)
        warnings = _build_warnings(signals, round_correlation, linkage, cache_freshness)
        overall_status = _overall_status(signals, round_correlation, linkage, cache_freshness)
        return {
            "overall_status": overall_status,
            # Codex §18.7: separate scopes so a caller looking at one date
            # doesn't read "partial" caused entirely by unrelated global
            # linkage debt (and vice versa — global debt must not hide
            # behind a healthy-looking selected scope).
            "selected_scope_status": _selected_scope_status(signals, round_correlation, cache_freshness),
            "global_maintenance_status": _global_maintenance_status(linkage),
            "scope": scope,
            "signals": signals,
            "round_correlation": round_correlation,
            "linkage": linkage,
            "cache_freshness": cache_freshness,
            "warnings": warnings,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        logger.error("proximity quality endpoint failed: %s", exc, exc_info=True)
        return {
            "overall_status": "error",
            "selected_scope_status": "error",
            "global_maintenance_status": "unknown",
            "scope": scope,
            "signals": {},
            "round_correlation": {"status": "error", "ready": False},
            "linkage": {
                "scope": "global",
                "status": "unknown",
                "metrics": {},
                "breach_count": 0,
                "breaches": [],
                "errors": [],
            },
            "cache_freshness": {"status": "unknown"},
            "warnings": [
                _warning("PROXIMITY_QUALITY_FAILED", "Proximity quality checks failed.")
            ],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
