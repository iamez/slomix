#!/usr/bin/env python3
"""Check what's missing from 2025-10-02 import"""

import os
import sqlite3
from collections import defaultdict
from glob import glob

# Connect to database
conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

# Get sessions from database for 2025-10-02
cursor.execute(
    '''
    SELECT map_name, round_number, actual_time
    FROM sessions
    WHERE session_date = '2025-10-02'
    ORDER BY map_name, round_number
'''
)
db_sessions = cursor.fetchall()

print('\n' + '=' * 70)
print('🔍 DATABASE vs FILES COMPARISON (2025-10-02)')
print('=' * 70)

print('\n📊 DATABASE SESSIONS:')
for row in db_sessions:
    print(f'  {row[0]:20s} | Round {row[1]} | Time: {row[2]}')
print(f'\n  Total: {len(db_sessions)} rounds')

# Get stat files
stat_files = sorted(glob('local_stats/2025-10-02*.txt'))
print(f'\n📁 STAT FILES:')
for f in stat_files:
    filename = os.path.basename(f)
    print(f'  {filename}')
print(f'\n  Total: {len(stat_files)} files')

# Find which files are imported
cursor.execute(
    '''
    SELECT DISTINCT map_name, round_number
    FROM sessions
    WHERE session_date = '2025-10-02'
    ORDER BY map_name, round_number
'''
)
db_map_rounds = set(cursor.fetchall())

# Parse filenames to see which should exist

file_map_rounds = defaultdict(int)
for f in stat_files:
    filename = os.path.basename(f)
    parts = filename.split('-')
    # Extract map name and round
    if 'round-1' in filename:
        round_num = 1
        map_part = filename.split('-round-1')[0]
        map_name = '-'.join(map_part.split('-')[4:])  # Everything after date-time
        file_map_rounds[(map_name, round_num)] += 1
    elif 'round-2' in filename:
        round_num = 2
        map_part = filename.split('-round-2')[0]
        map_name = '-'.join(map_part.split('-')[4:])
        file_map_rounds[(map_name, round_num)] += 1

print('\n' + '=' * 70)
print('❌ MISSING FROM DATABASE:')
print('=' * 70)
missing_count = 0
for (map_name, round_num), count in sorted(file_map_rounds.items()):
    if (map_name, round_num) not in db_map_rounds:
        print(f'  ❌ {map_name:20s} | Round {round_num} ({count} file(s))')
        missing_count += count
    elif count > 1:
        print(f'  ⚠️  {map_name:20s} | Round {round_num} ({count} files, only 1 in DB)')
        missing_count += count - 1

if missing_count == 0:
    print('  ✅ All files imported!')
else:
    print(f'\n  Total missing: {missing_count} rounds')

# Check escape specifically
print('\n' + '=' * 70)
print('🏃 ESCAPE MAP DETAIL:')
print('=' * 70)
escape_files = [f for f in stat_files if 'escape' in f]
print(f'\nEscape files found: {len(escape_files)}')
for f in escape_files:
    print(f'  {os.path.basename(f)}')

cursor.execute(
    '''
    SELECT id, round_number, actual_time
    FROM sessions
    WHERE session_date = '2025-10-02' AND map_name = 'te_escape2'
    ORDER BY id
'''
)
escape_sessions = cursor.fetchall()
print(f'\nEscape sessions in DB: {len(escape_sessions)}')
for row in escape_sessions:
    print(f'  ID {row[0]:4d} | Round {row[1]} | Time: {row[2]}')

print('\n' + '=' * 70)
print('💡 SOLUTION: Import missing escape files')
print('=' * 70)
print('\nRun this command:')
print(
    'python tools/simple_bulk_import.py local_stats/2025-10-02-221225-te_escape2-round-1.txt local_stats/2025-10-02-221711-te_escape2-round-2.txt'
)

conn.close()
