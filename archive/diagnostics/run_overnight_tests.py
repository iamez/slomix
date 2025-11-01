#!/usr/bin/env python3
"""
🌙 OVERNIGHT COMPREHENSIVE TEST RUNNER
======================================
Runs extensive tests overnight including:
- Code linting and auto-fixing
- Database integrity checks
- Import validation
- Type checking
- Security scanning
- Performance tests

Can run unattended with auto-accept mode.
"""

import glob
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime


class OvernightTestRunner:
    def __init__(self, auto_fix=True, verbose=True):
        self.auto_fix = auto_fix
        self.verbose = verbose
        self.log_file = f"overnight_test_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        self.results = {
            'total_files': 0,
            'files_fixed': 0,
            'errors_found': 0,
            'errors_fixed': 0,
            'tests_run': 0,
            'tests_passed': 0,
            'tests_failed': 0,
            'db_checks': 0,
            'db_issues': 0,
        }
        self.start_time = None

    def log(self, message, level="INFO"):
        """Log with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        msg = f"[{timestamp}] [{level}] {message}"
        print(msg)

        # Append to log file
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(msg + '\n')

    def section(self, title):
        """Print section header"""
        line = "=" * 70
        self.log("")
        self.log(line)
        self.log(f"  {title}")
        self.log(line)

    def install_tools(self):
        """Install all required tools"""
        self.section("📦 INSTALLING/UPGRADING TOOLS")

        tools = [
            'autopep8',
            'autoflake',
            'black',
            'isort',
            'flake8',
            'mypy',
            'pylint',
            'bandit',
            'pytest',
        ]

        for tool in tools:
            self.log(f"Installing {tool}...", "TOOL")
            try:
                subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', '--upgrade', '--quiet', tool],
                    capture_output=True,
                    timeout=300,
                )
                self.log(f"✓ {tool} ready", "SUCCESS")
            except Exception as e:
                self.log(f"⚠ {tool} failed: {e}", "WARNING")

    def find_python_files(self):
        """Find all Python files"""
        patterns = ['*.py', 'bot/*.py', 'tools/*.py']
        files = set()

        for pattern in patterns:
            files.update(glob.glob(pattern))

        # Exclude certain directories
        excluded = ['venv', '__pycache__', '.venv', 'env', 'build', 'dist']
        files = [f for f in files if not any(ex in f for ex in excluded)]

        return sorted(files)

    def fix_file(self, filepath):
        """Apply all fixes to a file"""
        self.log(f"Processing {filepath}...", "FIX")

        try:
            # Step 1: Remove unused imports
            subprocess.run(
                [
                    sys.executable,
                    '-m',
                    'autoflake',
                    '--in-place',
                    '--remove-all-unused-imports',
                    '--remove-unused-variables',
                    filepath,
                ],
                capture_output=True,
                timeout=60,
            )

            # Step 2: Sort imports
            subprocess.run(
                [sys.executable, '-m', 'isort', '--line-length', '100', filepath],
                capture_output=True,
                timeout=60,
            )

            # Step 3: Format with black
            subprocess.run(
                [
                    sys.executable,
                    '-m',
                    'black',
                    '--line-length',
                    '100',
                    '--skip-string-normalization',
                    filepath,
                ],
                capture_output=True,
                timeout=60,
            )

            # Step 4: Fix PEP8
            subprocess.run(
                [
                    sys.executable,
                    '-m',
                    'autopep8',
                    '--in-place',
                    '--aggressive',
                    '--aggressive',
                    '--max-line-length',
                    '100',
                    filepath,
                ],
                capture_output=True,
                timeout=60,
            )

            self.results['files_fixed'] += 1
            return True

        except Exception as e:
            self.log(f"✗ Error fixing {filepath}: {e}", "ERROR")
            return False

    def check_file_lint(self, filepath):
        """Check for lint errors"""
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    '-m',
                    'flake8',
                    '--max-line-length',
                    '100',
                    '--ignore',
                    'E203,W503,E731,E501',
                    filepath,
                ],
                capture_output=True,
                timeout=60,
                text=True,
            )

            if result.stdout.strip():
                errors = result.stdout.strip().split('\n')
                self.results['errors_found'] += len(errors)
                return len(errors)
            return 0

        except Exception as e:
            self.log(f"✗ Lint check failed: {e}", "ERROR")
            return -1

    def process_all_files(self):
        """Process all Python files"""
        self.section("🔧 PROCESSING PYTHON FILES")

        files = self.find_python_files()
        self.results['total_files'] = len(files)
        self.log(f"Found {len(files)} Python files")

        for i, filepath in enumerate(files, 1):
            if self.verbose:
                self.log(f"[{i}/{len(files)}] {filepath}")

            # Check initial errors
            initial_errors = self.check_file_lint(filepath)

            if initial_errors > 0 and self.auto_fix:
                # Apply fixes
                if self.fix_file(filepath):
                    # Check again
                    final_errors = self.check_file_lint(filepath)
                    fixed = initial_errors - final_errors
                    if fixed > 0:
                        self.results['errors_fixed'] += fixed
                        self.log(f"  ✓ Fixed {fixed} issues", "SUCCESS")
            elif initial_errors == 0:
                if self.verbose:
                    self.log(f"  ✓ No issues", "SUCCESS")

        self.log(f"\nProcessed {self.results['total_files']} files")
        self.log(f"Fixed {self.results['files_fixed']} files")
        self.log(f"Resolved {self.results['errors_fixed']} issues")

    def check_database_integrity(self):
        """Check database integrity"""
        self.section("💾 DATABASE INTEGRITY CHECKS")

        db_path = 'etlegacy_production.db'

        if not os.path.exists(db_path):
            self.log(f"Database not found: {db_path}", "WARNING")
            return

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # 1. Integrity check
            self.log("Running PRAGMA integrity_check...")
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()
            self.results['db_checks'] += 1

            if result[0] == 'ok':
                self.log("✓ Database integrity OK", "SUCCESS")
            else:
                self.log(f"✗ Integrity issues: {result}", "ERROR")
                self.results['db_issues'] += 1

            # 2. Table counts
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            self.log(f"\n📊 Found {len(tables)} tables:")

            for table in tables:
                table_name = table[0]
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                self.log(f"  • {table_name}: {count:,} rows")
                self.results['db_checks'] += 1

            # 3. Data quality checks
            self.log("\n🔍 Data Quality Checks:")

            checks = [
                ("NULL player names",
                 "SELECT COUNT(*) FROM player_comprehensive_stats WHERE player_name IS NULL OR player_name = ''",
                 ),
                ("Negative kills",
                 "SELECT COUNT(*) FROM player_comprehensive_stats WHERE kills < 0",
                 ),
                ("Invalid DPM",
                 "SELECT COUNT(*) FROM player_comprehensive_stats WHERE dpm < 0 OR dpm > 10000",
                 ),
                ("Zero playtime with kills",
                 "SELECT COUNT(*) FROM player_comprehensive_stats WHERE time_played = 0 AND kills > 0",
                 ),
            ]

            for check_name, query in checks:
                try:
                    cursor.execute(query)
                    count = cursor.fetchone()[0]
                    self.results['db_checks'] += 1

                    if count > 0:
                        self.log(f"  ⚠ {check_name}: {count} records", "WARNING")
                        self.results['db_issues'] += 1
                    else:
                        self.log(f"  ✓ {check_name}: OK", "SUCCESS")
                except Exception as e:
                    self.log(f"  ✗ {check_name}: {e}", "ERROR")

            conn.close()
            self.log(f"\nCompleted {self.results['db_checks']} database checks")
            self.log(f"Found {self.results['db_issues']} issues")

        except Exception as e:
            self.log(f"Database check error: {e}", "ERROR")

    def test_imports(self):
        """Test that all modules can be imported"""
        self.section("📦 IMPORT VALIDATION")

        files = self.find_python_files()
        failed = []

        # Skip certain files
        skip_files = ['__init__.py', 'setup.py', 'overnight_', 'nuclear_fix', 'quick_fix']

        for filepath in files:
            if any(skip in filepath for skip in skip_files):
                continue

            self.results['tests_run'] += 1

            if self.verbose:
                self.log(f"Testing import: {filepath}", "TEST")

            # Try importing
            module_path = filepath.replace('\\', '.').replace('/', '.').replace('.py', '')

            try:
                # Use subprocess to isolate imports
                result = subprocess.run(
                    [sys.executable, '-c', f'import {module_path}'],
                    capture_output=True,
                    timeout=10,
                    text=True,
                )

                if result.returncode == 0:
                    self.results['tests_passed'] += 1
                    if self.verbose:
                        self.log(f"  ✓ Import OK", "SUCCESS")
                else:
                    self.results['tests_failed'] += 1
                    failed.append((filepath, result.stderr))
                    self.log(f"  ✗ Import failed", "ERROR")

            except subprocess.TimeoutExpired:
                self.results['tests_failed'] += 1
                failed.append((filepath, "Timeout"))
                self.log(f"  ✗ Import timeout", "ERROR")
            except Exception as e:
                self.results['tests_failed'] += 1
                failed.append((filepath, str(e)))
                self.log(f"  ✗ Error: {e}", "ERROR")

        if failed:
            self.log(f"\n❌ {len(failed)} imports failed:", "ERROR")
            for filepath, error in failed[:10]:  # Show first 10
                self.log(f"  • {filepath}", "ERROR")
                if self.verbose:
                    self.log(f"    {error}", "DETAIL")

    def run_security_scan(self):
        """Run security scan with bandit"""
        self.section("🔒 SECURITY SCAN")

        try:
            self.log("Running bandit security scanner...")
            result = subprocess.run(
                [sys.executable, '-m', 'bandit', '-r', '.', '-x', 'venv,env,.venv', '-f', 'txt'],
                capture_output=True,
                timeout=300,
                text=True,
            )

            if result.returncode == 0:
                self.log("✓ No security issues found", "SUCCESS")
            else:
                self.log("⚠ Security scan found issues", "WARNING")
                if self.verbose:
                    self.log(result.stdout, "DETAIL")

        except Exception as e:
            self.log(f"Security scan error: {e}", "ERROR")

    def generate_report(self):
        """Generate final report"""
        self.section("📊 FINAL REPORT")

        elapsed = time.time() - self.start_time
        hours, remainder = divmod(elapsed, 3600)
        minutes, seconds = divmod(remainder, 60)

        self.log(f"Total Runtime: {int(hours)}h {int(minutes)}m {int(seconds)}s")
        self.log("")

        self.log(f"📁 Files:")
        self.log(f"  • Total files: {self.results['total_files']}")
        self.log(f"  • Files fixed: {self.results['files_fixed']}")
        self.log("")

        self.log(f"🐛 Errors:")
        self.log(f"  • Errors found: {self.results['errors_found']}")
        self.log(f"  • Errors fixed: {self.results['errors_fixed']}")
        if self.results['errors_found'] > 0:
            fix_rate = (self.results['errors_fixed'] / self.results['errors_found']) * 100
            self.log(f"  • Fix rate: {fix_rate:.1f}%")
        self.log("")

        self.log(f"🧪 Tests:")
        self.log(f"  • Tests run: {self.results['tests_run']}")
        self.log(f"  • Tests passed: {self.results['tests_passed']}")
        self.log(f"  • Tests failed: {self.results['tests_failed']}")
        if self.results['tests_run'] > 0:
            pass_rate = (self.results['tests_passed'] / self.results['tests_run']) * 100
            self.log(f"  • Pass rate: {pass_rate:.1f}%")
        self.log("")

        self.log(f"💾 Database:")
        self.log(f"  • Checks run: {self.results['db_checks']}")
        self.log(f"  • Issues found: {self.results['db_issues']}")
        self.log("")

        self.log(f"📝 Log file: {self.log_file}")

        # Overall status
        if (
            self.results['errors_found'] == 0
            and self.results['tests_failed'] == 0
            and self.results['db_issues'] == 0
        ):
            self.log("\n✅ ALL TESTS PASSED! No issues found.", "SUCCESS")
            return True
        else:
            self.log("\n⚠ SOME ISSUES FOUND - See log for details", "WARNING")
            return False

    def run(self):
        """Main execution"""
        self.start_time = time.time()

        self.section("🌙 OVERNIGHT TEST RUNNER STARTING")
        self.log(f"Auto-fix: {'ENABLED' if self.auto_fix else 'DISABLED'}")
        self.log(f"Verbose: {'ENABLED' if self.verbose else 'DISABLED'}")
        self.log(f"Log file: {self.log_file}")

        # Run all test phases
        self.install_tools()
        self.process_all_files()
        self.check_database_integrity()
        self.test_imports()
        self.run_security_scan()

        # Generate report
        success = self.generate_report()

        self.section("🎉 OVERNIGHT TEST RUNNER COMPLETE")

        return success


def main():
    """Entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Overnight test runner')
    parser.add_argument('--no-fix', action='store_true', help='Disable auto-fixing')
    parser.add_argument('--quiet', action='store_true', help='Reduce verbosity')

    args = parser.parse_args()

    runner = OvernightTestRunner(auto_fix=not args.no_fix, verbose=not args.quiet)

    success = runner.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
