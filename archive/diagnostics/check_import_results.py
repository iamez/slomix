import sqlite3

db = sqlite3.connect('etlegacy_production.db')
c = db.cursor()

print('📊 IMPORT RESULTS:')
print('=' * 60)

# Player records
total = c.execute('SELECT COUNT(*) FROM player_comprehensive_stats').fetchone()[0]
print(f'Player records: {total:,}')

# Sessions
sessions = c.execute('SELECT COUNT(*) FROM sessions').fetchone()[0]
print(f'Sessions: {sessions:,}')

# Zero-time records
zero_times = c.execute('SELECT COUNT(*) FROM player_comprehensive_stats WHERE time_played_seconds = 0').fetchone()[0]
print(f'Zero-time records: {zero_times:,}')

# Check for duplicates
dup_check = c.execute('''
    SELECT COUNT(*) - COUNT(DISTINCT session_id || player_guid)
    FROM player_comprehensive_stats
''').fetchone()[0]
print(f'Duplicate records: {dup_check:,}')

print('\n📋 SESSIONS TABLE SCHEMA:')
print('=' * 60)
for row in c.execute('PRAGMA table_info(sessions)').fetchall():
    print(f'  {row[1]:20} {row[2]}')

db.close()
