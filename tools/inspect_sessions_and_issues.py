"""Inspect sessions table and report time-dead inconsistencies per session.

Prints total sessions, a brief listing (id, session_date, map_name, created_at),
and for each session the number of player rows where stored time_dead_minutes >> expected.
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

# Count sessions
cur.execute("SELECT COUNT(*) as c FROM sessions")
count = cur.fetchone()['c']
print(f"Total sessions in DB: {count}\n")

# List recent sessions (limit 50)
cur.execute("SELECT id, session_date, map_name, round_number, created_at FROM sessions ORDER BY created_at DESC, id DESC LIMIT 100")
sessions = cur.fetchall()
print(f"Recent sessions (up to 100):\n")
for s in sessions[:50]:
    print(f"  id={s['id']:5d} date={s['session_date'][:19]} map={s['map_name'][:30]:30s} round={s['round_number']} created_at={s['created_at']}")

# For each session in the DB (or recent), count problematic player rows
print('\nProblematic time_dead rows per session (stored >> expected):')
cur.execute("SELECT id FROM sessions")
all_session_ids = [r['id'] for r in cur.fetchall()]
problematic_sessions = []
for sid in all_session_ids:
    cur.execute(
        '''
        SELECT COUNT(*) as c FROM player_comprehensive_stats
        WHERE session_id = ? AND time_played_minutes > 0 AND time_dead_ratio IS NOT NULL
          AND (time_dead_minutes / NULLIF((time_played_minutes * (time_dead_ratio/100.0)),0)) > 5
        ''',
        (sid,)
    )
    c = cur.fetchone()['c']
    if c > 0:
        problematic_sessions.append((sid, c))

# Sort by count desc and show top 30
problematic_sessions.sort(key=lambda x: x[1], reverse=True)
if problematic_sessions:
    for sid, c in problematic_sessions[:50]:
        cur.execute("SELECT session_date, map_name FROM sessions WHERE id = ?", (sid,))
        s = cur.fetchone()
        print(f"  session_id={sid} -> {c} problematic rows  ({s['session_date']} {s['map_name']})")
else:
    print("  None found")

conn.close()
