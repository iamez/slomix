#!/usr/bin/env python3
"""
Add time_played_seconds column to database
==========================================
Adds INTEGER column to store time in seconds (more efficient than float minutes)
"""
import sqlite3
import os
from datetime import datetime

DB_PATH = 'etlegacy_production.db'

def backup_database():
    """Create a backup before modification"""
    if not os.path.exists('database_backups'):
        os.makedirs('database_backups')
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = f'database_backups/seconds_migration_{timestamp}'
    os.makedirs(backup_dir)
    
    backup_path = f'{backup_dir}/etlegacy_production_backup.db'
    
    # Copy database
    import shutil
    shutil.copy2(DB_PATH, backup_path)
    
    print(f"✅ Backup created: {backup_path}")
    return backup_path

def add_seconds_column():
    """Add time_played_seconds column to player_comprehensive_stats"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    try:
        # Check if column already exists
        columns = c.execute('PRAGMA table_info(player_comprehensive_stats)').fetchall()
        col_names = [col[1] for col in columns]
        
        if 'time_played_seconds' in col_names:
            print("⚠️  Column 'time_played_seconds' already exists!")
            return False
        
        # Add the column
        print("Adding time_played_seconds column...")
        c.execute('''
            ALTER TABLE player_comprehensive_stats
            ADD COLUMN time_played_seconds INTEGER DEFAULT 0
        ''')
        
        conn.commit()
        print("✅ Column added successfully!")
        
        # Show stats
        total_records = c.execute('SELECT COUNT(*) FROM player_comprehensive_stats').fetchone()[0]
        print(f"\nTotal records: {total_records}")
        print("All existing records have time_played_seconds = 0 (default)")
        print("\nNext step: Re-import files with new parser to populate seconds field")
        
        return True
        
    except sqlite3.OperationalError as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        conn.close()

def main():
    print('='*80)
    print('DATABASE MIGRATION: Add time_played_seconds Column')
    print('='*80)
    print()
    
    # Backup first
    backup_path = backup_database()
    print()
    
    # Add column
    success = add_seconds_column()
    
    if success:
        print()
        print('='*80)
        print('✅ MIGRATION COMPLETE!')
        print('='*80)
        print()
        print('📝 Next Steps:')
        print('  1. Re-import October 2nd files with updated parser')
        print('  2. Verify time_played_seconds is populated correctly')
        print('  3. Update bot queries to use seconds-based DPM calculation')
        print()
        print(f'💾 Backup location: {backup_path}')
    else:
        print()
        print('⚠️  Migration skipped or failed')
        print(f'💾 Backup location: {backup_path}')

if __name__ == '__main__':
    main()
