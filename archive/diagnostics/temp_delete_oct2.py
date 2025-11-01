import os
import sqlite3

# The database is in the root, not in the bot/bot directory for this script
db_path = 'g:/VisualStudio/Python/stats/etlegacy_production.db'

if not os.path.exists(db_path):
    print(f"❌ ERROR: Database not found at {db_path}")
else:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    try:
        # Get counts before deleting
        c.execute(
            "SELECT COUNT(*) FROM player_comprehensive_stats WHERE session_date = '2025-10-02'"
        )
        before_players = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM sessions WHERE session_date = '2025-10-02'")
        before_sessions = c.fetchone()[0]

        if before_players == 0 and before_sessions == 0:
            print("✅ No October 2nd data found to delete. Already clean.")
        else:
            print(
                f"Found {before_players} player records and {before_sessions} sessions for Oct 2nd. Deleting...")
            # Delete player stats for October 2nd
            c.execute("DELETE FROM player_comprehensive_stats WHERE session_date = '2025-10-02'")
            deleted_players = c.rowcount

            # Delete sessions for October 2nd
            c.execute("DELETE FROM sessions WHERE session_date = '2025-10-02'")
            deleted_sessions = c.rowcount

            conn.commit()
            print(
                f"✅ Deleted {deleted_players} player records and {deleted_sessions} session records for Oct 2nd.")

    except sqlite3.Error as e:
        print(f"❌ An error occurred: {e}")
    finally:
        conn.close()
