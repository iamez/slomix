#!/usr/bin/env python3
"""
Add processed_files table to existing database

This table tracks which stats files have been processed to prevent
re-downloading and re-importing files that already exist locally or
in the database.
"""

import sqlite3
import sys
from pathlib import Path

def add_processed_files_table(db_path='etlegacy_production.db'):
    """Add processed_files table if it doesn't exist"""
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if table already exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='processed_files'
        """)
        
        if cursor.fetchone():
            print("✅ processed_files table already exists")
            return True
        
        # Create the table
        cursor.execute("""
            CREATE TABLE processed_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL UNIQUE,
                success INTEGER NOT NULL DEFAULT 1,
                error_message TEXT,
                processed_at TEXT NOT NULL,
                CONSTRAINT chk_success CHECK (success IN (0, 1))
            )
        """)
        
        # Create index for faster filename lookups
        cursor.execute("""
            CREATE INDEX idx_processed_files_filename 
            ON processed_files(filename)
        """)
        
        # Create index for successful files
        cursor.execute("""
            CREATE INDEX idx_processed_files_success 
            ON processed_files(success)
        """)
        
        conn.commit()
        
        print("✅ Created processed_files table successfully")
        print("✅ Created indexes: idx_processed_files_filename, idx_processed_files_success")
        
        return True
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        return False
        
    finally:
        if conn:
            conn.close()


def main():
    """Main migration function"""
    
    # Check if database exists
    db_path = Path('etlegacy_production.db')
    
    if not db_path.exists():
        print("❌ Database not found: etlegacy_production.db")
        print("   Please run recreate_database.py first")
        sys.exit(1)
    
    print("🔄 Adding processed_files table to database...")
    
    if add_processed_files_table(str(db_path)):
        print("\n✅ Migration complete!")
        print("\nTable Schema:")
        print("  - id: Primary key")
        print("  - filename: Unique stats filename (e.g., 2025-01-15-203045-radar-round-1.txt)")
        print("  - success: 1 if processed successfully, 0 if failed")
        print("  - error_message: Error details if processing failed")
        print("  - processed_at: ISO timestamp of when file was processed")
        print("\nThis table enables:")
        print("  ✅ Persistent tracking of processed files (survives bot restarts)")
        print("  ✅ Prevention of re-downloading existing files")
        print("  ✅ Prevention of re-importing already-processed stats")
        print("  ✅ Error tracking for failed file processing")
    else:
        print("\n❌ Migration failed")
        sys.exit(1)


if __name__ == '__main__':
    main()
