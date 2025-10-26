import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
c = conn.cursor()

c.execute('SELECT COUNT(*) FROM player_comprehensive_stats')
print(f'✅ Player records: {c.fetchone()[0]:,}')

c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='player_links'")
print(f'✅ player_links table: {"EXISTS" if c.fetchone() else "MISSING"}')

c.execute('SELECT COUNT(*) FROM sessions')
print(f'✅ Session records: {c.fetchone()[0]:,}')

conn.close()
print('\n🎉 Database ready for bot!')
