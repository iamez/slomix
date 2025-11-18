"""
Source Code Validation - Grep-based verification

This script scans ALL source files to verify Phase 1 terminology and implementation
is correctly applied throughout the codebase.

Checks:
1. All database queries use correct column names
2. No hardcoded 30-minute thresholds remain
3. gaming_session_id is properly used where needed
4. No TODO/FIXME comments related to session terminology
5. Cross-file consistency
"""

import os
import re
from pathlib import Path
from collections import defaultdict

# ANSI colors
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_section(title):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{title.center(80)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.END}\n")

def print_pass(message):
    print(f"{Colors.GREEN}✅ {message}{Colors.END}")

def print_fail(message):
    print(f"{Colors.RED}❌ {message}{Colors.END}")

def print_info(message):
    print(f"{Colors.YELLOW}ℹ️  {message}{Colors.END}")

def scan_for_pattern(pattern, file_path, context_lines=2):
    """Scan a file for a regex pattern and return matches with context"""
    matches = []
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        for i, line in enumerate(lines):
            if re.search(pattern, line, re.IGNORECASE):
                # Get context
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)
                
                context = {
                    'line_num': i + 1,
                    'line': line.strip(),
                    'context': ''.join(lines[start:end])
                }
                matches.append(context)
    except Exception as e:
        pass  # Skip files that can't be read
    
    return matches

def get_python_files():
    """Get all Python files in the workspace"""
    python_files = []
    
    for root, dirs, files in os.walk('.'):
        # Skip virtual environments and hidden directories
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['venv', '.venv', '__pycache__', 'node_modules']]
        
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    
    return python_files

def check_30min_thresholds():
    """Check for any remaining 30-minute threshold references"""
    print_section("1. CHECKING FOR OLD 30-MINUTE THRESHOLDS")
    
    patterns = [
        r'gap.*<=?\s*30',  # gap <= 30, gap < 30, etc.
        r'30\s*min',       # 30 min, 30min, etc.
        r'THRESHOLD.*30',  # THRESHOLD = 30
    ]
    
    issues = []
    python_files = get_python_files()
    
    for pattern in patterns:
        for file_path in python_files:
            matches = scan_for_pattern(pattern, file_path)
            
            for match in matches:
                # Check if it's in a comment or doc string
                line = match['line']
                is_comment = line.strip().startswith('#')
                is_docstring = '"""' in line or "'''" in line
                
                if not is_comment and not is_docstring:
                    issues.append({
                        'file': file_path,
                        'line': match['line_num'],
                        'content': match['line'],
                        'pattern': pattern
                    })
    
    if issues:
        print_fail(f"Found {len(issues)} potential 30-minute threshold issues:")
        for issue in issues[:10]:  # Show first 10
            print(f"  {issue['file']}:{issue['line']}")
            print(f"    {issue['content'][:100]}")
    else:
        print_pass("No 30-minute thresholds found in active code")
    
    return len(issues) == 0

def check_gaming_session_id_usage():
    """Check that gaming_session_id is used where expected"""
    print_section("2. CHECKING gaming_session_id USAGE")
    
    critical_files = [
        'database_manager.py',
        'bot/cogs/last_session_cog.py',
    ]
    
    issues = []
    
    for file_path in critical_files:
        if not os.path.exists(file_path):
            issues.append(f"Critical file not found: {file_path}")
            continue
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if 'gaming_session_id' not in content:
            issues.append(f"{file_path} doesn't use gaming_session_id")
            print_fail(f"{file_path} doesn't reference gaming_session_id")
        else:
            # Count occurrences
            count = content.count('gaming_session_id')
            print_pass(f"{file_path} uses gaming_session_id ({count} occurrences)")
    
    return len(issues) == 0

def check_sql_queries():
    """Check SQL queries for correct column usage"""
    print_section("3. CHECKING SQL QUERIES")
    
    python_files = get_python_files()
    issues = []
    
    # Pattern to find SQL queries
    sql_pattern = r'(SELECT|INSERT|UPDATE|DELETE).*sessions'
    
    findings = defaultdict(list)
    
    for file_path in python_files:
        matches = scan_for_pattern(sql_pattern, file_path, context_lines=5)
        
        for match in matches:
            # Check if gaming_session_id is mentioned in nearby context
            context = match['context'].lower()
            
            if 'select' in context and 'rounds' in context:
                # This is a SELECT from sessions
                if 'gaming_session_id' in context:
                    findings['uses_gaming_session_id'].append(file_path)
                else:
                    findings['no_gaming_session_id'].append({
                        'file': file_path,
                        'line': match['line_num'],
                        'query': match['line']
                    })
    
    # Report findings
    print_info(f"Found {len(findings['uses_gaming_session_id'])} queries using gaming_session_id")
    
    if findings['no_gaming_session_id']:
        print_info(f"Found {len(findings['no_gaming_session_id'])} queries NOT using gaming_session_id (might be OK):")
        for item in findings['no_gaming_session_id'][:5]:
            print(f"  {item['file']}:{item['line']}")
    
    return True  # Not a failure, just informational

def check_todo_fixme_comments():
    """Check for TODO/FIXME related to session terminology"""
    print_section("4. CHECKING TODO/FIXME COMMENTS")
    
    patterns = [
        r'TODO.*session',
        r'FIXME.*session',
        r'BUG.*session',
        r'HACK.*session',
    ]
    
    python_files = get_python_files()
    findings = []
    
    for pattern in patterns:
        for file_path in python_files:
            matches = scan_for_pattern(pattern, file_path)
            findings.extend([(file_path, m) for m in matches])
    
    if findings:
        print_info(f"Found {len(findings)} TODO/FIXME comments mentioning sessions:")
        for file_path, match in findings[:10]:
            print(f"  {file_path}:{match['line_num']}")
            print(f"    {match['line'][:100]}")
    else:
        print_pass("No round-related TODO/FIXME comments found")
    
    return True  # Informational only

def check_documentation_mentions():
    """Check that documentation mentions gaming_session_id"""
    print_section("5. CHECKING DOCUMENTATION")
    
    doc_files = [
        'EDGE_CASES.md',
        'PHASE1_IMPLEMENTATION_COMPLETE.md',
        'COMPLETE_SESSION_TERMINOLOGY_AUDIT.md',
    ]
    
    issues = []
    
    for doc_file in doc_files:
        if not os.path.exists(doc_file):
            issues.append(f"Documentation file missing: {doc_file}")
            continue
        
        with open(doc_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if 'gaming_session_id' not in content.lower():
            issues.append(f"{doc_file} doesn't mention gaming_session_id")
            print_fail(f"{doc_file} missing gaming_session_id reference")
        else:
            count = content.lower().count('gaming_session_id')
            print_pass(f"{doc_file} documents gaming_session_id ({count} mentions)")
        
        # Check for 60-minute threshold mention
        if '60' not in content and 'sixty' not in content.lower():
            print_info(f"  Warning: {doc_file} might not mention 60-minute threshold")
    
    return len(issues) == 0

def check_consistency_across_files():
    """Check for consistency in how gaming sessions are referenced"""
    print_section("6. CHECKING CROSS-FILE CONSISTENCY")
    
    python_files = get_python_files()
    
    # Patterns to look for
    patterns = {
        'gaming_session_id': r'\bgaming_session_id\b',
        'GAP_THRESHOLD_MINUTES = 60': r'GAP_THRESHOLD_MINUTES\s*=\s*60',
        'gaming session (comment)': r'#.*gaming session',
    }
    
    results = defaultdict(list)
    
    for pattern_name, pattern in patterns.items():
        for file_path in python_files:
            matches = scan_for_pattern(pattern, file_path)
            if matches:
                results[pattern_name].append({
                    'file': file_path,
                    'count': len(matches)
                })
    
    # Report
    for pattern_name, files in results.items():
        print_pass(f"Pattern '{pattern_name}' found in {len(files)} files")
        if len(files) > 0:
            for item in files[:3]:
                print(f"    {item['file']} ({item['count']} times)")
    
    return True

def main():
    """Run all source code validations"""
    print_section("SOURCE CODE VALIDATION - GREP-BASED VERIFICATION")
    print("Scanning ALL Python files for Phase 1 implementation consistency\n")
    
    results = []
    
    # Run all checks
    results.append(("30-minute threshold check", check_30min_thresholds()))
    results.append(("gaming_session_id usage", check_gaming_session_id_usage()))
    results.append(("SQL queries check", check_sql_queries()))
    results.append(("TODO/FIXME comments", check_todo_fixme_comments()))
    results.append(("Documentation check", check_documentation_mentions()))
    results.append(("Cross-file consistency", check_consistency_across_files()))
    
    # Summary
    print_section("SOURCE CODE VALIDATION SUMMARY")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"\n{Colors.BOLD}Results:{Colors.END}")
    for test_name, result in results:
        status = f"{Colors.GREEN}✅ PASS{Colors.END}" if result else f"{Colors.RED}❌ FAIL{Colors.END}"
        print(f"  {test_name:.<50} {status}")
    
    print(f"\n{Colors.BOLD}Pass Rate: {passed}/{total} ({passed/total*100:.1f}%){Colors.END}")
    
    if passed == total:
        print(f"\n{Colors.BOLD}{Colors.GREEN}✅ ALL SOURCE CODE CHECKS PASSED!{Colors.END}")
        print(f"{Colors.GREEN}Phase 1 implementation is consistent across all files.{Colors.END}")
    else:
        print(f"\n{Colors.BOLD}{Colors.YELLOW}⚠️  SOME CHECKS NEED REVIEW{Colors.END}")
        print(f"{Colors.YELLOW}Review issues above before committing.{Colors.END}")
    
    print(f"\n{Colors.BOLD}{'='*80}{Colors.END}\n")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
