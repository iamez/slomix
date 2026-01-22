"""
Simple runnable test script to validate:
- The TEMP VIEW alias behavior (SELECT player_name works even if only clean_name exists)
- The graph helper can generate a PNG buffer

Run with:
  python tests/check_alias_and_graphs.py

This is a lightweight runner (no pytest required).
"""
import asyncio
import os
import sqlite3
import tempfile

import aiosqlite

# Ensure the ultimate_bot module is imported early so its aiosqlite.connect
# wrapper (if present) is applied in the running process.
import bot.ultimate_bot as ub  # noqa: F401

from bot.last_session_helpers import create_performance_image


async def test_alias_and_graph(tmp_db_path: str):
    # Use sqlite3 to create the DB and seed it
    conn = sqlite3.connect(tmp_db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE player_comprehensive_stats (
            player_guid TEXT,
            clean_name TEXT,
            kills INTEGER
        )
    """)
    cur.execute("INSERT INTO player_comprehensive_stats (player_guid, clean_name, kills) VALUES (?, ?, ?)",
                ("guid-123", "Tester", 5))
    conn.commit()
    conn.close()

    # Now open with aiosqlite (this will exercise any connect wrapper)
    async with aiosqlite.connect(tmp_db_path) as db:
        # If a TEMP VIEW alias to player_name was created by the wrapper, this will succeed.
        try:
            async with db.execute("SELECT player_name FROM player_comprehensive_stats") as c:
                row = await c.fetchone()
                if row is None:
                    print("ERROR: SELECT player_name returned no rows")
                else:
                    print("OK: player_name SELECT works ->", row[0])
        except Exception as e:
            print("ERROR: SELECT player_name failed:", type(e).__name__, str(e)[:200])

    # Test graph helper
    top_players = [
        ("Tester", 5, 1, 120.0, 600, 30, 0),
        ("Alice", 3, 2, 90.0, 400, 20, 5),
    ]
    try:
        buf = create_performance_image(top_players, "2099-01-01")
        if buf and buf.getbuffer().nbytes > 100:
            print("OK: graph generated (buffer bytes =", buf.getbuffer().nbytes, ")")
        else:
            print("ERROR: graph buffer too small")
    except ImportError:
        print("SKIP: matplotlib not available for graph test")
    except Exception as e:
        print("ERROR: graph helper failed:", type(e).__name__, str(e)[:200])


if __name__ == '__main__':
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    tmp.close()
    try:
        asyncio.run(test_alias_and_graph(tmp.name))
    finally:
        try:
            os.remove(tmp.name)
        except Exception:
            pass
