#!/usr/bin/env python3
"""
Bulk Stats Import Tool - Production Version
============================================
Purpose: Import all c0rnp0rn3.lua stat files into production database

CRITICAL DESIGN DECISION:
- Each round (Round 1 and Round 2) is stored as a SEPARATE session
- This allows accurate DPM tracking per round
- Map summaries can be calculated by combining rounds when needed
- Never combines Round 1 + Round 2 stats into single record

Features:
- Progress tracking with ETA
- Error recovery (continues on failures)
- Duplicate detection (skips already processed files)
- Year filtering (test with 2025 files first)
- Detailed logging
- Summary report

Created: October 3, 2025
Location: /dev folder (as per ground rules)
"""

import sqlite3
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import logging
import time
import json
from typing import Dict, List, Optional, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.community_stats_parser import C0RNP0RN3StatsParser

# Setup logging
log_dir = Path(__file__).parent
log_file = log_dir / 'bulk_import.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(str(log_file), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('BulkImport')


class BulkStatsImporter:
    """Import all stat files into production database"""
    
    def __init__(self, db_path: str = "etlegacy_production.db"):
        self.db_path = db_path
        self.parser = C0RNP0RN3StatsParser()
        
        # Statistics tracking
        self.stats = {
            'total_files': 0,
            'processed_files': 0,
            'skipped_files': 0,
            'failed_files': 0,
            'sessions_created': 0,
            'players_inserted': 0,
            'weapons_inserted': 0,
            'start_time': None,
            'end_time': None,
            'errors': []
        }
        
        # Performance tracking
        self.start_time = None
        self.last_progress_time = None
        
        # Ensure database schema exists
        self.ensure_schema()
    
    def ensure_schema(self):
        """Create database schema if it doesn't exist"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if sessions table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'")
            if cursor.fetchone():
                logger.info("✅ Database schema already exists")
                conn.close()
                return
            
            logger.info("🏗️  Creating database schema...")
            
            # 1. Sessions table
            cursor.execute('''
                CREATE TABLE sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_date TEXT NOT NULL,
                    map_name TEXT NOT NULL,
                    round_number INTEGER NOT NULL,
                    defender_team INTEGER DEFAULT 0,
                    winner_team INTEGER DEFAULT 0,
                    time_limit TEXT,
                    actual_time TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    map_id INTEGER
                )
            ''')
            logger.info("  ✅ Created sessions table")
            
            # 2. Player comprehensive stats (53 columns!)
            cursor.execute('''
                CREATE TABLE player_comprehensive_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    session_date TEXT NOT NULL,
                    map_name TEXT NOT NULL,
                    round_number INTEGER NOT NULL,
                    player_guid TEXT NOT NULL,
                    player_name TEXT NOT NULL,
                    clean_name TEXT NOT NULL,
                    team INTEGER,
                    
                    -- Core combat stats
                    kills INTEGER DEFAULT 0,
                    deaths INTEGER DEFAULT 0,
                    damage_given INTEGER DEFAULT 0,
                    damage_received INTEGER DEFAULT 0,
                    team_damage_given INTEGER DEFAULT 0,
                    team_damage_received INTEGER DEFAULT 0,
                    
                    -- Special kills
                    gibs INTEGER DEFAULT 0,
                    self_kills INTEGER DEFAULT 0,
                    team_kills INTEGER DEFAULT 0,
                    team_gibs INTEGER DEFAULT 0,
                    headshot_kills INTEGER DEFAULT 0,
                    
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
                    FOREIGN KEY (session_id) REFERENCES sessions(id),
                    
                    -- ✅ DUPLICATE PREVENTION: Ensure one player per session
                    UNIQUE(session_id, player_guid)
                )
            ''')
            logger.info("  ✅ Created player_comprehensive_stats table (53 columns + duplicate prevention)")
            
            # 3. Weapon comprehensive stats
            cursor.execute('''
                CREATE TABLE weapon_comprehensive_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    session_date TEXT NOT NULL,
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
                    FOREIGN KEY (session_id) REFERENCES sessions(id),
                    
                    -- ✅ DUPLICATE PREVENTION: Ensure one weapon per player per session
                    UNIQUE(session_id, player_guid, weapon_name)
                )
            ''')
            logger.info("  ✅ Created weapon_comprehensive_stats table (with duplicate prevention)")
            
            # 4. Player links (Discord ↔ GUID)
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
            logger.info("  ✅ Created player_links table")
            
            # 5. Processed files tracking
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
            logger.info("  ✅ Created processed_files table")
            
            # 6. Session teams (for team detection)
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
            logger.info("  ✅ Created session_teams table")
            
            # 7. Player aliases
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
            logger.info("  ✅ Created player_aliases table")
            
            # Create indexes for performance
            cursor.execute('CREATE INDEX idx_sessions_date_map ON sessions(session_date, map_name)')
            cursor.execute('CREATE INDEX idx_player_stats_session ON player_comprehensive_stats(session_id)')
            cursor.execute('CREATE INDEX idx_player_stats_guid ON player_comprehensive_stats(player_guid)')
            cursor.execute('CREATE INDEX idx_weapon_stats_session ON weapon_comprehensive_stats(session_id)')
            cursor.execute('CREATE INDEX idx_weapon_stats_guid ON weapon_comprehensive_stats(player_guid)')
            logger.info("  ✅ Created performance indexes")
            
            conn.commit()
            conn.close()
            
            logger.info("🎉 Database schema created successfully!")
            logger.info("   • 7 tables + indexes created")
            logger.info("   • Ready for import!")
            
        except sqlite3.Error as e:
            logger.error(f"❌ Failed to create schema: {e}")
            raise
        
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
        except sqlite3.Error as e:
            logger.warning(f"Error checking processed files: {e}")
            return False
    
    def mark_file_processed(self, filename: str, file_size: int = 0, 
                           player_count: int = 0, success: bool = True):
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
    
    def create_or_get_session(self, parsed_data: Dict, file_date: str) -> Optional[int]:
        """
        Create new session or get existing one
        
        IMPORTANT: Each round is a SEPARATE session!
        Round 1 and Round 2 are stored independently.
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()
            
            map_name = parsed_data.get('map_name', 'Unknown')
            round_num = parsed_data.get('round_num', 1)
            
            # Extract time from parsed data
            time_limit = parsed_data.get('map_time', '0:00')
            actual_time = parsed_data.get('actual_time', '0:00')
            
            # FIXED: Remove deduplication logic - allow multiple plays of same map!
            # Players can play escape (or any map) multiple times in a row if they want
            # Each file gets its own session - full granularity tracking
            
            # Create new session - EVERY FILE CREATES A NEW SESSION!
            cursor.execute('''
                INSERT INTO sessions (
                    session_date, map_name, round_number,
                    time_limit, actual_time, created_at
                )
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (file_date, map_name, round_num, time_limit, actual_time))
            
            session_id = cursor.lastrowid
            conn.commit()
            
            self.stats['sessions_created'] += 1
            logger.debug(f"Created new session {session_id}: {map_name} Round {round_num}")
            
            return session_id
            
        except sqlite3.Error as e:
            logger.error(f"Database error creating session: {e}")
            return None
        finally:
            if conn:
                conn.close()
    
    def insert_player_stats(self, session_id: int, session_date: str, map_name: str, round_num: int, player: Dict) -> bool:
        """Insert player comprehensive stats for this session"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.execute('BEGIN TRANSACTION')  # ✅ FIX: Start transaction
            cursor = conn.cursor()
            
            # Extract player data with defaults
            guid = player.get('guid', 'UNKNOWN')
            name = player.get('name', 'Unknown')
            clean_name = self.parser.strip_color_codes(name)
            team = player.get('team', 0)
            
            # Extract objective/support stats from parser (36 fields from c0rnp0rn3.lua)
            obj_stats = player.get('objective_stats', {})
            
            # Basic combat stats
            kills = player.get('kills', 0)
            deaths = player.get('deaths', 0)
            damage_given = player.get('damage_given', 0)
            damage_received = player.get('damage_received', 0)
            
            # K/D ratio
            kd_ratio = kills / deaths if deaths > 0 else float(kills)
            
            # Time fields - seconds is primary
            time_played_seconds = player.get('time_played_seconds', 0)
            time_played_minutes = time_played_seconds / 60.0 if time_played_seconds > 0 else 0.0
            
            # DPM already calculated by parser
            dpm = player.get('dpm', 0.0)
            
            # Efficiency & Accuracy
            bullets_fired = obj_stats.get('bullets_fired', 0)
            efficiency = (kills / (kills + deaths) * 100) if (kills + deaths) > 0 else 0.0
            accuracy = player.get('accuracy', 0.0)
            
            # Time dead - normalize to percentage and compute minutes
            raw_td = obj_stats.get('time_dead_ratio', 0) or 0
            if raw_td <= 1:
                time_dead_ratio = raw_td * 100.0
            else:
                time_dead_ratio = float(raw_td)
            
            time_dead_minutes = time_played_minutes * (time_dead_ratio / 100.0)
            
            # ✅ INSERT ALL 51 VALUES (matching bot's implementation)
            cursor.execute('''
                INSERT INTO player_comprehensive_stats (
                    session_id, session_date, map_name, round_number,
                    player_guid, player_name, clean_name, team,
                    kills, deaths, damage_given, damage_received,
                    team_damage_given, team_damage_received,
                    gibs, self_kills, team_kills, team_gibs, headshot_kills,
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
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session_id, session_date, map_name, round_num,
                guid, name, clean_name, team,
                kills, deaths, damage_given, damage_received,
                obj_stats.get('team_damage_given', 0),  # ✅ FIX: was player.get()
                obj_stats.get('team_damage_received', 0),  # ✅ FIX: was player.get()
                obj_stats.get('gibs', 0),
                obj_stats.get('self_kills', 0),
                obj_stats.get('team_kills', 0),
                obj_stats.get('team_gibs', 0),
                obj_stats.get('headshot_kills', 0),  # ✅ FIX: was player.get('headshots')
                time_played_seconds,
                time_played_minutes,
                time_dead_minutes,
                time_dead_ratio,
                obj_stats.get('xp', 0),
                kd_ratio,
                dpm,
                efficiency,
                bullets_fired,
                accuracy,
                obj_stats.get('kill_assists', 0),
                0,  # objectives_completed
                0,  # objectives_destroyed
                obj_stats.get('objectives_stolen', 0),
                obj_stats.get('objectives_returned', 0),
                obj_stats.get('dynamites_planted', 0),
                obj_stats.get('dynamites_defused', 0),
                obj_stats.get('times_revived', 0),
                obj_stats.get('revives_given', 0),
                obj_stats.get('useful_kills', 0),  # ✅ FIX: was 'most_useful_kills'
                obj_stats.get('useless_kills', 0),
                obj_stats.get('kill_steals', 0),
                obj_stats.get('denied_playtime', 0),
                obj_stats.get('repairs_constructions', 0),  # ✅ FIX: was hardcoded 0
                obj_stats.get('tank_meatshield', 0),
                obj_stats.get('multikill_2x', 0),  # ✅ FIX: was 'double_kills'
                obj_stats.get('multikill_3x', 0),  # ✅ FIX: was 'triple_kills'
                obj_stats.get('multikill_4x', 0),  # ✅ FIX: was 'quad_kills'
                obj_stats.get('multikill_5x', 0),  # ✅ FIX: was 'multi_kills'
                obj_stats.get('multikill_6x', 0),  # ✅ FIX: was 'mega_kills'
                obj_stats.get('killing_spree', 0),
                obj_stats.get('death_spree', 0),
            ))
            
            conn.commit()  # ✅ FIX: Commit transaction (only if all succeeded)
            
            self.stats['players_inserted'] += 1
            return True
            
        except sqlite3.Error as e:
            if conn:
                conn.rollback()  # ✅ FIX: Rollback on error to prevent partial writes
            logger.error(f"Error inserting player stats: {e}")
            logger.error(f"Player: {name}, Session: {session_id}")
            return False
        finally:
            if conn:
                conn.close()
    
    def insert_weapon_stats(self, session_id: int, session_date: str, map_name: str, round_num: int, player: Dict) -> bool:
        """Insert weapon stats for this player/session"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.execute('BEGIN TRANSACTION')  # ✅ FIX: Start transaction
            cursor = conn.cursor()
            
            guid = player.get('guid', 'UNKNOWN')
            name = player.get('name', 'Unknown')
            weapon_stats = player.get('weapon_stats', {})
            
            weapons_inserted = 0
            
            logger.debug(f"[WEAPON] Player {name} has {len(weapon_stats)} weapons")
            
            # Insert each weapon that was used
            for weapon_name, stats in weapon_stats.items():
                logger.debug(f"[WEAPON] {weapon_name}: shots={stats.get('shots', 0)}, kills={stats.get('kills', 0)}")
                # Only insert weapons with actual usage
                if stats.get('shots', 0) > 0 or stats.get('kills', 0) > 0:
                    cursor.execute('''
                        INSERT INTO weapon_comprehensive_stats (
                            session_id, session_date, map_name, round_number,
                            player_guid, player_name, weapon_name,
                            kills, deaths, headshots, hits, shots, accuracy
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        session_id, session_date, map_name, round_num,
                        guid, name, weapon_name,
                        stats.get('kills', 0), stats.get('deaths', 0), stats.get('headshots', 0),
                        stats.get('hits', 0), stats.get('shots', 0), stats.get('accuracy', 0.0)
                    ))
                    weapons_inserted += 1
            
            conn.commit()  # ✅ FIX: Commit transaction (only if all succeeded)
            
            self.stats['weapons_inserted'] += weapons_inserted
            return True
            
        except sqlite3.Error as e:
            if conn:
                conn.rollback()  # ✅ FIX: Rollback on error to prevent partial writes
            logger.error(f"Error inserting weapon stats: {e}")
            return False
        finally:
            if conn:
                conn.close()
    
    def process_single_file(self, file_path: Path) -> Tuple[bool, str]:
        """
        Process a single stat file
        
        Returns: (success: bool, message: str)
        """
        filename = file_path.name
        
        try:
            # Check if already processed
            if self.is_file_processed(filename):
                logger.debug(f"Skipping already processed: {filename}")
                self.stats['skipped_files'] += 1
                return True, "Already processed"
            
            # Parse the file
            logger.debug(f"Parsing: {filename}")
            parsed = self.parser.parse_stats_file(str(file_path))
            
            if not parsed.get('success', False):
                error_msg = parsed.get('error', 'Unknown parse error')
                logger.warning(f"Parse failed for {filename}: {error_msg}")
                self.stats['failed_files'] += 1
                self.stats['errors'].append({
                    'file': filename,
                    'error': f"Parse error: {error_msg}"
                })
                
                # Mark as processed but failed
                self.mark_file_processed(filename, file_path.stat().st_size, 0, success=False)
                return False, f"Parse error: {error_msg}"
            
            # Extract date from filename (YYYY-MM-DD-HHMMSS-...)
            file_date = '-'.join(filename.split('-')[:3])  # YYYY-MM-DD
            
            # Create session for THIS ROUND
            session_id = self.create_or_get_session(parsed, file_date)
            if not session_id:
                logger.error(f"Failed to create session for {filename}")
                self.stats['failed_files'] += 1
                self.stats['errors'].append({
                    'file': filename,
                    'error': 'Failed to create session'
                })
                return False, "Session creation failed"
            
            # Insert player stats for this round
            players = parsed.get('players', [])
            success_count = 0
            map_name = parsed.get('map_name', 'Unknown')
            round_num = parsed.get('round_num', 1)
            
            for player in players:
                if self.insert_player_stats(session_id, file_date, map_name, round_num, player):
                    # Also insert weapon stats
                    self.insert_weapon_stats(session_id, file_date, map_name, round_num, player)
                    success_count += 1
            
            # Mark file as successfully processed
            self.mark_file_processed(
                filename, 
                file_path.stat().st_size,
                len(players),
                success=True
            )
            
            self.stats['processed_files'] += 1
            logger.debug(f"[OK] Processed {filename}: {len(players)} players, session {session_id}")
            
            return True, f"Imported {len(players)} players"
            
        except Exception as e:
            logger.error(f"Exception processing {filename}: {e}")
            self.stats['failed_files'] += 1
            self.stats['errors'].append({
                'file': filename,
                'error': str(e)
            })
            return False, str(e)
    
    def show_progress(self, current: int, total: int, file_name: str):
        """Show progress bar and ETA"""
        # Update every 10 files or every 5 seconds
        now = time.time()
        if self.last_progress_time and (now - self.last_progress_time < 5) and current % 10 != 0:
            return
        
        self.last_progress_time = now
        
        # Calculate progress
        percentage = (current / total) * 100
        elapsed = now - self.start_time
        
        # Calculate ETA
        if current > 0:
            rate = current / elapsed  # files per second
            remaining = total - current
            eta_seconds = remaining / rate if rate > 0 else 0
            eta = timedelta(seconds=int(eta_seconds))
        else:
            eta = "calculating..."
        
        # Create progress bar
        bar_length = 40
        filled = int(bar_length * current / total)
        bar = '█' * filled + '░' * (bar_length - filled)
        
        # Show progress
        print(f"\r[{bar}] {percentage:.1f}% ({current}/{total}) | "
              f"ETA: {eta} | {file_name[:40]:<40}", end='', flush=True)
    
    def import_all_files(self, year_filter: Optional[int] = None, 
                        limit: Optional[int] = None,
                        resume: bool = True) -> bool:
        """
        Import all stat files from local_stats folder
        
        Args:
            year_filter: Only import files from this year (e.g., 2025)
            limit: Only import first N files (for testing)
            resume: Skip already processed files (default: True)
        """
        logger.info("="*70)
        logger.info("[START] BULK STATS IMPORT - STARTING")
        logger.info("="*70)
        logger.info(f"Database: {self.db_path}")
        logger.info(f"Year filter: {year_filter or 'All years'}")
        logger.info(f"Limit: {limit or 'No limit'}")
        logger.info(f"Resume mode: {'ON' if resume else 'OFF'}")
        logger.info("IMPORTANT: Each round stored as SEPARATE session!")
        logger.info("")
        
        # Find all stat files
        local_stats = Path(__file__).parent.parent / "local_stats"
        all_files = sorted(local_stats.glob("*.txt"))
        
        # Apply year filter
        if year_filter:
            all_files = [f for f in all_files if f.name.startswith(f"{year_filter}-")]
            logger.info(f"[FILTER] Filtered to {year_filter}: {len(all_files)} files")
        
        # Apply last 2 weeks filter (default if no year filter)
        if not year_filter and not limit:
            two_weeks_ago = datetime.now() - timedelta(days=14)
            cutoff_date = two_weeks_ago.strftime("%Y-%m-%d")
            all_files = [f for f in all_files if f.name >= cutoff_date]
            logger.info(f"[FILTER] Last 2 weeks (since {cutoff_date}): {len(all_files)} files")
        
        # Apply limit
        if limit:
            all_files = all_files[:limit]
            logger.info(f"[LIMIT] Limited to first {limit} files")
        
        self.stats['total_files'] = len(all_files)
        
        if len(all_files) == 0:
            logger.warning("[WARN] No files found to import!")
            return False
        
        logger.info(f"[INFO] Found {len(all_files)} files to process")
        logger.info("")
        
        # Start import
        self.start_time = time.time()
        self.last_progress_time = self.start_time
        self.stats['start_time'] = datetime.now()
        
        # Process each file
        for i, file_path in enumerate(all_files, 1):
            self.show_progress(i, len(all_files), file_path.name)
            success, message = self.process_single_file(file_path)
        
        # Clear progress line
        print()  # New line after progress bar
        
        self.stats['end_time'] = datetime.now()
        
        # Show summary
        self.show_summary()
        
        return True
    
    def show_summary(self):
        """Show import summary report"""
        logger.info("")
        logger.info("="*70)
        logger.info("[DONE] BULK IMPORT COMPLETE")
        logger.info("="*70)
        
        elapsed = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
        
        logger.info(f"\n[TIME] Import Duration:")
        logger.info(f"   Started:  {self.stats['start_time'].strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"   Finished: {self.stats['end_time'].strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"   Duration: {timedelta(seconds=int(elapsed))}")
        
        logger.info(f"\n[STATS] Files Processed:")
        logger.info(f"   Total:     {self.stats['total_files']}")
        logger.info(f"   Processed: {self.stats['processed_files']} [OK]")
        logger.info(f"   Skipped:   {self.stats['skipped_files']} [SKIP]")
        logger.info(f"   Failed:    {self.stats['failed_files']} [FAIL]")
        
        success_rate = (self.stats['processed_files'] / self.stats['total_files'] * 100) if self.stats['total_files'] > 0 else 0
        logger.info(f"   Success rate: {success_rate:.1f}%")
        
        logger.info(f"\n[DATABASE] Records Created:")
        logger.info(f"   Sessions created:  {self.stats['sessions_created']}")
        logger.info(f"   Players inserted:  {self.stats['players_inserted']}")
        logger.info(f"   Weapons inserted:  {self.stats['weapons_inserted']}")
        
        if self.stats['processed_files'] > 0:
            avg_players = self.stats['players_inserted'] / self.stats['processed_files']
            logger.info(f"   Avg players/file:  {avg_players:.1f}")
        
        logger.info(f"\n[PERFORMANCE] Speed Metrics:")
        if elapsed > 0:
            rate = self.stats['processed_files'] / elapsed
            logger.info(f"   Files per second:  {rate:.2f}")
            logger.info(f"   Files per minute:  {rate * 60:.1f}")
        
        # Show errors if any
        if self.stats['errors']:
            logger.info(f"\n[ERRORS] Import Errors ({len(self.stats['errors'])}):")
            # Show first 10 errors
            for error in self.stats['errors'][:10]:
                logger.info(f"   - {error['file']}: {error['error']}")
            
            if len(self.stats['errors']) > 10:
                logger.info(f"   ... and {len(self.stats['errors']) - 10} more errors")
            
            # Save full error report
            error_file = Path("dev") / f"import_errors_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(error_file, 'w') as f:
                json.dump(self.stats['errors'], f, indent=2)
            logger.info(f"\n   Full error report saved to: {error_file.name}")
        
        logger.info("\n" + "="*70)
        logger.info(f"Database: {self.db_path}")
        logger.info(f"Log file: dev/bulk_import.log")
        logger.info("="*70)


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Bulk import ET:Legacy stat files into production database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Import all files
  python dev/bulk_import_stats.py
  
  # Import only 2025 files (for testing)
  python dev/bulk_import_stats.py --year 2025
  
  # Import first 100 files
  python dev/bulk_import_stats.py --limit 100
  
  # Import with custom database
  python dev/bulk_import_stats.py --db my_database.db
  
  # Fresh import (ignore processed files)
  python dev/bulk_import_stats.py --no-resume
        '''
    )
    
    parser.add_argument(
        '--db',
        default='etlegacy_production.db',
        help='Path to database file (default: etlegacy_production.db)'
    )
    parser.add_argument(
        '--year',
        type=int,
        help='Only import files from this year (e.g., 2025)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Only import first N files (for testing)'
    )
    parser.add_argument(
        '--no-resume',
        action='store_true',
        help='Do not skip already processed files'
    )
    
    args = parser.parse_args()
    
    # Create importer
    importer = BulkStatsImporter(args.db)
    
    # Run import
    try:
        success = importer.import_all_files(
            year_filter=args.year,
            limit=args.limit,
            resume=not args.no_resume
        )
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n\n[WARN] Import interrupted by user")
        logger.info("Import interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
