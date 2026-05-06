#!/usr/bin/env python3
"""Backfill round_canonical_id for existing rounds.

Per ADR docs/ADR_round_canonical_id.md (Phase 1).

Usage:
    python3 tools/backfill_round_canonical_id.py --dry-run   # report only
    python3 tools/backfill_round_canonical_id.py --apply     # actual writes

Idempotent: re-running is safe (only sets NULL → computed value).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass

import asyncpg  # type: ignore

from bot.core.round_canonical import compute_canonical_id


async def get_conn():
    password = os.getenv("DB_PASSWORD")
    if not password:
        raise RuntimeError(
            "DB_PASSWORD env var is required. Export it (or load .env) before running this tool."
        )
    return await asyncpg.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "5432")),
        user=os.getenv("DB_USER", "etlegacy_user"),
        password=password,
        database=os.getenv("DB_NAME", "etlegacy"),
    )


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write canonical_ids; default is dry-run")
    parser.add_argument("--limit", type=int, default=0, help="Cap to N rounds for testing")
    parser.add_argument(
        "--allow-collisions",
        action="store_true",
        help="On collision, first-by-id wins (gets canonical), others stay NULL. "
             "Without this flag, --apply refuses if any collision detected.",
    )
    args = parser.parse_args()

    conn = await get_conn()
    try:
        # Verify migration 049 was applied (column exists)
        col = await conn.fetchval(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='rounds' AND column_name='round_canonical_id'"
        )
        if not col:
            print("ERROR: migration 049 not applied — round_canonical_id column missing.")
            print("Run: psql -f migrations/049_add_round_canonical_id.sql first.")
            sys.exit(1)

        # Pre-state
        total = await conn.fetchval("SELECT COUNT(*) FROM rounds")
        already = await conn.fetchval(
            "SELECT COUNT(*) FROM rounds WHERE round_canonical_id IS NOT NULL"
        )
        print(f"Pre-state: {total} total rounds, {already} already have canonical_id, "
              f"{total - already} pending backfill.")

        # Fetch rounds needing backfill
        sql = """
            SELECT id, round_start_unix, map_name, round_number
            FROM rounds
            WHERE round_canonical_id IS NULL
            ORDER BY id
        """
        if args.limit:
            sql += f" LIMIT {int(args.limit)}"
        rows = await conn.fetch(sql)

        if not rows:
            print("Nothing to backfill.")
            return

        print(f"\nProcessing {len(rows)} rounds...")
        stats = Counter()
        updates: list[tuple[str, int]] = []  # (canonical_id, round_id)
        skipped: list[tuple[int, str]] = []  # (round_id, reason)
        collisions: list[tuple[int, int, str]] = []  # (id_a, id_b, canonical_id)
        seen: dict[str, int] = {}  # canonical_id → first round_id

        for r in rows:
            cid = compute_canonical_id(
                round_start_unix=r["round_start_unix"],
                map_name=r["map_name"],
                round_number=r["round_number"],
            )
            if cid is None:
                reason = []
                if not r["round_start_unix"] or r["round_start_unix"] <= 0:
                    reason.append("no_start_unix")
                if not r["map_name"]:
                    reason.append("no_map")
                if r["round_number"] is None:
                    reason.append("no_rn")
                skipped.append((r["id"], ",".join(reason) or "unknown"))
                stats["skipped"] += 1
                continue

            if cid in seen:
                collisions.append((seen[cid], r["id"], cid))
                stats["collisions"] += 1
                # Don't write conflicting id — would violate future UNIQUE
                continue

            seen[cid] = r["id"]
            updates.append((cid, r["id"]))
            stats["computed"] += 1

        print(f"\n=== Backfill plan ===")
        print(f"  computed: {stats['computed']}")
        print(f"  skipped:  {stats['skipped']}")
        print(f"  collisions: {stats['collisions']}")

        if skipped:
            print(f"\nSkipped rounds (sample of {min(len(skipped),10)}/{len(skipped)}):")
            for round_id, reason in skipped[:10]:
                print(f"  round_id={round_id} reason={reason}")

        if collisions:
            print(f"\n⚠️  COLLISIONS detected ({len(collisions)})!")
            for a, b, cid in collisions[:10]:
                print(f"  rounds {a} + {b} both compute canonical_id={cid}")
            print("Investigate before applying. Same canonical fields → same id is correct only if rounds are duplicates.")

        if not args.apply:
            print("\nDRY-RUN. Pass --apply to write.")
            return

        if collisions and not args.allow_collisions:
            print("\n⚠️  Collisions present. Refusing --apply.")
            print("   Re-run with --allow-collisions to first-come-first-served "
                  "(later rows stay NULL canonical_id).")
            sys.exit(2)
        if collisions and args.allow_collisions:
            print(f"\n--allow-collisions set. {len(collisions)} duplicate(s) keep first-by-id, "
                  "later rows stay NULL.")

        # Apply
        print(f"\nWriting {len(updates)} canonical_ids...")
        async with conn.transaction():
            await conn.executemany(
                "UPDATE rounds SET round_canonical_id = $1 WHERE id = $2",
                updates,
            )
        print(f"✓ Written {len(updates)} canonical_ids.")

        # Post-state
        post_total = await conn.fetchval("SELECT COUNT(*) FROM rounds")
        post_with = await conn.fetchval(
            "SELECT COUNT(*) FROM rounds WHERE round_canonical_id IS NOT NULL"
        )
        post_unique = await conn.fetchval(
            "SELECT COUNT(DISTINCT round_canonical_id) FROM rounds WHERE round_canonical_id IS NOT NULL"
        )
        print(f"\nPost-state: {post_total} total, {post_with} with canonical, "
              f"{post_unique} unique canonical_ids.")
        if post_with != post_unique:
            print("⚠️  WARNING: with_canonical != unique_canonical — there are duplicates!")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
