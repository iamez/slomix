#!/usr/bin/env python3
"""
Find all cases where multiple games of the same map were played on the same day
"""
from pathlib import Path
from collections import defaultdict

stats_dir = Path("local_stats")
all_files = sorted(stats_dir.glob("2025*.txt"))

# Group by date-map-round
games_per_day = defaultdict(list)

for file in all_files:
    parts = file.name.split('-')
    date = '-'.join(parts[:3])  # YYYY-MM-DD
    # Find map name (everything between date and "round")
    round_idx = file.name.rfind('-round-')
    if round_idx == -1:
        continue
    
    # Get map name
    after_date = file.name[len(date)+1:round_idx]
    timestamp = after_date.split('-')[0]  # HHMMSS
    map_name = '-'.join(after_date.split('-')[1:])
    
    round_num = file.name[round_idx+7]  # Get '1' or '2' from '-round-1.txt'
    
    key = (date, map_name, round_num)
    games_per_day[key].append((timestamp, file.name))

# Find duplicates
print("=" * 100)
print("MULTIPLE SESSIONS OF SAME MAP ON SAME DAY")
print("=" * 100)

duplicates = {k: v for k, v in games_per_day.items() if len(v) > 1}

print(f"\nFound {len(duplicates)} date/map/round combinations with multiple sessions")
print(f"Total affected files: {sum(len(v) for v in duplicates.values())}")
print(f"Files that can't be imported: {sum(len(v)-1 for v in duplicates.values())}")

print("\n📊 TOP 10 MOST REPLAYED MAP/DAY COMBINATIONS:")
sorted_dupes = sorted(duplicates.items(), key=lambda x: len(x[1]), reverse=True)

for (date, map_name, round_num), sessions in sorted_dupes[:10]:
    print(f"\n{date} - {map_name} - Round {round_num}: {len(sessions)} sessions")
    for timestamp, filename in sorted(sessions):
        print(f"   {timestamp} - {filename}")

print("\n" + "=" * 100)
print(f"⚠️  LOST DATA: {sum(len(v)-1 for v in duplicates.values())} sessions cannot be imported!")
print(f"⚠️  Only the FIRST session per date/map/round gets imported")
print(f"⚠️  This is because UNIQUE constraint is (round_date, map_name, round_number)")
print(f"⚠️  It SHOULD be (round_date, round_time, map_name, round_number)")
print("=" * 100)
