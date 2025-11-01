#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('bot/bot/etlegacy_production.db')
c = conn.cursor()

c.execute(
    '''
    SELECT player_name, round_number, time_played_seconds,
           time_display, damage_given, dpm
    FROM player_comprehensive_stats
    WHERE session_date="2025-10-02" AND player_name LIKE "%vid%"
    ORDER BY round_number
'''
)

rows = c.fetchall()
print('\nOct 2 vid records in database:')
for r in rows:
    print(f'R{r[1]}: {r[2]}s ({r[3]}) - {r[4]} dmg - {r[5]:.2f} DPM')

# Check all Oct 2
c.execute(
    '''
    SELECT COUNT(*),
           SUM(CASE WHEN time_played_seconds = 0 THEN 1 ELSE 0 END) as zero_time,
           SUM(CASE WHEN time_played_seconds > 0 THEN 1 ELSE 0 END) as valid_time
    FROM player_comprehensive_stats
    WHERE session_date="2025-10-02"
'''
)

total, zero, valid = c.fetchone()
print(f'\nOct 2 totals:')
print(f'  Total records: {total}')
print(f'  Zero time: {zero} ({zero / total * 100:.1f}%)')
print(f'  Valid time: {valid} ({valid / total * 100:.1f}%)')

conn.close()
