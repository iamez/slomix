"""Check October 2nd sessions - Who actually WON based on objectives"""
import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

print("=" * 80)
print("OCTOBER 2, 2025 - GAME OUTCOMES")
print("=" * 80)

# Get unique map sessions (both rounds together)
cursor.execute('''
    SELECT DISTINCT map_name
    FROM sessions 
    WHERE session_date LIKE '2025-10-02%'
''')

maps = [row[0] for row in cursor.fetchall()]

print(f"\nTotal maps played: {len(maps)}\n")

for map_name in maps:
    print(f"\n{'=' * 80}")
    print(f"MAP: {map_name}")
    print(f"{'=' * 80}")
    
    # Get both rounds for this map
    cursor.execute('''
        SELECT id, session_date, round_number, actual_time
        FROM sessions
        WHERE session_date LIKE '2025-10-02%' AND map_name = ?
        ORDER BY id
        LIMIT 2
    ''', (map_name,))
    
    rounds = cursor.fetchall()
    
    for session_id, date, round_num, time in rounds:
        print(f"\nRound {round_num} (Session {session_id}):")
        print(f"Time: {time}")
        
        # Get team stats
        cursor.execute('''
            SELECT 
                team,
                COUNT(*) as players,
                SUM(kills) as kills,
                SUM(deaths) as deaths,
                SUM(objectives_completed) as obj_completed,
                SUM(objectives_destroyed) as obj_destroyed,
                SUM(dynamites_planted) as dyna_planted,
                SUM(dynamites_defused) as dyna_defused
            FROM player_comprehensive_stats
            WHERE session_id = ?
            GROUP BY team
            ORDER BY team
        ''', (session_id,))
        
        teams = cursor.fetchall()
        
        for team_data in teams:
            team, players, kills, deaths, obj_c, obj_d, dyna_p, dyna_def = team_data
            team_name = "AXIS" if team == 1 else "ALLIES"
            print(f"  {team_name:7} ({players} players):")
            print(f"    Combat: {kills}K / {deaths}D")
            print(f"    Objectives: Completed={obj_c}, Destroyed={obj_d}")
            print(f"    Dynamites: Planted={dyna_p}, Defused={dyna_def}")

conn.close()
