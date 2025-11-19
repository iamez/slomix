"""
Direct test without parser print statements
"""
import sys
sys.path.insert(0, 'bot')

# Temporarily disable print
import builtins
original_print = builtins.print
def silent_print(*args, **kwargs):
    pass
builtins.print = silent_print

from community_stats_parser import C0RNP0RN3StatsParser

parser = C0RNP0RN3StatsParser()

# Restore print
builtins.print = original_print

# Test files
files_to_test = [
    ('bot/local_stats/2025-11-01-221036-sw_goldrush_te-round-2.txt', 'Nov 1 same-date'),
    ('bot/local_stats/2025-11-02-000624-etl_adlernest-round-2.txt', 'Nov 2 midnight'),
]

for filepath, label in files_to_test:
    print(f"\n{'=' * 80}")
    print(f"{label}: {filepath.split('/')[-1]}")
    print("=" * 80)
    
    try:
        result = parser.parse_stats_file(filepath)
        if result and 'players' in result and len(result['players']) > 0:
            p = result['players'][0]
            print(f"  Player: {p.get('name', 'Unknown')}")
            print(f"  Kills/Deaths: {p.get('kills')}/{p.get('deaths')}")
            print(f"  Top-level accuracy: {p.get('accuracy')}")
            
            obj = p.get('objective_stats', {})
            print(f"  obj_stats.accuracy: {obj.get('accuracy', 'NOT_FOUND')}")
            print(f"  obj_stats.time_dead_minutes: {obj.get('time_dead_minutes')}")
            print(f"  obj_stats.time_dead_ratio: {obj.get('time_dead_ratio')}")
            print(f"  obj_stats.headshot_kills: {obj.get('headshot_kills')}")
            print(f"  obj_stats.revives_given: {obj.get('revives_given')}")
        else:
            print("  ERROR: No players found")
    except Exception as e:
        print(f"  ERROR: {e}")
