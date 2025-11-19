import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

print("Sessions breakdown by date:")
print("="*70)

cursor.execute("""
    SELECT SUBSTR(round_date, 1, 10) as date, COUNT(*) as count
    FROM rounds
    GROUP BY date
    ORDER BY date DESC
""")

for row in cursor.fetchall():
    print(f"{row[0]}: {row[1]} sessions")

print("\nSample of recent session data:")
print("="*70)

cursor.execute("""
    SELECT s.id, s.round_date, s.map_name, s.round_number, COUNT(p.id) as players
    FROM rounds s
    LEFT JOIN player_comprehensive_stats p ON s.id = p.round_id
    GROUP BY s.id
    ORDER BY s.round_date DESC
    LIMIT 10
""")

for row in cursor.fetchall():
    print(f"ID {row[0]}: {row[1]} - {row[2]} R{row[3]} - {row[4]} players")

conn.close()
