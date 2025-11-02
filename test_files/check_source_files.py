import sqlite3
import os

db_path = 'bot/etlegacy_production.db'
local_stats = 'local_stats'

# Connect to database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get session date we've been analyzing
session_date = '2025-10-30'

# Find the te_escape2 files from that date
escape2_files = [f for f in os.listdir(local_stats) 
                 if session_date in f and 'te_escape2' in f]

print(f"Found {len(escape2_files)} te_escape2 files for {session_date}:")
for f in sorted(escape2_files):
    print(f"  {f}")

print("\n" + "="*80)
print("RAW FILE CONTENTS:")
print("="*80)

# Parse and display what's actually in the files
for filename in sorted(escape2_files):
    filepath = os.path.join(local_stats, filename)
    print(f"\n{filename}:")
    
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
        
        # First line is header with map info
        header = lines[0].strip()
        parts = header.split('\\')
        if len(parts) >= 6:
            map_name = parts[1]
            round_num = parts[5]
            print(f"  Map: {map_name}, Round: {round_num}")
        
        # Count players
        player_lines = [l for l in lines[1:] if l.strip() and not l.startswith('^')]
        print(f"  Players in file: {len(player_lines)}")
        
        # Show each player and their team
        for line in player_lines:
            parts = line.split('\\')
            if len(parts) >= 3:
                guid = parts[0]
                name = parts[1]
                team = parts[2]
                print(f"    {name:30s} GUID: {guid} Team: {team}")

print("\n" + "="*80)
print("DATABASE CONTENTS FOR SAME SESSION:")
print("="*80)

# Find session_id(s) for te_escape2 on this date
cursor.execute("""
    SELECT DISTINCT session_id, session_date, map_name, round_number
    FROM player_comprehensive_stats
    WHERE session_date LIKE ? AND map_name = 'te_escape2'
    ORDER BY session_id, round_number
""", (f'{session_date}%',))

sessions = cursor.fetchall()
print(f"\nFound {len(sessions)} session records:")
for sess_id, sess_date, map_name, round_num in sessions:
    print(f"  Session ID: {sess_id}, Date: {sess_date}, Map: {map_name}, Round: {round_num}")

# For each session, show what players are in the database
for sess_id, sess_date, map_name, round_num in sessions:
    print(f"\n--- Session {sess_id}, Round {round_num} ---")
    
    cursor.execute("""
        SELECT player_guid, player_name, team, kills, deaths
        FROM player_comprehensive_stats
        WHERE session_id = ? AND round_number = ?
        ORDER BY team, player_name
    """, (sess_id, round_num))
    
    players = cursor.fetchall()
    print(f"  Players in database: {len(players)}")
    
    for guid, name, team, kills, deaths in players:
        print(f"    {name:30s} GUID: {guid} Team: {team} K/D: {kills}/{deaths}")

conn.close()

print("\n" + "="*80)
print("CONCLUSION:")
print("="*80)
print("Compare the RAW FILES vs DATABASE - do they match?")
print("If files have 6 players but database has 12, we have a duplicate import bug!")
