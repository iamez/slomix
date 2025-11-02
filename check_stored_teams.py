import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

cursor.execute("""
    SELECT DISTINCT session_start_date 
    FROM session_teams 
    WHERE map_name='ALL' 
    ORDER BY session_start_date DESC 
    LIMIT 10
""")

dates = cursor.fetchall()

if dates:
    print('Sessions with stored teams:')
    for d in dates:
        print(f'  - {d[0]}')
else:
    print('No sessions with stored teams')

conn.close()
