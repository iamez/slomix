"""
Comprehensive parser verification against dev's official field mapping
"""

import sys

from community_stats_parser import C0RNP0RN3StatsParser

sys.path.insert(0, 'bot')

# Dev's official mapping (from message)
DEV_MAPPING = {
    0: 'damageGiven',
    1: 'damageReceived',
    2: 'teamDamageGiven',
    3: 'teamDamageReceived',
    4: 'gibs',
    5: 'selfkills',
    6: 'teamkills',
    7: 'teamgibs',
    8: 'timePlayed ratio',
    9: 'xp',
    10: 'killing spree',
    11: 'death spree',
    12: 'kill assists',
    13: 'kill steals',
    14: 'headshot kills',
    15: 'objectives stolen',
    16: 'objectives returned',
    17: 'dynamites planted',
    18: 'dynamites defused',
    19: 'most revived',
    20: 'bullets fired',
    21: 'DPM',
    22: 'time played',
    23: 'tank/meatshield',
    24: 'time dead ratio',
    25: 'time dead',
    26: 'k/d ratio',
    27: 'useful kills',
    28: 'multikills(2)',
    29: 'multikills(3)',
    30: 'multikills(4)',
    31: 'multikills(5)',
    32: 'multikills(6)',
}

# Read test file
test_file = "local_stats/2025-10-02-211808-etl_adlernest-round-1.txt"

print("=" * 80)
print("PARSER FIELD MAPPING VERIFICATION")
print("=" * 80)

# Parse with our parser
parser = C0RNP0RN3StatsParser()
result = parser.parse_stats_file(test_file)

vid_data = None
for player in result['players']:
    if player['name'] == 'vid':
        vid_data = player
        break

# Read raw file to get actual TAB fields
with open(test_file, 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

vid_line = None
for line in lines:
    if '\\^pvid\\' in line or '\\vid\\' in line:
        vid_line = line.strip()
        break

# Extract TAB-separated fields
parts = vid_line.split('\t')
tab_fields = parts[1:]  # Skip prefix before first TAB

print(f"\n📁 File: {test_file}")
print(f"👤 Player: vid")
print(f"📋 TAB fields found: {len(tab_fields)}")

print("\n" + "=" * 80)
print("FIELD VERIFICATION (First 33 fields)")
print("=" * 80)
print(f"{'#':<3} {'Dev Name':<25} {'Raw Value':<12} {'Parser Key':<25} {'Match'}")
print("-" * 80)

# Map dev names to our parser keys
dev_to_parser = {
    'damageGiven': 'damage_given',
    'damageReceived': 'damage_received',
    'teamDamageGiven': 'team_damage_given',
    'teamDamageReceived': 'team_damage_received',
    'gibs': 'gibs',
    'selfkills': 'self_kills',
    'teamkills': 'team_kills',
    'teamgibs': 'team_gibs',
    'timePlayed ratio': 'time_played_percent',
    'xp': 'xp',
    'killing spree': 'killing_spree',
    'death spree': 'death_spree',
    'kill assists': 'kill_assists',
    'kill steals': 'kill_steals',
    'headshot kills': 'headshot_kills',
    'objectives stolen': 'objectives_stolen',
    'objectives returned': 'objectives_returned',
    'dynamites planted': 'dynamites_planted',
    'dynamites defused': 'dynamites_defused',
    'most revived': 'times_revived',
    'bullets fired': 'bullets_fired',
    'DPM': 'dpm',
    'time played': 'time_played_minutes',
    'tank/meatshield': 'tank_meatshield',
    'time dead ratio': 'time_dead_ratio',
    'time dead': 'time_dead_minutes',
    'k/d ratio': 'kd_ratio',
    'useful kills': 'useful_kills',
    'multikills(2)': 'multikill_2x',
    'multikills(3)': 'multikill_3x',
    'multikills(4)': 'multikill_4x',
    'multikills(5)': 'multikill_5x',
    'multikills(6)': 'multikill_6x',
}

errors = []
obj_stats = vid_data.get('objective_stats', {})

for field_num in range(33):
    dev_name = DEV_MAPPING.get(field_num, 'UNKNOWN')
    raw_value = tab_fields[field_num] if field_num < len(tab_fields) else 'N/A'
    parser_key = dev_to_parser.get(dev_name, 'UNMAPPED')

    if parser_key in obj_stats:
        parser_value = obj_stats[parser_key]
        # Try to convert for comparison
        try:
            if '.' in str(raw_value):
                raw_float = float(raw_value)
                match = abs(float(parser_value) - raw_float) < 0.01
            else:
                match = int(parser_value) == int(raw_value)
        except BaseException:
            match = str(parser_value) == str(raw_value)

        status = "✅" if match else f"❌ ({parser_value})"
        if not match:
            errors.append(f"Field {field_num} ({dev_name}): raw={raw_value}, parser={parser_value}")
    else:
        status = "❌ NOT_FOUND"
        errors.append(f"Field {field_num} ({dev_name}): NOT FOUND in parser output")

    print(f"{field_num:<3} {dev_name:<25} {raw_value:<12} {parser_key:<25} {status}")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

if errors:
    print(f"\n❌ ERRORS FOUND ({len(errors)}):")
    for error in errors:
        print(f"  {error}")
else:
    print("\n✅ ALL FIELDS VERIFIED CORRECT!")
    print("Parser matches dev's official field mapping 100%")
