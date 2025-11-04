import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

cursor.execute("""
    SELECT 
        player_name,
        team_damage_given,
        team_damage_received,
        headshot_kills,
        most_useful_kills,
        double_kills
    FROM player_comprehensive_stats
    WHERE round_id = 3404
    AND player_name LIKE '%SuperBoyy%'
""")

row = cursor.fetchone()

if row:
    print("SuperBoyy stats from session 3404:")
    print(f"  team_damage_given: {row[1]} (expected 85)")
    print(f"  team_damage_received: {row[2]} (expected 18)")
    print(f"  headshot_kills: {row[3]} (expected 4)")
    print(f"  most_useful_kills: {row[4]} (expected 2)")
    print(f"  double_kills: {row[5]} (expected 2)")
    
    if row[1] == 85 and row[2] == 18 and row[3] == 4 and row[4] == 2 and row[5] == 2:
        print("\n🎉 ALL VALUES CORRECT!")
    else:
        print("\n⚠️  Values don't match expected!")
else:
    print("❌ SuperBoyy not found!")

conn.close()
