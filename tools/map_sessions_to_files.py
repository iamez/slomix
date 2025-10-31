import sqlite3, os

db='bot/etlegacy_production.db'
if not os.path.exists(db):
    print('DB not found:', db)
    raise SystemExit

conn=sqlite3.connect(db)
c=conn.cursor()
# get recent empty sessions
q='''SELECT s.id, s.session_date, s.map_name, s.round_number
FROM sessions s
LEFT JOIN weapon_comprehensive_stats w ON w.session_id = s.id
GROUP BY s.id
HAVING COUNT(w.session_id) = 0
ORDER BY s.id DESC
LIMIT 20
'''
rows = c.execute(q).fetchall()
for sid, sdate, mapn, rnd in rows:
    prefix = sdate.replace(' ', '-')[:15]  # YYYY-MM-DD-HHMMSS
    print('\nSESSION', sid, sdate, mapn, rnd)
    cur = conn.cursor()
    cur.execute("SELECT filename, success FROM processed_files WHERE filename LIKE ?", (prefix+'%',))
    matches = cur.fetchall()
    if matches:
        for m in matches:
            print('  matched processed file:', m)
    else:
        # also try local_stats dir
        ls = [f for f in os.listdir('local_stats') if f.startswith(prefix)] if os.path.exists('local_stats') else []
        for f in ls:
            print('  local file:', f)

conn.close()
