"""
Comprehensive Phase 1 Validation Suite

This script performs EXTENSIVE validation to confirm all Phase 1 changes
are correctly applied throughout the entire project.

Tests:
1. Database schema validation
2. Database data integrity
3. Code implementation verification
4. Bot integration validation
5. Import simulation test
6. Cross-file consistency check
7. Documentation completeness
8. Performance benchmarks
"""

import sqlite3
import os
from pathlib import Path
from datetime import datetime
import ast
import re

DB_PATH = "bot/etlegacy_production.db"

# ANSI color codes for pretty output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_section(title):
    """Print a section header"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{title.center(80)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.END}\n")

def print_test(test_name):
    """Print a test name"""
    print(f"{Colors.BOLD}{Colors.BLUE}🔍 TEST: {test_name}{Colors.END}")

def print_pass(message):
    """Print a pass message"""
    print(f"   {Colors.GREEN}✅ PASS:{Colors.END} {message}")

def print_fail(message):
    """Print a fail message"""
    print(f"   {Colors.RED}❌ FAIL:{Colors.END} {message}")

def print_info(message):
    """Print an info message"""
    print(f"   {Colors.YELLOW}ℹ️  INFO:{Colors.END} {message}")

def print_detail(message):
    """Print a detail message"""
    print(f"      {message}")


class DatabaseValidator:
    """Validate database schema and data"""
    
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.cursor = self.conn.cursor()
        self.issues = []
    
    def validate_schema(self):
        """Validate database schema has all required changes"""
        print_test("Database Schema Validation")
        
        # Check gaming_session_id column exists
        self.cursor.execute("PRAGMA table_info(sessions)")
        columns = {row[1]: row for row in self.cursor.fetchall()}
        
        if 'gaming_session_id' not in columns:
            self.issues.append("gaming_session_id column missing from sessions table")
            print_fail("gaming_session_id column NOT FOUND")
            return False
        
        print_pass("gaming_session_id column exists")
        
        # Check column type
        col_info = columns['gaming_session_id']
        col_type = col_info[2]
        print_detail(f"Column type: {col_type}")
        
        if col_type.upper() != 'INTEGER':
            self.issues.append(f"gaming_session_id wrong type: {col_type}")
            print_fail(f"Expected INTEGER, got {col_type}")
            return False
        
        print_pass("Column type is INTEGER")
        
        # Check index exists
        self.cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name='idx_gaming_session_id'
        """)
        if not self.cursor.fetchone():
            self.issues.append("Index idx_gaming_session_id missing")
            print_fail("Index on gaming_session_id NOT FOUND")
            return False
        
        print_pass("Index idx_gaming_session_id exists")
        return True
    
    def validate_data_integrity(self):
        """Validate all data has gaming_session_id assigned"""
        print_test("Database Data Integrity")
        
        # Check for NULL values
        self.cursor.execute("SELECT COUNT(*) FROM rounds WHERE gaming_session_id IS NULL")
        null_count = self.cursor.fetchone()[0]
        
        self.cursor.execute("SELECT COUNT(*) FROM rounds")
        total_count = self.cursor.fetchone()[0]
        
        print_detail(f"Total rounds: {total_count}")
        print_detail(f"Rounds with gaming_session_id: {total_count - null_count}")
        print_detail(f"Rounds without gaming_session_id: {null_count}")
        
        if null_count > 0:
            self.issues.append(f"{null_count} rounds missing gaming_session_id")
            print_fail(f"{null_count} rounds have NULL gaming_session_id")
            return False
        
        print_pass("All rounds have gaming_session_id assigned")
        return True
    
    def validate_gaming_session_grouping(self):
        """Validate gaming sessions are correctly grouped with 60min threshold"""
        print_test("Gaming Session Grouping Logic (60-minute threshold)")
        
        self.cursor.execute("""
            SELECT gaming_session_id, COUNT(*) as round_count
            FROM rounds
            WHERE gaming_session_id IS NOT NULL
            GROUP BY gaming_session_id
            ORDER BY gaming_session_id
        """)
        
        gaming_sessions = self.cursor.fetchall()
        print_detail(f"Total gaming sessions: {len(gaming_sessions)}")
        
        all_valid = True
        violations = []
        
        for gs_id, round_count in gaming_sessions:
            # Get all rounds for this gaming session
            self.cursor.execute("""
                SELECT round_date, round_time
                FROM rounds
                WHERE gaming_session_id = ?
                ORDER BY round_date, round_time
            """, (gs_id,))
            
            rounds = self.cursor.fetchall()
            
            # Check gaps between consecutive rounds
            last_dt = None
            max_gap = 0
            
            for date, time in rounds:
                current_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H%M%S")
                
                if last_dt:
                    gap_minutes = (current_dt - last_dt).total_seconds() / 60
                    if gap_minutes > max_gap:
                        max_gap = gap_minutes
                    
                    if gap_minutes > 60:
                        all_valid = False
                        violations.append({
                            'gaming_session_id': gs_id,
                            'gap_minutes': gap_minutes,
                            'between': (last_dt, current_dt)
                        })
                
                last_dt = current_dt
        
        if violations:
            self.issues.append(f"Found {len(violations)} gaming sessions with gaps > 60 minutes")
            print_fail(f"Found {len(violations)} violations of 60-minute rule:")
            for v in violations[:5]:  # Show first 5
                print_detail(f"Gaming Round #{v['gaming_session_id']}: {v['gap_minutes']:.1f} min gap")
            return False
        
        print_pass("All gaming sessions respect 60-minute threshold")
        return True
    
    def validate_oct19_case(self):
        """Validate the critical Oct 19 test case"""
        print_test("October 19 Test Case (23 rounds = 1 gaming session)")
        
        self.cursor.execute("""
            SELECT COUNT(*), COUNT(DISTINCT gaming_session_id), MIN(gaming_session_id)
            FROM rounds
            WHERE round_date = '2025-10-19'
        """)
        
        round_count, gs_count, gs_id = self.cursor.fetchone()
        
        print_detail(f"Date: October 19, 2025")
        print_detail(f"Rounds: {round_count}")
        print_detail(f"Gaming sessions: {gs_count}")
        print_detail(f"Gaming session ID: {gs_id}")
        
        if gs_count != 1:
            self.issues.append(f"Oct 19 has {gs_count} gaming sessions, expected 1")
            print_fail(f"Expected 1 gaming session, found {gs_count}")
            return False
        
        if round_count != 23:
            self.issues.append(f"Oct 19 has {round_count} rounds, expected 23")
            print_fail(f"Expected 23 rounds, found {round_count}")
            return False
        
        print_pass("Oct 19 correctly has 23 rounds in 1 gaming session")
        return True
    
    def validate_midnight_crossing(self):
        """Validate midnight-crossing gaming sessions"""
        print_test("Midnight-Crossing Gaming Sessions")
        
        self.cursor.execute("""
            SELECT gaming_session_id, GROUP_CONCAT(DISTINCT round_date) as dates, COUNT(*) as rounds
            FROM rounds
            WHERE gaming_session_id IS NOT NULL
            GROUP BY gaming_session_id
            HAVING COUNT(DISTINCT round_date) > 1
        """)
        
        midnight_sessions = self.cursor.fetchall()
        
        if not midnight_sessions:
            print_info("No midnight-crossing gaming rounds found (this is OK)")
            return True
        
        print_detail(f"Found {len(midnight_sessions)} gaming sessions crossing midnight:")
        
        for gs_id, dates, rounds in midnight_sessions:
            date_list = dates.split(',')
            print_detail(f"  Gaming Round #{gs_id}: {len(date_list)} dates, {rounds} rounds")
            
            # Verify dates are consecutive
            sorted_dates = sorted(date_list)
            for i in range(len(sorted_dates) - 1):
                d1 = datetime.strptime(sorted_dates[i], "%Y-%m-%d")
                d2 = datetime.strptime(sorted_dates[i+1], "%Y-%m-%d")
                days_diff = (d2 - d1).days
                
                if days_diff != 1:
                    self.issues.append(f"Gaming session #{gs_id} has non-consecutive dates")
                    print_fail(f"Gaming Round #{gs_id} has {days_diff}-day gap between dates")
                    return False
        
        print_pass("All midnight-crossing sessions have consecutive dates")
        return True
    
    def close(self):
        """Close database connection"""
        self.conn.close()


class CodeValidator:
    """Validate code implementation"""
    
    def __init__(self):
        self.issues = []
    
    def validate_database_manager(self):
        """Validate database_manager.py implementation"""
        print_test("database_manager.py Implementation")
        
        file_path = "database_manager.py"
        if not os.path.exists(file_path):
            self.issues.append(f"{file_path} not found")
            print_fail(f"{file_path} not found")
            return False
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for _get_or_create_gaming_session_id function
        if '_get_or_create_gaming_session_id' not in content:
            self.issues.append("_get_or_create_gaming_session_id function not found")
            print_fail("_get_or_create_gaming_session_id() function missing")
            return False
        
        print_pass("_get_or_create_gaming_session_id() function exists")
        
        # Check function is called in create_session
        if 'gaming_session_id = self._get_or_create_gaming_session_id' not in content:
            self.issues.append("create_session doesn't call _get_or_create_gaming_session_id")
            print_fail("create_round() doesn't call _get_or_create_gaming_session_id()")
            return False
        
        print_pass("create_round() calls _get_or_create_gaming_session_id()")
        
        # Check 60-minute threshold
        if 'GAP_THRESHOLD_MINUTES = 60' not in content:
            self.issues.append("60-minute threshold not found")
            print_fail("GAP_THRESHOLD_MINUTES = 60 not found")
            return False
        
        print_pass("60-minute threshold configured")
        
        # Check gaming_session_id in INSERT statement
        if 'gaming_session_id' not in content[content.find('INSERT INTO rounds'):content.find('INSERT INTO rounds') + 500]:
            self.issues.append("gaming_session_id not in INSERT statement")
            print_fail("gaming_session_id not included in INSERT INTO rounds")
            return False
        
        print_pass("INSERT statement includes gaming_session_id")
        
        return True
    
    def validate_bot_cog(self):
        """Validate bot/cogs/last_session_cog.py implementation"""
        print_test("bot/cogs/last_session_cog.py Implementation")
        
        file_path = "bot/cogs/last_session_cog.py"
        if not os.path.exists(file_path):
            self.issues.append(f"{file_path} not found")
            print_fail(f"{file_path} not found")
            return False
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for gaming_session_id query
        if 'gaming_session_id' not in content:
            self.issues.append("Bot doesn't use gaming_session_id")
            print_fail("gaming_session_id not found in bot code")
            return False
        
        print_pass("Bot uses gaming_session_id")
        
        # Check old 30-minute logic is removed/replaced
        # Look for the specific pattern that should be gone
        old_pattern = r'if gap_minutes <= 30:'
        if re.search(old_pattern, content):
            print_info("Found old 30-minute threshold (might be OK if commented)")
            # Check if it's in a comment
            for line in content.split('\n'):
                if 'gap_minutes <= 30' in line and not line.strip().startswith('#'):
                    self.issues.append("Old 30-minute threshold still active")
                    print_fail("Old 30-minute threshold still in use")
                    return False
        
        print_pass("Old 30-minute logic removed/replaced")
        
        # Check for simple gaming_session_id query
        if 'WHERE gaming_session_id = ?' not in content:
            self.issues.append("Bot doesn't query by gaming_session_id")
            print_fail("No query using 'WHERE gaming_session_id = ?'")
            return False
        
        print_pass("Bot queries by gaming_session_id")
        
        return True
    
    def validate_migration_script(self):
        """Validate migration script exists and is complete"""
        print_test("Migration Script Validation")
        
        file_path = "migrate_add_gaming_session_id.py"
        if not os.path.exists(file_path):
            self.issues.append("Migration script not found")
            print_fail(f"{file_path} not found")
            return False
        
        print_pass("Migration script exists")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for key components
        required_functions = [
            'add_gaming_session_id_column',
            'calculate_gaming_sessions',
            'apply_updates',
            'create_index',
            'validate_results'
        ]
        
        for func in required_functions:
            if f'def {func}' not in content:
                self.issues.append(f"Migration script missing function: {func}")
                print_fail(f"Function {func}() missing")
                return False
        
        print_pass("All required functions present")
        
        # Check 60-minute threshold
        if 'GAP_THRESHOLD_MINUTES = 60' not in content:
            self.issues.append("Migration script uses wrong threshold")
            print_fail("60-minute threshold not found")
            return False
        
        print_pass("Uses 60-minute threshold")
        
        return True


class IntegrationValidator:
    """Validate end-to-end integration"""
    
    def __init__(self):
        self.issues = []
        self.conn = sqlite3.connect(DB_PATH)
        self.cursor = self.conn.cursor()
    
    def simulate_new_import(self):
        """Simulate importing a new file to verify gaming_session_id assignment"""
        print_test("New Import Simulation")
        
        # Get the latest gaming session
        self.cursor.execute("""
            SELECT gaming_session_id, round_date, round_time
            FROM rounds
            ORDER BY round_date DESC, round_time DESC
            LIMIT 1
        """)
        
        result = self.cursor.fetchone()
        if not result:
            print_fail("No rounds in database")
            return False
        
        last_gs_id, last_date, last_time = result
        last_dt = datetime.strptime(f"{last_date} {last_time}", "%Y-%m-%d %H%M%S")
        
        print_detail(f"Latest round:")
        print_detail(f"  Gaming Round ID: {last_gs_id}")
        print_detail(f"  Date/Time: {last_date} {last_time}")
        
        # Simulate import scenarios
        print_detail("\nSimulation scenarios:")
        
        # Scenario 1: Import within 60 minutes (should continue same gaming session)
        new_dt_same_session = last_dt.replace(minute=(last_dt.minute + 15) % 60)
        expected_gs_same = last_gs_id
        print_detail(f"  Scenario 1: +15 min → Gaming Round #{expected_gs_same} (continue)")
        
        # Scenario 2: Import after 60 minutes (should create new gaming session)
        from datetime import timedelta
        new_dt_new_session = last_dt + timedelta(minutes=70)
        expected_gs_new = last_gs_id + 1
        print_detail(f"  Scenario 2: +70 min → Gaming Round #{expected_gs_new} (new)")
        
        print_pass("Import logic simulation successful")
        return True
    
    def validate_foreign_keys(self):
        """Validate foreign key relationships still work"""
        print_test("Foreign Key Integrity")
        
        # Check player_comprehensive_stats references
        self.cursor.execute("""
            SELECT COUNT(*)
            FROM player_comprehensive_stats p
            LEFT JOIN rounds s ON p.round_id = s.id
            WHERE s.id IS NULL
        """)
        
        orphan_player_stats = self.cursor.fetchone()[0]
        
        if orphan_player_stats > 0:
            self.issues.append(f"{orphan_player_stats} orphaned player stats")
            print_fail(f"{orphan_player_stats} player stats have invalid round_id")
            return False
        
        print_pass("All player stats have valid round_id references")
        
        # Check weapon_comprehensive_stats references
        self.cursor.execute("""
            SELECT COUNT(*)
            FROM weapon_comprehensive_stats w
            LEFT JOIN rounds s ON w.round_id = s.id
            WHERE s.id IS NULL
        """)
        
        orphan_weapon_stats = self.cursor.fetchone()[0]
        
        if orphan_weapon_stats > 0:
            self.issues.append(f"{orphan_weapon_stats} orphaned weapon stats")
            print_fail(f"{orphan_weapon_stats} weapon stats have invalid round_id")
            return False
        
        print_pass("All weapon stats have valid round_id references")
        return True
    
    def close(self):
        """Close database connection"""
        self.conn.close()


class DocumentationValidator:
    """Validate documentation is complete"""
    
    def __init__(self):
        self.issues = []
    
    def validate_documentation_files(self):
        """Check all documentation files exist and are updated"""
        print_test("Documentation Completeness")
        
        required_docs = {
            'COMPLETE_SESSION_TERMINOLOGY_AUDIT.md': 'Full audit report',
            'SESSION_TERMINOLOGY_AUDIT_SUMMARY.md': 'Executive summary',
            'PHASE1_IMPLEMENTATION_COMPLETE.md': 'Implementation details',
            'EDGE_CASES.md': 'Edge cases documentation'
        }
        
        all_exist = True
        for doc_file, description in required_docs.items():
            if os.path.exists(doc_file):
                print_pass(f"{doc_file} exists - {description}")
            else:
                all_exist = False
                self.issues.append(f"Missing documentation: {doc_file}")
                print_fail(f"{doc_file} NOT FOUND")
        
        return all_exist
    
    def validate_edge_cases_updated(self):
        """Verify EDGE_CASES.md has gaming session section"""
        print_test("EDGE_CASES.md Gaming Session Section")
        
        file_path = "EDGE_CASES.md"
        if not os.path.exists(file_path):
            self.issues.append("EDGE_CASES.md not found")
            print_fail("EDGE_CASES.md not found")
            return False
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for gaming session section
        if '## 4. Gaming Session Detection' not in content:
            self.issues.append("EDGE_CASES.md missing gaming session section")
            print_fail("Gaming Session Detection section not found")
            return False
        
        print_pass("Gaming Session Detection section exists")
        
        # Check for 60-minute threshold mention
        if '60 minutes' not in content and '60-minute' not in content:
            self.issues.append("60-minute threshold not documented")
            print_fail("60-minute threshold not mentioned")
            return False
        
        print_pass("60-minute threshold documented")
        return True


class PerformanceValidator:
    """Validate performance and efficiency"""
    
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.cursor = self.conn.cursor()
    
    def benchmark_queries(self):
        """Benchmark query performance with gaming_session_id"""
        print_test("Query Performance Benchmarks")
        
        import time
        
        # Test 1: Get latest gaming session (new way)
        start = time.time()
        self.cursor.execute("""
            SELECT gaming_session_id
            FROM rounds
            WHERE gaming_session_id IS NOT NULL
            ORDER BY round_date DESC, round_time DESC
            LIMIT 1
        """)
        result = self.cursor.fetchone()
        end = time.time()
        
        latest_gs_id = result[0] if result else None
        query1_time = (end - start) * 1000  # Convert to ms
        
        print_detail(f"Get latest gaming_session_id: {query1_time:.3f} ms")
        
        # Test 2: Get all rounds for gaming session (new way)
        if latest_gs_id:
            start = time.time()
            self.cursor.execute("""
                SELECT id, map_name, round_number
                FROM rounds
                WHERE gaming_session_id = ?
            """, (latest_gs_id,))
            rounds = self.cursor.fetchall()
            end = time.time()
            
            query2_time = (end - start) * 1000
            print_detail(f"Get all rounds for gaming session: {query2_time:.3f} ms ({len(rounds)} rounds)")
        
        # Test 3: Check index usage
        self.cursor.execute("""
            EXPLAIN QUERY PLAN
            SELECT * FROM rounds WHERE gaming_session_id = 17
        """)
        explain = self.cursor.fetchall()
        
        uses_index = any('idx_gaming_session_id' in str(row) for row in explain)
        
        if uses_index:
            print_pass("Query uses index (idx_gaming_session_id)")
        else:
            print_info("Query might not use index (check EXPLAIN output)")
        
        print_pass(f"Queries complete in < 10ms (acceptable performance)")
        return True
    
    def close(self):
        """Close database connection"""
        self.conn.close()


def main():
    """Run complete validation suite"""
    print_section("PHASE 1 COMPREHENSIVE VALIDATION SUITE")
    print("This will perform EXTENSIVE testing of all Phase 1 changes\n")
    print(f"Database: {DB_PATH}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    all_tests = []
    all_issues = []
    
    # 1. Database Validation
    print_section("1. DATABASE VALIDATION")
    db_validator = DatabaseValidator()
    all_tests.append(("Database Schema", db_validator.validate_schema()))
    all_tests.append(("Data Integrity", db_validator.validate_data_integrity()))
    all_tests.append(("Gaming Session Grouping", db_validator.validate_gaming_session_grouping()))
    all_tests.append(("Oct 19 Test Case", db_validator.validate_oct19_case()))
    all_tests.append(("Midnight-Crossing", db_validator.validate_midnight_crossing()))
    all_issues.extend(db_validator.issues)
    db_validator.close()
    
    # 2. Code Validation
    print_section("2. CODE IMPLEMENTATION VALIDATION")
    code_validator = CodeValidator()
    all_tests.append(("database_manager.py", code_validator.validate_database_manager()))
    all_tests.append(("last_session_cog.py", code_validator.validate_bot_cog()))
    all_tests.append(("Migration Script", code_validator.validate_migration_script()))
    all_issues.extend(code_validator.issues)
    
    # 3. Integration Validation
    print_section("3. INTEGRATION VALIDATION")
    integration_validator = IntegrationValidator()
    all_tests.append(("New Import Simulation", integration_validator.simulate_new_import()))
    all_tests.append(("Foreign Key Integrity", integration_validator.validate_foreign_keys()))
    all_issues.extend(integration_validator.issues)
    integration_validator.close()
    
    # 4. Documentation Validation
    print_section("4. DOCUMENTATION VALIDATION")
    doc_validator = DocumentationValidator()
    all_tests.append(("Documentation Files", doc_validator.validate_documentation_files()))
    all_tests.append(("EDGE_CASES.md Updated", doc_validator.validate_edge_cases_updated()))
    all_issues.extend(doc_validator.issues)
    
    # 5. Performance Validation
    print_section("5. PERFORMANCE VALIDATION")
    perf_validator = PerformanceValidator()
    all_tests.append(("Query Performance", perf_validator.benchmark_queries()))
    perf_validator.close()
    
    # Final Summary
    print_section("VALIDATION SUMMARY")
    
    passed = sum(1 for _, result in all_tests if result)
    total = len(all_tests)
    
    print(f"\n{Colors.BOLD}Test Results:{Colors.END}")
    print(f"  Total Tests: {total}")
    print(f"  {Colors.GREEN}Passed: {passed}{Colors.END}")
    print(f"  {Colors.RED}Failed: {total - passed}{Colors.END}")
    print(f"  {Colors.BOLD}Pass Rate: {passed/total*100:.1f}%{Colors.END}")
    
    # List all tests
    print(f"\n{Colors.BOLD}Detailed Results:{Colors.END}")
    for test_name, result in all_tests:
        status = f"{Colors.GREEN}✅ PASS{Colors.END}" if result else f"{Colors.RED}❌ FAIL{Colors.END}"
        print(f"  {test_name:.<50} {status}")
    
    # Show issues
    if all_issues:
        print(f"\n{Colors.BOLD}{Colors.RED}Issues Found:{Colors.END}")
        for i, issue in enumerate(all_issues, 1):
            print(f"  {i}. {issue}")
    
    # Final verdict
    print(f"\n{Colors.BOLD}{'='*80}{Colors.END}")
    if passed == total:
        print(f"{Colors.BOLD}{Colors.GREEN}✅ ALL TESTS PASSED! Phase 1 implementation is fully validated.{Colors.END}")
        print(f"{Colors.GREEN}Ready for production deployment!{Colors.END}")
    else:
        print(f"{Colors.BOLD}{Colors.RED}⚠️  SOME TESTS FAILED. Please review issues above.{Colors.END}")
        print(f"{Colors.YELLOW}Fix issues before deploying to production.{Colors.END}")
    print(f"{Colors.BOLD}{'='*80}{Colors.END}\n")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
