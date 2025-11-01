"""Backup DB and apply conservative time_dead_minutes fix.

Behavior:
 - Create a timestamped copy of bot/etlegacy_production.db (same folder)
 - On the backup copy, compute pre-fix aggregates (counts, sums)
 - Show top sample problematic rows (stored >> expected)
 - Apply conservative UPDATE:
     UPDATE ... SET time_dead_minutes = time_played_minutes * (time_dead_ratio / 100.0)
     WHERE time_played_minutes > 0
       AND time_dead_ratio IS NOT NULL
       AND time_dead_minutes > time_played_minutes * 10
 - Commit, then compute post-fix aggregates and show counts and a few sample rows
 - Print summary and exit

Run this from project root: .venv\Scripts\python.exe .\tools\apply_time_dead_fix.py
"""

import os
import shutil
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'bot', 'etlegacy_production.db')
if not os.path.exists(DB_PATH):
    print(f"DB not found at {DB_PATH}")
    raise SystemExit(1)

# Create backup filename
ts = datetime.now().strftime('%Y%m%d_%H%M%S')
backup_path = DB_PATH + f".bak_{ts}"
shutil.copy2(DB_PATH, backup_path)
print(f"Created backup: {backup_path}")

# Connect to the backup DB
conn = sqlite3.connect(backup_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

def summary_stats(c):
    s = c.execute(
        """
        SELECT COUNT(*) as cnt,
               SUM(time_dead_minutes) as sum_stored,
               SUM(time_played_minutes * (time_dead_ratio / 100.0)) as sum_expected
        FROM player_comprehensive_stats
        WHERE time_played_minutes > 0 AND time_dead_ratio IS NOT NULL
        """
    ).fetchone()
    return (s['cnt'] or 0, float(s['sum_stored'] or 0.0), float(s['sum_expected'] or 0.0))

print('\nPre-fix aggregates:')
cnt, sum_stored, sum_expected = summary_stats(cur)
print(f" Rows considered: {cnt}")
print(f" Total stored time_dead_minutes: {sum_stored:.3f}")
print(f" Total expected time_dead_minutes: {sum_expected:.3f}")
print(f" Delta (expected - stored): {sum_expected - sum_stored:.3f}\n")

print("Top problematic sample rows (pre-fix):")
for r in cur.execute(
    """
    SELECT id, session_id, player_name, time_played_minutes, time_dead_ratio, time_dead_minutes,
           time_played_minutes * (time_dead_ratio / 100.0) as expected_td,
           CASE WHEN (time_played_minutes * (time_dead_ratio / 100.0)) = 0 THEN NULL ELSE time_dead_minutes / (time_played_minutes * (time_dead_ratio / 100.0)) END as factor
    FROM player_comprehensive_stats
    WHERE time_played_minutes > 0 AND time_dead_ratio IS NOT NULL
    ORDER BY factor DESC NULLS LAST
    LIMIT 12
    """
):
    print(f" {r['id']:6d} {r['session_id']:6d} {r['player_name'][:20]:20s} tmin={float(r['time_played_minutes']):5.2f} ratio={float(r['time_dead_ratio']):6.3f} stored={float(r['time_dead_minutes']):8.3f} expected={float(r['expected_td']):8.3f} factor={r['factor']}")

# Apply conservative update
before_changes = conn.total_changes
print('\nApplying conservative UPDATE on the backup DB...')
update_sql = (
    """
    UPDATE player_comprehensive_stats
    SET time_dead_minutes = time_played_minutes * (time_dead_ratio / 100.0)
    WHERE time_played_minutes > 0
      AND time_dead_ratio IS NOT NULL
      AND time_dead_minutes > time_played_minutes * 10
    """
)
cur.execute(update_sql)
conn.commit()
after_changes = conn.total_changes
rows_changed = after_changes - before_changes
print(f"Rows changed by UPDATE: {rows_changed}\n")

# Post-fix aggregates
print('Post-fix aggregates:')
cnt2, sum_stored2, sum_expected2 = summary_stats(cur)
print(f" Rows considered: {cnt2}")
print(f" Total stored time_dead_minutes: {sum_stored2:.3f}")
print(f" Total expected time_dead_minutes: {sum_expected2:.3f}")
print(f" Delta (expected - stored): {sum_expected2 - sum_stored2:.3f}\n")

# Mismatch count after fix (tolerance 0.5 minutes)
mismatches = cur.execute(
    """
    SELECT COUNT(*) as c FROM player_comprehensive_stats
    WHERE time_played_minutes > 0
      AND time_dead_ratio IS NOT NULL
      AND ABS(time_dead_minutes - (time_played_minutes * (time_dead_ratio / 100.0))) > 0.5
    """
).fetchone()['c']
print(f"Rows mismatching expected after fix (tolerance 0.5 min): {mismatches}\n")

print('Top sample rows (post-fix, largest remaining discrepancy):')
for r in cur.execute(
    """
    SELECT id, session_id, player_name, time_played_minutes, time_dead_ratio, time_dead_minutes,
           time_played_minutes * (time_dead_ratio / 100.0) as expected_td,
           CASE WHEN (time_played_minutes * (time_dead_ratio / 100.0)) = 0 THEN NULL ELSE time_dead_minutes / (time_played_minutes * (time_dead_ratio / 100.0)) END as factor
    FROM player_comprehensive_stats
    WHERE time_played_minutes > 0 AND time_dead_ratio IS NOT NULL
    ORDER BY factor DESC NULLS LAST
    LIMIT 12
    """
):
    print(f" {r['id']:6d} {r['session_id']:6d} {r['player_name'][:20]:20s} tmin={float(r['time_played_minutes']):5.2f} ratio={float(r['time_dead_ratio']):6.3f} stored={float(r['time_dead_minutes']):8.3f} expected={float(r['expected_td']):8.3f} factor={r['factor']}")

conn.close()
print('\nDone. Backup left in place; fixed DB is the backup file shown above.')
