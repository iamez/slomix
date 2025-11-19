"""
Test script to demonstrate comprehensive logging system
Run this to see all log files being created and populated
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from bot.logging_config import (
    setup_logging,
    log_command_execution,
    log_database_operation,
    log_stats_import,
    log_performance_warning,
    get_logger
)
import logging
import time

def test_logging_system():
    """Test all logging features"""
    
    print("=" * 80)
    print("  Testing Comprehensive Logging System")
    print("=" * 80)
    print()
    
    # Setup logging
    setup_logging(logging.DEBUG)
    
    # Get various loggers
    core_logger = get_logger('bot.core')
    command_logger = get_logger('bot.commands')
    db_logger = get_logger('bot.database')
    error_logger = get_logger('bot.errors')
    
    print("✓ Logging system initialized")
    print("✓ Log files created in ./logs/")
    print()
    
    # Test different log levels
    print("Testing log levels...")
    core_logger.debug("🐛 This is a DEBUG message")
    core_logger.info("ℹ️  This is an INFO message")
    core_logger.warning("⚠️  This is a WARNING message")
    core_logger.error("❌ This is an ERROR message")
    
    # Test command logging
    print("\nTesting command logging...")
    class MockContext:
        class Author:
            name = "TestUser"
            discriminator = "1234"
            id = 123456789
        class Guild:
            name = "Test Server"
            id = 987654321
        class Channel:
            name = "test-channel"
            id = 111222333
        author = Author()
        guild = Guild()
        channel = Channel()
        class Command:
            name = "test_command"
        command = Command()
    
    ctx = MockContext()
    start = time.time()
    time.sleep(0.1)  # Simulate command execution
    end = time.time()
    
    log_command_execution(ctx, "!test_command", start, end)
    print("✓ Command execution logged")
    
    # Test database operations
    print("\nTesting database logging...")
    start = time.time()
    time.sleep(0.05)
    duration = time.time() - start
    
    log_database_operation("SELECT", "Fetching player stats", duration=duration)
    log_database_operation("INSERT", "Inserting round data", duration=0.2)
    log_database_operation("UPDATE", "Updating gaming sessions", duration=0.1)
    print("✓ Database operations logged")
    
    # Test stats import logging
    print("\nTesting stats import logging...")
    log_stats_import(
        "gamestats_2025-11-06_120000.xml",
        round_count=1,
        player_count=8,
        weapon_count=45,
        duration=2.5
    )
    log_stats_import(
        "gamestats_2025-11-06_121500.xml",
        error="Parse error: Invalid XML format",
        duration=0.3
    )
    print("✓ Stats imports logged")
    
    # Test performance warnings
    print("\nTesting performance warnings...")
    log_performance_warning("Slow query: SELECT * FROM rounds", 5.5, threshold=1.0)
    log_performance_warning("Graph generation", 3.2, threshold=2.0)
    print("✓ Performance warnings logged")
    
    # Test error logging with exception
    print("\nTesting error logging with exceptions...")
    try:
        raise ValueError("This is a test error with full stack trace")
    except Exception as e:
        error_logger.error(f"Test error: {e}", exc_info=True)
    print("✓ Error with stack trace logged")
    
    # Summary
    print("\n" + "=" * 80)
    print("  Logging Test Complete!")
    print("=" * 80)
    print()
    print("Check the following log files in ./logs/:")
    print("  📄 bot.log       - All INFO and above messages")
    print("  📄 errors.log    - Only ERROR and CRITICAL messages")
    print("  📄 commands.log  - Command execution tracking")
    print("  📄 database.log  - Database operations (DEBUG level)")
    print()
    print("Each file rotates at 10MB with 5 backups (max 50MB per log type)")
    print()
    
    # Show file sizes
    logs_dir = Path("logs")
    if logs_dir.exists():
        print("Current log file sizes:")
        for log_file in sorted(logs_dir.glob("*.log")):
            size = log_file.stat().st_size
            print(f"  {log_file.name:20} - {size:,} bytes")
        print()

if __name__ == "__main__":
    test_logging_system()
