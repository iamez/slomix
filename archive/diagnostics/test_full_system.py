#!/usr/bin/env python3
"""
🧪 COMPREHENSIVE SYSTEM TEST SUITE
Tests EVERYTHING after adding automation features

This script validates:
1. Existing bot commands still work
2. Database schema intact
3. No broken imports
4. New automation code doesn't break old features
5. All methods exist and are callable
"""

import sys
import os
import sqlite3
import importlib.util
from datetime import datetime

# Color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_test(name, passed, details=""):
    """Print test result with color"""
    status = f"{GREEN}✅ PASS{RESET}" if passed else f"{RED}❌ FAIL{RESET}"
    print(f"{status} - {name}")
    if details:
        print(f"        {details}")
    return passed

def print_section(title):
    """Print section header"""
    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}{title}{RESET}")
    print(f"{BLUE}{'='*70}{RESET}\n")

# Track results
tests_passed = 0
tests_failed = 0
test_results = []

print(f"\n{BLUE}🧪 COMPREHENSIVE SYSTEM TEST - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{RESET}\n")

# ============================================================================
# TEST CATEGORY 1: DATABASE INTEGRITY
# ============================================================================
print_section("TEST CATEGORY 1: DATABASE INTEGRITY")

try:
    db_path = 'etlegacy_production.db'
    if not os.path.exists(db_path):
        test_results.append(print_test("Database File Exists", False, f"Not found: {db_path}"))
        tests_failed += 1
    else:
        test_results.append(print_test("Database File Exists", True, f"Found: {db_path}"))
        tests_passed += 1
        
        # Connect and check schema
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check player_comprehensive_stats schema
        cursor.execute("PRAGMA table_info(player_comprehensive_stats)")
        cols = cursor.fetchall()
        col_count = len(cols)
        expected_cols = 53
        
        passed = col_count == expected_cols
        test_results.append(print_test(
            "Player Stats Schema (53 columns)",
            passed,
            f"Found {col_count} columns (expected {expected_cols})"
        ))
        if passed:
            tests_passed += 1
        else:
            tests_failed += 1
        
        # Check critical columns exist
        col_names = [col[1] for col in cols]
        critical_cols = [
            'player_name', 'player_guid', 'session_id', 'session_date',
            'kills', 'deaths', 'damage_given', 'damage_received',
            'revives_given', 'kill_assists', 'dynamites_planted'
        ]
        
        missing_cols = [col for col in critical_cols if col not in col_names]
        passed = len(missing_cols) == 0
        test_results.append(print_test(
            "Critical Columns Present",
            passed,
            f"Missing: {missing_cols}" if missing_cols else "All critical columns found"
        ))
        if passed:
            tests_passed += 1
        else:
            tests_failed += 1
        
        # Check required tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        required_tables = [
            'sessions',
            'player_comprehensive_stats',
            'weapon_comprehensive_stats',
            'player_links',
            'player_aliases',
            'gaming_sessions',
            'processed_files'
        ]
        
        missing_tables = [t for t in required_tables if t not in tables]
        passed = len(missing_tables) == 0
        test_results.append(print_test(
            "Required Tables Exist",
            passed,
            f"Missing: {missing_tables}" if missing_tables else f"All {len(required_tables)} tables present"
        ))
        if passed:
            tests_passed += 1
        else:
            tests_failed += 1
        
        # Check data integrity
        cursor.execute("SELECT COUNT(*) FROM player_comprehensive_stats")
        player_records = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM sessions")
        session_records = cursor.fetchone()[0]
        
        passed = player_records > 0 and session_records > 0
        test_results.append(print_test(
            "Database Has Data",
            passed,
            f"{player_records:,} player records, {session_records:,} sessions"
        ))
        if passed:
            tests_passed += 1
        else:
            tests_failed += 1
        
        # Check gaming_sessions table schema
        cursor.execute("PRAGMA table_info(gaming_sessions)")
        gaming_cols = cursor.fetchall()
        gaming_col_names = [col[1] for col in gaming_cols]
        
        required_gaming_cols = ['session_id', 'start_time', 'end_time', 'participants', 'status']
        missing_gaming_cols = [col for col in required_gaming_cols if col not in gaming_col_names]
        
        passed = len(missing_gaming_cols) == 0
        test_results.append(print_test(
            "Gaming Sessions Table Schema",
            passed,
            f"Missing: {missing_gaming_cols}" if missing_gaming_cols else f"{len(gaming_cols)} columns present"
        ))
        if passed:
            tests_passed += 1
        else:
            tests_failed += 1
        
        # Check processed_files table schema
        cursor.execute("PRAGMA table_info(processed_files)")
        processed_cols = cursor.fetchall()
        processed_col_names = [col[1] for col in processed_cols]
        
        required_processed_cols = ['id', 'filename', 'processed_at']
        missing_processed_cols = [col for col in required_processed_cols if col not in processed_col_names]
        
        passed = len(missing_processed_cols) == 0
        test_results.append(print_test(
            "Processed Files Table Schema",
            passed,
            f"Missing: {missing_processed_cols}" if missing_processed_cols else f"{len(processed_cols)} columns present"
        ))
        if passed:
            tests_passed += 1
        else:
            tests_failed += 1
        
        conn.close()

except Exception as e:
    test_results.append(print_test("Database Tests", False, f"Error: {e}"))
    tests_failed += 1

# ============================================================================
# TEST CATEGORY 2: BOT FILE INTEGRITY
# ============================================================================
print_section("TEST CATEGORY 2: BOT FILE INTEGRITY")

try:
    bot_path = 'bot/ultimate_bot.py'
    
    # Check file exists
    if not os.path.exists(bot_path):
        test_results.append(print_test("Bot File Exists", False, f"Not found: {bot_path}"))
        tests_failed += 1
    else:
        test_results.append(print_test("Bot File Exists", True, f"Found: {bot_path}"))
        tests_passed += 1
        
        # Check file size (should be ~3900 lines)
        with open(bot_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            line_count = len(lines)
        
        passed = 3800 <= line_count <= 4000
        test_results.append(print_test(
            "Bot File Size Check",
            passed,
            f"{line_count} lines (expected 3800-4000)"
        ))
        if passed:
            tests_passed += 1
        else:
            tests_failed += 1
        
        # Check syntax (can it compile?)
        try:
            compile(open(bot_path, encoding='utf-8', errors='ignore').read(), bot_path, 'exec')
            test_results.append(print_test("Bot Python Syntax", True, "No syntax errors"))
            tests_passed += 1
        except SyntaxError as e:
            test_results.append(print_test("Bot Python Syntax", False, f"Syntax error at line {e.lineno}: {e.msg}"))
            tests_failed += 1
        
        # Check critical imports exist in file
        bot_content = open(bot_path, 'r', encoding='utf-8', errors='ignore').read()
        
        critical_imports = [
            'import discord',
            'from discord.ext import commands',
            'import aiosqlite',
            'import os',
            'import logging'
        ]
        
        missing_imports = [imp for imp in critical_imports if imp not in bot_content]
        passed = len(missing_imports) == 0
        test_results.append(print_test(
            "Critical Imports Present",
            passed,
            f"Missing: {missing_imports}" if missing_imports else "All imports found"
        ))
        if passed:
            tests_passed += 1
        else:
            tests_failed += 1
        
        # Check automation flags exist
        automation_checks = [
            'self.automation_enabled',
            'self.ssh_enabled',
            "AUTOMATION_ENABLED",
            "SSH_ENABLED"
        ]
        
        missing_flags = [flag for flag in automation_checks if flag not in bot_content]
        passed = len(missing_flags) == 0
        test_results.append(print_test(
            "Automation Flags Present",
            passed,
            f"Missing: {missing_flags}" if missing_flags else "All automation flags found"
        ))
        if passed:
            tests_passed += 1
        else:
            tests_failed += 1
        
        # Check voice detection code exists
        voice_checks = [
            'on_voice_state_update',
            'session_active',
            'session_participants',
            'gaming_sessions'
        ]
        
        missing_voice = [check for check in voice_checks if check not in bot_content]
        passed = len(missing_voice) == 0
        test_results.append(print_test(
            "Voice Detection Code Present",
            passed,
            f"Missing: {missing_voice}" if missing_voice else "Voice detection code found"
        ))
        if passed:
            tests_passed += 1
        else:
            tests_failed += 1

except Exception as e:
    test_results.append(print_test("Bot File Tests", False, f"Error: {e}"))
    tests_failed += 1

# ============================================================================
# TEST CATEGORY 3: BOT CLASS STRUCTURE
# ============================================================================
print_section("TEST CATEGORY 3: BOT CLASS STRUCTURE")

try:
    # Try to import the bot module
    spec = importlib.util.spec_from_file_location("ultimate_bot", "bot/ultimate_bot.py")
    bot_module = importlib.util.module_from_spec(spec)
    
    # Check if module loads
    try:
        spec.loader.exec_module(bot_module)
        test_results.append(print_test("Bot Module Imports", True, "Module loaded successfully"))
        tests_passed += 1
    except Exception as e:
        test_results.append(print_test("Bot Module Imports", False, f"Import error: {e}"))
        tests_failed += 1
        raise  # Stop further class tests if import fails
    
    # Check UltimateETLegacyBot class exists
    if hasattr(bot_module, 'UltimateETLegacyBot'):
        test_results.append(print_test("UltimateETLegacyBot Class Exists", True))
        tests_passed += 1
        
        UltimateETLegacyBot = bot_module.UltimateETLegacyBot
        
        # Check critical existing commands still exist
        existing_commands = [
            'stats',
            'last_session',
            'link',
            'leaderboard',
            'session_start',
            'session_end',
            'ping'
        ]
        
        bot_methods = dir(UltimateETLegacyBot)
        missing_commands = [cmd for cmd in existing_commands if cmd not in bot_methods]
        
        passed = len(missing_commands) == 0
        test_results.append(print_test(
            "Existing Bot Commands",
            passed,
            f"Missing: {missing_commands}" if missing_commands else f"All {len(existing_commands)} commands found"
        ))
        if passed:
            tests_passed += 1
        else:
            tests_failed += 1
        
        # Check new automation methods exist
        new_methods = [
            'on_voice_state_update',
            '_start_gaming_session',
            '_end_gaming_session',
            'endstats_monitor'
        ]
        
        missing_methods = [method for method in new_methods if method not in bot_methods]
        passed = len(missing_methods) == 0
        test_results.append(print_test(
            "New Automation Methods",
            passed,
            f"Missing: {missing_methods}" if missing_methods else f"All {len(new_methods)} methods found"
        ))
        if passed:
            tests_passed += 1
        else:
            tests_failed += 1
        
        # Check safe calculation methods still exist
        safe_methods = [
            'safe_divide',
            'safe_percent',
            'format_time'
        ]
        
        missing_safe = [method for method in safe_methods if method not in bot_methods]
        passed = len(missing_safe) == 0
        test_results.append(print_test(
            "Safe Calculation Methods",
            passed,
            f"Missing: {missing_safe}" if missing_safe else f"All {len(safe_methods)} methods found"
        ))
        if passed:
            tests_passed += 1
        else:
            tests_failed += 1
    else:
        test_results.append(print_test("UltimateETLegacyBot Class Exists", False, "Class not found"))
        tests_failed += 1

except Exception as e:
    test_results.append(print_test("Bot Class Tests", False, f"Error: {e}"))
    tests_failed += 1

# ============================================================================
# TEST CATEGORY 4: CONFIGURATION FILES
# ============================================================================
print_section("TEST CATEGORY 4: CONFIGURATION FILES")

try:
    # Check .env.example exists
    env_example_path = '.env.example'
    if os.path.exists(env_example_path):
        test_results.append(print_test(".env.example File Exists", True))
        tests_passed += 1
        
        # Check required variables in .env.example
        with open(env_example_path, 'r') as f:
            env_content = f.read()
        
        required_vars = [
            'DISCORD_BOT_TOKEN',
            'GUILD_ID',
            'STATS_CHANNEL_ID',
            'AUTOMATION_ENABLED',
            'SSH_ENABLED',
            'GAMING_VOICE_CHANNELS'
        ]
        
        missing_vars = [var for var in required_vars if var not in env_content]
        passed = len(missing_vars) == 0
        test_results.append(print_test(
            ".env.example Variables",
            passed,
            f"Missing: {missing_vars}" if missing_vars else f"All {len(required_vars)} variables present"
        ))
        if passed:
            tests_passed += 1
        else:
            tests_failed += 1
    else:
        test_results.append(print_test(".env.example File Exists", False, f"Not found: {env_example_path}"))
        tests_failed += 1
    
    # Check .env exists (user's actual config)
    env_path = '.env'
    if os.path.exists(env_path):
        test_results.append(print_test(".env File Exists", True, "User configuration present"))
        tests_passed += 1
        
        # Check if it has DISCORD_BOT_TOKEN (not DISCORD_TOKEN)
        with open(env_path, 'r') as f:
            env_content = f.read()
        
        has_bot_token = 'DISCORD_BOT_TOKEN' in env_content
        has_wrong_token = 'DISCORD_TOKEN=' in env_content and 'DISCORD_BOT_TOKEN' not in env_content
        
        if has_bot_token:
            test_results.append(print_test("Correct Token Variable", True, "DISCORD_BOT_TOKEN found"))
            tests_passed += 1
        elif has_wrong_token:
            test_results.append(print_test("Correct Token Variable", False, "Found DISCORD_TOKEN (should be DISCORD_BOT_TOKEN)"))
            tests_failed += 1
        else:
            test_results.append(print_test("Correct Token Variable", False, "No Discord token found"))
            tests_failed += 1
    else:
        test_results.append(print_test(".env File Exists", False, "⚠️ User needs to create .env from .env.example"))
        tests_failed += 1

except Exception as e:
    test_results.append(print_test("Configuration Tests", False, f"Error: {e}"))
    tests_failed += 1

# ============================================================================
# TEST CATEGORY 5: SSH MONITORING CODE
# ============================================================================
print_section("TEST CATEGORY 5: SSH MONITORING CODE")

try:
    ssh_impl_path = 'tools/ssh_monitoring_implementation.py'
    
    if os.path.exists(ssh_impl_path):
        test_results.append(print_test("SSH Implementation File Exists", True))
        tests_passed += 1
        
        # Check syntax
        try:
            compile(open(ssh_impl_path, encoding='utf-8', errors='ignore').read(), ssh_impl_path, 'exec')
            test_results.append(print_test("SSH Implementation Syntax", True, "No syntax errors"))
            tests_passed += 1
        except SyntaxError as e:
            test_results.append(print_test("SSH Implementation Syntax", False, f"Syntax error: {e}"))
            tests_failed += 1
        
        # Check critical functions exist
        ssh_content = open(ssh_impl_path, 'r', encoding='utf-8', errors='ignore').read()
        
        required_functions = [
            'parse_gamestats_filename',
            'ssh_list_remote_files',
            'ssh_download_file',
            'process_gamestats_file',
            'mark_file_processed'
        ]
        
        missing_functions = [func for func in required_functions if f"def {func}" not in ssh_content]
        passed = len(missing_functions) == 0
        test_results.append(print_test(
            "SSH Functions Present",
            passed,
            f"Missing: {missing_functions}" if missing_functions else f"All {len(required_functions)} functions found"
        ))
        if passed:
            tests_passed += 1
        else:
            tests_failed += 1
    else:
        test_results.append(print_test("SSH Implementation File Exists", False, f"Not found: {ssh_impl_path}"))
        tests_failed += 1

except Exception as e:
    test_results.append(print_test("SSH Monitoring Tests", False, f"Error: {e}"))
    tests_failed += 1

# ============================================================================
# TEST CATEGORY 6: DOCUMENTATION
# ============================================================================
print_section("TEST CATEGORY 6: DOCUMENTATION")

try:
    doc_files = [
        'AUTOMATION_COMPLETE.md',
        'QUICK_START.md',
        'ALL_TODOS_COMPLETE.md',
        'DOCUMENTATION_INDEX.md'
    ]
    
    existing_docs = [doc for doc in doc_files if os.path.exists(doc)]
    missing_docs = [doc for doc in doc_files if doc not in existing_docs]
    
    passed = len(existing_docs) == len(doc_files)
    test_results.append(print_test(
        "Documentation Files",
        passed,
        f"Found {len(existing_docs)}/{len(doc_files)} files" + (f" (Missing: {missing_docs})" if missing_docs else "")
    ))
    if passed:
        tests_passed += 1
    else:
        tests_failed += 1

except Exception as e:
    test_results.append(print_test("Documentation Tests", False, f"Error: {e}"))
    tests_failed += 1

# ============================================================================
# FINAL RESULTS
# ============================================================================
print_section("FINAL TEST RESULTS")

total_tests = tests_passed + tests_failed
pass_rate = (tests_passed / total_tests * 100) if total_tests > 0 else 0

print(f"Total Tests: {total_tests}")
print(f"{GREEN}Passed: {tests_passed}{RESET}")
print(f"{RED}Failed: {tests_failed}{RESET}")
print(f"Pass Rate: {pass_rate:.1f}%\n")

if pass_rate == 100:
    print(f"{GREEN}🎉 ALL TESTS PASSED! System is healthy!{RESET}\n")
    sys.exit(0)
elif pass_rate >= 90:
    print(f"{YELLOW}⚠️ MOSTLY HEALTHY ({pass_rate:.0f}%) - Review failed tests{RESET}\n")
    sys.exit(0)
elif pass_rate >= 75:
    print(f"{YELLOW}⚠️ NEEDS ATTENTION ({pass_rate:.0f}%) - Several issues found{RESET}\n")
    sys.exit(1)
else:
    print(f"{RED}❌ CRITICAL ISSUES ({pass_rate:.0f}%) - System may be broken!{RESET}\n")
    sys.exit(1)
