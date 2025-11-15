import asyncio
import sys
sys.path.insert(0, '.')
from bot.core.database_adapter import create_adapter
from bot.config import load_config

async def main():
    config = load_config()
    db = create_adapter(**config.get_database_adapter_kwargs())
    await db.connect()

    print("🔍 Checking what gaming_session_ids exist for 2025-11-11...\n")

    # Get gaming_session_ids for 2025-11-11
    session_ids_for_date = await db.fetch_all("""
        SELECT DISTINCT gaming_session_id
        FROM rounds
        WHERE gaming_session_id IS NOT NULL
          AND SUBSTR(round_date, 1, 10) = '2025-11-11'
        ORDER BY gaming_session_id
    """)

    if not session_ids_for_date:
        print("❌ No gaming sessions found for 2025-11-11")
        await db.close()
        return

    session_id_list = [row[0] for row in session_ids_for_date]
    print(f"Found {len(session_id_list)} gaming_session_id(s) for 2025-11-11:")
    for sid in session_id_list:
        print(f"  - Session ID: {sid}")

    # Now check ALL rounds with these gaming_session_ids (regardless of date!)
    session_id_placeholders = ",".join("?" * len(session_id_list))

    all_rounds_in_sessions = await db.fetch_all(f"""
        SELECT round_date, round_time, map_name, round_number, gaming_session_id, id
        FROM rounds
        WHERE gaming_session_id IN ({session_id_placeholders})
        ORDER BY round_date, round_time, round_number
    """, tuple(session_id_list))

    print(f"\n📊 Total rounds with these gaming_session_ids: {len(all_rounds_in_sessions)}")
    print("\n" + "="*80)
    print("ALL rounds (including other dates if session spans midnight):")
    print("="*80)

    rounds_by_date = {}
    for date, time, map_name, rnd, sess_id, round_id in all_rounds_in_sessions:
        if date not in rounds_by_date:
            rounds_by_date[date] = []
        rounds_by_date[date].append((date, time, map_name, rnd, sess_id, round_id))

    for date in sorted(rounds_by_date.keys()):
        rounds = rounds_by_date[date]
        print(f"\n📅 Date: {date} ({len(rounds)} rounds)")
        for date, time, map_name, rnd, sess_id, round_id in rounds:
            print(f"  {date} {time} - {map_name} R{rnd} (ID: {round_id}, Session: {sess_id})")

    # Count R1+R2 only
    r1_r2_only = [r for r in all_rounds_in_sessions if r[3] in (1, 2)]
    print(f"\n" + "="*80)
    print(f"📊 R1+R2 rounds only (ALL sessions): {len(r1_r2_only)}")
    print("="*80)

    # Show what !last_session would query WITH THE FIX
    print("\n🤖 OLD BEHAVIOR (before fix):")
    print(f"   - Gaming session IDs from 2025-11-11: {session_id_list}")
    print(f"   - Total rounds (R1+R2 only): {len(r1_r2_only)}")
    print(f"   - This includes rounds from OTHER dates if they're in the same gaming session!")

    # Show what the FIXED query returns
    filtered_rounds = await db.fetch_all(f"""
        SELECT id, round_date, round_time, map_name, round_number
        FROM rounds
        WHERE gaming_session_id IN ({session_id_placeholders})
          AND round_number IN (1, 2)
          AND SUBSTR(round_date, 1, 10) = '2025-11-11'
        ORDER BY round_date, round_time
    """, tuple(session_id_list))

    print(f"\n✅ NEW BEHAVIOR (after fix):")
    print(f"   - Gaming session IDs from 2025-11-11: {session_id_list}")
    print(f"   - Filtered to ONLY 2025-11-11 rounds: {len(filtered_rounds)}")
    print(f"\nFiltered rounds (what !last_session NOW uses):")
    for round_id, date, time, map_name, rnd in filtered_rounds:
        print(f"  ID {round_id}: {date} {time} - {map_name} R{rnd}")

    await db.close()

asyncio.run(main())
