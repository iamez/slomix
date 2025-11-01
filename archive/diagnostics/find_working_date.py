import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
cur = conn.cursor()

# Find a date that HAS player stats
print("Looking for dates WITH player stats...\n")

dates_with_stats = cur.execute('''
    SELECT DISTINCT substr(session_date, 1, 10) as date, COUNT(*) as count
    FROM player_comprehensive_stats
    GROUP BY date
    ORDER BY date DESC
    LIMIT 10
''').fetchall()

print("Recent dates WITH player data:")
for date, count in dates_with_stats:
    print(f"  {date}: {count} player records")

# Check one of those dates
if dates_with_stats:
    recent_date = dates_with_stats[0][0]
    print(f"\n\n=== Sample from {recent_date} ===\n")
    
    sample_stats = cur.execute('''
        SELECT session_date, player_name, time_played_seconds
        FROM player_comprehensive_stats
        WHERE session_date LIKE ?
        ORDER BY session_date DESC
        LIMIT 5
    ''', (f"{recent_date}%",)).fetchall()
    
    for session, player, time_secs in sample_stats:
        mins = time_secs / 60
        print(f"{session}: {player:20s} = {time_secs:5d}s ({mins:6.2f} min)")

conn.close()
