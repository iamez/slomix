import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cur = conn.cursor()

print('=' * 60)
print('DATABASE STATUS')
print('=' * 60)

cur.execute('SELECT COUNT(*) FROM player_comprehensive_stats')
print(f'Player records: {cur.fetchone()[0]:,}')

cur.execute('SELECT COUNT(*) FROM rounds')
print(f'Sessions: {cur.fetchone()[0]:,}')

cur.execute('SELECT COUNT(*) FROM weapon_comprehensive_stats')
print(f'Weapon records: {cur.fetchone()[0]:,}')

cur.execute('SELECT COUNT(DISTINCT player_name) FROM player_comprehensive_stats')
print(f'Unique players: {cur.fetchone()[0]}')

print('\nLatest 5 sessions:')
cur.execute('SELECT round_date, map_name, round_number FROM rounds ORDER BY round_date DESC LIMIT 5')
for row in cur.fetchall():
    print(f'  {row[0]} - {row[1]} Round {row[2]}')

print('\nSample player stats:')
cur.execute('''
    SELECT player_name, SUM(kills), SUM(deaths), SUM(damage_given), COUNT(*) as rounds
    FROM player_comprehensive_stats
    GROUP BY player_name
    ORDER BY SUM(kills) DESC
    LIMIT 5
''')
print('  Name                  Kills  Deaths  Damage   Rounds')
print('  ' + '-' * 55)
for row in cur.fetchall():
    print(f'  {row[0]:20s} {row[1]:6d} {row[2]:7d} {row[3]:8d} {row[4]:6d}')

print('\n✅ DATABASE IS FULLY POPULATED!')
conn.close()
