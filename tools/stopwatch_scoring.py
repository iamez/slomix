#!/usr/bin/env python3
"""
Stopwatch Scoring Calculator

Correct Stopwatch scoring (independent round scoring):

- Each map has two rounds with a shared time limit.
- Round 1: Team1 attacks vs Team2 defends.
  - If attackers complete under time limit → Team1 gets 1 point
  - If time runs out (fullhold) → Team2 gets 1 point
- Round 2: Team2 attacks vs Team1 defends.
  - If attackers complete under time limit → Team2 gets 1 point
  - If time runs out (fullhold) → Team1 gets 1 point

Map score = sum of the two round results (0, 1, or 2 points per team).
"""

import sqlite3
import json
from typing import Dict, Tuple, Optional, List


class StopwatchScoring:
    """Calculate Stopwatch mode map scores"""
    
    def __init__(self, db_path: str = "bot/etlegacy_production.db"):
        self.db_path = db_path
    
    def parse_time_to_seconds(self, time_str: str) -> int:
        """Convert MM:SS or M:SS to seconds"""
        try:
            if ':' in time_str:
                parts = time_str.split(':')
                minutes = int(parts[0])
                seconds = int(parts[1])
                return minutes * 60 + seconds
            return int(float(time_str))
        except (ValueError, IndexError):
            return 0
    
    def calculate_map_score(
        self,
        round1_time_limit: str,
        round1_actual_time: str,
        round2_actual_time: str
    ) -> Tuple[int, int, str]:
        """
        Calculate map score using independent round scoring.

        Args:
            round1_time_limit: Max map time (MM:SS)
            round1_actual_time: R1 completion time (MM:SS)
            round2_actual_time: R2 completion time (MM:SS)

        Returns:
            (team1_score, team2_score, description)
            team1 = R1 attackers, team2 = R2 attackers
        """

        # Parse times to seconds
        limit_sec = self.parse_time_to_seconds(round1_time_limit)
        r1_sec = self.parse_time_to_seconds(round1_actual_time)
        r2_sec = self.parse_time_to_seconds(round2_actual_time)

        # Determine round outcomes
        r1_attackers_succeed = (r1_sec > 0) and (r1_sec < limit_sec)
        r2_attackers_succeed = (r2_sec > 0) and (r2_sec < limit_sec)

        # Award points independently per round
        team1_points = 0
        team2_points = 0

        # Round 1: Team1 attacks
        if r1_attackers_succeed:
            team1_points += 1
            r1_desc = f"R1: attackers completed in {round1_actual_time} (Team1 +1)"
        else:
            team2_points += 1
            r1_desc = (
                f"R1: fullhold at {round1_time_limit} (Team2 +1)"
                if limit_sec > 0
                else "R1: fullhold (Team2 +1)"
            )

        # Round 2: Team2 attacks
        if r2_attackers_succeed:
            team2_points += 1
            r2_desc = f"R2: attackers completed in {round2_actual_time} (Team2 +1)"
        else:
            team1_points += 1
            r2_desc = (
                f"R2: fullhold at {round1_time_limit} (Team1 +1)"
                if limit_sec > 0
                else "R2: fullhold (Team1 +1)"
            )

        description = f"{r1_desc}; {r2_desc}"
        return (team1_points, team2_points, description)
    
    def calculate_session_scores(
        self, 
        session_ids: Optional[List[int]] = None,
        session_date: Optional[str] = None
    ) -> Optional[Dict[str, int]]:
        """
        Calculate total scores for a gaming session
        
        NOTE: "sessions" table stores ROUNDS (one row per stats file).
              A MATCH = 2 rounds (R1+R2) linked by match_id.
              A GAMING SESSION = multiple matches played continuously (within 30min gaps).
        
        Args:
            session_ids: List of session IDs for this gaming session (preferred)
            session_date: Session date (YYYY-MM-DD) - legacy fallback
        
        Returns:
            Dict with team names as keys and total points as values
        """
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all rounds for this gaming session (grouped by match_id)
        # Use match_id to properly pair R1+R2 together
        if session_ids:
            # Use session_ids list (correct approach - filters to specific gaming session)
            placeholders = ','.join('?' * len(session_ids))
            cursor.execute(f'''
                SELECT map_name, match_id, round_number, defender_team, 
                       winner_team, time_limit, actual_time
                FROM rounds
                WHERE id IN ({placeholders})
                AND match_id IS NOT NULL
                ORDER BY match_id, round_number
            ''', session_ids)
        else:
            # Fallback to date query (may include multiple gaming sessions on same day!)
            cursor.execute('''
                SELECT map_name, match_id, round_number, defender_team, 
                       winner_team, time_limit, actual_time
                FROM rounds
                WHERE substr(round_date, 1, 10) = ?
                AND match_id IS NOT NULL
                ORDER BY match_id, round_number
            ''', (session_date,))
        
        rows = cursor.fetchall()
        
        # Group rounds by match_id (proper R1+R2 pairs)
        maps_dict = {}
        for row in rows:
            map_name, match_id, round_num, defender, winner, \
                time_limit, actual_time = row
            
            if match_id not in maps_dict:
                maps_dict[match_id] = {
                    'map_name': map_name,
                    'match_id': match_id,
                    'round1': None,
                    'round2': None
                }
            
            round_data = {
                'defender': defender,
                'winner': winner,
                'time_limit': time_limit,
                'actual_time': actual_time
            }
            
            if round_num == 1:
                maps_dict[match_id]['round1'] = round_data
            elif round_num == 2:
                maps_dict[match_id]['round2'] = round_data
        
        # Filter to complete maps only (both R1 and R2)
        maps = [
            m for m in maps_dict.values()
            if m['round1'] is not None and m['round2'] is not None
        ]
        
        # Get team assignments from session_teams (use DISTINCT to avoid duplicates)
        cursor.execute('''
            SELECT DISTINCT team_name, player_guids
            FROM session_teams
            WHERE substr(session_start_date, 1, 10) = ?
        ''', (session_date,))
        
        team_rows = cursor.fetchall()
        
        if not team_rows or len(team_rows) < 2:
            conn.close()
            return None
        
        # Parse team assignments
        team_names_list = []
        team_guids_list = []
        for row in team_rows:
            team_name, player_guids_json = row
            player_guids = json.loads(player_guids_json)
            team_names_list.append(team_name)
            team_guids_list.append(set(player_guids))
        
        # Map game team numbers (1=Axis, 2=Allies) to actual team names
        # by checking which GUIDs were on which game team in Round 1
        cursor.execute('''
            SELECT player_guid, team
            FROM player_comprehensive_stats
            WHERE substr(session_date, 1, 10) = ?
            AND round_number = 1
            LIMIT 1
        ''', (session_date,))
        
        sample_player = cursor.fetchone()
        if not sample_player:
            conn.close()
            return None
        
        sample_guid, sample_team = sample_player
        
        # Determine which actual team this GUID belongs to
        if sample_guid in team_guids_list[0]:
            # First team in session_teams = game team number sample_team
            if sample_team == 1:
                team_mapping = {1: 0, 2: 1}  # Game team 1 = team_names_list[0]
            else:
                team_mapping = {1: 1, 2: 0}  # Game team 1 = team_names_list[1]
        else:
            # Second team in session_teams = game team number sample_team
            if sample_team == 1:
                team_mapping = {1: 1, 2: 0}
            else:
                team_mapping = {1: 0, 2: 1}
        
        teams = {
            1: {'name': team_names_list[team_mapping[1]], 'score': 0},
            2: {'name': team_names_list[team_mapping[2]], 'score': 0}
        }
        
        # Calculate scores for each map pair
        map_results = []
        for map_data in maps:
            r1 = map_data['round1']
            r2 = map_data['round2']
            
            # New simplified calculate_map_score only needs times
            team1_pts, team2_pts, desc = self.calculate_map_score(
                r1['time_limit'], r1['actual_time'],
                r2['actual_time']
            )
            
            teams[1]['score'] += team1_pts
            teams[2]['score'] += team2_pts
            
            map_results.append({
                'map': map_data['map_name'],
                'team1_points': team1_pts,
                'team2_points': team2_pts,
                'description': desc
            })
        
        conn.close()
        
        # Return team scores with names
        result = {
            teams[1]['name']: teams[1]['score'],
            teams[2]['name']: teams[2]['score'],
            'maps': map_results,
            'total_maps': len(map_results)
        }
        
        return result


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python stopwatch_scoring.py YYYY-MM-DD")
        sys.exit(1)
    
    session_date = sys.argv[1]
    
    scorer = StopwatchScoring()
    results = scorer.calculate_session_scores(session_date=session_date)
    
    if not results:
        print(f"❌ No session_teams data found for {session_date}")
        print("Run: python tools/dynamic_team_detector.py {session_date}")
        sys.exit(1)
    
    print("\n" + "="*60)
    print(f"🏆 STOPWATCH SCORING: {session_date}")
    print("="*60)
    
    team_names = [k for k in results.keys() if k not in ['maps', 'total_maps']]
    team1_name = team_names[0]
    team2_name = team_names[1]
    
    print(f"\n📊 Final Score:")
    print(f"   {team1_name}: {results[team1_name]} points")
    print(f"   {team2_name}: {results[team2_name]} points")
    
    print(f"\n🗺️  Map-by-Map Breakdown ({results['total_maps']} maps):")
    for map_result in results['maps']:
        print(f"\n   {map_result['map']}:")
        print(f"      {team1_name}: {map_result['team1_points']}")
        print(f"      {team2_name}: {map_result['team2_points']}")
        print(f"      {map_result['description']}")
    
    print("\n" + "="*60 + "\n")
