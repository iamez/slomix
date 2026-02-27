#!/usr/bin/env python3
"""Read-only team consistency smoke check for the latest session date (SQLite)."""

import os
import sqlite3
import sys

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _pick_db() -> str | None:
    candidates = [
        os.path.join(ROOT, "etlegacy_production.db"),
        os.path.join(ROOT, "bot", "etlegacy_production.db"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def main() -> int:
    logger.info("Script started: %s", __file__)
    db_path = _pick_db()
    if not db_path:
        print("No sqlite DB found. Skipping team consistency check.")
        return 0

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Find latest session date from player stats
    cur.execute(
        """
        SELECT SUBSTR(session_date, 1, 10)
        FROM player_comprehensive_stats
        ORDER BY session_date DESC
        LIMIT 1
        """
    )
    row = cur.fetchone()
    if not row or not row[0]:
        print("No session_date found in player_comprehensive_stats. Skipping.")
        conn.close()
        return 0

    session_date = row[0]
    print(f"Team consistency check for session_date={session_date}")

    # Find players on multiple teams
    cur.execute(
        """
        SELECT player_name, player_guid, GROUP_CONCAT(DISTINCT team), COUNT(DISTINCT team) as team_count
        FROM player_comprehensive_stats
        WHERE SUBSTR(session_date, 1, 10) = ?
        GROUP BY player_guid
        HAVING team_count > 1
        ORDER BY player_name
        """,
        (session_date,),
    )
    conflicts = cur.fetchall()

    if not conflicts:
        print("OK: No players appear on multiple teams for this session.")
    else:
        print("WARN: Players on multiple teams detected:")
        for name, guid, teams, team_count in conflicts[:25]:
            guid_display = guid[:12] if guid else "unknown"
            print(f"  {name} ({guid_display}) -> teams {teams}")
        if len(conflicts) > 25:
            print(f"  ... and {len(conflicts) - 25} more")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
