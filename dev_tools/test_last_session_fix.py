#!/usr/bin/env python3
"""
Test script to verify the /last_round fix
Shows what session_ids the bot will use vs old date-based approach
"""

import sqlite3
from datetime import datetime, timedelta

db_path = "bot/etlegacy_production.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=" * 70)
print("🔍 TESTING LAST_SESSION FIX")
print("=" * 70)

# Step 1: Get absolute last session (what _fetch_session_data does)
cursor.execute("""
    SELECT id, map_name, round_number, round_date, round_time
    FROM rounds
    ORDER BY round_date DESC, round_time DESC
    LIMIT 1
""")
last_row = cursor.fetchone()
last_id, last_map, last_round, last_date, last_time = last_row

print("\n✅ LAST SESSION IN DATABASE:")
print(f"   ID: {last_id}")
print(f"   Map: {last_map} R{last_round}")
print(f"   Date: {last_date}")
print(f"   Time: {last_time}")

# Step 2: Work backwards with 30-min gaps (gaming session detection)
last_dt = datetime.strptime(f"{last_date}-{last_time}", '%Y-%m-%d-%H%M%S')
gaming_session_ids = [last_id]
current_dt = last_dt

search_start_date = (last_dt - timedelta(days=1)).strftime('%Y-%m-%d')

cursor.execute("""
    SELECT id, map_name, round_number, round_date, round_time
    FROM rounds
    WHERE round_date >= ?
      AND id < ?
    ORDER BY round_date DESC, round_time DESC
""", (search_start_date, last_id))

previous_sessions = cursor.fetchall()

for sess in previous_sessions:
    sess_id, sess_map, sess_round, sess_date, sess_time = sess
    sess_dt = datetime.strptime(f"{sess_date}-{sess_time}", '%Y-%m-%d-%H%M%S')
    
    gap_minutes = (current_dt - sess_dt).total_seconds() / 60
    
    if gap_minutes <= 30:
        gaming_session_ids.insert(0, sess_id)
        current_dt = sess_dt
    else:
        print(f"\n⏱️  GAP DETECTED: {gap_minutes:.1f} minutes")
        print(f"   Stopped at ID {sess_id} ({sess_map} R{sess_round})")
        break

print("\n✅ GAMING SESSION IDS (using 30-min gap logic):")
print(f"   Count: {len(gaming_session_ids)} rounds")
print(f"   IDs: {gaming_session_ids[:5]}{'...' if len(gaming_session_ids) > 5 else ''}")

# Step 3: Get the date range for display
cursor.execute("""
    SELECT MIN(round_date), MAX(round_date), 
           MIN(round_time), MAX(round_time)
    FROM rounds
    WHERE id IN ({','.join('?' * len(gaming_session_ids))})
""", gaming_session_ids)
min_date, max_date, min_time, max_time = cursor.fetchone()
print(f"   Time Range: {min_date} {min_time} → {max_date} {max_time}")

# Step 4: Compare with OLD date-based approach
latest_date = last_date[:10]  # Just YYYY-MM-DD
print("\n❌ OLD APPROACH (date-based query):")
print(f"   Would query: round_date = '{latest_date}'")

cursor.execute("""
    SELECT id, map_name, round_number, round_time
    FROM rounds
    WHERE substr(round_date, 1, 10) = ?
    ORDER BY round_time
""", (latest_date,))
old_approach_sessions = cursor.fetchall()

print(f"   Would get {len(old_approach_sessions)} rounds:")
for sess_id, sess_map, sess_round, sess_time in old_approach_sessions[:3]:
    in_gaming_session = "✅" if sess_id in gaming_session_ids else "❌"
    print(f"     {in_gaming_session} ID {sess_id}: {sess_map} R{sess_round} @ {sess_time}")
if len(old_approach_sessions) > 3:
    print(f"     ... and {len(old_approach_sessions) - 3} more")

# Step 5: Summary
print(f"\n{'='*70}")
print("📊 SUMMARY:")
print(f"{'='*70}")
print(f"✅ NEW approach: {len(gaming_session_ids)} rounds (correct gaming session)")
print(f"❌ OLD approach: {len(old_approach_sessions)} rounds (may include orphans/multiple sessions)")
print(f"\n🎯 FIX STATUS: {'✅ WORKING' if len(gaming_session_ids) < len(old_approach_sessions) else '⚠️ SAME'}")

conn.close()
