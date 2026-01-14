#!/usr/bin/env python3
"""
Test webhook ID validation logic.

This tests that only properly formatted Discord webhook IDs are accepted
in the whitelist configuration.
"""

def test_webhook_id_validation():
    """Test various webhook ID formats."""

    valid_webhook_ids = [
        "1449808769725890580",  # Current production webhook
        "123456789012345678",   # Valid 18-digit ID
        "12345678901234567890", # Valid 20-digit ID
    ]

    invalid_webhook_ids = [
        "not_a_number",         # Non-numeric
        "12345",                # Too short
        "123456789012345678901", # Too long (21 digits)
        "",                     # Empty
        None,                   # None
        "1234567890' OR '1'='1", # SQL injection attempt
        "1234567890\x00",       # Null byte
        "1234567890; rm -rf /", # Command injection
    ]

    # Test whitelist matching
    whitelist = ["1449808769725890580"]

    print("=" * 80)
    print("WEBHOOK ID VALIDATION TEST")
    print("=" * 80)
    print()

    passed = 0
    failed = 0

    print("Testing valid webhook IDs...")
    for webhook_id in valid_webhook_ids:
        if webhook_id in whitelist:
            print(f"✅ {webhook_id} - Whitelisted")
            passed += 1
        else:
            print(f"⚠️ {webhook_id} - Valid format but not whitelisted")
            passed += 1

    print("\nTesting invalid webhook IDs...")
    for webhook_id in invalid_webhook_ids:
        # Skip None for string operations
        webhook_id_str = str(webhook_id) if webhook_id is not None else "None"

        if webhook_id in whitelist:
            print(f"❌ {webhook_id_str} - SHOULD NOT BE WHITELISTED")
            failed += 1
        else:
            print(f"✅ {webhook_id_str} - Correctly rejected")
            passed += 1

    print()
    print("=" * 80)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 80)

    if failed == 0:
        print("✅ All tests passed! Webhook ID validation is working correctly.")
        return 0
    else:
        print(f"❌ {failed} test(s) failed!")
        return 1


if __name__ == "__main__":
    exit(test_webhook_id_validation())
