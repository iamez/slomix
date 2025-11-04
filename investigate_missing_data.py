import sqlite3
from pathlib import Path

db_path = Path("bot/etlegacy_production.db")

print("=" * 100)
print("INVESTIGATING MISSING DATA")
print("=" * 100)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check processed_files
print("\n📁 PROCESSED FILES:")
print("-" * 100)
cursor.execute("SELECT COUNT(*) FROM processed_files")
total_files = cursor.fetchone()[0]
print(f"   Total files: {total_files}")

cursor.execute("SELECT COUNT(*) FROM processed_files WHERE success = 1")
success_files = cursor.fetchone()[0]
print(f"   Successful: {success_files}")

cursor.execute("SELECT COUNT(*) FROM processed_files WHERE success = 0")
failed_files = cursor.fetchone()[0]
print(f"   Failed: {failed_files}")

# Check date range of processed files
cursor.execute("""
    SELECT 
        MIN(SUBSTR(filename, 1, 10)) as earliest_date,
        MAX(SUBSTR(filename, 1, 10)) as latest_date
    FROM processed_files 
    WHERE filename LIKE '____-__-__-%'
""")
date_range = cursor.fetchone()
print(f"\n   Date range in filenames: {date_range[0]} to {date_range[1]}")

# Count files by date
print("\n📊 FILES PER DATE (from filenames):")
print("-" * 100)
cursor.execute("""
    SELECT 
        SUBSTR(filename, 1, 10) as date,
        COUNT(*) as count
    FROM processed_files 
    WHERE filename LIKE '____-__-__-%'
    GROUP BY date
    ORDER BY date DESC
    LIMIT 20
""")
for row in cursor.fetchall():
    print(f"   {row[0]}: {row[1]} files")

# Now check sessions table
print("\n" + "=" * 100)
print("📋 SESSIONS TABLE:")
print("-" * 100)
cursor.execute("SELECT COUNT(*) FROM rounds")
total_rounds = cursor.fetchone()[0]
print(f"   Total sessions: {total_rounds}")

cursor.execute("SELECT DISTINCT round_date FROM rounds ORDER BY round_date")
session_dates = cursor.fetchall()
print(f"   Unique dates: {len(session_dates)}")
for date in session_dates:
    print(f"      - {date[0]}")

# Check player_comprehensive_stats
print("\n" + "=" * 100)
print("👤 PLAYER STATS:")
print("-" * 100)
cursor.execute("SELECT COUNT(*) FROM player_comprehensive_stats")
player_records = cursor.fetchone()[0]
print(f"   Total player records: {player_records}")

cursor.execute("SELECT DISTINCT round_date FROM player_comprehensive_stats ORDER BY round_date")
player_dates = cursor.fetchall()
print(f"   Unique dates: {len(player_dates)}")
for date in player_dates:
    print(f"      - {date[0]}")

# Check weapon_comprehensive_stats
print("\n" + "=" * 100)
print("🔫 WEAPON STATS:")
print("-" * 100)
cursor.execute("SELECT COUNT(*) FROM weapon_comprehensive_stats")
weapon_records = cursor.fetchone()[0]
print(f"   Total weapon records: {weapon_records}")

cursor.execute("SELECT DISTINCT round_date FROM weapon_comprehensive_stats ORDER BY round_date")
weapon_dates = cursor.fetchall()
print(f"   Unique dates: {len(weapon_dates)}")
for date in weapon_dates:
    print(f"      - {date[0]}")

# THE SMOKING GUN
print("\n" + "=" * 100)
print("🔍 THE SMOKING GUN:")
print("=" * 100)
print(f"""
FILES PROCESSED: {total_files} files (spanning {date_range[0]} to {date_range[1]})
SESSIONS TABLE:  {total_rounds} sessions (only date: 2025-01-01)
PLAYER STATS:    {player_records} records (only date: 2025-01-01)
WEAPON STATS:    {weapon_records} records (only date: 2025-01-01)

🚨 PROBLEM: {total_files} files were processed but only 8 sessions created!

Where did the other ~3,500 files go???
""")

# Check some failed imports
print("\n" + "=" * 100)
print("❌ SAMPLE FAILED IMPORTS:")
print("-" * 100)
cursor.execute("""
    SELECT filename, error_message 
    FROM processed_files 
    WHERE success = 0 
    LIMIT 10
""")
failed = cursor.fetchall()
if failed:
    for filename, error in failed:
        print(f"\n   File: {filename}")
        print(f"   Error: {error[:100]}...")
else:
    print("   No failed imports found!")

# Check if files were marked as processed but nothing inserted
print("\n" + "=" * 100)
print("🤔 WERE FILES MARKED AS 'PROCESSED' BUT NOTHING INSERTED?")
print("-" * 100)
cursor.execute("""
    SELECT 
        SUBSTR(filename, 1, 10) as date,
        COUNT(*) as files_processed
    FROM processed_files 
    WHERE success = 1 AND filename LIKE '____-__-__-%'
    GROUP BY date
    ORDER BY date DESC
    LIMIT 10
""")
print(f"\n{'Date':<15} {'Files Marked Success':<20}")
print("-" * 40)
for row in cursor.fetchall():
    print(f"{row[0]:<15} {row[1]:<20}")

conn.close()
print("\n" + "=" * 100)
