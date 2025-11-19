import sqlite3

db = sqlite3.connect('bot/ultimate_et_bot.db')
c = db.cursor()

# Find round 234 (the supply round you mentioned)
print("Checking round 234 from database...")
players = c.execute("""
    SELECT player_name, kills, deaths, headshot_kills, damage_given
    FROM players 
    WHERE round_id = 234
    ORDER BY kills DESC
""").fetchall()

print(f"\n{'Player':<20} {'K':<4} {'D':<4} {'HS':<4} {'DMG':<6}")
print("-" * 45)
for p in players:
    print(f"{p[0]:<20} {p[1]:<4} {p[2]:<4} {p[3]:<4} {p[4]:<6}")

print("\n\nNow let's find the corresponding Round 1 and Round 2 files...")
print("Round 234 is Round 2 on supply map")

# Find what file was processed for this round
files = c.execute("""
    SELECT filename FROM processed_files 
    WHERE success = 1 
    ORDER BY processed_at DESC 
    LIMIT 20
""").fetchall()

print("\nRecent processed files:")
for f in files:
    if 'supply' in f[0]:
        print(f"  {f[0]}")
