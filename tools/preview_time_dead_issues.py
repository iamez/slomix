"""Preview time_dead_minutes inconsistencies in the DB.

Find rows where stored time_dead_minutes is much larger than expected
(time_played_minutes * time_dead_ratio / 100). Print counts and sample rows.
"""
import sqlite3
import os
from math import isclose

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'bot', 'etlegacy_production.db')
if not os.path.exists(DB_PATH):
    print(f"DB not found at {DB_PATH}")
    raise SystemExit(1)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Query all rows with positive playtime and ratio
cur.execute(
    """
    SELECT id, session_id, player_guid, player_name,
           time_played_minutes, time_dead_ratio, time_dead_minutes
    FROM player_comprehensive_stats
    WHERE time_played_minutes > 0 AND time_dead_ratio IS NOT NULL
    """
)
rows = cur.fetchall()

bad_rows = []
for r in rows:
    tmin = float(r['time_played_minutes'] or 0.0)
    ratio = float(r['time_dead_ratio'] or 0.0)
    stored = float(r['time_dead_minutes'] or 0.0)
    expected = tmin * (ratio / 100.0)
    # if expected is zero, skip
    if expected == 0:
        continue
    factor = stored / expected if expected else float('inf')
    # flag if stored is >5x expected (conservative)
    if factor > 5.0:
        bad_rows.append((r['id'], r['session_id'], r['player_name'], tmin, ratio, stored, expected, factor))

print(f"Total player rows checked: {len(rows)}")
print(f"Rows with stored >> expected (factor>5): {len(bad_rows)}")

if bad_rows:
    print("\nSample problematic rows (id, session_id, player_name, tmin, ratio, stored_td, expected_td, factor):")
    for sample in bad_rows[:20]:
        print(sample)
else:
    print("No obvious large-scale mis-scaling found (factor>5).")

# Also show distribution by session (how many bad rows per session)
from collections import Counter
sess_counts = Counter(s[1] for s in bad_rows)
most = sess_counts.most_common(10)
if most:
    print("\nTop sessions with problems (session_id -> count):")
    for sid, cnt in most:
        print(f"  {sid} -> {cnt}")

conn.close()
