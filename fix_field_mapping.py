"""
FIX FIELD MAPPING ISSUE - c0rnp0rn3.lua Field Order Analysis
=============================================================

CORRECT c0rnp0rn3.lua TAB-separated field order (line 269):
------------------------------------------------------------
Field 0:  damageGiven
Field 1:  damageReceived
Field 2:  teamDamageGiven         ← Parser currently reads this as 'gibs' (WRONG!)
Field 3:  teamDamageReceived
Field 4:  gibs                    ← ACTUAL gibs position!
Field 5:  selfkills
Field 6:  teamkills
Field 7:  teamgibs
Field 8:  timePlayed (percentage)
Field 9:  xp
Field 10: topshots[i][1]  (killing spree)
Field 11: topshots[i][2]  (death spree)
Field 12: topshots[i][3]  (kill assists)
Field 13: topshots[i][4]  (kill steals)
Field 14: topshots[i][5]  (headshot kills)
Field 15: topshots[i][6]  (objectives stolen)
Field 16: topshots[i][7]  (objectives returned)
Field 17: topshots[i][8]  (dynamites planted)
Field 18: topshots[i][9]  (dynamites defused)
Field 19: topshots[i][10] (number of times revived)
Field 20: topshots[i][11] (bullets fired)
Field 21: topshots[i][12] (DPM)
Field 22: roundNum((tp/1000)/60, 1) (time played minutes)
Field 23: topshots[i][13] (tank/meatshield)
Field 24: topshots[i][14] (time dead ratio)
Field 25: roundNum((death_time_total[i] / 60000), 1) (time dead minutes)
Field 26: kd (kill/death ratio)
Field 27: topshots[i][15] (most useful kills)
Field 28: math.floor(topshots[i][16]/1000) (denied playtime)
Field 29: multikills[i][1] (2 kills)
Field 30: multikills[i][2] (3 kills)
Field 31: multikills[i][3] (4 kills)
Field 32: multikills[i][4] (4 kills)
Field 33: multikills[i][5] (5 kills)
Field 34: topshots[i][17] (useless kills)
Field 35: topshots[i][18] (full selfkills)
Field 36: topshots[i][19] (repairs/constructions)

PARSER BUG:
-----------
Current parser mapping (community_stats_parser.py line 665):
    'gibs': int(tab_fields[2])  ← WRONG! This reads teamDamageGiven

Correct mapping should be:
    'gibs': int(tab_fields[4])  ← CORRECT position!

IMPACT:
-------
- All imported gibs values are actually teamDamageGiven values (6x-9x higher)
- Database has incorrect gibs for ALL players
- Need to re-import after fixing parser

FIX REQUIRED:
-------------
1. Update parser field mappings in community_stats_parser.py
2. Recreate database
3. Re-import all stats files
"""

import sys

from community_stats_parser import C0RNP0RN3StatsParser

print(__doc__)

# Let's verify with actual data

sys.path.insert(0, 'bot')

test_file = "local_stats/2025-10-02-211808-etl_adlernest-round-1.txt"
parser = C0RNP0RN3StatsParser()
result = parser.parse_stats_file(test_file)

print("\n" + "=" * 80)
print("VERIFICATION WITH ACTUAL FILE")
print("=" * 80)
print(f"File: {test_file}")

for player in result['players']:
    if player['name'] == 'vid':
        print(f"\nPlayer: {player['name']}")
        print(f"  Current parser reads 'gibs' as: {player.get('gibs', 'N/A')}")
        print(f"  Expected (from human-readable): 3")
        print(f"\n  This confirms: Parser is reading tab_fields[2] (teamDamageGiven)")
        print(f"  Should be reading: tab_fields[4] (actual gibs)")
        break
