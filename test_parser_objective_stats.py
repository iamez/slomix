#!/usr/bin/env python3
"""Test if parser extracts objective stats correctly from Oct 2nd files"""

from bot.community_stats_parser import C0RNP0RN3StatsParser

# Parse one of the Oct 2nd files
parser = C0RNP0RN3StatsParser()
result = parser.parse_stats_file('local_stats/2025-10-02-223755-sw_goldrush_te-round-2.txt')

print(f"\n=== PARSER TEST ===")
print(f"Parsed {len(result['players'])} players")
print(f"Map: {result.get('map_name')}")
print(f"Date: {result.get('session_date')}")

# Check vid (second player)
player = result['players'][1]
print(f"\n--- Player: {player['name']} ---")
obj_stats = player.get('objective_stats', {})

print(f"objective_stats dict exists: {obj_stats is not None}")
print(f"objective_stats keys: {len(obj_stats.keys() if obj_stats else 0)}")

if obj_stats:
    print(f"\nKey values:")
    print(f"  damage_given: {obj_stats.get('damage_given')}")
    print(f"  gibs: {obj_stats.get('gibs')}")
    print(f"  xp: {obj_stats.get('xp')}")
    print(f"  kill_assists: {obj_stats.get('kill_assists')}")
    print(f"  times_revived: {obj_stats.get('times_revived')}")
    print(f"  dynamites_planted: {obj_stats.get('dynamites_planted')}")
    print(f"  dynamites_defused: {obj_stats.get('dynamites_defused')}")
else:
    print("ERROR: No objective_stats dictionary!")

# Check if additional_stats exists (old format fallback)
add_stats = player.get('additional_stats', {})
print(f"\nadditional_stats exists: {add_stats is not None}")
if add_stats:
    print(f"  damage_given: {add_stats.get('damage_given')}")
    print(f"  gibs: {add_stats.get('gibs')}")
