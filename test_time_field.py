import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
c = conn.cursor()

# Check if time_played_minutes is populated
result = c.execute(
    '''
    SELECT
        s.session_date,
        p.player_name,
        p.dpm,
        p.time_played_minutes,
        p.damage_given
    FROM sessions s
    JOIN player_comprehensive_stats p ON s.id = p.session_id
    WHERE s.session_date LIKE '2025-10-02%'
    ORDER BY p.damage_given DESC
    LIMIT 10
'''
).fetchall()

print("✅ Top 10 players from Oct 2, 2025 session:")
print("=" * 80)
for r in result:
    print(f"{r[1]:20} | {r[4]:6} dmg | {r[2]:6.1f} dpm | {r[3]:6.1f} min")

print(f"\n📊 Total records with time_played > 0:")
count = c.execute(
    'SELECT COUNT(*) FROM player_comprehensive_stats WHERE time_played_minutes > 0'
).fetchone()[0]
print(f"   {count:,} records")

conn.close()
