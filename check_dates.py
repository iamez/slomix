import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

# Get all unique session dates
cursor.execute('SELECT DISTINCT session_date FROM sessions ORDER BY session_date DESC')
dates = cursor.fetchall()

print('📅 Session dates in database:')
print('='*50)
for row in dates:
    cursor.execute('SELECT COUNT(*) FROM sessions WHERE session_date = ?', (row[0],))
    count = cursor.fetchone()[0]
    print(f'  {row[0]:<20} ({count} sessions)')

print(f'\n✅ Total unique dates: {len(dates)}')

# Get most recent
cursor.execute('SELECT session_date FROM sessions ORDER BY datetime(session_date) DESC LIMIT 1')
last = cursor.fetchone()
print(f'🔍 Most recent session: {last[0] if last else "None"}')

conn.close()
