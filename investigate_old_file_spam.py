"""
Investigate: Why did old files suddenly get imported?

Theory: Something cleared/reset the processed_files table
"""
import sqlite3
from datetime import datetime

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

print("="*80)
print("INVESTIGATION: Why did bot import old files?")
print("="*80 + "\n")

# Check when files were first tracked
print("When were files added to processed_files table?")
cursor.execute('''
    SELECT 
        DATE(processed_at) as date,
        COUNT(*) as count
    FROM processed_files 
    GROUP BY DATE(processed_at)
    ORDER BY date DESC
    LIMIT 10
''')

print("\nFiles processed by date:")
for date, count in cursor.fetchall():
    print(f"  {date}: {count} files")

# Check if there was a gap
print("\n" + "="*80)
print("Files processed BEFORE today:")
cursor.execute('''
    SELECT COUNT(*) 
    FROM processed_files 
    WHERE DATE(processed_at) < DATE('now')
''')
before_today = cursor.fetchone()[0]
print(f"  Files marked processed before today: {before_today}")

cursor.execute('''
    SELECT COUNT(*) 
    FROM processed_files 
    WHERE DATE(processed_at) = DATE('now')
''')
today = cursor.fetchone()[0]
print(f"  Files marked processed today: {today}")

# Check rounds table for actual imports
print("\n" + "="*80)
print("Sessions (rounds) imported to database:")
cursor.execute('SELECT COUNT(*) FROM rounds')
total_rounds = cursor.fetchone()[0]
print(f"  Total sessions in database: {total_rounds}")

cursor.execute('''
    SELECT round_date, COUNT(*) 
    FROM rounds 
    GROUP BY round_date 
    ORDER BY round_date DESC 
    LIMIT 10
''')
print("\nSessions by date (last 10 days):")
for date, count in cursor.fetchall():
    print(f"  {date}: {count} rounds")

# The smoking gun
print("\n" + "="*80)
print("🔍 THE SMOKING GUN:")
print("="*80)

cursor.execute('''
    SELECT round_date, round_time, map_name, id
    FROM rounds 
    WHERE round_date IN ('2025-08-21', '2025-02-16')
    ORDER BY round_date, round_time
''')

old_sessions = cursor.fetchall()
if old_sessions:
    print(f"\n❌ Found {len(old_sessions)} sessions from old dates in database!")
    print("These shouldn't have been imported if bot was working correctly:\n")
    for date, time, map_name, round_id in old_sessions:
        print(f"  Round #{round_id}: {date} {time} - {map_name}")
    print("\n💡 CONCLUSION: Bot imported these OLD files because:")
    print("   1. They exist on SSH server")
    print("   2. They were NOT in processed_files table before bot start")
    print("   3. Bot's should_process_file() had no date filter")
    print("   4. So bot thought they were 'new' and imported them!")
else:
    print("\n✅ No old rounds found in database")
    print("   Files were detected but skipped before import")

conn.close()
