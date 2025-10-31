import asyncio
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.ultimate_bot import UltimateETLegacyBot

async def run_sim_light():
    bot = UltimateETLegacyBot()

    # Monkeypatch wait_until_ready to avoid requiring a Discord login
    async def _dummy_wait():
        return None
    bot.wait_until_ready = _dummy_wait

    # Call on_ready to start background tasks (should be idempotent)
    await bot.on_ready()
    print('ON_READY_STARTED')

    # Let loops run briefly
    await asyncio.sleep(1)

    # Stop any running loops to clean up
    for attr in ('endstats_monitor', 'cache_refresher', 'scheduled_monitoring_check', 'voice_session_monitor'):
        task = getattr(bot, attr, None)
        try:
            if task and task.is_running():
                task.stop()
                print(f'STOPPED {attr}')
        except Exception as e:
            print('STOP_ERROR', attr, e)

    print('ON_READY_SIM_OK')

if __name__ == '__main__':
    asyncio.run(run_sim_light())
