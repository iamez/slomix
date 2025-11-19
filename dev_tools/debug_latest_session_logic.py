import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

print("Current _get_latest_session_date logic:")
print("="*70)

# Current query logic
cursor.execute("""
    SELECT MIN(SUBSTR(s.round_date, 1, 10)) as start_date
    FROM rounds s
    WHERE SUBSTR(s.round_date, 1, 10) IN (
        SELECT DISTINCT SUBSTR(round_date, 1, 10)
        FROM rounds
        ORDER BY round_date DESC
        LIMIT 2
    )
    AND EXISTS (
        SELECT 1 FROM player_comprehensive_stats p
        WHERE p.round_id = s.id
    )
""")

result = cursor.fetchone()
print(f"Returns: {result[0]}")
print()

print("What we WANT (actual latest map_id):")
print("="*70)

# Better query: get the date of the session with the highest map_id
cursor.execute("""
    SELECT SUBSTR(round_date, 1, 10) as date, 
           MAX(map_id) as latest_map_id,
           COUNT(*) as rounds
    FROM rounds
    WHERE map_id IS NOT NULL
    GROUP BY SUBSTR(round_date, 1, 10)
    ORDER BY MAX(map_id) DESC
    LIMIT 3
""")

print("Dates with their highest map_id:")
for row in cursor.fetchall():
    print(f"  {row[0]}: map_id up to {row[1]} ({row[2]} rounds)")

print()
print("Actual latest session:")
print("="*70)

# Get the session with the absolute highest map_id
cursor.execute("""
    SELECT map_id, MIN(round_date) as session_start, 
           MAX(round_date) as session_end,
           GROUP_CONCAT(DISTINCT map_name) as maps
    FROM rounds
    WHERE map_id = (SELECT MAX(map_id) FROM rounds WHERE map_id IS NOT NULL)
    GROUP BY map_id
""")

row = cursor.fetchone()
print(f"map_id: {row[0]}")
print(f"Session started: {row[1]}")
print(f"Session ended: {row[2]}")
print(f"Maps: {row[3]}")

conn.close()
