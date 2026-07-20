"""Read-only wrong-round-linkage inventory (Codex SS-E follow-up, §L4).

Enumerates rows whose stored `round_start_unix` disagrees with the
`round_start_unix` of the round they are actually linked to via `round_id`
— the same "the FK proves *a* link, never the CORRECT one" signal L1's
`proximity_quality.py::_collect_signal` uses (Codex §18.6). For each wrong
row this also looks up whether there is a *deterministic* correct target:
exactly one row in `rounds` whose `(round_start_unix, map_name,
round_number)` matches the source row — the same three-column shape as the
repo-wide canonical round key (`round_ctx_key`, see
`website/backend/services/storytelling/loaders.py` docstring). Zero or
more-than-one candidates means no safe automatic target exists (L3's
"never guess" principle applies here too).

This module makes NO writes. It is inventory/preparation for a later,
separate, owner-gated repair step (L5/L6) — it does not attempt any repair
itself.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

# Tables carrying round_id + round_start_unix, i.e. the same "comparable"
# sources L1's proximity_quality signal collector checks (has_round_id=True
# entries in _SIGNAL_SOURCES, minus storytelling_kill_impact which has no
# round_id of its own).
LINKAGE_INVENTORY_TABLES: tuple[str, ...] = (
    "combat_engagement",
    "player_track",
    "proximity_kill_outcome",
    "proximity_spawn_timing",
    "proximity_team_push",
    "proximity_crossfire_opportunity",
    "proximity_reaction_metric",
    "proximity_shot_fired",
    "proximity_hit_region",
)


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
    except (KeyError, IndexError, TypeError):
        pass
    try:
        return row[index]  # tuple/list fallback
    except (IndexError, TypeError):
        return default


def _date_range_where(since_date: str | None, until_date: str | None, params: list) -> str:
    clauses = []
    if since_date:
        clauses.append("src.session_date >= ?")
        params.append(since_date)
    if until_date:
        clauses.append("src.session_date <= ?")
        params.append(until_date)
    return (" AND " + " AND ".join(clauses)) if clauses else ""


async def _counts_by_date(db: Any, table: str, since_date: str | None, until_date: str | None) -> list[dict[str, Any]]:
    params: list = []
    date_where = _date_range_where(since_date, until_date, params)
    # nosec B608 - table is a hardcoded constant from LINKAGE_INVENTORY_TABLES.
    query = f"""
        /* linkage_inventory_counts:{table} */
        SELECT
            src.session_date AS session_date,
            COUNT(*) AS wrong_rows,
            COUNT(*) FILTER (WHERE cand.candidate_count = 1) AS deterministic_target_available,
            COUNT(*) FILTER (WHERE cand.candidate_count > 1) AS ambiguous_multiple_targets,
            COUNT(*) FILTER (WHERE cand.candidate_count = 0) AS no_target_found
        FROM {table} src
        JOIN rounds r ON src.round_id = r.id
        CROSS JOIN LATERAL (
            SELECT COUNT(*) AS candidate_count
            FROM rounds t
            WHERE t.round_start_unix = src.round_start_unix
              AND t.map_name = src.map_name
              AND t.round_number = src.round_number
        ) cand
        WHERE src.round_id IS NOT NULL
          AND src.round_start_unix IS NOT NULL
          AND src.round_start_unix > 0
          AND r.round_start_unix IS NOT NULL
          AND src.round_start_unix <> r.round_start_unix
          {date_where}
        GROUP BY src.session_date
        ORDER BY src.session_date
    """
    rows = await db.fetch_all(query, tuple(params))
    return [
        {
            "session_date": str(_row_get(row, 0, "session_date")),
            "wrong_rows": _safe_int(_row_get(row, 1, "wrong_rows")),
            "deterministic_target_available": _safe_int(
                _row_get(row, 2, "deterministic_target_available")),
            "ambiguous_multiple_targets": _safe_int(
                _row_get(row, 3, "ambiguous_multiple_targets")),
            "no_target_found": _safe_int(_row_get(row, 4, "no_target_found")),
        }
        for row in (rows or [])
    ]


async def _sample_rows(
    db: Any, table: str, since_date: str | None, until_date: str | None, sample_limit: int,
) -> list[dict[str, Any]]:
    params: list = []
    date_where = _date_range_where(since_date, until_date, params)
    params.append(max(0, sample_limit))
    # nosec B608 - table is a hardcoded constant from LINKAGE_INVENTORY_TABLES.
    query = f"""
        /* linkage_inventory_sample:{table} */
        SELECT
            src.id AS row_id,
            src.session_date AS session_date,
            src.map_name AS map_name,
            src.round_number AS round_number,
            src.round_start_unix AS src_start_unix,
            src.round_id AS current_round_id,
            r.round_start_unix AS linked_start_unix,
            (SELECT COUNT(*) FROM rounds t
               WHERE t.round_start_unix = src.round_start_unix
                 AND t.map_name = src.map_name
                 AND t.round_number = src.round_number) AS candidate_count,
            (SELECT t.id FROM rounds t
               WHERE t.round_start_unix = src.round_start_unix
                 AND t.map_name = src.map_name
                 AND t.round_number = src.round_number
               ORDER BY t.id LIMIT 1) AS candidate_round_id
        FROM {table} src
        JOIN rounds r ON src.round_id = r.id
        WHERE src.round_id IS NOT NULL
          AND src.round_start_unix IS NOT NULL
          AND src.round_start_unix > 0
          AND r.round_start_unix IS NOT NULL
          AND src.round_start_unix <> r.round_start_unix
          {date_where}
        ORDER BY src.session_date, src.id
        LIMIT ?
    """
    rows = await db.fetch_all(query, tuple(params))
    return [
        {
            "row_id": _safe_int(_row_get(row, 0, "row_id")),
            "session_date": str(_row_get(row, 1, "session_date")),
            "map_name": _row_get(row, 2, "map_name"),
            "round_number": _safe_int(_row_get(row, 3, "round_number")),
            "src_start_unix": _safe_int(_row_get(row, 4, "src_start_unix")),
            "current_round_id": _safe_int(_row_get(row, 5, "current_round_id")),
            "linked_start_unix": _safe_int(_row_get(row, 6, "linked_start_unix")),
            "candidate_count": _safe_int(_row_get(row, 7, "candidate_count")),
            "candidate_round_id": (
                _safe_int(_row_get(row, 8, "candidate_round_id"))
                if _row_get(row, 8, "candidate_round_id") is not None else None
            ),
        }
        for row in (rows or [])
    ]


async def build_linkage_inventory(
    db: Any,
    *,
    since_date: str | None = None,
    until_date: str | None = None,
    sample_limit: int = 10,
    tables: tuple[str, ...] = LINKAGE_INVENTORY_TABLES,
) -> dict[str, Any]:
    """Read-only wrong-round-linkage inventory, grouped by table and date.

    No writes. `tables` defaults to every has_round_id source; callers may
    pass a subset (e.g. for a targeted re-run against one table).
    """
    report: dict[str, Any] = {"tables": {}}
    totals = {
        "wrong_rows": 0,
        "deterministic_target_available": 0,
        "ambiguous_multiple_targets": 0,
        "no_target_found": 0,
    }

    for table in tables:
        if table not in LINKAGE_INVENTORY_TABLES:
            # `table` is f-string interpolated into raw SQL below — an
            # allowlist check here (not just at the CLI layer) is the only
            # thing standing between a future caller passing untrusted
            # input and SQL injection (Copilot PR #532 finding).
            report["tables"][table] = {"status": "error", "error": "unknown_table"}
            continue
        try:
            by_date = await _counts_by_date(db, table, since_date, until_date)
            samples = await _sample_rows(db, table, since_date, until_date, sample_limit)
        except Exception as exc:  # noqa: BLE001 - surfaced per-table, not fatal to the whole report
            report["tables"][table] = {"status": "error", "error": str(exc)}
            continue

        table_totals = {
            "wrong_rows": sum(d["wrong_rows"] for d in by_date),
            "deterministic_target_available": sum(
                d["deterministic_target_available"] for d in by_date),
            "ambiguous_multiple_targets": sum(
                d["ambiguous_multiple_targets"] for d in by_date),
            "no_target_found": sum(d["no_target_found"] for d in by_date),
        }
        for key, value in table_totals.items():
            totals[key] += value

        report["tables"][table] = {
            "status": "ok",
            **table_totals,
            "by_date": by_date,
            "sample_rows": samples,
        }

    report["totals"] = totals
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    report["scope"] = {"since_date": since_date, "until_date": until_date, "sample_limit": sample_limit}
    return report
