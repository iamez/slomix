"""Check how many sessions have 0:00 as actual_time."""
import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
c = conn.cursor()

# Get totals
total = c.execute('SELECT COUNT(*) FROM sessions').fetchone()[0]
zero_time = c.execute("SELECT COUNT(*) FROM sessions WHERE actual_time = '0:00'").fetchone()[0]

print(f'Total sessions: {total}')
print(f'Sessions with 0:00 actual_time: {zero_time}')
if total > 0:
    print(f'Percentage: {(zero_time/total*100):.1f}%')
print()

# Breakdown by round
r1_zero = c.execute("SELECT COUNT(*) FROM sessions WHERE actual_time = '0:00' AND round_number = 1").fetchone()[0]
r2_zero = c.execute("SELECT COUNT(*) FROM sessions WHERE actual_time = '0:00' AND round_number = 2").fetchone()[0]

print('Breakdown by round:')
print(f'  Round 1 with 0:00: {r1_zero}')
print(f'  Round 2 with 0:00: {r2_zero}')
print()

# Sample sessions
print('Sample sessions with 0:00:')
rows = c.execute("""
    SELECT id, session_date, map_name, round_number, time_limit, actual_time 
    FROM sessions 
    WHERE actual_time = '0:00' 
    LIMIT 10
""").fetchall()

for r in rows:
    print(f'  Session {r[0]}: {r[1]} | {r[2]:20} | Round {r[3]} | Limit: {r[4]}')

print()
print('All unique actual_time values in database:')
time_values = c.execute("SELECT DISTINCT actual_time, COUNT(*) as count FROM sessions GROUP BY actual_time ORDER BY count DESC").fetchall()
for time_val, count in time_values:
    print(f'  {time_val:10} : {count} sessions')

conn.close()
