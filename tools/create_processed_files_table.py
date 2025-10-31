"""
Create processed_files table for tracking imported gamestats files
"""
import sqlite3
import os

def create_processed_files_table():
    """Create the processed_files table if it doesn't exist"""
    db_path = 'etlegacy_production.db'
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("🗄️ Checking processed_files table...")
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='processed_files'")
        exists = cursor.fetchone()
        
        if not exists:
            print("Creating new table...")
            # Create table
            cursor.execute('''
                CREATE TABLE processed_files (
                    filename TEXT PRIMARY KEY,
                    processed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    file_size INTEGER,
                    session_id INTEGER,
                    map_name TEXT,
                    round_number INTEGER,
                    player_count INTEGER,
                    status TEXT DEFAULT 'completed',
                    error_message TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            ''')
        else:
            print("Table already exists, verifying structure...")
            cursor.execute("PRAGMA table_info(processed_files)")
            columns = {col[1] for col in cursor.fetchall()}
            required = {'filename', 'processed_at'}
            if not required.issubset(columns):
                print(f"❌ Missing required columns: {required - columns}")
                return False
        
        # Create indexes for performance (only for existing columns)
        cursor.execute("PRAGMA table_info(processed_files)")
        columns = {col[1] for col in cursor.fetchall()}
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_processed_files_date
            ON processed_files(processed_at DESC)
        ''')
        
        if 'map_name' in columns:
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_processed_files_map
                ON processed_files(map_name)
            ''')
        
        if 'status' in columns:
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_processed_files_status
                ON processed_files(status)
            ''')
        
        conn.commit()
        
        # Verify table was created
        cursor.execute("PRAGMA table_info(processed_files)")
        columns = cursor.fetchall()
        
        print(f"✅ Created processed_files table with {len(columns)} columns:")
        for col in columns:
            print(f"   - {col[1]} ({col[2]})")
        
        # Show existing file count
        cursor.execute("SELECT COUNT(*) FROM processed_files")
        count = cursor.fetchone()[0]
        print(f"\n📊 Current processed files: {count}")
        
        print("\n✅ Success!")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == '__main__':
    create_processed_files_table()
