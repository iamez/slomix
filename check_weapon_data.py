import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
c = conn.cursor()

print('=== WS_SYRINGE Stats (Oct 2) ===')
c.execute(
    '''
    SELECT player_name, SUM(kills), SUM(deaths), SUM(headshots)
    FROM weapon_comprehensive_stats
    WHERE weapon_name='WS_SYRINGE' AND session_date='2025-10-02'
    GROUP BY player_name
    ORDER BY SUM(kills) DESC
    LIMIT 5
'''
)
for row in c.fetchall():
    print(f'{row[0]:20} Kills:{row[1]:3} Deaths:{row[2]:3} HS:{row[3]:3}')

print('\n=== WS_COLT Stats (Oct 2) ===')
c.execute(
    '''
    SELECT player_name, SUM(kills), SUM(deaths), SUM(headshots)
    FROM weapon_comprehensive_stats
    WHERE weapon_name='WS_COLT' AND session_date='2025-10-02'
    GROUP BY player_name
    ORDER BY SUM(kills) DESC
    LIMIT 5
'''
)
for row in c.fetchall():
    print(f'{row[0]:20} Kills:{row[1]:3} Deaths:{row[2]:3} HS:{row[3]:3}')

print('\n=== WS_LUGER Stats (Oct 2) ===')
c.execute(
    '''
    SELECT player_name, SUM(kills), SUM(deaths), SUM(headshots)
    FROM weapon_comprehensive_stats
    WHERE weapon_name='WS_LUGER' AND session_date='2025-10-02'
    GROUP BY player_name
    ORDER BY SUM(kills) DESC
    LIMIT 5
'''
)
for row in c.fetchall():
    print(f'{row[0]:20} Kills:{row[1]:3} Deaths:{row[2]:3} HS:{row[3]:3}')

conn.close()
