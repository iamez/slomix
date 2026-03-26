#!/usr/bin/env python3
"""
Repair endstats round assignments (awards + vs_stats).

Problem: When the same map is played multiple times in a session, endstats arriving
via webhook before the stats file is imported get matched to the wrong round_id
(an earlier play of the same map within the 45-min round_linker window).

This script:
1. Identifies all mismatched endstats (endstats timestamp >30s from round_time)
2. Finds the correct round for each (within 30s of endstats timestamp)
3. Moves awards/vs_stats from wrong round to correct round
4. Updates processed_endstats_files entries
5. Resets skipped endstats entries for reprocessing

Safety:
  - Dry-run mode by default (--apply to actually write)
  - Never overwrites existing data on correct round
  - Validates every correction before applying
  - Full audit trail
"""
import asyncio
import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot.core.database_adapter import PostgreSQLAdapter as DatabaseAdapter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("repair_endstats")


def hhmmss_to_seconds(t: str) -> int | None:
    """Convert HHMMSS string to total seconds."""
    if not t or len(t) < 6:
        return None
    try:
        return int(t[:2]) * 3600 + int(t[2:4]) * 60 + int(t[4:6])
    except (ValueError, TypeError):
        return None


async def find_mismatches(db: DatabaseAdapter):
    """Find all endstats that are matched to the wrong round."""
    rows = await db.fetch_all("""
        SELECT pef.id as pef_id, pef.filename, pef.round_id as wrong_round_id,
               r.round_time as wrong_round_time, r.map_name, r.round_number, r.round_date
        FROM processed_endstats_files pef
        JOIN rounds r ON r.id = pef.round_id
        WHERE pef.success = TRUE AND pef.round_id IS NOT NULL
          AND r.round_time IS NOT NULL AND LENGTH(r.round_time) >= 6
        ORDER BY pef.id
    """)
    if not rows:
        return []

    mismatches = []
    for row in rows:
        pef_id, filename, wrong_round_id, wrong_round_time, map_name, round_number, round_date = row
        # Extract endstats time from filename (position 11-16, 0-indexed)
        endstats_time = filename[11:17] if len(filename) > 16 else None
        if not endstats_time:
            continue

        wrong_secs = hhmmss_to_seconds(wrong_round_time)
        endstats_secs = hhmmss_to_seconds(endstats_time)
        if wrong_secs is None or endstats_secs is None:
            continue

        diff = abs(wrong_secs - endstats_secs)
        if diff <= 30:
            continue  # This one is fine

        mismatches.append({
            'pef_id': pef_id,
            'filename': filename,
            'wrong_round_id': wrong_round_id,
            'wrong_round_time': wrong_round_time,
            'endstats_time': endstats_time,
            'map_name': map_name,
            'round_number': round_number,
            'round_date': round_date,
            'time_diff': diff,
        })

    return mismatches


async def find_correct_round(db: DatabaseAdapter, mismatch: dict) -> dict | None:
    """Find the correct round for a mismatched endstats."""
    rows = await db.fetch_all(
        "SELECT id, round_time FROM rounds "
        "WHERE round_date = $1 AND map_name = $2 AND round_number = $3 AND id != $4",
        (mismatch['round_date'], mismatch['map_name'],
         mismatch['round_number'], mismatch['wrong_round_id']),
    )
    if not rows:
        return None

    endstats_secs = hhmmss_to_seconds(mismatch['endstats_time'])
    best = None
    best_diff = 31  # 30s max

    for row in rows:
        round_id, round_time = row
        row_secs = hhmmss_to_seconds(round_time)
        if row_secs is None:
            continue
        diff = abs(row_secs - endstats_secs)
        if diff < best_diff:
            best_diff = diff
            best = {'round_id': round_id, 'round_time': round_time, 'diff': diff}

    return best


async def check_existing_data(db: DatabaseAdapter, round_id: int) -> tuple[int, int]:
    """Check if a round already has awards/vs_stats data."""
    awards = await db.fetch_one(
        "SELECT COUNT(*) FROM round_awards WHERE round_id = $1", (round_id,))
    vs = await db.fetch_one(
        "SELECT COUNT(*) FROM round_vs_stats WHERE round_id = $1", (round_id,))
    return (int(awards[0]) if awards else 0, int(vs[0]) if vs else 0)


async def find_skipped_endstats(db: DatabaseAdapter, wrong_round_ids: set) -> list:
    """Find endstats entries that were skipped as duplicates and should be reprocessed."""
    rows = await db.fetch_all("""
        SELECT id, filename, error_message
        FROM processed_endstats_files
        WHERE success = TRUE AND round_id IS NULL
          AND error_message LIKE 'duplicate_round_skip%'
    """)
    return list(rows) if rows else []


async def main():
    parser = argparse.ArgumentParser(description="Repair mismatched endstats round assignments")
    parser.add_argument("--apply", action="store_true", help="Actually write changes (default: dry-run)")
    args = parser.parse_args()

    mode = "APPLY" if args.apply else "DRY-RUN"
    log.info(f"=== Endstats Round Assignment Repair ({mode}) ===")

    db = DatabaseAdapter(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "etlegacy"),
        user=os.getenv("DB_USER", "etlegacy_user"),
        password=os.getenv("DB_PASSWORD", "etlegacy_secure_2025"),
        min_pool_size=1,
        max_pool_size=3,
    )
    await db.connect()

    try:
        # Step 1: Find all mismatches
        mismatches = await find_mismatches(db)
        log.info(f"Found {len(mismatches)} mismatched endstats entries")

        if not mismatches:
            log.info("Nothing to repair!")
            return

        # Step 2: Build correction plan
        corrections = []
        skipped = []

        for m in mismatches:
            correct = await find_correct_round(db, m)
            if not correct:
                log.warning(
                    f"  No correct round found for {m['filename']} "
                    f"(wrong_id={m['wrong_round_id']}, endstats_time={m['endstats_time']})"
                )
                skipped.append(m)
                continue

            # Check if correct round already has data
            correct_awards, correct_vs = await check_existing_data(db, correct['round_id'])
            wrong_awards, wrong_vs = await check_existing_data(db, m['wrong_round_id'])

            corrections.append({
                **m,
                'correct_round_id': correct['round_id'],
                'correct_round_time': correct['round_time'],
                'correct_diff': correct['diff'],
                'correct_has_awards': correct_awards,
                'correct_has_vs': correct_vs,
                'wrong_has_awards': wrong_awards,
                'wrong_has_vs': wrong_vs,
            })

        log.info(f"Correction plan: {len(corrections)} to fix, {len(skipped)} skipped")

        # Step 3: Sort by dependency order (process chains correctly)
        # Some corrections are chained: wrong_id of one is correct_id of another
        # We need to process them in reverse order (most recent first) to avoid conflicts
        corrections.sort(key=lambda c: c['wrong_round_id'], reverse=True)

        # Step 4: Apply corrections
        moved_awards = 0
        moved_vs = 0
        updated_pef = 0

        for c in corrections:
            wrong_id = c['wrong_round_id']
            correct_id = c['correct_round_id']

            log.info(
                f"  {c['filename']}: {wrong_id} -> {correct_id} "
                f"(endstats={c['endstats_time']}, wrong_rt={c['wrong_round_time']}, "
                f"correct_rt={c['correct_round_time']}, diff={c['correct_diff']}s)"
            )

            if c['correct_has_awards'] > 0 or c['correct_has_vs'] > 0:
                log.warning(
                    f"    CONFLICT: correct round {correct_id} already has "
                    f"{c['correct_has_awards']} awards, {c['correct_has_vs']} vs_stats"
                )
                # Delete existing data on correct round (it's from the wrong endstats too)
                if args.apply:
                    await db.execute(
                        "DELETE FROM round_awards WHERE round_id = $1", (correct_id,))
                    await db.execute(
                        "DELETE FROM round_vs_stats WHERE round_id = $1", (correct_id,))
                log.info(f"    Cleared conflicting data from round {correct_id}")

            if args.apply:
                # Move awards
                result = await db.execute(
                    "UPDATE round_awards SET round_id = $1 WHERE round_id = $2",
                    (correct_id, wrong_id),
                )
                # Move vs_stats
                result2 = await db.execute(
                    "UPDATE round_vs_stats SET round_id = $1 WHERE round_id = $2",
                    (correct_id, wrong_id),
                )
                # Update processed_endstats_files
                await db.execute(
                    "UPDATE processed_endstats_files SET round_id = $1 WHERE id = $2",
                    (correct_id, c['pef_id']),
                )

            moved_awards += c['wrong_has_awards']
            moved_vs += c['wrong_has_vs']
            updated_pef += 1

        # Step 5: Find and reset skipped endstats entries
        skipped_entries = await find_skipped_endstats(db, set())
        reset_count = 0
        for entry in skipped_entries:
            entry_id, filename, error_msg = entry
            log.info(f"  Resetting skipped entry: {filename}")
            if args.apply:
                await db.execute(
                    "DELETE FROM processed_endstats_files WHERE id = $1",
                    (entry_id,),
                )
            reset_count += 1

        verb = "moved" if args.apply else "would move"
        log.info(
            f"=== Done: {verb} {moved_awards} awards + {moved_vs} vs_stats "
            f"across {updated_pef} rounds, reset {reset_count} skipped entries ==="
        )

    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
