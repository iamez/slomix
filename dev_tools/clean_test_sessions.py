import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

print("Test sessions (tmp_dry_ru):")
print("="*70)

cursor.execute("""
    SELECT id, round_date, map_name, round_number, created_at
    FROM rounds
    WHERE round_date LIKE 'tmp%'
    ORDER BY id
""")

for row in cursor.fetchall():
    print(f"ID {row[0]}: {row[1]} - {row[2]} R{row[3]} - created: {row[4]}")

print("\nDeleting these test sessions...")
cursor.execute("DELETE FROM rounds WHERE round_date LIKE 'tmp%'")
deleted = cursor.rowcount
print(f"Deleted {deleted} sessions")

# Also delete associated player stats
cursor.execute("DELETE FROM player_comprehensive_stats WHERE round_id NOT IN (SELECT id FROM rounds)")
deleted_stats = cursor.rowcount
print(f"Deleted {deleted_stats} orphaned player stats")

conn.commit()
conn.close()

print("\n✅ Test data cleaned up!")
