"""
FINAL SOLUTION: Team Detection That Actually Works With Your Data
==================================================================

The Issue:
----------
- player_comprehensive_stats has multiple snapshots per round
- Players appear on BOTH Axis AND Allies in same round (team switches)
- Axis/Allies labels are meaningless for team detection

The Solution:
-------------
Ignore Axis/Allies labels completely. Instead:
1. Get all unique players in session
2. Calculate how often each pair plays together (co-occurrence)
3. Cluster players who consistently play together
4. These clusters = the real persistent teams

This works because:
- Organized match: Players A,B,C always together → high co-occurrence
- Pub server: Players randomly switch → low/random co-occurrence
"""

import sqlite3
from collections import defaultdict
from typing import Dict, List, Set, Tuple

class RealTeamDetector:
    """Team detector that ignores bogus Axis/Allies labels"""
    
    def __init__(self, db_path: str = "bot/etlegacy_production.db"):
        self.db_path = db_path
        
    def detect_teams(self, round_date: str) -> Dict:
        """
        Detect persistent teams by analyzing who plays together,
        completely ignoring Axis/Allies team labels.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        print("="*80)
        print(f"REAL TEAM DETECTION: {round_date}")
        print("="*80)
        print("\n🔍 Strategy: Analyze co-play patterns, ignore Axis/Allies labels\n")
        
        # Get ALL unique players across all rounds
        cursor.execute("""
            SELECT DISTINCT player_guid, player_name
            FROM player_comprehensive_stats
            WHERE round_date = ?
            ORDER BY player_name
        """, (round_date,))
        
        all_players = cursor.fetchall()
        player_names = {guid: name for guid, name in all_players}
        
        print(f"Total unique players: {len(all_players)}\n")
        
        # Get round count
        cursor.execute("""
            SELECT DISTINCT round_number
            FROM player_comprehensive_stats
            WHERE round_date = ?
            ORDER BY round_number
        """, (round_date,))
        
        rounds = [r[0] for r in cursor.fetchall()]
        print(f"Rounds: {rounds}")
        print(f"Total rounds: {len(rounds)}\n")
        
        # For each round, see which players participated
        # (regardless of which team/side)
        round_participants = {}
        
        for round_num in rounds:
            cursor.execute("""
                SELECT DISTINCT player_guid
                FROM player_comprehensive_stats
                WHERE round_date = ? AND round_number = ?
            """, (round_date, round_num))
            
            participants = {row[0] for row in cursor.fetchall()}
            round_participants[round_num] = participants
            
        # Calculate co-occurrence: how many rounds did each pair play together?
        co_occurrence = defaultdict(lambda: defaultdict(int))
        
        for round_num, participants in round_participants.items():
            participant_list = list(participants)
            # Every pair of players in this round played together
            for i, guid1 in enumerate(participant_list):
                for guid2 in participant_list[i+1:]:
                    co_occurrence[guid1][guid2] += 1
                    co_occurrence[guid2][guid1] += 1
        
        # Show co-occurrence matrix
        print("="*80)
        print("CO-OCCURRENCE MATRIX")
        print("="*80)
        print("(How many rounds did each pair play together?)\n")
        
        for guid in sorted(player_names.keys(), key=lambda g: player_names[g]):
            name = player_names[guid]
            rounds_played = sum(1 for r in round_participants.values() if guid in r)
            teammates = co_occurrence[guid]
            
            if teammates:
                print(f"{name} (played {rounds_played}/{len(rounds)} rounds):")
                sorted_teammates = sorted(teammates.items(), 
                                        key=lambda x: (-x[1], player_names[x[0]]))
                for teammate_guid, count in sorted_teammates:
                    teammate_name = player_names[teammate_guid]
                    percentage = (count / rounds_played * 100) if rounds_played > 0 else 0
                    print(f"  {count:2d}/{rounds_played} rounds ({percentage:5.1f}%) with {teammate_name}")
                print()
        
        # Cluster into teams using threshold
        # Players who play together in ALL their rounds are teammates
        print("="*80)
        print("TEAM CLUSTERING")
        print("="*80)
        
        visited = set()
        teams = []
        
        for guid in sorted(player_names.keys(), key=lambda g: player_names[g]):
            if guid in visited:
                continue
                
            # Start new team
            team = {guid}
            visited.add(guid)
            rounds_played = sum(1 for r in round_participants.values() if guid in r)
            
            # Add players who played with this player in ALL their mutual rounds
            for other_guid in player_names.keys():
                if other_guid in visited:
                    continue
                    
                # How many rounds did they both participate in?
                mutual_rounds = sum(1 for r in round_participants.values() 
                                  if guid in r and other_guid in r)
                
                # How many rounds did they play together?
                together_count = co_occurrence[guid][other_guid]
                
                # If they played together in ALL mutual rounds, same team
                if mutual_rounds > 0 and together_count == mutual_rounds:
                    team.add(other_guid)
                    visited.add(other_guid)
            
            teams.append(team)
        
        # Display teams
        print(f"\n✅ Detected {len(teams)} persistent team(s):\n")
        
        for i, team in enumerate(teams, 1):
            print(f"🏆 TEAM {i} ({len(team)} players):")
            for guid in sorted(team, key=lambda g: player_names[g]):
                rounds_played = sum(1 for r in round_participants.values() if guid in r)
                print(f"   - {player_names[guid]:<30} (played {rounds_played}/{len(rounds)} rounds)")
            print()
        
        # Verify: Show who each team member co-occurred with WITHIN their team
        print("="*80)
        print("TEAM COHESION VERIFICATION")
        print("="*80)
        
        for i, team in enumerate(teams, 1):
            print(f"\nTeam {i} internal co-occurrence:")
            team_list = list(team)
            
            for j, guid1 in enumerate(team_list):
                name1 = player_names[guid1]
                rounds1 = sum(1 for r in round_participants.values() if guid1 in r)
                
                print(f"\n  {name1} (played {rounds1} rounds):")
                for guid2 in team_list:
                    if guid1 == guid2:
                        continue
                    name2 = player_names[guid2]
                    together = co_occurrence[guid1][guid2]
                    print(f"    - {together}/{rounds1} rounds with {name2}")
        
        conn.close()
        
        return {
            'teams': teams,
            'player_names': player_names,
            'co_occurrence': dict(co_occurrence),
            'rounds': rounds
        }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python real_team_detector.py <round_date>")
        print("Example: python real_team_detector.py 2024-10-28")
        sys.exit(1)
        
    round_date = sys.argv[1]
    
    detector = RealTeamDetector()
    result = detector.detect_teams(round_date)
