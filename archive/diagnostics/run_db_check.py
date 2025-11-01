import sqlite3
conn=sqlite3.connect('bot/etlegacy_production.db')
c=conn.cursor()
for sid in (3208,3212):
    print('\nSession', sid)
    for row in c.execute('SELECT COUNT(*) FROM player_comprehensive_stats WHERE session_id=?',(sid,)):
        print('players:', row[0])
    for row in c.execute('SELECT COUNT(*), SUM(hits), SUM(shots), SUM(headshots) FROM weapon_comprehensive_stats WHERE session_id=?',(sid,)):
        print('weapons rows, total_hits, total_shots, total_headshots:', row)
conn.close()
