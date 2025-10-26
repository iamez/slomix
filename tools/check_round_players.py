"""
Check if all players present in Round 1 appear in Round 2 and vice versa
to diagnose duplicate/0-time issues
"""
import sqlite3
from collections import defaultdict

conn = sqlite3.connect('etlegacy_production.db')
c = conn.cursor()

print("🔍 Analyzing Round 1 vs Round 2 player presence...\n")

# Get all Round 2 sessions (these should have corresponding Round 1 sessions)
round2_sessions = c.execute("""
    SELECT DISTINCT id, session_date, map_name
    FROM sessions
    WHERE round_number = 2
    ORDER BY id
    LIMIT 20
""").fetchall()

print(f"Found {len(round2_sessions)} Round 2 sessions (showing first 20)\n")

mismatches = []

for session_id, session_date, map_name in round2_sessions:
    # Get the corresponding Round 1 session
    round1_data = c.execute("""
        SELECT id, session_date
        FROM sessions
        WHERE round_number = 1
        AND map_name = ?
        AND session_date <= ?
        ORDER BY session_date DESC
        LIMIT 1
    """, (map_name, session_date)).fetchone()
    
    if not round1_data:
        print(f"⚠️  Session {session_id}: No Round 1 found for {map_name}")
        continue
    
    round1_id = round1_data[0]
    round1_date = round1_data[1]
    
    # Get players in Round 1
    round1_players = set(c.execute("""
        SELECT player_guid
        FROM player_comprehensive_stats
        WHERE session_id = ?
    """, (round1_id,)).fetchall())
    
    # Get players in Round 2
    round2_players = set(c.execute("""
        SELECT player_guid
        FROM player_comprehensive_stats
        WHERE session_id = ?
    """, (session_id,)).fetchall())
    
    # Check for mismatches
    only_in_round1 = round1_players - round2_players
    only_in_round2 = round2_players - round1_players
    
    if only_in_round1 or only_in_round2:
        mismatches.append({
            'r1_id': round1_id,
            'r2_id': session_id,
            'r1_date': round1_date,
            'r2_date': session_date,
            'map': map_name,
            'only_r1': len(only_in_round1),
            'only_r2': len(only_in_round2)
        })

if mismatches:
    print(f"\n⚠️  Found {len(mismatches)} sessions with player mismatches:\n")
    for m in mismatches[:10]:
        print(f"Session R1={m['r1_id']}, R2={m['r2_id']} - {m['map']}")
        print(f"  R1 date: {m['r1_date']}")
        print(f"  R2 date: {m['r2_date']}")
        print(f"  Players only in R1: {m['only_r1']}")
        print(f"  Players only in R2: {m['only_r2']}")
        print()
else:
    print("✅ All Round 1 and Round 2 sessions have matching players!")

# Now check for duplicate records within same session
print("\n🔍 Checking for duplicate player records within sessions...\n")

duplicates = c.execute("""
    SELECT 
        session_id,
        player_guid,
        player_name,
        COUNT(*) as count,
        GROUP_CONCAT(time_played_seconds) as times
    FROM player_comprehensive_stats
    GROUP BY session_id, player_guid
    HAVING count > 1
    LIMIT 20
""").fetchall()

if duplicates:
    print(f"⚠️  Found {len(duplicates)} duplicate player records (showing first 20):\n")
    for dup in duplicates:
        times = dup[4].split(',')
        print(f"Session {dup[0]}: {dup[2]} (GUID: {dup[1]})")
        print(f"  Appears {dup[3]} times with times: {', '.join(times)}s")
        
        # Get more details
        records = c.execute("""
            SELECT id, time_played_seconds, kills, deaths
            FROM player_comprehensive_stats
            WHERE session_id = ? AND player_guid = ?
        """, (dup[0], dup[1])).fetchall()
        
        for rec in records:
            print(f"    Record ID {rec[0]}: {rec[1]}s, {rec[2]} kills, {rec[3]} deaths")
        print()
else:
    print("✅ No duplicate player records found!")

conn.close()
