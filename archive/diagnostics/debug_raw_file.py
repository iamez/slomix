#!/usr/bin/env python3
"""Debug: Check raw file line by line"""

print('\n' + '='*80)
print('RAW FILE LINE-BY-LINE CHECK')
print('='*80)

file_path = 'local_stats/2025-10-02-232339-erdenberg_t2-round-1.txt'

with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

print(f"\nTotal lines in file: {len(lines)}")
print("\nLine-by-line breakdown:\n")

for i, line in enumerate(lines, 1):
    line = line.strip()
    if not line:
        continue
        
    print(f"Line {i}:")
    if '\\' in line:
        # Player line
        parts = line.split('\\')
        if len(parts) >= 2:
            guid = parts[0]
            name = parts[1]
            print(f"  Player: {name}")
            print(f"  GUID: {guid}")
            
            if 'olz' in name.lower():
                print(f"  ⭐ OLZ FOUND! ⭐")
    else:
        # Header line
        print(f"  Header: {line[:80]}...")
    print()

print('='*80)
print("✅ Manual check complete")
