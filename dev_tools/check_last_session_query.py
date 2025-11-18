import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

print("Nov 2 sessions with player counts:")
print("="*70)

cursor.execute("""
    SELECT s.id, s.round_date, s.map_name, s.round_number,
           COUNT(p.id) as player_count
    FROM rounds s
    LEFT JOIN player_comprehensive_stats p ON s.id = p.round_id
    WHERE s.round_date LIKE '2025-11-02-2%'
    GROUP BY s.id
    ORDER BY s.id DESC
    LIMIT 10
""")

for row in cursor.fetchall():
    print(f"  ID {row[0]}: {row[1]} - {row[2]} R{row[3]} - {row[4]} players")

print()
print("Does the query return Nov 2?")
print("="*70)

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
print(f"Query returns: {result[0]}")

print()
print("What are the last 2 distinct dates with player stats?")
print("="*70)

cursor.execute("""
    SELECT DISTINCT SUBSTR(s.round_date, 1, 10) as date,
           COUNT(DISTINCT s.id) as sessions
    FROM rounds s
    WHERE EXISTS (
        SELECT 1 FROM player_comprehensive_stats p
        WHERE p.round_id = s.id
    )
    GROUP BY SUBSTR(s.round_date, 1, 10)
    ORDER BY date DESC
    LIMIT 3
""")

for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]} sessions")

conn.close()
