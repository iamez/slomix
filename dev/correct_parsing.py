"""
Parse player line correctly using TAB separator for stats.
"""

test_file = 'local_stats/2025-10-02-211808-etl_adlernest-round-1.txt'

print("=" * 100)
print("🔍 CORRECT PARSING: Fields are TAB-separated!")
print("=" * 100)
print()

with open(test_file, 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

# Header
header = lines[0].strip()
header_parts = header.split('\\')
actual_time = header_parts[7] if len(header_parts) > 7 else "0:00"

# Parse to minutes
if ':' in actual_time:
    parts = actual_time.split(':')
    session_min = int(parts[0]) + int(parts[1]) / 60.0
else:
    session_min = 0.0

print(f"📋 Session Time (from header): {actual_time} = {session_min:.2f} minutes")
print()

print(f"{'Player':<20} {'Team':<6} {'Field 22':<12} {'Comparison':<40}")
print("-" * 100)

for line in lines[1:]:
    if not line.strip():
        continue
    
    # Split by backslash first
    parts = line.strip().split('\\')
    if len(parts) < 5:
        continue
    
    guid = parts[0]
    name = parts[1]
    team = parts[3]
    stats_part = parts[4]
    
    # NOW split the stats part by TAB
    tab_fields = stats_part.split('\t')
    
    # Field 22 should be at index 22 in tab_fields
    if len(tab_fields) > 22:
        field_22_raw = tab_fields[22]
        try:
            field_22 = float(field_22_raw)
            diff = field_22 - session_min
            pct = (diff / session_min * 100) if session_min > 0 else 0
            
            comparison = f"{field_22:.2f} min (diff: {diff:+.2f} = {pct:+.1f}%)"
            print(f"{name:<20} {team:<6} {field_22_raw:<12} {comparison:<40}")
        except ValueError:
            print(f"{name:<20} {team:<6} {field_22_raw:<12} ERROR: Can't parse as float")
    else:
        print(f"{name:<20} {team:<6} N/A          Not enough fields ({len(tab_fields)})")

print()
print("💡 DISCOVERY:")
print("  ALL players have Field 22 = 3.9 minutes")
print(f"  Session time = 3.85 minutes")
print(f"  Difference = +0.05 minutes (3 seconds)")
print()
print("  So in a competitive environment:")
print("  - All players have SAME player time ✅")
print("  - Player time is slightly LONGER than session time")
print()
print("❓ WHY is player time 3.9 instead of 3.85?")
print("  Theory 1: Rounding difference in lua script")
print("  Theory 2: Player time includes warmup/setup?")
print("  Theory 3: Session time excludes some period?")
print("  Theory 4: Different calculation methods")
