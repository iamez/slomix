"""Check October 2nd session details and scores"""
import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

# Get all sessions from October 2nd
print("=" * 80)
print("SESSIONS ON OCTOBER 2, 2025")
print("=" * 80)

cursor.execute('''
    SELECT id, session_date, map_name, round_number, actual_time
    FROM sessions 
    WHERE session_date LIKE '2025-10-02%' 
    ORDER BY session_date DESC
''')

sessions = cursor.fetchall()
print(f"\nFound {len(sessions)} sessions:\n")

for session in sessions:
    session_id, date, map_name, round_num, actual_time = session
    print(f"Session ID: {session_id}")
    print(f"Date: {date}")
    print(f"Map: {map_name}")
    print(f"Round: {round_num}")
    print(f"Time: {actual_time}")
    
    # Get team stats for this session
    cursor.execute('''
        SELECT 
            team,
            COUNT(*) as player_count,
            SUM(kills) as total_kills,
            SUM(deaths) as total_deaths,
            SUM(damage_given) as total_damage
        FROM player_comprehensive_stats
        WHERE session_id = ?
        GROUP BY team
        ORDER BY team
    ''', (session_id,))
    
    teams = cursor.fetchall()
    print("\n  Team Stats:")
    for team_data in teams:
        team, players, kills, deaths, damage = team_data
        team_name = "Axis" if team == 1 else "Allies" if team == 2 else f"Team {team}"
        print(f"    {team_name}: {players} players | {kills} kills | {deaths} deaths | {damage:,} damage")
    
    # Get top 5 players by kills
    cursor.execute('''
        SELECT player_name, team, kills, deaths, damage_given
        FROM player_comprehensive_stats
        WHERE session_id = ?
        ORDER BY kills DESC
        LIMIT 5
    ''', (session_id,))
    
    top_players = cursor.fetchall()
    print("\n  Top 5 Players:")
    for i, player_data in enumerate(top_players, 1):
        name, team, kills, deaths, damage = player_data
        team_name = "Axis" if team == 1 else "Allies"
        print(f"    {i}. {name} ({team_name}): {kills}K / {deaths}D / {damage:,} DMG")
    
    print("\n" + "-" * 80 + "\n")

conn.close()
