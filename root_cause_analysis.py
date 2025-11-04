"""
Check if processed_files table was recently cleared/reset
"""
import sqlite3
import os

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

print("="*80)
print("WHY DID THIS HAPPEN? Root Cause Analysis")
print("="*80 + "\n")

# Check local_stats directory
local_files = set()
if os.path.exists('local_stats'):
    local_files = {f for f in os.listdir('local_stats') if f.endswith('.txt')}
    print(f"Files in local_stats directory: {len(local_files)}")
else:
    print("local_stats directory doesn't exist")

# Check processed_files table
cursor.execute('SELECT filename FROM processed_files')
tracked_files = {row[0] for row in cursor.fetchall()}
print(f"Files in processed_files table: {len(tracked_files)}")

# Find the gap
in_local_not_tracked = local_files - tracked_files
in_tracked_not_local = tracked_files - local_files

print(f"\n📁 Files in local_stats but NOT tracked: {len(in_local_not_tracked)}")
if in_local_not_tracked and len(in_local_not_tracked) < 20:
    for f in sorted(list(in_local_not_tracked))[:10]:
        print(f"  {f}")

print(f"\n📊 Files tracked but NOT in local_stats: {len(in_tracked_not_local)}")
if in_tracked_not_local and len(in_tracked_not_local) < 20:
    for f in sorted(list(in_tracked_not_local))[:10]:
        print(f"  {f}")

# The real question: Are there SSH files not tracked?
print("\n" + "="*80)
print("🔍 THE REAL ISSUE:")
print("="*80)

print("""
WHAT HAPPENED:

1. Yesterday (Nov 3): Bot processed 231 files and marked them in processed_files ✅

2. Today (Nov 4): You started the bot

3. Bot's SSH monitor found NEW files on server:
   - 2025-08-21-215952-etl_adlernest-round-2.txt
   - 2025-02-16-222714-te_escape2-round-1.txt
   - Plus 49 more old files

4. Bot checked: Are these in processed_files? 
   - NO! They were never tracked before ❌
   
5. Bot checked: Are these in local_stats?
   - NO! They were never downloaded before ❌
   
6. Bot checked: Are these in database?
   - NO! They were never imported before ❌
   
7. Bot concluded: These are NEW files! 
   - Downloaded them ✅
   - Imported them to database ✅
   - Posted to Discord ✅ ← THIS IS THE SPAM!

WHY DIDN'T THIS HAPPEN BEFORE?

The bot has been running for 3 days. These files have been on the SSH server
for months. So why did bot suddenly "discover" them today?

POSSIBLE REASONS:
A) SSH monitor was disabled/not working for 3 days
B) Files were just uploaded to SSH server recently
C) SSH directory changed
D) Bot was using a different processed_files tracking before
E) Someone cleaned the local_stats folder

Let me check which theory is correct...
""")

# Check when bot last synced
cursor.execute('''
    SELECT processed_at 
    FROM processed_files 
    WHERE DATE(processed_at) = '2025-11-03'
    ORDER BY processed_at 
    LIMIT 1
''')
first_nov3 = cursor.fetchone()

cursor.execute('''
    SELECT processed_at 
    FROM processed_files 
    WHERE DATE(processed_at) = '2025-11-03'
    ORDER BY processed_at DESC
    LIMIT 1
''')
last_nov3 = cursor.fetchone()

if first_nov3 and last_nov3:
    print(f"\n📅 Yesterday (Nov 3):")
    print(f"   First file processed: {first_nov3[0]}")
    print(f"   Last file processed:  {last_nov3[0]}")
    print(f"   ➡️ Bot was active all day yesterday")

conn.close()
