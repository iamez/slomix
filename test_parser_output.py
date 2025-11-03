"""
Test what the parser actually returns for a recent stats file
"""
import sys
sys.path.insert(0, 'bot')  # Use the bot version
from community_stats_parser import C0RNP0RN3StatsParser

# Parse the most recent file
parser = C0RNP0RN3StatsParser()
result = parser.parse_stats_file('bot/local_stats/2025-11-02-000624-etl_adlernest-round-2.txt')

print("📊 Parser Result Structure:")
print("=" * 80)
print(f"Map: {result.get('map_name')}")
print(f"Round: {result.get('round_num')}")
print(f"Players: {len(result.get('players', []))}")

print("\n🔍 First Player Data Structure:")
print("=" * 80)
if result.get('players'):
    player = result['players'][0]
    print(f"Player Name: {player.get('name')}")
    print(f"\nTop-level keys: {list(player.keys())}")
    
    print(f"\n📋 Player direct fields:")
    for key in ['kills', 'deaths', 'damage_given', 'damage_received', 'team', 'guid', 'accuracy']:
        print(f"  {key}: {player.get(key, 'NOT FOUND')}")
    
    print(f"\n📋 objective_stats keys:")
    obj_stats = player.get('objective_stats', {})
    if obj_stats:
        print(f"  Keys available: {list(obj_stats.keys())}")
        print(f"\n  Critical fields:")
        for key in ['headshot_kills', 'revives_given', 'team_damage_given', 'team_damage_received', 'gibs', 'time_dead_minutes', 'bullets_fired']:
            val = obj_stats.get(key, 'NOT FOUND')
            print(f"    {key}: {val}")
    else:
        print("  ⚠️ objective_stats is EMPTY or missing!")
    
    print(f"\n📋 weapon_stats:")
    weapon_stats = player.get('weapon_stats', {})
    if weapon_stats:
        print(f"  {len(weapon_stats)} weapons found")
        # Show first weapon
        first_weapon = list(weapon_stats.keys())[0] if weapon_stats else None
        if first_weapon:
            print(f"  Example: {first_weapon} = {weapon_stats[first_weapon]}")
    else:
        print("  No weapon stats")

print("\n\n🔍 Second Player for Comparison:")
print("=" * 80)
if len(result.get('players', [])) > 1:
    player2 = result['players'][1]
    print(f"Player Name: {player2.get('name')}")
    obj_stats2 = player2.get('objective_stats', {})
    print(f"\nObjective Stats:")
    for key in ['headshot_kills', 'revives_given', 'team_damage_given', 'gibs']:
        val = obj_stats2.get(key, 'NOT FOUND')
        print(f"  {key}: {val}")
