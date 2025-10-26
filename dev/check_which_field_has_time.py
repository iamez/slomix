#!/usr/bin/env python3
"""
Check if Tab[23] has the time data, not Tab[22]!
"""

files_to_check = [
    'local_stats/2025-10-02-211808-etl_adlernest-round-1.txt',
    'local_stats/2025-10-02-212249-etl_adlernest-round-2.txt',
    'local_stats/2025-10-02-213333-supply-round-1.txt',
]

print("=" * 80)
print("CHECKING WHICH FIELD HAS TIME DATA")
print("=" * 80)
print()

for filepath in files_to_check:
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    header = lines[0].strip()
    header_parts = header.split('\\')
    actual_time_mmss = header_parts[7]
    
    # Convert to decimal
    if ':' in actual_time_mmss:
        parts = actual_time_mmss.split(':')
        minutes = int(parts[0])
        seconds = int(parts[1])
        total_seconds = minutes * 60 + seconds
        exact_decimal = total_seconds / 60.0
        lua_rounded = round(exact_decimal, 1)
    else:
        exact_decimal = float(actual_time_mmss)
        lua_rounded = round(exact_decimal, 1)
    
    # Get first player line
    player_line = lines[1].strip()
    parts = player_line.split('\t')
    
    tab22 = parts[22] if len(parts) > 22 else "N/A"
    tab23 = parts[23] if len(parts) > 23 else "N/A"
    
    print(f"File: {filepath.split('/')[-1]}")
    print(f"  Header time: {actual_time_mmss}")
    print(f"  Exact decimal: {exact_decimal:.6f}")
    print(f"  Lua rounded: {lua_rounded:.1f}")
    print(f"  Tab[22]: {tab22}")
    print(f"  Tab[23]: {tab23}")
    
    if tab23 == str(lua_rounded):
        print(f"  ✅ Tab[23] matches lua rounded time!")
    elif tab22 == str(lua_rounded):
        print(f"  ✅ Tab[22] matches lua rounded time!")
    else:
        print(f"  ❓ Neither Tab[22] nor Tab[23] matches")
    
    print()

print("=" * 80)
print("CONCLUSION")
print("=" * 80)
print()
print("It looks like:")
print("  - Tab[22] = 0.0 (unused/not written by lua)")
print("  - Tab[23] = Player's time in minutes (lua rounded)")
print()
print("We might have been reading the WRONG field!")
print("Parser might need to read Tab[23] instead of Tab[22]")
