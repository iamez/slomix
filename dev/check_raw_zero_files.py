#!/usr/bin/env python3
"""
Read RAW content of 0:00 files to see what data exists
"""
from pathlib import Path

# Get a few 0:00 files
stats_dir = Path('local_stats')
zero_files = []

for f in stats_dir.glob('*.txt'):
    with open(f, 'r', encoding='utf-8', errors='ignore') as file:
        first_line = file.readline()
        if '\\0:00' in first_line:
            zero_files.append(f)
            if len(zero_files) >= 3:
                break

print('='*80)
print('RAW FILE CONTENT ANALYSIS - 0:00 FILES')
print('='*80)

for filepath in zero_files:
    print(f'\n📄 {filepath.name}')
    print('-'*80)
    
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    # Header analysis
    header = lines[0].strip() if lines else ''
    header_parts = header.split('\\')
    
    print('HEADER FIELDS:')
    for i, part in enumerate(header_parts[:10]):
        print(f'  [{i}] {part}')
    
    # Player line analysis
    if len(lines) > 1:
        print('\nFIRST PLAYER LINE:')
        player_line = lines[1].strip()
        
        # Check if it's GUID\tfield1\tfield2...
        if '\t' in player_line:
            parts = player_line.split('\t')
            print(f'  GUID: {parts[0]}')
            print(f'  Total TAB-separated fields: {len(parts)}')
            
            # Key fields
            if len(parts) > 1:
                print(f'  [1] damage_given: {parts[1]}')
            if len(parts) > 22:
                print(f'  [22] DPM: {parts[22]}')
            if len(parts) > 23:
                print(f'  [23] time_played_minutes: {parts[23]}')
            
            # Check if time_played exists even though session time is 0:00
            if len(parts) > 23 and parts[23] != '0' and parts[23] != '0.0':
                print(f'\n  ✅ PLAYER HAS TIME DATA: {parts[23]} minutes!')
                print(f'     Even though session shows 0:00!')
        else:
            print(f'  ⚠️  No TAB-separated data found')
            print(f'  Raw: {player_line[:100]}...')

print('\n' + '='*80)
print('🎯 KEY FINDING:')
print('='*80)
print('''
If players have time_played_minutes in Field 23,
even when session time is 0:00, we can use THAT!

SOLUTION: Use player's time_played_minutes, ignore session time.
''')
