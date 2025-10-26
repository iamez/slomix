import sqlite3

db_path = "etlegacy_production.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get all sessions for vid on October 2nd
query = """
SELECT
    s.id,
    s.session_date,
    s.map_name,
    s.round_number,
    p.kills,
    p.deaths,
    p.gibs,
    p.xp,
    p.kill_assists,
    p.times_revived
FROM player_comprehensive_stats p
JOIN sessions s ON p.session_id = s.id
WHERE p.player_name = 'vid'
AND s.session_date = '2025-10-02'
ORDER BY s.id
"""

cursor.execute(query)
sessions = cursor.fetchall()

print("=" * 80)
print(f"VID'S OCTOBER 2ND SESSIONS (Total: {len(sessions)})")
print("=" * 80)
print()

for session in sessions:
    session_id, date, map_name, round_num, kills, deaths, gibs, xp, assists, revived = session
    print(f"Session {session_id}: {map_name} Round {round_num}")
    print(
        f"  Kills: {kills}, Deaths: {deaths}, Gibs: {gibs}, XP: {xp}, Assists: {assists}, Revived: {revived}"
    )
    print()

# Get unique maps and rounds
cursor.execute(
    """
SELECT DISTINCT s.map_name, s.round_number
FROM player_comprehensive_stats p
JOIN sessions s ON p.session_id = s.id
WHERE p.player_name = 'vid'
AND s.session_date = '2025-10-02'
ORDER BY s.map_name, s.round_number
"""
)

map_rounds = cursor.fetchall()

print("=" * 80)
print("UNIQUE MAP/ROUND COMBINATIONS:")
print("=" * 80)
for map_name, round_num in map_rounds:
    print(f"  {map_name} - Round {round_num}")

conn.close()
