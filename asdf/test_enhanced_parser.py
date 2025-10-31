#!/usr/bin/env python3
"""
Test the enhanced parser with Round 2 differential calculation
"""

import sys
import os

# Add the bot directory to the path so we can import the parser
sys.path.append(os.path.join(os.path.dirname(__file__), 'bot'))

from community_stats_parser import C0RNP0RN3StatsParser

def test_differential_calculation():
    """Test the differential calculation with te_escape2 Round 1/2 pair"""
    parser = C0RNP0RN3StatsParser()
    
    # Test Round 1 file (should parse normally)
    round_1_file = "local_stats/2024-03-24-212616-te_escape2-round-1.txt"
    round_2_file = "local_stats/2024-03-24-213050-te_escape2-round-2.txt"
    
    print("=== Testing Enhanced Parser with Differential Calculation ===")
    print()
    
    # Test Round 1 (should be normal parsing)
    print("🔍 Testing Round 1 file parsing...")
    r1_result = parser.parse_stats_file(round_1_file)
    print(f"   Success: {r1_result['success']}")
    print(f"   Map: {r1_result['map_name']} Round {r1_result['round_num']}")
    print(f"   Players: {r1_result['total_players']}")
    print()
    
    # Test Round 2 (should trigger differential calculation)
    print("🔍 Testing Round 2 file parsing with differential calculation...")
    r2_result = parser.parse_stats_file(round_2_file)
    print(f"   Success: {r2_result['success']}")
    print(f"   Map: {r2_result['map_name']} Round {r2_result['round_num']}")
    print(f"   Players: {r2_result['total_players']}")
    print(f"   Differential calculation used: {r2_result.get('differential_calculation', False)}")
    print()
    
    # Find carniee in both rounds for comparison
    carniee_r1 = next((p for p in r1_result['players'] if p['name'] == 'carniee'), None)
    carniee_r2 = next((p for p in r2_result['players'] if p['name'] == 'carniee'), None)
    
    if carniee_r1 and carniee_r2:
        print("🎯 carniee Stats Comparison:")
        print(f"   Round 1: {carniee_r1['kills']} kills, {carniee_r1['damage_given']} damage, {carniee_r1['dpm']:.1f} DPM")
        print(f"   Round 2 (differential): {carniee_r2['kills']} kills, {carniee_r2['damage_given']} damage, {carniee_r2['dpm']:.1f} DPM")
        print()
        
        # Show expected vs actual based on our hypothesis testing
        print("📊 Expected vs Actual (based on cumulative hypothesis):")
        print("   Expected Round 2-only: ~7 kills, ~954 damage")
        print(f"   Actual Round 2-only: {carniee_r2['kills']} kills, {carniee_r2['damage_given']} damage")
        
        if carniee_r2['kills'] >= 5 and carniee_r2['kills'] <= 10:
            print("   ✅ Kill count looks realistic for Round 2-only!")
        else:
            print("   ❌ Kill count seems off for Round 2-only")
            
        if carniee_r2['damage_given'] >= 500 and carniee_r2['damage_given'] <= 1500:
            print("   ✅ Damage amount looks realistic for Round 2-only!")
        else:
            print("   ❌ Damage amount seems off for Round 2-only")
    else:
        print("❌ Could not find carniee in both rounds for comparison")
    
    print()
    print("🏆 Top 3 Players - Round 2 ONLY Stats:")
    sorted_players = sorted(r2_result['players'], key=lambda x: x['dpm'], reverse=True)
    for i, player in enumerate(sorted_players[:3], 1):
        dpm = player['dpm']
        print(f"   {i}. {player['name']}: {player['kills']}K/{player['deaths']}D | {player['damage_given']} DMG | {dpm:.1f} DPM")
        
        # Check if DPM is in realistic range
        if 100 <= dpm <= 1000:
            print("      ✅ DPM is in realistic range!")
        else:
            print(f"      ⚠️ DPM might be off (expected 100-1000, got {dpm:.1f})")
    
    return r1_result, r2_result

if __name__ == "__main__":
    test_differential_calculation()