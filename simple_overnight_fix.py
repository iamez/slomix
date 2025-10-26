#!/usr/bin/env python3
"""
🔧 SIMPLE OVERNIGHT FIXER - ROBUST VERSION
==========================================
Simplified overnight fixer that just works.
Fixes all code issues automatically without complex checks.
"""

import glob
import subprocess
import sys
import time
from datetime import datetime


def log(msg):
    """Simple logging"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def get_python_files():
    """Get all Python files"""
    patterns = ['*.py', 'bot/*.py', 'tools/*.py']
    files = set()
    for pattern in patterns:
        files.update(glob.glob(pattern))
    # Exclude venv
    return [f for f in files if 'venv' not in f and '__pycache__' not in f]


def fix_file_robust(filepath):
    """Apply all fixes robustly"""
    try:
        # Fix 1: Remove unused imports
        subprocess.run(
            [
                sys.executable,
                '-m',
                'autoflake',
                '--in-place',
                '--remove-all-unused-imports',
                filepath,
            ],
            capture_output=True,
            timeout=30,
        )

        # Fix 2: Sort imports
        subprocess.run(
            [sys.executable, '-m', 'isort', '--line-length', '100', filepath],
            capture_output=True,
            timeout=30,
        )

        # Fix 3: Format with black
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
            timeout=30,
        )

        # Fix 4: PEP8
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
            timeout=30,
        )

        return True
    except Exception as e:
        log(f"  ⚠ Error fixing {filepath}: {e}")
        return False


def main():
    log("=" * 60)
    log("🔧 SIMPLE OVERNIGHT FIXER STARTING")
    log("=" * 60)

    start = time.time()

    # Get files
    files = get_python_files()
    log(f"Found {len(files)} Python files to fix")
    log("")

    # Fix each file
    fixed = 0
    for i, filepath in enumerate(files, 1):
        log(f"[{i}/{len(files)}] Fixing {filepath}...")
        if fix_file_robust(filepath):
            fixed += 1

    # Summary
    elapsed = time.time() - start
    log("")
    log("=" * 60)
    log(f"✅ COMPLETE!")
    log(f"Files processed: {len(files)}")
    log(f"Files fixed: {fixed}")
    log(f"Time: {elapsed / 60:.1f} minutes")
    log("=" * 60)


if __name__ == "__main__":
    main()
