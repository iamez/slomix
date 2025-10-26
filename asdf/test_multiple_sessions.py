#!/usr/bin/env python3
"""
Test the parser with the multiple te_escape2 sessions from 2025-09-29
"""

import sys
import os

# Add the bot directory to the path so we can import the parser
sys.path.append(os.path.join(os.path.dirname(__file__), 'bot'))

from community_stats_parser import C0RNP0RN3StatsParser

def test_multiple_sessions():
    """Test parsing with multiple sessions on the same day"""
    parser = C0RNP0RN3StatsParser()
    
    # Test files from 2025-09-29 (multiple sessions)
    files_to_test = [
        # Session 1: 22:12:49 → 22:20:25
        ("local_stats/2025-09-29-221249-te_escape2-round-1.txt", "Session 1 Round 1"),
        ("local_stats/2025-09-29-222025-te_escape2-round-2.txt", "Session 1 Round 2"),
        
        # Session 2: 22:24:55 → 22:29:00  
        ("local_stats/2025-09-29-222455-te_escape2-round-1.txt", "Session 2 Round 1"),
        ("local_stats/2025-09-29-222900-te_escape2-round-2.txt", "Session 2 Round 2"),
        
        # Session 3: 22:33:38 → 22:38:14
        ("local_stats/2025-09-29-223338-te_escape2-round-1.txt", "Session 3 Round 1"),
        ("local_stats/2025-09-29-223814-te_escape2-round-2.txt", "Session 3 Round 2"),
    ]
    
    print("=== Testing Multiple te_escape2 Sessions on Same Day ===")
    print("Date: 2025-09-29")
    print()
    
    for file_path, description in files_to_test:
        if os.path.exists(file_path):
            print(f"🔍 {description}: {os.path.basename(file_path)}")
            result = parser.parse_stats_file(file_path)
            
            if result['success']:
                differential = result.get('differential_calculation', False)
                print(f"   ✅ Success | Players: {result['total_players']} | Differential: {differential}")
                
                if differential:
                    # Show which Round 1 file was matched
                    print(f"   📂 This should match the immediately preceding Round 1 in this session")
                    
                    # Show top player for verification
                    if result['players']:
                        top_player = max(result['players'], key=lambda x: x['dpm'])
                        print(f"   🏆 Top DPM: {top_player['name']} - {top_player['dpm']:.1f} DPM")
                        
                        # Check if DPM is realistic
                        if 50 <= top_player['dpm'] <= 1000:
                            print(f"   ✅ DPM looks realistic")
                        else:
                            print(f"   ⚠️ DPM might be wrong (expected 50-1000)")
                
            else:
                print(f"   ❌ Failed: {result.get('error', 'Unknown error')}")
            print()
    
    print("🔧 If any Round 2 files are matching wrong Round 1 files,")
    print("   we need to improve the session grouping logic!")

if __name__ == "__main__":
    test_multiple_sessions()