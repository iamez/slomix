#!/usr/bin/env python3
"""Count fields in each line to find the truncated olz line"""

with open('local_stats/2025-10-02-232339-erdenberg_t2-round-1.txt', 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

print('\n' + '='*80)
print('FIELD COUNT ANALYSIS - Round 1 File')
print('='*80 + '\n')

for i, line in enumerate(lines, 1):
    line = line.strip()
    if not line:
        continue
    
    # Count tab-delimited fields
    tab_fields = line.count('\t') + 1
    
    # Get player name
    if '\\' in line:
        parts = line.split('\\')
        if len(parts) >= 2:
            player_name = parts[1]
            # Remove color codes for display
            import re
            clean_name = re.sub(r'\^[0-9a-zA-Z]', '', player_name)
            
            print(f"Line {i}: {clean_name:20s} | Tab-delimited fields: {tab_fields}")
            
            if 'olz' in clean_name.lower():
                print(f"         ⚠️  OLZ LINE - Checking if truncated...")
                # Show the actual line length
                print(f"         Line length: {len(line)} characters")
    else:
        print(f"Line {i}: HEADER")

print('\n' + '='*80)
