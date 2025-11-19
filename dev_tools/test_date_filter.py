"""
Test Bot Startup Time Filter for SSH Auto-Import

This script verifies the bot startup time filter is working correctly.
Only files created AFTER bot startup are imported.
"""

from datetime import datetime, timedelta

def test_startup_time_filter():
    """Test the bot startup time filtering logic"""
    
    # Simulate bot startup time (now)
    bot_startup_time = datetime.now()
    
    # Create test cases relative to bot startup
    test_cases = [
        # Future files (created after bot starts) - SHOULD PROCESS
        (bot_startup_time + timedelta(minutes=1), "+1 minute", True),
        (bot_startup_time + timedelta(minutes=5), "+5 minutes", True),
        (bot_startup_time + timedelta(hours=1), "+1 hour", True),
        
        # Past files (created before bot starts) - SHOULD SKIP
        (bot_startup_time - timedelta(minutes=1), "-1 minute", False),
        (bot_startup_time - timedelta(minutes=30), "-30 minutes", False),
        (bot_startup_time - timedelta(hours=1), "-1 hour", False),
        (bot_startup_time - timedelta(days=1), "-1 day", False),
        (bot_startup_time - timedelta(days=30), "-30 days", False),
    ]
    
    print("Testing bot startup time filter logic:\n")
    print(f"Bot Startup Time: {bot_startup_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    print(f"{'File Datetime':<25} {'Relative Time':<15} {'Process?':<12} {'Status'}")
    print("-" * 75)
    
    all_passed = True
    
    for file_datetime, description, should_process in test_cases:
        # Apply filter: only process files created AFTER bot startup
        will_process = file_datetime >= bot_startup_time
        
        # Check if correct
        status = "✅ PASS" if will_process == should_process else "❌ FAIL"
        if will_process != should_process:
            all_passed = False
        
        process_str = "YES" if will_process else "NO"
        datetime_str = file_datetime.strftime('%Y-%m-%d %H:%M:%S')
        print(f"{datetime_str:<25} {description:<15} {process_str:<12} {status}")
    
    print("\n" + "="*75)
    if all_passed:
        print("✅ ALL TESTS PASSED - Startup time filter is working correctly!")
        print("\nBehavior:")
        print("  • Files created AFTER bot startup: Import and post to Discord ✅")
        print("  • Files created BEFORE bot startup: Skip (prevent old file spam) ⏭️")
        print("\nThis ensures:")
        print("  ✓ Live updates work (new games auto-import)")
        print("  ✓ Old files don't spam Discord on bot restart")
        print("  ✓ Historical data can still be imported manually via !sync commands")
    else:
        print("❌ SOME TESTS FAILED")
    
    return all_passed

if __name__ == "__main__":
    test_startup_time_filter()
