#!/usr/bin/env python3
"""Check how to determine round winners from player stats"""

import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
c = conn.cursor()

print("=" * 80)
print("Checking player stats for 2025-10-30 to find round winners")
print("=" * 80)

# Get a sample round
c.execute("""
    SELECT DISTINCT map_name, round_number, session_id
    FROM player_comprehensive_stats
    WHERE session_date LIKE '2025-10-30%'
    ORDER BY session_id
    LIMIT 3
""")

for map_name, round_num, sess_id in c.fetchall():
    print(f"\n{map_name} - Round {round_num} (session_id: {sess_id}):")
    
    # Get team summary
    c.execute("""
        SELECT team, 
               COUNT(*) as players,
               SUM(kills) as total_kills,
               SUM(deaths) as total_deaths,
               SUM(damage_given) as total_dmg
        FROM player_comprehensive_stats
        WHERE session_id = ? AND round_number = ?
        GROUP BY team
        ORDER BY team
    """, (sess_id, round_num))
    
    teams = c.fetchall()
    for team, players, kills, deaths, dmg in teams:
        print(f"  Team {team}: {players} players, {kills} kills, {deaths} deaths, {dmg} damage")

# Now check if there's any other field that indicates winners
print("\n" + "=" * 80)
print("Checking sessions table for any usable fields:")
print("=" * 80)

c.execute("""
    SELECT id, map_name, round_number, defender_team, winner_team, 
           time_limit, actual_time
    FROM sessions
    WHERE session_date LIKE '2025-10-30%'
    LIMIT 5
""")

for sid, map_name, rnd, def_t, win_t, limit, actual in c.fetchall():
    print(f"ID {sid}: {map_name} R{rnd} - Def:{def_t} Win:{win_t} Time:{actual}/{limit}")

conn.close()
