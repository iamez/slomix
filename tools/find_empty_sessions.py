import sqlite3, os

db='bot/etlegacy_production.db'
if not os.path.exists(db):
    print('DB not found:', db)
    raise SystemExit

c=sqlite3.connect(db).cursor()
q='''SELECT s.id, s.session_date, s.map_name, s.round_number, COUNT(w.session_id) as wcount
FROM sessions s
LEFT JOIN weapon_comprehensive_stats w ON w.session_id = s.id
GROUP BY s.id
HAVING wcount = 0
ORDER BY s.id DESC
LIMIT 50
'''
for row in c.execute(q):
    print(row)
