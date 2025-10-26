"""
Detailed session tracker - shows player assignments across all rounds.
Track which "hardcoded team" each player is on and their in-game role (Axis/Allies).
"""

import sqlite3
import os
from collections import defaultdict
import re

def strip_color_codes(text):
    """Remove ET color codes from text."""
    return re.sub(r'\^\w', '', text)

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
        name_raw = parts[1]
        name_clean = strip_color_codes(name_raw)
        rounds = parts[2]
        team = parts[3]  # "1" = Allies, "2" = Axis, "0"/"3" = Spec
        
        players.append({
            'guid': guid,
            'name': name_clean,
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

def determine_hardcoded_teams(all_rounds_data):
    """
    Analyze all rounds to determine which players are on which hardcoded team.
    Uses first round as baseline, then tracks any swaps.
    """
    
    # Get first round to establish baseline
    first_round = all_rounds_data[0]
    
    # Count how often each player is with each other player
    player_pairings = defaultdict(lambda: defaultdict(int))
    
    for round_data in all_rounds_data:
        allies = []
        axis = []
        
        for player in round_data['players']:
            if player['team'] == '1':  # Allies
                allies.append(player['guid'])
            elif player['team'] == '2':  # Axis
                axis.append(player['guid'])
        
        # Count pairings within Allies
        for i, p1 in enumerate(allies):
            for p2 in allies[i+1:]:
                player_pairings[p1][p2] += 1
                player_pairings[p2][p1] += 1
        
        # Count pairings within Axis
        for i, p1 in enumerate(axis):
            for p2 in axis[i+1:]:
                player_pairings[p1][p2] += 1
                player_pairings[p2][p1] += 1
    
    # Find the most common pairing sets
    # Start with first round's Allies as Team A
    team_a = set()
    team_b = set()
    
    for player in first_round['players']:
        if player['team'] == '1':  # Allies in R1
            team_a.add(player['guid'])
        elif player['team'] == '2':  # Axis in R1
            team_b.add(player['guid'])
    
    return team_a, team_b

def get_player_name(guid, all_rounds_data):
    """Get the most recent clean name for a GUID."""
    for round_data in reversed(all_rounds_data):
        for player in round_data['players']:
            if player['guid'] == guid:
                return player['name']
    return f"GUID:{guid[:8]}"

def main():
    """Track detailed player assignments across October 2nd session."""
    
    stats_dir = "local_stats"
    
    # Get all October 2nd files
    oct2_files = []
    for filename in os.listdir(stats_dir):
        if filename.startswith("2025-10-02") and filename.endswith(".txt"):
            oct2_files.append(filename)
    
    oct2_files.sort()
    
    print(f"Found {len(oct2_files)} rounds for October 2nd\n")
    
    # Parse all files
    all_rounds_data = []
    for filename in oct2_files:
        filepath = os.path.join(stats_dir, filename)
        round_data = parse_stats_file(filepath)
        round_data['filename'] = filename
        all_rounds_data.append(round_data)
    
    # Determine hardcoded teams
    team_a_guids, team_b_guids = determine_hardcoded_teams(all_rounds_data)
    
    team_a_names = [get_player_name(guid, all_rounds_data) for guid in team_a_guids]
    team_b_names = [get_player_name(guid, all_rounds_data) for guid in team_b_guids]
    
    print("="*100)
    print("HARDCODED TEAMS (based on Round 1 assignments):")
    print("="*100)
    print(f"Team A: {', '.join(team_a_names)}")
    print(f"Team B: {', '.join(team_b_names)}")
    print("\n")
    
    # Track round by round
    print("="*100)
    print("ROUND-BY-ROUND PLAYER TRACKING")
    print("="*100)
    
    for idx, round_data in enumerate(all_rounds_data, 1):
        print(f"\n{'='*100}")
        print(f"Round #{idx}: {round_data['map']} - Round {round_data['round']}")
        print(f"File: {round_data['filename']}")
        print(f"Score: Axis {round_data['score1']} - Allies {round_data['score2']}")
        print(f"{'='*100}")
        
        # Organize players by their in-game team
        allies_players = []
        axis_players = []
        spec_players = []
        
        for player in round_data['players']:
            player_info = {
                'guid': player['guid'],
                'name': player['name'],
                'hardcoded_team': None
            }
            
            # Determine hardcoded team
            if player['guid'] in team_a_guids:
                player_info['hardcoded_team'] = 'A'
            elif player['guid'] in team_b_guids:
                player_info['hardcoded_team'] = 'B'
            else:
                player_info['hardcoded_team'] = '?'
            
            if player['team'] == '1':  # Allies
                allies_players.append(player_info)
            elif player['team'] == '2':  # Axis
                axis_players.append(player_info)
            else:  # Spectator
                spec_players.append(player_info)
        
        # Display Allies
        print(f"\n  🔵 ALLIES (Attackers in R{round_data['round']}):")
        if allies_players:
            for p in allies_players:
                team_marker = f"[Team {p['hardcoded_team']}]"
                print(f"    {team_marker:10} {p['name']}")
        else:
            print("    (none)")
        
        # Display Axis
        print(f"\n  🔴 AXIS (Defenders in R{round_data['round']}):")
        if axis_players:
            for p in axis_players:
                team_marker = f"[Team {p['hardcoded_team']}]"
                print(f"    {team_marker:10} {p['name']}")
        else:
            print("    (none)")
        
        # Display Spectators (if any)
        if spec_players:
            print(f"\n  ⚪ SPECTATORS:")
            for p in spec_players:
                team_marker = f"[Team {p['hardcoded_team']}]"
                print(f"    {team_marker:10} {p['name']}")
        
        # Analysis: Are teams balanced?
        team_a_on_allies = sum(1 for p in allies_players if p['hardcoded_team'] == 'A')
        team_a_on_axis = sum(1 for p in axis_players if p['hardcoded_team'] == 'A')
        team_b_on_allies = sum(1 for p in allies_players if p['hardcoded_team'] == 'B')
        team_b_on_axis = sum(1 for p in axis_players if p['hardcoded_team'] == 'B')
        
        print(f"\n  📊 Team Distribution:")
        print(f"    Team A: {team_a_on_allies} on Allies, {team_a_on_axis} on Axis")
        print(f"    Team B: {team_b_on_allies} on Allies, {team_b_on_axis} on Axis")
        
        # Check for player swaps
        if idx > 1:
            prev_round = all_rounds_data[idx - 2]
            
            # Build previous round's assignments
            prev_team_a_allies = sum(1 for p in prev_round['players'] 
                                    if p['guid'] in team_a_guids and p['team'] == '1')
            prev_team_a_axis = sum(1 for p in prev_round['players'] 
                                  if p['guid'] in team_a_guids and p['team'] == '2')
            
            # Check if distribution changed (player swap detected)
            if team_a_on_allies != prev_team_a_allies or team_a_on_axis != prev_team_a_axis:
                print(f"\n  ⚠️  PLAYER SWAP DETECTED between rounds!")
    
    # Summary statistics
    print("\n\n" + "="*100)
    print("SESSION SUMMARY")
    print("="*100)
    
    # Count how many rounds each team played on each side
    team_a_as_allies = 0
    team_a_as_axis = 0
    team_b_as_allies = 0
    team_b_as_axis = 0
    
    for round_data in all_rounds_data:
        for player in round_data['players']:
            if player['guid'] in team_a_guids:
                if player['team'] == '1':
                    team_a_as_allies += 1
                elif player['team'] == '2':
                    team_a_as_axis += 1
            elif player['guid'] in team_b_guids:
                if player['team'] == '1':
                    team_b_as_allies += 1
                elif player['team'] == '2':
                    team_b_as_axis += 1
    
    print(f"\nTeam A played:")
    print(f"  - As Allies: {team_a_as_allies} player-rounds")
    print(f"  - As Axis: {team_a_as_axis} player-rounds")
    
    print(f"\nTeam B played:")
    print(f"  - As Allies: {team_b_as_allies} player-rounds")
    print(f"  - As Axis: {team_b_as_axis} player-rounds")

if __name__ == "__main__":
    main()
