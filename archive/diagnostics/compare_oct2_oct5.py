import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
cur = conn.cursor()

# Check October 2nd
print("=== OCTOBER 2nd Data ===\n")
oct2_sessions = cur.execute('''
    SELECT session_date, map_name, round_number
    FROM sessions
    WHERE session_date LIKE "2025-10-02%"
    ORDER BY session_date DESC
    LIMIT 5
''').fetchall()

for session in oct2_sessions:
    print(f"📅 {session[0]} - {session[1]} (Round {session[2]})")
    
    stats = cur.execute('''
        SELECT player_name, time_played_seconds
        FROM player_comprehensive_stats
        WHERE session_date = ?
        ORDER BY time_played_seconds DESC
        LIMIT 3
    ''', (session[0],)).fetchall()
    
    if stats:
        for player, time_secs in stats:
            mins = time_secs / 60
            print(f"   {player:20s}: {time_secs:5d}s ({mins:6.2f} min)")
    else:
        print("   ❌ NO PLAYER STATS!")

# Check October 5th
print("\n\n=== OCTOBER 5th Data ===\n")
oct5_sessions = cur.execute('''
    SELECT session_date, map_name, round_number
    FROM sessions
    WHERE session_date LIKE "2025-10-05%"
    ORDER BY session_date DESC
    LIMIT 5
''').fetchall()

for session in oct5_sessions:
    print(f"📅 {session[0]} - {session[1]} (Round {session[2]})")
    
    stats = cur.execute('''
        SELECT player_name, time_played_seconds
        FROM player_comprehensive_stats
        WHERE session_date = ?
        ORDER BY time_played_seconds DESC
        LIMIT 3
    ''', (session[0],)).fetchall()
    
    if stats:
        for player, time_secs in stats:
            mins = time_secs / 60
            print(f"   {player:20s}: {time_secs:5d}s ({mins:6.2f} min)")
    else:
        print("   ❌ NO PLAYER STATS!")

conn.close()
