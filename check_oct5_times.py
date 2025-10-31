import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
cur = conn.cursor()

# Get all October 5th sessions
print("=== October 5th Sessions ===\n")
sessions = cur.execute('''
    SELECT DISTINCT session_date, map_name, round_number 
    FROM sessions 
    WHERE session_date LIKE "2025-10-05%"
    ORDER BY session_date DESC
''').fetchall()

for session in sessions[:5]:
    print(f"\n📅 Session: {session[0]} - {session[1]} (Round {session[2]})")
    
    # Get player times for this session
    stats = cur.execute('''
        SELECT player_name, time_played_seconds
        FROM player_comprehensive_stats
        WHERE session_date = ?
        ORDER BY time_played_seconds DESC
    ''', (session[0],)).fetchall()
    
    if stats:
        print(f"   Players: {len(stats)}")
        for player, time_secs in stats[:3]:
            print(f"      {player:20s}: {time_secs:5d}s ({time_secs/60:6.2f} min)")
        
        if len(stats) > 3:
            print(f"      ... and {len(stats)-3} more players")

conn.close()
