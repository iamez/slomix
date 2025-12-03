#!/usr/bin/env python3
"""Test Round 2 parsing with actual matching Round 1/2 pair"""
from bot.community_stats_parser import C0RNP0RN3StatsParser

# Test with actual matching Round 1 and Round 2 files
print("=" * 70)
print("Testing Round 2 parsing with matching Round 1")
print("=" * 70)

parser = C0RNP0RN3StatsParser()
result = parser.parse_stats_file('local_stats/2025-10-12-225242-sw_goldrush_te-round-2.txt')

print("\n✅ Parsing complete!")
print(f"Map: {result.get('map_name', 'unknown')}")
print(f"Round: {result.get('round_num', '?')}")
print(f"Players: {len(result.get('players', []))}")

if result.get('error'):
    print(f"❌ Error: {result['error']}")
else:
    print("✅ No errors")

# Show some player stats
if result.get('players'):
    print("\nSample player stats:")
    for player in result['players'][:3]:
        print(f"  - {player['name']}: {player.get('kills', 0)} kills, {player.get('deaths', 0)} deaths")
