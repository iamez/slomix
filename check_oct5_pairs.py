import os

path = 'local_stats'
files = sorted([f for f in os.listdir(path) if '2025-10-05' in f])

r1_files = set([f for f in files if 'round-1' in f])
r2_files = [f for f in files if 'round-2' in f]

print("Round 2 files and their Round 1 status:\n")
for r2 in r2_files:
    r1 = r2.replace('-round-2', '-round-1')
    has_r1 = r1 in r1_files
    status = "✅ HAS Round 1" if has_r1 else "❌ MISSING Round 1"
    print(f"{status}: {r2}")
    if has_r1:
        print(f"           {r1}")
