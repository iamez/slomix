"""
Check Oct 27 sessions (the live test period)
"""
import sqlite3
import sys
sys.path.insert(0, 'bot')
from community_stats_parser import C0RNP0RN3StatsParser
import os

db_path = "bot/etlegacy_production.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get sessions from Oct 27
cursor.execute("""
    SELECT id, session_date, map_name, round_number
    FROM sessions
    WHERE session_date LIKE '2025-10-27%'
    ORDER BY id DESC
    LIMIT 20
""")

sessions = cursor.fetchall()
print("=" * 100)
print(f"OCT 27 SESSIONS ({len(sessions)} found)")
print("=" * 100)

parser = C0RNP0RN3StatsParser()

for session_id, session_date, map_name, round_num in sessions:
    # Get top player stats
    cursor.execute("""
        SELECT 
            player_name, kills, deaths, headshot_kills, revives_given,
            team_damage_given, team_damage_received, gibs, accuracy, time_dead_minutes
        FROM player_comprehensive_stats
        WHERE session_id = ? AND round_number = ?
        ORDER BY kills DESC
        LIMIT 1
    """, (session_id, round_num))
    
    db_row = cursor.fetchone()
    if db_row:
        name, k, d, hs, revs, tdg, tdr, gibs, acc, tdead = db_row
        
        # Check for zeros
        zeros = []
        if hs == 0:
            zeros.append("HS=0")
        if revs == 0:
            zeros.append("Revs=0")
        if acc == 0:
            zeros.append("Acc=0")
        if tdead == 0:
            zeros.append("TDead=0")
        
        if zeros:
            print(f"Session {session_id} R{round_num} {map_name[:15]:15s} | K={k:2d} | " + " ".join(zeros))

conn.close()
