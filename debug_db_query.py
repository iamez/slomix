import sqlite3
import os
db='bot/etlegacy_production.db'
if not os.path.exists(db):
    print('DB not found:', db)
    raise SystemExit(1)
conn=sqlite3.connect(db)
c=conn.cursor()
print('PRAGMA table_info(sessions):')
for row in c.execute("PRAGMA table_info(sessions)"):
    print(row)

print('\nRecent sessions for map braundorf_b4 (limit 20):')
for row in c.execute("SELECT id, session_date, map_name, round_number FROM sessions WHERE map_name LIKE '%braundorf%' ORDER BY id DESC LIMIT 20"):
    print(row)

print('\nSession id 3212 player counts:')
for row in c.execute("SELECT COUNT(*) FROM player_comprehensive_stats WHERE session_id = ?", (3212,)):
    print(row)

print('\nWeapon rows for session 3212:')
for row in c.execute("SELECT COUNT(*), SUM(hits), SUM(shots), SUM(headshots) FROM weapon_comprehensive_stats WHERE session_id = ?", (3212,)):
    print(row)

# print example session for the braundorf file time
for row in c.execute("SELECT id, session_date, map_name, round_number FROM sessions ORDER BY id DESC LIMIT 10"):
    print('recent session:', row)

conn.close()
