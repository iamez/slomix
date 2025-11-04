#!/usr/bin/env python3
"""
🏗️ ET:Legacy Database Manager - THE ONLY TOOL YOU NEED
================================================================================

This is THE SINGLE SOURCE OF TRUTH for database operations.
Consolidates all scattered import/rebuild/reimport tools into ONE.

NEVER CREATE ANOTHER IMPORT SCRIPT AGAIN!

This tool handles:
  ✅ Fresh database creation
  ✅ Schema setup with all fixes applied
  ✅ Bulk import (with duplicate prevention)
  ✅ Incremental updates
  ✅ Disaster recovery (rebuild from scratch)
  ✅ Date range fixes
  ✅ Validation and verification

Author: Your ET:Legacy Stats System
Date: November 3, 2025
Version: 1.0 - Production Ready
"""

import sqlite3
import logging
import time
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from bot.community_stats_parser import C0RNP0RN3StatsParser

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('database_manager.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('DatabaseManager')


class DatabaseManager:
    """
    The ONE and ONLY database management tool
    
    Handles all database operations from creation to disaster recovery.
    """
    
    def __init__(self, db_path: Optional[str] = None, stats_dir: str = "local_stats"):
        # Always create database in bot/ directory to avoid path issues
        if db_path is None:
            script_dir = Path(__file__).parent
            db_path = str(script_dir / "bot" / "etlegacy_production.db")
        self.db_path = db_path
        self.stats_dir = Path(stats_dir)
        self.parser = C0RNP0RN3StatsParser()
        
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
        
        # Auto-create database/schema if needed
        self._ensure_database_exists()
    
    # =========================================================================
    # AUTO-DETECTION AND CREATION
    # =========================================================================
    
    def _ensure_database_exists(self):
        """
        Auto-detect if database/tables exist, create if needed
        
        This runs automatically on init, so you never have to worry
        about missing databases or tables.
        """
        db_path = Path(self.db_path)
        
        # Check if database file exists
        if not db_path.exists():
            logger.info("🔍 Database not found - creating fresh database...")
            self.create_fresh_database(backup_existing=False)
            return
        
        # Check if tables exist
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check for sessions table (if this exists, assume all tables exist)
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='rounds'")
            if cursor.fetchone() is None:
                logger.info("🔍 Database exists but tables missing - creating schema...")
                conn.close()
                self.create_fresh_database(backup_existing=True)
                return
            
            conn.close()
            logger.debug("✅ Database and tables exist")
            
        except sqlite3.Error as e:
            logger.warning(f"⚠️  Database check failed: {e}")
            logger.info("🔧 Creating fresh database...")
            self.create_fresh_database(backup_existing=True)
    
    # =========================================================================
    # SCHEMA CREATION (With ALL fixes applied)
    # =========================================================================
    
    def create_fresh_database(self, backup_existing: bool = True) -> bool:
        """
        Create a fresh database with correct schema
        
        This includes ALL fixes discovered during development:
        - 51 fields in player_comprehensive_stats
        - UNIQUE constraints for duplicate prevention
        - Proper indexes for performance
        - All required tables
        
        Args:
            backup_existing: If True and DB exists, creates backup first
        
        Returns:
            True if successful
        """
        logger.info("=" * 70)
        logger.info("🏗️  DATABASE CREATION - Starting")
        logger.info("=" * 70)
        
        db_path = Path(self.db_path)
        
        # Ensure bot directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Backup existing database if requested
        if backup_existing and db_path.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = db_path.parent / f"{db_path.stem}_backup_{timestamp}.db"
            
            logger.info(f"📦 Backing up existing database...")
            logger.info(f"   Source: {db_path}")
            logger.info(f"   Backup: {backup_path}")
            
            import shutil
            shutil.copy2(db_path, backup_path)
            logger.info("   ✅ Backup complete!")
            
            # Delete old database
            db_path.unlink()
            logger.info("   🗑️  Deleted old database")
        
        logger.info(f"\n🔨 Creating fresh database: {db_path}")
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 1. rounds table (with gaming_session_id for Phase 1 grouping)
            logger.info("   Creating rounds table...")
            cursor.execute('''
                CREATE TABLE rounds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    round_date TEXT NOT NULL,
                    round_time TEXT NOT NULL,
                    match_id TEXT NOT NULL,
                    map_name TEXT NOT NULL,
                    round_number INTEGER NOT NULL,
                    time_limit TEXT,
                    actual_time TEXT,
                    winner_team INTEGER DEFAULT 0,
                    defender_team INTEGER DEFAULT 0,
                    is_tied BOOLEAN DEFAULT FALSE,
                    round_outcome TEXT,
                    gaming_session_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(match_id, round_number)
                )
            ''')
            
            # 2. Player comprehensive stats (53 columns + ALL FIXES)
            logger.info("   Creating player_comprehensive_stats table...")
            cursor.execute('''
                CREATE TABLE player_comprehensive_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    round_id INTEGER NOT NULL,
                    round_date TEXT NOT NULL,
                    map_name TEXT NOT NULL,
                    round_number INTEGER NOT NULL,
                    player_guid TEXT NOT NULL,
                    player_name TEXT NOT NULL,
                    clean_name TEXT,
                    team INTEGER DEFAULT 0,
                    
                    -- Core combat stats
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
                    
                    -- Time tracking
                    time_played_seconds INTEGER DEFAULT 0,
                    time_played_minutes REAL DEFAULT 0,
                    time_dead_minutes REAL DEFAULT 0,
                    time_dead_ratio REAL DEFAULT 0,
                    
                    -- Performance metrics
                    xp INTEGER DEFAULT 0,
                    kd_ratio REAL DEFAULT 0,
                    dpm REAL DEFAULT 0,
                    efficiency REAL DEFAULT 0,
                    
                    -- Weapon stats
                    bullets_fired INTEGER DEFAULT 0,
                    accuracy REAL DEFAULT 0,
                    
                    -- Objective stats
                    kill_assists INTEGER DEFAULT 0,
                    objectives_completed INTEGER DEFAULT 0,
                    objectives_destroyed INTEGER DEFAULT 0,
                    objectives_stolen INTEGER DEFAULT 0,
                    objectives_returned INTEGER DEFAULT 0,
                    dynamites_planted INTEGER DEFAULT 0,
                    dynamites_defused INTEGER DEFAULT 0,
                    times_revived INTEGER DEFAULT 0,
                    revives_given INTEGER DEFAULT 0,
                    
                    -- Advanced objective stats
                    most_useful_kills INTEGER DEFAULT 0,
                    useless_kills INTEGER DEFAULT 0,
                    kill_steals INTEGER DEFAULT 0,
                    denied_playtime INTEGER DEFAULT 0,
                    constructions INTEGER DEFAULT 0,
                    tank_meatshield REAL DEFAULT 0,
                    
                    -- Multikills
                    double_kills INTEGER DEFAULT 0,
                    triple_kills INTEGER DEFAULT 0,
                    quad_kills INTEGER DEFAULT 0,
                    multi_kills INTEGER DEFAULT 0,
                    mega_kills INTEGER DEFAULT 0,
                    
                    -- Sprees
                    killing_spree_best INTEGER DEFAULT 0,
                    death_spree_worst INTEGER DEFAULT 0,
                    
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (round_id) REFERENCES rounds(id),
                    
                    -- ✅ DUPLICATE PREVENTION
                    UNIQUE(round_id, player_guid)
                )
            ''')
            
            # 3. Weapon comprehensive stats
            logger.info("   Creating weapon_comprehensive_stats table...")
            cursor.execute('''
                CREATE TABLE weapon_comprehensive_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                    
                    -- ✅ DUPLICATE PREVENTION
                    UNIQUE(round_id, player_guid, weapon_name)
                )
            ''')
            
            # 4. Player links (Discord ↔ GUID)
            logger.info("   Creating player_links table...")
            cursor.execute('''
                CREATE TABLE player_links (
                    discord_id BIGINT PRIMARY KEY,
                    discord_username TEXT NOT NULL,
                    et_guid TEXT UNIQUE NOT NULL,
                    et_name TEXT,
                    linked_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    verified BOOLEAN DEFAULT FALSE
                )
            ''')
            
            # 5. Processed files tracking
            logger.info("   Creating processed_files table...")
            cursor.execute('''
                CREATE TABLE processed_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT UNIQUE NOT NULL,
                    file_hash TEXT,
                    success BOOLEAN DEFAULT 1,
                    error_message TEXT,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 6. Session teams
            logger.info("   Creating round_teams table...")
            cursor.execute('''
                CREATE TABLE session_teams (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_start_date TEXT NOT NULL,
                    map_name TEXT NOT NULL,
                    team_name TEXT NOT NULL,
                    player_guids TEXT NOT NULL,
                    player_names TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(session_start_date, map_name, team_name)
                )
            ''')
            
            # 7. Player aliases
            logger.info("   Creating player_aliases table...")
            cursor.execute('''
                CREATE TABLE player_aliases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guid TEXT NOT NULL,
                    alias TEXT NOT NULL,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    times_seen INTEGER DEFAULT 1,
                    UNIQUE(guid, alias)
                )
            ''')
            
            # Create indexes for performance
            logger.info("   Creating indexes...")
            cursor.execute('CREATE INDEX idx_rounds_date_map ON rounds(round_date, map_name)')
            cursor.execute('CREATE INDEX idx_rounds_match_id ON rounds(match_id)')
            cursor.execute('CREATE INDEX idx_player_stats_round ON player_comprehensive_stats(round_id)')
            cursor.execute('CREATE INDEX idx_player_stats_guid ON player_comprehensive_stats(player_guid)')
            cursor.execute('CREATE INDEX idx_weapon_stats_round ON weapon_comprehensive_stats(round_id)')
            cursor.execute('CREATE INDEX idx_weapon_stats_guid ON weapon_comprehensive_stats(player_guid)')
            cursor.execute('CREATE INDEX idx_aliases_guid ON player_aliases(guid)')
            
            conn.commit()
            conn.close()
            
            logger.info("\n🎉 Database created successfully!")
            logger.info("   ✅ 7 tables created")
            logger.info("   ✅ 6 indexes created")
            logger.info("   ✅ UNIQUE constraints applied")
            logger.info("   ✅ All fixes included (51 fields, transactions, etc.)")
            logger.info("   ✅ Ready for import!")
            
            return True
            
        except sqlite3.Error as e:
            logger.error(f"❌ Failed to create database: {e}")
            return False
    
    # =========================================================================
    # DATA IMPORT (With transaction safety and duplicate prevention)
    # =========================================================================
    
    def _find_or_create_match_id(self, file_date: str, round_time: str, 
                                  map_name: str, round_num: int, file_path: Path) -> str:
        """
        Find or create match_id to pair Round 1 and Round 2 together
        
        Strategy:
        - Round 1: Create new match_id = date_time_map
        - Round 2: Find closest Round 1 file (same date, same map, before R2)
        
        This ensures R1 and R2 from the SAME MATCH are linked together!
        """
        if round_num == 1:
            # Round 1: Create new match_id
            match_id = f"{file_date}_{round_time}_{map_name}"
            return match_id
        
        else:
            # Round 2: Find matching Round 1 file
            # Look for R1 files on same date, same map, BEFORE this R2 file
            r1_pattern = f"{file_date}-*-{map_name}-round-1.txt"
            r1_files = list(self.stats_dir.glob(r1_pattern))
            same_day_count = len(r1_files)
            
            # ✅ FIX: ALWAYS check PREVIOUS day for midnight-crossing matches
            # (Don't just check if no same-day files - we need to check both!)
            from datetime import datetime, timedelta
            prev_day_r1_files = []
            try:
                current_date = datetime.strptime(file_date, "%Y-%m-%d")
                prev_date = current_date - timedelta(days=1)
                prev_date_str = prev_date.strftime("%Y-%m-%d")
                r1_pattern_prev = f"{prev_date_str}-*-{map_name}-round-1.txt"
                prev_day_r1_files = list(self.stats_dir.glob(r1_pattern_prev))
                if prev_day_r1_files:
                    r1_files.extend(prev_day_r1_files)
                    logger.debug(f"🌙 Checking previous day for R1: {prev_date_str} ({len(prev_day_r1_files)} files)")
            except ValueError:
                pass  # Invalid date format, skip previous date search
            
            if not r1_files:
                # No R1 file found on same day or previous day - create orphan match_id
                logger.warning(f"⚠️  No Round 1 file found for {file_path.name} (checked today and yesterday)")
                match_id = f"{file_date}_{round_time}_{map_name}_orphan"
                return match_id
            
            # Find R1 file closest in time BEFORE this R2
            # Use full datetime comparison to handle midnight crossings
            from datetime import datetime
            try:
                r2_datetime = datetime.strptime(f"{file_date} {round_time}", "%Y-%m-%d %H%M%S")
            except ValueError:
                # Fallback to orphan if date parsing fails
                logger.warning(f"⚠️  Invalid datetime for R2: {file_path.name}")
                match_id = f"{file_date}_{round_time}_{map_name}_orphan"
                return match_id
            
            closest_r1 = None
            closest_time_diff = float('inf')
            closest_r1_time = None
            
            for r1_file in r1_files:
                r1_parts = r1_file.name.split('-')
                if len(r1_parts) < 4:
                    continue
                r1_date = '-'.join(r1_parts[:3])
                r1_time_str = r1_parts[3]
                
                try:
                    r1_datetime = datetime.strptime(f"{r1_date} {r1_time_str}", "%Y-%m-%d %H%M%S")
                    # R1 must be BEFORE R2
                    if r1_datetime < r2_datetime:
                        time_diff = (r2_datetime - r1_datetime).total_seconds()
                        if time_diff < closest_time_diff:
                            closest_time_diff = time_diff
                            closest_r1 = r1_file
                            closest_r1_time = r1_time_str
                except ValueError:
                    continue
            
            if closest_r1:
                # Found matching R1 - use its match_id
                # Extract the date from the R1 file (not the R2 date!)
                r1_parts = closest_r1.name.split('-')
                r1_date_str = '-'.join(r1_parts[0:3])
                match_id = f"{r1_date_str}_{closest_r1_time}_{map_name}"
                
                # Check if this is a midnight-crossing match
                is_midnight_crossing = (r1_date_str != file_date)
                if is_midnight_crossing:
                    logger.info(f"🌙 Midnight-crossing match: R1 {closest_r1.name} -> R2 {file_path.name} ({closest_time_diff:.0f}s)")
                else:
                    logger.debug(f"✅ Paired R2 {round_time} with R1 {closest_r1_time} (diff: {closest_time_diff:.0f}s)")
                return match_id
            else:
                # All R1 files are AFTER R2 (weird case)
                logger.warning(f"⚠️  All R1 files are after R2 for {file_path.name}")
                match_id = f"{file_date}_{round_time}_{map_name}_orphan"
                return match_id
    
    def is_file_processed(self, filename: str) -> bool:
        """Check if file has already been processed"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM processed_files WHERE filename = ? AND success = 1",
                (filename,)
            )
            result = cursor.fetchone()
            conn.close()
            return result is not None
        except sqlite3.Error:
            return False
    
    def mark_file_processed(self, filename: str, success: bool = True):
        """Mark file as processed in database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO processed_files (filename, success)
                VALUES (?, ?)
            ''', (filename, 1 if success else 0))
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            logger.warning(f"Error marking file as processed: {e}")
    
    def _get_or_create_gaming_session_id(self, cursor, file_date: str, round_time: str) -> Optional[int]:
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
            cursor.execute('''
                SELECT gaming_session_id, round_date, round_time
                FROM rounds
                WHERE gaming_session_id IS NOT NULL
                ORDER BY round_date DESC, round_time DESC
                LIMIT 1
            ''')
            
            last_round = cursor.fetchone()
            
            if not last_round:
                # First round ever - start with gaming_session_id = 1
                return 1
            
            last_gaming_session_id, last_date, last_time = last_round
            
            # Parse datetimes
            current_datetime = datetime.strptime(f"{file_date} {round_time}", "%Y-%m-%d %H%M%S")
            last_datetime = datetime.strptime(f"{last_date} {last_time}", "%Y-%m-%d %H%M%S")
            
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
    
    def create_round(self, parsed_data: Dict, file_date: str, round_time: str, match_id: str) -> Optional[int]:
        """Create new round (with transaction safety and duplicate handling)"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()
            
            map_name = parsed_data.get('map_name', 'Unknown')
            round_num = parsed_data.get('round_num', 1)
            time_limit = parsed_data.get('map_time', '0:00')
            actual_time = parsed_data.get('actual_time', '0:00')
            winner_team = parsed_data.get('winner_team', 0)
            
            # Determine round outcome based on winner_team
            # 0 = Tie, 1 = Axis won, 2 = Allies won
            if winner_team == 0:
                round_outcome = "Tie"
                is_tied = True
            elif winner_team == 1:
                round_outcome = "Axis Victory"
                is_tied = False
            elif winner_team == 2:
                round_outcome = "Allies Victory"
                is_tied = False
            else:
                round_outcome = None
                is_tied = False
            
            # Defender team is opposite of round number (R1 = Axis defend, R2 = Allies defend)
            defender_team = 1 if round_num == 1 else 2
            
            # ✅ Check if session already exists
            cursor.execute('''
                SELECT id FROM rounds 
                WHERE match_id = ? AND round_number = ?
            ''', (match_id, round_num))
            
            existing = cursor.fetchone()
            if existing:
                # Round already exists - return existing ID
                logger.debug(f"Round already exists: {match_id} R{round_num} (ID: {existing[0]})")
                return existing[0]
            
            # Calculate gaming_session_id for this round
            gaming_session_id = self._get_or_create_gaming_session_id(cursor, file_date, round_time)
            
            # Create new round
            conn.execute('BEGIN TRANSACTION')  # ✅ Transaction safety
            cursor.execute('''
                INSERT INTO rounds (
                    round_date, round_time, match_id, map_name, round_number,
                    time_limit, actual_time, winner_team, defender_team, is_tied,
                    round_outcome, gaming_session_id, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (file_date, round_time, match_id, map_name, round_num, time_limit, actual_time, 
                  winner_team, defender_team, is_tied, round_outcome, gaming_session_id))
            
            round_id = cursor.lastrowid
            conn.commit()  # ✅ Commit transaction
            self.stats['rounds_created'] += 1
            
            return round_id
            
        except sqlite3.Error as e:
            if conn:
                conn.rollback()  # ✅ Rollback on error
            logger.error(f"Error creating session: {e}")
            return None
        finally:
            if conn:
                conn.close()
    
    def insert_player_stats(self, round_id: int, round_date: str, 
                           map_name: str, round_num: int, player: Dict) -> bool:
        """Insert player stats (with transaction safety)"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.execute('BEGIN TRANSACTION')  # ✅ Transaction safety
            cursor = conn.cursor()
            
            # Extract data
            guid = player.get('guid', 'UNKNOWN')
            name = player.get('name', 'Unknown')
            clean_name = self.parser.strip_color_codes(name)
            team = player.get('team', 0)
            obj_stats = player.get('objective_stats', {})
            
            kills = player.get('kills', 0)
            deaths = player.get('deaths', 0)
            kd_ratio = kills / deaths if deaths > 0 else float(kills)
            
            time_seconds = player.get('time_played_seconds', 0)
            time_minutes = time_seconds / 60.0 if time_seconds > 0 else 0.0
            dpm = player.get('dpm', 0.0)
            efficiency = (kills / (kills + deaths) * 100) if (kills + deaths) > 0 else 0.0
            accuracy = player.get('accuracy', 0.0)
            
            raw_td = obj_stats.get('time_dead_ratio', 0) or 0
            time_dead_ratio = raw_td * 100.0 if raw_td <= 1 else float(raw_td)
            time_dead_minutes = time_minutes * (time_dead_ratio / 100.0)
            
            # ✅ INSERT ALL 51 VALUES with correct field mappings
            cursor.execute('''
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
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                round_id, round_date, map_name, round_num,
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
                obj_stats.get('death_spree', 0),
            ))
            
            conn.commit()  # ✅ Commit transaction
            self.stats['players_inserted'] += 1
            return True
            
        except sqlite3.Error as e:
            if conn:
                conn.rollback()  # ✅ Rollback on error
            logger.error(f"Error inserting player: {e}")
            return False
        finally:
            if conn:
                conn.close()
    
    def insert_weapon_stats(self, round_id: int, round_date: str,
                           map_name: str, round_num: int, player: Dict) -> bool:
        """Insert weapon stats (with transaction safety)"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.execute('BEGIN TRANSACTION')  # ✅ Transaction safety
            cursor = conn.cursor()
            
            guid = player.get('guid', 'UNKNOWN')
            name = player.get('name', 'Unknown')
            weapon_stats = player.get('weapon_stats', {})
            
            for weapon_name, stats in weapon_stats.items():
                if stats.get('shots', 0) > 0 or stats.get('kills', 0) > 0:
                    cursor.execute('''
                        INSERT INTO weapon_comprehensive_stats (
                            round_id, round_date, map_name, round_number,
                            player_guid, player_name, weapon_name,
                            kills, deaths, headshots, hits, shots, accuracy
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        round_id, round_date, map_name, round_num,
                        guid, name, weapon_name,
                        stats.get('kills', 0), stats.get('deaths', 0), stats.get('headshots', 0),
                        stats.get('hits', 0), stats.get('shots', 0), stats.get('accuracy', 0.0)
                    ))
                    self.stats['weapons_inserted'] += 1
            
            conn.commit()  # ✅ Commit transaction
            return True
            
        except sqlite3.Error as e:
            if conn:
                conn.rollback()  # ✅ Rollback on error
            logger.error(f"Error inserting weapons: {e}")
            return False
        finally:
            if conn:
                conn.close()
    
    def process_file(self, file_path: Path) -> Tuple[bool, str]:
        """Process a single stats file"""
        filename = file_path.name
        
        try:
            # ✅ DUPLICATE PREVENTION: Check if already processed
            if self.is_file_processed(filename):
                self.stats['files_skipped'] += 1
                return True, "Already processed"
            
            # ✅ Validate filename format first
            parts = filename.split('-')
            if len(parts) < 4:
                error_msg = f"Invalid filename format: {filename} (expected: YYYY-MM-DD-HHMMSS-...)"
                logger.warning(f"⚠️  {error_msg}")
                self.mark_file_processed(filename, success=False)
                self.stats['files_failed'] += 1
                return False, error_msg
            
            # Parse file
            parsed = self.parser.parse_stats_file(str(file_path))
            
            if not parsed.get('success', False):
                error_msg = parsed.get('error', 'Unknown parse error')
                self.mark_file_processed(filename, success=False)
                self.stats['files_failed'] += 1
                return False, f"Parse error: {error_msg}"
            
            # Extract date and time from filename: 2025-09-09-225817-map-round-1.txt
            file_date = '-'.join(parts[:3])  # 2025-09-09
            round_time = parts[3]  # 225817
            
            # Generate match_id by finding R1 file for this match
            map_name = parsed.get('map_name', 'Unknown')
            round_num = parsed.get('round_num', 1)
            match_id = self._find_or_create_match_id(file_date, round_time, map_name, round_num, file_path)
            
            # Create round
            round_id = self.create_round(parsed, file_date, round_time, match_id)
            if not round_id:
                self.stats['files_failed'] += 1
                return False, "Round creation failed"
            
            # Insert players and weapons
            players = parsed.get('players', [])
            map_name = parsed.get('map_name', 'Unknown')
            round_num = parsed.get('round_num', 1)
            
            for player in players:
                if self.insert_player_stats(round_id, file_date, map_name, round_num, player):
                    self.insert_weapon_stats(round_id, file_date, map_name, round_num, player)
            
            # Mark as processed
            self.mark_file_processed(filename, success=True)
            self.stats['files_processed'] += 1
            
            return True, f"Imported {len(players)} players"
            
        except Exception as e:
            logger.error(f"Exception processing {filename}: {e}")
            self.stats['files_failed'] += 1
            return False, str(e)
    
    # =========================================================================
    # BULK OPERATIONS
    # =========================================================================
    
    def import_all_files(self, year_filter: Optional[int] = None, 
                        limit: Optional[int] = None) -> bool:
        """
        Import all stats files with progress tracking
        
        Args:
            year_filter: Only import files from this year (e.g., 2025)
            limit: Only import first N files (for testing)
        
        Returns:
            True if successful
        """
        logger.info("=" * 70)
        logger.info("📥 BULK IMPORT - Starting")
        logger.info("=" * 70)
        
        # Get all files
        all_files = sorted(self.stats_dir.glob("*.txt"))
        
        # Apply filters
        if year_filter:
            all_files = [f for f in all_files if f.name.startswith(str(year_filter))]
            logger.info(f"   Year filter: {year_filter}")
        
        if limit:
            all_files = all_files[:limit]
            logger.info(f"   Limit: {limit} files")
        
        total_files = len(all_files)
        logger.info(f"   Total files to process: {total_files:,}")
        
        if total_files == 0:
            logger.warning("⚠️  No files found to import!")
            return False
        
        # Start import
        self.start_time = time.time()
        logger.info("\n🔄 Processing files...")
        
        for i, file_path in enumerate(all_files, 1):
            success, msg = self.process_file(file_path)
            
            # Show progress every 10 files or every 5 seconds
            if i % 10 == 0 or (time.time() - (self.last_progress_time or 0)) > 5:
                self.last_progress_time = time.time()
                elapsed = time.time() - self.start_time
                rate = i / elapsed if elapsed > 0 else 0
                remaining = (total_files - i) / rate if rate > 0 else 0
                eta = timedelta(seconds=int(remaining))
                
                pct = (i / total_files) * 100
                logger.info(f"   [{i:,}/{total_files:,}] {pct:.1f}% | "
                          f"{rate:.1f} files/sec | ETA: {eta}")
        
        # Summary
        elapsed = time.time() - self.start_time
        rate = total_files / elapsed if elapsed > 0 else 0
        
        logger.info("\n" + "=" * 70)
        logger.info("📊 IMPORT COMPLETE - Summary")
        logger.info("=" * 70)
        logger.info(f"   Files processed:  {self.stats['files_processed']:,}")
        logger.info(f"   Files skipped:    {self.stats['files_skipped']:,}")
        logger.info(f"   Files failed:     {self.stats['files_failed']:,}")
        logger.info(f"   Rounds created: {self.stats['rounds_created']:,}")
        logger.info(f"   Players inserted: {self.stats['players_inserted']:,}")
        logger.info(f"   Weapons inserted: {self.stats['weapons_inserted']:,}")
        logger.info(f"   Time elapsed:     {timedelta(seconds=int(elapsed))}")
        logger.info(f"   Processing rate:  {rate:.2f} files/second")
        logger.info("=" * 70)
        
        return True
    
    # =========================================================================
    # DISASTER RECOVERY & MAINTENANCE
    # =========================================================================
    
    def rebuild_from_scratch(self, year: int = 2025, confirm: bool = False) -> bool:
        """
        NUCLEAR OPTION: Delete everything and rebuild from scratch
        
        Use this when database is corrupted or you need a fresh start.
        
        Args:
            year: Year to import (default: 2025)
            confirm: Must be True to proceed (safety check)
        
        Returns:
            True if successful
        """
        if not confirm:
            logger.error("❌ Must set confirm=True to rebuild from scratch!")
            logger.error("   This is a safety check to prevent accidental deletion.")
            return False
        
        logger.info("=" * 70)
        logger.info("💣 DISASTER RECOVERY - Rebuild from scratch")
        logger.info("=" * 70)
        logger.warning("⚠️  This will DELETE ALL DATA and recreate database!")
        
        # Create fresh database (with backup)
        if not self.create_fresh_database(backup_existing=True):
            return False
        
        # Import all data
        logger.info("\n📥 Importing all data...")
        return self.import_all_files(year_filter=year)
    
    def fix_date_range(self, start_date: str, end_date: str) -> bool:
        """
        Surgical fix: Re-import specific date range
        
        Use this to fix known bad data without touching everything else.
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        
        Returns:
            True if successful
        """
        logger.info("=" * 70)
        logger.info(f"🔧 DATE RANGE FIX - {start_date} to {end_date}")
        logger.info("=" * 70)
        
        # Delete data in range
        logger.info("🗑️  Deleting existing data in range...")
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                DELETE FROM weapon_comprehensive_stats 
                WHERE round_date BETWEEN ? AND ?
            """, (start_date, end_date))
            weapons_deleted = cursor.rowcount
            
            cursor.execute("""
                DELETE FROM player_comprehensive_stats 
                WHERE round_date BETWEEN ? AND ?
            """, (start_date, end_date))
            players_deleted = cursor.rowcount
            
            cursor.execute("""
                DELETE FROM rounds 
                WHERE round_date BETWEEN ? AND ?
            """, (start_date, end_date))
            sessions_deleted = cursor.rowcount
            
            cursor.execute("""
                DELETE FROM processed_files 
                WHERE filename BETWEEN ? AND ?
            """, (f"{start_date}-%", f"{end_date}-~"))
            files_cleared = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            logger.info(f"   Deleted {sessions_deleted:,} sessions")
            logger.info(f"   Deleted {players_deleted:,} player rows")
            logger.info(f"   Deleted {weapons_deleted:,} weapon rows")
            logger.info(f"   Cleared {files_cleared:,} processed file records")
            
        except sqlite3.Error as e:
            logger.error(f"❌ Failed to clear date range: {e}")
            return False
        
        # Re-import files in range
        logger.info("\n📥 Re-importing files in date range...")
        
        files_to_import = []
        for file_path in sorted(self.stats_dir.glob("*.txt")):
            file_date = '-'.join(file_path.name.split('-')[:3])
            if start_date <= file_date <= end_date:
                files_to_import.append(file_path)
        
        logger.info(f"   Found {len(files_to_import)} files in range")
        
        for file_path in files_to_import:
            self.process_file(file_path)
        
        logger.info(f"\n✅ Date range fix complete!")
        logger.info(f"   Files processed: {len(files_to_import)}")
        
        return True
    
    def validate_database(self) -> Dict:
        """
        Validate database integrity and return statistics
        
        Returns:
            Dict with validation results
        """
        logger.info("🔍 Validating database...")
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check rounds
            cursor.execute("SELECT COUNT(*) FROM rounds")
            round_count = cursor.fetchone()[0]
            
            # Check players
            cursor.execute("SELECT COUNT(*) FROM player_comprehensive_stats")
            player_count = cursor.fetchone()[0]
            
            # Check weapons
            cursor.execute("SELECT COUNT(*) FROM weapon_comprehensive_stats")
            weapon_count = cursor.fetchone()[0]
            
            # Check processed files
            cursor.execute("SELECT COUNT(*) FROM processed_files WHERE success = 1")
            processed_count = cursor.fetchone()[0]
            
            # Date range
            cursor.execute("SELECT MIN(round_date), MAX(round_date) FROM rounds")
            date_range = cursor.fetchone()
            
            # Check for sessions without players (data integrity issue)
            cursor.execute("""
                SELECT COUNT(*) FROM rounds s
                LEFT JOIN player_comprehensive_stats p ON p.round_id = s.id
                WHERE p.id IS NULL
            """)
            orphan_sessions = cursor.fetchone()[0]
            
            # Check for sessions without weapons (potential issue)
            cursor.execute("""
                SELECT COUNT(*) FROM rounds s
                LEFT JOIN weapon_comprehensive_stats w ON w.round_id = s.id
                WHERE w.id IS NULL
            """)
            no_weapon_sessions = cursor.fetchone()[0]
            
            conn.close()
            
            results = {
                'rounds': round_count,
                'players': player_count,
                'weapons': weapon_count,
                'processed_files': processed_count,
                'date_range': date_range,
                'orphan_sessions': orphan_sessions,
                'no_weapon_sessions': no_weapon_sessions,
                'valid': orphan_sessions == 0
            }
            
            logger.info("\n📊 Database Statistics:")
            logger.info(f"   Sessions:          {round_count:,}")
            logger.info(f"   Player stats:      {player_count:,}")
            logger.info(f"   Weapon stats:      {weapon_count:,}")
            logger.info(f"   Processed files:   {processed_count:,}")
            logger.info(f"   Date range:        {date_range[0]} to {date_range[1]}")
            logger.info(f"   Orphan sessions:   {orphan_sessions:,}")
            logger.info(f"   No weapon sessions: {no_weapon_sessions:,}")
            
            if results['valid']:
                logger.info("✅ Database validation passed!")
            else:
                logger.warning("⚠️  Database has integrity issues!")
            
            return results
            
        except sqlite3.Error as e:
            logger.error(f"❌ Validation failed: {e}")
            return {'valid': False, 'error': str(e)}


def main():
    """Interactive database manager"""
    print("\n" + "=" * 70)
    print("🏗️  ET:LEGACY DATABASE MANAGER")
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
    
    manager = DatabaseManager()
    
    if choice == "1":
        manager.create_fresh_database(backup_existing=True)
        
    elif choice == "2":
        print("\nImport options:")
        print("  1 - Full year (all 2025 files)")
        print("  2 - Last 30 days only")
        print("  3 - Custom date range")
        sub = input("Select [1]: ").strip() or "1"
        
        if sub == "1":
            year = input("Year to import [2025]: ").strip() or "2025"
            manager.import_all_files(year_filter=int(year))
        elif sub == "2":
            from datetime import datetime, timedelta
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            print(f"📅 Importing files from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
            # Filter files by date
            all_files = sorted(manager.stats_dir.glob("*.txt"))
            recent_files = [f for f in all_files if f.name[:10] >= start_date.strftime('%Y-%m-%d')]
            print(f"   Found {len(recent_files)} files in last 30 days")
            for file_path in recent_files:
                manager.process_file(file_path)
        elif sub == "3":
            start = input("Start date (YYYY-MM-DD): ").strip()
            end = input("End date (YYYY-MM-DD): ").strip()
            all_files = sorted(manager.stats_dir.glob("*.txt"))
            filtered = [f for f in all_files if start <= f.name[:10] <= end]
            print(f"   Found {len(filtered)} files in range")
            for file_path in filtered:
                manager.process_file(file_path)
        
    elif choice == "3":
        print("\n⚠️  WARNING: This will DELETE ALL DATA!")
        confirm = input("Type 'YES DELETE EVERYTHING' to confirm: ")
        if confirm == "YES DELETE EVERYTHING":
            print("\nRebuild options:")
            print("  1 - Full year (all 2025 files)")
            print("  2 - Last 30 days only (RECOMMENDED for production)")
            print("  3 - Custom date range")
            sub = input("Select [2]: ").strip() or "2"
            
            if sub == "1":
                year = input("Year to import [2025]: ").strip() or "2025"
                manager.rebuild_from_scratch(year=int(year), confirm=True)
            elif sub == "2":
                from datetime import datetime, timedelta
                # For rebuild, we still need to create DB first
                if not manager.create_fresh_database(backup_existing=True):
                    print("❌ Failed to create database")
                else:
                    end_date = datetime.now()
                    start_date = end_date - timedelta(days=30)
                    print(f"📅 Importing files from {start_date.strftime('%Y-%m-%d')} onwards...")
                    all_files = sorted(manager.stats_dir.glob("*.txt"))
                    recent_files = [f for f in all_files if f.name[:10] >= start_date.strftime('%Y-%m-%d')]
                    print(f"   Found {len(recent_files)} files in last 30 days")
                    manager.start_time = time.time()
                    for i, file_path in enumerate(recent_files, 1):
                        manager.process_file(file_path)
                        if i % 10 == 0:
                            pct = (i / len(recent_files)) * 100
                            print(f"   [{i}/{len(recent_files)}] {pct:.1f}%")
            elif sub == "3":
                start = input("Start date (YYYY-MM-DD): ").strip()
                end = input("End date (YYYY-MM-DD): ").strip()
                if not manager.create_fresh_database(backup_existing=True):
                    print("❌ Failed to create database")
                else:
                    all_files = sorted(manager.stats_dir.glob("*.txt"))
                    filtered = [f for f in all_files if start <= f.name[:10] <= end]
                    print(f"   Found {len(filtered)} files in range")
                    manager.start_time = time.time()
                    for i, file_path in enumerate(filtered, 1):
                        manager.process_file(file_path)
                        if i % 10 == 0:
                            pct = (i / len(filtered)) * 100
                            print(f"   [{i}/{len(filtered)}] {pct:.1f}%")
        else:
            print("❌ Aborted")
    
    elif choice == "4":
        start = input("Start date (YYYY-MM-DD) [2025-10-28]: ").strip() or "2025-10-28"
        end = input("End date (YYYY-MM-DD) [2025-10-30]: ").strip() or "2025-10-30"
        manager.fix_date_range(start, end)
    
    elif choice == "5":
        manager.validate_database()
    
    elif choice == "6":
        print("\n🧪 Quick test - importing 10 files...")
        manager.import_all_files(year_filter=2025, limit=10)
    
    else:
        print("❌ Invalid choice")


if __name__ == "__main__":
    main()
