#!/usr/bin/env python3
"""slomix_backfill.py — Unified backfill tool for Slomix database.

Consolidates 6 backfill/relink scripts into a single CLI with subcommands:
  slomix_backfill.py endstats [--date YYYY-MM-DD] [--since] [--until] [--stats-dir] [--dry-run]
  slomix_backfill.py selfkills [--stats-dir] [--limit N] [--dry-run]
  slomix_backfill.py gametimes [--stats-dir] [--limit N] [--dry-run]
  slomix_backfill.py lua-round-ids [--stats-dir] [--dry-run]
  slomix_backfill.py r2-time-played [--dry-run]
  slomix_backfill.py relink-lua [--dry-run]

All scripts use .env for database configuration (DB_HOST, DB_USER, etc).
"""

from __future__ import annotations

import argparse
import asyncio
import glob
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional, Tuple

# Setup sys.path and load .env
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / '.env')

from bot.config import BotConfig
from bot.core.database_adapter import PostgreSQLAdapter
from bot.core.round_linker import resolve_round_id
from bot.community_stats_parser import C0RNP0RN3StatsParser
from bot.endstats_parser import parse_endstats_file

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# ============================================================================
# SUBCOMMAND: endstats
# ============================================================================

ENDSTATS_FILENAME_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2})-(\d{6})-(.+)-round-(\d+)-endstats\.txt$"
)

def iter_endstats_files(
    stats_dir: str,
    *,
    date_exact: Optional[str] = None,
    date_since: Optional[str] = None,
    date_until: Optional[str] = None,
    limit: Optional[int] = None,
) -> Iterable[str]:
    files = sorted(glob.glob(os.path.join(stats_dir, "*-endstats.txt")))
    count = 0
    for path in files:
        filename = os.path.basename(path)
        match = ENDSTATS_FILENAME_RE.match(filename)
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


async def backfill_endstats(
    stats_dir: str,
    *,
    date_exact: Optional[str] = None,
    date_since: Optional[str] = None,
    date_until: Optional[str] = None,
    limit: Optional[int] = None,
    dry_run: bool = False,
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
                    "INSERT INTO processed_endstats_files (filename, round_id, success) VALUES ($1, $2, TRUE) ON CONFLICT (filename) DO NOTHING",
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
        "Endstats backfill complete. "
        f"files_processed={files_processed}, "
        f"awards_inserted={awards_inserted}, "
        f"vs_inserted={vs_inserted}, "
        f"skipped_processed={skipped_processed}, "
        f"skipped_existing={skipped_existing}, "
        f"rounds_missing={rounds_missing}, "
        f"parse_failed={parse_failed}"
    )
    return 0


def cmd_endstats(args):
    return asyncio.run(
        backfill_endstats(
            args.stats_dir,
            date_exact=args.date,
            date_since=args.since,
            date_until=args.until,
            limit=args.limit,
            dry_run=args.dry_run,
        )
    )

# ============================================================================
# SUBCOMMAND: selfkills
# ============================================================================

STATS_FILENAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(\d{6})-.*-round-(\d+)\.txt$")

def iter_stat_files(stats_dir: str, limit: Optional[int] = None):
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
    match = STATS_FILENAME_RE.match(filename)
    if not match:
        return None, None
    date_str, time_str, round_str = match.groups()
    match_id = f"{date_str}-{time_str}"
    return match_id, int(round_str)


async def backfill_selfkills(stats_dir: str, limit: Optional[int] = None, dry_run: bool = False) -> int:
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

    print(f"Selfkills backfill done. Files: {files_processed}, rows updated: {rows_updated}, rounds missing: {rounds_missing}")
    return 0


def cmd_selfkills(args):
    return asyncio.run(
        backfill_selfkills(args.stats_dir, limit=args.limit, dry_run=args.dry_run)
    )

# ============================================================================
# SUBCOMMAND: gametimes
# ============================================================================

async def backfill_gametimes(
    stats_dir: str,
    limit: Optional[int] = None,
    dry_run: bool = False,
) -> int:
    """Backfill gametime (time_played) from stats files."""
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
            time_played = int(player.get("time_played", 0) or 0)
            if guid is None:
                continue
            if dry_run:
                continue
            await adapter.execute(
                "UPDATE player_comprehensive_stats SET time_played = $1 WHERE round_id = $2 AND player_guid = $3",
                (time_played, round_id, guid),
            )
            rows_updated += 1

        files_processed += 1

    await adapter.close()

    print(f"Gametimes backfill done. Files: {files_processed}, rows updated: {rows_updated}, rounds missing: {rounds_missing}")
    return 0


def cmd_gametimes(args):
    return asyncio.run(
        backfill_gametimes(args.stats_dir, limit=args.limit, dry_run=args.dry_run)
    )

# ============================================================================
# SUBCOMMAND: lua-round-ids
# ============================================================================

async def backfill_lua_round_ids(stats_dir: str, dry_run: bool = False) -> int:
    """Backfill lua_round_teams.round_id from lua files."""
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

    # Get all lua_round_teams rows without round_id
    rows = await adapter.fetch_all(
        "SELECT id, timestamp, map_name, round_number FROM lua_round_teams WHERE round_id IS NULL ORDER BY id ASC"
    )

    scanned = 0
    updated = 0
    window_minutes = getattr(config, "round_match_window_minutes", 45)

    for row in rows:
        lua_id, timestamp, map_name, round_number = row
        scanned += 1

        target_dt = None
        if timestamp:
            try:
                target_dt = datetime.fromisoformat(str(timestamp))
            except Exception:
                pass

        round_id = await resolve_round_id(
            adapter,
            map_name,
            int(round_number),
            target_dt=target_dt,
            round_date=target_dt.strftime("%Y-%m-%d") if target_dt else None,
            round_time=target_dt.strftime("%H%M%S") if target_dt else None,
            window_minutes=window_minutes,
        )

        if round_id and not dry_run:
            await adapter.execute(
                "UPDATE lua_round_teams SET round_id = $1 WHERE id = $2",
                (round_id, lua_id),
            )
            updated += 1
        elif round_id:
            updated += 1

    await adapter.close()
    print(f"Backfill lua_round_teams.round_id done. scanned={scanned}, updated={updated}, dry_run={dry_run}")
    return 0


def cmd_lua_round_ids(args):
    return asyncio.run(
        backfill_lua_round_ids(args.stats_dir, dry_run=args.dry_run)
    )

# ============================================================================
# SUBCOMMAND: r2-time-played
# ============================================================================

async def backfill_r2_time_played(dry_run: bool = False) -> int:
    """Backfill time_played for R2 rounds from endstats files."""
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

    # Fetch all R2 rounds without time_played
    rows = await adapter.fetch_all(
        "SELECT id, match_id, round_number FROM rounds WHERE round_number = 2 AND (time_played IS NULL OR time_played = 0) ORDER BY id DESC LIMIT 500"
    )

    updated = 0
    skipped = 0

    for round_id, match_id, round_number in rows:
        # Try to find R2 endstats file
        # Filename pattern: YYYY-MM-DD-HHMMSS-{server}-{map}-round-2-endstats.txt
        stats_dir = "local_stats"
        # Search for matching endstats files
        pattern = os.path.join(stats_dir, f"*-round-2-endstats.txt")
        files = glob.glob(pattern)

        found = False
        for path in files:
            data = parse_endstats_file(path)
            if not data:
                continue
            metadata = data.get("metadata", {})
            if metadata.get("round_number") == 2:
                # Extract time_played from first player
                players = data.get("players", [])
                for player in players:
                    time_played = int(player.get("time_played", 0) or 0)
                    if time_played > 0 and not dry_run:
                        await adapter.execute(
                            "UPDATE player_comprehensive_stats SET time_played = $1 WHERE round_id = $2 AND player_guid = $3",
                            (time_played, round_id, player.get("guid")),
                        )
                        updated += 1
                found = True
                break

        if not found:
            skipped += 1

    await adapter.close()
    print(f"R2 time_played backfill done. updated={updated}, skipped={skipped}, dry_run={dry_run}")
    return 0


def cmd_r2_time_played(args):
    return asyncio.run(
        backfill_r2_time_played(dry_run=args.dry_run)
    )

# ============================================================================
# SUBCOMMAND: relink-lua
# ============================================================================

async def relink_lua_round_teams(dry_run: bool = False) -> int:
    """Relink lua_round_teams to correct round_id by timestamp."""
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

    # Get all lua_round_teams
    rows = await adapter.fetch_all(
        "SELECT id, timestamp, map_name, round_number FROM lua_round_teams ORDER BY id ASC"
    )

    scanned = 0
    updated = 0
    window_minutes = getattr(config, "round_match_window_minutes", 45)

    for lua_id, timestamp, map_name, round_number in rows:
        scanned += 1

        target_dt = None
        if timestamp:
            try:
                target_dt = datetime.fromisoformat(str(timestamp))
            except Exception:
                pass

        round_id = await resolve_round_id(
            adapter,
            map_name,
            int(round_number),
            target_dt=target_dt,
            round_date=target_dt.strftime("%Y-%m-%d") if target_dt else None,
            round_time=target_dt.strftime("%H%M%S") if target_dt else None,
            window_minutes=window_minutes,
        )

        if round_id and not dry_run:
            await adapter.execute(
                "UPDATE lua_round_teams SET round_id = $1 WHERE id = $2",
                (round_id, lua_id),
            )
            updated += 1
        elif round_id:
            updated += 1

    await adapter.close()
    print(f"Relink lua_round_teams done. scanned={scanned}, updated={updated}, dry_run={dry_run}")
    return 0


def cmd_relink_lua(args):
    return asyncio.run(
        relink_lua_round_teams(dry_run=args.dry_run)
    )

# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Unified backfill tool for Slomix database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/slomix_backfill.py endstats --date 2026-02-02
  python tools/slomix_backfill.py selfkills --stats-dir local_stats --dry-run
  python tools/slomix_backfill.py gametimes --limit 100
  python tools/slomix_backfill.py lua-round-ids --dry-run
  python tools/slomix_backfill.py r2-time-played
  python tools/slomix_backfill.py relink-lua --dry-run
        """
    )

    subs = parser.add_subparsers(dest='command', required=True, help='Backfill subcommand')

    # ENDSTATS subcommand
    sub = subs.add_parser('endstats', help='Backfill endstats into round_awards and round_vs_stats')
    sub.add_argument('--stats-dir', default='local_stats', help='Stats directory')
    sub.add_argument('--date', dest='date', default=None, help='Exact date (YYYY-MM-DD)')
    sub.add_argument('--since', dest='since', default=None, help='Start date (YYYY-MM-DD)')
    sub.add_argument('--until', dest='until', default=None, help='End date (YYYY-MM-DD)')
    sub.add_argument('--limit', type=int, default=None, help='Limit number of files')
    sub.add_argument('--dry-run', action='store_true', help='Dry run mode')
    sub.set_defaults(func=cmd_endstats)

    # SELFKILLS subcommand
    sub = subs.add_parser('selfkills', help='Backfill full_selfkills into player_comprehensive_stats')
    sub.add_argument('--stats-dir', default='local_stats', help='Stats directory')
    sub.add_argument('--limit', type=int, default=None, help='Limit number of files')
    sub.add_argument('--dry-run', action='store_true', help='Dry run mode')
    sub.set_defaults(func=cmd_selfkills)

    # GAMETIMES subcommand
    sub = subs.add_parser('gametimes', help='Backfill time_played from stats files')
    sub.add_argument('--stats-dir', default='local_stats', help='Stats directory')
    sub.add_argument('--limit', type=int, default=None, help='Limit number of files')
    sub.add_argument('--dry-run', action='store_true', help='Dry run mode')
    sub.set_defaults(func=cmd_gametimes)

    # LUA-ROUND-IDS subcommand
    sub = subs.add_parser('lua-round-ids', help='Backfill lua_round_teams.round_id for nulls only')
    sub.add_argument('--stats-dir', default='local_stats', help='Stats directory (unused)')
    sub.add_argument('--dry-run', action='store_true', help='Dry run mode')
    sub.set_defaults(func=cmd_lua_round_ids)

    # R2-TIME-PLAYED subcommand
    sub = subs.add_parser('r2-time-played', help='Backfill time_played for R2 rounds')
    sub.add_argument('--dry-run', action='store_true', help='Dry run mode')
    sub.set_defaults(func=cmd_r2_time_played)

    # RELINK-LUA subcommand
    sub = subs.add_parser('relink-lua', help='Relink all lua_round_teams by timestamp')
    sub.add_argument('--dry-run', action='store_true', help='Dry run mode')
    sub.set_defaults(func=cmd_relink_lua)

    args = parser.parse_args()
    logger.info("Script started: %s with command: %s", __file__, args.command)

    return args.func(args)


if __name__ == '__main__':
    raise SystemExit(main())
