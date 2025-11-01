"""Check last session time-dead values vs computed/normalized values.

This script opens bot/etlegacy_production.db, finds the most recently created session,
and prints for each player: stored time_played_minutes, stored time_dead_ratio,
stored time_dead_minutes, computed minutes (time_played_minutes * ratio/100),
and minutes if the ratio was a fraction (<=1) normalized to percent.
"""

import sqlite3
import os
from pathlib import Path

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'bot', 'etlegacy_production.db')

if not os.path.exists(DB_PATH):
    print(f"DB not found at {DB_PATH}")
    raise SystemExit(1)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Find last session by created_at or id
cur.execute("SELECT id, session_date, map_name, round_number, created_at FROM sessions ORDER BY created_at DESC, id DESC LIMIT 1")
session = cur.fetchone()
if not session:
    print("No sessions found in DB.")
    raise SystemExit(1)

session_id = session['id']
print(f"Last session: id={session_id} date={session['session_date']} map={session['map_name']} round={session['round_number']} created_at={session['created_at']}")
print()

# Select players for this session
cur.execute(
    """
    SELECT player_guid, player_name, time_played_minutes, time_dead_ratio, time_dead_minutes
    FROM player_comprehensive_stats
    WHERE session_id = ?
    ORDER BY player_name COLLATE NOCASE
    """,
    (session_id,),
)
rows = cur.fetchall()
if not rows:
    print("No player rows found for this session.")
    raise SystemExit(0)

print("{:<24} {:>8} {:>10} {:>12} {:>12} {:>12} {:>12}".format(
    "player_name", "t_min", "raw_ratio", "stored_td", "calc_td", "norm_pct", "norm_td"
))
print("-" * 100)

for r in rows:
    name = (r['player_name'] or "").strip()
    tmin = float(r['time_played_minutes'] or 0.0)
    raw_ratio = float(r['time_dead_ratio'] or 0.0)
    stored_td = float(r['time_dead_minutes'] or 0.0)

    # computed directly from stored ratio assuming ratio is percent (e.g., 25 => 25%)
    calc_td = tmin * (raw_ratio / 100.0)

    # normalized percent if parser provided fraction
    if raw_ratio <= 1.0:
        norm_pct = raw_ratio * 100.0
    else:
        norm_pct = raw_ratio
    norm_td = tmin * (norm_pct / 100.0)

    print("{:<24} {:8.2f} {:10.4f} {:12.2f} {:12.2f} {:12.2f} {:12.2f}".format(
        name[:24], tmin, raw_ratio, stored_td, calc_td, norm_pct, norm_td
    ))

conn.close()
