"""
Deep analysis - compare multiple recent files with database
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

# Get the 5 most recent Round 2 sessions
cursor.execute("""
    SELECT id, round_date, map_name, round_number
    FROM rounds
    WHERE round_number = 2
    ORDER BY id DESC
    LIMIT 5
""")

sessions = cursor.fetchall()

print("=" * 100)
print("DEEP ANALYSIS: Recent Round 2 Sessions")
print("=" * 100)

parser = C0RNP0RN3StatsParser()

for round_id, round_date, map_name, round_num in sessions:
    print(f"\n{'=' * 100}")
    print(f"Session {round_id}: {round_date} - {map_name} Round {round_num}")
    print("=" * 100)
    
    # Find the corresponding raw file
    raw_files = [f for f in os.listdir('bot/local_stats') 
                 if map_name in f and f'round-{round_num}.txt' in f and round_date[:10] in f]
    
    if not raw_files:
        print(f"  WARNING: No raw file found for {round_date} {map_name}")
        continue
    
    # Use the first matching file
    raw_file = f"bot/local_stats/{raw_files[0]}"
    print(f"\n📄 Raw file: {raw_files[0]}")
    
    # Check if Round 1 can be found
    round_1_found = parser.find_corresponding_round_1_file(raw_file)
    if round_1_found:
        print(f"[OK] Round 1 found: {os.path.basename(round_1_found)}")
    else:
        print(f"[FAIL] Round 1 NOT found!")
    
    # Parse the file
    try:
        result = parser.parse_stats_file(raw_file)
        parsed_players = result.get('players', [])
        print(f"\nParsed {len(parsed_players)} players from file")
        
        # Get database stats for this session
        cursor.execute("""
            SELECT 
                player_name,
                kills, deaths,
                headshot_kills,
                revives_given,
                team_damage_given, team_damage_received,
                gibs,
                accuracy,
                time_dead_minutes
            FROM player_comprehensive_stats
            WHERE round_id = ? AND round_number = ?
            ORDER BY kills DESC
            LIMIT 3
        """, (round_id, round_num))
        
        db_players = cursor.fetchall()
        print(f"Database has {len(db_players)} players (showing top 3)")
        
        # Compare first 3 players
        print(f"\nCOMPARISON (Top 3 players):")
        print("-" * 100)
        
        for i, (name, kills, deaths, hs, revs, tdmg_g, tdmg_r, gibs, acc, time_dead) in enumerate(db_players):
            clean_name = re.sub(r'\^.', '', name)
            
            # Find matching player in parsed data
            parsed_player = None
            for p in parsed_players:
                if p.get('guid') in name or clean_name in p.get('name', ''):
                    parsed_player = p
                    break
            
            print(f"\n  Player {i+1}: {clean_name}")
            print(f"    DATABASE:")
            print(f"      K/D: {kills}/{deaths}, HS: {hs}, Revives: {revs}, Gibs: {gibs}")
            print(f"      Team Dmg: {tdmg_g}/{tdmg_r}, Acc: {acc}%, Time Dead: {time_dead}m")
            
            if parsed_player:
                obj_stats = parsed_player.get('objective_stats', {})
                print(f"    PARSER OUTPUT:")
                print(f"      K/D: {parsed_player.get('kills')}/{parsed_player.get('deaths')}, " +
                      f"HS: {obj_stats.get('headshot_kills')}, " +
                      f"Revives: {obj_stats.get('revives_given')}, " +
                      f"Gibs: {obj_stats.get('gibs')}")
                print(f"      Team Dmg: {obj_stats.get('team_damage_given')}/{obj_stats.get('team_damage_received')}, " +
                      f"Acc: {parsed_player.get('accuracy', 0):.1f}%, " +
                      f"Time Dead: {obj_stats.get('time_dead_minutes', 0)}m")
                
                # Check for mismatches
                issues = []
                if kills != parsed_player.get('kills'):
                    issues.append(f"Kills mismatch: DB={kills} vs Parser={parsed_player.get('kills')}")
                if hs != obj_stats.get('headshot_kills'):
                    issues.append(f"Headshots: DB={hs} vs Parser={obj_stats.get('headshot_kills')}")
                if revs != obj_stats.get('revives_given'):
                    issues.append(f"Revives: DB={revs} vs Parser={obj_stats.get('revives_given')}")
                if abs(acc - parsed_player.get('accuracy', 0)) > 1:
                    issues.append(f"Accuracy: DB={acc} vs Parser={parsed_player.get('accuracy', 0):.1f}")
                if tdmg_g != obj_stats.get('team_damage_given'):
                    issues.append(f"Team Dmg Given: DB={tdmg_g} vs Parser={obj_stats.get('team_damage_given')}")
                
                if issues:
                    print(f"    ** ISSUES FOUND:")
                    for issue in issues:
                        print(f"      - {issue}")
                else:
                    print(f"    [OK] All stats match!")
            else:
                print(f"    WARNING: Could not find matching player in parser output")
    
    except Exception as e:
        print(f"  ERROR processing: {e}")
        import traceback
        traceback.print_exc()

conn.close()

print(f"\n\n{'=' * 100}")
print("SUMMARY")
print("=" * 100)
print("Check above for:")
print("  1. [FAIL] Round 1 NOT found - indicates parser issue")
print("  2. ** ISSUES FOUND - indicates data mismatch between parser and database")
print("  3. [OK] All stats match - indicates correct import")
