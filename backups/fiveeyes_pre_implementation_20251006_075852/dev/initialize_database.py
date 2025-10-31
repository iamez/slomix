#!/usr/bin/env python3
"""
Properly Initialize and Populate Comprehensive Database
Creates the comprehensive database schema and populates with test data for Discord testing
"""

import sqlite3
import os
from datetime import datetime, date, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('DatabaseInit')

def initialize_comprehensive_database():
    """Initialize the comprehensive database with all tables"""
    
    db_path = "dev/etlegacy_comprehensive.db"
    
    # Remove existing database if it exists
    if os.path.exists(db_path):
        os.remove(db_path)
        logger.info(f"🗑️ Removed existing database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    logger.info("🏗️ Creating comprehensive database schema...")
    
    # Sessions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_date DATE NOT NULL,
            map_name TEXT NOT NULL,
            round_number INTEGER NOT NULL,
            server_name TEXT,
            config_name TEXT,
            defender_team INTEGER,
            winner_team INTEGER,
            time_limit TEXT,
            next_time_limit TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Comprehensive player stats - captures EVERYTHING from C0RNP0RN3.lua
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_comprehensive_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            player_guid TEXT NOT NULL,
            player_name TEXT NOT NULL,
            clean_name TEXT NOT NULL,
            team INTEGER NOT NULL,
            rounds INTEGER DEFAULT 0,
            
            -- Basic combat stats
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
            
            -- Time and XP
            time_axis INTEGER DEFAULT 0,
            time_allies INTEGER DEFAULT 0,
            time_played REAL DEFAULT 0.0,
            time_played_minutes REAL DEFAULT 0.0,
            xp INTEGER DEFAULT 0,
            
            -- Advanced analytics from topshots array
            killing_spree_best INTEGER DEFAULT 0,          -- topshots[1]
            death_spree_worst INTEGER DEFAULT 0,           -- topshots[2]
            kill_assists INTEGER DEFAULT 0,               -- topshots[3]
            kill_steals INTEGER DEFAULT 0,                -- topshots[4]
            headshot_kills INTEGER DEFAULT 0,             -- topshots[5]
            objectives_stolen INTEGER DEFAULT 0,          -- topshots[6]
            objectives_returned INTEGER DEFAULT 0,        -- topshots[7]
            dynamites_planted INTEGER DEFAULT 0,          -- topshots[8]
            dynamites_defused INTEGER DEFAULT 0,          -- topshots[9]
            times_revived INTEGER DEFAULT 0,              -- topshots[10]
            bullets_fired INTEGER DEFAULT 0,              -- topshots[11]
            dpm REAL DEFAULT 0.0,                         -- topshots[12]
            tank_meatshield REAL DEFAULT 0.0,            -- topshots[13]
            time_dead_ratio REAL DEFAULT 0.0,            -- topshots[14]
            most_useful_kills INTEGER DEFAULT 0,          -- topshots[15]
            denied_playtime INTEGER DEFAULT 0,            -- topshots[16] (ms)
            useless_kills INTEGER DEFAULT 0,              -- topshots[17]
            full_selfkills INTEGER DEFAULT 0,             -- topshots[18]
            repairs_constructions INTEGER DEFAULT 0,      -- topshots[19]
            
            -- Multikills from multikills array
            double_kills INTEGER DEFAULT 0,               -- multikills[1]
            triple_kills INTEGER DEFAULT 0,               -- multikills[2]
            quad_kills INTEGER DEFAULT 0,                 -- multikills[3]
            multi_kills INTEGER DEFAULT 0,                -- multikills[4]
            mega_kills INTEGER DEFAULT 0,                 -- multikills[5]
            ultra_kills INTEGER DEFAULT 0,                -- multikills[6]
            monster_kills INTEGER DEFAULT 0,              -- multikills[7]
            ludicrous_kills INTEGER DEFAULT 0,            -- multikills[8]
            holy_shit_kills INTEGER DEFAULT 0,            -- multikills[9]
            
            -- Calculated fields
            kd_ratio REAL DEFAULT 0.0,
            accuracy REAL DEFAULT 0.0,
            headshot_ratio REAL DEFAULT 0.0,
            
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions (id)
        )
    ''')
    
    # Weapon comprehensive stats - ALL 28 weapons from C0RNP0RN3.lua
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS weapon_comprehensive_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            player_guid TEXT NOT NULL,
            weapon_id INTEGER NOT NULL,
            weapon_name TEXT NOT NULL,
            kills INTEGER DEFAULT 0,
            deaths INTEGER DEFAULT 0,
            hits INTEGER DEFAULT 0,
            shots INTEGER DEFAULT 0,
            headshots INTEGER DEFAULT 0,
            accuracy REAL DEFAULT 0.0,
            headshot_ratio REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions (id)
        )
    ''')
    
    # Player links for Discord integration
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_guid TEXT UNIQUE NOT NULL,
            discord_id TEXT UNIQUE NOT NULL,
            discord_username TEXT,
            player_name TEXT,
            linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    logger.info("✅ Comprehensive database schema created successfully")
    
    return conn, cursor

def populate_test_data():
    """Populate with realistic test data including all C0RNP0RN3.lua fields"""
    
    conn, cursor = initialize_comprehensive_database()
    
    logger.info("🎯 Creating realistic test data for Discord commands...")
    
    # Create test sessions for the last few days
    test_dates = [
        (date.today() - timedelta(days=2), 'et_supply', 1),
        (date.today() - timedelta(days=2), 'et_supply', 2),
        (date.today() - timedelta(days=1), 'et_goldrush', 1),
        (date.today() - timedelta(days=1), 'et_goldrush', 2),
        (date.today(), 'etl_adlernest', 1),
    ]
    
    session_ids = []
    for session_date, map_name, round_num in test_dates:
        cursor.execute("""
            INSERT OR REPLACE INTO sessions 
            (session_date, map_name, round_number, server_name, config_name, 
             defender_team, winner_team, time_limit, next_time_limit)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_date.isoformat(), map_name, round_num, 
            'ET:Legacy Community Server', 'etpub',
            1 if round_num == 1 else 2,  # Defender team
            2 if round_num == 1 else 1,  # Winner team (opposite)
            '20:00', '20:00'
        ))
        session_ids.append(cursor.lastrowid)
    
    logger.info(f"✅ Created {len(session_ids)} test sessions")
    
    # Create test players with different skill levels
    test_players = [
        ('GUID001', 'seareal', 'seareal', 2, 85),  # High skill 
        ('GUID002', 'zebra', 'zebra', 1, 75),     # Good skill
        ('GUID003', 'KaNii', 'KaNii', 2, 70),     # Decent skill
        ('GUID004', 'NewPlayer', 'NewPlayer', 1, 45),  # Low skill
        ('GUID005', 'OldSchool', 'OldSchool', 2, 90),  # Very high skill
    ]
    
    # Add realistic comprehensive stats for each player across sessions
    for session_id in session_ids:
        for guid, name, clean_name, team, skill_level in test_players:
            
            # Base stats scaled by skill level
            base_kills = int(25 * (skill_level / 100))
            base_deaths = int(20 * (100 - skill_level) / 100)
            base_damage = base_kills * 85
            
            # Advanced stats from C0RNP0RN3.lua topshots array
            cursor.execute("""
                INSERT INTO player_comprehensive_stats (
                    session_id, player_guid, player_name, clean_name, team,
                    kills, deaths, damage_given, damage_received,
                    killing_spree_best, death_spree_worst, kill_assists, kill_steals,
                    headshot_kills, objectives_stolen, objectives_returned,
                    dynamites_planted, dynamites_defused, times_revived,
                    bullets_fired, dpm, tank_meatshield, time_dead_ratio,
                    most_useful_kills, denied_playtime, useless_kills,
                    double_kills, triple_kills, quad_kills,
                    kd_ratio, accuracy, headshot_ratio,
                    time_played_minutes, xp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id, guid, name, clean_name, team,
                base_kills, base_deaths, base_damage, base_damage // 2,
                # Advanced topshots analytics
                max(3, base_kills // 5),  # killing_spree_best
                max(1, base_deaths // 8), # death_spree_worst
                base_kills // 3,          # kill_assists
                base_kills // 10,         # kill_steals
                base_kills // 4,          # headshot_kills
                2 if skill_level > 70 else 1,  # objectives_stolen
                1 if skill_level > 60 else 0,  # objectives_returned
                2 if skill_level > 65 else 1,  # dynamites_planted
                1 if skill_level > 70 else 0,  # dynamites_defused
                base_deaths // 3,         # times_revived
                base_kills * 15,          # bullets_fired
                base_damage / 15.0,       # dpm (damage per minute)
                50.0 + skill_level,       # tank_meatshield
                (100 - skill_level) / 100.0,  # time_dead_ratio
                base_kills // 2,          # most_useful_kills
                base_deaths * 15000,      # denied_playtime (ms)
                max(0, base_kills // 8),  # useless_kills
                # Multikills
                base_kills // 6 if skill_level > 60 else 0,  # double_kills
                base_kills // 12 if skill_level > 70 else 0, # triple_kills
                1 if skill_level > 80 else 0,                # quad_kills
                # Calculated ratios
                base_kills / max(1, base_deaths),  # kd_ratio
                min(35.0, 15.0 + skill_level / 5),  # accuracy
                25.0 + skill_level / 10,  # headshot_ratio
                15.0,  # time_played_minutes
                base_kills * 50  # xp
            ))
    
    # Create weapon stats for all 28 C0RNP0RN3.lua weapons
    weapons = [
        (0, "WS_KNIFE"), (1, "WS_KNIFE_KBAR"), (2, "WS_LUGER"), (3, "WS_COLT"),
        (4, "WS_MP40"), (5, "WS_THOMPSON"), (6, "WS_STEN"), (7, "WS_FG42"),
        (8, "WS_PANZERFAUST"), (9, "WS_BAZOOKA"), (10, "WS_FLAMETHROWER"),
        (11, "WS_GRENADE"), (12, "WS_MORTAR"), (13, "WS_MORTAR2"),
        (14, "WS_DYNAMITE"), (15, "WS_AIRSTRIKE"), (16, "WS_ARTILLERY"),
        (17, "WS_SATCHEL"), (18, "WS_GRENADELAUNCHER"), (19, "WS_LANDMINE"),
        (20, "WS_MG42"), (21, "WS_BROWNING"), (22, "WS_CARBINE"),
        (23, "WS_KAR98"), (24, "WS_GARAND"), (25, "WS_K43"),
        (26, "WS_MP34"), (27, "WS_SYRINGE")
    ]
    
    weapon_stats_count = 0
    for session_id in session_ids:
        for guid, name, clean_name, team, skill_level in test_players:
            # Add stats for primary weapons based on team and skill
            primary_weapons = [(4, "WS_MP40"), (5, "WS_THOMPSON"), (7, "WS_FG42")] 
            
            for weapon_id, weapon_name in primary_weapons:
                kills = max(1, int(10 * skill_level / 100))
                shots = kills * 8
                hits = int(shots * (skill_level / 200))  # Skill-based accuracy
                
                cursor.execute("""
                    INSERT INTO weapon_comprehensive_stats 
                    (session_id, player_guid, weapon_id, weapon_name, kills, hits, shots, headshots, accuracy, headshot_ratio)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id, guid, weapon_id, weapon_name,
                    kills, hits, shots, max(1, kills // 4),
                    (hits / shots * 100) if shots > 0 else 0,
                    25.0 if kills > 0 else 0
                ))
                weapon_stats_count += 1
    
    # Create Discord player links for testing @mentions
    test_links = [
        ('GUID001', '231165917604741121', 'seareal#1234'),  # seareal
        ('GUID002', '688065923839688794', 'zebra#5678'),    # zebra  
        ('GUID003', '1276520122302861475', 'KaNii#9012'),   # KaNii
        ('GUID005', '509737538555084810', 'vid#3456'),      # OldSchool -> vid from your list
    ]
    
    for guid, discord_id, discord_username in test_links:
        cursor.execute("""
            INSERT OR REPLACE INTO player_links (player_guid, discord_id, discord_username, player_name)
            VALUES (?, ?, ?, ?)
        """, (guid, discord_id, discord_username, discord_username.split('#')[0]))
    
    conn.commit()
    conn.close()
    
    # Get final counts
    conn = sqlite3.connect("dev/etlegacy_comprehensive.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM sessions")
    session_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM player_comprehensive_stats")
    player_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM weapon_comprehensive_stats")
    weapon_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM player_links")
    link_count = cursor.fetchone()[0]
    
    conn.close()
    
    logger.info("📊 Test Data Summary:")
    logger.info(f"   Sessions: {session_count}")
    logger.info(f"   Player stats records: {player_count}")
    logger.info(f"   Weapon stats records: {weapon_count}")
    logger.info(f"   Player links: {link_count}")
    logger.info("")
    logger.info("🎮 Test Discord Commands:")
    logger.info("   !stats seareal")
    logger.info("   !stats @seareal")
    logger.info("   !stats seareal 02.10.2025")
    logger.info("   !session_stats 02.10")
    logger.info("   !link NewPlayer")
    logger.info("🎉 Test data created successfully!")
    logger.info("💡 You can now test Discord commands!")

if __name__ == "__main__":
    populate_test_data()