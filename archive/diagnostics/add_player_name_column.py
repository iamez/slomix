"""
Safe migration script to add a `player_name` column to `player_comprehensive_stats`
if it does not exist, and populate it from `clean_name` when available.

Usage:
  python add_player_name_column.py /path/to/db.sqlite

If no path given, defaults to environment variable STATS_DB_PATH or
`stats.db` in repository root.
"""
import sqlite3
import sys
import os


def main(db_path: str):
    if not os.path.exists(db_path):
        print(f"DB not found: {db_path}")
        return 1

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info('player_comprehensive_stats')")
        cols = {r[1] for r in cur.fetchall()}  # name is at index 1
        if 'player_name' in cols:
            print("player_name already exists - nothing to do")
            return 0

        # Add column (TEXT). ALTER TABLE ADD COLUMN is safe for SQLite and
        # will initialize to NULL for existing rows.
        cur.execute("ALTER TABLE player_comprehensive_stats ADD COLUMN player_name TEXT")
        print("Added column player_name")

        # Populate from clean_name when present
        if 'clean_name' in cols:
            cur.execute(
                "UPDATE player_comprehensive_stats SET player_name = clean_name WHERE player_name IS NULL AND clean_name IS NOT NULL"
            )
            updated = conn.total_changes
            print(f"Populated player_name from clean_name (changes: {updated})")
        else:
            print("clean_name column not present - left player_name NULL for all rows")

        conn.commit()
        return 0
    except Exception as e:
        print("Migration failed:", type(e).__name__, str(e))
        conn.rollback()
        return 2
    finally:
        conn.close()


if __name__ == '__main__':
    db = None
    if len(sys.argv) > 1:
        db = sys.argv[1]
    else:
        db = os.environ.get('STATS_DB_PATH', 'stats.db')
    raise SystemExit(main(db))
