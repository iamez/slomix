#!/usr/bin/env python3
"""
Reprocess endstats files that were skipped due to the replayed-map bug.

These files exist in local_stats/ but were never inserted into the database
because the round_linker matched them to the wrong round_id.

Safety:
  - Dry-run by default (--apply to write)
  - Uses narrow 30s time matching (same as the new bot logic)
  - Only processes files that have no existing endstats for the correct round
  - Resolves player GUIDs from player_aliases
"""
import asyncio
import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot.core.database_adapter import PostgreSQLAdapter as DatabaseAdapter
from bot.endstats_parser import parse_endstats_file

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("reprocess_endstats")

LOCAL_STATS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "local_stats")


def hhmmss_to_seconds(t: str) -> int | None:
    if not t or len(t) < 6:
        return None
    try:
        return int(t[:2]) * 3600 + int(t[2:4]) * 60 + int(t[4:6])
    except (ValueError, TypeError):
        return None


async def resolve_round_id_narrow(db: DatabaseAdapter, round_date: str, round_time: str,
                                   map_name: str, round_number: int) -> int | None:
    """Find round_id using narrow 30s time window."""
    rows = await db.fetch_all(
        "SELECT id, round_time FROM rounds WHERE round_date = $1 AND map_name = $2 AND round_number = $3",
        (round_date, map_name, round_number),
    )
    if not rows:
        return None
    target_secs = hhmmss_to_seconds(round_time)
    if target_secs is None:
        return None
    best_id = None
    best_diff = 31
    for row in rows:
        row_secs = hhmmss_to_seconds(row[1])
        if row_secs is not None:
            diff = abs(row_secs - target_secs)
            if diff < best_diff:
                best_diff = diff
                best_id = row[0]
    return best_id


async def find_missing_endstats(db: DatabaseAdapter) -> list[str]:
    """Find endstats files in local_stats that aren't successfully processed."""
    # Get all successfully processed filenames
    rows = await db.fetch_all(
        "SELECT filename FROM processed_endstats_files WHERE success = TRUE"
    )
    processed = {r[0] for r in rows} if rows else set()

    # Scan local_stats for endstats files
    missing = []
    for fname in sorted(os.listdir(LOCAL_STATS_DIR)):
        if fname.endswith("-endstats.txt") and fname not in processed:
            missing.append(fname)
    return missing


async def resolve_guid(db: DatabaseAdapter, player_name: str) -> str | None:
    """Resolve player GUID from alias."""
    result = await db.fetch_one(
        "SELECT guid FROM player_aliases WHERE alias = $1 ORDER BY last_seen DESC LIMIT 1",
        (player_name,),
    )
    return result[0] if result else None


async def process_endstats(db: DatabaseAdapter, filename: str, apply: bool) -> tuple[int, int, str | None]:
    """Process a single endstats file. Returns (awards_count, vs_count, error)."""
    filepath = os.path.join(LOCAL_STATS_DIR, filename)
    if not os.path.exists(filepath):
        return 0, 0, "file not found"

    data = parse_endstats_file(filepath)
    if not data:
        return 0, 0, "parse failed"

    metadata = data['metadata']
    awards = data['awards']
    vs_stats = data['vs_stats']

    round_date = metadata.get('date')
    round_time = metadata.get('time')
    map_name = metadata.get('map_name')
    round_number = metadata.get('round_number')

    if not all([round_date, round_time, map_name, round_number]):
        return 0, 0, "incomplete metadata"

    round_id = await resolve_round_id_narrow(db, round_date, round_time, map_name, round_number)
    if not round_id:
        return 0, 0, f"no round within 30s (date={round_date} time={round_time})"

    # Check if round already has endstats
    existing = await db.fetch_one(
        "SELECT COUNT(*) FROM round_awards WHERE round_id = $1", (round_id,)
    )
    if existing and int(existing[0]) > 0:
        return 0, 0, f"round {round_id} already has {existing[0]} awards"

    if not apply:
        log.info(f"  Would process: {filename} -> round_id={round_id} ({len(awards)} awards, {len(vs_stats)} vs)")
        return len(awards), len(vs_stats), None

    # Insert awards
    for award in awards:
        player_guid = await resolve_guid(db, award['player'])
        await db.execute(
            """INSERT INTO round_awards
               (round_id, round_date, map_name, round_number, award_name,
                player_name, player_guid, award_value, award_value_numeric)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
            (round_id, round_date, map_name, round_number,
             award['name'], award['player'], player_guid,
             award['value'], award.get('numeric')),
        )

    # Insert VS stats
    for vs in vs_stats:
        opponent_guid = await resolve_guid(db, vs['player'])
        subject_name = vs.get('subject')
        subject_guid = vs.get('subject_guid')
        if subject_name and not subject_guid:
            subject_guid = await resolve_guid(db, subject_name)

        await db.execute(
            """INSERT INTO round_vs_stats
               (round_id, round_date, map_name, round_number,
                player_name, player_guid, kills, deaths,
                subject_name, subject_guid)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)""",
            (round_id, round_date, map_name, round_number,
             vs['player'], opponent_guid, vs['kills'], vs['deaths'],
             subject_name, subject_guid),
        )

    # Mark as processed
    await db.execute(
        """INSERT INTO processed_endstats_files (filename, round_id, success, error_message, processed_at)
           VALUES ($1, $2, TRUE, NULL, CURRENT_TIMESTAMP)
           ON CONFLICT (filename) DO UPDATE SET
               round_id = EXCLUDED.round_id, success = TRUE,
               error_message = NULL, processed_at = CURRENT_TIMESTAMP""",
        (filename, round_id),
    )

    log.info(f"  Processed: {filename} -> round_id={round_id} ({len(awards)} awards, {len(vs_stats)} vs)")
    return len(awards), len(vs_stats), None


async def main():
    parser = argparse.ArgumentParser(description="Reprocess missing endstats files")
    parser.add_argument("--apply", action="store_true", help="Actually write (default: dry-run)")
    args = parser.parse_args()

    mode = "APPLY" if args.apply else "DRY-RUN"
    log.info(f"=== Reprocess Missing Endstats ({mode}) ===")

    db = DatabaseAdapter(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "etlegacy"),
        user=os.getenv("DB_USER", "etlegacy_user"),
        password=os.getenv("DB_PASSWORD"),
        min_pool_size=1,
        max_pool_size=3,
    )
    await db.connect()

    try:
        missing = await find_missing_endstats(db)
        log.info(f"Found {len(missing)} unprocessed endstats files in local_stats/")

        total_awards = 0
        total_vs = 0
        processed = 0
        skipped = 0

        for filename in missing:
            awards, vs, error = await process_endstats(db, filename, args.apply)
            if error:
                log.warning(f"  Skip: {filename} — {error}")
                skipped += 1
            else:
                total_awards += awards
                total_vs += vs
                processed += 1

        verb = "inserted" if args.apply else "would insert"
        log.info(f"=== Done: {verb} {total_awards} awards + {total_vs} vs_stats "
                 f"across {processed} files, {skipped} skipped ===")

    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
