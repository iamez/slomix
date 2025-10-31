"""Check October 2nd file count vs database"""

import os
import sqlite3

files = [f for f in os.listdir('local_stats') if f.startswith('2025-10-02')]
print(f"October 2nd FILES: {len(files)}")

conn = sqlite3.connect('bot/bot/etlegacy_production.db')
c = conn.cursor()

total = c.execute(
    "SELECT COUNT(*) FROM player_comprehensive_stats WHERE session_date = '2025-10-02'"
).fetchone()[0]
print(f"Database RECORDS: {total}")

# Expected: 20 files × ~6 players = ~120 records
expected = len(files) * 6
print(f"Expected records: ~{expected}")
print(f"Missing: ~{expected - total} records")
print()
print(f"Conclusion: We have {len(files)} files but only {total} database records.")
print(f"This means NOT ALL October 2nd files were imported!")

conn.close()
