import sqlite3

db = sqlite3.connect('bot/ultimate_et_bot.db')
c = db.cursor()

# Get table names
tables = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("Tables:", [t[0] for t in tables])

# Find rounds table
print("\nLooking for round 234...")
rounds = c.execute("SELECT id, map_name, round_num FROM rounds WHERE id=234").fetchall()
print("Round info:", rounds)

# Check players table
print("\nPlayers in round 234:")
players = c.execute("""
    SELECT player_name, kills, deaths, headshot_kills, damage_given 
    FROM players 
    WHERE round_id=234 
    ORDER BY kills DESC
""").fetchall()

for p in players:
    print(f"{p[0]:20s} K:{p[1]:2d} D:{p[2]:2d} HS:{p[3]:2d} DMG:{p[4]:5d}")
