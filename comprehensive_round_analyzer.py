"""
COMPREHENSIVE ROUND-BY-ROUND SESSION ANALYZER
==============================================
Shows EVERYTHING about a session:
- Every player in every round
- Exact side assignments (Axis/Allies)
- Team swapping in stopwatch mode
- Player consistency across rounds
- Duplicate detection
- Team persistence verification
"""

import sqlite3
import json
from collections import defaultdict
from typing import Dict, List, Set, Tuple

class ComprehensiveRoundAnalyzer:
    def __init__(self, db_path: str = "bot/etlegacy_production.db"):
        self.db_path = db_path
        
    def analyze_session(self, round_date: str):
        """Perform comprehensive round-by-round analysis"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        print("=" * 100)
        print(f"🔍 COMPREHENSIVE ROUND-BY-ROUND ANALYSIS: {round_date}")
        print("=" * 100)
        print()
        
        # Step 1: Get session info
        self._show_session_info(cursor, round_date)
        print()
        
        # Step 2: Get ALL rounds with ALL data
        rounds_data = self._get_all_rounds_detailed(cursor, round_date)
        print()
        
        # Step 3: Analyze each round in detail
        self._analyze_each_round_detailed(rounds_data)
        print()
        
        # Step 4: Track player consistency
        self._analyze_player_consistency(rounds_data)
        print()
        
        # Step 5: Verify stopwatch swapping
        self._verify_stopwatch_swapping(rounds_data)
        print()
        
        # Step 6: Detect true teams (accounting for swaps)
        self._detect_persistent_teams(rounds_data)
        print()
        
        conn.close()
        
    def _show_session_info(self, cursor, round_date: str):
        """Show detailed session information"""
        print("📋 SESSION INFORMATION")
        print("-" * 100)
        
        cursor.execute("""
            SELECT 
                round_date,
                map_name,
                COUNT(DISTINCT round_number) as total_rounds,
                COUNT(DISTINCT player_guid) as total_players,
                MIN(round_number) as first_round,
                MAX(round_number) as last_round
            FROM player_comprehensive_stats
            WHERE round_date = ?
            GROUP BY round_date, map_name
        """, (round_date,))
        
        session_info = cursor.fetchone()
        if not session_info:
            print(f"❌ No data found for session {round_date}")
            return
            
        print(f"Date:          {session_info[0]}")
        print(f"Map:           {session_info[1]}")
        print(f"Total Rounds:  {session_info[2]}")
        print(f"Total Players: {session_info[3]}")
        print(f"Round Range:   {session_info[4]} - {session_info[5]}")
        
    def _get_all_rounds_detailed(self, cursor, round_date: str) -> Dict[int, Dict]:
        """Get ALL data for every round with full details"""
        print("📊 LOADING ROUND DATA")
        print("-" * 100)
        
        # Get EVERY player record for EVERY round
        cursor.execute("""
            SELECT 
                round_number,
                player_guid,
                player_name,
                team,
                kills,
                deaths,
                damage_given,
                damage_received,
                time_played_minutes
            FROM player_comprehensive_stats
            WHERE round_date = ?
            ORDER BY round_number, team, player_name
        """, (round_date,))
        
        rows = cursor.fetchall()
        print(f"✅ Loaded {len(rows)} player records from database")
        
        # Organize by round
        rounds_data = defaultdict(lambda: {
            'axis_players': [],
            'allies_players': [],
            'all_players': []
        })
        
        for row in rows:
            round_num = row[0]
            player_data = {
                'guid': row[1],
                'name': row[2],
                'team': row[3],
                'kills': row[4],
                'deaths': row[5],
                'damage_given': row[6],
                'damage_received': row[7],
                'time_played': row[8]
            }
            
            rounds_data[round_num]['all_players'].append(player_data)
            
            if player_data['team'] == 1:  # Axis
                rounds_data[round_num]['axis_players'].append(player_data)
            elif player_data['team'] == 2:  # Allies
                rounds_data[round_num]['allies_players'].append(player_data)
                
        print(f"✅ Organized into {len(rounds_data)} rounds")
        return dict(rounds_data)
        
    def _analyze_each_round_detailed(self, rounds_data: Dict[int, Dict]):
        """Show detailed analysis of each round"""
        print("🔍 ROUND-BY-ROUND DETAILED BREAKDOWN")
        print("=" * 100)
        
        for round_num in sorted(rounds_data.keys()):
            round_info = rounds_data[round_num]
            
            print(f"\n{'='*100}")
            print(f"⚔️  ROUND {round_num}")
            print(f"{'='*100}")
            
            axis_players = round_info['axis_players']
            allies_players = round_info['allies_players']
            
            print(f"\n📊 Round Statistics:")
            print(f"   Total Players: {len(round_info['all_players'])}")
            print(f"   Axis Players:  {len(axis_players)}")
            print(f"   Allies Players: {len(allies_players)}")
            
            # Check for duplicates
            all_guids = [p['guid'] for p in round_info['all_players']]
            unique_guids = set(all_guids)
            if len(all_guids) != len(unique_guids):
                print(f"   ⚠️  DUPLICATE DETECTION: {len(all_guids)} total records, {len(unique_guids)} unique players")
                # Find duplicates
                guid_counts = defaultdict(int)
                for guid in all_guids:
                    guid_counts[guid] += 1
                duplicates = {guid: count for guid, count in guid_counts.items() if count > 1}
                print(f"   ⚠️  Duplicate GUIDs: {duplicates}")
            else:
                print(f"   ✅ No duplicates - all {len(unique_guids)} players unique")
            
            # Show Axis team
            print(f"\n🔴 AXIS TEAM ({len(axis_players)} players):")
            print(f"{'Name':<30} {'GUID':<40} {'K':<4} {'D':<4} {'DMG':<8} {'Time':<6}")
            print("-" * 100)
            for player in sorted(axis_players, key=lambda x: x['name']):
                print(f"{player['name']:<30} {player['guid']:<40} "
                      f"{player['kills']:<4} {player['deaths']:<4} "
                      f"{player['damage_given']:<8} {player['time_played']:<6}")
            
            # Show Allies team
            print(f"\n🔵 ALLIES TEAM ({len(allies_players)} players):")
            print(f"{'Name':<30} {'GUID':<40} {'K':<4} {'D':<4} {'DMG':<8} {'Time':<6}")
            print("-" * 100)
            for player in sorted(allies_players, key=lambda x: x['name']):
                print(f"{player['name']:<30} {player['guid']:<40} "
                      f"{player['kills']:<4} {player['deaths']:<4} "
                      f"{player['damage_given']:<8} {player['time_played']:<6}")
            
            # Extract unique GUIDs for this round
            axis_guids = {p['guid'] for p in axis_players}
            allies_guids = {p['guid'] for p in allies_players}
            
            print(f"\n🔑 Unique Player GUIDs:")
            print(f"   Axis:   {len(axis_guids)} unique GUIDs")
            print(f"   Allies: {len(allies_guids)} unique GUIDs")
            
            # Check for overlap (shouldn't happen)
            overlap = axis_guids & allies_guids
            if overlap:
                print(f"   ⚠️  OVERLAP DETECTED: {len(overlap)} players on BOTH teams!")
                for guid in overlap:
                    player_name = next(p['name'] for p in round_info['all_players'] if p['guid'] == guid)
                    print(f"      - {player_name} ({guid})")
            else:
                print(f"   ✅ No overlap - teams are distinct")
                
    def _analyze_player_consistency(self, rounds_data: Dict[int, Dict]):
        """Track each player across all rounds"""
        print("👥 PLAYER CONSISTENCY ANALYSIS")
        print("=" * 100)
        
        # Track each player's participation
        player_rounds = defaultdict(list)
        
        for round_num in sorted(rounds_data.keys()):
            for player in rounds_data[round_num]['all_players']:
                player_rounds[player['guid']].append({
                    'round': round_num,
                    'name': player['name'],
                    'team': player['team'],
                    'kills': player['kills'],
                    'deaths': player['deaths']
                })
        
        print(f"\n📋 Found {len(player_rounds)} unique players across all rounds\n")
        
        # Analyze each player
        for guid, rounds in sorted(player_rounds.items(), key=lambda x: x[1][0]['name']):
            player_name = rounds[0]['name']
            total_rounds = len(rounds)
            rounds_present = sorted([r['round'] for r in rounds])
            
            print(f"{'='*100}")
            print(f"Player: {player_name}")
            print(f"GUID:   {guid}")
            print(f"Rounds: {total_rounds} / {len(rounds_data)} total")
            print(f"Present in rounds: {rounds_present}")
            
            # Check if full session or partial
            if total_rounds == len(rounds_data):
                print(f"Status: ✅ FULL SESSION PLAYER")
            else:
                missing = set(rounds_data.keys()) - set(rounds_present)
                print(f"Status: ⚠️  PARTIAL PARTICIPATION - missing rounds: {sorted(missing)}")
            
            # Show round-by-round teams
            print(f"\nRound-by-round breakdown:")
            print(f"{'Round':<10} {'Team':<15} {'Side':<10} {'K':<5} {'D':<5}")
            print("-" * 50)
            for r in rounds:
                team_name = "Axis" if r['team'] == 1 else "Allies" if r['team'] == 2 else "Unknown"
                side_emoji = "🔴" if r['team'] == 1 else "🔵" if r['team'] == 2 else "⚪"
                print(f"{r['round']:<10} {team_name:<15} {side_emoji:<10} {r['kills']:<5} {r['deaths']:<5}")
            
            print()
            
    def _verify_stopwatch_swapping(self, rounds_data: Dict[int, Dict]):
        """Verify that teams swap sides between rounds (stopwatch mode)"""
        print("🔄 STOPWATCH SIDE-SWAPPING VERIFICATION")
        print("=" * 100)
        
        print("\nIn stopwatch mode, teams should swap sides each round:")
        print("- Round 1: Team A = Axis, Team B = Allies")
        print("- Round 2: Team A = Allies, Team B = Axis")
        print("- etc.\n")
        
        # Track player sides across rounds
        player_sides = defaultdict(list)
        
        for round_num in sorted(rounds_data.keys()):
            for player in rounds_data[round_num]['all_players']:
                player_sides[player['guid']].append({
                    'round': round_num,
                    'team': player['team']
                })
        
        # Analyze swapping patterns
        print("🔍 Analyzing side-swapping patterns:\n")
        
        swap_compliant = 0
        swap_non_compliant = 0
        partial_players = 0
        
        for guid, sides in player_sides.items():
            player_name = next(p['name'] for p in rounds_data[sides[0]['round']]['all_players'] 
                             if p['guid'] == guid)
            
            if len(sides) < 2:
                partial_players += 1
                continue
                
            # Check if sides alternate
            swaps_correctly = True
            for i in range(len(sides) - 1):
                current_team = sides[i]['team']
                next_team = sides[i + 1]['team']
                
                # In stopwatch, teams SHOULD swap
                if current_team == next_team:
                    swaps_correctly = False
                    break
            
            if swaps_correctly:
                swap_compliant += 1
                print(f"✅ {player_name:<30} - Swaps sides correctly between rounds")
            else:
                swap_non_compliant += 1
                print(f"❌ {player_name:<30} - Does NOT swap (stays on same side)")
                # Show the pattern
                pattern = " -> ".join([f"R{s['round']}:{'Axis' if s['team']==1 else 'Allies'}" 
                                      for s in sides])
                print(f"   Pattern: {pattern}")
        
        print(f"\n📊 SWAPPING SUMMARY:")
        print(f"   Swap-compliant players:     {swap_compliant}")
        print(f"   Non-swapping players:       {swap_non_compliant}")
        print(f"   Partial participation:      {partial_players}")
        
        if swap_non_compliant > 0:
            print(f"\n⚠️  WARNING: {swap_non_compliant} players don't swap sides!")
            print(f"   This suggests they might NOT be stopwatch mode, or there's a data issue.")
        else:
            print(f"\n✅ All full-session players swap sides correctly - confirms stopwatch mode")
            
    def _detect_persistent_teams(self, rounds_data: Dict[int, Dict]):
        """Detect the TRUE persistent teams accounting for side swapping"""
        print("🎯 PERSISTENT TEAM DETECTION (Accounting for Side Swaps)")
        print("=" * 100)
        
        print("\nIn stopwatch mode, the TRUE teams persist across rounds,")
        print("even though they swap which side (Axis/Allies) they play.\n")
        
        # Build co-occurrence matrix
        # Two players are teammates if they're on the SAME SIDE in a round
        co_occurrence = defaultdict(lambda: defaultdict(int))
        player_names = {}
        
        for round_num in sorted(rounds_data.keys()):
            round_info = rounds_data[round_num]
            
            # Axis players in this round
            axis_guids = [p['guid'] for p in round_info['axis_players']]
            allies_guids = [p['guid'] for p in round_info['allies_players']]
            
            # Store names
            for p in round_info['all_players']:
                player_names[p['guid']] = p['name']
            
            # Players on same side are teammates
            for i, guid1 in enumerate(axis_guids):
                for guid2 in axis_guids[i+1:]:
                    co_occurrence[guid1][guid2] += 1
                    co_occurrence[guid2][guid1] += 1
            
            for i, guid1 in enumerate(allies_guids):
                for guid2 in allies_guids[i+1:]:
                    co_occurrence[guid1][guid2] += 1
                    co_occurrence[guid2][guid1] += 1
        
        print("🔍 Co-occurrence Matrix Analysis:")
        print("\nShowing how often each player was on the SAME SIDE as others:\n")
        
        # Show matrix for each player
        all_guids = sorted(player_names.keys(), key=lambda g: player_names[g])
        
        for guid in all_guids:
            name = player_names[guid]
            print(f"\n{name}:")
            
            teammates = co_occurrence[guid]
            if not teammates:
                print(f"   (No co-occurrence data - single round player?)")
                continue
                
            # Sort by co-occurrence count
            sorted_teammates = sorted(teammates.items(), 
                                    key=lambda x: x[1], 
                                    reverse=True)
            
            for teammate_guid, count in sorted_teammates:
                teammate_name = player_names[teammate_guid]
                print(f"   {count} rounds with {teammate_name}")
        
        # Cluster into teams
        print("\n" + "="*100)
        print("🎯 FINAL TEAM CLUSTERING")
        print("="*100)
        
        # Simple clustering: start with first player, add their most frequent teammates
        visited = set()
        teams = []
        
        for guid in all_guids:
            if guid in visited:
                continue
                
            # Start new team
            team = {guid}
            visited.add(guid)
            
            # Add teammates who appear together frequently
            teammates = co_occurrence[guid]
            for teammate_guid, count in teammates.items():
                if teammate_guid not in visited:
                    # If they played together in most rounds, they're on same team
                    total_rounds = len([r for r in rounds_data.values() 
                                      if any(p['guid'] == guid for p in r['all_players'])])
                    if count >= total_rounds * 0.5:  # Together in 50%+ of rounds
                        team.add(teammate_guid)
                        visited.add(teammate_guid)
            
            teams.append(team)
        
        # Show final teams
        print(f"\n✅ Detected {len(teams)} persistent teams:\n")
        
        for i, team in enumerate(teams, 1):
            print(f"🏆 TEAM {i} ({len(team)} players):")
            for guid in sorted(team, key=lambda g: player_names[g]):
                print(f"   - {player_names[guid]}")
            print()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python comprehensive_round_analyzer.py <round_date>")
        print("Example: python comprehensive_round_analyzer.py 2025-11-01")
        sys.exit(1)
    
    round_date = sys.argv[1]
    
    analyzer = ComprehensiveRoundAnalyzer()
    analyzer.analyze_session(round_date)
