"""Check what fields the parser actually returns."""
import sys
sys.path.insert(0, 'bot')
from community_stats_parser import C0RNP0RN3StatsParser

# Parse a sample R1 file
parser = C0RNP0RN3StatsParser()
result = parser.parse_stats_file('local_stats/2025-11-02-211530-etl_adlernest-round-1.txt')

if result and result.get('players'):
    player = result['players'][0]
    
    print("=" * 80)
    print("PARSER OUTPUT FIELDS")
    print("=" * 80)
    print(f"\nTotal fields returned: {len(player.keys())}")
    print("\nField names:")
    for i, field in enumerate(sorted(player.keys()), 1):
        print(f"  {i:2}. {field}")
    
    print("\n" + "=" * 80)
    print("SAMPLE VALUES (first player)")
    print("=" * 80)
    for key in sorted(player.keys()):
        value = player[key]
        if isinstance(value, dict):
            print(f"\n{key}:")
            for sub_key, sub_val in value.items():
                print(f"    {sub_key}: {sub_val}")
        else:
            print(f"{key}: {value}")
    
    print("\n" + "=" * 80)
    print("DATABASE SCHEMA HAS THESE ADDITIONAL FIELDS:")
    print("=" * 80)
    db_only_fields = [
        'id', 'round_id', 'team_damage_given', 'team_damage_received',
        'team_kills', 'team_killed_by', 'useful_kills', 'useless_kills',
        'kill_steals', 'constructions', 'denied_playtime', 'tank_meatshield',
        'double_kills', 'triple_kills', 'quad_kills', 'multi_kills',
        'mega_kills', 'killing_spree_best', 'death_spree_worst',
        'objectives_assists', 'objectives_completed', 'objectives_destroyed',
        'objectives_stolen', 'objectives_returned', 'dynamites_planted',
        'dynamites_defused', 'revives', 'revived', 'health_packs', 'ammo_packs'
    ]
    
    parser_fields = set(player.keys())
    if 'objective_stats' in player:
        parser_fields.update(player['objective_stats'].keys())
    
    missing = []
    for field in db_only_fields:
        if field not in parser_fields:
            missing.append(field)
    
    print(f"\nFields in DB but NOT in parser output: {len(missing)}")
    for field in missing:
        print(f"  - {field}")
else:
    print("❌ Failed to parse file")
