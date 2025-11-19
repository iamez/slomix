"""
Check what accuracy value the parser returns for Round 2 differential
"""
import sys
sys.path.insert(0, 'bot')
from community_stats_parser import C0RNP0RN3StatsParser

parser = C0RNP0RN3StatsParser()

# Test a Nov 1 file (should work)
print("=" * 80)
print("TEST 1: Nov 1st file (same date, should work)")
print("=" * 80)
result1 = parser.parse_stats_file('bot/local_stats/2025-11-01-221036-sw_goldrush_te-round-2.txt')
p1 = result1['players'][0]
print(f"Player: {p1.get('name')}")
print(f"Top-level 'accuracy': {p1.get('accuracy')}")
print(f"objective_stats 'accuracy': {p1.get('objective_stats', {}).get('accuracy', 'NOT FOUND')}")
print(f"objective_stats 'time_dead_minutes': {p1.get('objective_stats', {}).get('time_dead_minutes')}")
print(f"objective_stats 'time_dead_ratio': {p1.get('objective_stats', {}).get('time_dead_ratio')}")

print("\n" + "=" * 80)
print("TEST 2: Nov 2nd file (midnight boundary)")
print("=" * 80)
result2 = parser.parse_stats_file('bot/local_stats/2025-11-02-000624-etl_adlernest-round-2.txt')
p2 = result2['players'][0]
print(f"Player: {p2.get('name')}")
print(f"Top-level 'accuracy': {p2.get('accuracy')}")
print(f"objective_stats 'accuracy': {p2.get('objective_stats', {}).get('accuracy', 'NOT FOUND')}")
print(f"objective_stats 'time_dead_minutes': {p2.get('objective_stats', {}).get('time_dead_minutes')}")
print(f"objective_stats 'time_dead_ratio': {p2.get('objective_stats', {}).get('time_dead_ratio')}")
