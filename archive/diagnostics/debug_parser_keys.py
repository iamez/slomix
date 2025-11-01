"""
Debug: Show ALL keys that parser returns for vid
"""

import sys

from community_stats_parser import C0RNP0RN3StatsParser

sys.path.insert(0, 'bot')

test_file = "local_stats/2025-10-02-211808-etl_adlernest-round-1.txt"
parser = C0RNP0RN3StatsParser()
result = parser.parse_stats_file(test_file)

# Find vid's data
vid_data = None
for player in result['players']:
    if player['name'] == 'vid':
        vid_data = player
        break

print("=" * 80)
print("ALL KEYS IN VID'S PARSER OUTPUT:")
print("=" * 80)
for key, value in sorted(vid_data.items()):
    print(f"{key:30s} = {value}")
