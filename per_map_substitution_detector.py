"""
Per-Map Substitution Detection
================================
Analyzes each map separately for roster changes between rounds.
"""

import sqlite3
from collections import defaultdict

def analyze_map_substitutions(cursor, round_date: str, map_name: str):
    """Analyze substitutions for a single map."""
    
    print(f"\n{'='*80}")
    print(f"MAP: {map_name}")
    print(f"{'='*80}")
    
    # Get rounds
    cursor.execute("""
        SELECT DISTINCT round_number
        FROM player_comprehensive_stats
        WHERE round_date = ? AND map_name = ?
        ORDER BY round_number
    """, (round_date, map_name))
    
    rounds = [r[0] for r in cursor.fetchall()]
    
    if len(rounds) < 2:
        print(f"Only {len(rounds)} round - skipping substitution analysis")
        return
    
    print(f"Rounds: {rounds}\n")
    
    # Track player participation per round
    round_players = {}
    
    for round_num in rounds:
        cursor.execute("""
            SELECT DISTINCT player_guid, player_name
            FROM player_comprehensive_stats
            WHERE round_date = ? AND map_name = ? AND round_number = ?
        """, (round_date, map_name, round_num))
        
        round_players[round_num] = {row[0]: row[1] for row in cursor.fetchall()}
    
    # Show roster for each round
    for round_num in rounds:
        players = round_players[round_num]
        print(f"Round {round_num}: {len(players)} players")
        for guid, name in sorted(players.items(), key=lambda x: x[1]):
            print(f"   - {name:<30} ({guid})")
        print()
    
    # Analyze changes between consecutive rounds
    print("🔍 ROSTER CHANGES:\n")
    
    all_players = {}
    for players in round_players.values():
        all_players.update(players)
    
    for i in range(len(rounds) - 1):
        r1 = rounds[i]
        r2 = rounds[i + 1]
        
        r1_guids = set(round_players[r1].keys())
        r2_guids = set(round_players[r2].keys())
        
        departed = r1_guids - r2_guids
        joined = r2_guids - r1_guids
        stayed = r1_guids & r2_guids
        
        print(f"Round {r1} → Round {r2}:")
        print(f"   Stayed: {len(stayed)} players")
        
        if departed:
            print(f"   ❌ Left ({len(departed)}):")
            for guid in departed:
                print(f"      - {all_players[guid]}")
        
        if joined:
            print(f"   ➕ Joined ({len(joined)}):")
            for guid in joined:
                print(f"      - {all_players[guid]}")
        
        if not departed and not joined:
            print(f"   ✅ Stable roster - no changes")
        
        print()


def analyze_session_substitutions(round_date: str):
    """Analyze substitutions across all maps in a session."""
    
    conn = sqlite3.connect('bot/etlegacy_production.db')
    cursor = conn.cursor()
    
    print("="*80)
    print(f"SUBSTITUTION ANALYSIS: {round_date}")
    print("="*80)
    
    # Get all maps
    cursor.execute("""
        SELECT DISTINCT map_name
        FROM player_comprehensive_stats
        WHERE round_date = ?
    """, (round_date,))
    
    maps = [row[0] for row in cursor.fetchall()]
    print(f"\nMaps in session: {len(maps)}")
    
    # Analyze each map
    for map_name in maps:
        analyze_map_substitutions(cursor, round_date, map_name)
    
    # Session-wide player participation
    print("="*80)
    print("SESSION-WIDE PLAYER PARTICIPATION")
    print("="*80)
    
    # Track which maps each player participated in
    cursor.execute("""
        SELECT DISTINCT player_guid, player_name, map_name
        FROM player_comprehensive_stats
        WHERE round_date = ?
    """, (round_date,))
    
    player_maps = defaultdict(set)
    player_names = {}
    
    for guid, name, map_name in cursor.fetchall():
        player_maps[guid].add(map_name)
        player_names[guid] = name
    
    # Group by participation count
    by_map_count = defaultdict(list)
    for guid, maps_played in player_maps.items():
        by_map_count[len(maps_played)].append(guid)
    
    print(f"\nTotal unique players: {len(player_maps)}\n")
    
    for count in sorted(by_map_count.keys(), reverse=True):
        players = by_map_count[count]
        print(f"Played {count}/{len(maps)} map(s): {len(players)} player(s)")
        for guid in sorted(players, key=lambda g: player_names[g]):
            maps_str = ', '.join(sorted(player_maps[guid]))
            print(f"   - {player_names[guid]:<30} [{maps_str}]")
        print()
    
    conn.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python per_map_substitution_detector.py <round_date>")
        print("Example: python per_map_substitution_detector.py 2025-11-01")
        sys.exit(1)
    
    round_date = sys.argv[1]
    analyze_session_substitutions(round_date)
