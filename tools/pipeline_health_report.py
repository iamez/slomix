#!/usr/bin/env python3
"""Pipeline health report for recent rounds.

Prints stage completeness and freshness values for the latest rounds:
- stats imported
- lua linked
- endstats processed
- endstats rows count (awards + vs rows)
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot.config import load_config
from bot.core.database_adapter import create_adapter


def _format_bool(value: bool) -> str:
    return "yes" if value else "no"


def _format_age(seconds: float | None) -> str:
    if seconds is None:
        return "-"
    if seconds < 0:
        seconds = 0
    total = int(seconds)
    minutes, sec = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    if days > 0:
        return f"{days}d{hours:02d}h"
    if hours > 0:
        return f"{hours}h{minutes:02d}m"
    return f"{minutes}m{sec:02d}s"


def _parse_round_timestamp(round_end_unix, round_date, round_time) -> datetime | None:
    if round_end_unix:
        try:
            return datetime.fromtimestamp(int(round_end_unix), tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            pass

    if not round_date:
        return None

    time_value = (round_time or "00:00:00").strip()
    candidates = (
        f"{round_date} {time_value}",
        f"{round_date} {time_value}:00",
    )
    formats = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
    )
    for text in candidates:
        for fmt in formats:
            try:
                return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return None


def _normalize_db_datetime(value) -> datetime | None:
    if value is None:
        return None

    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    if not isinstance(value, datetime):
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def _run(limit: int) -> int:
    config = load_config()
    adapter = create_adapter(**config.get_database_adapter_kwargs())
    await adapter.connect()

    query = """
        WITH recent_rounds AS (
            SELECT
                r.id AS round_id,
                r.map_name,
                r.round_number,
                r.round_date,
                r.round_time,
                r.round_status,
                r.round_end_unix
            FROM rounds r
            ORDER BY r.id DESC
            LIMIT $1
        ),
        stats_counts AS (
            SELECT
                p.round_id,
                COUNT(*)::int AS stats_rows
            FROM player_comprehensive_stats p
            WHERE p.round_id IN (SELECT round_id FROM recent_rounds)
            GROUP BY p.round_id
        ),
        lua_counts AS (
            SELECT
                l.round_id,
                COUNT(*)::int AS lua_rows,
                MAX(l.captured_at) AS lua_last_captured_at
            FROM lua_round_teams l
            WHERE l.round_id IN (SELECT round_id FROM recent_rounds)
            GROUP BY l.round_id
        ),
        endstats_flags AS (
            SELECT
                p.round_id,
                BOOL_OR(p.success) AS endstats_processed,
                MAX(p.processed_at) AS endstats_processed_at
            FROM processed_endstats_files p
            WHERE p.round_id IN (SELECT round_id FROM recent_rounds)
            GROUP BY p.round_id
        ),
        awards_counts AS (
            SELECT
                a.round_id,
                COUNT(*)::int AS awards_rows
            FROM round_awards a
            WHERE a.round_id IN (SELECT round_id FROM recent_rounds)
            GROUP BY a.round_id
        ),
        vs_counts AS (
            SELECT
                v.round_id,
                COUNT(*)::int AS vs_rows
            FROM round_vs_stats v
            WHERE v.round_id IN (SELECT round_id FROM recent_rounds)
            GROUP BY v.round_id
        )
        SELECT
            rr.round_id,
            rr.map_name,
            rr.round_number,
            rr.round_date,
            rr.round_time,
            rr.round_status,
            rr.round_end_unix,
            COALESCE(sc.stats_rows, 0) AS stats_rows,
            COALESCE(lc.lua_rows, 0) AS lua_rows,
            COALESCE(ef.endstats_processed, FALSE) AS endstats_processed,
            ef.endstats_processed_at,
            lc.lua_last_captured_at,
            COALESCE(ac.awards_rows, 0) AS awards_rows,
            COALESCE(vc.vs_rows, 0) AS vs_rows
        FROM recent_rounds rr
        LEFT JOIN stats_counts sc ON sc.round_id = rr.round_id
        LEFT JOIN lua_counts lc ON lc.round_id = rr.round_id
        LEFT JOIN endstats_flags ef ON ef.round_id = rr.round_id
        LEFT JOIN awards_counts ac ON ac.round_id = rr.round_id
        LEFT JOIN vs_counts vc ON vc.round_id = rr.round_id
        ORDER BY rr.round_id DESC
    """

    try:
        rows = await adapter.fetch_all(query, (limit,))
    finally:
        await adapter.close()

    now = datetime.now(timezone.utc)
    print(f"Pipeline Health Report - {now.isoformat()}")
    print(f"Rounds inspected: {len(rows)}")
    print(
        "ID    Map           R  Status         Stats Lua Endstats EndRows RoundAge  LuaAge    EndstatsAge"
    )
    print(
        "----  ------------  -  -------------  ----- --- -------- ------- --------  --------  -----------"
    )

    complete_rounds = 0
    for row in rows:
        round_id = row["round_id"]
        map_name = (row["map_name"] or "unknown")[:12]
        round_number = row["round_number"] or 0
        status = row["round_status"] if row["round_status"] is not None else "null"
        stats_rows = int(row["stats_rows"] or 0)
        lua_rows = int(row["lua_rows"] or 0)
        endstats_processed = bool(row["endstats_processed"])
        endstats_rows = int(row["awards_rows"] or 0) + int(row["vs_rows"] or 0)

        stats_imported = stats_rows > 0
        lua_linked = lua_rows > 0
        if stats_imported and lua_linked and endstats_processed and endstats_rows > 0:
            complete_rounds += 1

        round_ts = _parse_round_timestamp(
            row["round_end_unix"], row["round_date"], row["round_time"]
        )
        round_age = _format_age((now - round_ts).total_seconds()) if round_ts else "-"

        lua_age = None
        lua_last_captured_at = _normalize_db_datetime(row["lua_last_captured_at"])
        if lua_last_captured_at:
            lua_age = (now - lua_last_captured_at).total_seconds()

        endstats_age = None
        endstats_processed_at = _normalize_db_datetime(row["endstats_processed_at"])
        if endstats_processed_at:
            endstats_age = (now - endstats_processed_at).total_seconds()

        print(
            f"{round_id:>4}  "
            f"{map_name:<12}  "
            f"{round_number:>1}  "
            f"{status:<13}  "
            f"{_format_bool(stats_imported):>5} "
            f"{_format_bool(lua_linked):>3} "
            f"{_format_bool(endstats_processed):>8} "
            f"{endstats_rows:>7} "
            f"{round_age:>8}  "
            f"{_format_age(lua_age):>8}  "
            f"{_format_age(endstats_age):>11}"
        )

    print("")
    print(
        f"Complete rounds (all stages + endstats rows): {complete_rounds}/{len(rows)}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Show stage completeness/freshness for recent ETL rounds."
    )
    parser.add_argument(
        "-n",
        "--limit",
        type=int,
        default=int(os.environ.get("PIPELINE_HEALTH_LIMIT", "20")),
        help="Number of most recent rounds to inspect (default: 20).",
    )
    args = parser.parse_args()
    limit = max(1, int(args.limit))
    return asyncio.run(_run(limit))


if __name__ == "__main__":
    raise SystemExit(main())
