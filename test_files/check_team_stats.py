"""Quick script to check team stats in database"""
import sqlite3
import os

db_path = 'bot/etlegacy_production.db'
if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=" * 80)
print("TEAM STATS DIAGNOSIS")
print("=" * 80)

# Check 1: What team values exist?
print("\n1. TEAM VALUES IN DATABASE:")
cursor.execute("SELECT DISTINCT team FROM player_comprehensive_stats WHERE team IS NOT NULL ORDER BY team")
teams = cursor.fetchall()
print(f"   Distinct team values: {[t[0] for t in teams]}")

# Check 2: Distribution of team values
print("\n2. TEAM DISTRIBUTION:")
cursor.execute("SELECT team, COUNT(*) as count FROM player_comprehensive_stats GROUP BY team ORDER BY team")
for row in cursor.fetchall():
    print(f"   Team {row[0]}: {row[1]:,} records")

# Check 3: Sample recent session
print("\n3. SAMPLE RECENT SESSION:")
cursor.execute("SELECT DISTINCT session_date FROM player_comprehensive_stats ORDER BY id DESC LIMIT 1")
latest_session = cursor.fetchone()
if latest_session:
    session_date = latest_session[0]
    print(f"   Latest session: {session_date}")
    
    cursor.execute("""
        SELECT DISTINCT session_id FROM player_comprehensive_stats
        WHERE session_date = ? 
        ORDER BY session_id
    """, (session_date,))
    session_ids = [r[0] for r in cursor.fetchall()]
    
    print(f"   Session IDs: {session_ids}")
    
    # Check team stats for this session
    placeholders = ','.join('?' * len(session_ids))
    cursor.execute(f"""
        SELECT team, 
               COUNT(DISTINCT player_guid) as players,
               SUM(kills) as total_kills,
               SUM(deaths) as total_deaths,
               SUM(damage_given) as total_damage
        FROM player_comprehensive_stats
        WHERE session_id IN ({placeholders})
        GROUP BY team
    """, session_ids)
    
    print("\n   Team aggregation for this session:")
    for row in cursor.fetchall():
        team, players, kills, deaths, damage = row
        print(f"   Team {team}: {players} unique players, {kills} kills, {deaths} deaths, {damage:,} damage")

# Check 4: Sample player records
print("\n4. SAMPLE PLAYER RECORDS (showing team field):")
cursor.execute("""
    SELECT player_name, team, kills, deaths 
    FROM player_comprehensive_stats 
    WHERE session_id IN (SELECT id FROM sessions ORDER BY id DESC LIMIT 1)
    LIMIT 10
""")
for row in cursor.fetchall():
    print(f"   {row[0]:20} | Team: {row[1]} | K/D: {row[2]}/{row[3]}")

conn.close()
print("\n" + "=" * 80)
