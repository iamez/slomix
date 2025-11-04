"""Aggregate sessions by day and report time-dead issues per day.

Outputs a table: date, sessions_on_day, total_player_rows, problematic_rows (stored >> expected).
"""
import sqlite3
import os
from collections import defaultdict

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'bot', 'etlegacy_production.db')
if not os.path.exists(DB_PATH):
    print(f"DB not found at {DB_PATH}")
    raise SystemExit(1)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Get sessions and map to day (YYYY-MM-DD)
cur.execute("SELECT id, session_date FROM sessions")
sessions = cur.fetchall()

day_sessions = defaultdict(list)
for s in sessions:
    sd = s['session_date']
    # session_date format: YYYY-MM-DD-HHMMSS(-...)
    day = sd.split('-')[0:3]
    day_key = '-'.join(day)
    day_sessions[day_key].append(s['id'])

print(f"Days found: {len(day_sessions)}\n")
print("date       | sessions | player_rows | problematic_rows")
print("-----------------------------------------------------")

for day_key in sorted(day_sessions.keys()):
    sids = day_sessions[day_key]
    # count player rows for these sessions
    placeholders = ','.join('?' for _ in sids)
    cur.execute(f"SELECT COUNT(*) as c FROM player_comprehensive_stats WHERE session_id IN ({placeholders})", sids)
    total_players = cur.fetchone()['c']

    # count problematic rows (stored >> expected, factor>5)
    cur.execute(
        f"SELECT COUNT(*) as c FROM player_comprehensive_stats WHERE session_id IN ({placeholders}) AND time_played_minutes > 0 AND time_dead_ratio IS NOT NULL AND (time_dead_minutes / NULLIF((time_played_minutes * (time_dead_ratio/100.0)),0)) > 5",
        sids,
    )
    bad = cur.fetchone()['c']

    print(f"{day_key} | {len(sids):8d} | {total_players:11d} | {bad:16d}")

conn.close()
