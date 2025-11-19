#!/usr/bin/env python3
"""
Quick fix to create PostgreSQL schema
Run this on VPS before using postgresql_database_manager.py
"""

import asyncio
import asyncpg
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from bot.config import load_config

async def create_schema():
    config = load_config()
    
    print("🔧 Creating PostgreSQL schema...")
    print(f"   Database: {config.postgres_database}")
    print(f"   User: {config.postgres_user}")
    
    # Connect to PostgreSQL
    conn = await asyncpg.connect(
        host=config.postgres_host.split(':')[0],
        port=int(config.postgres_port),
        database=config.postgres_database,
        user=config.postgres_user,
        password=config.postgres_password
    )
    
    try:
        # 1. Rounds table
        print("   Creating rounds table...")
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS rounds (
                id SERIAL PRIMARY KEY,
                match_id BIGINT,
                round_number INTEGER,
                round_date TEXT,
                round_time TEXT,
                map_name TEXT,
                defender_team INTEGER DEFAULT 0,
                winner_team INTEGER DEFAULT 0,
                is_tied BOOLEAN DEFAULT FALSE,
                round_outcome TEXT,
                gaming_session_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(match_id, round_number)
            )
        ''')
        
        # 2. Player comprehensive stats
        print("   Creating player_comprehensive_stats table...")
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS player_comprehensive_stats (
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
                time_played_seconds INTEGER DEFAULT 0,
                time_played_minutes REAL DEFAULT 0,
                time_axis INTEGER DEFAULT 0,
                time_allies INTEGER DEFAULT 0,
                bullets_fired INTEGER DEFAULT 0,
                bullets_hit INTEGER DEFAULT 0,
                accuracy REAL DEFAULT 0,
                revives_given INTEGER DEFAULT 0,
                revives_received INTEGER DEFAULT 0,
                ammopacks_given INTEGER DEFAULT 0,
                healthpacks_given INTEGER DEFAULT 0,
                poisoned INTEGER DEFAULT 0,
                knife_kills INTEGER DEFAULT 0,
                knife_deaths INTEGER DEFAULT 0,
                dyn_planted INTEGER DEFAULT 0,
                dyn_defused INTEGER DEFAULT 0,
                obj_captured INTEGER DEFAULT 0,
                obj_destroyed INTEGER DEFAULT 0,
                obj_returned INTEGER DEFAULT 0,
                obj_taken INTEGER DEFAULT 0,
                xp REAL DEFAULT 0,
                kd_ratio REAL DEFAULT 0,
                dpm REAL DEFAULT 0,
                efficiency REAL DEFAULT 0,
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
        print("   Creating weapon_comprehensive_stats table...")
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS weapon_comprehensive_stats (
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
        print("   Creating processed_files table...")
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS processed_files (
                id SERIAL PRIMARY KEY,
                filename TEXT UNIQUE NOT NULL,
                file_hash TEXT,
                success BOOLEAN DEFAULT TRUE,
                error_message TEXT,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 5. Session teams
        print("   Creating session_teams table...")
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS session_teams (
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
        print("   Creating player_links table...")
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS player_links (
                id SERIAL PRIMARY KEY,
                player_guid TEXT UNIQUE NOT NULL,
                discord_id BIGINT UNIQUE NOT NULL,
                discord_username TEXT,
                player_name TEXT,
                linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 7. Player aliases
        print("   Creating player_aliases table...")
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS player_aliases (
                id SERIAL PRIMARY KEY,
                guid TEXT NOT NULL,
                alias TEXT NOT NULL,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(guid, alias)
            )
        ''')
        
        # Create indexes
        print("   Creating indexes...")
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_rounds_date ON rounds(round_date)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_player_stats_round ON player_comprehensive_stats(round_id)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_player_stats_guid ON player_comprehensive_stats(player_guid)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_weapon_stats_round ON weapon_comprehensive_stats(round_id)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_processed_files_filename ON processed_files(filename)')
        
        print("✅ Schema created successfully!")
        
    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(create_schema())
