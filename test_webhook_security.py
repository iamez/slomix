#!/usr/bin/env python3
"""
Test script for webhook security validation.

This demonstrates the filename validation protection against:
- Path traversal attacks
- Malicious filenames
- Invalid formats
"""

import re

def validate_stats_filename(filename: str) -> bool:
    """
    Strict validation for stats filenames.

    Valid format: YYYY-MM-DD-HHMMSS-mapname-round-N.txt
    Example: 2025-12-09-221829-etl_sp_delivery-round-1.txt

    Security: Prevents path traversal, injection, null bytes
    """
    # Length check (prevent DoS)
    if len(filename) > 255:
        print(f"❌ Filename too long: {len(filename)} chars")
        return False

    # Path traversal checks
    if any(char in filename for char in ['/', '\\', '\0']):
        print(f"❌ Invalid characters in filename: {filename}")
        return False

    if '..' in filename:
        print(f"❌ Parent directory reference: {filename}")
        return False

    # Strict pattern: YYYY-MM-DD-HHMMSS-mapname-round-N.txt
    pattern = r'^(\d{4})-(\d{2})-(\d{2})-(\d{6})-([a-zA-Z0-9_-]+)-round-(\d+)\.txt$'
    match = re.match(pattern, filename)

    if not match:
        print(f"❌ Invalid filename format: {filename}")
        return False

    # Validate components
    year, month, day, timestamp, map_name, round_num = match.groups()

    if not (2020 <= int(year) <= 2035):
        print(f"❌ Invalid year: {year}")
        return False
    if not (1 <= int(month) <= 12):
        print(f"❌ Invalid month: {month}")
        return False
    if not (1 <= int(day) <= 31):
        print(f"❌ Invalid day: {day}")
        return False
    if not (1 <= int(round_num) <= 10):
        print(f"❌ Invalid round number: {round_num}")
        return False
    if len(map_name) > 50:
        print(f"❌ Map name too long: {map_name}")
        return False

    # Validate timestamp (HHMMSS)
    hour = int(timestamp[0:2])
    minute = int(timestamp[2:4])
    second = int(timestamp[4:6])
    if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
        print(f"❌ Invalid timestamp: {timestamp}")
        return False

    print(f"✅ Filename validated: {filename}")
    return True


def main():
    print("=" * 80)
    print("WEBHOOK SECURITY VALIDATION TEST")
    print("=" * 80)
    print()

    # Test cases
    test_cases = [
        # Valid filenames
        ("2025-12-14-120000-goldrush-round-1.txt", True, "Valid filename"),
        ("2025-01-01-235959-etl_sp_delivery-round-2.txt", True, "Valid with underscores"),
        ("2024-06-15-143022-baserace-round-1.txt", True, "Valid past date"),

        # Path traversal attacks (SHOULD FAIL)
        ("../../../../etc/passwd.txt", False, "Path traversal with ../"),
        ("../../../etc/shadow-round-1.txt", False, "Path traversal attempt"),
        ("/etc/passwd.txt", False, "Absolute path"),
        ("subdir/file-round-1.txt", False, "Subdirectory path"),
        ("C:\\Windows\\System32\\config-round-1.txt", False, "Windows path"),

        # Invalid formats (SHOULD FAIL)
        ("test-file.txt", False, "Missing date pattern"),
        ("2025-12-14-goldrush.txt", False, "Missing time and round"),
        ("malicious`rm -rf /`.txt", False, "Command injection attempt"),
        ("file; rm -rf /-round-1.txt", False, "Shell metacharacters"),

        # Null byte injection (SHOULD FAIL)
        ("2025-12-14-120000-map-round-1.txt\x00malicious", False, "Null byte injection"),

        # Invalid dates (SHOULD FAIL)
        ("2025-13-14-120000-map-round-1.txt", False, "Invalid month (13)"),
        ("2025-12-32-120000-map-round-1.txt", False, "Invalid day (32)"),
        ("1999-12-14-120000-map-round-1.txt", False, "Year too old"),
        ("2050-12-14-120000-map-round-1.txt", False, "Year too far future"),

        # Invalid timestamps (SHOULD FAIL)
        ("2025-12-14-250000-map-round-1.txt", False, "Invalid hour (25)"),
        ("2025-12-14-126000-map-round-1.txt", False, "Invalid minute (60)"),
        ("2025-12-14-120060-map-round-1.txt", False, "Invalid second (60)"),

        # Invalid round numbers (SHOULD FAIL)
        ("2025-12-14-120000-map-round-0.txt", False, "Round 0 (invalid)"),
        ("2025-12-14-120000-map-round-11.txt", False, "Round 11 (too high)"),

        # Length attacks (SHOULD FAIL)
        ("2025-12-14-120000-" + "A" * 100 + "-round-1.txt", False, "Map name too long"),
        ("A" * 300 + ".txt", False, "Filename too long"),
    ]

    passed = 0
    failed = 0

    for filename, should_pass, description in test_cases:
        print(f"\nTest: {description}")
        print(f"  Filename: {filename[:80]}")
        print(f"  Expected: {'PASS' if should_pass else 'FAIL'}")
        print(f"  Result: ", end="")

        result = validate_stats_filename(filename)

        if result == should_pass:
            print(f"  ✅ CORRECT")
            passed += 1
        else:
            print(f"  ❌ WRONG (expected {should_pass}, got {result})")
            failed += 1

    print()
    print("=" * 80)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 80)

    if failed == 0:
        print("✅ All tests passed! Filename validation is working correctly.")
        return 0
    else:
        print(f"❌ {failed} test(s) failed!")
        return 1


if __name__ == "__main__":
    exit(main())
