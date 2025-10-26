#!/usr/bin/env python3
"""Check the GOOD backup from October 5th."""

import sqlite3

print("\n" + "="*70)
print("🔍 CHECKING GOOD BACKUP FROM OCTOBER 5TH")
print("="*70)

conn = sqlite3.connect('etlegacy_production.db.backup_GOOD_20251005')
cursor = conn.cursor()

# Check session_date format
cursor.execute("""
    SELECT DISTINCT session_date
    FROM player_comprehensive_stats
    WHERE session_date LIKE '2025-10-05%'
    ORDER BY session_date
    LIMIT 20
""")
results = cursor.fetchall()

print(f"\n📅 Session dates in backup ({len(results)} unique):")
for r in results:
    print(f"  {r[0]}")

# Check total records
cursor.execute("""
    SELECT COUNT(*)
    FROM player_comprehensive_stats
    WHERE session_date LIKE '2025-10-05%'
""")
total = cursor.fetchone()[0]

print(f"\n✅ Total Oct 5th player records: {total}")

# Check if it has proper timestamps
if results:
    sample_date = results[0][0]
    if len(sample_date) > 10:  # More than just YYYY-MM-DD
        print(f"\n✅ GOOD! Backup has full timestamps: {sample_date}")
    else:
        print(f"\n❌ BAD! Backup has truncated dates: {sample_date}")

conn.close()
