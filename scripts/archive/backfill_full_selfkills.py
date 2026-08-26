#!/usr/bin/env python3
"""Backfill full_selfkills from stats files into player_comprehensive_stats.

Usage:
  python3 scripts/backfill_full_selfkills.py
  python3 scripts/backfill_full_selfkills.py --stats-dir local_stats --limit 200
  python3 scripts/backfill_full_selfkills.py --db-type sqlite --sqlite-path bot/etlegacy_production.db

Notes:
- Uses filename match_id (YYYY-MM-DD-HHMMSS) + round_number to find round_id.
- Updates full_selfkills for each player in the stats file.
- Safe to run multiple times.
"""

from __future__ import annotations

import argparse
import asyncio
import glob
import logging
import os
import re
import sqlite3

from bot.community_stats_parser import C0RNP0RN3StatsParser
from bot.config import BotConfig
from bot.core.database_adapter import PostgreSQLAdapter

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)
FILENAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(\d{6})-.*-round-(\d+)\.txt$")


def iter_stat_files(stats_dir: str, limit: int | None = None):
    files = sorted(glob.glob(os.path.join(stats_dir, "*.txt")))
    count = 0
    for path in files:
        name = os.path.basename(path)
        if name.endswith("_ws.txt") or name.endswith("-endstats.txt"):
            continue
        if limit is not None and count >= limit:
            break
        yield path
        count += 1


def parse_match_id_and_round(filename: str):
    match = FILENAME_RE.match(filename)
    if not match:
        return None, None
    date_str, time_str, round_str = match.groups()
    match_id = f"{date_str}-{time_str}"
    return match_id, int(round_str)


async def backfill_postgres(stats_dir: str, limit: int | None, dry_run: bool) -> int:
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

    # Ensure column exists
    col_check = await adapter.fetch_one(
        "SELECT 1 FROM information_schema.columns WHERE table_name = 'player_comprehensive_stats' AND column_name = 'full_selfkills'"
    )
    if not col_check:
        await adapter.close()
        raise RuntimeError("full_selfkills column missing. Run migrations/006_add_full_selfkills.sql first.")

    parser = C0RNP0RN3StatsParser()
    files_processed = 0
    rows_updated = 0
    rounds_missing = 0

    for path in iter_stat_files(stats_dir, limit):
        filename = os.path.basename(path)
        match_id, round_number = parse_match_id_and_round(filename)
        if not match_id:
            continue

        data = parser.parse_stats_file(path)
        if not data or data.get("error"):
            continue

        round_row = await adapter.fetch_one(
            "SELECT id FROM rounds WHERE match_id = $1 AND round_number = $2 ORDER BY id DESC LIMIT 1",
            (match_id, round_number),
        )
        if not round_row:
            rounds_missing += 1
            continue

        round_id = round_row[0]
        players = data.get("players", [])
        for player in players:
            guid = player.get("guid")
            obj = player.get("objective_stats", {}) or {}
            full_selfkills = int(obj.get("full_selfkills", 0) or 0)
            if guid is None:
                continue
            if dry_run:
                continue
            await adapter.execute(
                "UPDATE player_comprehensive_stats SET full_selfkills = $1 WHERE round_id = $2 AND player_guid = $3",
                (full_selfkills, round_id, guid),
            )
            rows_updated += 1

        files_processed += 1

    await adapter.close()

    print(f"Postgres backfill done. Files: {files_processed}, rows updated: {rows_updated}, rounds missing: {rounds_missing}")
    return 0


def backfill_sqlite(stats_dir: str, limit: int | None, dry_run: bool, sqlite_path: str) -> int:
    if not os.path.exists(sqlite_path):
        raise RuntimeError(f"SQLite DB not found: {sqlite_path}")

    conn = sqlite3.connect(sqlite_path)
    cur = conn.cursor()

    # Ensure column exists
    cur.execute("PRAGMA table_info(player_comprehensive_stats)")
    columns = {row[1] for row in cur.fetchall()}
    if "full_selfkills" not in columns:
        conn.close()
        raise RuntimeError("full_selfkills column missing. Run ALTER TABLE to add it.")

    parser = C0RNP0RN3StatsParser()
    files_processed = 0
    rows_updated = 0
    rounds_missing = 0

    for path in iter_stat_files(stats_dir, limit):
        filename = os.path.basename(path)
        match_id, round_number = parse_match_id_and_round(filename)
        if not match_id:
            continue

        data = parser.parse_stats_file(path)
        if not data or data.get("error"):
            continue

        cur.execute(
            "SELECT id FROM rounds WHERE match_id = ? AND round_number = ? ORDER BY id DESC LIMIT 1",
            (match_id, round_number),
        )
        row = cur.fetchone()
        if not row:
            rounds_missing += 1
            continue

        round_id = row[0]
        players = data.get("players", [])
        for player in players:
            guid = player.get("guid")
            obj = player.get("objective_stats", {}) or {}
            full_selfkills = int(obj.get("full_selfkills", 0) or 0)
            if guid is None:
                continue
            if not dry_run:
                cur.execute(
                    "UPDATE player_comprehensive_stats SET full_selfkills = ? WHERE round_id = ? AND player_guid = ?",
                    (full_selfkills, round_id, guid),
                )
                rows_updated += 1

        files_processed += 1

    if not dry_run:
        conn.commit()
    conn.close()

    print(f"SQLite backfill done. Files: {files_processed}, rows updated: {rows_updated}, rounds missing: {rounds_missing}")
    return 0


def main() -> int:
    logger.info("Script started: %s", __file__)
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats-dir", default="local_stats")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--db-type", choices=["postgres", "postgresql", "sqlite"], default=None)
    ap.add_argument("--sqlite-path", default=None)
    args = ap.parse_args()

    stats_dir = args.stats_dir
    if not os.path.isdir(stats_dir):
        raise RuntimeError(f"Stats dir not found: {stats_dir}")

    config = BotConfig()
    db_type = (args.db_type or config.database_type or "postgresql").lower()

    if db_type in ("postgres", "postgresql"):
        return asyncio.run(backfill_postgres(stats_dir, args.limit, args.dry_run))

    # SQLite fallback
    sqlite_path = args.sqlite_path or config.sqlite_db_path or "bot/etlegacy_production.db"
    return backfill_sqlite(stats_dir, args.limit, args.dry_run, sqlite_path)


if __name__ == "__main__":
    raise SystemExit(main())
