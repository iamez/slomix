import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

# Get all sessions ordered by date and map
cursor.execute("""
    SELECT id, round_date, map_name, round_number
    FROM rounds
    ORDER BY round_date, map_name, round_number
""")

sessions = cursor.fetchall()
print(f"Found {len(sessions)} sessions")

# Assign map_id to pair R1+R2
current_map_id = 1
prev_date = None
prev_map = None

for round_id, round_date, map_name, round_num in sessions:
    # Extract just the date part (YYYY-MM-DD-HHMMSS)
    date_part = round_date[:17] if len(round_date) >= 17 else round_date
    
    # If it's a new session day or different map, increment map_id
    if date_part != prev_date or map_name != prev_map:
        if round_num == 2:
            # R2 without R1, increment
            current_map_id += 1
        prev_date = date_part
        prev_map = map_name
    
    # Assign map_id
    cursor.execute("UPDATE rounds SET map_id = ? WHERE id = ?", (current_map_id, round_id))
    
    # After R2, increment for next map
    if round_num == 2:
        current_map_id += 1

conn.commit()
print(f"✅ Assigned map_id values (1-{current_map_id-1})")
conn.close()
