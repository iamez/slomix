"""
Comprehensive Codebase Diagnostics
Checks for syntax errors, import issues, database problems, and code quality issues
"""

import os
import sys
import py_compile
import sqlite3
import importlib.util
from pathlib import Path
import traceback

class CodebaseDiagnostics:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.info = []
        self.stats = {
            'total_files': 0,
            'syntax_errors': 0,
            'import_errors': 0,
            'db_issues': 0,
            'warnings': 0
        }
    
    def log_error(self, category, message, file=None):
        """Log an error"""
        entry = {'category': category, 'message': message, 'file': file}
        self.errors.append(entry)
        self.stats[category] += 1
    
    def log_warning(self, category, message, file=None):
        """Log a warning"""
        entry = {'category': category, 'message': message, 'file': file}
        self.warnings.append(entry)
        self.stats['warnings'] += 1
    
    def log_info(self, message):
        """Log info message"""
        self.info.append(message)
    
    def check_python_syntax(self, root_dir='.'):
        """Check all Python files for syntax errors"""
        print("\n" + "="*80)
        print("1. CHECKING PYTHON SYNTAX ERRORS")
        print("="*80)
        
        python_files = list(Path(root_dir).rglob('*.py'))
        self.stats['total_files'] = len(python_files)
        
        print(f"📁 Found {len(python_files)} Python files")
        
        for py_file in python_files:
            try:
                # Skip __pycache__ and venv
                if '__pycache__' in str(py_file) or 'venv' in str(py_file):
                    continue
                
                with open(py_file, 'r', encoding='utf-8') as f:
                    code = f.read()
                    compile(code, str(py_file), 'exec')
                    
            except SyntaxError as e:
                self.log_error('syntax_errors', 
                    f"Line {e.lineno}: {e.msg}", 
                    str(py_file))
                print(f"❌ {py_file}: Line {e.lineno} - {e.msg}")
            except Exception as e:
                self.log_error('syntax_errors', 
                    f"Unexpected error: {str(e)}", 
                    str(py_file))
                print(f"⚠️ {py_file}: {str(e)}")
        
        if self.stats['syntax_errors'] == 0:
            print("✅ No syntax errors found!")
        else:
            print(f"\n❌ Found {self.stats['syntax_errors']} files with syntax errors")
    
    def check_imports(self, key_files):
        """Check if key files can be imported"""
        print("\n" + "="*80)
        print("2. CHECKING IMPORT ERRORS")
        print("="*80)
        
        for file_path in key_files:
            if not os.path.exists(file_path):
                self.log_error('import_errors', f"File not found", file_path)
                print(f"❌ {file_path}: File not found")
                continue
            
            try:
                # Try to import the module
                spec = importlib.util.spec_from_file_location("test_module", file_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules["test_module"] = module
                    spec.loader.exec_module(module)
                    print(f"✅ {file_path}: Imports successfully")
                else:
                    self.log_error('import_errors', "Could not load module spec", file_path)
                    print(f"❌ {file_path}: Could not load")
                    
            except Exception as e:
                self.log_error('import_errors', str(e), file_path)
                print(f"❌ {file_path}: {str(e)}")
        
        if self.stats['import_errors'] == 0:
            print("✅ All key files import successfully!")
        else:
            print(f"\n❌ Found {self.stats['import_errors']} import errors")
    
    def check_database(self, db_path='etlegacy_production.db'):
        """Check database integrity and schema"""
        print("\n" + "="*80)
        print("3. CHECKING DATABASE INTEGRITY")
        print("="*80)
        
        if not os.path.exists(db_path):
            self.log_error('db_issues', "Database file not found", db_path)
            print(f"❌ Database not found: {db_path}")
            return
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check required tables
            required_tables = [
                'sessions',
                'player_comprehensive_stats',
                'player_aliases',
                'session_teams',
                'weapon_stats',
                'processed_files',
                'player_synergies'
            ]
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing_tables = [row[0] for row in cursor.fetchall()]
            
            print(f"📊 Found {len(existing_tables)} tables in database")
            
            for table in required_tables:
                if table not in existing_tables:
                    self.log_error('db_issues', f"Missing required table: {table}", db_path)
                    print(f"❌ Missing table: {table}")
                else:
                    # Check row count
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    print(f"✅ {table}: {count} rows")
            
            # Run integrity check
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()[0]
            
            if result == 'ok':
                print("\n✅ Database integrity check: PASSED")
            else:
                self.log_error('db_issues', f"Integrity check failed: {result}", db_path)
                print(f"\n❌ Database integrity check: FAILED - {result}")
            
            conn.close()
            
        except Exception as e:
            self.log_error('db_issues', str(e), db_path)
            print(f"❌ Database error: {e}")
    
    def check_fiveeyes_status(self):
        """Check FIVEEYES implementation status"""
        print("\n" + "="*80)
        print("4. CHECKING FIVEEYES IMPLEMENTATION")
        print("="*80)
        
        fiveeyes_files = [
            'bot/cogs/synergy_analytics.py',
            'analytics/synergy_detector.py',
            'analytics/config.py',
            'fiveeyes_config.json'
        ]
        
        for file in fiveeyes_files:
            if os.path.exists(file):
                print(f"✅ {file}: exists")
            else:
                self.log_warning('warnings', f"FIVEEYES file missing", file)
                print(f"⚠️ {file}: MISSING")
        
        # Check for known issues from audit
        audit_file = 'bot/cogs/synergy_analytics.py'
        if os.path.exists(audit_file):
            with open(audit_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Check for Team B emoji issue (from audit)
                if '�' in content:
                    self.log_warning('warnings', 
                        "Invalid Unicode character found (Team B emoji)", 
                        audit_file)
                    print("⚠️ Found invalid Unicode character (Team B emoji)")
                else:
                    print("✅ No invalid Unicode characters")
                
                # Check for aiosqlite import location
                lines = content.split('\n')
                import_found_at_top = False
                import_in_function = False
                
                for i, line in enumerate(lines[:30], 1):
                    if 'import aiosqlite' in line:
                        import_found_at_top = True
                        print(f"✅ aiosqlite imported at module level (line {i})")
                        break
                
                if not import_found_at_top:
                    for i, line in enumerate(lines[30:], 31):
                        if 'import aiosqlite' in line:
                            import_in_function = True
                            self.log_warning('warnings',
                                f"aiosqlite imported inside function at line {i}",
                                audit_file)
                            print(f"⚠️ aiosqlite imported inside function (line {i})")
                            break
    
    def check_code_quality(self):
        """Check for common code quality issues"""
        print("\n" + "="*80)
        print("5. CHECKING CODE QUALITY ISSUES")
        print("="*80)
        
        key_files = [
            'bot/ultimate_bot.py',
            'bot/cogs/synergy_analytics.py',
            'analytics/synergy_detector.py'
        ]
        
        for file_path in key_files:
            if not os.path.exists(file_path):
                continue
            
            print(f"\n📄 Checking {file_path}...")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
                
                # Check for hardcoded paths
                hardcoded_paths = []
                for i, line in enumerate(lines, 1):
                    if 'etlegacy_production.db' in line and 'self.db_path' not in line:
                        # Allow in comments or variable assignments
                        if not line.strip().startswith('#') and '=' not in line:
                            hardcoded_paths.append(i)
                
                if hardcoded_paths:
                    self.log_warning('warnings',
                        f"Hardcoded database paths at lines: {hardcoded_paths}",
                        file_path)
                    print(f"⚠️ Hardcoded database paths: lines {hardcoded_paths}")
                else:
                    print("✅ No hardcoded database paths")
                
                # Check for TODO comments
                todos = []
                for i, line in enumerate(lines, 1):
                    if 'TODO' in line or 'FIXME' in line:
                        todos.append((i, line.strip()))
                
                if todos:
                    print(f"📝 Found {len(todos)} TODO/FIXME comments:")
                    for line_num, comment in todos[:3]:  # Show first 3
                        print(f"   Line {line_num}: {comment[:60]}...")
                
                # Check for except: pass (silent error handling)
                for i, line in enumerate(lines, 1):
                    if 'except:' in line or 'except Exception:' in line:
                        if i < len(lines) - 1 and 'pass' in lines[i]:
                            self.log_warning('warnings',
                                f"Silent exception handling at line {i}",
                                file_path)
                            print(f"⚠️ Silent exception handling at line {i}")
    
    def check_dependencies(self):
        """Check if required packages are installed"""
        print("\n" + "="*80)
        print("6. CHECKING DEPENDENCIES")
        print("="*80)
        
        required_packages = [
            'discord',
            'aiosqlite',
            'asyncssh',
            'python-dotenv',
            'schedule'
        ]
        
        missing = []
        
        for package in required_packages:
            try:
                __import__(package.replace('-', '_'))
                print(f"✅ {package}: installed")
            except ImportError:
                missing.append(package)
                print(f"❌ {package}: NOT INSTALLED")
        
        if missing:
            self.log_warning('warnings', f"Missing packages: {', '.join(missing)}", None)
            print(f"\n⚠️ Install missing packages: pip install {' '.join(missing)}")
    
    def generate_report(self):
        """Generate final diagnostic report"""
        print("\n" + "="*80)
        print("DIAGNOSTIC REPORT SUMMARY")
        print("="*80)
        
        print(f"\n📊 Statistics:")
        print(f"   Total Python files: {self.stats['total_files']}")
        print(f"   Syntax errors: {self.stats['syntax_errors']}")
        print(f"   Import errors: {self.stats['import_errors']}")
        print(f"   Database issues: {self.stats['db_issues']}")
        print(f"   Warnings: {self.stats['warnings']}")
        
        total_issues = (self.stats['syntax_errors'] + 
                       self.stats['import_errors'] + 
                       self.stats['db_issues'])
        
        if total_issues == 0 and self.stats['warnings'] == 0:
            print("\n✅ ✅ ✅ CODEBASE IS HEALTHY! ✅ ✅ ✅")
            print("No critical issues or warnings found.")
            return True
        
        if total_issues == 0:
            print(f"\n✅ No critical issues found!")
            print(f"⚠️ {self.stats['warnings']} warnings to review")
        else:
            print(f"\n❌ Found {total_issues} critical issues")
            print(f"⚠️ {self.stats['warnings']} additional warnings")
        
        # Show detailed errors
        if self.errors:
            print("\n🔴 CRITICAL ISSUES:")
            for error in self.errors:
                file_info = f" in {error['file']}" if error['file'] else ""
                print(f"   [{error['category']}] {error['message']}{file_info}")
        
        # Show warnings
        if self.warnings:
            print("\n🟡 WARNINGS:")
            for warning in self.warnings[:10]:  # Show first 10
                file_info = f" in {warning['file']}" if warning['file'] else ""
                print(f"   {warning['message']}{file_info}")
            
            if len(self.warnings) > 10:
                print(f"   ... and {len(self.warnings) - 10} more warnings")
        
        return total_issues == 0


def main():
    """Run all diagnostics"""
    print("╔" + "="*78 + "╗")
    print("║" + " "*20 + "CODEBASE DIAGNOSTICS" + " "*38 + "║")
    print("║" + " "*20 + "October 6, 2025" + " "*43 + "║")
    print("╚" + "="*78 + "╝")
    
    diagnostics = CodebaseDiagnostics()
    
    # Run all checks
    diagnostics.check_python_syntax()
    
    key_files = [
        'bot/ultimate_bot.py',
        'bot/cogs/synergy_analytics.py',
        'analytics/synergy_detector.py',
        'analytics/config.py'
    ]
    diagnostics.check_imports(key_files)
    
    diagnostics.check_database()
    diagnostics.check_fiveeyes_status()
    diagnostics.check_code_quality()
    diagnostics.check_dependencies()
    
    # Generate final report
    success = diagnostics.generate_report()
    
    print("\n" + "="*80)
    print("Diagnostics complete!")
    print("="*80)
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
