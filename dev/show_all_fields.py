"""
Show ALL tab fields to see where time_played_minutes actually is.
"""

test_file = 'local_stats/2025-10-02-211808-etl_adlernest-round-1.txt'

print("=" * 100)
print("🔍 SHOWING ALL TAB FIELDS")
print("=" * 100)
print()

with open(test_file, 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

# Get vid's line
for line in lines[1:]:
    if '^pvid\\' in line:
        parts = line.strip().split('\\')
        if len(parts) >= 5:
            name = parts[1]
            stats_part = parts[4]
            tab_fields = stats_part.split('\t')
            
            print(f"Player: {name}")
            print(f"Total tab fields: {len(tab_fields)}")
            print()
            
            print("Index | Value")
            print("-" * 50)
            for i, field in enumerate(tab_fields):
                print(f"[{i:2d}]   {field}")
            
            print()
            print("📋 KEY FIELDS:")
            if len(tab_fields) > 20:
                print(f"  [20] bullets_fired:       {tab_fields[20]}")
            if len(tab_fields) > 21:
                print(f"  [21] dpm (from lua):      {tab_fields[21]}")
            if len(tab_fields) > 22:
                print(f"  [22] time_played_minutes: {tab_fields[22]}")
            if len(tab_fields) > 23:
                print(f"  [23] tank_meatshield:     {tab_fields[23]}")
            if len(tab_fields) > 24:
                print(f"  [24] time_dead_ratio:     {tab_fields[24]}")
            if len(tab_fields) > 25:
                print(f"  [25] time_dead_minutes:   {tab_fields[25]}")
        break
