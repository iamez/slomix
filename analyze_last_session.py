"""
Complete analysis of the last session (Nov 1-2)
Round by round, map by map, with team tracking
"""
import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

print("="*80)
print("LAST SESSION ANALYSIS (Nov 1-2, 2025)")
print("="*80)

# Get the session
cursor.execute("""
    SELECT DISTINCT session_date, map_name, round_number
    FROM player_comprehensive_stats
    WHERE session_date IN ('2025-11-01', '2025-11-02')
    ORDER BY session_date, map_name, round_number
""")

session_data = cursor.fetchall()

# Group by session_date and map
from collections import defaultdict
by_session_map = defaultdict(list)

for session_date, map_name, round_num in session_data:
    by_session_map[(session_date, map_name)].append(round_num)

print(f"\nSession structure:")
for (date, map_name), rounds in sorted(by_session_map.items()):
    print(f"  {date} - {map_name}: Rounds {rounds}")

print("\n" + "="*80)
print("DETAILED MAP-BY-MAP ANALYSIS")
print("="*80)

map_count = 0

for (session_date, map_name), rounds in sorted(by_session_map.items()):
    map_count += 1
    
    print(f"\n{'#'*80}")
    print(f"MAP {map_count}: {map_name} ({session_date})")
    print(f"{'#'*80}")
    
    # Track teams across rounds for this map
    map_team_a = None
    map_team_b = None
    
    for round_num in sorted(rounds):
        print(f"\n{'-'*80}")
        print(f"ROUND {round_num}")
        print(f"{'-'*80}")
        
        # Get players for this round
        cursor.execute("""
            SELECT player_guid, player_name, team, kills, deaths, time_played_minutes
            FROM player_comprehensive_stats
            WHERE session_date = ? AND map_name = ? AND round_number = ?
            ORDER BY team, player_name
        """, (session_date, map_name, round_num))
        
        players = cursor.fetchall()
        
        axis_players = {}
        allies_players = {}
        
        for guid, name, team, kills, deaths, time_played in players:
            if team == 1:
                axis_players[guid] = {'name': name, 'kills': kills, 'deaths': deaths, 'time': time_played}
            else:
                allies_players[guid] = {'name': name, 'kills': kills, 'deaths': deaths, 'time': time_played}
        
        print(f"\n🔴 AXIS ({len(axis_players)} players):")
        for guid, info in sorted(axis_players.items(), key=lambda x: x[1]['name']):
            print(f"   {info['name']:<30} K:{info['kills']:<3} D:{info['deaths']:<3} Time:{info['time']:.1f}m")
        
        print(f"\n🔵 ALLIES ({len(allies_players)} players):")
        for guid, info in sorted(allies_players.items(), key=lambda x: x[1]['name']):
            print(f"   {info['name']:<30} K:{info['kills']:<3} D:{info['deaths']:<3} Time:{info['time']:.1f}m")
        
        # Establish teams from Round 1
        if round_num == min(rounds):
            map_team_a = set(axis_players.keys())
            map_team_b = set(allies_players.keys())
            print(f"\n📋 Established baseline:")
            print(f"   Team A (R1 Axis): {len(map_team_a)} players")
            print(f"   Team B (R1 Allies): {len(map_team_b)} players")
        else:
            # Check for roster changes and side swapping
            current_axis = set(axis_players.keys())
            current_allies = set(allies_players.keys())
            
            print(f"\n🔍 Team tracking:")
            
            # Check if Team A and B swapped sides (stopwatch)
            team_a_on_axis = map_team_a & current_axis
            team_a_on_allies = map_team_a & current_allies
            team_b_on_axis = map_team_b & current_axis
            team_b_on_allies = map_team_b & current_allies
            
            print(f"   Team A: {len(team_a_on_axis)} on Axis, {len(team_a_on_allies)} on Allies")
            print(f"   Team B: {len(team_b_on_axis)} on Axis, {len(team_b_on_allies)} on Allies")
            
            if team_a_on_allies and team_b_on_axis and not team_a_on_axis and not team_b_on_allies:
                print(f"   ✅ Perfect stopwatch swap!")
            
            # Check for new players
            all_current = current_axis | current_allies
            all_baseline = map_team_a | map_team_b
            
            new_players = all_current - all_baseline
            left_players = all_baseline - all_current
            
            if new_players:
                print(f"\n   ➕ New players joined this round:")
                for guid in new_players:
                    if guid in axis_players:
                        name = axis_players[guid]['name']
                        print(f"      - {name} (joined Axis)")
                    else:
                        name = allies_players[guid]['name']
                        print(f"      - {name} (joined Allies)")
            
            if left_players:
                print(f"\n   ❌ Players left after R1:")
                for guid in left_players:
                    # Get name from team baseline
                    cursor.execute("""
                        SELECT player_name
                        FROM player_comprehensive_stats
                        WHERE session_date = ? AND map_name = ? AND player_guid = ?
                        LIMIT 1
                    """, (session_date, map_name, guid))
                    result = cursor.fetchone()
                    if result:
                        print(f"      - {result[0]}")

# Session summary
print(f"\n{'='*80}")
print("SESSION SUMMARY")
print(f"{'='*80}")

cursor.execute("""
    SELECT DISTINCT player_guid, player_name
    FROM player_comprehensive_stats
    WHERE session_date IN ('2025-11-01', '2025-11-02')
    ORDER BY player_name
""")

all_players = cursor.fetchall()
print(f"\nTotal unique players in session: {len(all_players)}")

for guid, name in all_players:
    # Count maps played
    cursor.execute("""
        SELECT COUNT(DISTINCT map_name)
        FROM player_comprehensive_stats
        WHERE session_date IN ('2025-11-01', '2025-11-02') AND player_guid = ?
    """, (guid,))
    map_count = cursor.fetchone()[0]
    
    print(f"   {name:<30} - {map_count} map(s)")

conn.close()
