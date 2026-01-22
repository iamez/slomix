import asyncio, sqlite3, tempfile, sys
from types import SimpleNamespace
from pathlib import Path
# Add project root to sys.path (portable)
sys.path.append(str(Path(__file__).resolve().parent.parent))
from bot.ultimate_bot import ETLegacyCommands
import aiosqlite

# Create temp DB
tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
path = tmp.name
tmp.close()
conn = sqlite3.connect(path)
cur = conn.cursor()
cur.execute('CREATE TABLE player_comprehensive_stats (player_guid TEXT, clean_name TEXT, kills INTEGER)')
cur.execute("INSERT INTO player_comprehensive_stats (player_guid, clean_name, kills) VALUES (?, ?, ?)", ('g1','Tester',5))
conn.commit()
conn.close()

async def run():
    bot = SimpleNamespace(db_path=path)
    cog = ETLegacyCommands(bot)
    async with aiosqlite.connect(path) as db:
        try:
            async with db.execute('SELECT player_name FROM player_comprehensive_stats') as c:
                r = await c.fetchone()
                print('SELECT_BEFORE', r)
        except Exception as e:
            print('SELECT_BEFORE_FAILED', type(e).__name__, str(e))
        await cog._ensure_player_name_alias(db)
        try:
            async with db.execute('SELECT player_name FROM player_comprehensive_stats') as c:
                r = await c.fetchone()
                print('SELECT_AFTER', r)
        except Exception as e:
            print('SELECT_AFTER_FAILED', type(e).__name__, str(e))

asyncio.run(run())
print('CLEANUP', path)
