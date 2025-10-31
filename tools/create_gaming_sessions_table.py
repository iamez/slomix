#!/usr/bin/env python3
"""
Create gaming_sessions table for voice channel session tracking
"""

import sqlite3
import sys

DB_PATH = 'etlegacy_production.db'

def create_gaming_sessions_table():
    """Create gaming_sessions table"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create gaming_sessions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gaming_sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_time TEXT NOT NULL,
            end_time TEXT,
            duration_seconds INTEGER,
            participant_count INTEGER,
            participants TEXT,
            maps_played TEXT,
            total_rounds INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create indexes
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_gaming_sessions_start 
        ON gaming_sessions(start_time DESC)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_gaming_sessions_status 
        ON gaming_sessions(status)
    ''')
    
    conn.commit()
    
    # Verify
    cursor.execute("PRAGMA table_info(gaming_sessions)")
    columns = cursor.fetchall()
    
    print(f"✅ Created gaming_sessions table with {len(columns)} columns:")
    for col in columns:
        print(f"   - {col[1]} ({col[2]})")
    
    conn.close()

if __name__ == '__main__':
    print("🗄️ Creating gaming_sessions table...")
    try:
        create_gaming_sessions_table()
        print("✅ Success!")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
