import asyncio
import os
import sys

# Ensure project root is on path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.ultimate_bot import UltimateETLegacyBot

FILE = os.path.join('local_stats','2025-10-30-233301-te_escape2-round-2.txt')

async def main():
    bot = UltimateETLegacyBot()
    print(f"Using DB: {bot.db_path}")
    res = await bot.process_gamestats_file(FILE, os.path.basename(FILE))
    print('Result:', res)

if __name__ == '__main__':
    asyncio.run(main())
