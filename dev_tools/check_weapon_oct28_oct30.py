import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

for date in ['2025-10-28', '2025-10-30']:
    print(f"\n{'='*60}")
    print(f"📅 Checking {date}")
    print('='*60)
    
    # Get round IDs
    cursor.execute(f"SELECT id FROM rounds WHERE round_date LIKE '{date}%'")
    session_ids = [row[0] for row in cursor.fetchall()]
    print(f"\nFound {len(session_ids)} sessions")
    
    if session_ids:
        # Check weapon stats count
        cursor.execute(f"""
            SELECT COUNT(*)
            FROM weapon_comprehensive_stats
            WHERE round_id IN ({','.join('?' * len(session_ids))})
        """, session_ids)
        weapon_count = cursor.fetchone()[0]
        print(f"Weapon records: {weapon_count}")
        
        # Sample weapon data
        cursor.execute(f"""
            SELECT round_id, player_name, weapon_name, hits, shots, headshots
            FROM weapon_comprehensive_stats
            WHERE round_id IN ({','.join('?' * len(session_ids))})
            LIMIT 5
        """, session_ids)
        
        print("\n🔫 Sample weapon stats:")
        for row in cursor.fetchall():
            sid, name, weapon, hits, shots, hs = row
            acc = (hits / shots * 100) if shots > 0 else 0
            print(f"  {name} - {weapon}: {hits}/{shots} ({acc:.1f}%), {hs} HS")
        
        # Check aggregated player stats
        cursor.execute(f"""
            SELECT p.player_name,
                COALESCE(SUM(w.hits), 0) as total_hits,
                COALESCE(SUM(w.shots), 0) as total_shots,
                COALESCE(SUM(w.headshots), 0) as total_hs,
                SUM(p.headshot_kills) as hsk
            FROM player_comprehensive_stats p
            LEFT JOIN (
                SELECT round_id, player_guid,
                    SUM(hits) as hits,
                    SUM(shots) as shots,
                    SUM(headshots) as headshots
                FROM weapon_comprehensive_stats
                WHERE weapon_name NOT IN (
                    'WS_GRENADE', 'WS_SYRINGE', 'WS_DYNAMITE',
                    'WS_AIRSTRIKE', 'WS_ARTILLERY', 'WS_SATCHEL',
                    'WS_LANDMINE'
                )
                GROUP BY round_id, player_guid
            ) w ON p.round_id = w.round_id 
               AND p.player_guid = w.player_guid
            WHERE p.round_id IN ({','.join('?' * len(session_ids))})
            GROUP BY p.player_name
            ORDER BY total_hits DESC
            LIMIT 5
        """, session_ids)
        
        print("\n👥 Top 5 players (aggregated weapon stats):")
        for row in cursor.fetchall():
            name, hits, shots, hs, hsk = row
            acc = (hits / shots * 100) if shots > 0 else 0
            hs_rate = (hs / hits * 100) if hits > 0 else 0
            print(f"  {name}: {hits}/{shots} ({acc:.1f}% ACC)")
            print(f"    {hs} HS ({hs_rate:.1f}%), HSK in player_stats: {hsk}")

conn.close()
