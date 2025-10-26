"""
Deep dive into time calculation pipeline.
Let's verify EXACTLY what the numbers mean.
"""
import sys
sys.path.insert(0, 'G:\\VisualStudio\\Python\\stats')

def check_raw_file_directly():
    """Read raw file and check actual values."""
    
    test_file = 'local_stats/2025-10-02-211808-etl_adlernest-round-1.txt'
    
    print("=" * 100)
    print("🔬 RAW FILE ANALYSIS - Checking Actual Values")
    print("=" * 100)
    print()
    
    with open(test_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    # Header
    header = lines[0].strip()
    print("📋 HEADER (RAW):")
    print(f"  {repr(header)}")
    print()
    
    header_parts = header.split('\\')
    print("📋 HEADER PARTS:")
    for i, part in enumerate(header_parts):
        print(f"  [{i}]: {repr(part)}")
    print()
    
    # Focus on time fields
    if len(header_parts) >= 8:
        map_time = header_parts[6]
        actual_time = header_parts[7]
        
        print("⏱️  TIME FIELDS FROM HEADER:")
        print(f"  Part [6] Map Time:    {repr(map_time)}")
        print(f"  Part [7] Actual Time: {repr(actual_time)}")
        print()
        
        # Parse actual_time
        if ':' in actual_time:
            parts = actual_time.split(':')
            minutes = int(parts[0])
            seconds = int(parts[1])
            total_seconds = minutes * 60 + seconds
            total_minutes_decimal = total_seconds / 60.0
            
            print("🧮 CALCULATING SESSION TIME:")
            print(f"  Raw string:    {repr(actual_time)}")
            print(f"  Minutes part:  {minutes}")
            print(f"  Seconds part:  {seconds}")
            print(f"  Total seconds: {total_seconds}")
            print(f"  As decimal:    {total_minutes_decimal:.4f} minutes")
            print(f"  Rounded:       {total_minutes_decimal:.2f} minutes")
            print()
            
            # Wait... is this MM:SS or M:SS?
            print("❓ QUESTION: Is 3:51 actually:")
            print(f"  A) 3 minutes 51 seconds = 3 + (51/60) = {3 + 51/60:.4f} = 3.85 min ✅")
            print(f"  B) 3:51 format (3h 51m)?  = 3*60 + 51 = {3*60 + 51:.2f} min ❌ (unlikely)")
            print()
    
    # Now check player lines
    print("👤 PLAYER DATA (Field 22 - time_played_minutes):")
    print()
    print(f"{'Player':<20} {'Field 22 (raw)':<20} {'As Float':<15} {'Interpretation':<30}")
    print("-" * 100)
    
    for i, line in enumerate(lines[1:6], 1):  # First 5 players
        if not line.strip() or '\\' not in line:
            continue
        
        parts = line.strip().split('\\')
        if len(parts) < 23:
            continue
        
        name = parts[0]
        field_22_raw = parts[22]
        field_22_float = float(field_22_raw)
        
        # Is this already in minutes? Or seconds?
        as_seconds = field_22_float
        as_minutes = field_22_float
        from_seconds = field_22_float / 60.0
        
        print(f"{name:<20} {repr(field_22_raw):<20} {field_22_float:<15.2f} Already minutes? {as_minutes:.2f} min")
    
    print()
    print("🧐 OBSERVATIONS:")
    print("  Session time: 3:51 = 231 seconds = 3.85 minutes")
    print("  Player Field 22: 3.90 (already in minutes)")
    print()
    print("  Player time is GREATER than session time!")
    print("  3.90 min > 3.85 min by 0.05 minutes (3 seconds)")
    print()
    print("❓ How can player time be LONGER than session time?")
    print("  - Maybe Field 22 includes something session doesn't?")
    print("  - Maybe Field 22 is cumulative from previous rounds?")
    print("  - Maybe rounding/calculation difference?")
    print()

def check_field_22_meaning():
    """Check what Field 22 actually represents."""
    
    print("=" * 100)
    print("🔍 INVESTIGATING: What is Field 22?")
    print("=" * 100)
    print()
    
    # Check Round 1 and Round 2
    round_1 = 'local_stats/2025-10-02-211808-etl_adlernest-round-1.txt'
    round_2 = 'local_stats/2025-10-02-212249-etl_adlernest-round-2.txt'
    
    def get_vid_time(filepath):
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        # Get session time from header
        header = lines[0].strip()
        header_parts = header.split('\\')
        session_time_str = header_parts[7] if len(header_parts) > 7 else "0:00"
        
        # Parse to minutes
        if ':' in session_time_str:
            parts = session_time_str.split(':')
            session_min = int(parts[0]) + int(parts[1]) / 60.0
        else:
            session_min = 0.0
        
        # Find vid's Field 22
        for line in lines[1:]:
            if line.startswith('vid\\'):
                parts = line.strip().split('\\')
                if len(parts) > 22:
                    field_22 = float(parts[22])
                    return session_min, field_22
        return session_min, 0.0
    
    r1_session, r1_field22 = get_vid_time(round_1)
    r2_session, r2_field22 = get_vid_time(round_2)
    
    print("📊 ROUND 1:")
    print(f"  Session time (header): {r1_session:.2f} min")
    print(f"  vid Field 22:          {r1_field22:.2f} min")
    print(f"  Difference:            {r1_field22 - r1_session:.2f} min")
    print()
    
    print("📊 ROUND 2 (CUMULATIVE FILE):")
    print(f"  Session time (header): {r2_session:.2f} min (just R2)")
    print(f"  vid Field 22:          {r2_field22:.2f} min (cumulative?)")
    print(f"  Difference:            {r2_field22 - r2_session:.2f} min")
    print()
    
    print("🧮 CALCULATION:")
    print(f"  R1 Field 22:           {r1_field22:.2f} min")
    print(f"  R2 Field 22:           {r2_field22:.2f} min")
    print(f"  Difference:            {r2_field22 - r1_field22:.2f} min (R2 only)")
    print(f"  R2 Session time:       {r2_session:.2f} min")
    print()
    
    if abs(r2_field22 - r1_field22 - r2_session) < 0.1:
        print("✅ R2 Field 22 is CUMULATIVE (R1 + R2)")
        print(f"   Proof: {r2_field22:.2f} - {r1_field22:.2f} = {r2_field22 - r1_field22:.2f} ≈ {r2_session:.2f}")
    else:
        print("❌ R2 Field 22 is NOT simply cumulative")
    print()
    
    print("💡 HYPOTHESIS:")
    print("  Field 22 might be cumulative time across rounds,")
    print("  but header session time is only for THAT round.")
    print()
    print("  For Round 1: Both should be similar (first round)")
    print(f"  Expected: ~{r1_session:.2f} min")
    print(f"  Actual:   {r1_field22:.2f} min")
    print(f"  Diff:     {r1_field22 - r1_session:.2f} min ({(r1_field22 - r1_session) / r1_session * 100:.1f}%)")
    print()

def check_console_log_sample():
    """Check if console.log exists and show last 1000 lines."""
    
    import os
    import glob
    
    print("=" * 100)
    print("🔍 SEARCHING FOR CONSOLE LOG")
    print("=" * 100)
    print()
    
    # Search for console log files
    possible_paths = [
        'logs/console.log',
        'logs/etconsole.log',
        'server/etconsole.log',
        'etconsole.log',
        '*/console.log',
        '*/etconsole.log'
    ]
    
    for pattern in possible_paths:
        matches = glob.glob(pattern, recursive=True)
        if matches:
            print(f"✅ Found: {matches}")
        else:
            print(f"❌ Not found: {pattern}")
    
    print()
    print("💡 TO GET LAST 1000 LINES FROM CONSOLE LOG:")
    print("   PowerShell: Get-Content console.log -Tail 1000")
    print("   Or: Get-Content console.log -Tail 1000 | Select-String '2025-10-02'")
    print()
    print("🔍 WHAT TO LOOK FOR:")
    print("   - Session start/end timestamps")
    print("   - Player connect/disconnect")
    print("   - Round start/end markers")
    print("   - Time-related debug output")
    print()

if __name__ == '__main__':
    check_raw_file_directly()
    check_field_22_meaning()
    check_console_log_sample()
