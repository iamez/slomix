#!/usr/bin/env python3
"""
🔥 NUCLEAR AUTO-FIX
==================
Fixes ALL remaining issues including:
- Line length issues
- Unused imports
- Trailing whitespace
- Blank line issues
"""

import glob
import subprocess
import sys


def remove_unused_imports(filepath):
    """Remove unused imports using autoflake"""
    try:
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
            timeout=60,
            capture_output=True,
        )
        return True
    except BaseException:
        return False


def fix_line_length(filepath):
    """Fix line length issues aggressively"""
    try:
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
            timeout=60,
            capture_output=True,
        )
        return True
    except BaseException:
        return False


def fix_trailing_whitespace(filepath):
    """Remove trailing whitespace and fix blank lines"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Remove trailing whitespace from each line
        lines = content.split('\n')
        fixed_lines = [line.rstrip() for line in lines]

        # Fix blank lines with whitespace
        fixed_content = '\n'.join(fixed_lines)

        # Ensure file ends with single newline
        if fixed_content and not fixed_content.endswith('\n'):
            fixed_content += '\n'

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(fixed_content)

        return True
    except Exception as e:
        print(f"    Error: {e}")
        return False


def install_additional_tools():
    """Install additional fixing tools"""
    print("📥 Installing additional tools...")

    tools = ['autoflake', 'black']

    for tool in tools:
        try:
            subprocess.run(
                [sys.executable, '-m', 'pip', 'install', '--upgrade', '--quiet', tool],
                timeout=300,
                capture_output=True,
            )
            print(f"  ✓ {tool}")
        except BaseException:
            print(f"  ⚠ {tool} (continuing anyway)")


def process_all_files():
    """Process all Python files"""
    patterns = ['*.py', 'bot/*.py', 'tools/*.py']
    files = []

    for pattern in patterns:
        files.extend(glob.glob(pattern))

    files = [f for f in files if 'venv' not in f and '__pycache__' not in f]

    print(f"\n🔧 Processing {len(files)} files...")

    for i, filepath in enumerate(files, 1):
        print(f"  [{i}/{len(files)}] {filepath}...")

        # Step 1: Remove unused imports
        remove_unused_imports(filepath)

        # Step 2: Fix trailing whitespace
        fix_trailing_whitespace(filepath)

        # Step 3: Fix line length with black
        fix_line_length(filepath)

        # Step 4: Final autopep8 pass
        try:
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
                timeout=60,
                capture_output=True,
            )
        except BaseException:
            pass

    print(f"✓ Processed all {len(files)} files")


def main():
    print("=" * 70)
    print("🔥 NUCLEAR AUTO-FIX - FIXING ALL REMAINING ISSUES")
    print("=" * 70)

    install_additional_tools()
    process_all_files()

    print("\n" + "=" * 70)
    print("✅ COMPLETE! All issues should now be fixed.")
    print("=" * 70)
    print("\n💡 Tip: Run 'python -m flake8 --max-line-length=100 .' to verify")


if __name__ == "__main__":
    main()
