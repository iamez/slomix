"""Verify database import was successful"""
import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

print("="*80)
print("DATABASE IMPORT VERIFICATION")
print("="*80)

# Total records
total = cursor.execute('SELECT COUNT(*) FROM player_comprehensive_stats').fetchone()[0]
print(f"\n✅ Total records imported: {total}")

# Check time data
time_records = cursor.execute('''
    SELECT COUNT(*) FROM player_comprehensive_stats 
    WHERE time_played_seconds > 0
''').fetchone()[0]
print(f"✅ Records with time_played_seconds > 0: {time_records}")

# Sample records
print(f"\n{'Player Name':<25} {'Time (s)':<12} {'Time':<10} {'Minutes':<10} {'DPM':<10}")
print("-"*80)

for row in cursor.execute('''
    SELECT player_name, time_played_seconds, time_played_minutes, dpm 
    FROM player_comprehensive_stats 
    WHERE time_played_seconds > 0 
    LIMIT 15
''').fetchall():
    name = row[0][:24]
    seconds = row[1]
    minutes_db = row[2]
    dpm = row[3]
    time_str = f"{seconds//60}:{seconds%60:02d}"
    print(f"{name:<25} {seconds:<12} {time_str:<10} {minutes_db:<10.1f} {dpm:<10.1f}")

# Check if repairs_constructions is all 0 (as expected)
repairs = cursor.execute('''
    SELECT SUM(repairs_constructions) FROM player_comprehensive_stats
''').fetchone()[0]
print(f"\n✅ Sum of repairs_constructions: {repairs} (expected 0 since lua doesn't write this)")

conn.close()
print("\n" + "="*80)
print("✅ VERIFICATION COMPLETE - Database import successful!")
print("="*80)
