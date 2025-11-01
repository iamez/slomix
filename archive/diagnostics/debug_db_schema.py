import sqlite3
conn=sqlite3.connect('bot/etlegacy_production.db')
c=conn.cursor()
print('TABLE SQL for weapon_comprehensive_stats:')
for row in c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='weapon_comprehensive_stats'"):
    print(row[0])
print('\nPRAGMA table_info(weapon_comprehensive_stats):')
for row in c.execute('PRAGMA table_info(weapon_comprehensive_stats)'):
    print(row)
print('\nIndexes:')
for row in c.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='weapon_comprehensive_stats'"):
    print(row)
conn.close()
