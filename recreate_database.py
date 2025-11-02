"""#!/usr/bin/env python3

Complete Database Recreation Script"""

Creates fresh database with correct schema and imports all stat filesRecreate the database from scratch and import all stats files.

"""Run this AFTER manually deleting etlegacy_production.db

import sqlite3"""

import asyncio

import sysimport os

from pathlib import Pathimport sqlite3

from datetime import datetime

DB_PATH = "etlegacy_production.db"

sys.path.insert(0, str(Path(__file__).parent / 'bot'))

from community_stats_parser import C0RNP0RN3StatsParser

def create_database_schema():

    """Create all tables with proper schema"""

def create_fresh_database(db_path='bot/etlegacy_production_NEW.db'):    print("Creating database schema...")

    """Create a brand new database with correct schema"""

        conn = sqlite3.connect(DB_PATH)

    # Remove old database if exists    cursor = conn.cursor()

    if Path(db_path).exists():

        Path(db_path).unlink()    # Create sessions table (matches import script)

        print(f"Removed old database: {db_path}")    cursor.execute(

            '''

    conn = sqlite3.connect(db_path)        CREATE TABLE IF NOT EXISTS sessions (

    cursor = conn.cursor()            id INTEGER PRIMARY KEY AUTOINCREMENT,

                session_date TEXT NOT NULL,

    print("Creating tables with correct schema...")            map_name TEXT NOT NULL,

                round_number INTEGER NOT NULL,

    # Sessions table with 3 time columns            time_limit TEXT,

    cursor.execute("""            actual_time TEXT,

        CREATE TABLE sessions (            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

            id INTEGER PRIMARY KEY AUTOINCREMENT,        )

            session_date TEXT NOT NULL,    '''

            map_name TEXT NOT NULL,    )

            round_number INTEGER NOT NULL,

            defender_team INTEGER,    # Create player_comprehensive_stats table (matches import script columns)

            winner_team INTEGER,    cursor.execute(

            time_limit TEXT,        '''

            actual_time TEXT,        CREATE TABLE IF NOT EXISTS player_comprehensive_stats (

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,            id INTEGER PRIMARY KEY AUTOINCREMENT,

            map_id INTEGER,            session_id INTEGER NOT NULL,

            original_time_limit TEXT,            session_date TEXT NOT NULL,

            time_to_beat TEXT,            map_name TEXT NOT NULL,

            completion_time TEXT,            round_number INTEGER NOT NULL,

            UNIQUE(session_date, map_name, round_number)            player_guid TEXT,

        )            player_name TEXT NOT NULL,

    """)            clean_name TEXT,

    print("  ✅ sessions table created")            team INTEGER,

                kills INTEGER DEFAULT 0,

    # Player comprehensive stats with ALL fixed field names            deaths INTEGER DEFAULT 0,

    cursor.execute("""            damage_given INTEGER DEFAULT 0,

        CREATE TABLE player_comprehensive_stats (            damage_received INTEGER DEFAULT 0,

            id INTEGER PRIMARY KEY AUTOINCREMENT,            team_damage_given INTEGER DEFAULT 0,

            session_id INTEGER NOT NULL,            team_damage_received INTEGER DEFAULT 0,

            session_date TEXT NOT NULL,            gibs INTEGER DEFAULT 0,

            map_name TEXT NOT NULL,            self_kills INTEGER DEFAULT 0,

            round_number INTEGER NOT NULL,            team_kills INTEGER DEFAULT 0,

            player_guid TEXT NOT NULL,            team_gibs INTEGER DEFAULT 0,

            player_name TEXT NOT NULL,            time_played_seconds INTEGER DEFAULT 0,

            clean_name TEXT,            time_played_minutes REAL DEFAULT 0.0,

            team INTEGER,            time_display TEXT,

            kills INTEGER DEFAULT 0,            xp INTEGER DEFAULT 0,

            deaths INTEGER DEFAULT 0,            dpm REAL DEFAULT 0.0,

            damage_given INTEGER DEFAULT 0,            kd_ratio REAL DEFAULT 0.0,

            damage_received INTEGER DEFAULT 0,            killing_spree_best INTEGER DEFAULT 0,

            team_damage_given INTEGER DEFAULT 0,            death_spree_worst INTEGER DEFAULT 0,

            team_damage_received INTEGER DEFAULT 0,            kill_assists INTEGER DEFAULT 0,

            gibs INTEGER DEFAULT 0,            kill_steals INTEGER DEFAULT 0,

            self_kills INTEGER DEFAULT 0,            headshot_kills INTEGER DEFAULT 0,

            team_kills INTEGER DEFAULT 0,            objectives_stolen INTEGER DEFAULT 0,

            team_gibs INTEGER DEFAULT 0,            objectives_returned INTEGER DEFAULT 0,

            headshot_kills INTEGER DEFAULT 0,            dynamites_planted INTEGER DEFAULT 0,

            time_played_seconds INTEGER DEFAULT 0,            dynamites_defused INTEGER DEFAULT 0,

            time_played_minutes REAL DEFAULT 0,            times_revived INTEGER DEFAULT 0,

            time_dead_minutes REAL DEFAULT 0,            revives_given INTEGER DEFAULT 0,

            time_dead_ratio REAL DEFAULT 0,            bullets_fired INTEGER DEFAULT 0,

            xp INTEGER DEFAULT 0,            tank_meatshield INTEGER DEFAULT 0,

            kd_ratio REAL DEFAULT 0,            time_dead_ratio REAL DEFAULT 0.0,

            dpm REAL DEFAULT 0,            most_useful_kills INTEGER DEFAULT 0,

            efficiency REAL DEFAULT 0,            denied_playtime INTEGER DEFAULT 0,

            bullets_fired INTEGER DEFAULT 0,            useless_kills INTEGER DEFAULT 0,

            accuracy REAL DEFAULT 0,            full_selfkills INTEGER DEFAULT 0,

            kill_assists INTEGER DEFAULT 0,            repairs_constructions INTEGER DEFAULT 0,

            objectives_completed INTEGER DEFAULT 0,            double_kills INTEGER DEFAULT 0,

            objectives_destroyed INTEGER DEFAULT 0,            triple_kills INTEGER DEFAULT 0,

            objectives_stolen INTEGER DEFAULT 0,            quad_kills INTEGER DEFAULT 0,

            objectives_returned INTEGER DEFAULT 0,            multi_kills INTEGER DEFAULT 0,

            dynamites_planted INTEGER DEFAULT 0,            mega_kills INTEGER DEFAULT 0,

            dynamites_defused INTEGER DEFAULT 0,            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            times_revived INTEGER DEFAULT 0,            FOREIGN KEY (session_id) REFERENCES sessions(id)

            revives_given INTEGER DEFAULT 0,        )

            most_useful_kills INTEGER DEFAULT 0,    '''

            useless_kills INTEGER DEFAULT 0,    )

            kill_steals INTEGER DEFAULT 0,

            denied_playtime INTEGER DEFAULT 0,    # Create weapon_comprehensive_stats table

            constructions INTEGER DEFAULT 0,    cursor.execute(

            tank_meatshield REAL DEFAULT 0,        '''

            double_kills INTEGER DEFAULT 0,        CREATE TABLE IF NOT EXISTS weapon_comprehensive_stats (

            triple_kills INTEGER DEFAULT 0,            id INTEGER PRIMARY KEY AUTOINCREMENT,

            quad_kills INTEGER DEFAULT 0,            session_id INTEGER NOT NULL,

            multi_kills INTEGER DEFAULT 0,            session_date TEXT NOT NULL,

            mega_kills INTEGER DEFAULT 0,            map_name TEXT NOT NULL,

            killing_spree_best INTEGER DEFAULT 0,            round_number INTEGER NOT NULL,

            death_spree_worst INTEGER DEFAULT 0,            player_guid TEXT,

            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE            player_name TEXT NOT NULL,

        )            weapon_name TEXT NOT NULL,

    """)            kills INTEGER DEFAULT 0,

    print("  ✅ player_comprehensive_stats table created")            deaths INTEGER DEFAULT 0,

                headshots INTEGER DEFAULT 0,

    # Weapon stats table            hits INTEGER DEFAULT 0,

    cursor.execute("""            shots INTEGER DEFAULT 0,

        CREATE TABLE weapon_comprehensive_stats (            accuracy REAL DEFAULT 0.0,

            id INTEGER PRIMARY KEY AUTOINCREMENT,            damage_given INTEGER DEFAULT 0,

            session_id INTEGER NOT NULL,            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            session_date TEXT,            FOREIGN KEY (session_id) REFERENCES sessions(id)

            map_name TEXT,        )

            round_number INTEGER,    '''

            player_guid TEXT NOT NULL,    )

            player_name TEXT,

            weapon_name TEXT NOT NULL,    # Create player_links table (for Discord linking)

            kills INTEGER DEFAULT 0,    cursor.execute(

            deaths INTEGER DEFAULT 0,        '''

            headshots INTEGER DEFAULT 0,        CREATE TABLE IF NOT EXISTS player_links (

            hits INTEGER DEFAULT 0,            player_guid TEXT PRIMARY KEY,

            shots INTEGER DEFAULT 0,            player_name TEXT NOT NULL,

            accuracy REAL DEFAULT 0,            discord_id TEXT UNIQUE,

            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        )            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    """)        )

    print("  ✅ weapon_comprehensive_stats table created")    '''

        )

    # Player aliases table (for !stats command)

    cursor.execute("""    # Create indices for better query performance

        CREATE TABLE IF NOT EXISTS player_aliases (    cursor.execute(

            id INTEGER PRIMARY KEY AUTOINCREMENT,        '''

            guid TEXT NOT NULL,        CREATE INDEX IF NOT EXISTS idx_sessions_date

            alias TEXT NOT NULL,        ON sessions(session_date)

            first_seen TEXT,    '''

            last_seen TEXT,    )

            times_seen INTEGER DEFAULT 1,

            UNIQUE(guid, alias)    cursor.execute(

        )        '''

    """)        CREATE INDEX IF NOT EXISTS idx_player_stats_session

    print("  ✅ player_aliases table created")        ON player_comprehensive_stats(session_id)

        '''

    # Create indexes for performance    )

    cursor.execute("CREATE INDEX idx_sessions_date ON sessions(session_date)")

    cursor.execute("CREATE INDEX idx_player_stats_session ON player_comprehensive_stats(session_id)")    cursor.execute(

    cursor.execute("CREATE INDEX idx_player_stats_guid ON player_comprehensive_stats(player_guid)")        '''

    cursor.execute("CREATE INDEX idx_weapon_stats_session ON weapon_comprehensive_stats(session_id)")        CREATE INDEX IF NOT EXISTS idx_player_stats_name

    cursor.execute("CREATE INDEX idx_player_aliases_guid ON player_aliases(guid)")        ON player_comprehensive_stats(player_name)

    print("  ✅ Indexes created")    '''

        )

    conn.commit()

    conn.close()    cursor.execute(

            '''

    print(f"\n✅ Database created: {db_path}")        CREATE INDEX IF NOT EXISTS idx_weapon_stats_session

    return db_path        ON weapon_comprehensive_stats(session_id)

    '''

    )

async def import_all_stats(db_path, stats_dir='local_stats'):

    """Import all stat files"""    cursor.execute(

            '''

    parser = C0RNP0RN3StatsParser()        CREATE INDEX IF NOT EXISTS idx_weapon_stats_player

    stat_files = sorted(Path(stats_dir).glob('*.txt'))        ON weapon_comprehensive_stats(player_name)

        '''

    print(f"\nFound {len(stat_files)} stat files")    )

    

    import aiosqlite    conn.commit()

    db = await aiosqlite.connect(db_path)    conn.close()

    

    imported = 0    print("✅ Database schema created successfully!")

    failed = 0

    

    for stat_file in stat_files:def main():

        filename = stat_file.name    """Main execution"""

            if os.path.exists(DB_PATH):

        # Parse filename        print(f"❌ ERROR: {DB_PATH} already exists!")

        try:        print(f"Please delete it manually first:")

            parts = filename.replace('.txt', '').split('-')        print(f"   del {DB_PATH}")

            session_date = '-'.join(parts[:5])        return

            map_name = '-'.join(parts[5:-2])

            round_num = int(parts[-1])    print(f"Creating fresh database: {DB_PATH}")

        except:    create_database_schema()

            print(f"⏭️  {filename} - bad format")

            continue    print("\n" + "=" * 60)

            print("✅ DATABASE CREATED SUCCESSFULLY!")

        # Parse file    print("=" * 60)

        result = parser.parse_stats_file(str(stat_file))    print("\nNext step: Import all stats files")

        if not result or 'players' not in result:    print("Run: python tools/simple_bulk_import.py local_stats")

            failed += 1

            continue

        if __name__ == "__main__":

        # Insert session    main()

        try:
            await db.execute("""
                INSERT INTO sessions (
                    session_date, map_name, round_number, 
                    defender_team, winner_team,
                    original_time_limit, time_to_beat, completion_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_date, map_name, round_num,
                result.get('defender_team', 0), result.get('winner_team', 0),
                result.get('original_time_limit', ''),
                result.get('time_to_beat', ''),
                result.get('completion_time', ''),
            ))
            
            cursor = await db.execute("SELECT last_insert_rowid()")
            row = await cursor.fetchone()
            session_id = row[0]
            
        except:
            continue
        
        # Insert players with FIXED mappings
        for player in result.get('players', []):
            obj_stats = player.get('objective_stats', {})
            time_seconds = player.get('time_played_seconds', 0)
            
            await db.execute("""
                INSERT INTO player_comprehensive_stats (
                    session_id, session_date, map_name, round_number,
                    player_guid, player_name, team, kills, deaths,
                    damage_given, damage_received,
                    team_damage_given, team_damage_received,
                    gibs, self_kills, team_kills, team_gibs, headshot_kills,
                    time_played_seconds, xp, kd_ratio, dpm, bullets_fired,
                    most_useful_kills, constructions,
                    double_kills, triple_kills, quad_kills, multi_kills, mega_kills
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id, session_date, map_name, round_num,
                player.get('guid', '')[:8], player.get('name', ''),
                player.get('team', 0), player.get('kills', 0), player.get('deaths', 0),
                player.get('damage_given', 0), player.get('damage_received', 0),
                obj_stats.get('team_damage_given', 0),      # ✅ FIXED
                obj_stats.get('team_damage_received', 0),   # ✅ FIXED
                obj_stats.get('gibs', 0), obj_stats.get('self_kills', 0),
                obj_stats.get('team_kills', 0), obj_stats.get('team_gibs', 0),
                obj_stats.get('headshot_kills', 0),         # ✅ FIXED
                time_seconds, obj_stats.get('xp', 0),
                player.get('kd_ratio', 0), player.get('dpm', 0),
                obj_stats.get('bullets_fired', 0),
                obj_stats.get('useful_kills', 0),           # ✅ FIXED
                obj_stats.get('repairs_constructions', 0),  # ✅ FIXED
                obj_stats.get('multikill_2x', 0),           # ✅ FIXED
                obj_stats.get('multikill_3x', 0),
                obj_stats.get('multikill_4x', 0),
                obj_stats.get('multikill_5x', 0),
                obj_stats.get('multikill_6x', 0),
            ))
        
        await db.commit()
        imported += 1
        
        if imported % 100 == 0:
            print(f"   {imported}/{len(stat_files)}...")
    
    await db.close()
    print(f"\n✅ Imported {imported}/{len(stat_files)}")
    return imported


async def verify(db_path):
    """Verify SuperBoyy"""
    import aiosqlite
    db = await aiosqlite.connect(db_path)
    
    cursor = await db.execute("""
        SELECT team_damage_given, team_damage_received, headshot_kills, most_useful_kills, double_kills
        FROM player_comprehensive_stats
        WHERE session_date LIKE '2025-10-28-212120%' AND player_name LIKE '%SuperBoyy%'
    """)
    
    row = await cursor.fetchone()
    await db.close()
    
    if row and row[0] == 85 and row[1] == 18 and row[2] == 4:
        print("\n🎉 VERIFIED! All fixes working!")
        return True
    return False


async def main():
    print("Creating fresh database...")
    db_path = create_fresh_database()
    
    print("\nImporting all stats...")
    await import_all_stats(db_path)
    
    print("\nVerifying...")
    await verify(db_path)
    
    print("\n✅ DONE! New database: bot/etlegacy_production_NEW.db")


if __name__ == '__main__':
    asyncio.run(main())
