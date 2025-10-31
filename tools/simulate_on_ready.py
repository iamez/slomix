import asyncio
import os
import sys

# Make project root importable so `bot` package can be found when running this script
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.ultimate_bot import UltimateETLegacyBot

async def run_sim():
    bot = UltimateETLegacyBot()
    # Run setup_hook (DB init, cog add)
    await bot.setup_hook()

    # Monkeypatch wait_until_ready to avoid requiring a Discord login
    async def _dummy_wait():
        return True
    bot.wait_until_ready = _dummy_wait

    # Call on_ready to start background tasks
    await bot.on_ready()
    print('ON_READY_STARTED')

    # Let loops run briefly (they should be idle if monitoring disabled)
    await asyncio.sleep(1)

    # Stop any running loops to clean up
    for attr in ('endstats_monitor','cache_refresher','scheduled_monitoring_check','voice_session_monitor'):
        task = getattr(bot, attr, None)
        try:
            if task and task.is_running():
                task.stop()
                print(f'STOPPED {attr}')
        except Exception as e:
            print('STOP_ERROR', attr, e)

    print('ON_READY_SIM_OK')

if __name__ == '__main__':
    asyncio.run(run_sim())
