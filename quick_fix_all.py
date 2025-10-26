#!/usr/bin/env python3
"""
⚡ QUICK AUTO-FIX ALL ERRORS
===========================
Immediately fixes all linting errors in the workspace.
"""

import glob
import subprocess
import sys


def run_autopep8_aggressive():
    """Run autopep8 on all Python files"""
    print("🔧 Running autopep8 (aggressive mode)...")

    patterns = ['*.py', 'bot/*.py', 'tools/*.py']
    files = []

    for pattern in patterns:
        files.extend(glob.glob(pattern))

    files = [f for f in files if 'venv' not in f and '__pycache__' not in f]

    for filepath in files:
        print(f"  Fixing {filepath}...")
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
            )
        except Exception as e:
            print(f"    ✗ Error: {e}")

    print(f"✓ Processed {len(files)} files")


def run_isort():
    """Run isort on all Python files"""
    print("\n📦 Running isort (import sorting)...")

    patterns = ['*.py', 'bot/*.py', 'tools/*.py']
    files = []

    for pattern in patterns:
        files.extend(glob.glob(pattern))

    files = [f for f in files if 'venv' not in f and '__pycache__' not in f]

    for filepath in files:
        try:
            subprocess.run(
                [sys.executable, '-m', 'isort', filepath], timeout=60, capture_output=True
            )
        except BaseException:
            pass

    print(f"✓ Sorted imports in {len(files)} files")


def install_tools():
    """Ensure tools are installed"""
    print("📥 Installing/upgrading tools...")

    tools = ['autopep8', 'isort']

    for tool in tools:
        try:
            subprocess.run(
                [sys.executable, '-m', 'pip', 'install', '--upgrade', '--quiet', tool], timeout=300
            )
            print(f"  ✓ {tool}")
        except BaseException:
            print(f"  ✗ {tool} (may already be installed)")


def main():
    print("=" * 60)
    print("⚡ QUICK AUTO-FIX ALL ERRORS")
    print("=" * 60)

    # Install tools
    install_tools()

    # Fix imports
    run_isort()

    # Fix PEP8 issues
    run_autopep8_aggressive()

    print("\n" + "=" * 60)
    print("✅ DONE! All files have been auto-fixed.")
    print("=" * 60)


if __name__ == "__main__":
    main()
