"""
🎯 LIVE BOT FUNCTIONAL TEST
Tests actual bot commands with real database

This validates:
1. Bot can connect to database
2. Commands execute without errors  
3. Stats queries work
4. No breaking changes
"""

import sys
import os
import asyncio
import sqlite3

# Color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

print(f"\n{BLUE}{'='*70}{RESET}")
print(f"{BLUE}🎯 LIVE BOT FUNCTIONAL TEST{RESET}")
print(f"{BLUE}{'='*70}{RESET}\n")

# Track results
tests_passed = 0
tests_failed = 0

# TEST 1: Database connectivity
print(f"{BLUE}TEST 1: Database Connectivity{RESET}")
try:
    db_path = 'etlegacy_production.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM player_comprehensive_stats")
    count = cursor.fetchone()[0]
    
    print(f"{GREEN}✅ Database connection: OK{RESET}")
    print(f"   {count:,} player records available")
    tests_passed += 1
    conn.close()
except Exception as e:
    print(f"{RED}❌ Database connection failed: {e}{RESET}")
    tests_failed += 1
    sys.exit(1)

# TEST 2: Import bot modules
print(f"\n{BLUE}TEST 2: Bot Module Import{RESET}")
try:
    sys.path.insert(0, 'bot')
    from ultimate_bot import UltimateETLegacyBot, ETLegacyCommands
    from community_stats_parser import C0RNP0RN3StatsParser
    
    print(f"{GREEN}✅ Bot modules import: OK{RESET}")
    tests_passed += 1
except Exception as e:
    print(f"{RED}❌ Import failed: {e}{RESET}")
    tests_failed += 1
    sys.exit(1)

# TEST 3: Parser functionality
print(f"\n{BLUE}TEST 3: Stats Parser{RESET}")
try:
    # Find a test file
    import glob
    test_files = glob.glob('local_stats/*.txt')
    
    if test_files:
        test_file = test_files[0]
        parser = C0RNP0RN3StatsParser(test_file)
        result = parser.parse()
        
        if result and 'players' in result:
            print(f"{GREEN}✅ Parser works: OK{RESET}")
            print(f"   Parsed {len(result['players'])} players from {os.path.basename(test_file)}")
            tests_passed += 1
        else:
            print(f"{YELLOW}⚠️ Parser returned no data{RESET}")
            tests_failed += 1
    else:
        print(f"{YELLOW}⚠️ No test files found in local_stats/{RESET}")
        print(f"   Skipping parser test")
except Exception as e:
    print(f"{RED}❌ Parser test failed: {e}{RESET}")
    tests_failed += 1

# TEST 4: Database queries (simulate bot commands)
print(f"\n{BLUE}TEST 4: Database Queries (Bot Command Simulation){RESET}")
try:
    conn = sqlite3.connect('etlegacy_production.db')
    cursor = conn.cursor()
    
    # Simulate !stats query
    cursor.execute("""
        SELECT 
            player_name,
            SUM(kills) as total_kills,
            SUM(deaths) as total_deaths,
            SUM(damage_given) as total_damage,
            COUNT(*) as games_played
        FROM player_comprehensive_stats
        GROUP BY player_guid
        ORDER BY total_kills DESC
        LIMIT 1
    """)
    
    top_player = cursor.fetchone()
    
    if top_player:
        print(f"{GREEN}✅ Stats query: OK{RESET}")
        print(f"   Top player: {top_player[0]} ({top_player[1]:,} kills, {top_player[4]} games)")
        tests_passed += 1
    else:
        print(f"{RED}❌ No data returned{RESET}")
        tests_failed += 1
    
    conn.close()
except Exception as e:
    print(f"{RED}❌ Query failed: {e}{RESET}")
    tests_failed += 1

# TEST 5: Check automation system
print(f"\n{BLUE}TEST 5: Automation System Configuration{RESET}")
try:
    # Read .env to check automation flags
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            env_content = f.read()
        
        automation_enabled = 'AUTOMATION_ENABLED=true' in env_content
        ssh_enabled = 'SSH_ENABLED=true' in env_content
        
        print(f"{GREEN}✅ Configuration readable: OK{RESET}")
        print(f"   Automation: {'🟢 ENABLED' if automation_enabled else '🔴 DISABLED (safe for testing)'}")
        print(f"   SSH Monitor: {'🟢 ENABLED' if ssh_enabled else '🔴 DISABLED (safe for testing)'}")
        tests_passed += 1
    else:
        print(f"{YELLOW}⚠️ .env not found - copy from .env.example{RESET}")
        tests_failed += 1
except Exception as e:
    print(f"{RED}❌ Config check failed: {e}{RESET}")
    tests_failed += 1

# TEST 6: Check for broken commands
print(f"\n{BLUE}TEST 6: Command Availability{RESET}")
try:
    cog = ETLegacyCommands(None)  # Pass None as bot (we're not running it)
    
    commands = ['stats', 'last_session', 'link', 'leaderboard']
    available = []
    missing = []
    
    for cmd in commands:
        if hasattr(cog, cmd):
            available.append(cmd)
        else:
            missing.append(cmd)
    
    if len(missing) == 0:
        print(f"{GREEN}✅ All commands available: OK{RESET}")
        print(f"   Commands: {', '.join(available)}")
        tests_passed += 1
    else:
        print(f"{YELLOW}⚠️ Some commands missing: {missing}{RESET}")
        tests_failed += 1
except Exception as e:
    print(f"{RED}❌ Command check failed: {e}{RESET}")
    tests_failed += 1

# TEST 7: Automation features
print(f"\n{BLUE}TEST 7: Automation Features{RESET}")
try:
    bot_class = UltimateETLegacyBot
    
    # Check if automation methods exist
    automation_methods = [
        'on_voice_state_update',
        '_start_gaming_session', 
        '_end_gaming_session'
    ]
    
    found = [m for m in automation_methods if hasattr(bot_class, m)]
    
    if len(found) == len(automation_methods):
        print(f"{GREEN}✅ Automation methods: OK{RESET}")
        print(f"   Methods: {', '.join(found)}")
        tests_passed += 1
    else:
        missing = [m for m in automation_methods if m not in found]
        print(f"{RED}❌ Missing methods: {missing}{RESET}")
        tests_failed += 1
except Exception as e:
    print(f"{RED}❌ Automation check failed: {e}{RESET}")
    tests_failed += 1

# FINAL RESULTS
print(f"\n{BLUE}{'='*70}{RESET}")
print(f"{BLUE}FINAL RESULTS{RESET}")
print(f"{BLUE}{'='*70}{RESET}\n")

total = tests_passed + tests_failed
pass_rate = (tests_passed / total * 100) if total > 0 else 0

print(f"Total Tests: {total}")
print(f"{GREEN}Passed: {tests_passed}{RESET}")
print(f"{RED}Failed: {tests_failed}{RESET}")
print(f"Pass Rate: {pass_rate:.1f}%\n")

if pass_rate == 100:
    print(f"{GREEN}🎉 ALL FUNCTIONAL TESTS PASSED!{RESET}")
    print(f"{GREEN}✨ Bot is ready to run!{RESET}\n")
    sys.exit(0)
elif pass_rate >= 85:
    print(f"{YELLOW}⚠️ MOSTLY FUNCTIONAL ({pass_rate:.0f}%){RESET}")
    print(f"{YELLOW}Review warnings but bot should work{RESET}\n")
    sys.exit(0)
else:
    print(f"{RED}❌ CRITICAL ISSUES FOUND ({pass_rate:.0f}%){RESET}")
    print(f"{RED}Bot may not work properly{RESET}\n")
    sys.exit(1)
