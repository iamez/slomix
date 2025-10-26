#!/usr/bin/env python3
"""
Test the cumulative stats hypothesis with actual round files
"""
import sys
sys.path.append('./bot')

from community_stats_parser import C0RNP0RN3StatsParser

def test_cumulative_hypothesis():
    """Test if Round 2 stats are cumulative (Round 1 + Round 2)"""
    
    print("🔍 TESTING CUMULATIVE STATS HYPOTHESIS")
    print("=" * 50)
    
    parser = C0RNP0RN3StatsParser()
    
    # Test with te_escape2 pair
    r1_file = "./test_files/2025-09-24-233255-te_escape2-round-1.txt"
    r2_file = "./test_files/2025-09-24-233657-te_escape2-round-2.txt"
    
    print(f"📁 Round 1: {r1_file}")
    print(f"📁 Round 2: {r2_file}")
    print()
    
    # Parse both files
    r1_data = parser.parse_stats_file(r1_file)
    r2_data = parser.parse_stats_file(r2_file)
    
    if not (r1_data['success'] and r2_data['success']):
        print("❌ Failed to parse files")
        return
    
    print(f"⏱️  Round 1 time: {r1_data['actual_time']}")
    print(f"⏱️  Round 2 time: {r2_data['actual_time']}")
    print(f"🗺️  Map: {r1_data['map_name']}")
    print()
    
    # Create player lookup by GUID
    r1_players = {p['guid']: p for p in r1_data['players']}
    r2_players = {p['guid']: p for p in r2_data['players']}
    
    # Find common players
    common_guids = set(r1_players.keys()) & set(r2_players.keys())
    print(f"👥 Common players: {len(common_guids)}")
    print()
    
    print("🧪 CUMULATIVE TEST RESULTS:")
    print("=" * 40)
    
    cumulative_count = 0
    differential_count = 0
    
    for guid in list(common_guids)[:5]:  # Test first 5 players
        r1_player = r1_players[guid]
        r2_player = r2_players[guid]
        
        name = r1_player['name']
        r1_kills = r1_player.get('kills', 0)
        r2_kills = r2_player.get('kills', 0)
        r1_damage = r1_player.get('damage_given', 0)
        r2_damage = r2_player.get('damage_given', 0)
        r1_deaths = r1_player.get('deaths', 0)
        r2_deaths = r2_player.get('deaths', 0)
        
        print(f"👤 {name}")
        print(f"   Kills:  R1={r1_kills:2d} → R2={r2_kills:2d} (diff: {r2_kills-r1_kills:+d})")
        print(f"   Deaths: R1={r1_deaths:2d} → R2={r2_deaths:2d} (diff: {r2_deaths-r1_deaths:+d})")
        print(f"   Damage: R1={r1_damage:4d} → R2={r2_damage:4d} (diff: {r2_damage-r1_damage:+d})")
        
        # Test cumulative hypothesis
        if (r2_kills >= r1_kills and r2_deaths >= r1_deaths and r2_damage >= r1_damage and 
            (r2_kills > 0 or r2_deaths > 0 or r2_damage > 0)):
            print("   📊 CUMULATIVE CONFIRMED ✅")
            cumulative_count += 1
        else:
            print("   📊 Not cumulative ❌")
            differential_count += 1
            
        print()
    
    print("🎯 HYPOTHESIS TEST RESULTS:")
    print(f"   Cumulative indicators: {cumulative_count}")
    print(f"   Differential indicators: {differential_count}")
    
    if cumulative_count > differential_count:
        print("   🚨 CUMULATIVE BUG CONFIRMED!")
        print("   Round 2 stats include Round 1 stats")
        print("   Need to apply differential calculation")
    else:
        print("   ✅ Stats appear to be differential already")
    
    print()
    print("🧮 DPM ANALYSIS:")
    
    # Test DPM calculation with cumulative vs differential
    first_guid = next(iter(common_guids))
    r1p = r1_players[first_guid]
    r2p = r2_players[first_guid]
    
    r1_time_sec = parser.parse_time_to_seconds(r1_data['actual_time'])
    r2_time_sec = parser.parse_time_to_seconds(r2_data['actual_time'])
    
    print(f"Example player: {r1p['name']}")
    print(f"  R1: {r1p['damage_given']} damage in {r1_time_sec}s = {r1p.get('dpm', 0):.1f} DPM")
    print(f"  R2: {r2p['damage_given']} damage in {r2_time_sec}s = {r2p.get('dpm', 0):.1f} DPM")
    
    if cumulative_count > 0:
        # Calculate what R2-only DPM should be
        r2_only_damage = r2p['damage_given'] - r1p['damage_given']
        r2_only_time_sec = r2_time_sec - r1_time_sec
        r2_only_dpm = (r2_only_damage / (r2_only_time_sec / 60.0)) if r2_only_time_sec > 0 else 0
        
        print(f"  R2-only: {r2_only_damage} damage in {r2_only_time_sec}s = {r2_only_dpm:.1f} DPM")
        print(f"  Combined: {r2p['damage_given']} damage in {r2_time_sec}s = {r2p['damage_given']/(r2_time_sec/60.0):.1f} DPM")

if __name__ == "__main__":
    test_cumulative_hypothesis()