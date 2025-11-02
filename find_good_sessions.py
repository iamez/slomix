"""
Find sessions with PROPER team structure for testing
"""
import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

print("="*80)
print("SEARCHING FOR PROPER ORGANIZED MATCH DATA")
print("="*80)

# Get all sessions with their player counts per team
cursor.execute("""
    WITH DeduplicatedStats AS (
        SELECT *,
               ROW_NUMBER() OVER (
                   PARTITION BY session_date, round_number, player_guid, team
                   ORDER BY time_played_minutes DESC, id DESC
               ) as rn
        FROM player_comprehensive_stats
    ),
    SessionTeamCounts AS (
        SELECT 
            session_date,
            round_number,
            team,
            COUNT(DISTINCT player_guid) as player_count
        FROM DeduplicatedStats
        WHERE rn = 1
        GROUP BY session_date, round_number, team
    )
    SELECT 
        session_date,
        COUNT(DISTINCT round_number) as num_rounds,
        MIN(CASE WHEN team = 1 THEN player_count END) as axis_min,
        MAX(CASE WHEN team = 1 THEN player_count END) as axis_max,
        MIN(CASE WHEN team = 2 THEN player_count END) as allies_min,
        MAX(CASE WHEN team = 2 THEN player_count END) as allies_max
    FROM SessionTeamCounts
    GROUP BY session_date
    HAVING num_rounds >= 2
    ORDER BY session_date DESC
""")

sessions = cursor.fetchall()

print("\nSessions with 2+ rounds:\n")
print(f"{'Date':<15} {'Rounds':<10} {'Axis':<15} {'Allies':<15} {'Status'}")
print("-"*80)

good_sessions = []

for session in sessions:
    date, rounds, axis_min, axis_max, allies_min, allies_max = session
    
    # Check if it's a proper match (distinct teams, not everyone on both)
    # In proper stopwatch: axis and allies should have DIFFERENT players
    
    # Get unique player count
    cursor.execute("""
        WITH DeduplicatedStats AS (
            SELECT *,
                   ROW_NUMBER() OVER (
                       PARTITION BY session_date, round_number, player_guid, team
                       ORDER BY time_played_minutes DESC, id DESC
                   ) as rn
            FROM player_comprehensive_stats
            WHERE session_date = ?
        )
        SELECT COUNT(DISTINCT player_guid)
        FROM DeduplicatedStats
        WHERE rn = 1
    """, (date,))
    
    total_unique = cursor.fetchone()[0]
    
    # In stopwatch, each player appears on both teams
    # So total_unique should be roughly (axis + allies) / 2
    expected_if_stopwatch = (axis_max + allies_max) / 2
    
    is_stopwatch = abs(total_unique - expected_if_stopwatch) < 2
    
    status = "✅ STOPWATCH" if is_stopwatch else "❌ PUB/MIXED"
    
    if is_stopwatch:
        good_sessions.append(date)
    
    print(f"{date:<15} {rounds:<10} {axis_min}-{axis_max:<13} {allies_min}-{allies_max:<13} {status}")

print("\n" + "="*80)
print(f"FOUND {len(good_sessions)} GOOD SESSIONS FOR TESTING:")
print("="*80)
for date in good_sessions:
    print(f"  ✅ {date}")

if good_sessions:
    print(f"\n💡 Try testing with: python fixed_team_detector.py {good_sessions[0]}")

conn.close()
