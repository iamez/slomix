#!/usr/bin/env python3
"""Quick test: Verify parser extracts winner_team and defender_team"""

import sys
sys.path.insert(0, 'bot')

from community_stats_parser import C0RNP0RN3StatsParser

parser = C0RNP0RN3StatsParser()
result = parser.parse_stats_file('local_stats/2025-10-02-211808-etl_adlernest-round-1.txt')

print("\n" + "="*60)
print("PARSER TEST: winner_team & defender_team extraction")
print("="*60)
print(f"\n📁 File: 2025-10-02-211808-etl_adlernest-round-1.txt")
print(f"🗺️  Map: {result['map_name']}")
print(f"🔄 Round: {result['round_num']}")
print(f"🛡️  Defender Team: {result.get('defender_team', 'NOT FOUND')}")
print(f"🏆 Winner Team: {result.get('winner_team', 'NOT FOUND')}")

if 'defender_team' in result and 'winner_team' in result:
    print(f"\n✅ SUCCESS! Parser extracts both fields correctly")
    print(f"   • Defender: Team {result['defender_team']} ({'Axis' if result['defender_team'] == 1 else 'Allies'})")
    print(f"   • Winner: Team {result['winner_team']} ({'Axis' if result['winner_team'] == 1 else 'Allies' if result['winner_team'] == 2 else 'Draw'})")
else:
    print(f"\n❌ FAIL! Parser did NOT extract fields")

print("\n" + "="*60 + "\n")
