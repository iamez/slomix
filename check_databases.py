import sqlite3

databases = [
    'etlegacy_comprehensive.db',
    'etlegacy_discord_ready.db',
    'etlegacy_perfect.db',
    'etlegacy_production.db',
]

for db_name in databases:
    try:
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()

        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cursor.fetchall()]

        print(f"\n{'=' * 60}")
        print(f"DATABASE: {db_name}")
        print(f"{'=' * 60}")
        print(f"Tables: {', '.join(tables)}")

        # Check for comprehensive stats tables
        if 'player_comprehensive_stats' in tables:
            cursor.execute("SELECT COUNT(*) FROM player_comprehensive_stats")
            count = cursor.fetchone()[0]
            print(f"✅ player_comprehensive_stats: {count:,} rows")

            # Check sessions table structure
            if 'sessions' in tables:
                cursor.execute("PRAGMA table_info(sessions)")
                columns = [r[1] for r in cursor.fetchall()]
                print(f"   Sessions columns: {', '.join(columns)}")

                cursor.execute("SELECT COUNT(*) FROM sessions")
                sess_count = cursor.fetchone()[0]
                print(f"   Sessions: {sess_count:,} rows")

        conn.close()
    except Exception as e:
        print(f"❌ Error reading {db_name}: {e}")

print(f"\n{'=' * 60}")
