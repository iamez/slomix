"""
Pipeline Investigation: Session Time vs Player Time
Show actual samples to understand the difference.
"""
import sys
sys.path.insert(0, 'G:\\VisualStudio\\Python\\stats')

from bot.community_stats_parser import C0RNP0RN3StatsParser
import os

def parse_time_to_seconds(time_str):
    """Convert time string like '3:51' to seconds."""
    if ':' in time_str:
        parts = time_str.split(':')
        minutes = int(parts[0])
        seconds = int(parts[1])
        return minutes * 60 + seconds
    return 0

def investigate_time_sources():
    """Compare session time vs player time across multiple files."""
    
    parser = C0RNP0RN3StatsParser()
    
    # Test files from October 2
    test_files = [
        'local_stats/2025-10-02-211808-etl_adlernest-round-1.txt',
        'local_stats/2025-10-02-212249-etl_adlernest-round-2.txt',
    ]
    
    print("=" * 100)
    print("🔍 PIPELINE INVESTIGATION: Session Time vs Player Time")
    print("=" * 100)
    print()
    
    for file_path in test_files:
        if not os.path.exists(file_path):
            print(f"⚠️  File not found: {file_path}")
            continue
            
        print(f"📂 File: {os.path.basename(file_path)}")
        print("-" * 100)
        
        # Read raw file to get header info
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            
        if len(lines) < 2:
            print("❌ File too short")
            continue
            
        # Parse header
        header = lines[0].strip()
        header_parts = header.split('\\')
        
        if len(header_parts) < 8:
            print("❌ Invalid header format")
            continue
            
        server_name = header_parts[0]
        map_name = header_parts[1]
        round_num = header_parts[3]
        map_time = header_parts[6]      # Time limit
        actual_time = header_parts[7]   # Actual round duration
        
        # Calculate session time in minutes
        session_seconds = parse_time_to_seconds(actual_time)
        session_minutes = session_seconds / 60.0
        
        print(f"\n📋 HEADER INFO:")
        print(f"  Map: {map_name}")
        print(f"  Round: {round_num}")
        print(f"  Map Time (limit): {map_time}")
        print(f"  Actual Time (session): {actual_time} = {session_seconds} seconds = {session_minutes:.2f} minutes")
        print()
        
        # Parse with parser to get player data
        result = parser.parse_regular_stats_file(file_path)
        
        if not result['success']:
            print("❌ Parser failed")
            continue
            
        print(f"👥 PLAYER TIME DATA (Field 22 - time_played_minutes):")
        print()
        print(f"{'Player':<20} {'Field22 (min)':<15} {'Damage':<10} {'Session DPM':<15} {'Player DPM':<15} {'Diff':<10}")
        print("-" * 100)
        
        for player in result['players'][:10]:  # First 10 players
            player_name = player.get('name', 'Unknown')
            damage = player.get('damage_given', 0)
            
            # Get player time from Field 22 (stored in objective_stats)
            player_time = player.get('objective_stats', {}).get('time_played_minutes', 0)
            
            # Calculate DPM both ways
            session_dpm = damage / session_minutes if session_minutes > 0 else 0
            player_dpm = damage / player_time if player_time > 0 else 0
            
            diff = player_dpm - session_dpm
            diff_pct = (diff / session_dpm * 100) if session_dpm > 0 else 0
            
            print(f"{player_name:<20} {player_time:<15.2f} {damage:<10} {session_dpm:<15.2f} {player_dpm:<15.2f} {diff:>+7.2f} ({diff_pct:+.1f}%)")
        
        print()
        print("🔬 ANALYSIS:")
        
        # Calculate statistics
        player_times = [p.get('objective_stats', {}).get('time_played_minutes', 0) for p in result['players']]
        player_times = [t for t in player_times if t > 0]  # Remove zeros
        
        if player_times:
            avg_player_time = sum(player_times) / len(player_times)
            min_player_time = min(player_times)
            max_player_time = max(player_times)
            
            print(f"  Session time:        {session_minutes:.2f} minutes")
            print(f"  Avg player time:     {avg_player_time:.2f} minutes")
            print(f"  Min player time:     {min_player_time:.2f} minutes")
            print(f"  Max player time:     {max_player_time:.2f} minutes")
            print(f"  Range:               {max_player_time - min_player_time:.2f} minutes")
            print(f"  Diff from session:   {avg_player_time - session_minutes:.2f} minutes ({(avg_player_time - session_minutes) / session_minutes * 100:.1f}%)")
            
            # Check if all players have same time
            if max_player_time - min_player_time < 0.1:
                print(f"  ✅ All players have essentially SAME time (competitive environment confirmed)")
            else:
                print(f"  ⚠️  Players have DIFFERENT times (range: {max_player_time - min_player_time:.2f} min)")
        else:
            print("  ❌ No player time data available")
        
        print()
        print("=" * 100)
        print()

def check_raw_field_22():
    """Check what Field 22 actually contains in raw files."""
    
    print("\n" + "=" * 100)
    print("🔬 RAW DATA CHECK: What is Field 22?")
    print("=" * 100)
    print()
    
    test_file = 'local_stats/2025-10-02-211808-etl_adlernest-round-1.txt'
    
    if not os.path.exists(test_file):
        print(f"⚠️  File not found: {test_file}")
        return
    
    with open(test_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    # Parse header
    header = lines[0].strip()
    header_parts = header.split('\\')
    actual_time = header_parts[7] if len(header_parts) > 7 else "Unknown"
    
    session_seconds = parse_time_to_seconds(actual_time)
    session_minutes = session_seconds / 60.0
    
    print(f"📂 File: {os.path.basename(test_file)}")
    print(f"Session Time (header): {actual_time} = {session_minutes:.2f} minutes")
    print()
    print(f"{'Player':<20} {'Field 20':<12} {'Field 21':<12} {'Field 22':<12} {'Field 23':<12}")
    print(f"{'(name)':<20} {'(bullets)':<12} {'(dpm)':<12} {'(time?)':<12} {'(tank?)':<12}")
    print("-" * 100)
    
    for line in lines[1:11]:  # First 10 players
        if not line.strip() or '\\' not in line:
            continue
            
        parts = line.strip().split('\\')
        if len(parts) < 24:
            continue
            
        name = parts[0]
        field_20 = parts[20] if len(parts) > 20 else "N/A"  # bullets
        field_21 = parts[21] if len(parts) > 21 else "N/A"  # dpm (should be 0.0)
        field_22 = parts[22] if len(parts) > 22 else "N/A"  # time_played
        field_23 = parts[23] if len(parts) > 23 else "N/A"  # tank_meatshield
        
        print(f"{name:<20} {field_20:<12} {field_21:<12} {field_22:<12} {field_23:<12}")
    
    print()
    print("📝 OBSERVATIONS:")
    print("  - Field 20: bullets_fired (integer)")
    print("  - Field 21: DPM from lua (should be 0.0)")
    print("  - Field 22: time_played_minutes (THIS is what we read)")
    print("  - Field 23: tank_meatshield (float)")
    print()

if __name__ == '__main__':
    investigate_time_sources()
    check_raw_field_22()
    
    print("\n" + "=" * 100)
    print("💡 QUESTIONS FOR YOU:")
    print("=" * 100)
    print()
    print("1. Do all players have the SAME time? (competitive = yes)")
    print("2. Is player time CLOSE to session time? (should be)")
    print("3. What causes small differences? (death time? respawn time?)")
    print("4. Which time do you want to use for DPM?")
    print("   - Session time = Simple, always available, same for all")
    print("   - Player time = Slightly more accurate, accounts for deaths")
    print()
    print("Based on the samples above, which one represents 'full length of round'?")
    print("=" * 100)
