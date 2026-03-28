#!/usr/bin/env python3
"""Backfill movement analytics columns on player_track from existing JSONB path data.

Computes: peak_speed, stance_standing_sec, stance_crouching_sec, stance_prone_sec,
          sprint_sec, post_spawn_distance
from the stored 200ms path samples.

Usage:
    python scripts/backfill_player_track_metrics.py [--dry-run] [--batch-size 500]
"""
import argparse
import json
import math
import os
import psycopg2

DB_PARAMS = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "etlegacy"),
    "user": os.getenv("DB_USER", "etlegacy_user"),
    "password": os.getenv("DB_PASSWORD"),
}

SAMPLE_INTERVAL = 0.2  # 200ms


def compute_metrics(path: list[dict]) -> dict:
    """Compute movement metrics from path sample list."""
    samples = [p for p in path if p.get("event") == "sample"]

    peak_speed = max((p.get("speed", 0) for p in path), default=0.0)

    standing = sum(1 for p in samples if p.get("stance") == 0) * SAMPLE_INTERVAL
    crouching = sum(1 for p in samples if p.get("stance") == 1) * SAMPLE_INTERVAL
    prone = sum(1 for p in samples if p.get("stance") == 2) * SAMPLE_INTERVAL
    sprint_sec = sum(1 for p in samples if p.get("sprint") == 1) * SAMPLE_INTERVAL

    # Post-spawn distance: first 15 intervals (3s) after spawn event
    post_spawn_dist = 0.0
    if len(path) >= 2:
        start_idx = 0
        for i, p in enumerate(path):
            if p.get("event") == "spawn":
                start_idx = i
                break
        end_idx = min(start_idx + 16, len(path))
        for i in range(start_idx + 1, end_idx):
            p1, p2 = path[i - 1], path[i]
            dx = p2.get("x", 0) - p1.get("x", 0)
            dy = p2.get("y", 0) - p1.get("y", 0)
            dz = p2.get("z", 0) - p1.get("z", 0)
            post_spawn_dist += math.sqrt(dx * dx + dy * dy + dz * dz)

    return {
        "peak_speed": round(peak_speed, 2),
        "stance_standing_sec": round(standing, 1),
        "stance_crouching_sec": round(crouching, 1),
        "stance_prone_sec": round(prone, 1),
        "sprint_sec": round(sprint_sec, 1),
        "post_spawn_distance": round(post_spawn_dist, 2),
    }


def main():
    parser = argparse.ArgumentParser(description="Backfill player_track movement metrics")
    parser.add_argument("--dry-run", action="store_true", help="Only compute, don't write")
    parser.add_argument("--batch-size", type=int, default=500, help="Rows per batch")
    args = parser.parse_args()

    conn = psycopg2.connect(**DB_PARAMS)
    conn.autocommit = False

    with conn.cursor() as cur:
        # Count rows needing backfill
        cur.execute("SELECT COUNT(*) FROM player_track WHERE peak_speed IS NULL")
        total = cur.fetchone()[0]
        print(f"Tracks to backfill: {total}")

        if total == 0:
            print("Nothing to do.")
            return

        updated = 0
        offset = 0
        while offset < total:
            cur.execute(
                "SELECT id, path FROM player_track WHERE peak_speed IS NULL "
                "ORDER BY id LIMIT %s OFFSET %s",
                (args.batch_size, offset),
            )
            rows = cur.fetchall()
            if not rows:
                break

            for row_id, path_data in rows:
                if isinstance(path_data, str):
                    path = json.loads(path_data)
                elif isinstance(path_data, list):
                    path = path_data
                else:
                    path = []

                if not path:
                    # No path data — set zeros
                    metrics = {k: 0.0 for k in [
                        "peak_speed", "stance_standing_sec", "stance_crouching_sec",
                        "stance_prone_sec", "sprint_sec", "post_spawn_distance",
                    ]}
                else:
                    metrics = compute_metrics(path)

                if not args.dry_run:
                    cur.execute(
                        """UPDATE player_track SET
                            peak_speed = %s,
                            stance_standing_sec = %s,
                            stance_crouching_sec = %s,
                            stance_prone_sec = %s,
                            sprint_sec = %s,
                            post_spawn_distance = %s
                        WHERE id = %s""",
                        (
                            metrics["peak_speed"],
                            metrics["stance_standing_sec"],
                            metrics["stance_crouching_sec"],
                            metrics["stance_prone_sec"],
                            metrics["sprint_sec"],
                            metrics["post_spawn_distance"],
                            row_id,
                        ),
                    )
                updated += 1

            if not args.dry_run:
                conn.commit()

            offset += args.batch_size
            pct = min(100, (offset / total) * 100)
            print(f"  Processed {min(offset, total)}/{total} ({pct:.0f}%)")

        print(f"Done. {'Would update' if args.dry_run else 'Updated'} {updated} tracks.")

    conn.close()


if __name__ == "__main__":
    main()
