import asyncio
import os
import sqlite3
import tempfile

import aiosqlite

from bot.ultimate_bot import ensure_player_name_alias


def test_alias_fallback():
    """Integration test: ensure_player_name_alias creates a per-connection TEMP VIEW
    mapping an alternate name column (clean_name) to player_name so queries
    referencing player_name succeed on the same connection.
    """
    # Create temporary SQLite file
    tf = tempfile.NamedTemporaryFile(delete=False)
    db_path = tf.name
    tf.close()

    try:
        # Create minimal table with clean_name (no player_name)
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(
            "CREATE TABLE player_comprehensive_stats (player_guid TEXT, clean_name TEXT, kills INTEGER)"
        )
        cur.execute(
            "INSERT INTO player_comprehensive_stats (player_guid, clean_name, kills) VALUES (?, ?, ?)",
            ("GUID1234", "TestPlayer", 5),
        )
        conn.commit()
        conn.close()

        async def run():
            async with aiosqlite.connect(db_path) as db:
                # Call the alias helper under test
                await ensure_player_name_alias(db)

                # Now a query referencing player_name should work on this connection
                async with db.execute(
                    "SELECT player_name, kills FROM player_comprehensive_stats"
                ) as cur:
                    row = await cur.fetchone()

                assert row is not None
                assert row[0] == "TestPlayer"
                assert row[1] == 5

        asyncio.run(run())

    finally:
        try:
            os.unlink(db_path)
        except Exception:
            pass
