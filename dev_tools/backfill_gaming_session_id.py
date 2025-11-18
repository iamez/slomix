"""
Backfill gaming_session_id for all rounds in PostgreSQL database

Uses the same 60-minute gap logic as the original database_manager.py:
- If gap between rounds > 60 minutes → new gaming session
- If gap ≤ 60 minutes → same gaming session
"""
import asyncio
import asyncpg
from datetime import datetime, timedelta

async def backfill_gaming_sessions():
    """Backfill gaming_session_id for all rounds in chronological order"""
    
    conn = await asyncpg.connect(
        host='localhost',
        port=5432,
        user='etlegacy_user',
        password='etlegacy_secure_2025',
        database='etlegacy'
    )
    
    print("Fetching all rounds in chronological order...")
    rounds = await conn.fetch(
        """
        SELECT id, round_date, round_time
        FROM rounds
        ORDER BY round_date, round_time
        """
    )
    
    if not rounds:
        print("No rounds found!")
        await conn.close()
        return
    
    print(f"Processing {len(rounds)} rounds...")
    
    current_gaming_session_id = 1
    last_datetime = None
    updates = []
    
    for i, round_row in enumerate(rounds, 1):
        round_id = round_row['id']
        round_date = round_row['round_date']
        round_time = round_row['round_time']
        
        # Parse datetime
        try:
            # round_date is "YYYY-MM-DD", round_time is "HHMMSS"
            date_str = round_date
            time_str = round_time.zfill(6)  # Ensure 6 digits
            hour = int(time_str[0:2])
            minute = int(time_str[2:4])
            second = int(time_str[4:6])
            
            current_datetime = datetime.strptime(date_str, '%Y-%m-%d').replace(
                hour=hour, minute=minute, second=second
            )
        except Exception as e:
            print(f"  ERROR parsing round {round_id} ({round_date} {round_time}): {e}")
            continue
        
        # Determine gaming_session_id
        if last_datetime is None:
            # First round ever
            gaming_session_id = 1
            print(f"  Round {i}/{len(rounds)}: Starting gaming session #{gaming_session_id}")
        else:
            # Calculate gap
            gap = current_datetime - last_datetime
            gap_minutes = gap.total_seconds() / 60
            
            if gap_minutes > 60:
                # New session
                current_gaming_session_id += 1
                gaming_session_id = current_gaming_session_id
                print(f"  Round {i}/{len(rounds)}: New gaming session #{gaming_session_id} (gap: {gap_minutes:.1f} min)")
            else:
                # Continue session
                gaming_session_id = current_gaming_session_id
        
        # Add to batch update
        updates.append((gaming_session_id, round_id))
        last_datetime = current_datetime
        
        # Batch update every 50 rounds
        if len(updates) >= 50:
            await conn.executemany(
                "UPDATE rounds SET gaming_session_id = $1 WHERE id = $2",
                updates
            )
            updates = []
    
    # Final batch
    if updates:
        await conn.executemany(
            "UPDATE rounds SET gaming_session_id = $1 WHERE id = $2",
            updates
        )
    
    # Verify
    result = await conn.fetchval(
        "SELECT COUNT(*) FROM rounds WHERE gaming_session_id IS NOT NULL"
    )
    print(f"\n✅ Backfill complete!")
    print(f"   Total rounds: {len(rounds)}")
    print(f"   Updated rounds: {result}")
    print(f"   Total gaming sessions: {current_gaming_session_id}")
    
    # Show session distribution
    sessions = await conn.fetch(
        """
        SELECT gaming_session_id, 
               MIN(round_date) as first_date,
               MAX(round_date) as last_date,
               COUNT(*) as round_count
        FROM rounds
        WHERE gaming_session_id IS NOT NULL
        GROUP BY gaming_session_id
        ORDER BY gaming_session_id
        """
    )
    
    print(f"\nGaming Session Summary:")
    for session in sessions:
        print(f"  Session #{session['gaming_session_id']}: {session['round_count']} rounds "
              f"({session['first_date']} to {session['last_date']})")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(backfill_gaming_sessions())
