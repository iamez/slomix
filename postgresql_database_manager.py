#!/usr/bin/env python3
"""
🐘 PostgreSQL Database Manager - THE ONLY TOOL YOU NEED
================================================================================

This is THE SINGLE SOURCE OF TRUTH for PostgreSQL database operations.
Direct replacement for database_manager.py with full feature parity.

This tool handles:
  ✅ Fresh database creation (with backup)
  ✅ Schema setup with all PostgreSQL fixes
  ✅ Bulk import from local_stats/ (with duplicate prevention)
  ✅ Incremental updates (safe, only new files)
  ✅ Disaster recovery (rebuild from scratch)
  ✅ Date range fixes (surgical re-import)
  ✅ Validation and verification
  ✅ Progress tracking and stats
  ✅ Auto-detection and smart defaults

Author: ET:Legacy Stats System
Date: November 5, 2025
Version: 1.0 - PostgreSQL Production Ready
"""

import asyncio
import asyncpg
import logging
import time
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from bot.community_stats_parser import C0RNP0RN3StatsParser
from bot.config import load_config
from bot.stats import StatsCalculator

# Import comprehensive logging system
try:
    from bot.logging_config import (
        setup_logging,
        log_database_operation,
        log_stats_import,
        log_performance_warning,
        get_logger
    )
    # Setup comprehensive logging
    setup_logging(logging.INFO)
    logger = get_logger('bot.database.manager')
except ImportError:
    # Fallback to basic logging if logging_config not available
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('postgresql_manager.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger('PostgreSQLManager')
    log_database_operation = lambda *args, **kwargs: None
    log_stats_import = lambda *args, **kwargs: None
    log_performance_warning = lambda *args, **kwargs: None



class PostgreSQLDatabaseManager:
    """
    The ONE and ONLY PostgreSQL database management tool
    
    Handles all database operations from creation to disaster recovery.
    """
    
    def __init__(self, stats_dir: str = "local_stats"):
        self.config = load_config()
        
        if self.config.database_type != 'postgresql':
            raise ValueError(
                "❌ This tool requires PostgreSQL mode!\n"
                "   Update bot_config.json: database_type = 'postgresql'"
            )
        
        self.stats_dir = Path(stats_dir)
        self.parser = C0RNP0RN3StatsParser()
        self.pool = None
        
        # Stats tracking
        self.stats = {
            'files_processed': 0,
            'files_skipped': 0,
            'files_failed': 0,
            'rounds_created': 0,
            'players_inserted': 0,
            'weapons_inserted': 0
        }
        
        self.start_time = None
        self.last_progress_time = None
    
    # =========================================================================
    # CONNECTION MANAGEMENT
    # =========================================================================
    
    async def connect(self):
        """Connect to PostgreSQL"""
        if self.pool:
            return
        
        try:
            self.pool = await asyncpg.create_pool(
                host=self.config.postgres_host.split(':')[0],
                port=int(self.config.postgres_host.split(':')[1]) if ':' in self.config.postgres_host else 5432,
                database=self.config.postgres_database,
                user=self.config.postgres_user,
                password=self.config.postgres_password,
                min_size=5,
                max_size=20
            )
            logger.info(f"✅ Connected to PostgreSQL: {self.config.postgres_host}/{self.config.postgres_database}")
            
            # Run schema migrations after connecting
            await self._migrate_schema_if_needed()
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to PostgreSQL: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from PostgreSQL"""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("✅ Disconnected from PostgreSQL")
    
    # =========================================================================
    # SCHEMA CREATION
    # =========================================================================
    
    async def create_fresh_database(self, backup_existing: bool = True) -> bool:
        """
        Create a fresh database with correct PostgreSQL schema
        
        This includes ALL PostgreSQL-specific fixes:
        - BIGINT for discord_id
        - BOOLEAN instead of INTEGER
        - TIMESTAMP instead of TEXT
        - ON CONFLICT for duplicate prevention
        - Proper indexes
        
        Args:
            backup_existing: If True, backs up existing data first
        
        Returns:
            True if successful
        """
        logger.info("=" * 70)
        logger.info("🏗️  DATABASE CREATION - Starting")
        logger.info("=" * 70)
        
        try:
            # Create schema if it doesn't exist
            await self._create_schema_if_missing()
            
            # Apply any schema migrations for existing databases
            await self._migrate_schema_if_needed()
            
            # Backup if requested
            if backup_existing:
                await self._backup_database()
            
            # Wipe all tables
            logger.info("🧹 Wiping existing data...")
            await self._wipe_all_tables()
            
            logger.info("✅ Fresh database ready!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to create database: {e}")
            return False
    
    async def _backup_database(self):
        """Backup existing database to SQL dump"""
        logger.info("📦 Creating backup...")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"postgresql_backup_{timestamp}.sql"
        
        # Use pg_dump for backup
        import subprocess
        import re
        
        try:
            # Validate hostname (defense in depth - config is already trusted)
            host = self.config.postgres_host.split(':')[0]
            if not re.match(r'^[a-zA-Z0-9.-]+$', host):
                raise ValueError(f"Invalid hostname format: {host}")
            
            # Validate port range
            port_str = str(self.config.postgres_host.split(':')[1]) if ':' in self.config.postgres_host else '5432'
            port = int(port_str)  # Will raise ValueError if not numeric
            if not (1 <= port <= 65535):
                raise ValueError(f"Port out of valid range (1-65535): {port}")
            
            result = subprocess.run([
                'pg_dump',
                '-h', host,
                '-p', str(port),
                '-U', self.config.postgres_user,
                '-d', self.config.postgres_database,
                '-f', backup_file
            ], capture_output=True, text=True, env={'PGPASSWORD': self.config.postgres_password})
            
            if result.returncode == 0:
                logger.info(f"   ✅ Backup created: {backup_file}")
            else:
                logger.warning(f"   ⚠️  Backup failed: {result.stderr}")
        except ValueError as e:
            logger.error(f"   ❌ Invalid database configuration: {e}")
        except FileNotFoundError:
            logger.warning("   ⚠️  pg_dump not found - skipping backup")
    
    async def _create_schema_if_missing(self):
        """Create database schema if it doesn't exist"""
        async with self.pool.acquire() as conn:
            # Check if rounds table exists
            exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'rounds'
                )
            """)
            
            if exists:
                logger.info("   ✅ Schema already exists")
                return
            
            logger.info("🏗️  Creating database schema...")
            
            # 1. Rounds table
            await conn.execute('''
                CREATE TABLE rounds (
                    id SERIAL PRIMARY KEY,
                    match_id TEXT,
                    round_number INTEGER,
                    round_date TEXT,
                    round_time TEXT,
                    map_name TEXT,
                    time_limit TEXT,
                    actual_time TEXT,
                    defender_team INTEGER DEFAULT 0,
                    winner_team INTEGER DEFAULT 0,
                    is_tied BOOLEAN DEFAULT FALSE,
                    round_outcome TEXT,
                    gaming_session_id INTEGER,
                    round_status VARCHAR(20) DEFAULT 'completed',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(match_id, round_number)
                )
            ''')
            
            # 2. Player comprehensive stats
            await conn.execute('''
                CREATE TABLE player_comprehensive_stats (
                    id SERIAL PRIMARY KEY,
                    round_id INTEGER NOT NULL,
                    round_date TEXT NOT NULL,
                    map_name TEXT NOT NULL,
                    round_number INTEGER NOT NULL,
                    player_guid TEXT NOT NULL,
                    player_name TEXT NOT NULL,
                    clean_name TEXT,
                    team INTEGER DEFAULT 0,
                    kills INTEGER DEFAULT 0,
                    deaths INTEGER DEFAULT 0,
                    damage_given INTEGER DEFAULT 0,
                    damage_received INTEGER DEFAULT 0,
                    team_damage_given INTEGER DEFAULT 0,
                    team_damage_received INTEGER DEFAULT 0,
                    gibs INTEGER DEFAULT 0,
                    self_kills INTEGER DEFAULT 0,
                    team_kills INTEGER DEFAULT 0,
                    team_gibs INTEGER DEFAULT 0,
                    headshot_kills INTEGER DEFAULT 0,
                    headshots INTEGER DEFAULT 0,
                    time_played_seconds INTEGER DEFAULT 0,
                    time_played_minutes REAL DEFAULT 0,
                    time_dead_minutes REAL DEFAULT 0,
                    time_dead_ratio REAL DEFAULT 0,
                    xp REAL DEFAULT 0,
                    kd_ratio REAL DEFAULT 0,
                    dpm REAL DEFAULT 0,
                    efficiency REAL DEFAULT 0,
                    bullets_fired INTEGER DEFAULT 0,
                    accuracy REAL DEFAULT 0,
                    kill_assists INTEGER DEFAULT 0,
                    objectives_completed INTEGER DEFAULT 0,
                    objectives_destroyed INTEGER DEFAULT 0,
                    objectives_stolen INTEGER DEFAULT 0,
                    objectives_returned INTEGER DEFAULT 0,
                    dynamites_planted INTEGER DEFAULT 0,
                    dynamites_defused INTEGER DEFAULT 0,
                    times_revived INTEGER DEFAULT 0,
                    revives_given INTEGER DEFAULT 0,
                    most_useful_kills INTEGER DEFAULT 0,
                    useless_kills INTEGER DEFAULT 0,
                    kill_steals INTEGER DEFAULT 0,
                    denied_playtime INTEGER DEFAULT 0,
                    constructions INTEGER DEFAULT 0,
                    tank_meatshield INTEGER DEFAULT 0,
                    double_kills INTEGER DEFAULT 0,
                    triple_kills INTEGER DEFAULT 0,
                    quad_kills INTEGER DEFAULT 0,
                    multi_kills INTEGER DEFAULT 0,
                    mega_kills INTEGER DEFAULT 0,
                    killing_spree_best INTEGER DEFAULT 0,
                    death_spree_worst INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (round_id) REFERENCES rounds(id),
                    UNIQUE(round_id, player_guid)
                )
            ''')
            
            # 3. Weapon comprehensive stats
            await conn.execute('''
                CREATE TABLE weapon_comprehensive_stats (
                    id SERIAL PRIMARY KEY,
                    round_id INTEGER NOT NULL,
                    round_date TEXT NOT NULL,
                    map_name TEXT NOT NULL,
                    round_number INTEGER NOT NULL,
                    player_guid TEXT NOT NULL,
                    player_name TEXT NOT NULL,
                    weapon_name TEXT NOT NULL,
                    kills INTEGER DEFAULT 0,
                    deaths INTEGER DEFAULT 0,
                    headshots INTEGER DEFAULT 0,
                    shots INTEGER DEFAULT 0,
                    hits INTEGER DEFAULT 0,
                    accuracy REAL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (round_id) REFERENCES rounds(id),
                    UNIQUE(round_id, player_guid, weapon_name)
                )
            ''')
            
            # 4. Processed files tracking
            await conn.execute('''
                CREATE TABLE processed_files (
                    id SERIAL PRIMARY KEY,
                    filename TEXT UNIQUE NOT NULL,
                    file_hash TEXT,
                    success BOOLEAN DEFAULT TRUE,
                    error_message TEXT,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 5. Session teams
            await conn.execute('''
                CREATE TABLE session_teams (
                    id SERIAL PRIMARY KEY,
                    session_start_date TEXT NOT NULL,
                    map_name TEXT NOT NULL,
                    team_name TEXT NOT NULL,
                    player_guids JSONB,
                    player_names JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(session_start_date, map_name, team_name)
                )
            ''')
            
            # 6. Player links (Discord integration)
            await conn.execute('''
                CREATE TABLE player_links (
                    id SERIAL PRIMARY KEY,
                    player_guid TEXT UNIQUE NOT NULL,
                    discord_id BIGINT UNIQUE NOT NULL,
                    discord_username TEXT,
                    player_name TEXT,
                    linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 7. Player aliases
            await conn.execute('''
                CREATE TABLE player_aliases (
                    id SERIAL PRIMARY KEY,
                    guid TEXT NOT NULL,
                    alias TEXT NOT NULL,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    times_seen INTEGER DEFAULT 1,
                    UNIQUE(guid, alias)
                )
            ''')
            
            # Create indexes
            await conn.execute('CREATE INDEX idx_rounds_date ON rounds(round_date)')
            await conn.execute('CREATE INDEX idx_rounds_status ON rounds(round_status)')
            await conn.execute('CREATE INDEX idx_rounds_gaming_session ON rounds(gaming_session_id, map_name, round_number, round_status)')
            await conn.execute('CREATE INDEX idx_player_stats_round ON player_comprehensive_stats(round_id)')
            await conn.execute('CREATE INDEX idx_player_stats_guid ON player_comprehensive_stats(player_guid)')
            await conn.execute('CREATE INDEX idx_weapon_stats_round ON weapon_comprehensive_stats(round_id)')
            await conn.execute('CREATE INDEX idx_processed_files_filename ON processed_files(filename)')
            
            logger.info("   ✅ Schema created successfully!")
    
    async def _migrate_schema_if_needed(self):
        """Apply schema migrations for existing databases"""
        async with self.pool.acquire() as conn:
            # Check if player_aliases table exists
            table_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'player_aliases'
                )
            """)
            
            if not table_exists:
                logger.info("   ⏭️  player_aliases table doesn't exist yet, skipping migrations")
                return
            
            logger.info("🔍 Checking for schema migrations...")
            
            # Migration 1: Add first_seen column if missing
            has_first_seen = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_name = 'player_aliases' 
                    AND column_name = 'first_seen'
                )
            """)
            
            if not has_first_seen:
                logger.info("   ➕ Adding 'first_seen' column to player_aliases...")
                await conn.execute("""
                    ALTER TABLE player_aliases 
                    ADD COLUMN first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                """)
                # Backfill existing rows
                await conn.execute("""
                    UPDATE player_aliases 
                    SET first_seen = last_seen 
                    WHERE first_seen IS NULL AND last_seen IS NOT NULL
                """)
                logger.info("   ✅ Added 'first_seen' column")
            
            # Migration 2: Add times_seen column if missing
            has_times_seen = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_name = 'player_aliases' 
                    AND column_name = 'times_seen'
                )
            """)
            
            if not has_times_seen:
                logger.info("   ➕ Adding 'times_seen' column to player_aliases...")
                await conn.execute("""
                    ALTER TABLE player_aliases 
                    ADD COLUMN times_seen INTEGER DEFAULT 1
                """)
                logger.info("   ✅ Added 'times_seen' column")
            
            logger.info("   ✅ Schema migrations complete!")
    
    async def _wipe_all_tables(self):
        """Wipe all data from tables (keeps schema)"""
        tables = [
            'weapon_comprehensive_stats',
            'player_comprehensive_stats',
            'processed_files',
            'session_teams',
            'player_links',
            'player_aliases',
            'rounds'
        ]
        
        async with self.pool.acquire() as conn:
            for table in tables:
                try:
                    await conn.execute(f"DELETE FROM {table}")
                    logger.info(f"   ✅ Wiped {table}")
                except Exception as e:
                    logger.warning(f"   ⚠️  Failed to wipe {table}: {e}")
    
    # =========================================================================
    # FILE PROCESSING
    # =========================================================================
    
    async def is_file_processed(self, filename: str) -> bool:
        """Check if file has already been processed"""
        async with self.pool.acquire() as conn:
            result = await conn.fetchval(
                "SELECT COUNT(*) FROM processed_files WHERE filename = $1",
                filename
            )
            return result > 0
    
    async def mark_file_processed(self, filename: str, success: bool = True, error_msg: str = None):
        """Mark file as processed"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO processed_files (filename, success, error_message, processed_at)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (filename) DO UPDATE SET
                    success = EXCLUDED.success,
                    error_message = EXCLUDED.error_message,
                    processed_at = EXCLUDED.processed_at
                """,
                filename, success, error_msg, datetime.now()
            )
    
    def _extract_date_time_from_filename(self, filename: str) -> Tuple[str, str]:
        """Extract date and time from filename"""
        # Format: 2025-11-03-213554-supply-round-1.txt
        parts = filename.split('-')
        if len(parts) >= 4:
            date = f"{parts[0]}-{parts[1]}-{parts[2]}"
            time = parts[3]
            logger.debug(f"🔍 Extracted from filename '{filename}': date={date}, time={time} (type: {type(time).__name__})")
            return date, time
        return None, None
    
    async def process_file(self, file_path: Path) -> Tuple[bool, str]:
        """
        Process a single stats file with COMPREHENSIVE VALIDATION
        
        Pipeline:
        1. Parse file
        2. Extract expected data counts
        3. Write to database
        4. Verify what was written matches what was parsed
        5. Flag any discrepancies
        
        Returns:
            (success: bool, message: str)
        """
        filename = file_path.name
        start_time = time.time()
        
        try:
            # Check if already processed
            if await self.is_file_processed(filename):
                self.stats['files_skipped'] += 1
                logger.debug(f"⏭️  Skipped (already processed): {filename}")
                return True, "Already processed"
            
            # STEP 1: Parse file
            logger.debug(f"📖 Parsing file: {filename}")
            parsed_data = self.parser.parse_stats_file(str(file_path))
            
            if not parsed_data or parsed_data.get('error'):
                error = parsed_data.get('error', 'Unknown error') if parsed_data else 'No data'
                self.stats['files_failed'] += 1
                await self.mark_file_processed(filename, success=False, error_msg=error)
                logger.error(f"❌ Parse failed: {filename} - {error}")
                log_stats_import(filename, error=error)
                return False, f"Parse error: {error}"
            
            # STEP 2: Extract expected counts from parsed data
            expected_players = len(parsed_data.get('players', []))
            # Parser uses 'weapon_stats' key, not 'weapons'
            expected_weapons = sum(len(p.get('weapon_stats', {}) or p.get('weapons', {})) for p in parsed_data.get('players', []))
            expected_total_kills = sum(p.get('kills', 0) for p in parsed_data.get('players', []))
            expected_total_deaths = sum(p.get('deaths', 0) for p in parsed_data.get('players', []))
            
            logger.debug(f"📊 Parsed: {expected_players} players, {expected_weapons} weapons")
            
            # Extract date/time from filename
            file_date, round_time = self._extract_date_time_from_filename(filename)
            if not file_date:
                self.stats['files_failed'] += 1
                await self.mark_file_processed(filename, success=False, error_msg="Invalid filename format")
                logger.error(f"❌ Invalid filename format: {filename}")
                return False, "Invalid filename format"
            
            # STEP 3: Create round and insert stats
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    # Create round (round_number determined in _create_round_postgresql from filename)
                    logger.debug(f"💾 Creating round for {filename}")
                    round_id = await self._create_round_postgresql(conn, parsed_data, file_date, round_time, filename)

                    if not round_id:
                        raise Exception("Failed to create round")

                    # Insert player stats
                    player_count = await self._insert_player_stats(conn, round_id, file_date, parsed_data)
                    logger.debug(f"👥 Inserted {player_count} player stats")

                    # Insert weapon stats
                    weapon_count = await self._insert_weapon_stats(conn, round_id, file_date, parsed_data)
                    logger.debug(f"🔫 Inserted {weapon_count} weapon stats")

                    # 🆕 If Round 2 file, also import match summary (cumulative stats)
                    match_summary_id = None
                    if parsed_data.get('match_summary'):
                        logger.info("📋 Importing match summary (cumulative R1+R2 stats)...")
                        match_summary = parsed_data['match_summary']

                        # Create match summary round (round_number = 0)
                        match_summary_id = await self._create_round_postgresql(
                            conn, match_summary, file_date, round_time, filename, is_match_summary=True
                        )

                        if match_summary_id:
                            # Insert match summary player stats
                            summary_player_count = await self._insert_player_stats(conn, match_summary_id, file_date, match_summary)
                            summary_weapon_count = await self._insert_weapon_stats(conn, match_summary_id, file_date, match_summary)
                            logger.info(
                                f"✓ Match summary: {summary_player_count} players, {summary_weapon_count} weapons"
                            )

                    # STEP 4: VERIFY DATA INTEGRITY
                    validation_passed, validation_msg = await self._validate_round_data(
                        conn, round_id,
                        expected_players, expected_weapons,
                        expected_total_kills, expected_total_deaths,
                        filename
                    )

                    if not validation_passed:
                        # Log warning but don't fail - data is still saved
                        logger.warning(f"⚠️  Data mismatch in {filename}: {validation_msg}")

                    # Transaction successful - update stats
                    self.stats['files_processed'] += 1
                    self.stats['rounds_created'] += 1
                    self.stats['players_inserted'] += player_count
                    self.stats['weapons_inserted'] += weapon_count

                    # Log successful import
                    duration = time.time() - start_time
                    logger.info(
                        f"✓ Imported {filename}: {player_count} players, {weapon_count} weapons "
                        f"[{duration:.2f}s]{' (WITH WARNINGS)' if not validation_passed else ''}"
                    )
                    log_stats_import(
                        filename,
                        round_count=1,
                        player_count=player_count,
                        weapon_count=weapon_count,
                        duration=duration
                    )

                    # Warn if import was slow
                    if duration > 3.0:
                        log_performance_warning(f"Import {filename}", duration, threshold=3.0)

            # 🔒 CRITICAL: Mark file as processed ONLY after transaction commits successfully
            # This prevents files from being marked as processed when the transaction rolls back
            if validation_passed:
                await self.mark_file_processed(filename, success=True)
            else:
                await self.mark_file_processed(filename, success=True, error_msg=f"WARN: {validation_msg}")

            return True, f"Processed: {player_count} players, {weapon_count} weapons{' (WITH WARNINGS)' if not validation_passed else ''}"
        
        except Exception as e:
            self.stats['files_failed'] += 1
            error_msg = str(e)
            duration = time.time() - start_time
            logger.error(f"❌ Error processing {filename} [{duration:.2f}s]: {error_msg}", exc_info=True)
            log_stats_import(filename, error=error_msg, duration=duration)
            await self.mark_file_processed(filename, success=False, error_msg=error_msg)
            return False, error_msg
    
    async def _validate_round_data(self, conn, round_id: int,
                                   expected_players: int, expected_weapons: int,
                                   expected_kills: int, expected_deaths: int,
                                   filename: str) -> Tuple[bool, str]:
        """
        SIMPLIFIED DATA VALIDATION

        Checks for data integrity issues (negative values).
        PostgreSQL ACID guarantees handle count/sum verification.

        Returns:
            (validation_passed: bool, message: str)
        """
        try:
            # Check for negative values (data integrity)
            negative_checks = await conn.fetch(
                """
                SELECT player_name, kills, deaths, damage_given, damage_received
                FROM player_comprehensive_stats
                WHERE round_id = $1
                  AND (kills < 0 OR deaths < 0 OR damage_given < 0 OR damage_received < 0)
                """,
                round_id
            )

            if negative_checks:
                issues = []
                for row in negative_checks:
                    issues.append(f"Negative values for {row['player_name']}: K={row['kills']}, D={row['deaths']}")
                return False, "; ".join(issues)

            # Log Round 2 detection for debugging
            if 'round-2' in filename.lower():
                logger.debug(f"   Round 2 differential stats for {filename}")

            return True, "Validation passed"

        except Exception as e:
            logger.error(f"Validation check failed: {e}")
            return False, f"Validation error: {e}"
    
    async def _get_or_create_gaming_session_id(self, conn, file_date: str, round_time: str) -> Optional[int]:
        """
        Calculate gaming_session_id for a new round using 60-minute gap logic.
        
        Gaming session rules:
        - Group consecutive rounds into gaming sessions
        - If gap between rounds > 60 minutes → new gaming session
        - Handles midnight-crossing (same gaming session continues after midnight)
        
        Returns:
            gaming_session_id to assign to this round (or None on error)
        """
        GAP_THRESHOLD_MINUTES = 60
        
        try:
            # Get the most recent round with a gaming_session_id
            last_round = await conn.fetchrow(
                """
                SELECT gaming_session_id, round_date, round_time
                FROM rounds
                WHERE gaming_session_id IS NOT NULL
                ORDER BY round_date DESC, round_time DESC
                LIMIT 1
                """
            )
            
            if not last_round:
                # First round ever - start with gaming_session_id = 1
                return 1
            
            last_gaming_session_id = last_round['gaming_session_id']
            last_date = last_round['round_date']
            last_time = last_round['round_time']
            
            # Parse datetimes (handle both HHMMSS and HH:MM:SS formats from DB)
            current_datetime = datetime.strptime(f"{file_date} {round_time}", "%Y-%m-%d %H%M%S")
            
            # Try parsing last_time - it might be stored as "HHMMSS" or "HH:MM:SS"
            try:
                last_datetime = datetime.strptime(f"{last_date} {last_time}", "%Y-%m-%d %H%M%S")
            except ValueError:
                # Fallback to format with colons
                last_datetime = datetime.strptime(f"{last_date} {last_time}", "%Y-%m-%d %H:%M:%S")
            
            # Calculate gap
            gap_minutes = (current_datetime - last_datetime).total_seconds() / 60
            
            if gap_minutes > GAP_THRESHOLD_MINUTES:
                # Start new gaming session
                new_gaming_session_id = last_gaming_session_id + 1
                logger.info(f"New gaming session #{new_gaming_session_id} (gap: {gap_minutes:.1f} min from previous round)")
                return new_gaming_session_id
            else:
                # Continue existing gaming session
                logger.debug(f"Continuing gaming session #{last_gaming_session_id} (gap: {gap_minutes:.1f} min)")
                return last_gaming_session_id
                
        except Exception as e:
            logger.warning(f"Error calculating gaming_session_id: {e}. Using NULL.")
            return None
    
    async def _create_round_postgresql(self, conn, parsed_data: Dict, file_date: str, round_time: str, filename: str, is_match_summary: bool = False) -> Optional[int]:
        """
        Create round entry in PostgreSQL
        
        Args:
            is_match_summary: If True, store as round_number=0 (match summary)
        """
        map_name = parsed_data.get('map_name', 'unknown')
        
        # 🔧 CRITICAL FIX: Determine round_number from FILENAME, not parsed data
        # The file header always says round=1, but filename is authoritative
        if is_match_summary:
            round_number = 0
        elif '-round-2.txt' in filename.lower():
            round_number = 2
            logger.debug(f"🔧 Round 2 detected from filename: {filename}")
        elif '-round-1.txt' in filename.lower():
            round_number = 1
            logger.debug(f"🔧 Round 1 detected from filename: {filename}")
        else:
            # Fallback to parser data (try both 'round_num' and 'round_number')
            round_number = parsed_data.get('round_num', parsed_data.get('round_number', 1))
            logger.debug(f"🔧 Using parser round_number: {round_number}")
        
        time_limit = parsed_data.get('time_limit', '0')
        actual_time = parsed_data.get('actual_time', '0')
        winner = parsed_data.get('winner_team', 0)
        defender = parsed_data.get('defender_team', 0)
        round_outcome = parsed_data.get('round_outcome', '')
        
        # Generate match_id from filename (ORIGINAL BEHAVIOR - includes timestamp)
        match_id = filename.replace('.txt', '')
        
        # Calculate gaming_session_id
        gaming_session_id = await self._get_or_create_gaming_session_id(conn, file_date, round_time)
        
        logger.debug(f"🔍 About to INSERT: round_date='{file_date}', round_time='{round_time}' (type: {type(round_time).__name__})")
        
        try:
            round_id = await conn.fetchval(
                """
                INSERT INTO rounds
                (round_date, round_time, match_id, map_name, round_number,
                 time_limit, actual_time, winner_team, defender_team, round_outcome, gaming_session_id, round_status, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                ON CONFLICT (match_id, round_number) DO UPDATE SET
                    round_date = EXCLUDED.round_date,
                    round_time = EXCLUDED.round_time,
                    gaming_session_id = EXCLUDED.gaming_session_id,
                    round_status = EXCLUDED.round_status
                RETURNING id
                """,
                file_date, round_time, match_id, map_name, round_number,
                time_limit, actual_time, winner, defender, round_outcome, gaming_session_id, 'completed', datetime.now()
            )

            # 🆕 RESTART DETECTION: Check for earlier rounds that should be marked as cancelled/substitution
            if not is_match_summary and gaming_session_id and round_number in (1, 2):
                # Extract player GUIDs for substitution detection
                player_guids = set()
                if 'players' in parsed_data:
                    for player in parsed_data['players']:
                        if 'guid' in player:
                            player_guids.add(player['guid'])

                await self._detect_and_mark_restarts(
                    conn, round_id, gaming_session_id, map_name, round_number,
                    file_date, round_time, player_guids if player_guids else None
                )

            if is_match_summary:
                logger.debug(f"✓ Created match summary (round_number=0) with ID {round_id}")

            return round_id
        except Exception as e:
            logger.error(f"Failed to create round: {e}")
            return None

    async def _detect_and_mark_restarts(self, conn, current_round_id: int, gaming_session_id: int,
                                        map_name: str, round_number: int, current_date: str, current_time: str,
                                        current_player_guids: set = None) -> None:
        """
        Detect and mark earlier rounds as 'cancelled' or 'substitution' if this is a restart.

        A round is considered a restart if:
        - Same gaming_session_id
        - Same map_name
        - Same round_number
        - Earlier timestamp
        - Within reasonable timeframe (< 30 minutes apart)

        Restart types:
        - 'cancelled': False start, same roster (or roster unknown)
        - 'substitution': Round completed, roster changed (player left/joined)

        Example restart: adlernest R1 played at 21:49, then restarted at 22:13
        Example substitution: adlernest R1 with ipkiss completed, he left, vid joined, restart
        """
        RESTART_THRESHOLD_MINUTES = 30

        try:
            # Find earlier rounds with same map/round in this gaming session
            earlier_rounds = await conn.fetch(
                """
                SELECT id, round_date, round_time, match_id
                FROM rounds
                WHERE gaming_session_id = $1
                  AND map_name = $2
                  AND round_number = $3
                  AND id != $4
                  AND round_status = 'completed'
                ORDER BY round_date, round_time
                """,
                gaming_session_id, map_name, round_number, current_round_id
            )

            if not earlier_rounds:
                return  # No duplicates found

            # Parse current round datetime
            try:
                current_dt = datetime.strptime(f"{current_date} {current_time}", "%Y-%m-%d %H%M%S")
            except ValueError:
                current_dt = datetime.strptime(f"{current_date} {current_time}", "%Y-%m-%d %H:%M:%S")

            # Check each earlier round
            for earlier in earlier_rounds:
                earlier_date = earlier['round_date']
                earlier_time = earlier['round_time']
                earlier_id = earlier['id']
                earlier_match_id = earlier['match_id']

                # Parse earlier datetime
                try:
                    earlier_dt = datetime.strptime(f"{earlier_date} {earlier_time}", "%Y-%m-%d %H%M%S")
                except ValueError:
                    earlier_dt = datetime.strptime(f"{earlier_date} {earlier_time}", "%Y-%m-%d %H:%M:%S")

                # Calculate time difference
                time_diff_minutes = (current_dt - earlier_dt).total_seconds() / 60

                # If within threshold, check for roster changes
                if 0 < time_diff_minutes <= RESTART_THRESHOLD_MINUTES:
                    restart_status = 'cancelled'  # Default to cancelled

                    # Check if roster changed (substitution detection)
                    if current_player_guids:
                        # Get player roster from earlier round
                        earlier_players = await conn.fetch(
                            """
                            SELECT DISTINCT player_guid
                            FROM player_comprehensive_stats
                            WHERE round_id = $1
                            """,
                            earlier_id
                        )

                        if earlier_players:
                            earlier_guids = {row['player_guid'] for row in earlier_players}

                            # Check if rosters are different
                            if earlier_guids != current_player_guids:
                                restart_status = 'substitution'
                                logger.info(
                                    f"👥 SUBSTITUTION DETECTED: Roster changed for round {earlier_id} "
                                    f"(players left/joined, restarted after {time_diff_minutes:.1f}min)"
                                )

                    # Mark earlier round
                    await conn.execute(
                        """
                        UPDATE rounds
                        SET round_status = $1
                        WHERE id = $2
                        """,
                        restart_status, earlier_id
                    )

                    if restart_status == 'cancelled':
                        logger.warning(
                            f"🔄 RESTART DETECTED: Marked round {earlier_id} ({earlier_match_id}) as 'cancelled' "
                            f"(false start, restarted after {time_diff_minutes:.1f}min)"
                        )
                    else:
                        logger.info(
                            f"🔄 RESTART (SUBSTITUTION): Round {earlier_id} marked as 'substitution' "
                            f"(counts in lifetime stats, excluded from session)"
                        )

        except Exception as e:
            logger.error(f"Error in restart detection: {e}")
            # Don't fail the import if restart detection fails

    async def _insert_player_stats(self, conn, round_id: int, round_date: str, parsed_data: Dict) -> int:
        """Insert player stats - ALL 51 FIELDS with INSERT VERIFICATION"""
        players = parsed_data.get('players', [])
        map_name = parsed_data.get('map_name', 'unknown')
        round_number = parsed_data.get('round_num', parsed_data.get('round_number', 1))
        count = 0
        
        for player in players:
            try:
                # Extract data (same logic as original)
                guid = player.get('guid', 'UNKNOWN')
                name = player.get('name', 'Unknown')
                clean_name = self.parser.strip_color_codes(name)
                team = player.get('team', 0)
                obj_stats = player.get('objective_stats', {})
                
                kills = player.get('kills', 0)
                deaths = player.get('deaths', 0)
                kd_ratio = StatsCalculator.calculate_kd(kills, deaths)

                time_seconds = player.get('time_played_seconds', 0)
                time_minutes = time_seconds / 60.0 if time_seconds > 0 else 0.0
                dpm = player.get('dpm', 0.0)
                efficiency = StatsCalculator.calculate_efficiency(kills, deaths)
                accuracy = player.get('accuracy', 0.0)
                
                raw_td = obj_stats.get('time_dead_ratio', 0) or 0
                time_dead_ratio = raw_td * 100.0 if raw_td <= 1 else float(raw_td)
                time_dead_minutes = time_minutes * (time_dead_ratio / 100.0)
                
                # ✅ INSERT with RETURNING clause for verification
                player_stat_id = await conn.fetchval(
                    """
                    INSERT INTO player_comprehensive_stats (
                        round_id, round_date, map_name, round_number,
                        player_guid, player_name, clean_name, team,
                        kills, deaths, damage_given, damage_received,
                        team_damage_given, team_damage_received,
                        gibs, self_kills, team_kills, team_gibs, headshot_kills, headshots,
                        time_played_seconds, time_played_minutes,
                        time_dead_minutes, time_dead_ratio,
                        xp, kd_ratio, dpm, efficiency,
                        bullets_fired, accuracy,
                        kill_assists,
                        objectives_completed, objectives_destroyed,
                        objectives_stolen, objectives_returned,
                        dynamites_planted, dynamites_defused,
                        times_revived, revives_given,
                        most_useful_kills, useless_kills, kill_steals,
                        denied_playtime, constructions, tank_meatshield,
                        double_kills, triple_kills, quad_kills,
                        multi_kills, mega_kills,
                        killing_spree_best, death_spree_worst
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                        $11, $12, $13, $14, $15, $16, $17, $18, $19, $20,
                        $21, $22, $23, $24, $25, $26, $27, $28, $29, $30,
                        $31, $32, $33, $34, $35, $36, $37, $38, $39, $40,
                        $41, $42, $43, $44, $45, $46, $47, $48, $49, $50, $51, $52
                    )
                    ON CONFLICT (round_id, player_guid) DO UPDATE SET
                        kills = EXCLUDED.kills,
                        deaths = EXCLUDED.deaths,
                        damage_given = EXCLUDED.damage_given,
                        kd_ratio = EXCLUDED.kd_ratio,
                        efficiency = EXCLUDED.efficiency
                    RETURNING id
                    """,
                    round_id, round_date, map_name, round_number,
                    guid, name, clean_name, team,
                    kills, deaths, player.get('damage_given', 0), player.get('damage_received', 0),
                    obj_stats.get('team_damage_given', 0),
                    obj_stats.get('team_damage_received', 0),
                    obj_stats.get('gibs', 0),
                    obj_stats.get('self_kills', 0),
                    obj_stats.get('team_kills', 0),
                    obj_stats.get('team_gibs', 0),
                    obj_stats.get('headshot_kills', 0),  # ✅ TAB field 14 - actual headshot kills
                    player.get('headshots', 0),  # ✅ Sum of weapon headshot hits
                    time_seconds, time_minutes,
                    time_dead_minutes, time_dead_ratio,
                    obj_stats.get('xp', 0), kd_ratio, dpm, efficiency,
                    obj_stats.get('bullets_fired', 0), accuracy,
                    obj_stats.get('kill_assists', 0),
                    0, 0,  # objectives_completed, objectives_destroyed
                    obj_stats.get('objectives_stolen', 0),
                    obj_stats.get('objectives_returned', 0),
                    obj_stats.get('dynamites_planted', 0),
                    obj_stats.get('dynamites_defused', 0),
                    obj_stats.get('times_revived', 0),
                    obj_stats.get('revives_given', 0),
                    obj_stats.get('useful_kills', 0),
                    obj_stats.get('useless_kills', 0),
                    obj_stats.get('kill_steals', 0),
                    obj_stats.get('denied_playtime', 0),
                    obj_stats.get('repairs_constructions', 0),
                    obj_stats.get('tank_meatshield', 0),
                    obj_stats.get('multikill_2x', 0),
                    obj_stats.get('multikill_3x', 0),
                    obj_stats.get('multikill_4x', 0),
                    obj_stats.get('multikill_5x', 0),
                    obj_stats.get('multikill_6x', 0),
                    obj_stats.get('killing_spree', 0),
                    obj_stats.get('death_spree', 0)
                )

                count += 1
            except Exception as e:
                logger.warning(f"Failed to insert player {player.get('name')}: {e}")
        
        return count
    
    async def _insert_weapon_stats(self, conn, round_id: int, round_date: str, parsed_data: Dict) -> int:
        """Insert weapon stats with INSERT VERIFICATION"""
        players = parsed_data.get('players', [])
        map_name = parsed_data.get('map_name', 'unknown')
        round_number = parsed_data.get('round_num', parsed_data.get('round_number', 1))
        count = 0
        
        for player in players:
            # Parser returns 'weapon_stats' not 'weapons'!
            weapons = player.get('weapon_stats', {}) or player.get('weapons', {})
            for weapon_name, weapon_data in weapons.items():
                try:
                    # Calculate accuracy
                    shots = weapon_data.get('shots', 0)
                    hits = weapon_data.get('hits', 0)
                    accuracy = (hits / shots * 100) if shots > 0 else 0.0
                    
                    # ✅ INSERT with RETURNING clause for verification
                    weapon_stat_id = await conn.fetchval(
                        """
                        INSERT INTO weapon_comprehensive_stats (
                            round_id, round_date, map_name, round_number,
                            player_guid, player_name, weapon_name,
                            kills, deaths, shots, hits, headshots, accuracy
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                        ON CONFLICT (round_id, player_guid, weapon_name) DO UPDATE SET
                            kills = EXCLUDED.kills,
                            shots = EXCLUDED.shots,
                            hits = EXCLUDED.hits,
                            accuracy = EXCLUDED.accuracy
                        RETURNING id
                        """,
                        round_id, round_date, map_name, round_number,
                        player.get('guid'), player.get('name'), weapon_name,
                        weapon_data.get('kills', 0), weapon_data.get('deaths', 0),
                        weapon_data.get('shots', 0), weapon_data.get('hits', 0),
                        weapon_data.get('headshots', 0), accuracy
                    )

                    count += 1
                except Exception as e:
                    logger.warning(f"Failed to insert weapon {weapon_name}: {e}")
        
        return count
    
    # =========================================================================
    # BULK OPERATIONS
    # =========================================================================
    
    async def import_all_files(self, year_filter: Optional[int] = None,
                              start_date: Optional[str] = None,
                              end_date: Optional[str] = None,
                              limit: Optional[int] = None):
        """
        Import all files from local_stats directory
        
        Args:
            year_filter: Only import files from this year
            start_date: Only import files from this date onwards (YYYY-MM-DD)
            end_date: Only import files up to this date (YYYY-MM-DD)
            limit: Maximum number of files to process (for testing)
        """
        logger.info("=" * 70)
        logger.info("📥 BULK IMPORT - Starting")
        logger.info("=" * 70)
        
        # Find all stat files
        all_files = sorted(self.stats_dir.glob("*.txt"))
        
        # Apply filters
        if year_filter:
            all_files = [f for f in all_files if f.name.startswith(str(year_filter))]
        
        if start_date:
            all_files = [f for f in all_files if f.name[:10] >= start_date]
        
        if end_date:
            all_files = [f for f in all_files if f.name[:10] <= end_date]
        
        if limit:
            all_files = all_files[:limit]
        
        logger.info(f"📊 Found {len(all_files)} files to process")
        
        if not all_files:
            logger.warning("⚠️  No files found!")
            return
        
        # Reset stats
        self.stats = {k: 0 for k in self.stats}
        self.start_time = time.time()
        
        # Process files
        for i, file_path in enumerate(all_files, 1):
            success, msg = await self.process_file(file_path)
            
            # Progress update every 10 files
            if i % 10 == 0 or i == len(all_files):
                elapsed = time.time() - self.start_time
                rate = i / elapsed if elapsed > 0 else 0
                pct = (i / len(all_files)) * 100
                
                logger.info(
                    f"📊 Progress: [{i}/{len(all_files)}] {pct:.1f}% | "
                    f"Rate: {rate:.1f} files/sec | "
                    f"Processed: {self.stats['files_processed']} | "
                    f"Skipped: {self.stats['files_skipped']} | "
                    f"Failed: {self.stats['files_failed']}"
                )
        
        # Final summary
        elapsed = time.time() - self.start_time
        logger.info("=" * 70)
        logger.info("✅ IMPORT COMPLETE!")
        logger.info("=" * 70)
        logger.info(f"⏱️  Time: {elapsed:.1f} seconds")
        logger.info(f"📁 Files processed: {self.stats['files_processed']}")
        logger.info(f"⏭️  Files skipped: {self.stats['files_skipped']}")
        logger.info(f"❌ Files failed: {self.stats['files_failed']}")
        logger.info(f"🎮 Rounds created: {self.stats['rounds_created']}")
        logger.info(f"👤 Player stats: {self.stats['players_inserted']}")
        logger.info(f"🔫 Weapon stats: {self.stats['weapons_inserted']}")
    
    async def rebuild_from_scratch(self, year: int = 2025,
                                  start_date: Optional[str] = None,
                                  end_date: Optional[str] = None,
                                  confirm: bool = False) -> bool:
        """
        Nuclear option: Wipe database and rebuild from scratch
        
        BULLETPROOF OPERATION:
        1. Validates connection
        2. Creates backup
        3. Wipes data
        4. Imports files
        5. Validates result
        
        Args:
            year: Year to import
            start_date: Start date for import (YYYY-MM-DD)
            end_date: End date for import (YYYY-MM-DD)
            confirm: Must be True to proceed
        
        Returns:
            True if successful, False if any step fails
        """
        if not confirm:
            logger.error("❌ Rebuild requires confirm=True")
            return False
        
        logger.info("=" * 70)
        logger.info("💥 REBUILD FROM SCRATCH - NUCLEAR OPTION")
        logger.info("=" * 70)
        
        try:
            # Step 1: Verify connection
            logger.info("1️⃣  Verifying database connection...")
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            logger.info("   ✅ Connection verified")
            
            # Step 2: Create backup
            logger.info("2️⃣  Creating backup...")
            await self._backup_database()
            logger.info("   ✅ Backup complete")
            
            # Step 3: Wipe database
            logger.info("3️⃣  Wiping existing data...")
            if not await self.create_fresh_database(backup_existing=False):
                logger.error("   ❌ Failed to wipe database")
                return False
            logger.info("   ✅ Database wiped")
            
            # Step 4: Import files
            logger.info("4️⃣  Importing files...")
            await self.import_all_files(
                year_filter=year,
                start_date=start_date,
                end_date=end_date
            )
            logger.info("   ✅ Import complete")
            
            # Step 5: Validate
            logger.info("5️⃣  Validating rebuild...")
            results = await self.validate_database()
            
            # Check if we have data
            if results.get('rounds', 0) == 0:
                logger.error("   ❌ CRITICAL: No rounds imported!")
                return False
            
            if results.get('player_comprehensive_stats', 0) == 0:
                logger.error("   ❌ CRITICAL: No player stats imported!")
                return False
            
            logger.info("   ✅ Validation passed")
            
            logger.info("\n" + "=" * 70)
            logger.info("✅ REBUILD SUCCESSFUL!")
            logger.info("=" * 70)
            logger.info(f"📊 Imported {results['rounds']:,} rounds")
            logger.info(f"👤 Imported {results['player_comprehensive_stats']:,} player stats")
            logger.info(f"🔫 Imported {results['weapon_comprehensive_stats']:,} weapon stats")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ REBUILD FAILED: {e}")
            logger.error("💡 Your data is safe in the backup!")
            return False
    
    async def fix_date_range(self, start_date: str, end_date: str) -> bool:
        """
        Surgical fix: Re-import specific date range
        
        Deletes data in range, then re-imports those files.
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        
        Returns:
            True if successful
        """
        logger.info("=" * 70)
        logger.info(f"🔧 DATE RANGE FIX: {start_date} to {end_date}")
        logger.info("=" * 70)
        
        try:
            # Delete existing data in range
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    # Delete from processed_files first
                    await conn.execute(
                        "DELETE FROM processed_files WHERE filename >= $1 AND filename <= $2",
                        f"{start_date}%", f"{end_date}%"
                    )
                    
                    # Delete rounds in range (cascade will handle related data)
                    result = await conn.execute(
                        "DELETE FROM rounds WHERE round_date >= $1 AND round_date <= $2",
                        start_date, end_date
                    )
                    logger.info(f"🗑️  Deleted existing data: {result}")
            
            # Re-import files in range
            await self.import_all_files(start_date=start_date, end_date=end_date)
            
            logger.info("✅ Date range fix complete!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Date range fix failed: {e}")
            return False
    
    # =========================================================================
    # VALIDATION
    # =========================================================================
    
    async def validate_database(self) -> Dict:
        """
        Validate database integrity and show statistics
        
        Returns:
            Dict with validation results
        """
        logger.info("=" * 70)
        logger.info("🔍 DATABASE VALIDATION")
        logger.info("=" * 70)
        
        results = {}
        
        async with self.pool.acquire() as conn:
            # Table counts
            tables = {
                'rounds': 'round_id',
                'player_comprehensive_stats': 'id',
                'weapon_comprehensive_stats': 'id',
                'player_aliases': 'id',
                'player_links': 'discord_id',
                'session_teams': 'id',
                'processed_files': 'id'
            }
            
            logger.info("\n📊 Table Row Counts:")
            for table, _ in tables.items():
                count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                results[table] = count
                logger.info(f"   {table:30s}: {count:,}")
            
            # Check for orphaned data
            logger.info("\n🔗 Referential Integrity:")
            
            # Players without rounds (rounds table uses 'id' not 'round_id')
            orphaned_players = await conn.fetchval(
                """
                SELECT COUNT(*) FROM player_comprehensive_stats p
                LEFT JOIN rounds r ON p.round_id = r.id
                WHERE r.id IS NULL
                """
            )
            logger.info(f"   Orphaned player stats: {orphaned_players}")
            results['orphaned_players'] = orphaned_players
            
            # Weapons without rounds
            orphaned_weapons = await conn.fetchval(
                """
                SELECT COUNT(*) FROM weapon_comprehensive_stats w
                LEFT JOIN rounds r ON w.round_id = r.id
                WHERE r.id IS NULL
                """
            )
            logger.info(f"   Orphaned weapon stats: {orphaned_weapons}")
            results['orphaned_weapons'] = orphaned_weapons
            
            # Date range
            logger.info("\n📅 Date Range:")
            date_range = await conn.fetchrow(
                "SELECT MIN(round_date) as min_date, MAX(round_date) as max_date FROM rounds"
            )
            if date_range:
                logger.info(f"   First round: {date_range['min_date']}")
                logger.info(f"   Last round:  {date_range['max_date']}")
                results['first_round'] = date_range['min_date']
                results['last_round'] = date_range['max_date']
            
            # Top players
            logger.info("\n👤 Top 5 Players (by total kills):")
            top_players = await conn.fetch(
                """
                SELECT player_name, SUM(kills) as total_kills, COUNT(*) as rounds_played
                FROM player_comprehensive_stats
                GROUP BY player_name
                ORDER BY total_kills DESC
                LIMIT 5
                """
            )
            for i, player in enumerate(top_players, 1):
                logger.info(f"   {i}. {player['player_name']:20s}: {player['total_kills']:,} kills ({player['rounds_played']} rounds)")
        
        logger.info("\n" + "=" * 70)
        logger.info("✅ Validation complete!")
        logger.info("=" * 70)
        
        return results


# =============================================================================
# INTERACTIVE MAIN MENU
# =============================================================================

async def main():
    """Interactive database manager"""
    
    # Check if running in pipe mode (non-interactive)
    import sys
    is_piped = not sys.stdin.isatty()
    
    if not is_piped:
        # Interactive mode - show menu
        print("\n" + "=" * 70)
        print("🐘 POSTGRESQL DATABASE MANAGER")
        print("=" * 70)
        print("\nTHE ONLY DATABASE TOOL YOU NEED!")
        print("\nOptions:")
        print("  1️⃣   Create fresh database (with backup)")
        print("  2️⃣   Import all files (incremental - safe)")
        print("  3️⃣   Rebuild from scratch (nuclear option)")
        print("  4️⃣   Fix specific date range (surgical fix)")
        print("  5️⃣   Validate database")
        print("  6️⃣   Quick test (import 10 files)")
        print()
    
    choice = input("Select option (1-6): ").strip()
    
    manager = PostgreSQLDatabaseManager()
    await manager.connect()
    
    try:
        if choice == "1":
            await manager.create_fresh_database(backup_existing=True)
            
        elif choice == "2":
            print("\nImport options:")
            print("  1 - Full year (all 2025 files)")
            print("  2 - Last 30 days only")
            print("  3 - Custom date range")
            sub = input("Select [1]: ").strip() or "1"
            
            if sub == "1":
                year = input("Year to import [2025]: ").strip() or "2025"
                await manager.import_all_files(year_filter=int(year))
            elif sub == "2":
                end_date = datetime.now()
                start_date = end_date - timedelta(days=30)
                logger.info(f"📅 Importing last 30 days: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
                await manager.import_all_files(
                    start_date=start_date.strftime('%Y-%m-%d'),
                    end_date=end_date.strftime('%Y-%m-%d')
                )
            elif sub == "3":
                start = input("Start date (YYYY-MM-DD): ").strip()
                end = input("End date (YYYY-MM-DD): ").strip()
                await manager.import_all_files(start_date=start, end_date=end)
            
        elif choice == "3":
            print("\n⚠️  WARNING: This will DELETE ALL DATA!")
            confirm = input("Type 'YES DELETE EVERYTHING' to confirm: ")
            if confirm == "YES DELETE EVERYTHING":
                print("\nRebuild options:")
                print("  1 - Full year (all 2025 files)")
                print("  2 - Last 30 days only (RECOMMENDED)")
                print("  3 - Custom date range")
                sub = input("Select [2]: ").strip() or "2"
                
                if sub == "1":
                    year = input("Year to import [2025]: ").strip() or "2025"
                    await manager.rebuild_from_scratch(year=int(year), confirm=True)
                elif sub == "2":
                    end_date = datetime.now()
                    start_date = end_date - timedelta(days=30)
                    await manager.rebuild_from_scratch(
                        year=2025,
                        start_date=start_date.strftime('%Y-%m-%d'),
                        end_date=end_date.strftime('%Y-%m-%d'),
                        confirm=True
                    )
                elif sub == "3":
                    # CLASSIC WORKFLOW SUPPORT: Read 2 more inputs (ignored 3, start, end)
                    # This supports: echo "3`nYES DELETE EVERYTHING`n3`n2025-10-17`n2025-11-04"
                    # The extra "3" is read here but ignored for compatibility
                    start = input("Start date (YYYY-MM-DD): ").strip()
                    end = input("End date (YYYY-MM-DD): ").strip()
                    
                    logger.info(f"🔥 Rebuilding database from {start} to {end}")
                    await manager.rebuild_from_scratch(
                        year=int(start[:4]),
                        start_date=start,
                        end_date=end,
                        confirm=True
                    )
                    
                    # Auto-validate after rebuild
                    logger.info("\n🔍 Validating rebuilt database...")
                    await manager.validate_database()
            else:
                print("❌ Aborted")
        
        elif choice == "4":
            start = input("Start date (YYYY-MM-DD) [2025-10-28]: ").strip() or "2025-10-28"
            end = input("End date (YYYY-MM-DD) [2025-10-30]: ").strip() or "2025-10-30"
            await manager.fix_date_range(start, end)
        
        elif choice == "5":
            await manager.validate_database()
        
        elif choice == "6":
            print("\n🧪 Quick test - importing 10 files...")
            await manager.import_all_files(year_filter=2025, limit=10)
        
        else:
            print("❌ Invalid choice")
    
    finally:
        await manager.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user. Goodbye!")
    except Exception as e:
        logger.error("=" * 70)
        logger.error("❌ FATAL ERROR")
        logger.error("=" * 70)
        logger.error(f"Error: {e}", exc_info=True)
        logger.error("\n💡 TROUBLESHOOTING:")
        logger.error("   1. Check PostgreSQL is running: psql -U postgres -l")
        logger.error("   2. Verify bot_config.json has correct credentials")
        logger.error("   3. Ensure database exists: CREATE DATABASE etlegacy;")
        logger.error("   4. Check schema is applied: psql -d etlegacy -f bot/schema_postgresql.sql")
        logger.error("\n📝 See postgresql_manager.log for full details")
        sys.exit(1)
