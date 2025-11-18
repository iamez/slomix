"""
Check processed_files table to understand what happened
"""
import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

# Check table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='processed_files'")
if not cursor.fetchone():
    print("❌ processed_files table doesn't exist!")
    exit()

print("✅ processed_files table exists\n")

# Get counts
cursor.execute('SELECT COUNT(*) FROM processed_files')
total = cursor.fetchone()[0]
print(f"Total files tracked: {total}")

cursor.execute('SELECT COUNT(*) FROM processed_files WHERE success = 1')
success_count = cursor.fetchone()[0]
print(f"Successfully processed: {success_count}")

cursor.execute('SELECT COUNT(*) FROM processed_files WHERE success = 0')
failed_count = cursor.fetchone()[0]
print(f"Failed: {failed_count}\n")

# Get recent entries
print("Last 10 processed files:")
cursor.execute('''
    SELECT filename, success, processed_at 
    FROM processed_files 
    ORDER BY processed_at DESC 
    LIMIT 10
''')
for filename, success, processed_at in cursor.fetchall():
    status = "✅" if success else "❌"
    print(f"  {status} {filename} ({processed_at})")

# Check for those old files that were spamming
print("\n" + "="*80)
print("Checking for the files that spammed Discord:")
old_files = [
    '2025-08-21-215952-etl_adlernest-round-2.txt',
    '2025-02-16-222714-te_escape2-round-1.txt'
]

for filename in old_files:
    cursor.execute('SELECT * FROM processed_files WHERE filename = ?', (filename,))
    result = cursor.fetchone()
    if result:
        print(f"✅ {filename} IS in processed_files table")
        print(f"   Success: {result[2]}, Processed at: {result[3]}")
    else:
        print(f"❌ {filename} NOT in processed_files table (explains why it tried to import!)")

conn.close()
