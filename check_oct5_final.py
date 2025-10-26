import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

# Get October 5th player stats
cursor.execute("""
SELECT session_date, player_name, time_played_seconds, time_display, kills, deaths, damage_given
FROM player_comprehensive_stats 
WHERE session_date LIKE '2025-10-05%' 
ORDER BY session_date, time_played_seconds DESC
""")

results = cursor.fetchall()

print("=" * 100)
print("📅 OCTOBER 5TH PLAYER STATS")
print("=" * 100)

if not results:
    print("❌ No October 5th data found!")
else:
    for row in results:
        date, name, seconds, display, kills, deaths, damage = row
        print(f"  {date} | {name[:20]:20s} | {seconds:5d}s ({display:>6s}) | K:{kills:3d} D:{deaths:3d} DMG:{damage:5d}")
    
    unique_players = len(set(r[1] for r in results))
    total_records = len(results)
    total_time = sum(r[2] for r in results)
    avg_time = total_time / total_records if total_records > 0 else 0
    
    print("\n" + "=" * 100)
    print(f"📊 SUMMARY:")
    print(f"   Total unique players: {unique_players}")
    print(f"   Total records: {total_records}")
    print(f"   Total time (all records): {total_time:,} seconds ({total_time/60:.1f} minutes)")
    print(f"   Average time per record: {avg_time:.1f} seconds ({avg_time/60:.1f} minutes)")
    print("=" * 100)

conn.close()
