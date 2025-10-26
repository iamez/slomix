#!/usr/bin/env python3
"""
Test the developer's GameStats.py with our real stats files
"""
import sys
import os

# Copy the developer files to test them
def test_developer_parser():
    """Test the original developer GameStats parser with our files"""
    
    # First, let's examine the format they expect
    test_file = "./test_files/2025-09-24-233255-te_escape2-round-1.txt"
    
    print("🔍 Analyzing stats file format...")
    print("=" * 50)
    
    with open(test_file, 'r') as f:
        lines = f.readlines()
        
    print(f"📁 File: {test_file}")
    print(f"📊 Total lines: {len(lines)}")
    print()
    
    # Parse header
    header = lines[0].strip().split('\\')
    print("📋 HEADER:")
    print(f"   Server: {header[0]}")
    print(f"   Map: {header[1]}")
    print(f"   Config: {header[2]}")
    print(f"   Round: {header[3]}")
    print(f"   Defender: {header[4]}")
    print(f"   Winner: {header[5]}")
    print(f"   Timelimit: {header[6]}")
    print(f"   NextTimelimit: {header[7]}")
    print()
    
    print("👤 PLAYERS:")
    for i, line in enumerate(lines[1:], 1):
        if line.strip():
            parts = line.strip().split('\\')
            if len(parts) >= 4:
                guid = parts[0]
                name = parts[1] 
                rounds = parts[2]
                team = parts[3]
                stats_part = parts[4] if len(parts) > 4 else ""
                
                print(f"   Player {i}:")
                print(f"     GUID: {guid}")
                print(f"     Name: {name}")
                print(f"     Rounds: {rounds}")
                print(f"     Team: {team}")
                
                # Parse stats part
                if stats_part:
                    stats = stats_part.split()
                    if len(stats) > 10:
                        # Try to find damage and time data
                        print(f"     Stats length: {len(stats)}")
                        print(f"     First 10 stats: {stats[:10]}")
                        print(f"     Last 10 stats: {stats[-10:]}")
                        
                        # Look for damage given (should be around index 25-30 in c0rnp0rn3 format)
                        if len(stats) > 30:
                            try:
                                damage_given = int(stats[29])  # Based on c0rnp0rn3 format
                                time_played = float(stats[32])  # Based on c0rnp0rn3 format
                                print(f"     🎯 Damage Given: {damage_given}")
                                print(f"     ⏱️  Time Played: {time_played}")
                                
                                if time_played > 0:
                                    dpm = damage_given / (time_played / 60.0)
                                    print(f"     📊 Calculated DPM: {dpm:.1f}")
                                    
                            except (ValueError, IndexError) as e:
                                print(f"     ❌ Could not parse damage/time: {e}")
                                
                print()
                
                if i >= 3:  # Just show first 3 players for brevity
                    break

if __name__ == "__main__":
    test_developer_parser()