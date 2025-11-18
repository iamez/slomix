"""Check what stats files are missing from local_stats directory"""
import os
from datetime import datetime, timedelta

# Get all files in local_stats
local_files = set()
for filename in os.listdir('local_stats'):
    if filename.endswith('.txt') and filename.startswith('2025-'):
        local_files.add(filename)

print(f"📁 Found {len(local_files)} files in local_stats/\n")

# Check date range
dates_with_files = {}
for filename in sorted(local_files):
    date_part = filename[:10]  # 2025-11-04
    if date_part not in dates_with_files:
        dates_with_files[date_part] = []
    dates_with_files[date_part].append(filename)

print("📊 Files by date:\n")
for date in sorted(dates_with_files.keys()):
    files = dates_with_files[date]
    print(f"{date}: {len(files)} files")
    
    # Check if we have both R1 and R2 for each map
    maps = {}
    for f in files:
        parts = f.split('-')
        if len(parts) >= 6:
            map_name = parts[3]
            round_num = parts[-1].replace('.txt', '').replace('round-', '')
            if map_name not in maps:
                maps[map_name] = set()
            maps[map_name].add(round_num)
    
    # Show any maps with only R1 or only R2
    incomplete_maps = []
    for map_name, rounds in maps.items():
        if '1' in rounds and '2' not in rounds:
            incomplete_maps.append(f"{map_name} (R1 only)")
        elif '2' in rounds and '1' not in rounds:
            incomplete_maps.append(f"{map_name} (R2 only)")
    
    if incomplete_maps:
        print(f"  ⚠️  Incomplete: {', '.join(incomplete_maps)}")

print(f"\n📅 Date range: {min(dates_with_files.keys())} to {max(dates_with_files.keys())}")

# Check for gaps in dates
all_dates = sorted(dates_with_files.keys())
date_gaps = []
for i in range(len(all_dates) - 1):
    current = datetime.strptime(all_dates[i], "%Y-%m-%d")
    next_date = datetime.strptime(all_dates[i + 1], "%Y-%m-%d")
    gap_days = (next_date - current).days
    if gap_days > 1:
        date_gaps.append(f"{all_dates[i]} → {all_dates[i+1]} ({gap_days} days)")

if date_gaps:
    print(f"\n⚠️  Date gaps found:")
    for gap in date_gaps:
        print(f"  {gap}")
