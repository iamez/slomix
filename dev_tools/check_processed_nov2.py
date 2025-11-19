import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

# Check Nov 2 files in processed_files table
cursor.execute("""
    SELECT filename, processed_at
    FROM processed_files
    WHERE filename LIKE '2025-11-02%'
    ORDER BY filename
""")

nov2_processed = cursor.fetchall()
print(f"Nov 2 files marked as processed: {len(nov2_processed)}")
for filename, proc_date in nov2_processed:
    print(f"  {filename} - {proc_date}")

print("\n" + "="*70)

# Check what sessions exist from Nov 2
cursor.execute("""
    SELECT COUNT(*), MIN(round_date), MAX(round_date)
    FROM rounds
    WHERE round_date LIKE '2025-11-02%'
""")

count, min_date, max_date = cursor.fetchone()
print(f"Nov 2 sessions in database: {count}")
print(f"  Earliest: {min_date}")
print(f"  Latest: {max_date}")

conn.close()
