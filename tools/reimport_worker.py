import sys
import asyncio
import os

# Make project root importable
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.ultimate_bot import UltimateETLegacyBot

async def main(fname):
    bot = UltimateETLegacyBot()
    print(f"Using DB: {bot.db_path}")
    res = await bot.process_gamestats_file(os.path.join('local_stats', fname), fname)
    print('RESULT:', res)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python reimport_worker.py <filename>')
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
