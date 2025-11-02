import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

# Get session IDs for Oct 9 (using LIKE to match date prefix)
cursor.execute("SELECT id FROM sessions WHERE session_date LIKE '2025-10-09%'")
session_ids = [row[0] for row in cursor.fetchall()]
print(f"📅 Found {len(session_ids)} sessions for 2025-10-09")
print(f"Session IDs: {session_ids[:5]}... (showing first 5)")

if session_ids:
    # Check weapon stats
    cursor.execute(f"""
        SELECT session_id, player_name, weapon_name, hits, shots, headshots
        FROM weapon_comprehensive_stats
        WHERE session_id IN ({','.join('?' * len(session_ids))})
        LIMIT 10
    """, session_ids)
    
    weapon_rows = cursor.fetchall()
    print(f"\n🔫 Sample weapon stats ({len(weapon_rows)} shown):")
    for row in weapon_rows:
        print(f"  Session {row[0]}: {row[1]} - {row[2]}: {row[3]} hits / {row[4]} shots, {row[5]} HS")
    
    # Count total
    cursor.execute(f"""
        SELECT COUNT(*)
        FROM weapon_comprehensive_stats
        WHERE session_id IN ({','.join('?' * len(session_ids))})
    """, session_ids)
    total = cursor.fetchone()[0]
    print(f"\n📊 Total weapon records for 2025-10-09: {total}")
    
    # Check aggregated stats
    cursor.execute(f"""
        SELECT p.player_name,
            COALESCE(SUM(w.hits), 0) as total_hits,
            COALESCE(SUM(w.shots), 0) as total_shots,
            COALESCE(SUM(w.headshots), 0) as total_headshots
        FROM player_comprehensive_stats p
        LEFT JOIN (
            SELECT session_id, player_guid,
                SUM(hits) as hits,
                SUM(shots) as shots,
                SUM(headshots) as headshots
            FROM weapon_comprehensive_stats
            WHERE weapon_name NOT IN ('WS_GRENADE', 'WS_SYRINGE', 'WS_DYNAMITE', 'WS_AIRSTRIKE', 'WS_ARTILLERY', 'WS_SATCHEL', 'WS_LANDMINE')
            GROUP BY session_id, player_guid
        ) w ON p.session_id = w.session_id AND p.player_guid = w.player_guid
        WHERE p.session_id IN ({','.join('?' * len(session_ids))})
        GROUP BY p.player_name
        ORDER BY p.player_name
        LIMIT 5
    """, session_ids)
    
    print(f"\n👥 Aggregated player weapon stats (top 5):")
    for row in cursor.fetchall():
        name, hits, shots, hs = row
        acc = (hits / shots * 100) if shots > 0 else 0
        print(f"  {name}: {hits} hits / {shots} shots ({acc:.1f}% ACC), {hs} HS")

conn.close()
