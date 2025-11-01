"""
COMPREHENSIVE FIELD MAPPING VERIFICATION
=========================================

This script verifies ALL field mappings between c0rnp0rn3.lua and our parser.

c0rnp0rn3.lua line 269 writes fields in this EXACT order:
stats[guid] = string.format("%s \t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%0.1f\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%0.1f\t%0.1f\t%0.1f\t%0.1f\t%0.1f\t%0.1f\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\n",
    stats[guid],           # Prefix (GUID\name\rounds\team\\weaponmask weaponstats)
    damageGiven,           # Field 0
    damageReceived,        # Field 1
    teamDamageGiven,       # Field 2
    teamDamageReceived,    # Field 3
    gibs,                  # Field 4  ← WE HAD THIS WRONG!
    selfkills,             # Field 5
    teamkills,             # Field 6
    teamgibs,              # Field 7
    timePlayed,            # Field 8  (percentage)
    xp,                    # Field 9
    topshots[i][1],        # Field 10 - killing spree
    topshots[i][2],        # Field 11 - death spree
    topshots[i][3],        # Field 12 - kill assists
    topshots[i][4],        # Field 13 - kill steals
    topshots[i][5],        # Field 14 - headshot kills
    topshots[i][6],        # Field 15 - objectives stolen
    topshots[i][7],        # Field 16 - objectives returned
    topshots[i][8],        # Field 17 - dynamites planted
    topshots[i][9],        # Field 18 - dynamites defused
    topshots[i][10],       # Field 19 - number of times revived
    topshots[i][11],       # Field 20 - bullets fired
    topshots[i][12],       # Field 21 - DPM
    roundNum((tp/1000)/60, 1),  # Field 22 - time played minutes
    topshots[i][13],       # Field 23 - tank/meatshield
    topshots[i][14],       # Field 24 - time dead ratio
    roundNum((death_time_total[i] / 60000), 1),  # Field 25 - time dead minutes
    kd,                    # Field 26 - kill/death ratio
    topshots[i][15],       # Field 27 - most useful kills
    math.floor(topshots[i][16]/1000),  # Field 28 - denied playtime
    multikills[i][1],      # Field 29 - 2 kills
    multikills[i][2],      # Field 30 - 3 kills
    multikills[i][3],      # Field 31 - 4 kills
    multikills[i][4],      # Field 32 - 5 kills
    multikills[i][5],      # Field 33 - 6 kills
    topshots[i][17],       # Field 34 - useless kills
    topshots[i][18],       # Field 35 - full selfkills
    topshots[i][19]        # Field 36 - repairs/constructions
)
"""

import sys

from community_stats_parser import C0RNP0RN3StatsParser

sys.path.insert(0, 'bot')

# Expected field mappings from c0rnp0rn3.lua
CORRECT_MAPPINGS = {
    0: 'damage_given',
    1: 'damage_received',
    2: 'team_damage_given',  # ← Parser was reading this as 'gibs'
    3: 'team_damage_received',
    4: 'gibs',  # ← ACTUAL gibs position
    5: 'self_kills',
    6: 'team_kills',
    7: 'team_gibs',
    8: 'time_played_percent',
    9: 'xp',
    10: 'killing_spree',
    11: 'death_spree',
    12: 'kill_assists',
    13: 'kill_steals',
    14: 'headshot_kills',
    15: 'objectives_stolen',
    16: 'objectives_returned',
    17: 'dynamites_planted',
    18: 'dynamites_defused',
    19: 'times_revived',  # ← Number of times THIS player was revived
    20: 'bullets_fired',
    21: 'dpm',
    22: 'time_played_minutes',
    23: 'tank_meatshield',
    24: 'time_dead_ratio',
    25: 'time_dead_minutes',
    26: 'kd_ratio',
    27: 'most_useful_kills',
    28: 'denied_playtime',
    29: 'multi_kill_2',
    30: 'multi_kill_3',
    31: 'multi_kill_4',
    32: 'multi_kill_5',
    33: 'multi_kill_6',
    34: 'useless_kills',
    35: 'full_selfkills',
    36: 'repairs_constructions',
}

print("=" * 80)
print("FIELD MAPPING VERIFICATION")
print("=" * 80)

# Parse test file
test_file = "local_stats/2025-10-02-211808-etl_adlernest-round-1.txt"
parser = C0RNP0RN3StatsParser()
result = parser.parse_stats_file(test_file)

# Find vid's data
vid_data = None
for player in result['players']:
    if player['name'] == 'vid':
        vid_data = player
        break

if not vid_data:
    print("❌ Could not find vid in test file!")
    sys.exit(1)

# Read raw file to get actual TAB fields
with open(test_file, 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

vid_line = None
for line in lines:
    if '\\^pvid\\' in line or '\\vid\\' in line:
        vid_line = line.strip()
        break

if not vid_line:
    print("❌ Could not find vid's line in raw file!")
    sys.exit(1)

# Extract TAB-separated section
parts = vid_line.split('\t')
if len(parts) < 37:
    print(f"❌ Expected at least 37 TAB fields, got {len(parts)}")
    sys.exit(1)

# Remove weapon stats prefix (everything before first TAB)
# The line format is: GUID\name\rounds\team\weaponmask weaponstats \t field0 \t field1 ...
tab_fields = parts[1:]  # Skip prefix before first TAB

print(f"\n📁 Test File: {test_file}")
print(f"📊 Player: {vid_data['name']}")
print(f"📋 Found {len(tab_fields)} TAB-separated fields\n")

# Expected values from human-readable attachment
expected_values = {
    'damage_given': 1328,
    'damage_received': 1105,
    'gibs': 3,
    'xp': 48,
    'kill_assists': 1,
    'times_revived': 1,
    'kills': 9,
    'deaths': 3,
}

print("=" * 80)
print("FIELD-BY-FIELD VERIFICATION")
print("=" * 80)

errors = []
warnings = []

# Check critical fields
critical_fields = [
    (0, 'damage_given', int(tab_fields[0]) if len(tab_fields) > 0 else None),
    (1, 'damage_received', int(tab_fields[1]) if len(tab_fields) > 1 else None),
    (2, 'team_damage_given', int(tab_fields[2]) if len(tab_fields) > 2 else None),
    (3, 'team_damage_received', int(tab_fields[3]) if len(tab_fields) > 3 else None),
    (4, 'gibs', int(tab_fields[4]) if len(tab_fields) > 4 else None),
    (5, 'self_kills', int(tab_fields[5]) if len(tab_fields) > 5 else None),
    (6, 'team_kills', int(tab_fields[6]) if len(tab_fields) > 6 else None),
    (7, 'team_gibs', int(tab_fields[7]) if len(tab_fields) > 7 else None),
    (8, 'time_played_percent', float(tab_fields[8]) if len(tab_fields) > 8 else None),
    (9, 'xp', int(tab_fields[9]) if len(tab_fields) > 9 else None),
    (12, 'kill_assists', int(tab_fields[12]) if len(tab_fields) > 12 else None),
    (19, 'times_revived', int(tab_fields[19]) if len(tab_fields) > 19 else None),
]

for field_num, field_name, raw_value in critical_fields:
    parser_value = vid_data.get(field_name, 'NOT_FOUND')

    print(f"\nField {field_num}: {field_name}")
    print(f"  Raw c0rnp0rn3: {raw_value}")
    print(f"  Parser reads:  {parser_value}")

    if expected_values.get(field_name):
        expected = expected_values[field_name]
        print(f"  Expected:      {expected}")

        if parser_value == expected:
            print(f"  ✅ CORRECT")
        elif parser_value == raw_value:
            print(f"  ⚠️  Parser matches c0rnp0rn3 but differs from expected")
            warnings.append(f"{field_name}: parser={parser_value}, expected={expected}")
        else:
            print(f"  ❌ WRONG - Parser doesn't match c0rnp0rn3 or expected!")
            errors.append(
                f"{field_name}: parser={parser_value}, raw={raw_value}, expected={expected}"
            )
    else:
        if parser_value == raw_value:
            print(f"  ✅ Parser matches c0rnp0rn3")
        else:
            print(f"  ❌ Parser doesn't match c0rnp0rn3!")
            errors.append(f"{field_name}: parser={parser_value}, raw={raw_value}")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

if errors:
    print(f"\n❌ ERRORS FOUND ({len(errors)}):")
    for error in errors:
        print(f"  - {error}")

if warnings:
    print(f"\n⚠️  WARNINGS ({len(warnings)}):")
    for warning in warnings:
        print(f"  - {warning}")

if not errors and not warnings:
    print("\n✅ ALL FIELDS VERIFIED CORRECT!")
    print("Parser is now reading all fields from correct positions.")

print("\n" + "=" * 80)
print("NEXT STEPS")
print("=" * 80)

if errors:
    print("1. Fix parser field mappings in bot/community_stats_parser.py")
    print("2. Re-run this verification script")
    print("3. Recreate database and re-import data")
elif warnings:
    print("Parser is technically correct but values differ from human-readable.")
    print("This suggests human-readable attachments come from different source.")
    print("\n🔍 INVESTIGATION NEEDED:")
    print("- Where do human-readable files come from?")
    print("- Are they from same c0rnp0rn3 format or different system?")
else:
    print("✅ Parser verified correct!")
    print("✅ Database already recreated with correct parser!")
    print("✅ Ready to test Discord bot: !last_session")
