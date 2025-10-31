#!/usr/bin/env python3
import sys

from community_stats_parser import C0RNP0RN3StatsParser

sys.path.insert(0, 'bot')

p = C0RNP0RN3StatsParser()
r = p.parse_stats_file('local_stats/2025-10-02-214239-supply-round-2.txt')

print(f"\nFile: 2025-10-02-214239-supply-round-2.txt")
print(f"Success: {r['success']}")
print(f"Round: {r['round_num']}")
print(f"Players: {r['total_players']}\n")

vid = [pl for pl in r['players'] if 'vid' in pl['name']]
if vid:
    v = vid[0]
    print(f"VID Data:")
    print(f"  time_played_seconds: {v.get('time_played_seconds', 'NOT FOUND')}")
    print(f"  time_display: {v.get('time_display', 'NOT FOUND')}")
    print(f"  damage_given: {v.get('damage_given', 0)}")
    print(f"  dpm: {v.get('dpm', 'NOT FOUND')}")
    obj = v.get('objective_stats', {})
    print(f"  objective_stats keys: {list(obj.keys())[:5]}")
    print(f"  objective_stats time_played_minutes: {obj.get('time_played_minutes', 'NOT FOUND')}")
else:
    print("vid not found!")
