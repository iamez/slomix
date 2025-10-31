#!/usr/bin/env python3
"""
Enhanced Database with Auto-Linking Feature
Automatically links Discord users when GUID matches are found
"""
import json
from typing import Dict, List, Optional
from datetime import datetime
import logging
import aiosqlite

logger = logging.getLogger('DatabaseAutoLink')

class AutoLinkDatabase:
    """Enhanced Database with auto-linking capabilities"""
    
    def __init__(self, db_path: str, auto_link_mappings: Optional[Dict[str, tuple]] = None):
        self.db_path = db_path
        # GUID -> (discord_id, discord_name) mappings
        self.auto_link_mappings = auto_link_mappings or {}
        
    async def initialize(self):
        """Create all database tables with auto-linking support"""
        async with aiosqlite.connect(self.db_path) as db:
            # Create players table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS players (
                    discord_id TEXT PRIMARY KEY,
                    et_guid TEXT UNIQUE,
                    et_name TEXT,
                    trueskill_mu REAL DEFAULT 25.0,
                    trueskill_sigma REAL DEFAULT 8.333,
                    matches_played INTEGER DEFAULT 0,
                    wins INTEGER DEFAULT 0,
                    losses INTEGER DEFAULT 0,
                    auto_linked BOOLEAN DEFAULT FALSE,
                    linked_at TIMESTAMP NULL
                )
            ''')
            
            # Create matches table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS matches (
                    match_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    map_name TEXT,
                    round_num INTEGER,
                    team1_score INTEGER,
                    team2_score INTEGER,
                    winner_team TEXT
                )
            ''')
            
            # Create player_stats table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS player_stats (
                    stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_guid TEXT,
                    match_id INTEGER,
                    damage_given INTEGER,
                    damage_received INTEGER,
                    kills INTEGER,
                    deaths INTEGER,
                    headshots INTEGER,
                    kill_quality REAL,
                    playtime_denied REAL,
                    weapon_stats TEXT
                )
            ''')
            
            # Create processed_files table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS processed_files (
                    file_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT UNIQUE NOT NULL,
                    file_hash TEXT NOT NULL,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create auto_link_log table to track linking activity
            await db.execute('''
                CREATE TABLE IF NOT EXISTS auto_link_log (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    et_guid TEXT,
                    discord_id TEXT,
                    discord_name TEXT,
                    et_name TEXT,
                    linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    link_method TEXT  -- 'auto' or 'manual'
                )
            ''')
            
            # Add indexes
            await db.execute('CREATE INDEX IF NOT EXISTS idx_players_discord_id ON players(discord_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_players_et_guid ON players(et_guid)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_player_stats_guid ON player_stats(player_guid)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_player_stats_match ON player_stats(match_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_matches_timestamp ON matches(timestamp)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_processed_files_filename ON processed_files(filename)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_auto_link_log_guid ON auto_link_log(et_guid)')
            
            await db.commit()
            logger.info(f"Auto-link database initialized with {len(self.auto_link_mappings)} pre-configured mappings")
    
    async def save_match_stats_with_auto_link(self, stats_data: Dict):
        """Save match statistics and automatically link Discord users"""
        async with aiosqlite.connect(self.db_path) as db:
            # Insert match
            cursor = await db.execute(
                'INSERT INTO matches (timestamp, map_name, round_num, team1_score, team2_score, winner_team) VALUES (?, ?, ?, ?, ?, ?)',
                (
                    stats_data.get('timestamp', datetime.utcnow().isoformat()),
                    stats_data.get('map_name'),
                    stats_data.get('round_num', 1),
                    stats_data.get('team1_score', 0),
                    stats_data.get('team2_score', 0),
                    stats_data.get('winner_team', '')
                )
            )
            match_id = cursor.lastrowid
            
            auto_link_count = 0
            
            # Process each player
            for player in stats_data.get('players', []):
                guid = player.get('guid')
                name = player.get('name')
                
                # Check if player exists in players table
                cursor = await db.execute('SELECT discord_id, auto_linked FROM players WHERE et_guid = ?', (guid,))
                existing_player = await cursor.fetchone()
                
                if existing_player:
                    # Update existing player name if it changed
                    await db.execute(
                        'UPDATE players SET et_name = ? WHERE et_guid = ?',
                        (name, guid)
                    )
                else:
                    # Check for auto-link opportunity
                    discord_id = None
                    discord_name = None
                    auto_linked = False
                    
                    if guid in self.auto_link_mappings:
                        discord_id, discord_name = self.auto_link_mappings[guid]
                        auto_linked = True
                        auto_link_count += 1
                        
                        # Log the auto-link
                        await db.execute(
                            'INSERT INTO auto_link_log (et_guid, discord_id, discord_name, et_name, link_method) VALUES (?, ?, ?, ?, ?)',
                            (guid, discord_id, discord_name, name, 'auto')
                        )
                        
                        logger.info(f"🔗 Auto-linked {name} ({guid}) -> {discord_name} ({discord_id})")
                    
                    # Insert new player with potential auto-link
                    await db.execute(
                        'INSERT INTO players (et_guid, et_name, discord_id, auto_linked, linked_at) VALUES (?, ?, ?, ?, ?)',
                        (
                            guid,
                            name,
                            discord_id,
                            auto_linked,
                            datetime.utcnow().isoformat() if auto_linked else None
                        )
                    )
                
                # Store per-weapon stats as JSON if present
                weapon_stats = player.get('weapon_stats')
                weapon_stats_json = json.dumps(weapon_stats) if weapon_stats else None
                
                # Insert player stats
                await db.execute(
                    'INSERT INTO player_stats (player_guid, match_id, damage_given, damage_received, kills, deaths, headshots, kill_quality, playtime_denied, weapon_stats) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    (
                        guid,
                        match_id,
                        player.get('damage_given', 0),
                        player.get('damage_received', 0),
                        player.get('kills', 0),
                        player.get('deaths', 0),
                        player.get('headshots', 0),
                        player.get('kill_quality', 0.0),
                        player.get('playtime_denied', 0.0),
                        weapon_stats_json
                    )
                )
            
            await db.commit()
            
            if auto_link_count > 0:
                logger.info(f"✨ Auto-linked {auto_link_count} players in this match!")
            
            return match_id
    
    async def is_file_processed(self, filename: str) -> bool:
        """Check if a stats file has already been processed"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('SELECT 1 FROM processed_files WHERE filename = ?', (filename,))
            result = await cursor.fetchone()
            return result is not None
    
    async def mark_file_processed(self, filename: str, file_hash: str):
        """Mark a stats file as processed"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'INSERT OR IGNORE INTO processed_files (filename, file_hash) VALUES (?, ?)',
                (filename, file_hash)
            )
            await db.commit()
    
    async def add_auto_link_mapping(self, guid: str, discord_id: str, discord_name: str):
        """Add a new auto-link mapping and apply it to existing unlinked players"""
        self.auto_link_mappings[guid] = (discord_id, discord_name)
        
        async with aiosqlite.connect(self.db_path) as db:
            # Check if player exists and is unlinked
            cursor = await db.execute(
                'SELECT et_name FROM players WHERE et_guid = ? AND discord_id IS NULL',
                (guid,)
            )
            player = await cursor.fetchone()
            
            if player:
                et_name = player[0]
                
                # Update the player
                await db.execute(
                    'UPDATE players SET discord_id = ?, auto_linked = TRUE, linked_at = ? WHERE et_guid = ?',
                    (discord_id, datetime.utcnow().isoformat(), guid)
                )
                
                # Log the linking
                await db.execute(
                    'INSERT INTO auto_link_log (et_guid, discord_id, discord_name, et_name, link_method) VALUES (?, ?, ?, ?, ?)',
                    (guid, discord_id, discord_name, et_name, 'manual_auto')
                )
                
                await db.commit()
                logger.info(f"🔗 Added auto-link mapping and applied to existing player: {et_name} -> {discord_name}")
                return True
            else:
                logger.info(f"📝 Added auto-link mapping for future use: {guid} -> {discord_name}")
                return False
    
    async def get_auto_link_stats(self) -> Dict:
        """Get statistics about auto-linking activity"""
        async with aiosqlite.connect(self.db_path) as db:
            # Total players
            cursor = await db.execute('SELECT COUNT(*) FROM players')
            result = await cursor.fetchone()
            total_players = result[0] if result else 0
            
            # Auto-linked players
            cursor = await db.execute('SELECT COUNT(*) FROM players WHERE auto_linked = TRUE')
            result = await cursor.fetchone()
            auto_linked = result[0] if result else 0
            
            # Manually linked players
            cursor = await db.execute('SELECT COUNT(*) FROM players WHERE discord_id IS NOT NULL AND auto_linked = FALSE')
            result = await cursor.fetchone()
            manual_linked = result[0] if result else 0
            
            # Unlinked players
            cursor = await db.execute('SELECT COUNT(*) FROM players WHERE discord_id IS NULL')
            result = await cursor.fetchone()
            unlinked = result[0] if result else 0
            
            # Recent auto-links
            cursor = await db.execute('''
                SELECT et_name, discord_name, linked_at 
                FROM auto_link_log 
                WHERE link_method = 'auto' 
                ORDER BY linked_at DESC 
                LIMIT 10
            ''')
            recent_links = await cursor.fetchall()
            
            return {
                'total_players': total_players,
                'auto_linked': auto_linked,
                'manual_linked': manual_linked,
                'unlinked': unlinked,
                'auto_link_rate': (auto_linked / total_players * 100) if total_players > 0 else 0,
                'recent_auto_links': recent_links,
                'available_mappings': len(self.auto_link_mappings)
            }

# Configuration for auto-linking mappings
DEFAULT_AUTO_LINK_MAPPINGS = {
    # Add your known GUID -> Discord mappings here
    # Format: "GUID": ("discord_id", "discord_name")
    
    # Example mappings (replace with actual values)
    "1C747DF1": ("123456789012345678", "SmetarskiProner#1234"),
    "EDBB5DA9": ("234567890123456789", "SuperBoyy#5678"), 
    "0A26D447": ("345678901234567890", "carniee#9012"),
    "5D989160": ("456789012345678901", "olz#3456"),
    "D8423F90": ("567890123456789012", "pvid#7890"),
    "9CC78CFE": ("678901234567890123", "v_kt_r#2345"),
    "652EB4A6": ("789012345678901234", "qmr#6789"),
    "2B5938F5": ("890123456789012345", "bronze#0123"),
    "FDA127DF": ("901234567890123456", "wjs#4567"),
    "A0B2063D": ("012345678901234567", "ipkiss#8901"),
}