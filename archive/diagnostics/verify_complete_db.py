import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
c = conn.cursor()

# Get all tables
tables = c.execute('SELECT name FROM sqlite_master WHERE type="table"').fetchall()
print(f'📋 Tables: {[t[0] for t in tables]}')
print()

# Count records in each table
print(f'📊 sessions: {c.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]:,}')
print(f'📊 player_comprehensive_stats: {c.execute("SELECT COUNT(*) FROM player_comprehensive_stats").fetchone()[0]:,}')
print(f'📊 weapon_comprehensive_stats: {c.execute("SELECT COUNT(*) FROM weapon_comprehensive_stats").fetchone()[0]:,}')
print(f'📊 session_teams: {c.execute("SELECT COUNT(*) FROM session_teams").fetchone()[0]:,}')
print(f'📊 player_aliases: {c.execute("SELECT COUNT(*) FROM player_aliases").fetchone()[0]:,}')
print(f'📊 processed_files: {c.execute("SELECT COUNT(*) FROM processed_files").fetchone()[0]:,}')
print(f'📊 player_links: {c.execute("SELECT COUNT(*) FROM player_links").fetchone()[0]:,}')
print()

# Column count
cols = len([d[0] for d in c.execute('PRAGMA table_info(player_comprehensive_stats)').fetchall()])
print(f'✅ player_comprehensive_stats columns: {cols} (expected: 53)')

conn.close()
