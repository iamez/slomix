#!/usr/bin/env python3
"""
Recompute safe derived metrics for proximity player_track rows from stored path JSON.

This script intentionally updates only player_track-derived columns:
- sample_count
- duration_ms
- first_move_time_ms (only when missing and inferable from path)
- time_to_first_move_ms
- total_distance
- avg_speed
- sprint_percentage

It does not touch combat_engagement or aggregate forever tables.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from proximity.parser.parser import PathPoint, PlayerTrack
from website.backend.dependencies import close_db_pool, get_db


TERMINAL_EVENTS = {
    "killed",
    "selfkill",
    "fallen",
    "world",
    "teamkill",
    "disconnect",
    "round_end",
    "death",
}


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _load_path(raw_path: Any) -> list[dict[str, Any]]:
    if raw_path is None:
        return []
    if isinstance(raw_path, str):
        try:
            parsed = json.loads(raw_path)
        except json.JSONDecodeError:
            return []
    else:
        parsed = raw_path
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, dict)]


def _infer_first_move_time(path_points: Iterable[PathPoint]) -> int | None:
    for point in path_points:
        if point.event in TERMINAL_EVENTS:
            continue
        if point.speed > 10:
            return point.time
    return None


def _build_track(row: Any) -> PlayerTrack:
    raw_points = _load_path(row["path"])
    path_points: list[PathPoint] = []
    for item in raw_points:
        path_points.append(
            PathPoint(
                time=_coerce_int(item.get("time")),
                x=_coerce_float(item.get("x")),
                y=_coerce_float(item.get("y")),
                z=_coerce_float(item.get("z")),
                health=_coerce_int(item.get("health"), 100),
                speed=_coerce_float(item.get("speed")),
                weapon=_coerce_int(item.get("weapon")),
                stance=_coerce_int(item.get("stance")),
                sprint=_coerce_int(item.get("sprint")),
                event=str(item.get("event") or "sample"),
            )
        )
    path_points.sort(key=lambda point: point.time)

    spawn_time_ms = row["spawn_time_ms"]
    if spawn_time_ms is None and path_points:
        spawn_time_ms = path_points[0].time

    death_time_ms = row["death_time_ms"]
    if death_time_ms is None and path_points:
        death_time_ms = path_points[-1].time

    first_move_time_ms = row["first_move_time_ms"]
    if first_move_time_ms is None:
        first_move_time_ms = _infer_first_move_time(path_points)

    return PlayerTrack(
        guid=row["player_guid"],
        name=row["player_name"],
        team=row["team"],
        player_class=row["player_class"],
        spawn_time=_coerce_int(spawn_time_ms),
        death_time=(
            _coerce_int(death_time_ms) if death_time_ms is not None else None
        ),
        first_move_time=(
            _coerce_int(first_move_time_ms) if first_move_time_ms is not None else None
        ),
        death_type=None,
        sample_count=len(path_points),
        path=path_points,
    )


def _float_changed(old_value: Any, new_value: float, precision: int = 3) -> bool:
    if old_value is None:
        return True
    try:
        old_number = float(old_value)
    except (TypeError, ValueError):
        return True
    return not math.isclose(old_number, new_value, rel_tol=0.0, abs_tol=10 ** (-precision))


def _int_changed(old_value: Any, new_value: int | None) -> bool:
    if old_value is None:
        return new_value is not None
    if new_value is None:
        return False
    try:
        return int(old_value) != int(new_value)
    except (TypeError, ValueError):
        return True


def _build_changes(row: Any, track: PlayerTrack) -> dict[str, Any]:
    updates = {
        "sample_count": len(track.path),
        "duration_ms": track.duration_ms,
        "first_move_time_ms": track.first_move_time,
        "time_to_first_move_ms": track.time_to_first_move_ms,
        "total_distance": track.total_distance,
        "avg_speed": track.avg_speed,
        "sprint_percentage": track.sprint_percentage,
    }

    changes: dict[str, Any] = {}
    for key, new_value in updates.items():
        old_value = row[key]
        if isinstance(new_value, float):
            if _float_changed(old_value, new_value):
                changes[key] = new_value
        else:
            if _int_changed(old_value, new_value):
                changes[key] = new_value
    return changes


async def _get_rows(args) -> list[Any]:
    async for db in get_db():
        params: list[Any] = []
        where_clauses = ["pt.path IS NOT NULL"]
        param_idx = 1

        if args.session_id is not None:
            where_clauses.append(f"r.gaming_session_id = ${param_idx}")
            params.append(args.session_id)
            param_idx += 1
        if args.session_date:
            where_clauses.append(f"pt.session_date = CAST(${param_idx} AS DATE)")
            params.append(args.session_date)
            param_idx += 1
        if args.round_id is not None:
            where_clauses.append(f"pt.round_id = ${param_idx}")
            params.append(args.round_id)
            param_idx += 1
        if args.player_guid:
            where_clauses.append(f"pt.player_guid = ${param_idx}")
            params.append(args.player_guid)
            param_idx += 1

        if not args.allow_all and len(where_clauses) == 1:
            raise SystemExit(
                "Refusing to scan all player_track rows without an explicit scope. "
                "Use --session-id/--session-date/--round-id or pass --allow-all."
            )

        limit_clause = ""
        if args.limit is not None:
            limit_clause = f" LIMIT ${param_idx}"
            params.append(args.limit)

        query = f"""
            SELECT
                pt.id,
                pt.round_id,
                pt.player_guid,
                pt.player_name,
                pt.team,
                pt.player_class,
                pt.spawn_time_ms,
                pt.death_time_ms,
                pt.duration_ms,
                pt.first_move_time_ms,
                pt.time_to_first_move_ms,
                pt.sample_count,
                pt.total_distance,
                pt.avg_speed,
                pt.sprint_percentage,
                pt.path
            FROM player_track pt
            LEFT JOIN rounds r ON r.id = pt.round_id
            WHERE {" AND ".join(where_clauses)}
            ORDER BY pt.id
            {limit_clause}
        """
        return await db.fetch_all(query, tuple(params))
    return []


async def _apply_updates(args, updates: list[tuple[int, dict[str, Any]]]) -> None:
    if not updates:
        return

    async for db in get_db():
        tx_factory = getattr(db, "transaction", None)
        if callable(tx_factory):
            async with tx_factory():
                for row_id, changes in updates:
                    await _update_row(db, row_id, changes)
        else:
            for row_id, changes in updates:
                await _update_row(db, row_id, changes)
        return


async def _update_row(db, row_id: int, changes: dict[str, Any]) -> None:
    assignments = []
    params: list[Any] = []
    for idx, (column, value) in enumerate(changes.items(), start=1):
        assignments.append(f"{column} = ${idx}")
        params.append(value)
    params.append(row_id)
    query = f"""
        UPDATE player_track
        SET {", ".join(assignments)}
        WHERE id = ${len(params)}
    """
    await db.execute(query, tuple(params))


def _format_preview(row: Any, changes: dict[str, Any]) -> str:
    parts = [
        f"id={row['id']}",
        f"round_id={row['round_id']}",
        f"player={row['player_name']}",
    ]
    for key, new_value in changes.items():
        parts.append(f"{key}:{row[key]}->{round(new_value, 3) if isinstance(new_value, float) else new_value}")
    return " | ".join(parts)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-id", type=int, help="Restrict to a gaming_session_id")
    parser.add_argument("--session-date", help="Restrict to a YYYY-MM-DD session_date")
    parser.add_argument("--round-id", type=int, help="Restrict to a specific round_id")
    parser.add_argument("--player-guid", help="Restrict to a specific player GUID")
    parser.add_argument("--limit", type=int, help="Limit scanned rows for debugging")
    parser.add_argument("--allow-all", action="store_true", help="Allow scanning all player_track rows")
    parser.add_argument("--apply", action="store_true", help="Write changes back to the database")
    parser.add_argument("--preview", type=int, default=15, help="Number of changed rows to print")
    args = parser.parse_args()

    rows = await _get_rows(args)
    updates: list[tuple[int, dict[str, Any]]] = []

    for row in rows:
        track = _build_track(row)
        changes = _build_changes(row, track)
        if changes:
            updates.append((int(row["id"]), changes))

    print(f"scanned_rows={len(rows)}")
    print(f"changed_rows={len(updates)}")
    for row_id, changes in updates[: max(0, args.preview)]:
        row = next(item for item in rows if int(item["id"]) == row_id)
        print(_format_preview(row, changes))

    if args.apply and updates:
        await _apply_updates(args, updates)
        print("apply_status=done")
    elif args.apply:
        print("apply_status=no_changes")
    else:
        print("apply_status=dry_run")

    await close_db_pool()


if __name__ == "__main__":
    asyncio.run(main())
