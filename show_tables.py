import sqlite3

db = sqlite3.connect('bot/etlegacy_production.db')
c = db.cursor()

# Get all tables
tables = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("Tables in database:")
for t in tables:
    print(f"  - {t[0]}")

# Check round 234
print("\n\nChecking round 234 (supply)...")
try:
    players = c.execute("""
        SELECT player_name, kills, deaths, headshot_kills, damage_given
        FROM player_comprehensive_stats 
        WHERE round_id = 234
        ORDER BY kills DESC
    """).fetchall()
    
    print(f"\n{'Player':<20} {'K':<4} {'D':<4} {'HS':<4} {'DMG':<6}")
    print("-" * 45)
    for p in players:
        print(f"{p[0]:<20} {p[1]:<4} {p[2]:<4} {p[3]:<4} {p[4]:<6}")
except Exception as e:
    print(f"Error: {e}")
