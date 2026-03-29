#!/usr/bin/env python3
"""Backfill endstats files into round_awards and round_vs_stats.

Usage:
  python3 scripts/backfill_endstats.py --date 2026-02-02
  python3 scripts/backfill_endstats.py --since 2026-01-25 --until 2026-02-02
  python3 scripts/backfill_endstats.py --stats-dir local_stats --dry-run

Notes:
- Skips files already in processed_endstats_files.
- Skips rounds that already have awards (prevents duplicate inserts).
- Does NOT post to Discord; DB-only backfill.
"""

from __future__ import annotations

import argparse
import asyncio
import glob
import logging
import os
import re
from typing import Iterable

from bot.config import BotConfig
from bot.core.database_adapter import PostgreSQLAdapter
from bot.core.round_linker import resolve_round_id
from bot.endstats_parser import parse_endstats_file

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)
FILENAME_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2})-(\d{6})-(.+)-round-(\d+)-endstats\.txt$"
)


def iter_endstats_files(
    stats_dir: str,
    *,
    date_exact: str | None = None,
    date_since: str | None = None,
    date_until: str | None = None,
    limit: int | None = None,
) -> Iterable[str]:
    files = sorted(glob.glob(os.path.join(stats_dir, "*-endstats.txt")))
    count = 0
    for path in files:
        filename = os.path.basename(path)
        match = FILENAME_RE.match(filename)
        if not match:
            continue
        date_str = match.group(1)

        if date_exact and date_str != date_exact:
            continue
        if date_since and date_str < date_since:
            continue
        if date_until and date_str > date_until:
            continue

        yield path
        count += 1
        if limit is not None and count >= limit:
            break


def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats-dir", default="local_stats")
    ap.add_argument("--date", dest="date_exact", default=None)
    ap.add_argument("--since", dest="date_since", default=None)
    ap.add_argument("--until", dest="date_until", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--db-type", choices=["postgres", "postgresql"], default=None)
    return ap.parse_args()


async def backfill_postgres(
    stats_dir: str,
    *,
    date_exact: str | None,
    date_since: str | None,
    date_until: str | None,
    limit: int | None,
    dry_run: bool,
) -> int:
    config = BotConfig()
    adapter = PostgreSQLAdapter(
        host=config.postgres_host,
        port=config.postgres_port,
        database=config.postgres_database,
        user=config.postgres_user,
        password=config.postgres_password,
        min_pool_size=config.postgres_min_pool,
        max_pool_size=config.postgres_max_pool,
        ssl_mode=getattr(config, "postgres_ssl_mode", "disable"),
        ssl_cert=getattr(config, "postgres_ssl_cert", ""),
        ssl_key=getattr(config, "postgres_ssl_key", ""),
        ssl_root_cert=getattr(config, "postgres_ssl_root_cert", ""),
    )

    await adapter.connect()

    files_processed = 0
    awards_inserted = 0
    vs_inserted = 0
    rounds_missing = 0
    skipped_processed = 0
    skipped_existing = 0
    parse_failed = 0

    for path in iter_endstats_files(
        stats_dir,
        date_exact=date_exact,
        date_since=date_since,
        date_until=date_until,
        limit=limit,
    ):
        filename = os.path.basename(path)

        already = await adapter.fetch_one(
            "SELECT 1 FROM processed_endstats_files WHERE filename = $1",
            (filename,),
        )
        if already:
            skipped_processed += 1
            continue

        endstats_data = parse_endstats_file(path)
        if not endstats_data:
            parse_failed += 1
            continue

        metadata = endstats_data.get("metadata", {}) or {}
        map_name = metadata.get("map_name")
        round_number = metadata.get("round_number")
        round_date = metadata.get("date")
        round_time = metadata.get("time")

        round_id = await resolve_round_id(
            adapter,
            map_name,
            round_number,
            round_date=round_date,
            round_time=round_time,
            window_minutes=config.round_match_window_minutes,
        )

        if not round_id:
            rounds_missing += 1
            continue

        existing_awards = await adapter.fetch_one(
            "SELECT 1 FROM round_awards WHERE round_id = $1 LIMIT 1",
            (round_id,),
        )
        if existing_awards:
            skipped_existing += 1
            if not dry_run:
                await adapter.execute(
                    "INSERT INTO processed_endstats_files (filename, round_id, success) VALUES ($1, $2, TRUE) ON CONFLICT DO NOTHING",
                    (filename, round_id),
                )
            continue

        awards = endstats_data.get("awards", [])
        vs_stats = endstats_data.get("vs_stats", [])

        if not dry_run:
            for award in awards:
                player_guid = None
                alias_row = await adapter.fetch_one(
                    "SELECT guid FROM player_aliases WHERE alias = $1 ORDER BY last_seen DESC LIMIT 1",
                    (award.get("player"),),
                )
                if alias_row:
                    player_guid = alias_row[0]

                await adapter.execute(
                    """
                    INSERT INTO round_awards
                    (round_id, round_date, map_name, round_number, award_name,
                     player_name, player_guid, award_value, award_value_numeric)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    (
                        round_id,
                        round_date,
                        map_name,
                        round_number,
                        award.get("name"),
                        award.get("player"),
                        player_guid,
                        award.get("value"),
                        award.get("numeric"),
                    ),
                )

            for vs in vs_stats:
                player_guid = None
                alias_row = await adapter.fetch_one(
                    "SELECT guid FROM player_aliases WHERE alias = $1 ORDER BY last_seen DESC LIMIT 1",
                    (vs.get("player"),),
                )
                if alias_row:
                    player_guid = alias_row[0]

                await adapter.execute(
                    """
                    INSERT INTO round_vs_stats
                    (round_id, round_date, map_name, round_number,
                     player_name, player_guid, kills, deaths)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    (
                        round_id,
                        round_date,
                        map_name,
                        round_number,
                        vs.get("player"),
                        player_guid,
                        vs.get("kills"),
                        vs.get("deaths"),
                    ),
                )

            await adapter.execute(
                "INSERT INTO processed_endstats_files (filename, round_id, success) VALUES ($1, $2, TRUE)",
                (filename, round_id),
            )

        awards_inserted += len(awards)
        vs_inserted += len(vs_stats)
        files_processed += 1

    await adapter.close()

    print(
        "Backfill complete. "
        f"files_processed={files_processed}, "
        f"awards_inserted={awards_inserted}, "
        f"vs_inserted={vs_inserted}, "
        f"skipped_processed={skipped_processed}, "
        f"skipped_existing={skipped_existing}, "
        f"rounds_missing={rounds_missing}, "
        f"parse_failed={parse_failed}"
    )
    return 0


def main() -> int:
    logger.info("Script started: %s", __file__)
    args = _parse_args()

    stats_dir = args.stats_dir
    if not os.path.isdir(stats_dir):
        raise RuntimeError(f"Stats dir not found: {stats_dir}")

    db_type = (args.db_type or BotConfig().database_type or "postgresql").lower()
    if db_type not in ("postgres", "postgresql"):
        raise RuntimeError("This backfill script currently supports PostgreSQL only.")

    return asyncio.run(
        backfill_postgres(
            stats_dir,
            date_exact=args.date_exact,
            date_since=args.date_since,
            date_until=args.date_until,
            limit=args.limit,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
