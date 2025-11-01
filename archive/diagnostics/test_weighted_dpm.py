import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
c = conn.cursor()

# Count Oct 2 records with time_played_minutes = 0
zero_count = c.execute(
    '''
    SELECT COUNT(*)
    FROM sessions s
    JOIN player_comprehensive_stats p ON s.id = p.session_id
    WHERE s.session_date LIKE '2025-10-02%'
    AND p.time_played_minutes = 0
'''
).fetchone()[0]

total_count = c.execute(
    '''
    SELECT COUNT(*)
    FROM sessions s
    JOIN player_comprehensive_stats p ON s.id = p.session_id
    WHERE s.session_date LIKE '2025-10-02%'
'''
).fetchone()[0]

print(f"📊 Oct 2, 2025 session:")
print(f"   Total records: {total_count}")
print(f"   With time=0: {zero_count} ({zero_count / total_count * 100:.1f}%)")
print(
    f"   With time>0: {total_count -
                       zero_count} ({(total_count -
                                      zero_count) /
                                     total_count *
                                     100:.1f}%)"
)

# Now test the weighted DPM calculation
print(f"\n🧪 Testing weighted DPM calculation:")
result = c.execute(
    '''
    SELECT
        p.player_name,
        SUM(p.damage_given) as total_damage,
        SUM(p.time_played_minutes) as total_time,
        CASE
            WHEN SUM(p.time_played_minutes) > 0
            THEN SUM(p.damage_given) / SUM(p.time_played_minutes)
            ELSE 0
        END as weighted_dpm,
        COUNT(*) as rounds
    FROM sessions s
    JOIN player_comprehensive_stats p ON s.id = p.session_id
    WHERE s.session_date LIKE '2025-10-02%'
    GROUP BY p.player_guid
    HAVING SUM(p.damage_given) > 10000
    ORDER BY weighted_dpm DESC
    LIMIT 5
'''
).fetchall()

print(f"   Top 5 players by WEIGHTED DPM:")
for r in result:
    print(f"   {r[0]:20} | {r[1]:6.0f} dmg | {r[2]:6.1f} min | {r[3]:6.1f} DPM | {r[4]} rounds")

conn.close()
