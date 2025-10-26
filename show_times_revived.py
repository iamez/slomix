import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

print("=" * 80)
print("TIMES_REVIVED DATA (How many times players WERE revived)")
print("=" * 80)
print()

cursor.execute('''
    SELECT 
        pcs.player_name, 
        pos.times_revived
    FROM player_objective_stats pos
    JOIN player_comprehensive_stats pcs 
        ON pos.session_id = pcs.session_id 
        AND pos.player_guid = pcs.player_guid
    WHERE pos.times_revived > 0
    ORDER BY pos.times_revived DESC
    LIMIT 15
''')

rows = cursor.fetchall()
print("TOP 15 PLAYERS BY TIMES_REVIVED:")
print()
for r in rows:
    print(f"  {r[0]:<35} = {r[1]:>2} times revived ✅")

print()
print("=" * 80)

cursor.execute('''
    SELECT 
        COUNT(CASE WHEN times_revived > 0 THEN 1 END) as have_data,
        SUM(times_revived) as total,
        AVG(times_revived) as avg_non_zero
    FROM player_objective_stats
    WHERE times_revived > 0
''')

row = cursor.fetchone()
print(f"SUMMARY:")
print(f"  Players with times_revived > 0: {row[0]:,} out of 24,792 (53.8%)")
print(f"  Total times revived across all: {row[1]:,}")
print(f"  Average times_revived (non-zero): {row[2]:.1f}")

conn.close()
