#!/usr/bin/env python3
"""
Test the bot's community_stats_parser.py with real stats files
"""
import sys
import os

# Add the bot directory to the path
sys.path.append('./bot')

try:
    from community_stats_parser import C0RNP0RN3StatsParser
except ImportError:
    print("❌ Could not import community_stats_parser")
    sys.exit(1)

def test_bot_parser():
    """Test the bot's parser with real files"""
    
    print("🤖 Testing Bot's C0RNP0RN3StatsParser...")
    print("=" * 50)
    
    parser = C0RNP0RN3StatsParser()
    test_file = "./test_files/2025-09-24-233255-te_escape2-round-1.txt"
    
    try:
        with open(test_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        print(f"📁 Parsing: {test_file}")
        print(f"📊 File size: {len(content)} characters")
        print()
        
        # Try to parse the file content
        # Note: The parser methods may expect different input formats
        # Let's examine what methods are available
        
        print("🔍 Available parser methods:")
        methods = [method for method in dir(parser) if not method.startswith('_')]
        for method in methods:
            print(f"   - {method}")
        print()
        
        # Let's try to see how the parser works by looking at its methods
        # First, let's check if it has a parse method
        
        lines = content.strip().split('\n')
        header = lines[0]
        player_lines = lines[1:]
        
        print(f"📋 Header: {header}")
        print(f"👥 Players: {len(player_lines)}")
        print()
        
        # Test parsing each player line
        for i, line in enumerate(player_lines[:2], 1):  # Test first 2 players
            print(f"👤 Player {i}:")
            print(f"   Raw line: {line[:100]}...")
            
            # Try to parse the line manually based on what we learned
            parts = line.split('\\')
            if len(parts) >= 5:
                guid = parts[0]
                name = parser.strip_color_codes(parts[1])
                team = int(parts[3])
                stats_part = parts[4]
                
                print(f"   GUID: {guid}")
                print(f"   Name: {name}")
                print(f"   Team: {team}")
                
                # Parse the stats part
                stats = stats_part.split()
                weapon_mask = int(stats[0])
                weapon_count = bin(weapon_mask).count('1')
                weapon_stats_end = 1 + (weapon_count * 5)
                
                if len(stats) > weapon_stats_end + 9:
                    player_stats = stats[weapon_stats_end:]
                    damage_given = int(player_stats[0])
                    time_played = float(player_stats[8])
                    
                    print(f"   💥 Damage: {damage_given}")
                    print(f"   ⏱️  Time: {time_played}")
                    
                    # Test different DPM calculations
                    if time_played > 0:
                        # Bot's method might be wrong - let's see
                        dpm_percentage = damage_given / (time_played / 100.0 * 12)  # 12 min round
                        dpm_direct = damage_given / time_played
                        dpm_seconds = damage_given / (time_played / 60.0)
                        
                        print(f"   📊 DPM calculations:")
                        print(f"     As percentage of round: {dpm_percentage:.1f}")
                        print(f"     Direct division: {dpm_direct:.1f}")
                        print(f"     As seconds: {dpm_seconds:.1f}")
                
            print()
            
    except Exception as e:
        print(f"❌ Error testing bot parser: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_bot_parser()