"""
Check if raw file has inconsistent headshot values between weapon stats and TAB fields
"""

# Parse carniee's line manually
line = r"0A26D447\^7carniee\0\2\134236216 4 12 0 0 0 0 0 0 9 0 56 202 3 0 8 0 3 0 0 0 0 1 0 0 0 2 2 0 0 0 	1196	1438	97	18	1	3	1	0	79.8	22	0	7	3	0	1	0	0	1	0	2	220	0.0	4.3	0.0	27.5	1.2	0.3	2	23	0	0	0	0	0	0	0	0	2"

# Split by backslash
parts = line.split('\\')
print(f"GUID: {parts[0]}")
print(f"Name: {parts[1]}")
print(f"Team: {parts[2]}")
print(f"Rounds: {parts[3]}")

# Split weapon/TAB section
weapon_and_tab = parts[4]
sections = weapon_and_tab.split('\t')
weapon_section = sections[0]
tab_section = '\t'.join(sections[1:])  # Rest is TAB-separated fields

print(f"\nWeapon section: {weapon_section[:50]}...")
print(f"TAB section: {tab_section[:50]}...")

# Parse weapon stats
weapon_parts = weapon_section.strip().split(' ')
weapon_mask = int(weapon_parts[0])
print(f"\nWeapon mask: {weapon_mask}")

# Count weapons and extract headshots
stats_index = 1
total_headshots_from_weapons = 0
weapons_with_headshots = []

for weapon_id in range(28):
    if weapon_mask & (1 << weapon_id):
        if stats_index + 4 < len(weapon_parts):
            hits = int(weapon_parts[stats_index])
            shots = int(weapon_parts[stats_index + 1])
            kills = int(weapon_parts[stats_index + 2])
            deaths = int(weapon_parts[stats_index + 3])
            headshots = int(weapon_parts[stats_index + 4])
            
            if headshots > 0:
                weapons_with_headshots.append((weapon_id, headshots, kills))
            
            total_headshots_from_weapons += headshots
            stats_index += 5

print(f"\nWeapons with headshots:")
for wid, hs, k in weapons_with_headshots:
    print(f"  Weapon {wid}: {hs} headshots, {k} kills")

print(f"\nTotal headshots from weapon stats: {total_headshots_from_weapons}")

# Parse TAB field 14
tab_fields = tab_section.split('\t')
headshot_kills_from_tab = int(tab_fields[14]) if len(tab_fields) > 14 else 0
print(f"Headshot_kills from TAB field 14: {headshot_kills_from_tab}")

print(f"\n{'='*60}")
if total_headshots_from_weapons != headshot_kills_from_tab:
    print(f"❌ INCONSISTENCY IN RAW FILE!")
    print(f"   Weapon stats sum: {total_headshots_from_weapons}")
    print(f"   TAB field 14:     {headshot_kills_from_tab}")
    print(f"   Difference:       {total_headshots_from_weapons - headshot_kills_from_tab}")
else:
    print(f"✅ Raw file is consistent")
