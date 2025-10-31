"""
Smart SSH Sync Scheduler - Adaptive sync based on game session patterns
Syncs frequently during active hours (20:00-23:00 CET), less frequently during downtime
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from tools.sync_stats import sync_and_import

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('logs/smart_sync.log'), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Import the sync functionality

# Timezone
CET = ZoneInfo("Europe/Paris")


class SmartSyncScheduler:
    """Intelligent sync scheduler that adapts to game activity patterns"""

    def __init__(self):
        self.last_file_time = None
        self.consecutive_empty_checks = 0
        self.prime_time_start = 20  # 20:00 CET (8 PM)
        self.prime_time_end = 23  # 23:00 CET (11 PM)

    def get_current_cet_time(self):
        """Get current time in CET"""
        return datetime.now(CET)

    def is_prime_time(self):
        """Check if current time is during prime gaming hours (20:00-23:00 CET)"""
        current = self.get_current_cet_time()
        hour = current.hour
        return self.prime_time_start <= hour < self.prime_time_end

    def is_near_prime_time(self, minutes_before=30):
        """Check if we're within X minutes before prime time"""
        current = self.get_current_cet_time()
        hour = current.hour
        minute = current.minute

        # Check if we're 30 min before prime time (19:30-20:00)
        if hour == self.prime_time_start - 1 and minute >= (60 - minutes_before):
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
                # During active hours, check every 1 minute after finding files
                logger.info("📊 Active session detected during prime time - next check in 1 minute")
                return 60  # 1 minute
            else:
                # Off-hours but found files, check every 5 minutes
                logger.info("📊 Session detected during off-hours - next check in 5 minutes")
                return 300  # 5 minutes

        else:
            # No new files found
            self.consecutive_empty_checks += 1

            if self.is_prime_time():
                # During prime time
                if self.consecutive_empty_checks == 1:
                    # First empty check - maybe between rounds
                    logger.info("⏸️ No new files (1st check) - next check in 1 minute")
                    return 60  # 1 minute
                elif self.consecutive_empty_checks < 10:
                    # 2-9 empty checks - session might be ending
                    logger.info(
                        f"⏸️ No new files ({
                            self.consecutive_empty_checks} checks) - next check in 10 minutes"
                    )
                    return 600  # 10 minutes
                else:
                    # 10+ empty checks during prime time - session likely over
                    logger.info("💤 Session ended during prime time - next check in 30 minutes")
                    return 1800  # 30 minutes

            elif self.is_near_prime_time():
                # 30 minutes before prime time - start checking more frequently
                logger.info("⏰ Approaching prime time - next check in 5 minutes")
                return 300  # 5 minutes

            else:
                # Off-hours
                if self.consecutive_empty_checks < 6:
                    # First few checks - maybe late session
                    logger.info(
                        f"💤 Off-hours, no files ({self.consecutive_empty_checks} checks) - next check in 10 minutes"
                    )
                    return 600  # 10 minutes
                else:
                    # Deep sleep until near prime time
                    current = self.get_current_cet_time()

                    # Calculate time until next prime time
                    next_prime = current.replace(
                        hour=self.prime_time_start, minute=0, second=0, microsecond=0
                    )

                    # If we're past today's prime time, target tomorrow
                    if current.hour >= self.prime_time_end:
                        next_prime += timedelta(days=1)

                    # Wake up 30 minutes before prime time
                    wake_time = next_prime - timedelta(minutes=30)
                    seconds_until_wake = (wake_time - current).total_seconds()

                    # Minimum 1 hour sleep, maximum based on calculation
                    sleep_seconds = max(3600, int(seconds_until_wake))  # At least 1 hour

                    hours = sleep_seconds / 3600
                    logger.info(
                        f"😴 Deep sleep until {
                            wake_time.strftime('%H:%M CET')} ({
                            hours:.1f} hours)"
                    )
                    return sleep_seconds

    async def run_forever(self):
        """Main scheduler loop - runs continuously"""

        logger.info("=" * 70)
        logger.info("🤖 SMART SSH SYNC SCHEDULER STARTED")
        logger.info("=" * 70)
        logger.info(f"Prime time: {self.prime_time_start}:00 - {self.prime_time_end}:00 CET")
        logger.info(f"Current time: {self.get_current_cet_time().strftime('%H:%M:%S CET')}")
        logger.info("=" * 70)

        while True:
            try:
                current_time = self.get_current_cet_time()
                is_prime = self.is_prime_time()

                logger.info("")
                logger.info(
                    f"🔄 Sync check at {current_time.strftime('%H:%M:%S CET')} "
                    + f"({'PRIME TIME' if is_prime else 'off-hours'})"
                )
                logger.info("-" * 70)

                # Run sync
                result = await sync_and_import()

                # Determine next interval
                next_interval = self.get_next_sync_interval(result['new_files_count'] > 0)

                # Log summary
                if result['new_files_count'] > 0:
                    logger.info(
                        f"✅ Synced {result['new_files_count']} new files, "
                        + f"imported {result['imported_count']} sessions"
                    )
                else:
                    logger.info("✅ No new files found")

                logger.info(
                    f"⏰ Next sync in {next_interval} seconds ({
                        next_interval / 60:.1f} minutes)"
                )
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

    # Create logs directory if it doesn't exist
    Path("logs").mkdir(exist_ok=True)

    scheduler = SmartSyncScheduler()
    await scheduler.run_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
