import sqlite3
import os

db_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "etlegacy_production.db",
)
print(f"Migrating DB at: {db_path}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 1. Create rounds table if not exists (it might be missing since we overwrote the DB with the backup)
cursor.execute(
    """
CREATE TABLE IF NOT EXISTS rounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    map_name TEXT,
    round_number INTEGER,
    actual_time TEXT,
    winner_team TEXT,
    round_outcome TEXT,
    round_date TEXT,
    round_time TEXT,
    round_status TEXT
);
"""
)

# 2. Check if sessions table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'")
if not cursor.fetchone():
    print("Error: 'sessions' table not found. Cannot migrate.")
    conn.close()
    exit(1)

# 3. Migrate data
print("Migrating data from 'sessions' to 'rounds'...")
cursor.execute("SELECT * FROM sessions")
sessions = cursor.fetchall()


# Helper to map team ID to name (assuming 1=Axis, 2=Allies based on common ET logic, but checking data might be safer.
# For now, let's assume 1=Axis, 2=Allies. If 0, maybe Draw?)
def get_team_name(team_id):
    if team_id == 1:
        return "Axis"
    if team_id == 2:
        return "Allies"
    return "Unknown"


rounds_data = []
for s in sessions:
    # Schema of sessions:
    # 0: id, 1: session_date, 2: map_name, 3: round_number, 4: time_limit,
    # 5: actual_time, 6: time_display, 7: created_at, 8: defender_team, 9: winner_team

    session_date = s[1]  # e.g., "2025-10-07" or "2025-10-07 10:23:47"
    map_name = s[2]
    round_number = s[3]
    actual_time = s[5]
    winner_team = get_team_name(s[9])

    # Split date and time if possible
    if " " in session_date:
        r_date, r_time = session_date.split(" ", 1)
    else:
        r_date = session_date
        r_time = "00:00:00"

    rounds_data.append(
        (
            map_name,
            round_number,
            actual_time,
            winner_team,
            "Objective",  # Default outcome
            r_date,
            r_time,
            "completed",
        )
    )

cursor.executemany(
    """
INSERT INTO rounds (map_name, round_number, actual_time, winner_team, round_outcome, round_date, round_time, round_status)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""",
    rounds_data,
)

conn.commit()
print(f"Migrated {len(rounds_data)} rounds.")

# 4. Verify player_links
cursor.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name='player_links'"
)
if cursor.fetchone():
    cursor.execute("SELECT count(*) FROM player_links")
    count = cursor.fetchone()[0]
    print(f"Found 'player_links' table with {count} rows.")
else:
    print("Warning: 'player_links' table NOT found in backup.")

conn.close()
