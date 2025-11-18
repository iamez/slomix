"""
Phase 1 Migration: Add gaming_session_id Column

This migration adds gaming_session_id to the sessions table (which stores rounds)
and backfills all existing records using 60-minute gap logic.

NON-BREAKING CHANGE: Keeps all existing columns and foreign keys intact.

What this does:
1. Adds gaming_session_id column to sessions table
2. Calculates gaming sessions using 60-minute gap threshold
3. Backfills all 231 existing rounds
4. Adds index for performance
5. Validates results

Gaming Session Logic:
- Group consecutive rounds into gaming sessions
- If gap between rounds > 60 minutes → new gaming session
- Handles midnight-crossing (same gaming session continues after midnight)
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = "bot/etlegacy_production.db"
GAP_THRESHOLD_MINUTES = 60


def add_gaming_session_id_column(cursor):
    """Add gaming_session_id column to sessions table"""
    print("\n" + "="*70)
    print("STEP 1: Adding gaming_session_id column to sessions table")
    print("="*70)
    
    # Check if column already exists
    cursor.execute("PRAGMA table_info(sessions)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'gaming_session_id' in columns:
        print("⚠️  Column 'gaming_session_id' already exists!")
        response = input("Do you want to recalculate gaming sessions? (y/n): ")
        if response.lower() != 'y':
            return False
        print("✅ Will recalculate gaming_session_id values...")
        return True
    
    cursor.execute("ALTER TABLE sessions ADD COLUMN gaming_session_id INTEGER")
    print("✅ Added gaming_session_id column")
    return True


def calculate_gaming_sessions(cursor):
    """
    Calculate gaming_session_id for all rounds using 60-minute gap logic.
    
    Algorithm:
    1. Get all rounds sorted by date and time
    2. Start with gaming_session_id = 1
    3. For each round:
       - Calculate time gap from previous round
       - If gap > 60 minutes → increment gaming_session_id
       - Assign gaming_session_id to this round
    4. Bulk update database
    """
    print("\n" + "="*70)
    print("STEP 2: Calculating gaming sessions (60-minute gap threshold)")
    print("="*70)
    
    # Get all rounds sorted by date and time
    cursor.execute("""
        SELECT id, round_date, round_time, map_name, round_number
        FROM rounds
        ORDER BY round_date, round_time
    """)
    rounds = cursor.fetchall()
    
    print(f"📊 Found {len(rounds)} rounds to process")
    
    if not rounds:
        print("⚠️  No rounds found in database!")
        return []
    
    gaming_session_id = 1
    last_datetime = None
    updates = []
    
    gaming_session_info = {}  # Track info about each gaming session
    
    for round_id, date, time, map_name, round_num in rounds:
        # Parse datetime
        try:
            current_datetime = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H%M%S")
        except ValueError as e:
            print(f"⚠️  Error parsing datetime for round {round_id}: {date} {time}")
            print(f"   Error: {e}")
            continue
        
        # Check gap from previous round
        if last_datetime:
            gap_minutes = (current_datetime - last_datetime).total_seconds() / 60
            
            if gap_minutes > GAP_THRESHOLD_MINUTES:
                # Start new gaming session
                gaming_session_id += 1
                print(f"\n🔄 New gaming session #{gaming_session_id} started (gap: {gap_minutes:.1f} min)")
                print(f"   Previous: {last_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"   Current:  {current_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Store update
        updates.append((gaming_session_id, round_id))
        
        # Track gaming session info
        if gaming_session_id not in gaming_session_info:
            gaming_session_info[gaming_session_id] = {
                'start_date': date,
                'start_time': time,
                'end_date': date,
                'end_time': time,
                'rounds': [],
                'dates': set()
            }
        
        gaming_session_info[gaming_session_id]['end_date'] = date
        gaming_session_info[gaming_session_id]['end_time'] = time
        gaming_session_info[gaming_session_id]['rounds'].append(f"{map_name} R{round_num}")
        gaming_session_info[gaming_session_id]['dates'].add(date)
        
        last_datetime = current_datetime
    
    print(f"\n✅ Calculated {gaming_session_id} gaming sessions")
    print(f"✅ Prepared {len(updates)} updates")
    
    return updates, gaming_session_info


def apply_updates(cursor, updates):
    """Bulk update gaming_session_id for all rounds"""
    print("\n" + "="*70)
    print("STEP 3: Applying updates to database")
    print("="*70)
    
    cursor.executemany(
        "UPDATE rounds SET gaming_session_id = ? WHERE id = ?",
        updates
    )
    
    print(f"✅ Updated {len(updates)} rounds with gaming_session_id")


def create_index(cursor):
    """Create index on gaming_session_id for performance"""
    print("\n" + "="*70)
    print("STEP 4: Creating index on gaming_session_id")
    print("="*70)
    
    # Check if index already exists
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='index' AND name='idx_gaming_session_id'
    """)
    
    if cursor.fetchone():
        print("ℹ️  Index 'idx_gaming_session_id' already exists")
        return
    
    cursor.execute("""
        CREATE INDEX idx_gaming_session_id ON sessions(gaming_session_id)
    """)
    
    print("✅ Created index on gaming_session_id")


def validate_results(cursor, gaming_session_info):
    """Validate the gaming_session_id assignments"""
    print("\n" + "="*70)
    print("STEP 5: Validating results")
    print("="*70)
    
    # Check for NULL values
    cursor.execute("SELECT COUNT(*) FROM rounds WHERE gaming_session_id IS NULL")
    null_count = cursor.fetchone()[0]
    
    if null_count > 0:
        print(f"⚠️  WARNING: {null_count} rounds have NULL gaming_session_id")
    else:
        print("✅ All rounds have gaming_session_id assigned")
    
    # Count gaming sessions
    cursor.execute("SELECT COUNT(DISTINCT gaming_session_id) FROM rounds")
    total_gaming_sessions = cursor.fetchone()[0]
    print(f"✅ Total gaming sessions: {total_gaming_sessions}")
    
    # Show summary of each gaming session
    print("\n📊 Gaming Session Summary:")
    print("=" * 70)
    
    for gs_id in sorted(gaming_session_info.keys()):
        info = gaming_session_info[gs_id]
        
        cursor.execute("""
            SELECT COUNT(*) FROM rounds WHERE gaming_session_id = ?
        """, (gs_id,))
        round_count = cursor.fetchone()[0]
        
        start_date = info['start_date']
        start_time = info['start_time']
        end_date = info['end_date']
        end_time = info['end_time']
        
        # Calculate duration
        try:
            start_dt = datetime.strptime(f"{start_date} {start_time}", "%Y-%m-%d %H%M%S")
            end_dt = datetime.strptime(f"{end_date} {end_time}", "%Y-%m-%d %H%M%S")
            duration = (end_dt - start_dt).total_seconds() / 60
        except:
            duration = 0
        
        dates_str = ", ".join(sorted(info['dates']))
        
        print(f"\n🎮 Gaming Round #{gs_id}")
        print(f"   Date(s):  {dates_str}")
        print(f"   Start:    {start_date} {start_time[:2]}:{start_time[2:4]}:{start_time[4:]}")
        print(f"   End:      {end_date} {end_time[:2]}:{end_time[2:4]}:{end_time[4:]}")
        print(f"   Duration: {duration:.0f} minutes ({duration/60:.1f} hours)")
        print(f"   Rounds:   {round_count}")
        
        if len(info['dates']) > 1:
            print(f"   ⚠️  Crosses midnight: {list(info['dates'])}")
    
    # Specific validation: Oct 19 should have 1 gaming session
    print("\n" + "="*70)
    print("SPECIFIC VALIDATION: October 19, 2025")
    print("="*70)
    
    cursor.execute("""
        SELECT DISTINCT gaming_session_id
        FROM rounds
        WHERE round_date = '2025-10-19'
    """)
    oct19_sessions = cursor.fetchall()
    
    cursor.execute("""
        SELECT COUNT(*)
        FROM rounds
        WHERE round_date = '2025-10-19'
    """)
    oct19_round_count = cursor.fetchone()[0]
    
    print(f"📅 October 19, 2025:")
    print(f"   Rounds: {oct19_round_count}")
    print(f"   Gaming Sessions: {len(oct19_sessions)}")
    
    if len(oct19_sessions) == 1:
        print(f"   ✅ CORRECT: All 23 rounds belong to gaming session #{oct19_sessions[0][0]}")
    else:
        print(f"   ⚠️  WARNING: Found {len(oct19_sessions)} gaming sessions, expected 1")
        print(f"   Gaming session IDs: {[s[0] for s in oct19_sessions]}")


def main():
    """Run the migration"""
    print("\n" + "="*80)
    print("PHASE 1 MIGRATION: Add gaming_session_id Column")
    print("="*80)
    print(f"\nDatabase: {DB_PATH}")
    print(f"Gap Threshold: {GAP_THRESHOLD_MINUTES} minutes")
    print("\nThis migration will:")
    print("  1. Add gaming_session_id column to sessions table")
    print("  2. Calculate gaming sessions using 60-minute gap logic")
    print("  3. Backfill all existing rounds")
    print("  4. Create index for performance")
    print("  5. Validate results")
    print("\nThis is a NON-BREAKING change (keeps all existing columns intact)")
    print("="*80)
    
    # Check if database exists
    if not Path(DB_PATH).exists():
        print(f"\n❌ ERROR: Database not found at {DB_PATH}")
        return
    
    response = input("\n⚠️  Proceed with migration? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("❌ Migration cancelled")
        return
    
    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Step 1: Add column
        should_calculate = add_gaming_session_id_column(cursor)
        
        if not should_calculate:
            print("\n✅ Migration cancelled - no changes made")
            return
        
        # Step 2: Calculate gaming sessions
        updates, gaming_session_info = calculate_gaming_sessions(cursor)
        
        if not updates:
            print("\n❌ No updates to apply")
            return
        
        # Step 3: Apply updates
        apply_updates(cursor, updates)
        
        # Step 4: Create index
        create_index(cursor)
        
        # Commit changes
        conn.commit()
        print("\n✅ Changes committed to database")
        
        # Step 5: Validate
        validate_results(cursor, gaming_session_info)
        
        print("\n" + "="*80)
        print("✅ MIGRATION COMPLETED SUCCESSFULLY")
        print("="*80)
        print("\nNext steps:")
        print("  1. Update database_manager.py to assign gaming_session_id on import")
        print("  2. Update last_session_cog.py to use gaming_session_id")
        print("  3. Test !last_round bot command")
        print("  4. Import new files and verify gaming_session_id assignment")
        print("="*80)
        
    except Exception as e:
        print(f"\n❌ ERROR during migration: {e}")
        conn.rollback()
        print("⚠️  Changes rolled back - database unchanged")
        import traceback
        traceback.print_exc()
        
    finally:
        conn.close()


if __name__ == "__main__":
    main()
