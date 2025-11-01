"""
Detailed Round-by-Round Breakdown with Times
Shows score AND completion time for each round to verify Stopwatch scoring
"""
import os
import re

def parse_stats_file(filepath):
    """Parse a stats file and extract header data."""
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    if not lines:
        return None
    
    header = lines[0].strip()
    # Split by backslash and take the last 6 parts (the actual data)
    parts = header.split('\\')
    # Header format: <server_info>\<map>\<modname>\<score1>\<score2>\<time_limit>\<actual_time>
    # We need the last 6 parts
    if len(parts) < 6:
        return None
    
    # Take last 6 parts
    parts = parts[-6:]
    
    data = {
        'map': parts[0],
        'modname': parts[1],
        'score1': int(parts[2]),  # Axis score
        'score2': int(parts[3]),  # Allies score
        'time_limit': parts[4],
        'actual_time': parts[5]
    }
    return data

def time_to_seconds(time_str):
    """Convert MM:SS time to seconds."""
    if ':' not in time_str:
        return 0
    parts = time_str.split(':')
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    return 0

def main():
    stats_dir = 'local_stats'
    
    # Get all October 2nd files
    oct2_files = []
    for filename in os.listdir(stats_dir):
        if filename.startswith("2025-10-02") and filename.endswith(".txt"):
            oct2_files.append(filename)
    
    oct2_files.sort()
    
    print("=" * 100)
    print("🔍 DETAILED ROUND-BY-ROUND BREAKDOWN - October 2nd, 2025")
    print("=" * 100)
    print()
    print("STOPWATCH SCORING RULES:")
    print("• Round 1: Team A attacks (Allies), Team B defends (Axis)")
    print("• Round 2: Teams swap - Team B attacks (Allies), Team A defends (Axis)")
    print("• If attacker completes objectives (score=2): +1 point")
    print("• If defender holds (score=1): attacker gets 0 points")
    print("• If both complete: Faster time wins (+1 bonus point)")
    print("• If R1 completes but R2 fails: R1 team gets +1 defense point")
    print("=" * 100)
    print()
    
    # Group files by map
    matches = []
    i = 0
    while i < len(oct2_files) - 1:
        file1 = oct2_files[i]
        file2 = oct2_files[i + 1]
        
        if "round-1" in file1 and "round-2" in file2:
            matches.append((file1, file2))
            i += 2
        else:
            i += 1
    
    team_a_total = 0
    team_b_total = 0
    
    for idx, (file1, file2) in enumerate(matches, 1):
        r1_data = parse_stats_file(os.path.join(stats_dir, file1))
        r2_data = parse_stats_file(os.path.join(stats_dir, file2))
        
        print(f"\n{'='*100}")
        print(f"MATCH #{idx}: {r1_data['map']}")
        print(f"{'='*100}")
        
        # Round 1 Analysis
        print(f"\n📍 ROUND 1:")
        print(f"   Team A (Allies - ATTACK) vs Team B (Axis - DEFEND)")
        print(f"   Scores: Axis {r1_data['score1']} - Allies {r1_data['score2']}")
        print(f"   Time: {r1_data['actual_time']} / {r1_data['time_limit']}")
        
        r1_team_a_completed = (r1_data['score2'] == 2)
        r1_time_seconds = time_to_seconds(r1_data['actual_time']) if r1_team_a_completed else 999999
        
        if r1_team_a_completed:
            print(f"   ✅ Team A COMPLETED objectives in {r1_data['actual_time']}")
        else:
            print(f"   ❌ Team A FAILED (held by Team B)")
        
        # Round 2 Analysis
        print(f"\n📍 ROUND 2:")
        print(f"   Team B (Allies - ATTACK) vs Team A (Axis - DEFEND)")
        print(f"   Scores: Axis {r2_data['score1']} - Allies {r2_data['score2']}")
        print(f"   Time: {r2_data['actual_time']} / {r2_data['time_limit']}")
        
        r2_team_b_completed = (r2_data['score2'] == 2)
        r2_time_seconds = time_to_seconds(r2_data['actual_time']) if r2_team_b_completed else 999999
        
        if r2_team_b_completed:
            print(f"   ✅ Team B COMPLETED objectives in {r2_data['actual_time']}")
        else:
            print(f"   ❌ Team B FAILED (held by Team A)")
        
        # Scoring Logic
        print(f"\n🏆 SCORING:")
        team_a_points = 0
        team_b_points = 0
        
        if r1_team_a_completed and r2_team_b_completed:
            # Both completed - compare times
            print(f"   Both teams completed objectives!")
            print(f"   Team A time: {r1_data['actual_time']} ({r1_time_seconds}s)")
            print(f"   Team B time: {r2_data['actual_time']} ({r2_time_seconds}s)")
            
            if r2_time_seconds < r1_time_seconds:
                team_b_points = 2
                print(f"   → Team B was FASTER by {r1_time_seconds - r2_time_seconds}s")
                print(f"   → Team B: +2 points (WIN)")
            elif r1_time_seconds < r2_time_seconds:
                team_a_points = 2
                print(f"   → Team A was FASTER by {r2_time_seconds - r1_time_seconds}s")
                print(f"   → Team A: +2 points (WIN)")
            else:
                team_a_points = 1
                team_b_points = 1
                print(f"   → SAME TIME!")
                print(f"   → Both teams: +1 point (TIE)")
        
        elif r1_team_a_completed and not r2_team_b_completed:
            # Team A completed, Team B failed (full hold)
            team_a_points = 2
            print(f"   Team A completed, Team B held by Team A")
            print(f"   → Team A: +2 points (WIN - completed + defense)")
        
        elif not r1_team_a_completed and r2_team_b_completed:
            # Team A failed, Team B completed (full hold)
            team_b_points = 2
            print(f"   Team A held by Team B, Team B completed")
            print(f"   → Team B: +2 points (WIN - defense + completed)")
        
        else:
            # Both failed (double full hold)
            print(f"   Both teams held by defense (no objectives completed)")
            print(f"   → 0-0 (TIE)")
        
        print(f"\n   📊 Match Result: Team A {team_a_points} - {team_b_points} Team B")
        
        team_a_total += team_a_points
        team_b_total += team_b_points
        
        if team_a_points > team_b_points:
            print(f"   🏆 Winner: Team A")
        elif team_b_points > team_a_points:
            print(f"   🏆 Winner: Team B")
        else:
            print(f"   🤝 TIE")
    
    # Final Totals
    print(f"\n\n{'='*100}")
    print(f"📊 FINAL SESSION TOTALS")
    print(f"{'='*100}")
    print(f"\nTeam A (SuperBoyy, qmr, SmetarskiProner): {team_a_total} points")
    print(f"Team B (vid, endekk, .olz): {team_b_total} points")
    print()
    
    if team_a_total > team_b_total:
        win_pct = (team_a_total / (team_a_total + team_b_total)) * 100
        print(f"🏆 WINNER: Team A ({team_a_total}-{team_b_total}, {win_pct:.1f}%)")
    elif team_b_total > team_a_total:
        win_pct = (team_b_total / (team_a_total + team_b_total)) * 100
        print(f"🏆 WINNER: Team B ({team_b_total}-{team_a_total}, {win_pct:.1f}%)")
    else:
        print(f"🤝 SESSION TIE: {team_a_total}-{team_b_total}")
    
    print(f"{'='*100}")

if __name__ == "__main__":
    main()
