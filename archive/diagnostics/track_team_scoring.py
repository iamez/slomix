"""
Track team scoring for October 2nd session using team composition approach.

Teams are defined by the first 3 players on each side in Round 1.
We track their wins/losses across all matches.
"""

import sqlite3
import os
from collections import defaultdict

def parse_stats_file(filepath):
    """Parse a stats file to extract header and player info."""
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    # Parse header
    header = lines[0].strip()
    parts = header.split('\\')
    
    map_name = parts[1] if len(parts) > 1 else "unknown"
    round_num = int(parts[3]) if len(parts) > 3 else 0
    score1 = int(parts[4]) if len(parts) > 4 else 0
    score2 = int(parts[5]) if len(parts) > 5 else 0
    time_limit = parts[6] if len(parts) > 6 else "0:00"
    actual_time = parts[7] if len(parts) > 7 else "0:00"
    
    # Parse players
    players = []
    for line in lines[1:]:
        if not line.strip():
            continue
        
        parts = line.split('\\')
        if len(parts) < 4:
            continue
        
        guid = parts[0]
        name = parts[1]
        rounds = parts[2]
        team = parts[3]  # "0" = Axis, "1" = Allies, "2" = Spectator
        
        players.append({
            'guid': guid,
            'name': name,
            'team': team
        })
    
    return {
        'map': map_name,
        'round': round_num,
        'score1': score1,  # Axis score
        'score2': score2,  # Allies score
        'time_limit': time_limit,
        'actual_time': actual_time,
        'players': players
    }

def get_team_rosters(round1_data, round2_data):
    """
    Extract team rosters from Round 1.
    Returns Team A (Allies in R1) and Team B (Axis in R1) as sets of GUIDs.
    
    Team assignments:
    - team == '1' → ALLIES
    - team == '2' → AXIS
    - team == '0' or '3' → SPECTATORS
    """
    team_a = set()  # Allies in Round 1
    team_b = set()  # Axis in Round 1
    
    for player in round1_data['players']:
        if player['team'] == '1':  # Allies
            team_a.add(player['guid'])
        elif player['team'] == '2':  # Axis
            team_b.add(player['guid'])
    
    return team_a, team_b

def determine_match_winner(round1_data, round2_data, team_a_guids, team_b_guids):
    """
    Determine which team won the match using Stopwatch rules.
    
    Returns:
        - "Team A" if Team A won
        - "Team B" if Team B won
        - "Unknown" if we can't determine
    """
    
    # In Round 1:
    # - Team A is on Allies (score2) - ATTACKERS
    # - Team B is on Axis (score1) - DEFENDERS
    
    r1_axis_score = round1_data['score1']
    r1_allies_score = round1_data['score2']
    
    # In Round 2:
    # - Team A is on Axis (score1) - DEFENDERS
    # - Team B is on Allies (score2) - ATTACKERS
    
    r2_axis_score = round2_data['score1']
    r2_allies_score = round2_data['score2']
    
    print(f"\n  Round 1 scores: Axis {r1_axis_score} - Allies {r1_allies_score}")
    print(f"  Round 2 scores: Axis {r2_axis_score} - Allies {r2_allies_score}")
    
    # Team A starts as Allies (attackers) in R1
    # Team B starts as Axis (defenders) in R1
    
    team_a_points = 0
    team_b_points = 0
    
    # Round 1 analysis
    if r1_allies_score == 2:
        # Team A (Allies) completed objectives and set a time
        team_a_points += 1
        print("  R1: Team A (Allies) completed objectives → Team A +1 point")
    else:
        # Team A (Allies) failed
        print("  R1: Team A (Allies) failed to complete → No points")
    
    # Round 2 analysis (teams swapped)
    # Now Team B is Allies (attackers), Team A is Axis (defenders)
    if r2_allies_score == 2:
        # Team B (Allies in R2) completed objectives
        team_b_points += 1
        print("  R2: Team B (Allies) completed objectives → Team B +1 point")
        
        # Did they beat the time? (Match the R1 time or better)
        if team_a_points == 1:
            # Team A set a time, Team B needs to beat it
            team_b_points += 1
            print("  R2: Team B beat Team A's time → Team B +1 point (wins)")
    else:
        # Team B (Allies in R2) failed
        print("  R2: Team B (Allies) failed to complete → Team A defends")
        if team_a_points == 1:
            team_a_points += 1
            print("  R2: Team A gets defense point → Team A +1 point (wins)")
    
    print(f"  Final: Team A {team_a_points} - Team B {team_b_points}")
    
    if team_a_points > team_b_points:
        return "Team A"
    elif team_b_points > team_a_points:
        return "Team B"
    else:
        return "Draw"

def get_player_names(guids):
    """Get player names from database for display."""
    conn = sqlite3.connect('etlegacy_production.db')
    cursor = conn.cursor()
    
    names = []
    for guid in guids:
        cursor.execute("""
            SELECT player_name 
            FROM player_comprehensive_stats 
            WHERE player_guid = ? 
            ORDER BY session_date DESC 
            LIMIT 1
        """, (guid,))
        
        result = cursor.fetchone()
        if result:
            names.append(result[0])
        else:
            names.append(f"GUID:{guid[:8]}")
    
    conn.close()
    return names

def main():
    """Track team scoring for October 2nd session."""
    
    stats_dir = "local_stats"
    
    # Get all October 2nd files
    oct2_files = []
    for filename in os.listdir(stats_dir):
        if filename.startswith("2025-10-02") and filename.endswith(".txt"):
            oct2_files.append(filename)
    
    oct2_files.sort()
    
    print(f"Found {len(oct2_files)} files for October 2nd\n")
    
    # Group files by map (Round 1 + Round 2 pairs)
    matches = []
    i = 0
    while i < len(oct2_files) - 1:
        file1 = oct2_files[i]
        file2 = oct2_files[i + 1]
        
        # Check if they're consecutive rounds of same map
        if "round-1" in file1 and "round-2" in file2:
            matches.append((file1, file2))
            i += 2
        else:
            i += 1
    
    print(f"Found {len(matches)} complete matches (Round 1 + Round 2 pairs)\n")
    print("=" * 80)
    
    # Track overall team records
    team_records = defaultdict(lambda: {'wins': 0, 'losses': 0, 'players': set()})
    
    # Analyze each match
    for idx, (round1_file, round2_file) in enumerate(matches, 1):
        print(f"\nMatch #{idx}")
        print(f"Files: {round1_file}")
        print(f"       {round2_file}")
        
        # Parse both rounds
        round1_path = os.path.join(stats_dir, round1_file)
        round2_path = os.path.join(stats_dir, round2_file)
        
        round1_data = parse_stats_file(round1_path)
        round2_data = parse_stats_file(round2_path)
        
        print(f"Map: {round1_data['map']}")
        
        # Get team rosters from Round 1
        team_a_guids, team_b_guids = get_team_rosters(round1_data, round2_data)
        
        # Get player names
        team_a_names = get_player_names(team_a_guids)
        team_b_names = get_player_names(team_b_guids)
        
        print(f"\n  Team A (Allies in R1): {', '.join(team_a_names)}")
        print(f"  Team B (Axis in R1): {', '.join(team_b_names)}")
        
        # Determine winner
        winner = determine_match_winner(round1_data, round2_data, team_a_guids, team_b_guids)
        
        print(f"\n  🏆 Winner: {winner}")
        
        # Update records
        team_a_key = tuple(sorted(team_a_guids))
        team_b_key = tuple(sorted(team_b_guids))
        
        team_records[team_a_key]['players'] = team_a_names
        team_records[team_b_key]['players'] = team_b_names
        
        if winner == "Team A":
            team_records[team_a_key]['wins'] += 1
            team_records[team_b_key]['losses'] += 1
        elif winner == "Team B":
            team_records[team_b_key]['wins'] += 1
            team_records[team_a_key]['losses'] += 1
        
        print("=" * 80)
    
    # Print overall standings
    print("\n\n🏆 OCTOBER 2ND SESSION - TEAM STANDINGS")
    print("=" * 80)
    
    # Sort teams by win percentage
    sorted_teams = sorted(
        team_records.items(),
        key=lambda x: x[1]['wins'] / max(1, x[1]['wins'] + x[1]['losses']),
        reverse=True
    )
    
    for rank, (team_key, record) in enumerate(sorted_teams, 1):
        wins = record['wins']
        losses = record['losses']
        total = wins + losses
        win_pct = (wins / total * 100) if total > 0 else 0
        
        players_str = ', '.join(record['players'])
        
        print(f"\n#{rank}. {players_str}")
        print(f"    Record: {wins}W - {losses}L ({win_pct:.1f}%)")

if __name__ == "__main__":
    main()
