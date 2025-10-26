"""
Quick check of 0-second time records after import
"""
import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
c = conn.cursor()

print("📊 Analyzing 0-second time_played records...\n")

# Total stats
total = c.execute("SELECT COUNT(*) FROM player_comprehensive_stats").fetchone()[0]
zero_time = c.execute("SELECT COUNT(*) FROM player_comprehensive_stats WHERE time_played_seconds = 0").fetchone()[0]

print(f"Total Records: {total:,}")
print(f"Records with 0s: {zero_time:,} ({100*zero_time/total:.1f}%)\n")

# Sample of 0-second records
print("Sample of 0-second records:")
for row in c.execute("""
    SELECT session_id, player_name, time_played_seconds, map_name 
    FROM player_comprehensive_stats 
    WHERE time_played_seconds = 0 
    LIMIT 10
""").fetchall():
    print(f"  Session {row[0]}: {row[1]} - {row[2]}s on {row[3]}")

# Check if duplicates exist
print("\nChecking for duplicate session/player combinations...")
duplicates = c.execute("""
    SELECT session_id, player_guid, COUNT(*) as count 
    FROM player_comprehensive_stats 
    GROUP BY session_id, player_guid 
    HAVING count > 1
    LIMIT 5
""").fetchall()

if duplicates:
    print(f"⚠️ Found {len(duplicates)} duplicate session/player combos (showing first 5):")
    for dup in duplicates:
        print(f"  Session {dup[0]}, GUID {dup[1]}: {dup[2]} records")
else:
    print("✅ No duplicates found")

conn.close()
