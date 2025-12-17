import sqlite3
import os

db_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "etlegacy_production.db",
)
print(f"Checking DB at: {db_path}")

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("\n--- sessions table schema ---")
    cursor.execute("PRAGMA table_info(sessions)")
    for col in cursor.fetchall():
        print(col)

    print("\n--- player_links table schema ---")
    cursor.execute("PRAGMA table_info(player_links)")
    for col in cursor.fetchall():
        print(col)

    conn.close()
except Exception as e:
    print(f"Error: {e}")
