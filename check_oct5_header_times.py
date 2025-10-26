import os
import re

path = 'local_stats'
files = sorted([f for f in os.listdir(path) if '2025-10-05' in f])

print("=== October 5th Files - Header Times ===\n")

for file in files:
    filepath = os.path.join(path, file)
    with open(filepath, encoding='latin-1') as f:
        first_line = f.readline().strip()
        
        # Extract time from header (format: \7:39\7:39\ or similar)
        time_match = re.search(r'\\(\d+):(\d+)\\', first_line)
        if time_match:
            mins = int(time_match.group(1))
            secs = int(time_match.group(2))
            total_secs = mins * 60 + secs
            print(f"{file}")
            print(f"  Time: {mins}:{secs:02d} ({total_secs} seconds)")
        else:
            print(f"{file}")
            print(f"  Time: NOT FOUND")
