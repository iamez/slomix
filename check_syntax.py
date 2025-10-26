#!/usr/bin/env python3
"""
Quick syntax checker for all Python files in workspace
"""
import os
import ast

def check_python_files():
    """Scan all Python files for syntax errors"""
    errors = []
    files_checked = 0
    skipped_docs = []
    
    for root, dirs, files in os.walk('.'):
        # Skip virtual environments and cache
        if 'venv' in root or '__pycache__' in root or '.venv' in root:
            continue
            
        for file in files:
            if not file.endswith('.py'):
                continue
                
            filepath = os.path.join(root, file)
            files_checked += 1
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Check if it's actually a documentation file with .py extension
                if content.strip().startswith('"""') and '═══════' in content[:200]:
                    skipped_docs.append(filepath)
                    continue
                    
                ast.parse(content, filename=file)
                
            except SyntaxError as e:
                errors.append({
                    'file': filepath,
                    'line': e.lineno,
                    'msg': e.msg,
                    'text': e.text.strip() if e.text else ''
                })
            except Exception as e:
                errors.append({
                    'file': filepath,
                    'line': '?',
                    'msg': str(e),
                    'text': ''
                })
    
    return files_checked, errors, skipped_docs

if __name__ == '__main__':
    print("🔍 PYTHON SYNTAX CHECK")
    print("=" * 80)
    
    files_checked, errors, skipped_docs = check_python_files()
    
    print(f"\n📊 RESULTS:")
    print(f"  Files checked: {files_checked}")
    print(f"  Documentation files skipped: {len(skipped_docs)}")
    print(f"  Syntax errors found: {len(errors)}")
    
    if skipped_docs:
        print(f"\n📄 SKIPPED (Documentation with .py extension):")
        for doc in skipped_docs[:5]:
            print(f"  📝 {doc}")
    
    if errors:
        print(f"\n❌ SYNTAX ERRORS:")
        for err in errors:
            print(f"\n  File: {err['file']}")
            print(f"  Line: {err['line']}")
            print(f"  Error: {err['msg']}")
            if err['text']:
                print(f"  Code: {err['text']}")
    else:
        print("\n✅ ALL PYTHON FILES PASSED SYNTAX CHECK!")
    
    print("\n" + "=" * 80)
