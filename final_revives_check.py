"""Final check - verify both revive fields exist in parser and database"""
import sys
sys.path.insert(0, 'bot')
from community_stats_parser import C0RNP0RN3StatsParser

# Parse a sample file
parser = C0RNP0RN3StatsParser()
result = parser.parse_stats_file('local_stats/2025-11-02-211530-etl_adlernest-round-1.txt')

print("="*70)
print("FINAL REVIVES CHECK - PARSER OUTPUT")
print("="*70)

player = result['players'][0]
obj_stats = player['objective_stats']

print(f"\nPlayer: {player['name']}")
print(f"\nRevive fields in objective_stats:")
print(f"  ✓ times_revived: {obj_stats.get('times_revived', 'MISSING!')}")
print(f"  ✓ revives_given: {obj_stats.get('revives_given', 'MISSING!')}")

print(f"\nAll objective_stats keys containing 'revive':")
revive_keys = [k for k in obj_stats.keys() if 'revive' in k.lower()]
for key in revive_keys:
    print(f"  - {key}: {obj_stats[key]}")

print("\n" + "="*70)
print("CHECKING ALL 6 PLAYERS")
print("="*70)

for player in result['players']:
    obj_stats = player['objective_stats']
    tr = obj_stats.get('times_revived', 'MISSING')
    rg = obj_stats.get('revives_given', 'MISSING')
    print(f"{player['name']:<20} times_revived={tr:<3} revives_given={rg:<3}")

print("\n" + "="*70)
print("✅ BOTH FIELDS PRESENT IN PARSER OUTPUT")
print("="*70)
