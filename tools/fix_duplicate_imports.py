"""
Fix Duplicate Import Records
=============================
Removes duplicate player records from Oct 4-6 when files were re-imported.
Keeps the records with correct time_played_seconds, deletes the ones with 0s.
"""

import sqlite3
from datetime import datetime

def fix_duplicates():
    """Remove duplicate player records, keeping the ones with time > 0"""
    conn = sqlite3.connect('etlegacy_production.db')
    cursor = conn.cursor()
    
    print("🔍 Analyzing duplicate records...")
    
    # Find all duplicates (same session_id + player_name + round_number)
    cursor.execute('''
        SELECT session_id, player_name, round_number, COUNT(*) as cnt
        FROM player_comprehensive_stats
        GROUP BY session_id, player_name, round_number
        HAVING cnt > 1
    ''')
    
    duplicates = cursor.fetchall()
    print(f"   Found {len(duplicates)} duplicate groups")
    
    if len(duplicates) == 0:
        print("✅ No duplicates found!")
        conn.close()
        return
    
    deleted_count = 0
    
    for session_id, player_name, round_number, count in duplicates:
        # Get all records for this group
        cursor.execute('''
            SELECT id, time_played_seconds, created_at
            FROM player_comprehensive_stats
            WHERE session_id = ? AND player_name = ? AND round_number = ?
            ORDER BY time_played_seconds DESC, created_at ASC
        ''', (session_id, player_name, round_number))
        
        records = cursor.fetchall()
        
        # Keep the first one (highest time, earliest created_at)
        keep_id = records[0][0]
        keep_time = records[0][1]
        
        # Delete the rest
        for record_id, time, created_at in records[1:]:
            cursor.execute('DELETE FROM player_comprehensive_stats WHERE id = ?', (record_id,))
            deleted_count += 1
            print(f"   🗑️  Deleted: Session {session_id}, {player_name}, R{round_number} "
                  f"(id={record_id}, time={time}s) [kept id={keep_id}, time={keep_time}s]")
    
    # Now fix duplicate sessions
    print("\n🔍 Analyzing duplicate sessions...")
    cursor.execute('''
        SELECT session_date, map_name, COUNT(*) as cnt
        FROM sessions
        GROUP BY session_date, map_name
        HAVING cnt > 1
    ''')
    
    session_dupes = cursor.fetchall()
    print(f"   Found {len(session_dupes)} duplicate session groups")
    
    session_deleted = 0
    
    for session_date, map_name, count in session_dupes:
        # Get all session records
        cursor.execute('''
            SELECT id, created_at
            FROM sessions
            WHERE session_date = ? AND map_name = ?
            ORDER BY created_at ASC
        ''', (session_date, map_name))
        
        sessions = cursor.fetchall()
        
        # Keep the first one (earliest)
        keep_session_id = sessions[0][0]
        
        # Update all player records to point to the kept session
        for session_id, created_at in sessions[1:]:
            cursor.execute('''
                UPDATE player_comprehensive_stats
                SET session_id = ?
                WHERE session_id = ?
            ''', (keep_session_id, session_id))
            
            # Delete the duplicate session
            cursor.execute('DELETE FROM sessions WHERE id = ?', (session_id,))
            session_deleted += 1
            print(f"   🗑️  Merged session {session_id} into {keep_session_id} ({session_date} {map_name})")
    
    conn.commit()
    
    print(f"\n✅ Cleanup complete!")
    print(f"   Deleted {deleted_count} duplicate player records")
    print(f"   Merged {session_deleted} duplicate sessions")
    
    # Verify
    cursor.execute('''
        SELECT COUNT(*) FROM (
            SELECT session_id, player_name, round_number
            FROM player_comprehensive_stats
            GROUP BY session_id, player_name, round_number
            HAVING COUNT(*) > 1
        )
    ''')
    
    remaining = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM player_comprehensive_stats WHERE time_played_seconds = 0')
    zero_count = cursor.fetchone()[0]
    
    print(f"\n📊 Final stats:")
    print(f"   Remaining duplicates: {remaining}")
    print(f"   Records with 0s time: {zero_count}")
    
    conn.close()

if __name__ == '__main__':
    print("="*60)
    print("DUPLICATE RECORD CLEANUP")
    print("="*60)
    print()
    
    # Ask for confirmation
    response = input("This will delete duplicate records. Continue? (yes/no): ")
    if response.lower() != 'yes':
        print("❌ Cancelled")
        exit()
    
    fix_duplicates()
    
    print("\n🎉 Database cleaned!")
