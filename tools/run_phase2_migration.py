"""
Phase 2 Database Migration Script
Migrates sessions table to rounds table
"""
import sqlite3
import sys

def run_migration():
    print("🚀 Starting Phase 2 Database Migration...")
    print("=" * 60)
    
    try:
        # Connect to database
        conn = sqlite3.connect('bot/etlegacy_production.db')
        cursor = conn.cursor()
        
        # Get initial counts
        cursor.execute("SELECT COUNT(*) FROM sessions")
        initial_sessions = cursor.fetchone()[0]
        print(f"Initial sessions count: {initial_sessions}")
        
        # STEP 1: Create rounds table
        print("\n1️⃣ Creating rounds table...")
        cursor.execute("""
            CREATE TABLE rounds (
                id INTEGER PRIMARY KEY,
                round_date TEXT NOT NULL,
                round_time TEXT NOT NULL,
                match_id TEXT,
                map_name TEXT NOT NULL,
                round_number INTEGER NOT NULL,
                time_limit TEXT,
                actual_time TEXT,
                winner_team INTEGER DEFAULT 0,
                defender_team INTEGER DEFAULT 0,
                is_tied INTEGER DEFAULT 0,
                round_outcome TEXT,
                gaming_session_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(round_date, round_time, map_name, round_number)
            )
        """)
        conn.commit()
        print("   ✅ rounds table created")
        
        # STEP 2: Copy data
        print("\n2️⃣ Copying data from sessions to rounds...")
        cursor.execute("""
            INSERT INTO rounds (
                id, round_date, round_time, match_id, map_name, round_number,
                time_limit, actual_time, winner_team, defender_team, is_tied,
                round_outcome, gaming_session_id, created_at
            )
            SELECT 
                id, session_date, session_time, match_id, map_name, round_number,
                time_limit, actual_time, winner_team, defender_team, is_tied,
                round_outcome, gaming_session_id, created_at
            FROM sessions
        """)
        conn.commit()
        
        cursor.execute("SELECT COUNT(*) FROM rounds")
        rounds_count = cursor.fetchone()[0]
        print(f"   ✅ Copied {rounds_count} records")
        
        if rounds_count != initial_sessions:
            print(f"   ❌ ERROR: Count mismatch! Expected {initial_sessions}, got {rounds_count}")
            return False
        
        # STEP 3: Update player_comprehensive_stats
        print("\n3️⃣ Updating player_comprehensive_stats...")
        cursor.execute("""
            CREATE TABLE player_comprehensive_stats_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                round_id INTEGER NOT NULL,
                round_date TEXT NOT NULL,
                map_name TEXT NOT NULL,
                round_number INTEGER NOT NULL,
                player_guid TEXT NOT NULL,
                player_name TEXT NOT NULL,
                clean_name TEXT NOT NULL,
                team INTEGER,
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
                time_dead_minutes REAL DEFAULT 0,
                time_dead_ratio REAL DEFAULT 0,
                xp INTEGER DEFAULT 0,
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
                tank_meatshield REAL DEFAULT 0,
                double_kills INTEGER DEFAULT 0,
                triple_kills INTEGER DEFAULT 0,
                quad_kills INTEGER DEFAULT 0,
                multi_kills INTEGER DEFAULT 0,
                mega_kills INTEGER DEFAULT 0,
                killing_spree_best INTEGER DEFAULT 0,
                death_spree_worst INTEGER DEFAULT 0,
                created_at TIMESTAMP,
                FOREIGN KEY (round_id) REFERENCES rounds(id),
                UNIQUE(round_id, player_guid)
            )
        """)
        
        cursor.execute("INSERT INTO player_comprehensive_stats_new SELECT * FROM player_comprehensive_stats")
        cursor.execute("DROP TABLE player_comprehensive_stats")
        cursor.execute("ALTER TABLE player_comprehensive_stats_new RENAME TO player_comprehensive_stats")
        conn.commit()
        print("   ✅ player_comprehensive_stats updated")
        
        # STEP 4: Update weapon_comprehensive_stats
        print("\n4️⃣ Updating weapon_comprehensive_stats...")
        cursor.execute("""
            CREATE TABLE weapon_comprehensive_stats_new (
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
                created_at TIMESTAMP,
                FOREIGN KEY (round_id) REFERENCES rounds(id),
                UNIQUE(round_id, player_guid, weapon_name)
            )
        """)
        
        cursor.execute("INSERT INTO weapon_comprehensive_stats_new SELECT * FROM weapon_comprehensive_stats")
        cursor.execute("DROP TABLE weapon_comprehensive_stats")
        cursor.execute("ALTER TABLE weapon_comprehensive_stats_new RENAME TO weapon_comprehensive_stats")
        conn.commit()
        print("   ✅ weapon_comprehensive_stats updated")
        
        # STEP 5: Drop sessions table
        print("\n5️⃣ Dropping old sessions table...")
        cursor.execute("DROP TABLE sessions")
        conn.commit()
        print("   ✅ sessions table dropped")
        
        # STEP 6: Create indexes
        print("\n6️⃣ Creating indexes...")
        cursor.execute("CREATE INDEX idx_rounds_date ON rounds(round_date)")
        cursor.execute("CREATE INDEX idx_rounds_match_id ON rounds(match_id)")
        cursor.execute("CREATE INDEX idx_rounds_gaming_session_id ON rounds(gaming_session_id)")
        cursor.execute("CREATE INDEX idx_rounds_date_time ON rounds(round_date, round_time)")
        cursor.execute("CREATE INDEX idx_player_stats_round ON player_comprehensive_stats(round_id)")
        cursor.execute("CREATE INDEX idx_player_stats_guid ON player_comprehensive_stats(player_guid)")
        cursor.execute("CREATE INDEX idx_player_stats_clean_name ON player_comprehensive_stats(clean_name)")
        cursor.execute("CREATE INDEX idx_players_dpm ON player_comprehensive_stats(dpm DESC)")
        cursor.execute("CREATE INDEX idx_players_kd ON player_comprehensive_stats(kd_ratio DESC)")
        cursor.execute("CREATE INDEX idx_weapon_stats_round ON weapon_comprehensive_stats(round_id)")
        cursor.execute("CREATE INDEX idx_weapons_player ON weapon_comprehensive_stats(player_guid)")
        conn.commit()
        print("   ✅ All indexes created")
        
        # Final verification
        print("\n" + "=" * 60)
        print("📊 FINAL VERIFICATION")
        print("=" * 60)
        
        cursor.execute("SELECT COUNT(*) FROM rounds")
        print(f"Rounds: {cursor.fetchone()[0]}")
        
        cursor.execute("SELECT COUNT(*) FROM player_comprehensive_stats")
        print(f"Player stats: {cursor.fetchone()[0]}")
        
        cursor.execute("SELECT COUNT(*) FROM weapon_comprehensive_stats")
        print(f"Weapon stats: {cursor.fetchone()[0]}")
        
        cursor.execute("""
            SELECT COUNT(DISTINCT gaming_session_id) 
            FROM rounds 
            WHERE gaming_session_id IS NOT NULL
        """)
        print(f"Gaming sessions: {cursor.fetchone()[0]}")
        
        # Check for orphans
        cursor.execute("""
            SELECT COUNT(*) FROM player_comprehensive_stats p
            LEFT JOIN rounds r ON p.round_id = r.id
            WHERE r.id IS NULL
        """)
        orphan_players = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM weapon_comprehensive_stats w
            LEFT JOIN rounds r ON w.round_id = r.id
            WHERE r.id IS NULL
        """)
        orphan_weapons = cursor.fetchone()[0]
        
        if orphan_players > 0 or orphan_weapons > 0:
            print(f"\n❌ ORPHANED DATA FOUND!")
            print(f"   Orphan player stats: {orphan_players}")
            print(f"   Orphan weapon stats: {orphan_weapons}")
            return False
        
        print("\n✅ No orphaned data")
        
        conn.close()
        
        print("\n" + "=" * 60)
        print("🎉 PHASE 2 DATABASE MIGRATION COMPLETE!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n❌ MIGRATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
