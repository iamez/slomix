import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
cur = conn.cursor()

print("=== October 2nd - Records with time > 0 ===\n")
oct2_stats = cur.execute('''
    SELECT session_date, player_name, time_played_seconds
    FROM player_comprehensive_stats
    WHERE session_date LIKE "2025-10-02%"
      AND time_played_seconds > 0
    ORDER BY time_played_seconds DESC
    LIMIT 10
''').fetchall()

print(f"Count: {len(oct2_stats)}")
for session, player, time_secs in oct2_stats:
    mins = time_secs / 60
    print(f"  {session}: {player:20s} = {time_secs:5d}s ({mins:6.2f} min)")

print("\n\n=== October 5th - Records with time > 0 ===\n")
oct5_stats = cur.execute('''
    SELECT session_date, player_name, time_played_seconds
    FROM player_comprehensive_stats
    WHERE session_date LIKE "2025-10-05%"
      AND time_played_seconds > 0
    ORDER BY time_played_seconds DESC
    LIMIT 10
''').fetchall()

print(f"Count: {len(oct5_stats)}")
for session, player, time_secs in oct5_stats:
    mins = time_secs / 60
    print(f"  {session}: {player:20s} = {time_secs:5d}s ({mins:6.2f} min)")

conn.close()
