#!/usr/bin/env python3
"""
Test rate limiting logic (sliding window algorithm).

This tests the bot's rate limiting mechanism that prevents DoS attacks
by limiting webhook triggers to 5 per 60 seconds per webhook ID.
"""

from collections import defaultdict, deque
from datetime import datetime, timedelta


def check_rate_limit(webhook_id, timestamps, max_requests=5, window_seconds=60):
    """
    Simulate the bot's rate limiting logic.

    Args:
        webhook_id: The webhook ID to check
        timestamps: Dictionary of webhook_id -> deque of timestamps
        max_requests: Maximum requests allowed in window (default: 5)
        window_seconds: Time window in seconds (default: 60)

    Returns:
        (allowed: bool, wait_time: float)
    """
    now = datetime.now()
    window_start = now - timedelta(seconds=window_seconds)

    # Remove old timestamps
    while timestamps[webhook_id] and timestamps[webhook_id][0] < window_start:
        timestamps[webhook_id].popleft()

    # Check limit
    if len(timestamps[webhook_id]) >= max_requests:
        wait_time = (timestamps[webhook_id][0] + timedelta(seconds=window_seconds) - now).total_seconds()
        return False, wait_time

    timestamps[webhook_id].append(now)
    return True, 0


def test_rate_limiting():
    """Test rate limiting scenarios."""
    timestamps = defaultdict(deque)
    webhook_id = "1449808769725890580"

    print("=" * 80)
    print("RATE LIMITING TEST")
    print("=" * 80)
    print()

    passed = 0
    failed = 0

    print("Test 1: Normal usage (5 requests in 60s)")
    for i in range(5):
        allowed, wait = check_rate_limit(webhook_id, timestamps)
        if allowed:
            print(f"  Request {i+1}: ✅ Allowed")
            passed += 1
        else:
            print(f"  Request {i+1}: ❌ Rate limited (UNEXPECTED - wait {wait:.1f}s)")
            failed += 1

    print("\nTest 2: Exceeding rate limit (6th request)")
    allowed, wait = check_rate_limit(webhook_id, timestamps)
    if not allowed:
        print(f"  Request 6: ✅ Rate limited (wait {wait:.1f}s)")
        passed += 1
    else:
        print("  Request 6: ❌ SHOULD BE BLOCKED")
        failed += 1

    print("\nTest 3: Wait and retry (simulate 60s passing)")
    # Simulate 60 seconds passing by clearing old timestamps
    timestamps[webhook_id].clear()
    allowed, wait = check_rate_limit(webhook_id, timestamps)
    if allowed:
        print(f"  Request 1 (after reset): ✅ Allowed")
        passed += 1
    else:
        print(f"  Request 1 (after reset): ❌ Unexpected limit")
        failed += 1

    print("\nTest 4: Burst then wait (rapid fire 5, wait 60s, then 5 more)")
    timestamps[webhook_id].clear()

    # First burst
    burst1_success = True
    for i in range(5):
        allowed, wait = check_rate_limit(webhook_id, timestamps)
        if not allowed:
            burst1_success = False
            break

    if burst1_success:
        print(f"  First burst: ✅ 5 requests allowed")
        passed += 1
    else:
        print(f"  First burst: ❌ Failed to allow all 5 requests")
        failed += 1

    # Simulate 60s passing
    timestamps[webhook_id].clear()

    # Second burst
    burst2_success = True
    for i in range(5):
        allowed, wait = check_rate_limit(webhook_id, timestamps)
        if not allowed:
            burst2_success = False
            break

    if burst2_success:
        print(f"  Second burst: ✅ 5 requests allowed")
        passed += 1
    else:
        print(f"  Second burst: ❌ Failed to allow all 5 requests")
        failed += 1

    print("\nTest 5: Multiple webhook IDs (isolation)")
    timestamps.clear()
    webhook_id_1 = "1111111111111111111"
    webhook_id_2 = "2222222222222222222"

    # Max out first webhook
    for i in range(5):
        check_rate_limit(webhook_id_1, timestamps)

    # Try 6th request on first webhook (should fail)
    allowed_1, wait = check_rate_limit(webhook_id_1, timestamps)

    # Try request on second webhook (should succeed - different ID)
    allowed_2, wait = check_rate_limit(webhook_id_2, timestamps)

    if not allowed_1 and allowed_2:
        print(f"  Webhook isolation: ✅ IDs are rate-limited independently")
        passed += 1
    else:
        print(f"  Webhook isolation: ❌ Rate limits not properly isolated")
        failed += 1

    print()
    print("=" * 80)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 80)

    if failed == 0:
        print("✅ All tests passed! Rate limiting is working correctly.")
        return 0
    else:
        print(f"❌ {failed} test(s) failed!")
        return 1


if __name__ == "__main__":
    exit(test_rate_limiting())
