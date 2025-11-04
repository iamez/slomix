#!/usr/bin/env python3
"""
Investigate duplicate players in last_round command
"""

import sqlite3
from datetime import datetime, timedelta

db_path = "bot/etlegacy_production.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=" * 80)
print("🔍 INVESTIGATING LAST SESSION PLAYERS")
print("=" * 80)

# Step 1: Get the gaming session IDs (same logic as bot)
cursor.execute("""
    SELECT id, map_name, round_number, round_date, round_time
    FROM rounds
    ORDER BY round_date DESC, round_time DESC
    LIMIT 1
""")
last_row = cursor.fetchone()
last_id, last_map, last_round, last_date, last_time = last_row

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
        break

print(f"\n✅ Gaming Session IDs: {len(gaming_session_ids)} rounds")
print(f"   IDs: {min(gaming_session_ids)} - {max(gaming_session_ids)}")

# Step 2: Get all ROUND 1 sessions
round1_ids = []
cursor.execute(f"""
    SELECT id, map_name, round_time
    FROM rounds
    WHERE id IN ({','.join('?' * len(gaming_session_ids))})
    AND round_number = 1
    ORDER BY id
""", gaming_session_ids)
round1_sessions = cursor.fetchall()

print(f"\n📋 ROUND 1 SESSIONS ({len(round1_sessions)} matches):")
print("=" * 80)

for sess_id, map_name, sess_time in round1_sessions:
    round1_ids.append(sess_id)
    
    # Get players for this Round 1
    cursor.execute("""
        SELECT player_name, player_guid, kills, deaths
        FROM player_comprehensive_stats
        WHERE round_id = ?
        ORDER BY kills DESC
    """, (sess_id,))
    
    players = cursor.fetchall()
    
    print(f"\n🎮 ID {sess_id}: {map_name} @ {sess_time}")
    print(f"   Players ({len(players)}):")
    for name, guid, k, d in players:
        print(f"     - {name:20s} (GUID: {guid[:8]}...) {k}K/{d}D")

# Step 3: Get ALL unique players across gaming session
print(f"\n{'='*80}")
print(f"📊 ALL UNIQUE PLAYERS IN GAMING SESSION:")
print(f"{'='*80}")

cursor.execute(f"""
    SELECT DISTINCT player_name, player_guid,
           SUM(kills) as total_kills,
           SUM(deaths) as total_deaths,
           COUNT(*) as rounds_played
    FROM player_comprehensive_stats
    WHERE round_id IN ({','.join('?' * len(gaming_session_ids))})
    GROUP BY player_guid, player_name
    ORDER BY total_kills DESC
""", gaming_session_ids)

all_players = cursor.fetchall()

print(f"\nTotal unique player records: {len(all_players)}\n")
for name, guid, k, d, rounds in all_players:
    print(f"  {name:25s} GUID: {guid[:12]}... {k:3d}K/{d:3d}D ({rounds} rounds)")

# Step 4: Check for GUID duplicates or name variations
print(f"\n{'='*80}")
print(f"🔎 CHECKING FOR DUPLICATES:")
print(f"{'='*80}")

# Group by GUID to find name changes
cursor.execute(f"""
    SELECT player_guid, GROUP_CONCAT(DISTINCT player_name) as names, COUNT(DISTINCT player_name) as name_count
    FROM player_comprehensive_stats
    WHERE round_id IN ({','.join('?' * len(gaming_session_ids))})
    GROUP BY player_guid
    HAVING name_count > 1
""", gaming_session_ids)

guid_duplicates = cursor.fetchall()

if guid_duplicates:
    print("\n⚠️  SAME GUID, DIFFERENT NAMES:")
    for guid, names, count in guid_duplicates:
        print(f"   GUID {guid[:12]}... has {count} names: {names}")
else:
    print("\n✅ No GUID duplicates with different names")

# Check for same name, different GUIDs
cursor.execute(f"""
    SELECT player_name, GROUP_CONCAT(DISTINCT player_guid) as guids, COUNT(DISTINCT player_guid) as guid_count
    FROM player_comprehensive_stats
    WHERE round_id IN ({','.join('?' * len(gaming_session_ids))})
    GROUP BY player_name
    HAVING guid_count > 1
""", gaming_session_ids)

name_duplicates = cursor.fetchall()

if name_duplicates:
    print("\n⚠️  SAME NAME, DIFFERENT GUIDS:")
    for name, guids, count in name_duplicates:
        print(f"   '{name}' has {count} GUIDs:")
        for guid in guids.split(','):
            cursor.execute(f"""
                SELECT SUM(kills), SUM(deaths), COUNT(*)
                FROM player_comprehensive_stats
                WHERE round_id IN ({','.join('?' * len(gaming_session_ids))})
                AND player_guid = ?
            """, gaming_session_ids + [guid])
            k, d, rounds = cursor.fetchone()
            print(f"      - {guid[:12]}... {k}K/{d}D ({rounds} rounds)")
else:
    print("\n✅ No name duplicates with different GUIDs")

# Step 5: Check specifically for SuperBoyy variants
print(f"\n{'='*80}")
print(f"🎯 SUPERBOY INVESTIGATION:")
print(f"{'='*80}")

cursor.execute(f"""
    SELECT player_name, player_guid, round_id, kills, deaths
    FROM player_comprehensive_stats
    WHERE round_id IN ({','.join('?' * len(gaming_session_ids))})
    AND (player_name LIKE '%SuperBoyy%' OR player_name LIKE '%superboyy%')
    ORDER BY round_id
""", gaming_session_ids)

superboy_records = cursor.fetchall()

print(f"\nFound {len(superboy_records)} SuperBoyy records:\n")
for name, guid, sess_id, k, d in superboy_records:
    cursor.execute("SELECT map_name, round_number FROM rounds WHERE id = ?", (sess_id,))
    map_name, round_num = cursor.fetchone()
    print(f"  Session {sess_id} ({map_name} R{round_num}): '{name}' GUID:{guid[:12]}... {k}K/{d}D")

conn.close()

print("\n" + "="*80)
