"""
CORRECT Stopwatch Team Detector - Per Map
==========================================
Analyzes each map separately, then tracks teams across maps.
"""

import sqlite3
from typing import Dict, Set, List

def detect_teams_for_map(cursor, round_date: str, map_name: str) -> Dict:
    """Detect teams for a single map in stopwatch mode."""
    
    print(f"\n{'='*80}")
    print(f"MAP: {map_name}")
    print(f"{'='*80}")
    
    # Get rounds for this map
    cursor.execute("""
        SELECT DISTINCT round_number
        FROM player_comprehensive_stats
        WHERE round_date = ? AND map_name = ?
        ORDER BY round_number
    """, (round_date, map_name))
    
    rounds = [r[0] for r in cursor.fetchall()]
    
    if len(rounds) < 2:
        print(f"⚠️  Only {len(rounds)} round(s) - can't determine stopwatch teams")
        return None
    
    print(f"Rounds: {rounds}")
    
    # Get Round 1 rosters
    cursor.execute("""
        SELECT player_guid, player_name, team
        FROM player_comprehensive_stats
        WHERE round_date = ? AND map_name = ? AND round_number = ?
    """, (round_date, map_name, rounds[0]))
    
    r1_axis = {}
    r1_allies = {}
    
    for guid, name, team in cursor.fetchall():
        if team == 1:
            r1_axis[guid] = name
        else:
            r1_allies[guid] = name
    
    print(f"\n🔴 Round 1 AXIS ({len(r1_axis)} players):")
    for guid, name in sorted(r1_axis.items(), key=lambda x: x[1]):
        print(f"   - {name:<30} ({guid})")
    
    print(f"\n🔵 Round 1 ALLIES ({len(r1_allies)} players):")
    for guid, name in sorted(r1_allies.items(), key=lambda x: x[1]):
        print(f"   - {name:<30} ({guid})")
    
    # Check Round 2 for swap
    cursor.execute("""
        SELECT player_guid, player_name, team
        FROM player_comprehensive_stats
        WHERE round_date = ? AND map_name = ? AND round_number = ?
    """, (round_date, map_name, rounds[1]))
    
    r2_axis = {}
    r2_allies = {}
    
    for guid, name, team in cursor.fetchall():
        if team == 1:
            r2_axis[guid] = name
        else:
            r2_allies[guid] = name
    
    print(f"\n🔴 Round 2 AXIS ({len(r2_axis)} players):")
    for guid, name in sorted(r2_axis.items(), key=lambda x: x[1]):
        print(f"   - {name:<30} ({guid})")
    
    print(f"\n🔵 Round 2 ALLIES ({len(r2_allies)} players):")
    for guid, name in sorted(r2_allies.items(), key=lambda x: x[1]):
        print(f"   - {name:<30} ({guid})")
    
    # Verify stopwatch swap
    r1_axis_guids = set(r1_axis.keys())
    r1_allies_guids = set(r1_allies.keys())
    r2_axis_guids = set(r2_axis.keys())
    r2_allies_guids = set(r2_allies.keys())
    
    if r1_axis_guids == r2_allies_guids and r1_allies_guids == r2_axis_guids:
        print(f"\n✅ PERFECT STOPWATCH SWAP!")
        team_a_guids = r1_axis_guids
        team_b_guids = r1_allies_guids
    else:
        print(f"\n⚠️  Not a perfect swap - using Round 1 as baseline")
        team_a_guids = r1_axis_guids
        team_b_guids = r1_allies_guids
    
    # Get all player names
    all_names = {**r1_axis, **r1_allies, **r2_axis, **r2_allies}
    
    return {
        'team_a': team_a_guids,
        'team_b': team_b_guids,
        'names': all_names,
        'map': map_name
    }


def detect_session_teams(round_date: str):
    """Detect teams across all maps in a session."""
    
    conn = sqlite3.connect('bot/etlegacy_production.db')
    cursor = conn.cursor()
    
    print("="*80)
    print(f"SESSION TEAM DETECTION: {round_date}")
    print("="*80)
    
    # Get all maps
    cursor.execute("""
        SELECT DISTINCT map_name
        FROM player_comprehensive_stats
        WHERE round_date = ?
    """, (round_date,))
    
    maps = [row[0] for row in cursor.fetchall()]
    print(f"\nMaps in session: {len(maps)}")
    for map_name in maps:
        print(f"  - {map_name}")
    
    # Detect teams for each map
    map_results = []
    for map_name in maps:
        result = detect_teams_for_map(cursor, round_date, map_name)
        if result:
            map_results.append(result)
    
    if not map_results:
        print("\n❌ No valid team detection results")
        conn.close()
        return
    
    # Find consistent teams across maps
    print(f"\n{'='*80}")
    print("CROSS-MAP TEAM CONSISTENCY")
    print(f"{'='*80}")
    
    # Use first map as baseline
    baseline = map_results[0]
    team_a_guids = baseline['team_a']
    team_b_guids = baseline['team_b']
    
    print(f"\nBaseline from {baseline['map']}:")
    print(f"  Team A: {len(team_a_guids)} players")
    print(f"  Team B: {len(team_b_guids)} players")
    
    # Check consistency across other maps
    for result in map_results[1:]:
        map_team_a = result['team_a']
        map_team_b = result['team_b']
        
        # Check if teams match (accounting for possible A/B label swap)
        if map_team_a == team_a_guids and map_team_b == team_b_guids:
            print(f"  {result['map']:<30} ✅ Same teams")
        elif map_team_a == team_b_guids and map_team_b == team_a_guids:
            print(f"  {result['map']:<30} ✅ Same teams (labels swapped)")
        else:
            print(f"  {result['map']:<30} ⚠️  Different roster")
    
    # Final team summary
    print(f"\n{'='*80}")
    print("FINAL TEAM ROSTERS")
    print(f"{'='*80}")
    
    all_names = baseline['names']
    
    print(f"\n🏆 TEAM A ({len(team_a_guids)} players):")
    for guid in sorted(team_a_guids, key=lambda g: all_names.get(g, '')):
        name = all_names.get(guid, 'Unknown')
        print(f"   - {name:<30} ({guid})")
    
    print(f"\n🏆 TEAM B ({len(team_b_guids)} players):")
    for guid in sorted(team_b_guids, key=lambda g: all_names.get(g, '')):
        name = all_names.get(guid, 'Unknown')
        print(f"   - {name:<30} ({guid})")
    
    conn.close()
    
    return {
        'team_a': team_a_guids,
        'team_b': team_b_guids,
        'names': all_names
    }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python correct_team_detector.py <round_date>")
        print("Example: python correct_team_detector.py 2024-10-28")
        sys.exit(1)
    
    round_date = sys.argv[1]
    result = detect_session_teams(round_date)
