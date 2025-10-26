"""
Complete Round-by-Round Analysis with Player Teams
Shows which ACTUAL team attacked first and who was on which side
"""
import os
import json

# Known team rosters from session_teams table
TEAM_A_GUIDS = ['9BCDBB6D', '9E21C51D', 'D7EE4F38']  # SuperBoyy, qmr, SmetarskiProner
TEAM_B_GUIDS = ['5C3D0BC7', 'D8423F90', 'E16F9C0A']  # .olz, vid, endekk

def parse_file(filepath):
    """Parse stats file to get header and player data."""
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    if not lines:
        return None
    
    # Parse header
    header = lines[0].strip()
    parts = header.split('\\')[-6:]
    
    # Parse players
    players = []
    for line in lines[1:]:
        if line.strip():
            player_parts = line.split('\\')
            if len(player_parts) > 6:
                name = player_parts[0].strip()
                guid = player_parts[5].strip()
                team = player_parts[6].strip()  # '1' = Axis, '2' = Allies
                
                # Clean name of color codes
                import re
                name_clean = re.sub(r'\^.', '', name)
                
                if guid and len(guid) == 8:
                    players.append({
                        'name': name_clean,
                        'guid': guid,
                        'side': 'Axis' if team == '1' else 'Allies' if team == '2' else 'Unknown'
                    })
    
    return {
        'map': parts[0],
        'score1': int(parts[2]),  # Axis score
        'score2': int(parts[3]),  # Allies score
        'time_limit': parts[4],
        'time': parts[5],
        'players': players
    }


def identify_team_sides(players):
    """Figure out which team (A or B) is on which side (Axis or Allies)."""
    team_a_on_axis = 0
    team_a_on_allies = 0
    
    for player in players:
        if player['guid'] in TEAM_A_GUIDS:
            if player['side'] == 'Axis':
                team_a_on_axis += 1
            elif player['side'] == 'Allies':
                team_a_on_allies += 1
    
    if team_a_on_axis > team_a_on_allies:
        return 'Team A on Axis, Team B on Allies'
    else:
        return 'Team A on Allies, Team B on Axis'


def main():
    stats_dir = 'local_stats'
    
    # Get all October 2nd files
    oct2_files = sorted([f for f in os.listdir(stats_dir) 
                        if f.startswith("2025-10-02") and f.endswith(".txt")])
    
    print("=" * 100)
    print("🔍 COMPLETE ROUND-BY-ROUND ANALYSIS - October 2nd, 2025")
    print("=" * 100)
    print()
    print("TEAM ROSTERS:")
    print("  Team A (GUIDs): SuperBoyy (9BCDBB6D), qmr (9E21C51D), SmetarskiProner (D7EE4F38)")
    print("  Team B (GUIDs): .olz (5C3D0BC7), vid (D8423F90), endekk (E16F9C0A)")
    print()
    print("STOPWATCH RULES:")
    print("  • In Stopwatch, teams play BOTH sides of each map")
    print("  • Round 1: One team attacks (Allies), other defends (Axis)")
    print("  • Round 2: Teams SWAP - attackers become defenders and vice versa")
    print("  • Attacker tries to complete objectives and set a time")
    print("  • Defender tries to hold and prevent completion")
    print("  • If both complete: Faster time wins")
    print("  • If only one completes: That team wins")
    print("=" * 100)
    print()
    
    # Group into matches
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
    
    total_team_a_wins = 0
    total_team_b_wins = 0
    
    for match_num, (file1, file2) in enumerate(matches, 1):
        r1 = parse_file(os.path.join(stats_dir, file1))
        r2 = parse_file(os.path.join(stats_dir, file2))
        
        print(f"\n{'='*100}")
        print(f"MATCH #{match_num}: {r1['map']}")
        print(f"{'='*100}")
        
        # Figure out which team was on which side in R1
        r1_sides = identify_team_sides(r1['players'])
        r2_sides = identify_team_sides(r2['players'])
        
        print(f"\n📍 ROUND 1:")
        print(f"   Sides: {r1_sides}")
        print(f"   Scores: Axis {r1['score1']} - Allies {r1['score2']}")
        print(f"   Time: {r1['time']} (limit: {r1['time_limit']})")
        print(f"   Players:")
        for p in r1['players']:
            team = "Team A" if p['guid'] in TEAM_A_GUIDS else "Team B" if p['guid'] in TEAM_B_GUIDS else "Unknown"
            print(f"      {p['name']:20} - {p['side']:8} - {team}")
        
        print(f"\n📍 ROUND 2:")
        print(f"   Sides: {r2_sides}")
        print(f"   Scores: Axis {r2['score1']} - Allies {r2['score2']}")
        print(f"   Time: {r2['time']} (limit: {r2['time_limit']})")
        print(f"   Players:")
        for p in r2['players']:
            team = "Team A" if p['guid'] in TEAM_A_GUIDS else "Team B" if p['guid'] in TEAM_B_GUIDS else "Unknown"
            print(f"      {p['name']:20} - {p['side']:8} - {team}")
        
        # Determine winner
        print(f"\n🏆 SCORING LOGIC:")
        
        # Figure out who was attacking in R1
        if 'Team A on Allies' in r1_sides:
            # Team A attacked first (Allies in R1)
            r1_attacker = "Team A"
            r1_defender = "Team B"
            r1_attack_score = r1['score2']  # Allies score
            r1_attack_time = r1['time']
            
            # Team B attacks in R2 (Allies in R2)
            r2_attacker = "Team B"
            r2_defender = "Team A"
            r2_attack_score = r2['score2']  # Allies score
            r2_attack_time = r2['time']
        else:
            # Team B attacked first (Allies in R1)
            r1_attacker = "Team B"
            r1_defender = "Team A"
            r1_attack_score = r1['score2']
            r1_attack_time = r1['time']
            
            # Team A attacks in R2
            r2_attacker = "Team A"
            r2_defender = "Team B"
            r2_attack_score = r2['score2']
            r2_attack_time = r2['time']
        
        print(f"   R1: {r1_attacker} attacks (Allies) vs {r1_defender} defends (Axis)")
        r1_completed = (r1_attack_score == 2)
        if r1_completed:
            print(f"       ✅ {r1_attacker} COMPLETED objectives in {r1_attack_time}")
        else:
            print(f"       ❌ {r1_attacker} FAILED to complete (full hold by {r1_defender})")
        
        print(f"\n   R2: {r2_attacker} attacks (Allies) vs {r2_defender} defends (Axis)")
        r2_completed = (r2_attack_score == 2)
        if r2_completed:
            print(f"       ✅ {r2_attacker} COMPLETED objectives in {r2_attack_time}")
        else:
            print(f"       ❌ {r2_attacker} FAILED to complete (full hold by {r2_defender})")
        
        # Determine winner
        print(f"\n   📊 RESULT:")
        if r1_completed and r2_completed:
            # Both completed - compare times
            def time_to_seconds(t):
                parts = t.split(':')
                return int(parts[0]) * 60 + int(parts[1])
            
            r1_seconds = time_to_seconds(r1_attack_time)
            r2_seconds = time_to_seconds(r2_attack_time)
            
            print(f"       Both teams completed!")
            print(f"       {r1_attacker}: {r1_attack_time} ({r1_seconds}s)")
            print(f"       {r2_attacker}: {r2_attack_time} ({r2_seconds}s)")
            
            if r1_seconds < r2_seconds:
                winner = r1_attacker
                diff = r2_seconds - r1_seconds
                print(f"       → {winner} WINS by {diff}s (faster)")
            elif r2_seconds < r1_seconds:
                winner = r2_attacker
                diff = r1_seconds - r2_seconds
                print(f"       → {winner} WINS by {diff}s (faster)")
            else:
                winner = "TIE"
                print(f"       → TIE (same time)")
        elif r1_completed and not r2_completed:
            winner = r1_attacker
            print(f"       → {winner} WINS (completed + successful defense)")
        elif not r1_completed and r2_completed:
            winner = r2_attacker
            print(f"       → {winner} WINS (defense + completed)")
        else:
            winner = "TIE"
            print(f"       → TIE (double full hold)")
        
        print(f"\n   🏆 WINNER: {winner}")
        
        if winner == "Team A":
            total_team_a_wins += 1
        elif winner == "Team B":
            total_team_b_wins += 1
    
    # Final summary
    print(f"\n\n{'='*100}")
    print(f"📊 FINAL SESSION RESULTS")
    print(f"{'='*100}")
    print(f"\nTeam A (SuperBoyy, qmr, SmetarskiProner): {total_team_a_wins} maps won")
    print(f"Team B (vid, endekk, .olz): {total_team_b_wins} maps won")
    print()
    
    if total_team_a_wins > total_team_b_wins:
        pct = (total_team_a_wins / (total_team_a_wins + total_team_b_wins)) * 100
        print(f"🏆 SESSION WINNER: Team A ({total_team_a_wins}-{total_team_b_wins}, {pct:.1f}%)")
    elif total_team_b_wins > total_team_a_wins:
        pct = (total_team_b_wins / (total_team_a_wins + total_team_b_wins)) * 100
        print(f"🏆 SESSION WINNER: Team B ({total_team_b_wins}-{total_team_a_wins}, {pct:.1f}%)")
    else:
        print(f"🤝 SESSION TIE: {total_team_a_wins}-{total_team_b_wins} (PERFECTLY BALANCED)")
    
    print(f"{'='*100}")


if __name__ == "__main__":
    main()
