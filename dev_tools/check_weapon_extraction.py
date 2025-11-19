#!/usr/bin/env python3
"""Check if parser extracts weapon stats"""
from bot.community_stats_parser import C0RNP0RN3StatsParser

parser = C0RNP0RN3StatsParser()
result = parser.parse_stats_file('local_stats/2025-10-12-220306-te_escape2-round-2.txt')

print("=" * 70)
print("CHECKING WEAPON STATS EXTRACTION")
print("=" * 70)

if result.get('players'):
    print(f"\nFound {len(result['players'])} players")
    
    for i, player in enumerate(result['players'][:3]):
        print(f"\n🎮 Player {i+1}: {player.get('name', 'unknown')}")
        print(f"   Kills: {player.get('kills', 0)}")
        print(f"   Deaths: {player.get('deaths', 0)}")
        
        weapons = player.get('weapons', {})
        if weapons:
            print(f"   ✅ Has {len(weapons)} weapons:")
            for weapon_name, weapon_data in list(weapons.items())[:3]:
                print(f"      - {weapon_name}: {weapon_data.get('kills', 0)} kills, {weapon_data.get('shots', 0)} shots")
        else:
            print(f"   ❌ NO WEAPON DATA!")
    
    # Check total
    total_players_with_weapons = sum(1 for p in result['players'] if p.get('weapons'))
    total_weapons = sum(len(p.get('weapons', {})) for p in result['players'])
    
    print(f"\n📊 Summary:")
    print(f"   Players with weapons: {total_players_with_weapons}/{len(result['players'])}")
    print(f"   Total weapons: {total_weapons}")
    
    if total_weapons == 0:
        print(f"\n❌ PROBLEM: No weapon data extracted from any player!")
    else:
        print(f"\n✅ Weapon data looks good!")
else:
    print("❌ No players found!")
