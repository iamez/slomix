"""
FIXED: Team Detection with Proper Data Deduplication
======================================================
The player_comprehensive_stats table contains MULTIPLE SNAPSHOTS per round,
not final stats. We MUST deduplicate using MAX(time_played) to get accurate data!
"""

import sqlite3
from collections import defaultdict
from typing import Dict, List, Tuple

class FixedTeamDetector:
    """Team detector that properly handles snapshot data"""
    
    def __init__(self, db_path: str = "bot/etlegacy_production.db"):
        self.db_path = db_path
        
    def get_deduplicated_round_data(self, round_date: str, round_number: int) -> List[Dict]:
        """
        Get FINAL stats for each player in a round (deduplicated).
        
        The player_comprehensive_stats table has multiple records per player per round
        representing snapshots during gameplay. We take the LAST snapshot (MAX time_played)
        to get the final stats.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            WITH RankedStats AS (
                SELECT *,
                       ROW_NUMBER() OVER (
                           PARTITION BY round_date, round_number, player_guid, team
                           ORDER BY time_played_minutes DESC, id DESC
                       ) as rn
                FROM player_comprehensive_stats
                WHERE round_date = ? AND round_number = ?
            )
            SELECT 
                player_guid,
                player_name,
                team,
                kills,
                deaths,
                damage_given,
                time_played_minutes
            FROM RankedStats
            WHERE rn = 1
            ORDER BY team, player_name
        """, (round_date, round_number))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                'guid': row[0],
                'name': row[1],
                'team': row[2],
                'kills': row[3],
                'deaths': row[4],
                'damage': row[5],
                'time': row[6]
            }
            for row in rows
        ]
        
    def analyze_session_stopwatch(self, round_date: str) -> Dict:
        """
        Analyze a stopwatch session and detect persistent teams.
        
        In stopwatch mode:
        - Round 1: Team A plays Axis, Team B plays Allies
        - Round 2: Team A plays Allies, Team B plays Axis (SWAP!)
        - We need to track which players consistently play together
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get round count
        cursor.execute("""
            SELECT DISTINCT round_number
            FROM player_comprehensive_stats
            WHERE round_date = ?
            ORDER BY round_number
        """, (round_date,))
        
        rounds = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        print(f"{'='*80}")
        print(f"STOPWATCH SESSION ANALYSIS: {round_date}")
        print(f"{'='*80}\n")
        print(f"Rounds detected: {rounds}\n")
        
        # Analyze each round
        round_data = {}
        for round_num in rounds:
            data = self.get_deduplicated_round_data(round_date, round_num)
            round_data[round_num] = data
            
            axis_players = [p for p in data if p['team'] == 1]
            allies_players = [p for p in data if p['team'] == 2]
            
            print(f"{'='*80}")
            print(f"ROUND {round_num} - DEDUPLICATED DATA")
            print(f"{'='*80}")
            print(f"Total unique players: {len(data)}")
            print(f"Axis players: {len(axis_players)}")
            print(f"Allies players: {len(allies_players)}")
            
            print(f"\n🔴 AXIS TEAM:")
            for p in axis_players:
                print(f"   {p['name']:<30} | K:{p['kills']:<3} D:{p['deaths']:<3} | {p['guid']}")
                
            print(f"\n🔵 ALLIES TEAM:")
            for p in allies_players:
                print(f"   {p['name']:<30} | K:{p['kills']:<3} D:{p['deaths']:<3} | {p['guid']}")
            print()
            
        # Now detect persistent teams
        print(f"{'='*80}")
        print(f"PERSISTENT TEAM DETECTION")
        print(f"{'='*80}\n")
        
        # Build co-occurrence matrix (who plays on same SIDE)
        co_occurrence = defaultdict(lambda: defaultdict(int))
        player_names = {}
        
        for round_num, data in round_data.items():
            # Group by team
            for team_num in [1, 2]:
                team_players = [p for p in data if p['team'] == team_num]
                player_guids = [p['guid'] for p in team_players]
                
                # Store names
                for p in team_players:
                    player_names[p['guid']] = p['name']
                
                # Count co-occurrences
                for i, guid1 in enumerate(player_guids):
                    for guid2 in player_guids[i+1:]:
                        co_occurrence[guid1][guid2] += 1
                        co_occurrence[guid2][guid1] += 1
                        
        # Cluster into teams
        if len(rounds) < 2:
            print("⚠️  Only 1 round - cannot determine persistent teams in stopwatch")
            print("    Need at least 2 rounds to see who swaps sides together!\n")
            return None
            
        # In stopwatch with 2 rounds:
        # - Players on same persistent team should co-occur in 2 rounds
        # - Players on opposite teams should co-occur in 0 rounds
        
        print("Co-occurrence Analysis:")
        print("  (How many rounds did each pair play on the SAME side?)\n")
        
        # Find the threshold - players who appear together in ALL rounds are teammates
        max_co_occurrence = len(rounds)
        
        # Start clustering
        visited = set()
        teams = []
        
        all_guids = list(player_names.keys())
        for guid in all_guids:
            if guid in visited:
                continue
                
            # Start new team
            team = {guid}
            visited.add(guid)
            
            # Add all players who co-occurred with this player in ALL rounds
            for other_guid in all_guids:
                if other_guid not in visited:
                    co_count = co_occurrence[guid][other_guid]
                    # If they played together in ALL rounds, same team
                    if co_count >= max_co_occurrence:
                        team.add(other_guid)
                        visited.add(other_guid)
                        
            teams.append(team)
            
        # Display teams
        print(f"\n✅ Detected {len(teams)} persistent teams:\n")
        
        for i, team in enumerate(teams, 1):
            print(f"🏆 TEAM {i} ({len(team)} players):")
            for guid in sorted(team, key=lambda g: player_names[g]):
                name = player_names[guid]
                print(f"   - {name}")
            print()
            
        # Verify stopwatch swapping
        print(f"{'='*80}")
        print(f"STOPWATCH SWAP VERIFICATION")
        print(f"{'='*80}\n")
        
        # For each team, check they swap sides each round
        for team_idx, team in enumerate(teams, 1):
            print(f"Team {team_idx} side assignments:")
            
            for round_num in sorted(round_data.keys()):
                # Find which side(s) this team played on
                team_sides = defaultdict(int)
                for guid in team:
                    player_data = next((p for p in round_data[round_num] if p['guid'] == guid), None)
                    if player_data:
                        side = "Axis" if player_data['team'] == 1 else "Allies"
                        team_sides[side] += 1
                        
                print(f"   Round {round_num}: {dict(team_sides)}")
                
            print()
            
        return {
            'rounds': rounds,
            'teams': teams,
            'player_names': player_names,
            'co_occurrence': dict(co_occurrence)
        }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python fixed_team_detector.py <round_date>")
        print("Example: python fixed_team_detector.py 2025-11-01")
        sys.exit(1)
        
    round_date = sys.argv[1]
    
    detector = FixedTeamDetector()
    result = detector.analyze_session_stopwatch(round_date)
