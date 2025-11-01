"""
Comprehensive Automation System Test Suite
Tests all components: database, SSH, parsing, voice detection, Discord integration
"""
import sys
import os
import sqlite3
import asyncio
import discord
from datetime import datetime


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'


def print_test(name, passed, details=''):
    """Print test result"""
    symbol = f"{Colors.GREEN}✅{Colors.END}" if passed else f"{Colors.RED}❌{Colors.END}"
    status = f"{Colors.GREEN}PASS{Colors.END}" if passed else f"{Colors.RED}FAIL{Colors.END}"
    print(f"{symbol} TEST: {name}")
    print(f"   Status: {status}")
    if details:
        print(f"   {details}")
    print()


def test_database_connection():
    """Test 1: Database exists and is accessible"""
    print(f"\n{Colors.BLUE}═══ TEST 1: Database Connection ═══{Colors.END}")
    
    db_path = 'etlegacy_production.db'
    try:
        if not os.path.exists(db_path):
            print_test("Database file exists", False, f"File not found: {db_path}")
            return False
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
        table_count = cursor.fetchone()[0]
        conn.close()
        
        print_test("Database connection", True, f"Found {table_count} tables")
        return True
        
    except Exception as e:
        print_test("Database connection", False, str(e))
        return False


def test_required_tables():
    """Test 2: All required tables exist"""
    print(f"\n{Colors.BLUE}═══ TEST 2: Required Tables ═══{Colors.END}")
    
    required_tables = {
        'sessions': 'Game session records',
        'player_comprehensive_stats': 'Player statistics (53 columns)',
        'weapon_comprehensive_stats': 'Weapon usage stats',
        'player_links': 'Discord to GUID linking',
        'player_aliases': 'Player name variations',
        'gaming_sessions': 'Voice channel sessions',
        'processed_files': 'Imported file tracking'
    }
    
    try:
        conn = sqlite3.connect('etlegacy_production.db')
        cursor = conn.cursor()
        
        all_passed = True
        for table, description in required_tables.items():
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,)
            )
            exists = cursor.fetchone() is not None
            
            if exists:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print_test(
                    f"Table: {table}",
                    True,
                    f"{description} | {count} records"
                )
            else:
                print_test(f"Table: {table}", False, "Table not found")
                all_passed = False
        
        conn.close()
        return all_passed
        
    except Exception as e:
        print_test("Table verification", False, str(e))
        return False


def test_unified_schema():
    """Test 3: player_comprehensive_stats has correct schema (53 columns)"""
    print(f"\n{Colors.BLUE}═══ TEST 3: Unified Schema Validation ═══{Colors.END}")
    
    try:
        conn = sqlite3.connect('etlegacy_production.db')
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA table_info(player_comprehensive_stats)")
        columns = cursor.fetchall()
        column_count = len(columns)
        
        # Check for key objective stats columns
        column_names = {col[1] for col in columns}
        objective_columns = {
            'kill_assists', 'revives_given', 'times_revived',
            'dynamites_planted', 'dynamites_defused',
            'objectives_completed', 'objectives_destroyed'
        }
        
        has_objectives = objective_columns.issubset(column_names)
        
        conn.close()
        
        if column_count == 53 and has_objectives:
            print_test(
                "Schema validation",
                True,
                f"53 columns with all objective stats"
            )
            return True
        else:
            print_test(
                "Schema validation",
                False,
                f"Expected 53 columns with objectives, got {column_count}"
            )
            return False
        
    except Exception as e:
        print_test("Schema validation", False, str(e))
        return False


def test_env_configuration():
    """Test 4: Check .env file exists and has required vars"""
    print(f"\n{Colors.BLUE}═══ TEST 4: Configuration File ═══{Colors.END}")
    
    env_file = '.env'
    env_example = '.env.example'
    
    # Check .env exists
    if not os.path.exists(env_file):
        print_test(
            ".env file exists",
            False,
            f"Create {env_file} from {env_example}"
        )
        return False
    
    # Read .env
    try:
        with open(env_file, 'r') as f:
            env_content = f.read()
        
        required_vars = [
            'DISCORD_TOKEN',
            'GUILD_ID',
            'STATS_CHANNEL_ID',
            'DATABASE_PATH'
        ]
        
        automation_vars = [
            'AUTOMATION_ENABLED',
            'SSH_ENABLED',
            'GAMING_VOICE_CHANNELS'
        ]
        
        all_found = True
        for var in required_vars:
            if var in env_content:
                print_test(f"Config: {var}", True, "Present")
            else:
                print_test(f"Config: {var}", False, "Missing")
                all_found = False
        
        # Check automation vars (optional but recommended)
        automation_count = sum(1 for var in automation_vars if var in env_content)
        print(f"\n{Colors.YELLOW}ℹ️  Automation vars: {automation_count}/{len(automation_vars)} configured{Colors.END}")
        
        return all_found
        
    except Exception as e:
        print_test("Configuration file", False, str(e))
        return False


def test_bot_file_syntax():
    """Test 5: Bot file compiles without syntax errors"""
    print(f"\n{Colors.BLUE}═══ TEST 5: Bot File Syntax ═══{Colors.END}")
    
    bot_file = 'bot/ultimate_bot.py'
    
    try:
        with open(bot_file, 'r', encoding='utf-8', errors='ignore') as f:
            code = f.read()
        
        compile(code, bot_file, 'exec')
        
        print_test("Bot syntax check", True, f"{bot_file} compiles successfully")
        return True
        
    except SyntaxError as e:
        print_test(
            "Bot syntax check",
            False,
            f"Line {e.lineno}: {e.msg}"
        )
        return False
    except Exception as e:
        print_test("Bot syntax check", False, str(e))
        return False


def test_ssh_monitoring_code():
    """Test 6: SSH monitoring functions are importable"""
    print(f"\n{Colors.BLUE}═══ TEST 6: SSH Monitoring Code ═══{Colors.END}")
    
    try:
        sys.path.insert(0, 'tools')
        from ssh_monitoring_implementation import (
            parse_gamestats_filename,
            ssh_list_remote_files,
            ssh_download_file,
            process_gamestats_file,
            mark_file_processed,
            get_processed_files
        )
        
        # Test filename parser
        test_filename = "2025-10-04-153045-erdenberg_t2-round-2.txt"
        result = parse_gamestats_filename(test_filename)
        
        if result and result['map_name'] == 'erdenberg_t2' and result['round_number'] == 2:
            print_test(
                "parse_gamestats_filename()",
                True,
                f"Parsed: {test_filename} → {result['map_name']} R{result['round_number']}"
            )
            return True
        else:
            print_test("parse_gamestats_filename()", False, "Parser returned unexpected result")
            return False
        
    except ImportError as e:
        print_test("SSH monitoring imports", False, f"Import error: {e}")
        return False
    except Exception as e:
        print_test("SSH monitoring functions", False, str(e))
        return False


def test_automation_flags():
    """Test 7: Check automation flags in bot code"""
    print(f"\n{Colors.BLUE}═══ TEST 7: Automation Flags ═══{Colors.END}")
    
    try:
        with open('bot/ultimate_bot.py', 'r', encoding='utf-8', errors='ignore') as f:
            bot_code = f.read()
        
        checks = {
            'automation_enabled flag': 'self.automation_enabled' in bot_code,
            'ssh_enabled flag': 'self.ssh_enabled' in bot_code,
            'on_voice_state_update': 'async def on_voice_state_update' in bot_code,
            'endstats_monitor task': '@tasks.loop(seconds=30)' in bot_code,
            'gaming_sessions integration': 'gaming_sessions' in bot_code
        }
        
        all_passed = True
        for check_name, passed in checks.items():
            print_test(check_name, passed)
            if not passed:
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        print_test("Automation flags check", False, str(e))
        return False


def test_voice_detection_setup():
    """Test 8: Voice channel detection components"""
    print(f"\n{Colors.BLUE}═══ TEST 8: Voice Detection Setup ═══{Colors.END}")
    
    try:
        conn = sqlite3.connect('etlegacy_production.db')
        cursor = conn.cursor()
        
        # Check gaming_sessions table
        cursor.execute("PRAGMA table_info(gaming_sessions)")
        columns = cursor.fetchall()
        
        if len(columns) >= 10:
            print_test(
                "gaming_sessions table",
                True,
                f"{len(columns)} columns configured"
            )
            
            # Check if table is ready for use
            cursor.execute("SELECT COUNT(*) FROM gaming_sessions")
            count = cursor.fetchone()[0]
            print(f"   {Colors.YELLOW}ℹ️  Current sessions tracked: {count}{Colors.END}\n")
            
            conn.close()
            return True
        else:
            print_test("gaming_sessions table", False, f"Only {len(columns)} columns")
            conn.close()
            return False
        
    except Exception as e:
        print_test("Voice detection setup", False, str(e))
        return False


def test_processed_files_table():
    """Test 9: processed_files table for duplicate prevention"""
    print(f"\n{Colors.BLUE}═══ TEST 9: Processed Files Tracking ═══{Colors.END}")
    
    try:
        conn = sqlite3.connect('etlegacy_production.db')
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA table_info(processed_files)")
        columns = cursor.fetchall()
        column_names = {col[1] for col in columns}
        
        required = {'filename', 'processed_at'}
        
        if required.issubset(column_names):
            cursor.execute("SELECT COUNT(*) FROM processed_files")
            count = cursor.fetchone()[0]
            
            print_test(
                "processed_files table",
                True,
                f"{len(columns)} columns | {count} files tracked"
            )
            conn.close()
            return True
        else:
            print_test("processed_files table", False, f"Missing columns: {required - column_names}")
            conn.close()
            return False
        
    except Exception as e:
        print_test("processed_files table", False, str(e))
        return False


def run_all_tests():
    """Run complete test suite"""
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}🧪 AUTOMATION SYSTEM TEST SUITE{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"Testing Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tests = [
        ("Database Connection", test_database_connection),
        ("Required Tables", test_required_tables),
        ("Unified Schema (53 cols)", test_unified_schema),
        ("Configuration File", test_env_configuration),
        ("Bot File Syntax", test_bot_file_syntax),
        ("SSH Monitoring Code", test_ssh_monitoring_code),
        ("Automation Flags", test_automation_flags),
        ("Voice Detection Setup", test_voice_detection_setup),
        ("Processed Files Table", test_processed_files_table)
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n{Colors.RED}❌ Test crashed: {name}{Colors.END}")
            print(f"   Error: {e}")
            results.append((name, False))
    
    # Summary
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}📊 TEST SUMMARY{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}\n")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    percentage = (passed / total) * 100 if total > 0 else 0
    
    for name, result in results:
        status = f"{Colors.GREEN}✅ PASS{Colors.END}" if result else f"{Colors.RED}❌ FAIL{Colors.END}"
        print(f"  {status}  {name}")
    
    print(f"\n{Colors.BLUE}{'─'*60}{Colors.END}")
    
    if passed == total:
        print(f"{Colors.GREEN}🎉 ALL TESTS PASSED! ({passed}/{total}) - {percentage:.0f}%{Colors.END}")
        print(f"\n{Colors.GREEN}✅ System is ready for automation!{Colors.END}")
        print(f"\n{Colors.YELLOW}Next steps:{Colors.END}")
        print(f"  1. Set AUTOMATION_ENABLED=true in .env")
        print(f"  2. Set SSH_ENABLED=true in .env")
        print(f"  3. Configure GAMING_VOICE_CHANNELS")
        print(f"  4. Start bot: python bot/ultimate_bot.py")
        return 0
    else:
        failed = total - passed
        print(f"{Colors.RED}❌ {failed} TEST(S) FAILED ({passed}/{total}) - {percentage:.0f}%{Colors.END}")
        print(f"\n{Colors.YELLOW}⚠️  Fix failed tests before enabling automation{Colors.END}")
        return 1


if __name__ == '__main__':
    exit_code = run_all_tests()
    sys.exit(exit_code)
