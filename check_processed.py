import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
c = conn.cursor()

# Check if October 2nd files are marked as processed
oct2_files = [
    '2025-10-02-211808-etl_adlernest-round-1.txt',
    '2025-10-02-212249-etl_adlernest-round-2.txt',
    '2025-10-02-232818-erdenberg_t2-round-2.txt',
]

print("🔍 Checking processed_files table...")
print()

for filename in oct2_files:
    result = c.execute(
        'SELECT filename, processed_at, success FROM processed_files WHERE filename = ?',
        (filename,),
    ).fetchone()

    if result:
        status = "✅ SUCCESS" if result[2] else "❌ FAILED"
        print(f"{status}: {result[0]}")
        print(f"         Processed at: {result[1]}")
    else:
        print(f"❓ NOT FOUND: {filename}")
    print()

# Check total processed files
total = c.execute('SELECT COUNT(*) FROM processed_files').fetchone()[0]
successful = c.execute('SELECT COUNT(*) FROM processed_files WHERE success = 1').fetchone()[0]
failed = c.execute('SELECT COUNT(*) FROM processed_files WHERE success = 0').fetchone()[0]

print("=" * 60)
print(f"Total processed files: {total}")
print(f"  Successful: {successful}")
print(f"  Failed: {failed}")

conn.close()
