#!/usr/bin/env python3
"""Verify imported data has correct seconds and DPM"""
import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
c = conn.cursor()

print('=' * 80)
print('DATABASE VERIFICATION - Seconds Implementation')
print('=' * 80)

# Check total records
total = c.execute('SELECT COUNT(*) FROM player_comprehensive_stats').fetchone()[0]
print(f'\n📊 Total records: {total}')

# Check time_played_seconds is populated
zero_seconds = c.execute(
    'SELECT COUNT(*) FROM player_comprehensive_stats WHERE time_played_seconds = 0'
).fetchone()[0]

print(f'✅ Records with time_played_seconds > 0: {total - zero_seconds}/{total}')
print(f'❌ Records with time_played_seconds = 0: {zero_seconds}/{total}')

# Sample vid's stats
print('\n--- Sample Data: vid ---')
rows = c.execute(
    '''
    SELECT map_name, round_number,
           damage_given, time_played_seconds, time_display, dpm
    FROM player_comprehensive_stats
    WHERE clean_name LIKE '%vid%'
    ORDER BY id
    LIMIT 5
'''
).fetchall()

print(f'\n{"Map":<20} {"Rnd":<4} {"Dmg":>6} {"Seconds":>8} {"Display":<8} {"DPM":>7}')
print('-' * 65)
for row in rows:
    print(f'{row[0]:<20} {row[1]:<4} {row[2]:>6} {row[3]:>8} {row[4]:<8} {row[5]:>7.2f}')

# Check weighted DPM calculation
print('\n--- Weighted DPM Calculation Test ---')
result = c.execute(
    '''
    SELECT
        SUM(damage_given) as total_dmg,
        SUM(time_played_seconds) as total_sec,
        CASE
            WHEN SUM(time_played_seconds) > 0
            THEN (CAST(SUM(damage_given) AS FLOAT) * 60.0) / SUM(time_played_seconds)
            ELSE 0.0
        END as weighted_dpm
    FROM player_comprehensive_stats
    WHERE clean_name LIKE '%vid%'
'''
).fetchone()

print(f'Total damage: {result[0]}')
print(f'Total seconds: {result[1]}')
print(f'Weighted DPM: {result[2]:.2f}')
print(f'Calculation: ({result[0]} * 60) / {result[1]} = {result[2]:.2f}')

# Check Round 2 differential preservation
print('\n--- Round 2 Differential Check ---')
r2_count = c.execute(
    'SELECT COUNT(*) FROM player_comprehensive_stats WHERE round_number = 2'
).fetchone()[0]
r2_with_time = c.execute(
    'SELECT COUNT(*) FROM player_comprehensive_stats WHERE round_number = 2 AND time_played_seconds > 0'
).fetchone()[0]

print(f'Round 2 records: {r2_count}')
print(f'Round 2 with time > 0: {r2_with_time}/{r2_count}')

if r2_with_time == r2_count:
    print('✅ All Round 2 records have time data! (Bug fixed)')
else:
    print(f'❌ {r2_count - r2_with_time} Round 2 records missing time!')

conn.close()

print('\n' + '=' * 80)
print('VERIFICATION COMPLETE')
print('=' * 80)
print('\nIf all checks passed:')
print('  ✅ Database has seconds-based time')
print('  ✅ DPM calculated correctly')
print('  ✅ Round 2 differential preserved')
print('  → Ready to test bot commands!')
