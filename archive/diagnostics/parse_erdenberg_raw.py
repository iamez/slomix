#!/usr/bin/env python3
"""Parse the raw Erdenberg files to see what really happened"""

import sys
sys.path.insert(0, '.')

from bot.community_stats_parser import C0RNP0RN3StatsParser

parser = C0RNP0RN3StatsParser()

print('\n' + '='*80)
print('RAW FILE ANALYSIS - Erdenberg October 2')
print('='*80)

# Parse Round 1
print('\n📄 ROUND 1 FILE: 2025-10-02-232339-erdenberg_t2-round-1.txt')
print('='*80)

r1 = parser.parse_stats_file('local_stats/2025-10-02-232339-erdenberg_t2-round-1.txt')

if r1.get('success'):
    print(f"\nMap: {r1['map_name']} Round {r1['round_num']}")
    print(f"Time: {r1['actual_time']}")
    print(f"Players: {len(r1['players'])}\n")
    
    for p in r1['players']:
        clean_name = parser.strip_color_codes(p['name'])
        print(f"  {clean_name:20s} GUID: {p['guid']} K/D: {p['kills']}/{p['deaths']} Damage: {p['damage_given']}")
        
        if 'olz' in clean_name.lower():
            print(f"    ⭐ OLZ FOUND IN ROUND 1! ⭐")

# Parse Round 2
print('\n\n📄 ROUND 2 FILE: 2025-10-02-232818-erdenberg_t2-round-2.txt')
print('='*80)

r2 = parser.parse_stats_file('local_stats/2025-10-02-232818-erdenberg_t2-round-2.txt')

if r2.get('success'):
    print(f"\nMap: {r2['map_name']} Round {r2['round_num']}")
    print(f"Time: {r2['actual_time']}")
    print(f"Players: {len(r2['players'])}\n")
    
    for p in r2['players']:
        clean_name = parser.strip_color_codes(p['name'])
        print(f"  {clean_name:20s} GUID: {p['guid']} K/D: {p['kills']}/{p['deaths']} Damage: {p['damage_given']}")
        
        if 'olz' in clean_name.lower():
            print(f"    ⭐ OLZ FOUND IN ROUND 2! ⭐")

# Compare
print('\n' + '='*80)
print('🐛 BUG INVESTIGATION')
print('='*80)

if r1.get('success') and r2.get('success'):
    r1_players = {parser.strip_color_codes(p['name']) for p in r1['players']}
    r2_players = {parser.strip_color_codes(p['name']) for p in r2['players']}
    
    print(f"\nRound 1 players: {r1_players}")
    print(f"Round 2 players: {r2_players}")
    
    # Check for olz
    olz_in_r1 = any('olz' in name.lower() for name in r1_players)
    olz_in_r2 = any('olz' in name.lower() for name in r2_players)
    
    print(f"\n🔍 OLZ in Round 1 raw file: {'✅ YES' if olz_in_r1 else '❌ NO'}")
    print(f"🔍 OLZ in Round 2 raw file: {'✅ YES' if olz_in_r2 else '❌ NO'}")
    
    if olz_in_r1:
        print("\n🚨 BUG CONFIRMED!")
        print("   olz is in the Round 1 RAW FILE but NOT in the database!")
        print("   This is an IMPORT BUG!")
