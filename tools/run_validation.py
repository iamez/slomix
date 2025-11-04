import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
c = conn.cursor()

# Get rounds with stat files (Oct 19 - Nov 1, exclude Nov 2-3)
c.execute("""
    SELECT id, round_date, map_name, round_number
    FROM rounds
    WHERE round_date BETWEEN '2025-10-19' AND '2025-11-01 23:59:59'
    ORDER BY round_date ASC
    LIMIT 30
""")

rounds = c.fetchall()
print(f"Found {len(rounds)} rounds\n")

for i, (rid, rdate, map_name, rnum) in enumerate(rounds[:10], 1):
    print(f"{i}. R{rnum} {map_name} on {rdate[:16]}")

conn.close()

# Now run validation
print("\n" + "="*80)
print("Running comprehensive validation...")
print("="*80 + "\n")

import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from tools.comprehensive_all_fields_validation import ComprehensiveStatsValidator

validator = ComprehensiveStatsValidator()
report = validator.run_validation(limit=50, start_date='2025-10-19')
