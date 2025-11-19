"""
Populate map_id for ALL sessions (not just Oct 28/30)
"""
import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

# Check if column exists
cursor.execute("PRAGMA table_info(sessions)")
columns = [col[1] for col in cursor.fetchall()]

if 'map_id' not in columns:
    print("Adding map_id column...")
    cursor.execute("ALTER TABLE sessions ADD COLUMN map_id INTEGER")
    conn.commit()
    print("✅ Column added")
else:
    print("✅ map_id column already exists")

# Get all sessions without map_id
cursor.execute("""
    SELECT id, round_date, map_name, round_number
    FROM rounds
    WHERE map_id IS NULL
    ORDER BY id
""")

sessions = cursor.fetchall()
print(f"\nFound {len(sessions)} sessions without map_id")

if len(sessions) == 0:
    print("✅ All sessions already have map_id!")
    conn.close()
    exit(0)

# Group by date
from collections import defaultdict
dates_dict = defaultdict(list)

for sid, sdate, map_name, rnum in sessions:
    date_part = sdate[:10]  # YYYY-MM-DD
    dates_dict[date_part].append((sid, map_name, rnum))

print(f"Processing {len(dates_dict)} dates...")

# Process each date
updates = []
for date, rounds in sorted(dates_dict.items()):
    print(f"\n  {date}: {len(rounds)} rounds", end="")
    
    # Get max map_id for this date
    cursor.execute("""
        SELECT MAX(map_id)
        FROM rounds
        WHERE round_date LIKE ?
    """, (f"{date}%",))
    
    max_map_id = cursor.fetchone()[0]
    map_counter = (max_map_id or 0) + 1
    
    # Assign map_ids
    current_map = None
    for sid, map_name, rnum in rounds:
        # New map starts when:
        # 1. First round of session
        # 2. Round 1 of any map
        # 3. Map name changes
        if current_map != map_name or rnum == 1:
            if rnum == 1:
                map_counter += 1
            current_map = map_name
        
        updates.append((map_counter, sid))
    
    print(f" → {map_counter - (max_map_id or 0)} maps")

# Apply updates
print(f"\nUpdating {len(updates)} sessions...")
cursor.executemany("UPDATE rounds SET map_id = ? WHERE id = ?", updates)
conn.commit()

print(f"✅ Done! Updated {len(updates)} sessions")

# Verify
cursor.execute("SELECT COUNT(*) FROM rounds WHERE map_id IS NULL")
remaining = cursor.fetchone()[0]

if remaining > 0:
    print(f"⚠️  {remaining} sessions still have NULL map_id")
else:
    print("✅ All sessions now have map_id!")

conn.close()
