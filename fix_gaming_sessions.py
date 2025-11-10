#!/usr/bin/env python3
"""
Fix Gaming Session IDs for 2025-11-09

This script recalculates gaming_session_id for all rounds that have NULL values
or need to be recalculated using the 60-minute gap logic.
"""

import asyncio
import logging
from datetime import datetime

from bot.core.database_adapter import create_adapter
from bot.config import load_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def fix_gaming_sessions():
    """Recalculate gaming_session_id for all rounds"""
    
    config = load_config()
    adapter = create_adapter(**config.get_database_adapter_kwargs())
    await adapter.connect()
    
    try:
        # Get all rounds ordered by date and time
        query = """
            SELECT id, round_date, round_time, gaming_session_id
            FROM rounds
            WHERE round_date LIKE '2025-%'
            ORDER BY round_date, round_time
        """
        rounds = await adapter.fetch_all(query)
        
        logger.info(f"Found {len(rounds)} rounds to process")
        
        current_session_id = 1
        last_dt = None
        updates = 0
        
        for round_id, round_date, round_time, old_session_id in rounds:
            # Parse datetime (handle both HHMMSS and HH:MM:SS formats)
            # Also normalize round_time to HHMMSS format for consistency
            normalized_time = round_time
            try:
                # Try HHMMSS format first (no colons)
                if ':' not in str(round_time):
                    dt = datetime.strptime(
                        f"{round_date} {round_time}", 
                        '%Y-%m-%d %H%M%S'
                    )
                    normalized_time = round_time  # Already correct format
                else:
                    # HH:MM:SS format (with colons) - need to normalize
                    dt = datetime.strptime(
                        f"{round_date} {round_time}", 
                        '%Y-%m-%d %H:%M:%S'
                    )
                    normalized_time = dt.strftime('%H%M%S')  # Convert to HHMMSS
            except Exception as e:
                logger.warning(
                    f"Failed to parse {round_date} {round_time}: {e}"
                )
                continue
            
            # Calculate gap from last round
            if last_dt:
                gap_minutes = (dt - last_dt).total_seconds() / 60
                
                # If gap > 60 minutes, start new session
                if gap_minutes > 60:
                    current_session_id += 1
                    logger.info(
                        f"New session #{current_session_id} after {gap_minutes:.1f} min gap "
                        f"({last_dt.strftime('%Y-%m-%d %H:%M:%S')} → {dt.strftime('%Y-%m-%d %H:%M:%S')})"
                    )
            
            # Update session ID AND normalize round_time format if needed
            if old_session_id != current_session_id or normalized_time != round_time:
                await adapter.execute(
                    "UPDATE rounds SET gaming_session_id = ?, round_time = ? WHERE id = ?",
                    (current_session_id, normalized_time, round_id)
                )
                updates += 1
                updates += 1
                logger.debug(
                    f"Updated round {round_id}: session {old_session_id} → {current_session_id}"
                )
            
            last_dt = dt
        
        logger.info(f"✅ Updated {updates} rounds with recalculated gaming_session_ids")
        
        # Show session distribution
        sessions = await adapter.fetch_all("""
            SELECT gaming_session_id, COUNT(*) as rounds,
                   MIN(round_date || ' ' || round_time) as first,
                   MAX(round_date || ' ' || round_time) as last
            FROM rounds
            WHERE gaming_session_id IS NOT NULL
            GROUP BY gaming_session_id
            ORDER BY gaming_session_id
        """)
        
        logger.info(f"\n{'='*80}")
        logger.info("Gaming Session Distribution:")
        logger.info(f"{'='*80}")
        for session_id, count, first, last in sessions:
            logger.info(f"Session #{session_id}: {count} rounds ({first} → {last})")
        
        # Show today's sessions specifically
        today_sessions = await adapter.fetch_all("""
            SELECT gaming_session_id, COUNT(*) as rounds,
                   GROUP_CONCAT(DISTINCT map_name) as maps
            FROM rounds
            WHERE round_date LIKE '2025-11-09%'
            GROUP BY gaming_session_id
        """)
        
        if today_sessions:
            logger.info(f"\n{'='*80}")
            logger.info("Today's Sessions (2025-11-09):")
            logger.info(f"{'='*80}")
            for session_id, count, maps in today_sessions:
                logger.info(f"Session #{session_id}: {count} rounds - Maps: {maps}")
        
    finally:
        await adapter.close()


if __name__ == "__main__":
    asyncio.run(fix_gaming_sessions())
