"""Compare current stored time_dead_minutes vs expected value after the fix.

Prints:
 - total player rows considered
 - total stored time_dead_minutes sum
 - total expected time_dead_minutes sum (computed from ratio)
 - difference and percent change
 - sample top rows where discrepancy is largest
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'bot', 'etlegacy_production.db')
if not os.path.exists(DB_PATH):
    print(f"DB not found at {DB_PATH}")
    raise SystemExit(1)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Consider only rows where we have time_played_minutes and time_dead_ratio
cur.execute(
    """
    SELECT COUNT(*) as cnt,
           SUM(time_dead_minutes) as sum_stored,
           SUM(time_played_minutes * (time_dead_ratio / 100.0)) as sum_expected
    FROM player_comprehensive_stats
    WHERE time_played_minutes > 0
      AND time_dead_ratio IS NOT NULL
    """
)
summary = cur.fetchone()

cnt = summary['cnt'] or 0
sum_stored = summary['sum_stored'] or 0.0
sum_expected = summary['sum_expected'] or 0.0

delta = sum_expected - sum_stored
pct_change = ((sum_expected - sum_stored) / sum_stored * 100.0) if sum_stored != 0 else float('inf')

print(f"Rows considered: {cnt}")
print(f"Total stored time_dead_minutes: {sum_stored:.3f}")
print(f"Total expected time_dead_minutes: {sum_expected:.3f}")
print(f"Delta (expected - stored): {delta:.3f} ({pct_change:+.2f}%)")
print()

# Show top 30 rows by factor stored/expected (largest discrepancy)
cur.execute(
    """
    SELECT id, session_id, player_name, time_played_minutes, time_dead_ratio, time_dead_minutes,
           time_played_minutes * (time_dead_ratio / 100.0) as expected_td,
           CASE WHEN (time_played_minutes * (time_dead_ratio / 100.0)) = 0 THEN NULL ELSE time_dead_minutes / (time_played_minutes * (time_dead_ratio / 100.0)) END as factor
    FROM player_comprehensive_stats
    WHERE time_played_minutes > 0
      AND time_dead_ratio IS NOT NULL
    ORDER BY factor DESC NULLS LAST
    LIMIT 30
    """
)
rows = cur.fetchall()

if rows:
    print("Top sample rows (id, session_id, player, tmin, ratio, stored_td, expected_td, factor):")
    for r in rows:
        print(f"{r['id']:6d} {r['session_id']:6d} {r['player_name'][:20]:20s} {float(r['time_played_minutes']):6.2f} {float(r['time_dead_ratio']):7.3f} {float(r['time_dead_minutes']):10.3f} {float(r['expected_td']):10.3f} {r['factor'] if r['factor'] is not None else 'N/A'}")
else:
    print("No rows found to display.")

conn.close()
