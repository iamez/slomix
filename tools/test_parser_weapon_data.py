#!/usr/bin/env python3
"""Test what weapon data the parser provides"""
import sys

from community_stats_parser import C0RNP0RN3StatsParser

sys.path.insert(0, 'bot')

parser = C0RNP0RN3StatsParser()
result = parser.parse_stats_file('local_stats/2025-10-02-211808-etl_adlernest-round-1.txt')

# Find vid
player = [p for p in result['players'] if 'vid' in p['name'].lower()][0]

print("=" * 80)
print("PARSER WEAPON DATA CHECK")
print("=" * 80)
print(f"\nPlayer: {player['name']}")
print(f"\nAll player keys:")
for key in sorted(player.keys()):
    print(f"  • {key}")

print(f"\n🔫 Weapon stats available: {'weapon_stats' in player}")

if 'weapon_stats' in player:
    print(f"\nWeapons found: {len(player['weapon_stats'])}")
    print("\nSample weapon data:")
    for weapon_name, stats in list(player['weapon_stats'].items())[:3]:
        print(f"\n  {weapon_name}:")
        for stat_key, value in stats.items():
            print(f"    {stat_key}: {value}")
