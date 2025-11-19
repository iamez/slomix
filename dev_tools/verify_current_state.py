#!/usr/bin/env python3
"""
Verify the current state of bot and database manager
"""

def check_ultimate_bot():
    """Check bot for issues"""
    print("🔍 Checking bot/ultimate_bot.py...")
    
    with open('bot/ultimate_bot.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Count process_gamestats_file functions
    count = content.count('async def process_gamestats_file')
    print(f"   Found {count} process_gamestats_file function(s)")
    
    # Check if it has _import_stats_to_db
    if '_import_stats_to_db' in content:
        print("   ✅ Has _import_stats_to_db call (WORKING VERSION)")
    else:
        print("   ❌ Missing _import_stats_to_db call (BROKEN)")
    
    # Check for PostgreSQL compatibility
    issues = []
    if 'INSERT OR REPLACE' in content:
        issues.append("Still has SQLite-specific INSERT OR REPLACE")
    
    if issues:
        print("   ⚠️ Issues found:")
        for issue in issues:
            print(f"      - {issue}")
    else:
        print("   ✅ No obvious issues")
    
    return count == 1 and '_import_stats_to_db' in content

def check_database_manager():
    """Check database manager"""
    print("\n🔍 Checking postgresql_database_manager.py...")
    
    with open('postgresql_database_manager.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    issues = []
    
    # Check for proper columns
    if 'team_damage_given' not in content or 'team_damage_received' not in content:
        issues.append("Missing team_damage_given/received columns")
    else:
        print("   ✅ Has correct team_damage columns")
    
    if 'map_name' not in content:
        issues.append("Missing map_name column in INSERT")
    else:
        print("   ✅ Has map_name column")
    
    if 'round_number' not in content:
        issues.append("Missing round_number column in INSERT")
    else:
        print("   ✅ Has round_number column")
    
    # Check for validation
    if '_validate_round_data' in content:
        print("   ✅ Has validation logic")
    else:
        issues.append("Missing validation logic")
    
    if issues:
        print("   ⚠️ Issues found:")
        for issue in issues:
            print(f"      - {issue}")
        return False
    else:
        print("   ✅ No issues found")
        return True

def check_test_results():
    """Check if test files exist"""
    import os
    print("\n🔍 Checking test files...")
    
    if os.path.exists('test_postgresql_manager.py'):
        print("   ✅ test_postgresql_manager.py exists")
    else:
        print("   ❌ test_postgresql_manager.py missing")
    
    if os.path.exists('test_validation.py'):
        print("   ✅ test_validation.py exists")
    else:
        print("   ❌ test_validation.py missing")

if __name__ == "__main__":
    print("=" * 60)
    print("VERIFICATION OF CURRENT STATE")
    print("=" * 60)
    
    bot_ok = check_ultimate_bot()
    db_ok = check_database_manager()
    check_test_results()
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    if bot_ok:
        print("✅ Bot: WORKING (no duplicate functions)")
    else:
        print("❌ Bot: HAS ISSUES")
    
    if db_ok:
        print("✅ Database Manager: WORKING")
    else:
        print("❌ Database Manager: HAS ISSUES")
    
    print("\n" + "=" * 60)
    print("RECOMMENDATIONS")
    print("=" * 60)
    
    if bot_ok and db_ok:
        print("✅ Everything looks good!")
        print("\nNext steps:")
        print("1. Run: python test_postgresql_manager.py")
        print("2. Run: python test_validation.py")
        print("3. If tests pass, restart bot: .\\restart_bot.bat")
    else:
        print("⚠️ Issues found that need fixing")
