#!/usr/bin/env python3
"""
Backfill script to fix DPM for R2 rounds with inflated time_played_seconds.

PROBLEM:
ET:Legacy stats files record actual_time (header field) as cumulative server uptime in R2 files,
not the round's actual play duration. When the Lua TAB field 22 (time_played_minutes) is absent,
the parser falls back to header actual_time, inflating time_played_seconds by 15-87x.

This causes DPM to be calculated with a 50-100x larger denominator, dropping DPM from 250-400
down to 3-11.

SOLUTION:
For affected old rounds where Lua webhook data (actual_duration_seconds) is NULL, use the
round's time_limit as the best available approximation. This is safe because no round can
exceed its time limit by definition.

AFFECTED ROUNDS (7 total):
- 9809 (etl_adlernest R2, session 86): 6 players, avg DPM 4-11
- 9817 (etl_adlernest R2, session 87): 6 players, avg DPM ~10
- 9811 (te_escape2 R2, session 84): 6 players, avg DPM ~12
- 9807 (sw_goldrush_te R2, session 85): 4 players, avg DPM 0 (insufficient data)
- 9804, 9815, 9816: 0-1 player each (edge cases)

USAGE:
  python scripts/backfill_r2_time_played.py              # Dry-run (show what would change)
  python scripts/backfill_r2_time_played.py --apply      # Apply fixes

DRY-RUN OUTPUT:
  - Identifies all affected rounds
  - Shows before/after DPM for each player
  - Calculates total players to be fixed
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add parent directory to path so we can import bot modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.core.database_adapter import DatabaseAdapter

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

class R2TimeFixer:
    """Fixes inflated time_played_seconds for R2 rounds where header fallback occurred."""

    def __init__(self, db_adapter: DatabaseAdapter, apply_fixes: bool = False):
        self.db = db_adapter
        self.apply_fixes = apply_fixes
        self.affected_rounds = []
        self.total_players = 0
        self.total_dpm_improvement = 0.0

    async def find_affected_rounds(self) -> list:
        """
        Find all rounds where actual_time > time_limit * 1.5.

        These are the R2 rounds where the header's actual_time is inflated
        (cumulative server time instead of round duration).
        """
        query = """
            SELECT
                r.id,
                r.map_name,
                r.round_number,
                r.actual_time,
                r.time_limit,
                r.gaming_session_id,
                -- Parse actual_time (MM:SS -> seconds)
                (SPLIT_PART(r.actual_time, ':', 1)::int * 60 + SPLIT_PART(r.actual_time, ':', 2)::int) AS actual_secs,
                -- Parse time_limit (MM:SS -> seconds)
                (SPLIT_PART(r.time_limit, ':', 1)::int * 60 + SPLIT_PART(r.time_limit, ':', 2)::int) AS limit_secs,
                COUNT(p.player_guid) AS player_count
            FROM rounds r
            JOIN player_comprehensive_stats p ON p.round_id = r.id
            WHERE r.actual_time ~ '^\d+:\d+$'
              AND r.time_limit ~ '^\d+:\d+$'
              AND (SPLIT_PART(r.actual_time, ':', 1)::int * 60 + SPLIT_PART(r.actual_time, ':', 2)::int)
                  > (SPLIT_PART(r.time_limit, ':', 1)::int * 60 + SPLIT_PART(r.time_limit, ':', 2)::int) * 1.5
              AND r.actual_duration_seconds IS NULL  -- Lua webhook data not available
            GROUP BY r.id, r.map_name, r.round_number, r.actual_time, r.time_limit, r.gaming_session_id
            ORDER BY actual_secs DESC
        """
        results = await self.db.fetch_all(query)
        self.affected_rounds = [dict(row) for row in results]
        return self.affected_rounds

    async def show_summary(self):
        """Display summary of affected rounds."""
        if not self.affected_rounds:
            print("✅ No affected rounds found! Database is clean.")
            return

        print(f"\n📋 Found {len(self.affected_rounds)} affected R2 rounds:")
        print("=" * 90)

        total_players = 0
        for round_info in self.affected_rounds:
            print(
                f"  Round {round_info['id']:4d} {round_info['map_name']:20s} "
                f"R{round_info['round_number']} "
                f"(session {round_info['gaming_session_id']}) "
                f"actual_time: {round_info['actual_time']} (should be ≤ {round_info['time_limit']}) "
                f"→ {round_info['player_count']} players"
            )
            total_players += round_info['player_count']

        print("=" * 90)
        print(f"Total players to fix: {total_players}\n")

    async def fix_round(self, round_info: dict) -> dict:
        """
        Fix a single round's player stats.

        Returns dict with before/after stats per player.
        """
        round_id = round_info['id']
        limit_secs = round_info['limit_secs']

        # Fetch before state
        before_query = """
            SELECT
                player_name,
                player_guid,
                damage_given,
                time_played_seconds,
                dpm AS old_dpm
            FROM player_comprehensive_stats
            WHERE round_id = $1
            ORDER BY player_name
        """
        before_rows = await self.db.fetch_all(before_query, (round_id,))
        before_players = [dict(row) for row in before_rows]

        # Compute expected DPM after fix
        results = []
        for player in before_players:
            damage = player['damage_given']
            new_dpm = (damage * 60.0) / limit_secs if limit_secs > 0 else 0.0
            old_dpm = player['old_dpm']

            results.append({
                'player_name': player['player_name'],
                'damage_given': damage,
                'old_time_played': player['time_played_seconds'],
                'new_time_played': limit_secs,
                'old_dpm': old_dpm,
                'new_dpm': new_dpm,
                'dpm_improvement': new_dpm - old_dpm,
            })

        # Apply fix if requested
        if self.apply_fixes:
            update_query = """
                UPDATE player_comprehensive_stats
                SET
                    time_played_seconds = $1,
                    time_played_minutes = $1 / 60.0,
                    dpm = CASE WHEN $1 > 0 THEN (damage_given * 60.0) / $1 ELSE 0 END
                WHERE round_id = $2
                  AND time_played_seconds > $1 * 1.5
            """
            try:
                await self.db.execute(update_query, (limit_secs, round_id))
            except Exception as e:
                print(f"  ⚠️  Failed to update round {round_id}: {e}")
                return results

        return results

    async def run(self):
        """Run the backfill process."""
        print("\n🔍 DPM Backfill Script - R2 time_played_seconds Fix")
        print("=" * 90)

        # Find affected rounds
        await self.find_affected_rounds()

        if not self.affected_rounds:
            print("✅ No affected rounds found!")
            return

        # Show summary
        await self.show_summary()

        # Show mode
        if self.apply_fixes:
            print("🔴 APPLY MODE: Changes will be written to database")
        else:
            print("🟡 DRY-RUN MODE: No changes will be made (use --apply to commit)")

        print("=" * 90)

        # Process each round
        total_players_fixed = 0
        for round_info in self.affected_rounds:
            round_id = round_info['id']
            limit_secs = round_info['limit_secs']

            print(f"\n📍 Round {round_id} ({round_info['map_name']} R{round_info['round_number']}):")
            print(f"   Time limit: {round_info['time_limit']} = {limit_secs}s")
            print(f"   Actual time (inflated): {round_info['actual_time']} = {round_info['actual_secs']}s")
            print(f"   Fix: clamp to {limit_secs}s")
            print()

            results = await self.fix_round(round_info)

            for player_result in results:
                total_players_fixed += 1
                print(
                    f"   {player_result['player_name']:20s} "
                    f"dmg={player_result['damage_given']:4d} "
                    f"time: {player_result['old_time_played']}s → {player_result['new_time_played']}s "
                    f"DPM: {player_result['old_dpm']:.1f} → {player_result['new_dpm']:.1f} "
                    f"(+{player_result['dpm_improvement']:.1f})"
                )

        # Summary
        print("\n" + "=" * 90)
        print(f"✅ Processed {total_players_fixed} players across {len(self.affected_rounds)} rounds")

        if self.apply_fixes:
            print("📝 Changes APPLIED to database")
        else:
            print("🟡 DRY-RUN: No changes made. Use --apply to commit.")

        print("=" * 90 + "\n")


async def main():
    logger.info("Script started: %s", __file__)
    parser = argparse.ArgumentParser(
        description="Fix DPM for R2 rounds with inflated time_played_seconds"
    )
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Apply fixes to database (default is dry-run)'
    )

    args = parser.parse_args()

    # Initialize database connection
    db = DatabaseAdapter(
        db_type='postgres',
        host='localhost',
        port=5432,
        database='etlegacy',
        user='etlegacy_user',
        password=None,  # Will use .env
    )

    try:
        await db.connect()

        fixer = R2TimeFixer(db, apply_fixes=args.apply)
        await fixer.run()

    finally:
        await db.close()


if __name__ == '__main__':
    asyncio.run(main())
