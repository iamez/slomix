"""Test to understand the exact line format"""

# Get a real player line
with open("local_stats/2025-04-03-215602-etl_adlernest-round-2.txt", 'r', encoding='utf-8') as f:
    lines = f.readlines()

player_line = lines[1].strip()  # First player

print("=" * 80)
print("RAW LINE:")
print(player_line[:200])
print()

# Step 1: Split by backslash
parts_backslash = player_line.split('\\')
print(f"STEP 1: Split by backslash - {len(parts_backslash)} parts")
for i, part in enumerate(parts_backslash[:5]):
    print(f"  Part {i}: {part[:80]}")
print()

# Step 2: The 5th part (index 4) should contain: weaponMask weaponStats TAB extendedStats
if len(parts_backslash) >= 5:
    stats_section = parts_backslash[4]
    print(f"STEP 2: Stats section (part 4):")
    print(f"  Length: {len(stats_section)}")
    print(f"  First 150 chars: {stats_section[:150]}")
    print()

    # Check for TAB
    if '\t' in stats_section:
        print(f"STEP 3: Contains TAB - splitting...")
        weapon_part, extended_part = stats_section.split('\t', 1)
        print(f"  Weapon part length: {len(weapon_part)}")
        print(f"  Weapon part: {weapon_part[:100]}")
        print()
        print(f"  Extended part - split by TAB:")
        extended_fields = extended_part.split('\t')
        print(f"    Number of TAB-separated fields: {len(extended_fields)}")
        print(f"    First 5 fields: {extended_fields[:5]}")
        print(f"    Last 5 fields: {extended_fields[-5:]}")
    else:
        print("  ❌ NO TAB FOUND!")
