"""
Smart SSH Sync Scheduler - Adaptive sync based on game session patterns
Syncs frequently during active hours (20:00-23:00 CET), less during downtime
"""

import asyncio
import logging
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# Setup logging
Path("logs").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/smart_sync.log', encoding='utf-8'),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Timezone
CET = ZoneInfo("Europe/Paris")


class SmartSyncScheduler:
    """Intelligent sync scheduler that adapts to game activity patterns"""

    def __init__(self):
        self.consecutive_empty_checks = 0
        self.prime_time_start = 20  # 20:00 CET (8 PM)
        self.prime_time_end = 23  # 23:00 CET (11 PM)

    def get_current_cet_time(self):
        """Get current time in CET"""
        return datetime.now(CET)

    def is_prime_time(self):
        """Check if current time is during prime gaming hours"""
        current = self.get_current_cet_time()
        hour = current.hour
        return self.prime_time_start <= hour < self.prime_time_end

    def is_near_prime_time(self, minutes_before=30):
        """Check if we're within X minutes before prime time"""
        current = self.get_current_cet_time()
        hour = current.hour
        minute = current.minute

        # Check if we're 30 min before prime time (19:30-20:00)
        if hour == self.prime_time_start - 1:
            if minute >= (60 - minutes_before):
                return True
        return False

    def get_next_sync_interval(self, found_new_files: bool) -> int:
        """
        Determine next sync interval based on:
        - Time of day (prime time vs off-hours)
        - Recent activity (found files or not)
        - Consecutive empty checks

        Returns: seconds until next sync
        """

        if found_new_files:
            # Reset consecutive empty counter
            self.consecutive_empty_checks = 0

            if self.is_prime_time():
                # During active hours, check every 1 minute after files
                msg = "📊 Active session - next check in 1 minute"
                logger.info(msg)
                return 60  # 1 minute
            else:
                # Off-hours but found files, check every 5 minutes
                msg = "📊 Off-hours session - next check in 5 minutes"
                logger.info(msg)
                return 300  # 5 minutes

        else:
            # No new files found
            self.consecutive_empty_checks += 1

            if self.is_prime_time():
                # During prime time
                if self.consecutive_empty_checks == 1:
                    # First empty check - maybe between rounds
                    logger.info("⏸️ No files (1st check) - wait 1 minute")
                    return 60  # 1 minute
                elif self.consecutive_empty_checks < 10:
                    # 2-9 empty checks - session might be ending
                    logger.info(
                        f"⏸️ No files ({self.consecutive_empty_checks} checks) - wait 10 minutes"
                    )
                    return 600  # 10 minutes
                else:
                    # 10+ empty checks - session likely over
                    logger.info("💤 Session ended - wait 30 minutes")
                    return 1800  # 30 minutes

            elif self.is_near_prime_time():
                # 30 minutes before prime time
                logger.info("⏰ Approaching prime time - wait 5 minutes")
                return 300  # 5 minutes

            else:
                # Off-hours
                if self.consecutive_empty_checks < 6:
                    # First few checks - maybe late session
                    logger.info(
                        f"💤 Off-hours, no files "
                        f"({self.consecutive_empty_checks}) - wait 10 min"
                    )
                    return 600  # 10 minutes
                else:
                    # Deep sleep until near prime time
                    current = self.get_current_cet_time()

                    # Calculate time until next prime time
                    next_prime = current.replace(
                        hour=self.prime_time_start, minute=0, second=0, microsecond=0
                    )

                    # If past today's prime time, target tomorrow
                    if current.hour >= self.prime_time_end:
                        next_prime += timedelta(days=1)

                    # Wake up 30 minutes before prime time
                    wake_time = next_prime - timedelta(minutes=30)
                    seconds_until_wake = (wake_time - current).total_seconds()

                    # Minimum 1 hour sleep
                    sleep_seconds = max(3600, int(seconds_until_wake))

                    hours = sleep_seconds / 3600
                    wake_str = wake_time.strftime('%H:%M CET')
                    logger.info(f"😴 Deep sleep until {wake_str} ({hours:.1f} hours)")
                    return sleep_seconds

    async def run_sync(self):
        """Run the sync script and return if new files were found"""
        try:
            result = subprocess.run(
                [sys.executable, 'tools/sync_stats.py'],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            output = result.stdout + result.stderr

            # Check if new files were found
            found_new = '🆕 Found' in output or '📥 Downloading' in output

            # Log relevant output
            if found_new:
                logger.info("✅ New files synced and imported")
                # Log number of files if available
                for line in output.split('\n'):
                    if 'Downloaded:' in line or 'Imported:' in line:
                        logger.info(line.strip())
            else:
                logger.info("✅ No new files found")

            return found_new

        except subprocess.TimeoutExpired:
            logger.error("❌ Sync timed out after 5 minutes")
            return False
        except Exception as e:
            logger.error(f"❌ Sync error: {e}")
            return False

    async def run_forever(self):
        """Main scheduler loop - runs continuously"""

        logger.info("=" * 70)
        logger.info("🤖 SMART SSH SYNC SCHEDULER STARTED")
        logger.info("=" * 70)
        logger.info(f"Prime time: {self.prime_time_start}:00 - " f"{self.prime_time_end}:00 CET")
        cet_time = self.get_current_cet_time().strftime('%H:%M:%S CET')
        logger.info(f"Current time: {cet_time}")
        logger.info("=" * 70)

        while True:
            try:
                current_time = self.get_current_cet_time()
                is_prime = self.is_prime_time()

                logger.info("")
                time_str = current_time.strftime('%H:%M:%S CET')
                mode = 'PRIME TIME' if is_prime else 'off-hours'
                logger.info(f"🔄 Sync check at {time_str} ({mode})")
                logger.info("-" * 70)

                # Run sync
                found_new = await self.run_sync()

                # Determine next interval
                next_interval = self.get_next_sync_interval(found_new)

                logger.info(f"⏰ Next sync in {next_interval}s " f"({next_interval / 60:.1f} min)")
                logger.info("-" * 70)

                # Sleep until next check
                await asyncio.sleep(next_interval)

            except KeyboardInterrupt:
                logger.info("\n🛑 Scheduler stopped by user")
                break
            except Exception as e:
                logger.error(f"❌ Error in scheduler: {e}", exc_info=True)
                # On error, wait 5 minutes before retrying
                logger.info("⏰ Waiting 5 minutes before retry...")
                await asyncio.sleep(300)


async def main():
    """Entry point"""
    scheduler = SmartSyncScheduler()
    await scheduler.run_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
