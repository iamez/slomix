import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

# Check Oct 28 sessions
cursor.execute("SELECT COUNT(*) FROM rounds WHERE round_date LIKE '2025-10-28%'")
oct28_count = cursor.fetchone()[0]
print(f"Oct 28 sessions in DB: {oct28_count}")

# Check Oct 30 sessions
cursor.execute("SELECT COUNT(*) FROM rounds WHERE round_date LIKE '2025-10-30%'")
oct30_count = cursor.fetchone()[0]
print(f"Oct 30 sessions in DB: {oct30_count}")

if oct28_count > 0 or oct30_count > 0:
    print("\n📅 Sample sessions:")
    cursor.execute("""
        SELECT round_date, map_name, id
        FROM rounds 
        WHERE round_date LIKE '2025-10-28%' OR round_date LIKE '2025-10-30%'
        ORDER BY round_date
        LIMIT 10
    """)
    for row in cursor.fetchall():
        print(f"  ID {row[2]}: {row[0]} - {row[1]}")
    
    # Check weapon stats for these sessions
    print("\n🔫 Checking weapon stats...")
    cursor.execute("""
        SELECT COUNT(*) FROM weapon_comprehensive_stats
        WHERE round_id IN (
            SELECT id FROM rounds 
            WHERE round_date LIKE '2025-10-28%' OR round_date LIKE '2025-10-30%'
        )
    """)
    weapon_count = cursor.fetchone()[0]
    print(f"Weapon stats records: {weapon_count}")
    
    if weapon_count > 0:
        cursor.execute("""
            SELECT w.player_name, SUM(w.hits), SUM(w.shots), SUM(w.headshots)
            FROM weapon_comprehensive_stats w
            WHERE w.round_id IN (
                SELECT id FROM rounds 
                WHERE round_date LIKE '2025-10-28%' OR round_date LIKE '2025-10-30%'
            )
            AND w.weapon_name NOT IN (
                'WS_GRENADE', 'WS_SYRINGE', 'WS_DYNAMITE',
                'WS_AIRSTRIKE', 'WS_ARTILLERY', 'WS_SATCHEL', 'WS_LANDMINE'
            )
            GROUP BY w.player_name
            ORDER BY SUM(w.hits) DESC
            LIMIT 5
        """)
        print("\n👥 Top 5 players by hits:")
        for row in cursor.fetchall():
            name, hits, shots, hs = row
            acc = (hits / shots * 100) if shots > 0 else 0
            print(f"  {name}: {hits}/{shots} ({acc:.1f}% ACC), {hs} HS")

conn.close()
