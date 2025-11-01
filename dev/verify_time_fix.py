"""
Verify that the time_played_minutes fix actually works.
This script tests the Round 2 differential calculation to ensure
time_played_minutes is preserved correctly.
"""
import sys
from pathlib import Path
# Add project root to sys.path (relative, portable)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.community_stats_parser import C0RNP0RN3StatsParser

def test_round_2_time_preservation():
    """Test that Round 2 differential preserves time_played_minutes."""
    
    parser = C0RNP0RN3StatsParser()
    
    # Use the October 2 files that were mentioned in the documentation
    round_1_file = 'local_stats/2025-10-02-211808-etl_adlernest-round-1.txt'
    round_2_file = 'local_stats/2025-10-02-212249-etl_adlernest-round-2.txt'
    
    print("=" * 80)
    print("🔍 Testing Round 2 Time Preservation Fix")
    print("=" * 80)
    print()
    
    # Parse Round 1
    print("📂 Parsing Round 1...")
    r1_result = parser.parse_regular_stats_file(round_1_file)
    if not r1_result['success']:
        print("❌ Failed to parse Round 1")
        return False
    
    # Parse Round 2 (cumulative)
    print("📂 Parsing Round 2 (cumulative)...")
    r2_result = parser.parse_regular_stats_file(round_2_file)
    if not r2_result['success']:
        print("❌ Failed to parse Round 2")
        return False
    
    # Calculate differential
    print("🧮 Calculating Round 2 differential...")
    differential = parser.calculate_round_2_differential(r1_result, r2_result)
    
    print()
    print("=" * 80)
    print("📊 RESULTS")
    print("=" * 80)
    print()
    
    # Find player 'vid' to test
    test_player_name = 'vid'
    
    r1_vid = next((p for p in r1_result['players'] if p['name'] == test_player_name), None)
    r2_vid = next((p for p in r2_result['players'] if p['name'] == test_player_name), None)
    diff_vid = next((p for p in differential['players'] if p['name'] == test_player_name), None)
    
    if not all([r1_vid, r2_vid, diff_vid]):
        print(f"❌ Could not find player '{test_player_name}' in all rounds")
        return False
    
    # Extract time values
    r1_time = r1_vid.get('objective_stats', {}).get('time_played_minutes', 0)
    r2_time_cumulative = r2_vid.get('objective_stats', {}).get('time_played_minutes', 0)
    diff_time = diff_vid.get('objective_stats', {}).get('time_played_minutes', 0)
    
    # Calculate expected differential time
    expected_diff_time = r2_time_cumulative - r1_time
    
    print(f"Player: {test_player_name}")
    print(f"  Round 1 time:           {r1_time:.2f} minutes")
    print(f"  Round 2 cumulative time: {r2_time_cumulative:.2f} minutes")
    print(f"  Expected R2-only time:   {expected_diff_time:.2f} minutes")
    print(f"  Actual differential time: {diff_time:.2f} minutes")
    print()
    
    # Check if the fix worked
    if diff_time == 0.0:
        print("❌ FAIL: time_played_minutes is 0.0 (fix didn't work!)")
        print()
        print("🔍 Debugging info:")
        print(f"  diff_vid keys: {diff_vid.keys()}")
        print(f"  diff_vid['objective_stats']: {diff_vid.get('objective_stats', {})}")
        return False
    
    if abs(diff_time - expected_diff_time) < 0.01:  # Allow small floating point errors
        print("✅ PASS: time_played_minutes correctly calculated!")
        print()
        
        # Also check damage and DPM
        r1_dmg = r1_vid.get('damage_given', 0)
        r2_dmg_cumulative = r2_vid.get('damage_given', 0)
        diff_dmg = diff_vid.get('damage_given', 0)
        diff_dpm = diff_vid.get('dpm', 0)
        
        expected_diff_dmg = r2_dmg_cumulative - r1_dmg
        expected_dpm = expected_diff_dmg / diff_time if diff_time > 0 else 0
        
        print("📈 Additional Stats:")
        print(f"  Round 1 damage:           {r1_dmg}")
        print(f"  Round 2 cumulative damage: {r2_dmg_cumulative}")
        print(f"  Expected R2-only damage:   {expected_diff_dmg}")
        print(f"  Actual differential damage: {diff_dmg}")
        print()
        print(f"  Calculated DPM from damage/time: {expected_dpm:.2f}")
        print(f"  Parser's DPM:                     {diff_dpm:.2f}")
        print()
        
        # Check if DPM calculation is using session time (wrong) or player time (right)
        session_time_seconds = parser.parse_time_to_seconds(differential['actual_time'])
        session_time_minutes = session_time_seconds / 60.0 if session_time_seconds > 0 else 5.0
        session_based_dpm = diff_dmg / session_time_minutes if session_time_minutes > 0 else 0
        
        print("🔬 DPM Calculation Check:")
        print(f"  Session time:         {session_time_minutes:.2f} minutes")
        print(f"  Player time:          {diff_time:.2f} minutes")
        print(f"  Session-based DPM:    {session_based_dpm:.2f} (WRONG if used)")
        print(f"  Player-based DPM:     {expected_dpm:.2f} (CORRECT)")
        print(f"  Parser's DPM:         {diff_dpm:.2f}")
        print()
        
        if abs(diff_dpm - session_based_dpm) < 0.01:
            print("⚠️ WARNING: Parser is using SESSION time for DPM calculation!")
            print("   This is the 'cDPM' issue mentioned in the documentation.")
            print("   DPM should be calculated using PLAYER time, not session time.")
            return True  # Fix works for time preservation, but DPM calc is still wrong
        elif abs(diff_dpm - expected_dpm) < 0.01:
            print("✅ EXCELLENT: Parser is using PLAYER time for DPM calculation!")
            return True
        else:
            print(f"⚠️ UNEXPECTED: Parser DPM doesn't match either calculation method")
            print(f"   Difference from session-based: {abs(diff_dpm - session_based_dpm):.2f}")
            print(f"   Difference from player-based:  {abs(diff_dpm - expected_dpm):.2f}")
            return True  # Time fix works, but DPM calculation is unclear
    else:
        print(f"❌ FAIL: time_played_minutes mismatch!")
        print(f"   Difference: {abs(diff_time - expected_diff_time):.2f}")
        return False

if __name__ == '__main__':
    success = test_round_2_time_preservation()
    print()
    print("=" * 80)
    if success:
        print("✅ Time preservation fix is working!")
    else:
        print("❌ Time preservation fix has issues!")
    print("=" * 80)
