"""
Verify objective_stats nested dictionary has correct values
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
print("VID'S OBJECTIVE_STATS DICTIONARY:")
print("=" * 80)

obj_stats = vid_data['objective_stats']
for key, value in sorted(obj_stats.items()):
    print(f"{key:30s} = {value}")

print("\n" + "=" * 80)
print("CRITICAL FIELD VERIFICATION:")
print("=" * 80)

# Expected values
expected = {
    'damage_given': 1328,
    'damage_received': 1105,
    'gibs': 3,  # ← CRITICAL: This should be 3, not 18!
    'xp': 48,
    'kill_assists': 1,
    'times_revived': 1,
}

print("\nField                          | Expected | Parser   | Status")
print("-" * 70)
all_correct = True
for field, exp_value in expected.items():
    parser_value = obj_stats.get(field, 'NOT_FOUND')
    status = "✅" if parser_value == exp_value else "❌"
    if parser_value != exp_value:
        all_correct = False
    print(f"{field:30s} | {exp_value:8} | {parser_value:8} | {status}")

if all_correct:
    print("\n✅ ALL CRITICAL FIELDS CORRECT!")
    print("Parser is now reading from correct field positions.")
else:
    print("\n❌ SOME FIELDS STILL WRONG!")
    print("Need to fix parser field mappings.")
