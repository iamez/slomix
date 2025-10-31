#!/usr/bin/env python3
"""
Check if Tab[22] field really is 0.0 or if we're reading it wrong
"""

# Read the file and parse player lines
with open('local_stats/2025-10-02-211808-etl_adlernest-round-1.txt', 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

# Get header
header = lines[0].strip()
header_parts = header.split('\\')
actual_time = header_parts[7]

print("=" * 80)
print("RAW FILE ANALYSIS - Tab[22] vs Session Time")
print("=" * 80)
print()
print(f"Session Header Time: {actual_time}")
print()

# Parse first player line (detailed)
player_line = lines[1].strip()
print("FULL PLAYER LINE:")
print(player_line[:200] + "...")
print()

# Split by TAB
parts = player_line.split('\t')
print(f"Number of TAB-separated fields: {len(parts)}")
print()

print("TAB FIELDS:")
for i, field in enumerate(parts):
    if i == 22:
        print(f"  [{i}] Tab[22] (time_played_minutes): '{field}' ⭐")
    elif i < 5 or i > 20:
        # Show first few and fields around 22
        print(f"  [{i}] {field[:50] if len(field) > 50 else field}")

print()
print("=" * 80)
print("ANALYSIS")
print("=" * 80)
print()

tab22_value = parts[22] if len(parts) > 22 else "NOT FOUND"
print(f"Tab[22] value: '{tab22_value}'")
print(f"Session time:  '{actual_time}'")
print()

if tab22_value == "0.0":
    print("✅ CONFIRMED: Tab[22] is 0.0 (lua doesn't write player time)")
    print()
    print("Explanation:")
    print("  - c0rnp0rn3.lua initializes Tab[22] but never updates it")
    print("  - Player time tracking is done separately in game")
    print("  - Only session time is written to file header")
    print("  - ALL players in same round have SAME time (can't join late)")
else:
    print(f"❓ UNEXPECTED: Tab[22] = '{tab22_value}' (not 0.0!)")
    print()
    print("This would mean player time IS tracked in Tab[22]")
    print("Need to investigate why we thought it was 0.0")
