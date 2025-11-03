"""
Analyze sessions from Nov 1st with available raw files
"""
import sqlite3
import sys
sys.path.insert(0, 'bot')
from community_stats_parser import C0RNP0RN3StatsParser
import os
import re

db_path = "bot/etlegacy_production.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get Round 2 sessions from Nov 1st
cursor.execute("""
    SELECT id, session_date, map_name, round_number
    FROM sessions
    WHERE round_number = 2 
    AND session_date LIKE '2025-11-01%'
    ORDER BY id DESC
    LIMIT 10
""")

sessions = cursor.fetchall()

print("=" * 100)
print("ANALYSIS: Nov 1st Round 2 Sessions (same-date files)")
print("=" * 100)

parser = C0RNP0RN3StatsParser()
problem_count = 0
ok_count = 0

for session_id, session_date, map_name, round_num in sessions:
    print(f"\n{'=' * 100}")
    print(f"Session {session_id}: {map_name} Round {round_num}")
    
    # Extract date prefix for file matching
    date_prefix = session_date[:10]  # YYYY-MM-DD
    
    # Find raw file
    try:
        all_files = os.listdir('bot/local_stats')
        raw_files = [f for f in all_files 
                     if map_name in f and f'round-{round_num}.txt' in f and date_prefix in f]
        
        if not raw_files:
            print(f"  [SKIP] No raw file found")
            continue
        
        raw_file = f"bot/local_stats/{raw_files[0]}"
        print(f"  File: {raw_files[0]}")
        
        # Check Round 1 finding
        round_1_found = parser.find_corresponding_round_1_file(raw_file)
        if round_1_found:
            print(f"  [OK] R1: {os.path.basename(round_1_found)}")
        else:
            print(f"  [FAIL] Round 1 NOT FOUND!")
            problem_count += 1
            continue
        
        # Parse
        result = parser.parse_stats_file(raw_file)
        parsed_players = result.get('players', [])
        
        # Get first player from database
        cursor.execute("""
            SELECT 
                player_name, kills, headshot_kills, revives_given,
                team_damage_given, accuracy, time_dead_minutes
            FROM player_comprehensive_stats
            WHERE session_id = ? AND round_number = ?
            ORDER BY kills DESC
            LIMIT 1
        """, (session_id, round_num))
        
        db_row = cursor.fetchone()
        if not db_row:
            print(f"  [SKIP] No database entry")
            continue
        
        name, kills, hs, revs, tdmg, acc, tdead = db_row
        
        # Find in parsed
        parsed = None
        for p in parsed_players:
            if p.get('kills') == kills:
                parsed = p
                break
        
        if parsed:
            obj = parsed.get('objective_stats', {})
            
            # Quick comparison
            issues = []
            if hs != obj.get('headshot_kills', 0):
                issues.append(f"HS: DB={hs} Parser={obj.get('headshot_kills')}")
            if revs != obj.get('revives_given', 0):
                issues.append(f"Revs: DB={revs} Parser={obj.get('revives_given')}")
            if abs(acc - parsed.get('accuracy', 0)) > 1:
                issues.append(f"Acc: DB={acc:.1f} Parser={parsed.get('accuracy', 0):.1f}")
            if tdmg != obj.get('team_damage_given', 0):
                issues.append(f"TDmg: DB={tdmg} Parser={obj.get('team_damage_given')}")
            if abs(tdead - obj.get('time_dead_minutes', 0)) > 0.1:
                issues.append(f"TDead: DB={tdead:.2f} Parser={obj.get('time_dead_minutes', 0):.2f}")
            
            if issues:
                print(f"  [PROBLEM] {' | '.join(issues)}")
                problem_count += 1
            else:
                print(f"  [OK] Stats match")
                ok_count += 1
        else:
            print(f"  [SKIP] Could not match player")
    
    except Exception as e:
        print(f"  [ERROR] {e}")

print(f"\n{'=' * 100}")
print("RESULTS:")
print(f"  OK: {ok_count}")
print(f"  PROBLEMS: {problem_count}")
print("=" * 100)

conn.close()
