#!/usr/bin/env python3
"""
Test differential calculation with specific supply files
"""

from pathlib import Path
from community_stats_parser import C0RNP0RN3StatsParser

def test_supply_differential():
    """Test the cumulative issue with specific supply round files"""
    parser = C0RNP0RN3StatsParser()
    
    # Use the specific files we know exist
    round1_file = "stats_cache/2025-09-30-213510-supply-round-1.txt"
    round2_file = "stats_cache/2025-09-30-214828-supply-round-2.txt"
    
    print(f"🔍 Testing with:")
    print(f"   Round 1: {round1_file}")
    print(f"   Round 2: {round2_file}")
    
    # Parse both files
    round1_data = parser.parse_stats_file(round1_file)
    round2_data = parser.parse_stats_file(round2_file)
    
    if not (round1_data['success'] and round2_data['success']):
        print("❌ Failed to parse files")
        return
    
    print(f"📊 Round 1: {len(round1_data['players'])} players")
    print(f"📊 Round 2: {len(round2_data['players'])} players")
    print(f"🗺️  Map: {round1_data['map_name']} vs {round2_data['map_name']}")
    
    # Debug: Show available keys
    print(f"🔑 Round 1 keys: {list(round1_data.keys())}")
    print(f"🔑 Round 2 keys: {list(round2_data.keys())}")
    
    # Get duration info from actual_time field and convert to float
    r1_duration_str = round1_data.get('actual_time', '0:00')
    r2_duration_str = round2_data.get('actual_time', '0:00')
    
    # Convert MM:SS to decimal minutes
    def time_to_minutes(time_str):
        if ':' in time_str:
            minutes, seconds = time_str.split(':')
            return float(minutes) + float(seconds) / 60.0
        return float(time_str)
    
    r1_duration = time_to_minutes(r1_duration_str)
    r2_duration = time_to_minutes(r2_duration_str)
    
    print(f"⏱️  Round 1 Duration: {r1_duration:.1f} min ({r1_duration_str})")
    print(f"⏱️  Round 2 Duration: {r2_duration:.1f} min ({r2_duration_str})")
    
    # Find common players and show the cumulative issue
    print("\n🔍 Checking for cumulative stats bug:")
    
    # Convert player lists to dictionaries for easier comparison
    r1_players = {p['name']: p for p in round1_data['players']}
    r2_players = {p['name']: p for p in round2_data['players']}
    
    # Show player names first
    print(f"Round 1 players: {list(r1_players.keys())}")
    print(f"Round 2 players: {list(r2_players.keys())}")
    
    # Show all players briefly
    print(f"\n📊 All players comparison:")
    for player_name in r1_players:
        if player_name in r2_players:
            r1 = r1_players[player_name]
            r2 = r2_players[player_name]
            diff = r2['damage_given'] - r1['damage_given']
            print(f"   {player_name[:20]}: R1={r1['damage_given']:,} → R2={r2['damage_given']:,} (+{diff:,})")
            
            # Check if CLEARLY cumulative
            if r2['damage_given'] > r1['damage_given']:
                print(f"      ✅ CUMULATIVE CONFIRMED!")
            else:
                print(f"      ⚠️  Not cumulative?")

if __name__ == "__main__":
    test_supply_differential()