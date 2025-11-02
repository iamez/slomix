"""Check if players are consistently assigned to the same team"""
import sqlite3
import sys

print("Starting script...", flush=True)
conn = sqlite3.connect('bot/etlegacy_production.db')
print("Connected to database", flush=True)
c = conn.cursor()

print("=" * 80, flush=True)
print("TEAM ASSIGNMENT CONSISTENCY CHECK")
print("=" * 80)

# Get player team assignments for latest session
c.execute("""
    SELECT player_name, player_guid, team, COUNT(*) as rounds
    FROM player_comprehensive_stats
    WHERE session_date = '2025-10-30'
    GROUP BY player_guid, team
    ORDER BY player_name, team
""")

print("\nPlayer team assignments (should be consistent per player):")
print(f"{'Player':<25} {'GUID':<15} {'Team':<6} {'Rounds'}")
print("-" * 70)

results = c.fetchall()
for row in results:
    player, guid, team, rounds = row
    print(f"{player:<25} {guid[:12]:<15} {team:<6} {rounds}")

# Check if any player appears on multiple teams (BAD!)
print("\n" + "=" * 80)
print("PLAYERS APPEARING ON MULTIPLE TEAMS (this is a problem!):")
print("=" * 80)

c.execute("""
    SELECT player_name, player_guid, GROUP_CONCAT(DISTINCT team) as teams, COUNT(DISTINCT team) as team_count
    FROM player_comprehensive_stats
    WHERE session_date = '2025-10-30'
    GROUP BY player_guid
    HAVING team_count > 1
""")

problem_players = c.fetchall()
if problem_players:
    for row in problem_players:
        print(f"WARNING: {row[0]} ({row[1][:12]}): appears on teams {row[2]}")
else:
    print("OK: No players appear on multiple teams - this is GOOD!")

# Show per-map team assignments
print("\n" + "=" * 80)
print("TEAM ASSIGNMENTS PER MAP:")
print("=" * 80)

c.execute("""
    SELECT DISTINCT map_name 
    FROM player_comprehensive_stats
    WHERE session_date = '2025-10-30'
    ORDER BY id
    LIMIT 3
""")

maps = [r[0] for r in c.fetchall()]
for map_name in maps:
    print(f"\n{map_name}:")
    c.execute("""
        SELECT player_name, team, kills, deaths
        FROM player_comprehensive_stats
        WHERE session_date = '2025-10-30' AND map_name = ?
        ORDER BY team, kills DESC
    """, (map_name,))
    
    current_team = None
    for row in c.fetchall():
        player, team, kills, deaths = row
        if team != current_team:
            current_team = team
            print(f"  Team {team}:")
        print(f"    {player:<20} {kills}K/{deaths}D")

conn.close()
