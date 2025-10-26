import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

print("=" * 80)
print("CHECKING OBJECTIVE STATS IN DATABASE")
print("=" * 80)
print()

# Get a sample from adlernest map
cursor.execute('''
    SELECT 
        s.session_date,
        s.map_name,
        pcs.player_name,
        pos.times_revived,
        pos.kill_assists,
        pos.most_useful_kills,
        pos.useless_kills,
        pos.denied_playtime,
        pos.dynamites_planted
    FROM sessions s
    JOIN player_objective_stats pos ON s.id = pos.session_id
    JOIN player_comprehensive_stats pcs ON pos.session_id = pcs.session_id 
        AND pos.player_guid = pcs.player_guid
    WHERE s.map_name LIKE "%adlernest%"
    LIMIT 10
''')

rows = cursor.fetchall()
print(f"Sample from adlernest map ({len(rows)} players):")
print()
for r in rows:
    print(f"  {r[0]} {r[1]} - {r[2]}:")
    print(f"    revived={r[3]}, assists={r[4]}, useful={r[5]}, " +
          f"useless={r[6]}, denied={r[7]}, dynamites={r[8]}")

print()
print("=" * 80)

# Check overall stats
cursor.execute('''
    SELECT 
        COUNT(*) as total,
        SUM(times_revived) as total_revived,
        SUM(kill_assists) as total_assists,
        SUM(most_useful_kills) as total_useful,
        SUM(useless_kills) as total_useless,
        SUM(denied_playtime) as total_denied,
        SUM(dynamites_planted) as total_dynamites
    FROM player_objective_stats
''')

row = cursor.fetchone()
print(f"OVERALL DATABASE STATS:")
print(f"  Total players: {row[0]:,}")
print(f"  Total times_revived: {row[1]:,}")
print(f"  Total kill_assists: {row[2]:,}")
print(f"  Total most_useful_kills: {row[3]:,}")
print(f"  Total useless_kills: {row[4]:,}")
print(f"  Total denied_playtime: {row[5]:,}")
print(f"  Total dynamites_planted: {row[6]:,}")

conn.close()
