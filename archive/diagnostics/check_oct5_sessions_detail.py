import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
cur = conn.cursor()

print("=== October 5th Sessions with Player Count ===\n")

sessions = cur.execute('''
    SELECT s.session_date, s.map_name, s.round_number, 
           COUNT(DISTINCT p.player_guid) as player_count,
           SUM(p.time_played_seconds) as total_time
    FROM sessions s
    LEFT JOIN player_comprehensive_stats p ON s.id = p.session_id
    WHERE s.session_date LIKE "2025-10-05%"
    GROUP BY s.id
    ORDER BY s.session_date
''').fetchall()

print(f"{'Session':<30} {'Map':<20} {'Round':<6} {'Players':<8} {'Total Time'}")
print("=" * 85)

for session_date, map_name, round_num, player_count, total_time in sessions:
    time_display = f"{total_time}s ({total_time/60:.1f} min)" if total_time else "0s"
    print(f"{session_date:<30} {map_name:<20} {round_num:<6} {player_count:<8} {time_display}")

# Now sum by date
print("\n\n=== Total for October 5th ===\n")
total = cur.execute('''
    SELECT COUNT(DISTINCT p.player_guid) as unique_players,
           SUM(p.time_played_seconds) as total_seconds
    FROM player_comprehensive_stats p
    JOIN sessions s ON p.session_id = s.id
    WHERE s.session_date LIKE "2025-10-05%"
''').fetchone()

if total and total[1]:
    unique_players, total_seconds = total
    print(f"Unique players: {unique_players}")
    print(f"Total time (summed): {total_seconds}s ({total_seconds/60:.1f} min)")
else:
    print("No data")

conn.close()
