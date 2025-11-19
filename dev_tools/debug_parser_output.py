"""
Debug script to check what the parser actually returns for weapon stats
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'bot'))

from community_stats_parser import C0RNP0RN3StatsParser

# Parse first Round 1 file
parser = C0RNP0RN3StatsParser()
result = parser.parse_stats_file('local_stats/2025-11-02-211530-etl_adlernest-round-1.txt')

if result and result.get('success'):
    print("SUCCESS! Parsed Round 1 file")
    print(f"Map: {result['map_name']}")
    print(f"Players: {len(result['players'])}")
    
    # Find carniee
    carniee = next((p for p in result['players'] if 'carniee' in p['name']), None)
    if carniee:
        print(f"\ncarniee ({carniee['guid']}):")
        print(f"  Headshots: {carniee.get('headshots', 'NOT FOUND')}")
        print(f"  Kills: {carniee.get('kills')}")
        print(f"  Deaths: {carniee.get('deaths')}")
        print(f"\n  ALL Weapon stats ({len(carniee.get('weapon_stats', {}))} total):")
        for weapon, stats in sorted(carniee.get('weapon_stats', {}).items()):
            print(f"    {weapon:20s} K:{stats.get('kills', 0):2d} D:{stats.get('deaths', 0):2d} HS:{stats.get('headshots', 0):2d} H:{stats.get('hits', 0):3d} S:{stats.get('shots', 0):3d}")
        
        # Check if MP40 is present
        mp40 = carniee.get('weapon_stats', {}).get('WS_MP40')
        if mp40:
            print(f"\n  WS_MP40 details:")
            print(f"    kills: {mp40.get('kills')}")
            print(f"    deaths: {mp40.get('deaths')}")
            print(f"    headshots: {mp40.get('headshots')}")
            print(f"    hits: {mp40.get('hits')}")
            print(f"    shots: {mp40.get('shots')}")
        else:
            print(f"\n  WS_MP40: NOT IN PARSER OUTPUT")
            
        # Total headshots from all weapons
        total_headshots = sum(w.get('headshots', 0) for w in carniee.get('weapon_stats', {}).values())
        print(f"\n  Total headshots from weapons: {total_headshots}")
        print(f"  Player-level headshots: {carniee.get('headshots')}")
        
        if total_headshots != carniee.get('headshots'):
            print(f"  ⚠️  MISMATCH! Weapon sum ({total_headshots}) != player level ({carniee.get('headshots')})")
else:
    print("FAILED to parse")
