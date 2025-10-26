#!/usr/bin/env python3
"""
📊 MONITOR OVERNIGHT TESTS
=========================
Check the progress of overnight test runner.
"""

import glob
import os


def main():
    # Find the most recent log file
    log_files = glob.glob("overnight_test_log_*.txt")

    if not log_files:
        print("❌ No log file found. Tests may not have started yet.")
        return

    # Get most recent
    log_file = max(log_files, key=os.path.getctime)

    print("=" * 70)
    print(f"📊 MONITORING: {log_file}")
    print("=" * 70)
    print()

    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Show last 30 lines
        print("Last 30 log entries:")
        print("-" * 70)
        for line in lines[-30:]:
            print(line.rstrip())

        print()
        print("-" * 70)
        print(f"Total log entries: {len(lines)}")

        # Count important markers
        successes = sum(1 for line in lines if '[SUCCESS]' in line)
        errors = sum(1 for line in lines if '[ERROR]' in line)
        warnings = sum(1 for line in lines if '[WARNING]' in line)

        print(f"✓ Successes: {successes}")
        print(f"⚠ Warnings: {warnings}")
        print(f"✗ Errors: {errors}")

        # Check if complete
        if 'COMPLETE' in lines[-1]:
            print()
            print("✅ Tests have COMPLETED!")
        else:
            print()
            print("⏳ Tests are still RUNNING...")

    except Exception as e:
        print(f"❌ Error reading log: {e}")


if __name__ == "__main__":
    main()
