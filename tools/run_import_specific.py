import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot.ultimate_bot import UltimateETLegacyBot

# Filename to re-import (from processed_files)
FILE = os.path.join('local_stats','2025-10-27-230734-sw_goldrush_te-round-2.txt')

async def main():
    bot = UltimateETLegacyBot()
    print(f"Using DB: {bot.db_path}")
    res = await bot.process_gamestats_file(FILE, os.path.basename(FILE))
    print('Result:', res)

if __name__ == '__main__':
    asyncio.run(main())
