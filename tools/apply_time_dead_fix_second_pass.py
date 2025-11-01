"""Second pass: update rows where stored/expected factor > 5 (catch small-expected cases).
Find the latest backup file (etlegacy_production.db.bak_*) and apply the UPDATE.
"""
import os
import sqlite3
import glob

BOT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'bot')
pattern = os.path.join(BOT_DIR, 'etlegacy_production.db.bak_*')
backs = glob.glob(pattern)
if not backs:
    print(f"No backups found matching {pattern}")
    raise SystemExit(1)

# choose newest
backs.sort(key=os.path.getmtime, reverse=True)
backup = backs[0]
print(f"Using backup: {backup}")

conn = sqlite3.connect(backup)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# compute pre counts
pre_mismatches = cur.execute(
    """
    SELECT COUNT(*) as c FROM player_comprehensive_stats
    WHERE time_played_minutes > 0
      AND time_dead_ratio IS NOT NULL
      AND (time_dead_minutes / NULLIF((time_played_minutes * (time_dead_ratio/100.0)),0)) > 5
    """
).fetchone()['c']
print(f"Rows with factor>5 before second pass: {pre_mismatches}")

before = conn.total_changes
cur.execute(
    """
    UPDATE player_comprehensive_stats
    SET time_dead_minutes = time_played_minutes * (time_dead_ratio / 100.0)
    WHERE time_played_minutes > 0
      AND time_dead_ratio IS NOT NULL
      AND (time_dead_minutes / NULLIF((time_played_minutes * (time_dead_ratio/100.0)),0)) > 5
    """
)
conn.commit()
after = conn.total_changes
changed = after - before
print(f"Rows changed by second pass UPDATE: {changed}")

# post counts
post_mismatches = cur.execute(
    """
    SELECT COUNT(*) as c FROM player_comprehensive_stats
    WHERE time_played_minutes > 0
      AND time_dead_ratio IS NOT NULL
      AND ABS(time_dead_minutes - (time_played_minutes * (time_dead_ratio / 100.0))) > 0.5
    """
).fetchone()['c']
print(f"Rows mismatching after second pass (tolerance 0.5): {post_mismatches}")

# show sample remaining mismatches
print('\nSample remaining mismatches (up to 20):')
for r in cur.execute(
    """
    SELECT id, session_id, player_name, time_played_minutes, time_dead_ratio, time_dead_minutes,
           time_played_minutes * (time_dead_ratio / 100.0) as expected_td,
           CASE WHEN (time_played_minutes * (time_dead_ratio / 100.0)) = 0 THEN NULL ELSE time_dead_minutes / (time_played_minutes * (time_dead_ratio / 100.0)) END as factor
    FROM player_comprehensive_stats
    WHERE time_played_minutes > 0
      AND time_dead_ratio IS NOT NULL
      AND ABS(time_dead_minutes - (time_played_minutes * (time_dead_ratio / 100.0))) > 0.5
    LIMIT 20
    """
):
    print(f" {r['id']:6d} {r['session_id']:6d} {r['player_name'][:20]:20s} tmin={float(r['time_played_minutes']):5.2f} ratio={float(r['time_dead_ratio']):6.3f} stored={float(r['time_dead_minutes']):8.3f} expected={float(r['expected_td']):8.3f} factor={r['factor']}")

conn.close()
