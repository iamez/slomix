import sqlite3

# Check if the bot query is creating duplicates
conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

# Get session IDs for October 2nd
cursor.execute("""
    SELECT id 
    FROM sessions 
    WHERE SUBSTR(session_date, 1, 10) = '2025-10-02'
    ORDER BY id ASC
""")
session_ids = [row[0] for row in cursor.fetchall()]
print(f"Session IDs for Oct 2nd: {len(session_ids)} sessions")
print(f"IDs: {session_ids[:5]}... (showing first 5)")

session_ids_str = ','.join('?' * len(session_ids))

# Run the BROKEN query from the bot
broken_query = f'''
    SELECT p.player_name,
           SUM(p.kills) as kills,
           SUM(p.deaths) as deaths,
           CASE
               WHEN SUM(p.time_played_seconds) > 0
               THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
               ELSE 0
           END as weighted_dpm,
           COALESCE(SUM(w.hits), 0) as total_hits,
           COALESCE(SUM(w.shots), 0) as total_shots
    FROM player_comprehensive_stats p
    LEFT JOIN (
        SELECT session_id, player_guid,
               SUM(hits) as hits,
               SUM(shots) as shots
        FROM weapon_comprehensive_stats
        WHERE weapon_name NOT IN ('WS_GRENADE', 'WS_SYRINGE', 'WS_DYNAMITE', 'WS_AIRSTRIKE', 'WS_ARTILLERY', 'WS_SATCHEL', 'WS_LANDMINE')
        GROUP BY session_id, player_guid
    ) w ON p.session_id = w.session_id AND p.player_guid = w.player_guid
    WHERE p.session_id IN ({session_ids_str})
    GROUP BY p.player_name
    ORDER BY kills DESC
'''

print("\n🔴 BROKEN Query Results (from bot):")
print(f"{'Player':<20} {'Kills':<10} {'Deaths':<10} {'DPM':<10}")
print("="*60)
cursor.execute(broken_query, session_ids)
for row in cursor.fetchall():
    print(f"{row[0]:<20} {row[1]:<10} {row[2]:<10} {row[3]:<10.1f}")

# Run the CORRECT query (without weapon join)
correct_query = f'''
    SELECT p.player_name,
           SUM(p.kills) as kills,
           SUM(p.deaths) as deaths,
           CASE
               WHEN SUM(p.time_played_seconds) > 0
               THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
               ELSE 0
           END as weighted_dpm
    FROM player_comprehensive_stats p
    WHERE p.session_id IN ({session_ids_str})
    GROUP BY p.player_name
    ORDER BY kills DESC
'''

print("\n\n✅ CORRECT Query Results (without weapon join):")
print(f"{'Player':<20} {'Kills':<10} {'Deaths':<10} {'DPM':<10}")
print("="*60)
cursor.execute(correct_query, session_ids)
for row in cursor.fetchall():
    print(f"{row[0]:<20} {row[1]:<10} {row[2]:<10} {row[3]:<10.1f}")

conn.close()
