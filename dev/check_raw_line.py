"""
Check raw player line format.
"""

test_file = 'local_stats/2025-10-02-211808-etl_adlernest-round-1.txt'

print("🔍 Checking raw player lines...")
print()

with open(test_file, 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")
print()

# Show first few lines
print("First 5 lines:")
for i, line in enumerate(lines[:5]):
    print(f"Line {i}: {repr(line[:100])}")
print()

# Check line 1 (first player - should be vid)
if len(lines) > 1:
    player_line = lines[1].strip()
    print("FIRST PLAYER LINE:")
    print(f"Raw: {repr(player_line[:200])}")
    print()
    
    parts = player_line.split('\\')
    print(f"Number of parts when split by '\\': {len(parts)}")
    print()
    
    # Show all parts
    for i, part in enumerate(parts[:30]):
        print(f"Part [{i:2d}]: {repr(part)}")
    print()
    
    # Focus on Field 22
    if len(parts) > 22:
        print(f"Field 22 (time_played_minutes): {repr(parts[22])}")
        try:
            field_22_value = float(parts[22])
            print(f"As float: {field_22_value}")
        except ValueError as e:
            print(f"ERROR parsing: {e}")
