"""
Comprehensive Phase 2 Validation - Find all broken references
Checks for old column names and table names in active bot code
"""
import os
import re
from pathlib import Path

# Active bot directories (exclude backup files)
ACTIVE_PATHS = [
    'bot/ultimate_bot.py',
    'bot/core/',
    'bot/cogs/',
]

EXCLUDE_PATTERNS = [
    '*.backup',
    '*.cleaned.py',
    '*_helpers.py',
    '*_impl.py',
    '__pycache__',
]

# Phase 2 changes to validate
OLD_TO_NEW = {
    'session_date': 'round_date',
    'session_time': 'round_time', 
    'session_id': 'round_id',
    'FROM sessions': 'FROM rounds',
    'JOIN sessions': 'JOIN rounds',
    'INTO sessions': 'INTO rounds',
}

def should_check_file(filepath):
    """Check if file should be scanned"""
    filepath_str = str(filepath)
    
    # Exclude patterns
    for pattern in EXCLUDE_PATTERNS:
        if pattern.replace('*', '') in filepath_str:
            return False
    
    return filepath.suffix == '.py'

def scan_file(filepath):
    """Scan a single file for old references"""
    issues = []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        for line_num, line in enumerate(lines, 1):
            # Skip comments
            if line.strip().startswith('#'):
                continue
            
            # Check for old column names in SQL
            if 'WHERE session_date' in line or 'SELECT.*session_date' in line:
                issues.append({
                    'file': filepath,
                    'line': line_num,
                    'issue': 'session_date column (should be round_date)',
                    'code': line.strip()
                })
            
            if 'WHERE session_id' in line and 'session_ids' not in line:
                issues.append({
                    'file': filepath,
                    'line': line_num,
                    'issue': 'session_id column (should be round_id)',
                    'code': line.strip()
                })
            
            # Check for old table names
            if re.search(r'\bFROM sessions\b', line) or re.search(r'\bJOIN sessions\b', line):
                issues.append({
                    'file': filepath,
                    'line': line_num,
                    'issue': 'sessions table (should be rounds)',
                    'code': line.strip()
                })
            
            if 'INTO sessions' in line and 'session_teams' not in line:
                issues.append({
                    'file': filepath,
                    'line': line_num,
                    'issue': 'sessions table INSERT (should be rounds)',
                    'code': line.strip()
                })
    
    except Exception as e:
        print(f"❌ Error reading {filepath}: {e}")
    
    return issues

def main():
    print("🔍 Phase 2 Validation - Scanning for broken references...")
    print()
    
    all_issues = []
    files_scanned = 0
    
    # Scan ultimate_bot.py
    if os.path.exists('bot/ultimate_bot.py'):
        print("📄 Scanning bot/ultimate_bot.py...")
        issues = scan_file(Path('bot/ultimate_bot.py'))
        all_issues.extend(issues)
        files_scanned += 1
    
    # Scan bot/core/
    if os.path.exists('bot/core'):
        print("📁 Scanning bot/core/...")
        for filepath in Path('bot/core').glob('*.py'):
            if should_check_file(filepath):
                issues = scan_file(filepath)
                all_issues.extend(issues)
                files_scanned += 1
    
    # Scan bot/cogs/
    if os.path.exists('bot/cogs'):
        print("📁 Scanning bot/cogs/...")
        for filepath in Path('bot/cogs').glob('*.py'):
            if should_check_file(filepath):
                issues = scan_file(filepath)
                all_issues.extend(issues)
                files_scanned += 1
    
    print()
    print(f"✅ Scanned {files_scanned} files")
    print()
    
    if not all_issues:
        print("🎉 No issues found! All Phase 2 references updated correctly.")
        return
    
    # Group by file
    by_file = {}
    for issue in all_issues:
        filename = str(issue['file'])
        if filename not in by_file:
            by_file[filename] = []
        by_file[filename].append(issue)
    
    print(f"⚠️  Found {len(all_issues)} potential issues in {len(by_file)} files:")
    print()
    
    for filename, issues in sorted(by_file.items()):
        print(f"📄 {filename}")
        for issue in issues:
            print(f"   Line {issue['line']}: {issue['issue']}")
            print(f"      {issue['code'][:100]}")
        print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY:")
    print(f"  Files scanned: {files_scanned}")
    print(f"  Issues found: {len(all_issues)}")
    print(f"  Files with issues: {len(by_file)}")
    print()
    print("💡 Note: Some references may be intentional (e.g., parameter names).")
    print("   Review each one to determine if it needs fixing.")
    print("=" * 80)

if __name__ == '__main__':
    main()
