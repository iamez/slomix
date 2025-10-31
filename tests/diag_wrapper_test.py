import asyncio
import sqlite3
import tempfile
import os
import sys
from types import SimpleNamespace

# Make project root importable so `bot` package can be imported
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import aiosqlite

# Import the Cog to get _enable_sql_diag
from bot.ultimate_bot import ETLegacyCommands

async def main():
    # create temp db
    tf = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    tf.close()
    db_path = tf.name
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE player_comprehensive_stats(player_guid TEXT, player_name TEXT)")
    conn.commit()
    conn.close()

    bot = SimpleNamespace(db_path=db_path)
    cog = ETLegacyCommands(bot)

    async with aiosqlite.connect(db_path) as db:
        # enable diagnostic wrapper
        await cog._enable_sql_diag(db)
        # run a simple query using async with
        async with db.execute('SELECT 1') as cur:
            row = await cur.fetchone()
            print('SELECT_OK:', row)

    os.unlink(db_path)

if __name__ == '__main__':
    asyncio.run(main())
