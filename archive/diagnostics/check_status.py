import os
import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
c = conn.cursor()

# Check tables
tables = [t[0] for t in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("📊 Database Tables:", tables)
print()

# Check session count and date range
if 'sessions' in tables:
    c.execute('SELECT COUNT(*) FROM sessions')
    session_count = c.fetchone()[0]
    c.execute('SELECT MIN(session_date), MAX(session_date) FROM sessions')
    date_range = c.fetchone()
    print(f"✅ Sessions in DB: {session_count}")
    print(f"   Date range: {date_range[0][:10]} to {date_range[1][:10]}")
    print()

# Count files in local_stats
if os.path.exists('local_stats'):
    stat_files = [f for f in os.listdir('local_stats') if f.endswith('.txt') and '_ws' not in f]
    print(f"📁 Files in local_stats: {len(stat_files)}")
    if stat_files:
        stat_files.sort()
        print(f"   Latest file: {stat_files[-1]}")
else:
    print("❌ local_stats directory not found")

conn.close()
