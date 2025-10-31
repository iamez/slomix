import sqlite3
import sys

DB = 'bot/etlegacy_production.db'

try:
    conn = sqlite3.connect(DB)
    c = conn.cursor()
except Exception as e:
    print('ERROR: could not open DB', DB, e)
    sys.exit(1)

print('DB Health Check:', DB)
print('----------------------------------------')

# Sessions overview
q = '''SELECT 
    COUNT(*) AS total_sessions,
    SUM(CASE WHEN weapon_rows = 0 THEN 1 ELSE 0 END) AS missing_weapons,
    SUM(CASE WHEN weapon_rows > 0 THEN 1 ELSE 0 END) AS has_weapons
FROM (
    SELECT s.id, COUNT(w.id) AS weapon_rows
    FROM sessions s
    LEFT JOIN weapon_comprehensive_stats w ON w.session_id = s.id
    GROUP BY s.id
);'''
row = c.execute(q).fetchone()
print('Sessions overview:')
print(' total_sessions | missing_weapons | has_weapons')
print(' ', row)
print()

# processed_files
q = "SELECT COUNT(*) AS total, SUM(success) AS successes, SUM(CASE WHEN success=0 THEN 1 ELSE 0 END) AS failures FROM processed_files"
pf = c.execute(q).fetchone()
print('Processed files: total, successes, failures')
print(' ', pf)
print()

# player_comprehensive_stats completeness
cols = ['kills','deaths','damage_given','time_played_seconds','accuracy','dpm','headshot_kills']
print('Player_comprehensive_stats completeness (NULL counts):')
total_players = c.execute('SELECT COUNT(*) FROM player_comprehensive_stats').fetchone()[0]
print(' Total player rows:', total_players)
for col in cols:
    q = f"SELECT SUM(CASE WHEN {col} IS NULL THEN 1 ELSE 0 END) FROM player_comprehensive_stats"
    nulls = c.execute(q).fetchone()[0]
    print(f'  {col}: NULLs={nulls}')
print()

# weapon_comprehensive_stats completeness
wcols = ['weapon_name','hits','shots','headshots','accuracy','player_name','player_guid']
print('Weapon_comprehensive_stats completeness (NULL counts, shots=0 count):')
total_weapons = c.execute('SELECT COUNT(*) FROM weapon_comprehensive_stats').fetchone()[0]
print(' Total weapon rows:', total_weapons)
for col in wcols:
    q = f"SELECT SUM(CASE WHEN {col} IS NULL THEN 1 ELSE 0 END) FROM weapon_comprehensive_stats"
    nulls = c.execute(q).fetchone()[0]
    print(f'  {col}: NULLs={nulls}')
shots0 = c.execute('SELECT SUM(CASE WHEN shots=0 OR shots IS NULL THEN 1 ELSE 0 END) FROM weapon_comprehensive_stats').fetchone()[0]
print('  shots==0 or NULL rows:', shots0)
print()

# Recent sessions summary
print('Recent sessions (last 10): id | session_date | map_name | round | player_rows | weapon_rows')
q = '''SELECT s.id, s.session_date, s.map_name, s.round_number,
    COALESCE(p.player_count,0) as player_rows, COALESCE(w.weapon_count,0) as weapon_rows
FROM sessions s
LEFT JOIN (
    SELECT session_id, COUNT(*) as player_count FROM player_comprehensive_stats GROUP BY session_id
) p ON p.session_id = s.id
LEFT JOIN (
    SELECT session_id, COUNT(*) as weapon_count FROM weapon_comprehensive_stats GROUP BY session_id
) w ON w.session_id = s.id
ORDER BY s.id DESC LIMIT 10'''
for r in c.execute(q).fetchall():
    print(' ', r)

# Show any player rows with NULL accuracy (limit 20)
print('\nSample player rows with NULL accuracy (up to 20):')
q = "SELECT id, session_id, player_guid, player_name, kills, deaths, accuracy FROM player_comprehensive_stats WHERE accuracy IS NULL LIMIT 20"
rows = c.execute(q).fetchall()
if not rows:
    print(' None')
else:
    for r in rows:
        print(' ', r)

# Show any weapon rows with NULL player_name or weapon_name
print('\nSample weapon rows with NULL player_name or weapon_name (up to 20):')
q = "SELECT id, session_id, player_guid, player_name, weapon_name, hits, shots, accuracy FROM weapon_comprehensive_stats WHERE player_name IS NULL OR weapon_name IS NULL LIMIT 20"
rows = c.execute(q).fetchall()
if not rows:
    print(' None')
else:
    for r in rows:
        print(' ', r)

conn.close()
print('\nDB health check complete')
