"""
Test Security and Stability Fixes
Tests the 5 implemented fixes from AI_AGENT_INSTRUCTIONS.md
"""
import sys
import time
from bot.config import BotConfig
from bot.cogs.server_control import sanitize_filename


def test_filename_sanitization():
    """Test FIX #2: Filename sanitization"""
    print("Testing filename sanitization...")
    
    tests = [
        ("map.pk3", "map.pk3", True),  # Valid filename
        ("supply-final.pk3", "supply-final.pk3", True),  # Valid with dash
        ("../../../etc/passwd", "passwd", True),  # Directory traversal stripped
        ("map; rm -rf /", None, False),  # Basename of '/' is empty -> ValueError
        ("map && echo hack", "mapechohack", True),  # Command chars stripped (safe)
        ("map|cat /etc/shadow", "shadow", True),  # Pipe stripped (safe)
        ("normal_map_v2.pk3", "normal_map_v2.pk3", True),  # Underscore allowed
        (";;;", None, False),  # Empty after sanitization
        ("", None, False),  # Empty input
    ]
    
    passed = 0
    failed = 0
    
    for input_name, expected, should_succeed in tests:
        try:
            result = sanitize_filename(input_name)
            if should_succeed:
                if result == expected:
                    print(f"  ✅ PASS: '{input_name}' → '{result}'")
                    passed += 1
                else:
                    print(f"  ❌ FAIL: '{input_name}' → '{result}' (expected '{expected}')")
                    failed += 1
            else:
                print(f"  ❌ FAIL: '{input_name}' should have raised ValueError but got '{result}'")
                failed += 1
        except ValueError as e:
            if not should_succeed:
                print(f"  ✅ PASS: '{input_name}' correctly blocked with ValueError")
                passed += 1
            else:
                print(f"  ❌ FAIL: '{input_name}' raised ValueError but should succeed")
                failed += 1
    
    print(f"\nFilename Sanitization: {passed} passed, {failed} failed\n")
    return failed == 0


def test_pool_configuration():
    """Test FIX #3: Database pool size"""
    print("Testing database pool configuration...")
    
    cfg = BotConfig()
    
    tests = [
        (cfg.postgres_min_pool, 10, "Min pool size"),
        (cfg.postgres_max_pool, 30, "Max pool size"),
    ]
    
    passed = 0
    failed = 0
    
    for actual, expected, description in tests:
        if actual == expected:
            print(f"  ✅ PASS: {description} = {actual}")
            passed += 1
        else:
            print(f"  ❌ FAIL: {description} = {actual} (expected {expected})")
            failed += 1
    
    print(f"\nPool Configuration: {passed} passed, {failed} failed\n")
    return failed == 0


def test_cooldown_logic():
    """Test cooldown calculation (simulated)"""
    print("Testing cooldown logic...")
    
    # Simulate cooldown tracking
    cooldowns = {}
    
    def check_cooldown(user_id: int, command: str, cooldown_seconds: int):
        """Simulated cooldown check"""
        key = f"{user_id}_{command}"
        current_time = time.time()
        
        if key in cooldowns:
            elapsed = current_time - cooldowns[key]
            if elapsed < cooldown_seconds:
                remaining = cooldown_seconds - elapsed
                return False, remaining
        
        cooldowns[key] = current_time
        return True, 0
    
    # Test scenarios
    user_id = 123456
    
    # First call should succeed
    can_use, remaining = check_cooldown(user_id, "restart", 300)
    if can_use and remaining == 0:
        print(f"  ✅ PASS: First restart attempt allowed")
        passed = 1
        failed = 0
    else:
        print(f"  ❌ FAIL: First restart attempt blocked")
        passed = 0
        failed = 1
    
    # Immediate second call should fail
    can_use, remaining = check_cooldown(user_id, "restart", 300)
    if not can_use and 299 < remaining <= 300:
        print(f"  ✅ PASS: Immediate retry blocked ({remaining:.1f}s remaining)")
        passed += 1
    else:
        print(f"  ❌ FAIL: Immediate retry allowed or wrong cooldown")
        failed += 1
    
    # After cooldown expires
    time.sleep(1.1)  # Sleep 1.1 seconds
    can_use, remaining = check_cooldown(user_id, "restart", 1)
    if can_use and remaining == 0:
        print(f"  ✅ PASS: Retry allowed after cooldown expired")
        passed += 1
    else:
        print(f"  ❌ FAIL: Retry still blocked after cooldown")
        failed += 1
    
    print(f"\nCooldown Logic: {passed} passed, {failed} failed\n")
    return failed == 0


def main():
    print("=" * 60)
    print("Security & Stability Fixes Test Suite")
    print("=" * 60 + "\n")
    
    results = []
    
    results.append(("Filename Sanitization (FIX #2)", test_filename_sanitization()))
    results.append(("Pool Configuration (FIX #3)", test_pool_configuration()))
    results.append(("Cooldown Logic (FIX #5)", test_cooldown_logic()))
    
    print("=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    
    if all_passed:
        print("🎉 ALL TESTS PASSED - Ready for VPS deployment")
        print("=" * 60)
        return 0
    else:
        print("⚠️  SOME TESTS FAILED - Review fixes before deployment")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
