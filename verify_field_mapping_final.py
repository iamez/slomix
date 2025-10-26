"""
Comprehensive field mapping verification before database import.
We need to be 100% certain about the field mapping!
"""

# Test file
filepath = "local_stats/2025-04-03-215602-etl_adlernest-round-2.txt"

print("=" * 80)
print("FIELD MAPPING VERIFICATION - CRITICAL CHECK BEFORE IMPORT")
print("=" * 80)

with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

# Get header
header = lines[0].strip()
print(f"\nHEADER: {header}")
header_parts = header.split('\\')
print(f"Header parts: {len(header_parts)}")
for i, part in enumerate(header_parts):
    print(f"  Header[{i}]: {part}")

# Get first player line
player_line = lines[1].strip()
print(f"\n{'=' * 80}")
print("FIRST PLAYER LINE ANALYSIS")
print(f"{'=' * 80}")

# Split by backslash
parts = player_line.split('\\')
print(f"\nBackslash-separated parts: {len(parts)}")
print(f"  Part 0 (GUID): {parts[0]}")
print(f"  Part 1 (Name): {parts[1]}")
print(f"  Part 2 (Rounds): {parts[2]}")
print(f"  Part 3 (Team): {parts[3]}")
print(f"  Part 4 (Stats section) length: {len(parts[4])}")

# Parse stats section
stats_section = parts[4]
if '\t' in stats_section:
    weapon_part, extended_part = stats_section.split('\t', 1)
    print(f"\nWeapon part (space-separated):")
    weapon_fields = weapon_part.split()
    print(f"  Field count: {len(weapon_fields)}")
    print(f"  First 5: {weapon_fields[:5]}")
    print(f"  weaponMask: {weapon_fields[0]}")

    print(f"\nExtended part (TAB-separated):")
    tab_fields = extended_part.split('\t')
    print(f"  Field count: {len(tab_fields)}")
    print(f"  ⚠️  CRITICAL: Lua writes 36 fields (0-35), NOT 37!")
    print()

    # Map out ALL fields according to lua
    field_mapping = [
        (0, "damageGiven", "int"),
        (1, "damageReceived", "int"),
        (2, "teamDamageGiven", "int"),
        (3, "teamDamageReceived", "int"),
        (4, "gibs", "int"),
        (5, "selfkills", "int"),
        (6, "teamkills", "int"),
        (7, "teamgibs", "int"),
        (8, "timePlayed", "float (% of time)"),
        (9, "xp", "int"),
        (10, "killing_spree", "int (topshots[1])"),
        (11, "death_spree", "int (topshots[2])"),
        (12, "kill_assists", "int (topshots[3])"),
        (13, "kill_steals", "int (topshots[4])"),
        (14, "headshot_kills", "int (topshots[5])"),
        (15, "objectives_stolen", "int (topshots[6])"),
        (16, "objectives_returned", "int (topshots[7])"),
        (17, "dynamites_planted", "int (topshots[8])"),
        (18, "dynamites_defused", "int (topshots[9])"),
        (19, "times_revived", "int (topshots[10])"),
        (20, "bullets_fired", "int (topshots[11])"),
        (21, "dpm", "float (topshots[12])"),
        (22, "time_played_minutes", "float (roundNum((tp/1000)/60, 1))"),
        (23, "tank_meatshield", "float (topshots[13])"),
        (24, "time_dead_ratio", "float (topshots[14])"),
        (25, "time_dead_minutes", "float (death_time_total/60000)"),
        (26, "kd_ratio", "float"),
        (27, "useful_kills", "int (topshots[15])"),
        (28, "denied_playtime", "int (topshots[16]/1000)"),
        (29, "multikill_2x", "int"),
        (30, "multikill_3x", "int"),
        (31, "multikill_4x", "int"),
        (32, "multikill_5x", "int"),
        (33, "multikill_6x", "int"),
        (34, "useless_kills", "int (topshots[17])"),
        (35, "full_selfkills", "int (topshots[18])"),
        # NOTE: topshots[19] (repairs_constructions) is NOT written!
    ]

    print("COMPLETE FIELD MAPPING:")
    print(f"{'Index':<6} {'Field Name':<25} {'Type':<30} {'Value':<15}")
    print("-" * 80)

    for idx, name, type_info in field_mapping:
        if idx < len(tab_fields):
            value = tab_fields[idx]
            print(f"{idx:<6} {name:<25} {type_info:<30} {value:<15}")
        else:
            print(f"{idx:<6} {name:<25} {type_info:<30} {'MISSING!':<15}")

    print()
    print(f"TOTAL FIELDS IN FILE: {len(tab_fields)}")
    print(f"EXPECTED FIELDS: 36 (indices 0-35)")

    if len(tab_fields) == 36:
        print("✅ CORRECT: File has 36 fields as expected!")
    else:
        print(f"❌ ERROR: File has {len(tab_fields)} fields, expected 36!")

    print()
    print("CRITICAL NOTES:")
    print("  1. repairs_constructions (topshots[19]) is tracked but NOT written to file")
    print("  2. Parser should read fields 0-35 ONLY (36 total fields)")
    print("  3. Field 22 is time_played_minutes (in minutes, lua-rounded)")
    print("  4. Field 28 is denied_playtime in SECONDS (already divided by 1000 in lua)")

else:
    print("❌ ERROR: No TAB found in stats section!")
