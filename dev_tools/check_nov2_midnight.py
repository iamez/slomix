"""Check Nov 2 midnight round import"""
import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

# List all Nov 2 rounds
print("All Nov 2 rounds:")
cursor.execute("""
    SELECT id, round_date, round_time, map_name
    FROM rounds
    WHERE round_date LIKE '2025-11-02%'
    ORDER BY round_time
""")
for row in cursor.fetchall():
    print(f"  ID {row[0]}: {row[1]} {row[2]} - {row[3]}")
print()

# Find the Nov 2 midnight round (round_id = 192, time = 000624)
cursor.execute("""
    SELECT r.id, r.round_date, r.round_time, r.map_name, COUNT(DISTINCT p.player_name) as player_count
    FROM rounds r
    LEFT JOIN player_comprehensive_stats p ON r.id = p.round_id
    WHERE r.id = 192
    GROUP BY r.id
""")
result = cursor.fetchone()

if result:
    round_id, date, time, map_name, player_count = result
    print("🌙 MIDNIGHT-CROSSING ROUND:")
    print(f"   Round ID: {round_id}")
    print(f"   Date: {date}")
    print(f"   Time: {time}")
    print(f"   Map: {map_name}")
    print(f"   Player count: {player_count}")
    print()
    
    # Get all players
    cursor.execute("""
        SELECT player_name, kills, deaths, damage_given, headshot_kills, time_played_seconds
        FROM player_comprehensive_stats
        WHERE round_id = ?
        ORDER BY kills DESC
    """, (round_id,))
    
    players = cursor.fetchall()
    print(f"Players in database ({len(players)}):")
    for p in players:
        print(f"  {p[0]:20} {p[1]:2}K/{p[2]:2}D  {p[3]:4} dmg  {p[4]:2} HS  {p[5]:3}s")
    
    print()
    if len(players) == 10:
        print("✅ SUCCESS! All 10 players imported correctly!")
    else:
        print(f"⚠️  Expected 10 players, got {len(players)}")
else:
    print("❌ Round not found!")

conn.close()
