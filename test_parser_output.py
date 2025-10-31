import sys
import glob
sys.path.insert(0, 'bot')

from community_stats_parser import C0RNP0RN3StatsParser

parser = C0RNP0RN3StatsParser()

# Get a recent file from local_stats
test_file = "local_stats/2025-01-01-211921-etl_adlernest-round-1.txt"

print("=" * 80)
print(f"PARSING TEST FILE: {test_file}")
print("=" * 80)
print()

result = parser.parse_stats_file(test_file)

if result and result.get('players'):
    player = result['players'][0]
    
    print(f"PLAYER: {player['name']}")
    print(f"Kills: {player.get('kills', 0)}")
    print(f"Deaths: {player.get('deaths', 0)}")
    print()
    
    obj_stats = player.get('objective_stats', {})
    
    print("OBJECTIVE_STATS DICTIONARY:")
    print("-" * 80)
    for key in sorted(obj_stats.keys()):
        value = obj_stats[key]
        print(f"  {key:<30} = {value}")
    
    print()
    print("=" * 80)
    print("CHECKING SPECIFIC FIELDS:")
    print("=" * 80)
    print(f"  times_revived: {obj_stats.get('times_revived', 'NOT FOUND')}")
    print(f"  dynamites_planted: {obj_stats.get('dynamites_planted', 'NOT FOUND')}")
    print(f"  kill_assists: {obj_stats.get('kill_assists', 'NOT FOUND')}")
    print(f"  useful_kills: {obj_stats.get('useful_kills', 'NOT FOUND')}")
    print(f"  useless_kills: {obj_stats.get('useless_kills', 'NOT FOUND')}")
    print(f"  denied_playtime: {obj_stats.get('denied_playtime', 'NOT FOUND')}")
    print(f"  repairs_constructions: {obj_stats.get('repairs_constructions', 'NOT FOUND')}")
else:
    print("ERROR: No players found in file!")
