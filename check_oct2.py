import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
c = conn.cursor()

# Check October 2nd sessions
rows = c.execute(
    '''
    SELECT session_date, map_name, round_number
    FROM sessions
    WHERE session_date LIKE "2025-10-02%"
    ORDER BY session_date
'''
).fetchall()

print(f"📅 October 2nd, 2025 sessions: {len(rows)}")
print()

if rows:
    for date, map_name, round_num in rows:
        print(f"  {date} - {map_name} (Round {round_num})")
else:
    print("  ❌ No sessions found for October 2nd!")
    print()
    # Check what's the latest
    latest = c.execute('SELECT MAX(session_date) FROM sessions').fetchone()[0]
    print(f"  Latest session in DB: {latest}")

conn.close()
