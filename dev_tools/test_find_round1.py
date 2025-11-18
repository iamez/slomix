import sys
sys.path.insert(0, 'bot')
from community_stats_parser import C0RNP0RN3StatsParser
import os

parser = C0RNP0RN3StatsParser()

# Test the find function directly
round_2_path = 'bot/local_stats/2025-11-02-000624-etl_adlernest-round-2.txt'
found = parser.find_corresponding_round_1_file(round_2_path)

print(f"Round 2 file: {os.path.basename(round_2_path)}")
print(f"Found Round 1: {found}")
if found:
    print(f"Round 1 basename: {os.path.basename(found)}")
