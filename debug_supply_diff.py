#!/usr/bin/env python3
import sys

from community_stats_parser import C0RNP0RN3StatsParser

sys.path.insert(0, 'bot')

p = C0RNP0RN3StatsParser()

# Parse R1
r1 = p.parse_regular_stats_file('local_stats/2025-10-02-213333-supply-round-1.txt')
vid_r1 = [pl for pl in r1['players'] if 'vid' in pl['name']][0]

# Parse R2
r2 = p.parse_regular_stats_file('local_stats/2025-10-02-214239-supply-round-2.txt')
vid_r2 = [pl for pl in r2['players'] if 'vid' in pl['name']][0]

print("\nR1 VID:")
print(f"  time_played_seconds: {vid_r1.get('time_played_seconds')}")
print(
    f"  objective_stats time_played_minutes: {
        vid_r1.get(
            'objective_stats',
            {}).get('time_played_minutes')}"
)

print("\nR2 CUMULATIVE VID:")
print(f"  time_played_seconds: {vid_r2.get('time_played_seconds')}")
print(
    f"  objective_stats time_played_minutes: {
        vid_r2.get(
            'objective_stats',
            {}).get('time_played_minutes')}"
)

print("\nDIFFERENTIAL:")
r1_time = vid_r1.get('objective_stats', {}).get('time_played_minutes', 0)
r2_time = vid_r2.get('objective_stats', {}).get('time_played_minutes', 0)
diff = max(0, r2_time - r1_time)
print(f"  R2 time: {r2_time}")
print(f"  R1 time: {r1_time}")
print(f"  Differential: {diff}")
print(f"  In seconds: {int(diff * 60)}")
