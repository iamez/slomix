#!/usr/bin/env python3
"""
🌙 OVERNIGHT AUTOMATED FIXER
============================
Runs comprehensive tests and auto-fixes all linting/formatting errors.
Can run unattended overnight.
"""

import glob
import os
import subprocess
import sys
import time

# Configuration
AUTO_FIX = True  # Set to True for auto-fixing
VERBOSE = True
LOG_FILE = "overnight_fix_log.txt"


class OvernightFixer:
    def __init__(self):
        self.log_entries = []
        self.errors_found = 0
        self.errors_fixed = 0
        self.files_processed = 0

    def log(self, message, level="INFO"):
        """Log message to console and file"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}"
        print(log_entry)
        self.log_entries.append(log_entry)

    def save_log(self):
        """Save log to file"""
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            f.write('\n'.join(self.log_entries))
        self.log(f"Log saved to {LOG_FILE}")

    def find_python_files(self):
        """Find all Python files in workspace"""
        patterns = ['*.py', 'bot/*.py', 'tools/*.py', 'src/*.py', 'scripts/*.py']

        files = set()
        for pattern in patterns:
            files.update(glob.glob(pattern, recursive=False))

        # Filter out virtual env and cache
        files = [
            f for f in files if not any(x in f for x in ['venv', '__pycache__', '.venv', 'env'])
        ]
        return sorted(files)

    def install_tools(self):
        """Install/upgrade required tools"""
        self.log("Installing/upgrading linting tools...")
        tools = ['autopep8', 'flake8', 'black', 'isort', 'pylint']

        for tool in tools:
            try:
                subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', '--upgrade', tool],
                    capture_output=True,
                    timeout=300,
                )
                self.log(f"✓ {tool} ready", "SUCCESS")
            except Exception as e:
                self.log(f"✗ Failed to install {tool}: {e}", "ERROR")

    def fix_with_autopep8(self, filepath):
        """Fix PEP8 issues automatically"""
        try:
            cmd = [
                sys.executable,
                '-m',
                'autopep8',
                '--in-place',
                '--aggressive',
                '--aggressive',
                '--max-line-length',
                '100',
                filepath,
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=60)
            return result.returncode == 0
        except Exception as e:
            self.log(f"autopep8 failed on {filepath}: {e}", "ERROR")
            return False

    def fix_with_isort(self, filepath):
        """Fix import ordering"""
        try:
            cmd = [sys.executable, '-m', 'isort', filepath]
            result = subprocess.run(cmd, capture_output=True, timeout=60)
            return result.returncode == 0
        except Exception as e:
            self.log(f"isort failed on {filepath}: {e}", "ERROR")
            return False

    def check_with_flake8(self, filepath):
        """Check for remaining issues"""
        try:
            cmd = [
                sys.executable,
                '-m',
                'flake8',
                '--max-line-length',
                '100',
                '--ignore',
                'E203,W503,E731',  # Ignore some style preferences
                filepath,
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=60, text=True)
            return result.stdout
        except Exception as e:
            self.log(f"flake8 check failed on {filepath}: {e}", "ERROR")
            return ""

    def run_tests(self):
        """Run test suite if available"""
        self.log("\n" + "=" * 60)
        self.log("RUNNING TESTS")
        self.log("=" * 60)

        test_patterns = ['test_*.py', '*_test.py', 'tests/*.py']
        test_files = []

        for pattern in test_patterns:
            test_files.extend(glob.glob(pattern))

        if not test_files:
            self.log("No test files found", "WARNING")
            return True

        for test_file in test_files:
            self.log(f"Running {test_file}...")
            try:
                result = subprocess.run(
                    [sys.executable, test_file], capture_output=True, timeout=300, text=True
                )

                if result.returncode == 0:
                    self.log(f"✓ {test_file} PASSED", "SUCCESS")
                else:
                    self.log(f"✗ {test_file} FAILED", "ERROR")
                    self.log(result.stdout, "OUTPUT")
                    self.log(result.stderr, "ERROR")

            except subprocess.TimeoutExpired:
                self.log(f"✗ {test_file} TIMEOUT", "ERROR")
            except Exception as e:
                self.log(f"✗ {test_file} ERROR: {e}", "ERROR")

        return True

    def process_file(self, filepath):
        """Process a single Python file"""
        self.log(f"\n{'=' * 60}")
        self.log(f"Processing: {filepath}")
        self.log(f"{'=' * 60}")

        # Check initial errors
        initial_errors = self.check_with_flake8(filepath)
        if initial_errors:
            error_count = len(initial_errors.strip().split('\n'))
            self.errors_found += error_count
            self.log(f"Found {error_count} issues", "WARNING")
            if VERBOSE:
                self.log(initial_errors, "DETAILS")
        else:
            self.log("✓ No issues found", "SUCCESS")
            return

        if not AUTO_FIX:
            self.log("Auto-fix disabled, skipping", "INFO")
            return

        # Apply fixes
        self.log("Applying fixes...")

        # 1. Fix imports
        if self.fix_with_isort(filepath):
            self.log("✓ Import order fixed", "SUCCESS")

        # 2. Fix PEP8 issues
        if self.fix_with_autopep8(filepath):
            self.log("✓ PEP8 issues fixed", "SUCCESS")

        # Check remaining errors
        final_errors = self.check_with_flake8(filepath)
        if final_errors:
            final_count = len(final_errors.strip().split('\n'))
            self.log(f"Remaining issues: {final_count}", "WARNING")
            if VERBOSE:
                self.log(final_errors, "DETAILS")
            fixed = error_count - final_count
            self.errors_fixed += fixed
        else:
            self.log("✓ All issues resolved!", "SUCCESS")
            self.errors_fixed += error_count

    def run_database_tests(self):
        """Test database integrity"""
        self.log("\n" + "=" * 60)
        self.log("DATABASE INTEGRITY TESTS")
        self.log("=" * 60)

        db_path = 'etlegacy_production.db'
        if not os.path.exists(db_path):
            self.log(f"Database not found: {db_path}", "WARNING")
            return

        try:
            import sqlite3

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Check database integrity
            self.log("Running PRAGMA integrity_check...")
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()
            if result[0] == 'ok':
                self.log("✓ Database integrity OK", "SUCCESS")
            else:
                self.log(f"✗ Database integrity issues: {result}", "ERROR")

            # Check table counts
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            self.log(f"Found {len(tables)} tables")

            for table in tables:
                table_name = table[0]
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                self.log(f"  {table_name}: {count} rows")

            # Check for orphaned records
            self.log("\nChecking for data integrity issues...")

            # Check player_comprehensive_stats
            cursor.execute(
                """
                SELECT COUNT(*) FROM player_comprehensive_stats
                WHERE player_name IS NULL OR player_name = ''
            """
            )
            null_players = cursor.fetchone()[0]
            if null_players > 0:
                self.log(f"✗ Found {null_players} records with NULL player names", "ERROR")
            else:
                self.log("✓ No NULL player names", "SUCCESS")

            conn.close()

        except Exception as e:
            self.log(f"Database test error: {e}", "ERROR")

    def run_import_tests(self):
        """Test that all modules can be imported"""
        self.log("\n" + "=" * 60)
        self.log("IMPORT TESTS")
        self.log("=" * 60)

        files = self.find_python_files()
        failed = []

        for filepath in files:
            # Skip certain files
            if any(x in filepath for x in ['__init__', 'setup.py', 'overnight_fix']):
                continue

            module_path = filepath.replace('\\', '/').replace('/', '.').replace('.py', '')
            module_path = module_path.lstrip('.')

            try:
                self.log(f"Importing {module_path}...")
                __import__(module_path)
                self.log(f"✓ {module_path}", "SUCCESS")
            except ImportError as e:
                self.log(f"✗ {module_path}: {e}", "ERROR")
                failed.append((module_path, str(e)))
            except Exception as e:
                self.log(f"⚠ {module_path}: {e}", "WARNING")

        if failed:
            self.log(f"\n{len(failed)} modules failed to import:", "ERROR")
            for module, error in failed:
                self.log(f"  {module}: {error}", "ERROR")
        else:
            self.log("\n✓ All modules imported successfully!", "SUCCESS")

    def run(self):
        """Main execution"""
        start_time = time.time()

        self.log("=" * 60)
        self.log("🌙 OVERNIGHT AUTOMATED FIXER STARTING")
        self.log("=" * 60)
        self.log(f"Auto-fix: {AUTO_FIX}")
        self.log(f"Verbose: {VERBOSE}")
        self.log("")

        # Step 1: Install tools
        self.install_tools()

        # Step 2: Find files
        files = self.find_python_files()
        self.log(f"\nFound {len(files)} Python files to process")

        # Step 3: Process each file
        for filepath in files:
            try:
                self.process_file(filepath)
                self.files_processed += 1
            except Exception as e:
                self.log(f"Failed to process {filepath}: {e}", "ERROR")

        # Step 4: Run database tests
        self.run_database_tests()

        # Step 5: Run import tests
        self.run_import_tests()

        # Step 6: Run test suite
        self.run_tests()

        # Summary
        elapsed = time.time() - start_time
        self.log("\n" + "=" * 60)
        self.log("🎉 OVERNIGHT FIXER COMPLETE")
        self.log("=" * 60)
        self.log(f"Files processed: {self.files_processed}")
        self.log(f"Errors found: {self.errors_found}")
        self.log(f"Errors fixed: {self.errors_fixed}")
        self.log(f"Time elapsed: {elapsed:.1f} seconds ({elapsed / 60:.1f} minutes)")
        self.log(
            f"Success rate: {(self.errors_fixed / self.errors_found * 100 if self.errors_found > 0 else 100):.1f}%"
        )

        # Save log
        self.save_log()

        return self.errors_found == 0 or self.errors_fixed == self.errors_found


if __name__ == "__main__":
    fixer = OvernightFixer()
    success = fixer.run()
    sys.exit(0 if success else 1)
