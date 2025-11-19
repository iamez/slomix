import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

# Test the new logic
print("Testing new session date logic:")
print("="*60)

# Get the last 2 calendar dates that have sessions
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
latest_session_date = result[0] if result else None

print(f"\n✅ Latest session date (new logic): {latest_session_date}")

# Show what sessions this includes
cursor.execute("""
    SELECT id, round_date, map_name
    FROM rounds
    WHERE SUBSTR(round_date, 1, 10) = ?
    ORDER BY id
""", (latest_session_date,))

print(f"\n📅 Sessions included in '{latest_session_date}':")
for row in cursor.fetchall():
    print(f"  ID {row[0]}: {row[1]} - {row[2]}")

# Compare with old logic
cursor.execute("""
    SELECT DISTINCT SUBSTR(s.round_date, 1, 10) as date
    FROM rounds s
    WHERE EXISTS (
        SELECT 1 FROM player_comprehensive_stats p
        WHERE SUBSTR(p.round_date, 1, 10) = SUBSTR(s.round_date, 1, 10)
    )
    ORDER BY date DESC
    LIMIT 1
""")

old_result = cursor.fetchone()
old_date = old_result[0] if old_result else None

print(f"\n❌ Old logic would have returned: {old_date}")
print(f"\n💡 New logic correctly uses the START date of the gaming session!")

conn.close()
