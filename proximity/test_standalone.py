#!/usr/bin/env python3
"""
PROXIMITY TRACKER - STANDALONE TEST SCRIPT

This script tests the proximity system WITHOUT touching the bot.
It creates its own database connection and can:
1. Parse test files
2. Import to database
3. Query results
4. Clean up test data

USAGE:
    # Test parser only (no DB)
    python3 test_standalone.py --parse-only <file>

    # Test with database
    python3 test_standalone.py --full-test <file>

    # Clean up test data from today
    python3 test_standalone.py --cleanup

    # Create sample test file
    python3 test_standalone.py --create-sample
"""

import os
import sys
import argparse
import asyncio
import logging
from datetime import date
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from parser.parser import ProximityParserV4, PlayerTrack, PathPoint

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# DATABASE ADAPTER (Standalone - doesn't use bot's adapter)
# =============================================================================

class StandaloneDBAdapter:
    """Minimal async database adapter for testing"""

    def __init__(self, host: str, port: int, user: str, password: str, database: str):
        self.dsn = f"postgresql://{user}:{password}@{host}:{port}/{database}"
        self.pool = None

    async def connect(self):
        """Create connection pool"""
        try:
            import asyncpg
            self.pool = await asyncpg.create_pool(self.dsn, min_size=1, max_size=5)
            logger.info(f"Connected to database")
            return True
        except ImportError:
            logger.error("asyncpg not installed. Run: pip install asyncpg")
            return False
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False

    async def close(self):
        """Close connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection closed")

    async def execute(self, query: str, params: tuple = None):
        """Execute a query"""
        async with self.pool.acquire() as conn:
            if params:
                await conn.execute(query, *params)
            else:
                await conn.execute(query)

    async def fetch(self, query: str, params: tuple = None):
        """Fetch results"""
        async with self.pool.acquire() as conn:
            if params:
                return await conn.fetch(query, *params)
            else:
                return await conn.fetch(query)

    async def fetchone(self, query: str, params: tuple = None):
        """Fetch one result"""
        async with self.pool.acquire() as conn:
            if params:
                return await conn.fetchrow(query, *params)
            else:
                return await conn.fetchrow(query)


# =============================================================================
# TEST FUNCTIONS
# =============================================================================

def create_sample_file(output_path: str):
    """Create a sample v4 engagement file for testing"""

    sample_content = """# PROXIMITY_TRACKER_V4
# map=test_map
# round=1
# crossfire_window=1000
# escape_time=5000
# escape_distance=300
# position_sample_interval=1000
# ENGAGEMENTS
# id;start_time;end_time;duration;target_guid;target_name;target_team;outcome;total_damage;killer_guid;killer_name;num_attackers;is_crossfire;crossfire_delay;crossfire_participants;start_x;start_y;start_z;end_x;end_y;end_z;distance_traveled;positions;attackers
1;10000;15000;5000;TEST_GUID_1;TestPlayer1;AXIS;killed;150;TEST_GUID_2;TestPlayer2;1;0;;;100.0;200.0;50.0;150.0;250.0;50.0;70.7;10000,100.0,200.0,50.0,start|12000,120.0,220.0,50.0,sample|15000,150.0,250.0,50.0,death;TEST_GUID_2,TestPlayer2,ALLIES,150,3,10000,15000,1,5:3;

# PLAYER_TRACKS
# guid;name;team;class;spawn_time;death_time;first_move_time;samples;path
# path format: time,x,y,z,health,speed,weapon,stance,sprint,event separated by |
# stance: 0=standing, 1=crouching, 2=prone | sprint: 0=no, 1=yes
TEST_GUID_1;TestPlayer1;AXIS;SOLDIER;5000;15000;5500;11;5000,0.0,0.0,0.0,100,0.0,8,0,0,spawn|6000,50.0,50.0,0.0,100,70.7,8,0,1,sample|7000,100.0,100.0,0.0,100,70.7,8,0,1,sample|8000,100.0,150.0,0.0,100,50.0,8,0,0,sample|9000,100.0,180.0,0.0,100,30.0,8,1,0,sample|10000,100.0,200.0,50.0,100,52.0,8,0,0,sample|11000,110.0,210.0,50.0,85,14.1,8,0,0,sample|12000,120.0,220.0,50.0,70,14.1,8,0,0,sample|13000,130.0,230.0,50.0,50,14.1,8,2,0,sample|14000,140.0,240.0,50.0,30,14.1,8,2,0,sample|15000,150.0,250.0,50.0,0,0.0,8,0,0,death
TEST_GUID_2;TestPlayer2;ALLIES;MEDIC;5000;0;5200;6;5000,500.0,500.0,0.0,100,0.0,10,0,0,spawn|6000,450.0,450.0,0.0,100,70.7,10,0,1,sample|7000,400.0,400.0,0.0,100,70.7,10,0,1,sample|8000,350.0,350.0,0.0,100,70.7,10,0,1,sample|9000,300.0,300.0,0.0,100,70.7,10,0,0,sample|20000,250.0,280.0,0.0,100,25.0,10,0,0,round_end

# KILL_HEATMAP
# grid_x;grid_y;axis_kills;allies_kills
0;0;0;1

# MOVEMENT_HEATMAP
# grid_x;grid_y;traversal;combat;escape
0;0;15;5;0
0;1;8;2;1
"""

    with open(output_path, 'w') as f:
        f.write(sample_content)

    logger.info(f"Created sample file: {output_path}")
    return output_path


def test_parse_only(filepath: str) -> bool:
    """Test parsing without database"""

    logger.info(f"=== PARSE-ONLY TEST ===")
    logger.info(f"File: {filepath}")

    parser = ProximityParserV4()

    if not parser.parse_file(filepath):
        logger.error("Parse failed!")
        return False

    stats = parser.get_stats()

    logger.info(f"\n=== PARSE RESULTS ===")
    logger.info(f"Map: {stats['map']}, Round: {stats['round']}")
    logger.info(f"Engagements: {stats['total_engagements']}")
    logger.info(f"  Crossfire: {stats['crossfire_engagements']}")
    logger.info(f"  Kills: {stats['kills']}")
    logger.info(f"  Escapes: {stats['escapes']}")
    logger.info(f"Player Tracks: {stats['total_tracks']}")
    logger.info(f"  Total samples: {stats['total_samples']}")
    logger.info(f"  Total distance: {stats['total_distance']:.1f} units")
    logger.info(f"Heatmap cells: {stats['heatmap_cells']}")

    if parser.player_tracks:
        logger.info(f"\n=== TRACK DETAILS ===")
        for i, track in enumerate(parser.player_tracks):
            logger.info(f"\nTrack {i+1}: {track.name} ({track.player_class})")
            logger.info(f"  Team: {track.team}")
            logger.info(f"  Duration: {track.duration_ms}ms")
            logger.info(f"  Distance: {track.total_distance:.1f} units")
            logger.info(f"  Avg speed: {track.avg_speed:.1f}")
            logger.info(f"  Sprint %: {track.sprint_percentage:.1f}%")
            logger.info(f"  Time to first move: {track.time_to_first_move_ms}ms")
            logger.info(f"  Path samples: {len(track.path)}")

            if track.path:
                logger.info(f"  First point: {track.path[0].event} at ({track.path[0].x}, {track.path[0].y})")
                logger.info(f"  Last point: {track.path[-1].event} at ({track.path[-1].x}, {track.path[-1].y})")

    logger.info(f"\n=== PARSE TEST PASSED ===")
    return True


async def test_full_import(filepath: str, db_config: dict) -> bool:
    """Test full import with database"""

    logger.info(f"=== FULL IMPORT TEST ===")
    logger.info(f"File: {filepath}")

    # Connect to database
    db = StandaloneDBAdapter(**db_config)
    if not await db.connect():
        return False

    try:
        # Parse and import
        parser = ProximityParserV4(db_adapter=db)

        session_date = date.today().isoformat()
        logger.info(f"Session date: {session_date}")

        if not await parser.import_file(filepath, session_date):
            logger.error("Import failed!")
            return False

        # Verify data was inserted
        logger.info(f"\n=== VERIFYING DATABASE ===")

        # Check engagements
        result = await db.fetchone(
            "SELECT COUNT(*) as cnt FROM combat_engagement WHERE session_date = $1",
            (date.today(),)
        )
        logger.info(f"Engagements inserted: {result['cnt']}")

        # Check tracks
        result = await db.fetchone(
            "SELECT COUNT(*) as cnt FROM player_track WHERE session_date = $1",
            (date.today(),)
        )
        logger.info(f"Tracks inserted: {result['cnt']}")

        # Check player stats
        result = await db.fetchone("SELECT COUNT(*) as cnt FROM player_teamplay_stats")
        logger.info(f"Player stats rows: {result['cnt']}")

        # Show sample track data
        tracks = await db.fetch(
            """SELECT player_name, player_class, duration_ms, total_distance, sprint_percentage
               FROM player_track WHERE session_date = $1""",
            (date.today(),)
        )
        if tracks:
            logger.info(f"\n=== TRACK DATA IN DB ===")
            for t in tracks:
                logger.info(f"  {t['player_name']} ({t['player_class']}): "
                           f"{t['duration_ms']}ms, {t['total_distance']:.1f} units, "
                           f"{t['sprint_percentage']:.1f}% sprint")

        logger.info(f"\n=== FULL IMPORT TEST PASSED ===")
        return True

    finally:
        await db.close()


async def cleanup_test_data(db_config: dict, session_date: str = None):
    """Remove test data from database"""

    if session_date is None:
        session_date = date.today().isoformat()

    logger.info(f"=== CLEANUP TEST DATA ===")
    logger.info(f"Session date: {session_date}")

    db = StandaloneDBAdapter(**db_config)
    if not await db.connect():
        return False

    try:
        # Delete from all proximity tables
        tables = [
            ("combat_engagement", "session_date"),
            ("player_track", "session_date"),
        ]

        for table, date_col in tables:
            result = await db.fetch(
                f"DELETE FROM {table} WHERE {date_col} = $1 RETURNING id",
                (date.fromisoformat(session_date),)
            )
            logger.info(f"Deleted {len(result)} rows from {table}")

        logger.info(f"\n=== CLEANUP COMPLETE ===")
        return True

    finally:
        await db.close()


async def show_db_status(db_config: dict):
    """Show current database status"""

    logger.info(f"=== DATABASE STATUS ===")

    db = StandaloneDBAdapter(**db_config)
    if not await db.connect():
        return False

    try:
        tables = [
            "combat_engagement",
            "player_track",
            "player_teamplay_stats",
            "crossfire_pairs",
            "map_kill_heatmap",
            "map_movement_heatmap"
        ]

        for table in tables:
            try:
                result = await db.fetchone(f"SELECT COUNT(*) as cnt FROM {table}")
                logger.info(f"  {table}: {result['cnt']} rows")
            except Exception as e:
                logger.warning(f"  {table}: ERROR - {e}")

        return True

    finally:
        await db.close()


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Proximity Tracker Standalone Test Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument("--parse-only", metavar="FILE",
                       help="Parse file without database")
    parser.add_argument("--full-test", metavar="FILE",
                       help="Parse and import to database")
    parser.add_argument("--cleanup", action="store_true",
                       help="Remove today's test data from database")
    parser.add_argument("--cleanup-date", metavar="DATE",
                       help="Remove specific date's data (YYYY-MM-DD)")
    parser.add_argument("--create-sample", metavar="FILE", nargs="?",
                       const="test_sample.txt",
                       help="Create sample test file")
    parser.add_argument("--status", action="store_true",
                       help="Show database status")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Verbose output")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Database config (same as bot, but standalone connection)
    db_config = {
        "host": "192.168.64.116",
        "port": 5432,
        "user": "etlegacy_user",
        "password": "etlegacy_secure_2025",
        "database": "etlegacy"
    }

    # Handle commands
    if args.create_sample:
        create_sample_file(args.create_sample)
        return 0

    if args.parse_only:
        if not os.path.exists(args.parse_only):
            logger.error(f"File not found: {args.parse_only}")
            return 1
        success = test_parse_only(args.parse_only)
        return 0 if success else 1

    if args.full_test:
        if not os.path.exists(args.full_test):
            logger.error(f"File not found: {args.full_test}")
            return 1
        success = asyncio.run(test_full_import(args.full_test, db_config))
        return 0 if success else 1

    if args.cleanup:
        asyncio.run(cleanup_test_data(db_config))
        return 0

    if args.cleanup_date:
        asyncio.run(cleanup_test_data(db_config, args.cleanup_date))
        return 0

    if args.status:
        asyncio.run(show_db_status(db_config))
        return 0

    # No command - show help
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
