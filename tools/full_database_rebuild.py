"""
Full Database Rebuild Script
=============================
Clears the database and re-imports all local stats files cleanly.
Creates a backup first for safety.
"""

import sqlite3
import shutil
import os
from datetime import datetime
from pathlib import Path

def backup_database():
    """Create a timestamped backup of the database"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_name = f'etlegacy_production_backup_{timestamp}.db'
    
    print(f"\n📦 Creating backup: {backup_name}")
    shutil.copy2('etlegacy_production.db', backup_name)
    print(f"✅ Backup created successfully!")
    return backup_name

def get_stats_snapshot():
    """Get current stats totals for verification"""
    conn = sqlite3.connect('etlegacy_production.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM player_comprehensive_stats')
    player_records = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM sessions')
    session_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM processed_files')
    processed_files = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(DISTINCT player_guid) FROM player_comprehensive_stats')
    unique_players = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(time_played_seconds) FROM player_comprehensive_stats WHERE time_played_seconds > 0')
    total_time_seconds = cursor.fetchone()[0] or 0
    
    conn.close()
    
    return {
        'player_records': player_records,
        'sessions': session_count,
        'processed_files': processed_files,
        'unique_players': unique_players,
        'total_time_seconds': total_time_seconds,
        'total_time_hours': total_time_seconds / 3600
    }

def clear_database():
    """Clear all player stats and sessions, keep schema"""
    print("\n🗑️  Clearing database tables...")
    
    conn = sqlite3.connect('etlegacy_production.db')
    cursor = conn.cursor()
    
    # Clear tables in correct order (respect foreign keys)
    tables_to_clear = [
        'player_comprehensive_stats',
        'sessions', 
        'processed_files',
        'player_synergies'
    ]
    
    for table in tables_to_clear:
        try:
            cursor.execute(f'DELETE FROM {table}')
            deleted = cursor.rowcount
            print(f"  ✓ Cleared {table}: {deleted} records deleted")
        except sqlite3.OperationalError as e:
            print(f"  ⚠️  {table}: {e}")
    
    # Reset autoincrement counters
    cursor.execute('DELETE FROM sqlite_sequence WHERE name IN (?, ?, ?, ?)', 
                   tuple(tables_to_clear))
    
    conn.commit()
    conn.close()
    print("✅ Database cleared successfully!")

def count_local_files():
    """Count stats files in local_stats directory"""
    local_stats = Path('local_stats')
    if not local_stats.exists():
        return 0
    
    files = [f for f in local_stats.glob('*.txt') if not f.name.endswith('_ws.txt')]
    return len(files)

def main():
    print("="*60)
    print("FULL DATABASE REBUILD")
    print("="*60)
    
    # Step 1: Get current stats snapshot
    print("\n📊 Current Database State:")
    before_stats = get_stats_snapshot()
    print(f"  • Player Records: {before_stats['player_records']:,}")
    print(f"  • Sessions: {before_stats['sessions']:,}")
    print(f"  • Processed Files: {before_stats['processed_files']:,}")
    print(f"  • Unique Players: {before_stats['unique_players']:,}")
    print(f"  • Total Playtime: {before_stats['total_time_hours']:.1f} hours")
    
    # Count records with 0 time
    conn = sqlite3.connect('etlegacy_production.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM player_comprehensive_stats WHERE time_played_seconds = 0')
    zero_time_count = cursor.fetchone()[0]
    conn.close()
    
    print(f"\n⚠️  Records with 0s time: {zero_time_count:,} ({zero_time_count/before_stats['player_records']*100:.1f}%)")
    
    # Step 2: Count local files
    local_file_count = count_local_files()
    print(f"\n📁 Local Stats Files: {local_file_count:,} files")
    
    # Step 3: Confirmation
    print("\n" + "="*60)
    print("⚠️  WARNING: This will DELETE all stats and re-import!")
    print("="*60)
    response = input("\nType 'YES' to continue: ")
    
    if response != 'YES':
        print("\n❌ Aborted. No changes made.")
        return
    
    # Step 4: Create backup
    backup_file = backup_database()
    
    # Step 5: Clear database
    clear_database()
    
    # Step 6: Verify cleared
    print("\n🔍 Verifying database is empty...")
    after_stats = get_stats_snapshot()
    print(f"  • Player Records: {after_stats['player_records']:,}")
    print(f"  • Sessions: {after_stats['sessions']:,}")
    print(f"  • Processed Files: {after_stats['processed_files']:,}")
    
    if after_stats['player_records'] == 0 and after_stats['sessions'] == 0:
        print("✅ Database successfully cleared!")
    else:
        print("⚠️  Warning: Database not fully cleared!")
        return
    
    # Step 7: Instructions for re-import
    print("\n" + "="*60)
    print("✅ DATABASE REBUILD COMPLETE")
    print("="*60)
    print("\n📝 Next Steps:")
    print("  1. Start the bot: python bot/ultimate_bot.py")
    print("  2. Bot will automatically re-import all local files")
    print(f"  3. Expected to import ~{local_file_count:,} files")
    print("  4. This may take 10-30 minutes")
    print("\n💾 Backup saved as:")
    print(f"  {backup_file}")
    print("\n📊 Expected Stats After Re-import:")
    print(f"  • Player Records: ~{before_stats['player_records'] - zero_time_count:,}")
    print(f"  • Sessions: ~{before_stats['sessions']:,}")
    print(f"  • Unique Players: ~{before_stats['unique_players']:,}")
    print(f"  • Total Playtime: ~{before_stats['total_time_hours']:.1f} hours")
    print("\n⚠️  IMPORTANT: If stats differ significantly, restore backup:")
    print(f"  python tools/restore_backup.py {backup_file}")

if __name__ == '__main__':
    main()
