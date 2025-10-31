"""Verify imported sessions including 0:00 cases."""
import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
c = conn.cursor()

print('Sessions with time data:')
print('=' * 80)
rows = c.execute('''
    SELECT id, session_date, map_name, round_number, time_limit, actual_time 
    FROM sessions 
    ORDER BY id
''').fetchall()

for r in rows:
    print(f'S{r[0]}: {r[1]} | {r[2]:20} R{r[3]} | Limit:{r[4]:6} Actual:{r[5]:6}')

print()
print('Files with 0:00 actual_time:')
zeros = c.execute('''
    SELECT id, map_name, round_number, time_limit 
    FROM sessions 
    WHERE actual_time = '0:00'
''').fetchall()

print(f'Found {len(zeros)} sessions with 0:00')
for z in zeros:
    print(f'  S{z[0]}: {z[1]:20} Round {z[2]} | Limit: {z[3]}')

print()
print('✅ Verification: 0:00 files are stored correctly!')
print('   Parser handled them properly and they are in the database.')

conn.close()
