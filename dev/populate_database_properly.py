#!/usr/bin/env python3
"""
🎮 Production Database Population with Real ET:Legacy Stats
==========================================================
Populates the database using your real stats files with proper schema structure
that matches your existing tools and Discord linking system.
"""

import asyncio
import aiosqlite
import sys
import os
from pathlib import Path
from datetime import datetime, date
import hashlib
import re
from typing import Dict, List, Optional, Any

# Add bot directory to path
sys.path.append(str(Path(__file__).parent.parent / 'bot'))

from community_stats_parser import C0RNP0RN3StatsParser


class ProductionDatabasePopulator:
    """Production-ready database populator for ET:Legacy stats"""
    
    def __init__(self, db_path: str = "../etlegacy_discord_ready.db"):
        self.db_path = db_path
        self.parser = C0RNP0RN3StatsParser()
        self.processed_files = set()
        
    async def initialize_production_database(self):
        """Initialize database with production-ready schema"""
        print("🗄️ Initializing production database schema...")
        
        async with aiosqlite.connect(self.db_path) as db:
            # Sessions table - core session tracking
            await db.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_date DATE NOT NULL,
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    total_rounds INTEGER DEFAULT 0,
                    total_maps INTEGER DEFAULT 0,
                    players_count INTEGER DEFAULT 0,
                    session_mvp_name TEXT,
                    session_mvp_guid TEXT,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Player round stats - individual columns for flexible queries
            await db.execute('''
                CREATE TABLE IF NOT EXISTS player_round_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    round_id TEXT NOT NULL,
                    player_guid TEXT NOT NULL,
                    player_clean_name TEXT NOT NULL,
                    clean_name_final TEXT NOT NULL,
                    
                    -- Core stats (individual columns for Discord queries)
                    kills INTEGER DEFAULT 0,
                    deaths INTEGER DEFAULT 0,
                    headshots INTEGER DEFAULT 0,
                    kd_ratio REAL DEFAULT 0.0,
                    accuracy REAL DEFAULT 0.0,
                    damage_given INTEGER DEFAULT 0,
                    damage_received INTEGER DEFAULT 0,
                    dpm REAL DEFAULT 0.0,
                    
                    -- Weapon-specific kills (individual columns)
                    mp40_kills INTEGER DEFAULT 0,
                    thompson_kills INTEGER DEFAULT 0,
                    fg42_kills INTEGER DEFAULT 0,
                    sniper_kills INTEGER DEFAULT 0,
                    panzerfaust_kills INTEGER DEFAULT 0,
                    grenade_kills INTEGER DEFAULT 0,
                    
                    -- Performance stats
                    killing_spree_best INTEGER DEFAULT 0,
                    kill_assists INTEGER DEFAULT 0,
                    multikills_3 INTEGER DEFAULT 0,
                    
                    -- Time and round info
                    round_duration_minutes REAL DEFAULT 0.0,
                    team INTEGER DEFAULT 0,
                    round_outcome TEXT,
                    
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    FOREIGN KEY (session_id) REFERENCES sessions (id)
                )
            ''')
            
            # Create indexes separately
            await db.execute('CREATE INDEX IF NOT EXISTS idx_player_guid ON player_round_stats (player_guid)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_session_id ON player_round_stats (session_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_clean_name ON player_round_stats (clean_name_final)')
            
            # Player links - Discord ID <-> GUID mapping
            await db.execute('''
                CREATE TABLE IF NOT EXISTS player_links (
                    discord_id TEXT PRIMARY KEY,
                    et_guid TEXT UNIQUE NOT NULL,
                    et_name TEXT NOT NULL,
                    discord_username TEXT,
                    linked_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # File processing tracking
            await db.execute('''
                CREATE TABLE IF NOT EXISTS processed_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT UNIQUE NOT NULL,
                    file_hash TEXT NOT NULL,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            await db.commit()
            print("✅ Production database schema initialized")

    def extract_date_from_filename(self, filename: str) -> Optional[date]:
        """Extract date from ET:Legacy stats filename"""
        # Format: 2025-09-24-233255-te_escape2-round-1.txt
        try:
            date_part = filename.split('-')[:3]  # ['2025', '09', '24']
            if len(date_part) == 3:
                year, month, day = map(int, date_part)
                return date(year, month, day)
        except (ValueError, IndexError):
            pass
        return None

    def calculate_file_hash(self, file_path: Path) -> str:
        """Calculate MD5 hash of file for duplicate detection"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    async def is_file_processed(self, filename: str, file_hash: str) -> bool:
        """Check if file has already been processed"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT id FROM processed_files WHERE filename = ? OR file_hash = ?",
                (filename, file_hash)
            )
            return await cursor.fetchone() is not None

    async def mark_file_processed(self, filename: str, file_hash: str):
        """Mark file as processed"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO processed_files (filename, file_hash) VALUES (?, ?)",
                (filename, file_hash)
            )
            await db.commit()

    def extract_weapon_stats(self, player_data: dict) -> dict:
        """Extract individual weapon kill counts"""
        weapon_stats = {
            'mp40_kills': 0,
            'thompson_kills': 0,
            'fg42_kills': 0,
            'sniper_kills': 0,
            'panzerfaust_kills': 0,
            'grenade_kills': 0
        }
        
        # Your parser should provide weapon breakdown
        weapons = player_data.get('weapon_stats', {})
        if isinstance(weapons, dict):
            weapon_stats['mp40_kills'] = weapons.get('WS_MP40', 0)
            weapon_stats['thompson_kills'] = weapons.get('WS_THOMPSON', 0)
            weapon_stats['fg42_kills'] = weapons.get('WS_FG42', 0)
            weapon_stats['sniper_kills'] = weapons.get('WS_KAR98', 0) + weapons.get('WS_GARAND', 0)
            weapon_stats['panzerfaust_kills'] = weapons.get('WS_PANZERFAUST', 0)
            weapon_stats['grenade_kills'] = weapons.get('WS_GRENADE', 0)
        
        return weapon_stats

    def clean_player_name(self, name: str) -> str:
        """Clean player name by removing color codes"""
        if not name:
            return "Unknown"
        # Remove ET:Legacy color codes (^x where x is any character)
        return re.sub(r'\^.', '', name).strip()

    async def find_or_create_session(self, session_date: date) -> int:
        """Find existing session for date or create new one"""
        async with aiosqlite.connect(self.db_path) as db:
            # Try to find existing session for this date
            cursor = await db.execute(
                "SELECT id FROM sessions WHERE session_date = ?",
                (session_date.isoformat(),)
            )
            session = await cursor.fetchone()
            
            if session:
                return session[0]
            
            # Create new session
            cursor = await db.execute('''
                INSERT INTO sessions (session_date, start_time, status)
                VALUES (?, ?, 'active')
            ''', (session_date.isoformat(), datetime.now().isoformat()))
            
            await db.commit()
            return cursor.lastrowid

    async def process_stats_file(self, file_path: Path) -> bool:
        """Process a single stats file and store in database"""
        try:
            print(f"📊 Processing: {file_path.name}")
            
            # Check if already processed
            file_hash = self.calculate_file_hash(file_path)
            if await self.is_file_processed(file_path.name, file_hash):
                print(f"   ⏭️ Already processed, skipping")
                return True
            
            # Parse the file
            parsed_data = self.parser.parse_stats_file(str(file_path))
            
            if not parsed_data.get('success', False):
                print(f"   ❌ Parser failed: {parsed_data.get('error', 'Unknown error')}")
                return False
            
            # Extract session info
            session_date = self.extract_date_from_filename(file_path.name)
            if not session_date:
                print(f"   ⚠️ Could not extract date from filename")
                session_date = date.today()
            
            session_id = await self.find_or_create_session(session_date)
            
            # Process players
            players = parsed_data.get('players', [])
            if not players:
                print(f"   ⚠️ No players found in file")
                return False
            
            async with aiosqlite.connect(self.db_path) as db:
                round_id = f"{session_date.isoformat()}_{file_path.stem}"
                
                for player in players:
                    # Extract player data
                    guid = player.get('guid', f'UNKNOWN_{player.get("name", "PLAYER")}')
                    raw_name = player.get('name', 'Unknown')
                    clean_name = self.clean_player_name(raw_name)
                    
                    # Extract stats
                    kills = player.get('kills', 0)
                    deaths = player.get('deaths', 0)
                    headshots = player.get('headshots', 0)
                    damage_given = player.get('damage_given', 0)
                    damage_received = player.get('damage_received', 0)
                    accuracy = player.get('accuracy', 0.0)
                    
                    # Calculate derived stats
                    kd_ratio = kills / deaths if deaths > 0 else kills
                    dpm = damage_given / 5.0  # Assume 5 min rounds for now
                    
                    # Extract weapon stats
                    weapon_stats = self.extract_weapon_stats(player)
                    
                    # Insert player round stats
                    await db.execute('''
                        INSERT INTO player_round_stats (
                            session_id, round_id, player_guid, player_clean_name, clean_name_final,
                            kills, deaths, headshots, kd_ratio, accuracy,
                            damage_given, damage_received, dpm,
                            mp40_kills, thompson_kills, fg42_kills, sniper_kills,
                            panzerfaust_kills, grenade_kills,
                            killing_spree_best, kill_assists, multikills_3,
                            round_duration_minutes, team, round_outcome
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        session_id, round_id, guid, raw_name, clean_name,
                        kills, deaths, headshots, kd_ratio, accuracy,
                        damage_given, damage_received, dpm,
                        weapon_stats['mp40_kills'], weapon_stats['thompson_kills'],
                        weapon_stats['fg42_kills'], weapon_stats['sniper_kills'],
                        weapon_stats['panzerfaust_kills'], weapon_stats['grenade_kills'],
                        player.get('killing_spree', 0), player.get('assists', 0), 
                        player.get('multikills', 0),
                        5.0, player.get('team', 0), parsed_data.get('round_outcome', 'unknown')
                    ))
                
                await db.commit()
            
            # Mark file as processed
            await self.mark_file_processed(file_path.name, file_hash)
            
            print(f"   ✅ Processed {len(players)} players")
            return True
            
        except Exception as e:
            print(f"   ❌ Error processing {file_path.name}: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def populate_from_test_files(self):
        """Populate database from all test files"""
        print("🎮 Starting production database population...")
        
        # Initialize database
        await self.initialize_production_database()
        
        # Get all stats files
        test_files_dir = Path("../test_files")
        if not test_files_dir.exists():
            print(f"❌ Test files directory not found: {test_files_dir}")
            return False
        
        stats_files = list(test_files_dir.glob("*.txt"))
        if not stats_files:
            print(f"❌ No stats files found in {test_files_dir}")
            return False
        
        print(f"📁 Found {len(stats_files)} stats files")
        
        # Process files
        successful = 0
        failed = 0
        
        for file_path in sorted(stats_files):
            success = await self.process_stats_file(file_path)
            if success:
                successful += 1
            else:
                failed += 1
        
        print(f"\n📊 Population Summary:")
        print(f"   ✅ Successful: {successful}")
        print(f"   ❌ Failed: {failed}")
        print(f"   📁 Total: {len(stats_files)}")
        
        # Show database stats
        await self.show_database_summary()
        
        return successful > 0

    async def show_database_summary(self):
        """Show summary of populated database"""
        print("\n📊 Database Summary:")
        
        async with aiosqlite.connect(self.db_path) as db:
            # Sessions
            cursor = await db.execute("SELECT COUNT(*) FROM sessions")
            session_count = (await cursor.fetchone())[0]
            
            # Players
            cursor = await db.execute("SELECT COUNT(DISTINCT player_guid) FROM player_round_stats")
            player_count = (await cursor.fetchone())[0]
            
            # Rounds
            cursor = await db.execute("SELECT COUNT(*) FROM player_round_stats")
            round_records = (await cursor.fetchone())[0]
            
            # Top players
            cursor = await db.execute('''
                SELECT clean_name_final, SUM(kills) as total_kills, COUNT(*) as rounds
                FROM player_round_stats
                GROUP BY player_guid
                ORDER BY total_kills DESC
                LIMIT 5
            ''')
            top_players = await cursor.fetchall()
            
            print(f"   📅 Sessions: {session_count}")
            print(f"   👥 Unique Players: {player_count}")
            print(f"   📈 Round Records: {round_records}")
            
            print(f"\n🏆 Top Players:")
            for i, (name, kills, rounds) in enumerate(top_players, 1):
                print(f"   {i}. {name}: {kills} kills ({rounds} rounds)")


async def main():
    """Run production database population"""
    print("🎮 ET:Legacy Production Database Population")
    print("=" * 60)
    
    populator = ProductionDatabasePopulator()
    success = await populator.populate_from_test_files()
    
    if success:
        print("\n🎉 Database population completed successfully!")
        print("✅ Ready for Discord command implementation")
    else:
        print("\n❌ Database population failed")


if __name__ == "__main__":
    asyncio.run(main())
