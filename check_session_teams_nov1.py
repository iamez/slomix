import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

# Check session_teams for Nov 1
cursor.execute("SELECT COUNT(*) FROM session_teams WHERE session_date LIKE '2025-11-01%'")
count = cursor.fetchone()[0]
print(f"session_teams records for Nov 1: {count}")

if count > 0:
    cursor.execute("""
        SELECT session_date, team_name, player_names 
        FROM session_teams 
        WHERE session_date LIKE '2025-11-01%'
        ORDER BY session_date
        LIMIT 10
    """)
    
    print("\n📋 Sample session_teams records:")
    for row in cursor.fetchall():
        sdate, team_name, player_names = row
        print(f"  {sdate}: {team_name}")
        print(f"    Players: {player_names[:80]}...")
else:
    print("\n❌ No session_teams data for Nov 1!")
    print("\n💡 This explains why team detection fails.")
    print("   Teams need to be set with !set_teams command before playing.")

conn.close()
