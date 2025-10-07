"""
Create session_teams table for tracking hardcoded team rosters.

This table stores the actual player team compositions (e.g., Team A vs Team B)
separate from their in-game Axis/Allies assignments which swap every round.
"""

import sqlite3
import os


def create_session_teams_table():
    """Create the session_teams table in etlegacy_production.db"""
    
    db_path = "etlegacy_production.db"
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return False
    
    print(f"📊 Connecting to database: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create session_teams table
    print("\n🔨 Creating session_teams table...")
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS session_teams (
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
    
    # Create indexes for performance
    print("📇 Creating indexes...")
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_session_teams_date 
        ON session_teams(session_start_date)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_session_teams_map 
        ON session_teams(map_name)
    ''')
    
    conn.commit()
    
    # Verify table creation
    print("\n✅ Verifying table structure...")
    cursor.execute("PRAGMA table_info(session_teams)")
    columns = cursor.fetchall()
    
    print(f"   Found {len(columns)} columns:")
    for col in columns:
        col_id, col_name, col_type, not_null, default_val, pk = col
        pk_str = " (PRIMARY KEY)" if pk else ""
        not_null_str = " NOT NULL" if not_null else ""
        print(f"     • {col_name}: {col_type}{not_null_str}{pk_str}")
    
    # Check indexes
    print("\n✅ Verifying indexes...")
    cursor.execute('''
        SELECT name FROM sqlite_master 
        WHERE type='index' AND tbl_name='session_teams'
    ''')
    indexes = cursor.fetchall()
    print(f"   Found {len(indexes)} indexes:")
    for idx in indexes:
        print(f"     • {idx[0]}")
    
    conn.close()
    
    print("\n🎉 session_teams table created successfully!")
    print("\nTable Schema:")
    print("  - session_start_date: TEXT (timestamp of first round)")
    print("  - map_name: TEXT (e.g., 'etl_adlernest')")
    print("  - team_name: TEXT ('Team A' or 'Team B')")
    print("  - player_guids: TEXT (JSON array of GUIDs)")
    print("  - player_names: TEXT (JSON array of player names)")
    print("  - created_at: TIMESTAMP (auto)")
    
    return True


if __name__ == "__main__":
    print("=" * 80)
    print("🎮 ET:Legacy - Create session_teams Table")
    print("=" * 80)
    print()
    
    success = create_session_teams_table()
    
    if success:
        print("\n✅ Database schema updated successfully!")
        print("Next step: Run populate_session_teams.py to add October 2nd data")
    else:
        print("\n❌ Failed to create table")
