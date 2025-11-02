"""
Player Substitution and Addition Detection

Analyzes round-by-round team rosters to detect:
1. Players who joined mid-session
2. Players who left mid-session
3. Player substitutions (player A replaced by player B)
4. Team composition changes

This helps improve team detection accuracy by understanding
roster changes throughout the session.
"""

import sqlite3
import logging
from typing import Dict, List, Tuple, Set, Optional
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class PlayerActivity:
    """Track when a player was active during session"""
    player_guid: str
    player_name: str
    first_round: int
    last_round: int
    rounds_played: Set[int]
    game_teams: Dict[int, int]  # round -> game_team (1 or 2)
    
    @property
    def is_full_session(self) -> bool:
        """Did player play entire session (from round 1)?"""
        return self.first_round == 1
    
    @property
    def is_late_joiner(self) -> bool:
        """Did player join after round 1?"""
        return self.first_round > 1
    
    @property
    def is_early_leaver(self) -> bool:
        """Did player leave before last round?"""
        # We don't know total rounds yet, will check later
        return False


@dataclass
class RosterChange:
    """Represents a roster change between rounds"""
    round_number: int
    change_type: str  # 'addition', 'substitution', 'departure'
    game_team: int  # 1 or 2
    player_in: Optional[str] = None  # Player who joined
    player_out: Optional[str] = None  # Player who left
    guid_in: Optional[str] = None
    guid_out: Optional[str] = None
    
    def __str__(self):
        if self.change_type == 'addition':
            return f"Round {self.round_number}: {self.player_in} joined Team {self.game_team}"
        elif self.change_type == 'departure':
            return f"Round {self.round_number}: {self.player_out} left Team {self.game_team}"
        elif self.change_type == 'substitution':
            return f"Round {self.round_number}: {self.player_out} → {self.player_in} (Team {self.game_team})"
        return f"Round {self.round_number}: Unknown change"


class SubstitutionDetector:
    """
    Detects player substitutions and roster changes
    """
    
    def __init__(self):
        self.substitution_window = 1  # Detect subs within N rounds
        
    def analyze_session_roster_changes(
        self,
        db: sqlite3.Connection,
        session_date: str
    ) -> Dict:
        """
        Analyze roster changes throughout a session
        
        Returns:
            {
                'player_activity': {guid: PlayerActivity},
                'roster_changes': [RosterChange],
                'full_session_players': [guids],
                'late_joiners': [guids],
                'early_leavers': [guids],
                'substitutions': [(guid_out, guid_in, round)],
                'round_rosters': {round: {'team1': [guids], 'team2': [guids]}}
            }
        """
        logger.info(f"🔍 Analyzing roster changes for {session_date}")
        
        # Get all player activity
        player_activity = self._get_player_activity(db, session_date)
        
        if not player_activity:
            logger.warning("No player activity found")
            return {}
        
        # Get round-by-round rosters
        round_rosters = self._get_round_rosters(db, session_date)
        
        # Detect changes
        roster_changes = self._detect_roster_changes(round_rosters, player_activity)
        
        # Categorize players
        total_rounds = max(round_rosters.keys()) if round_rosters else 0
        
        full_session = []
        late_joiners = []
        early_leavers = []
        
        for guid, activity in player_activity.items():
            if activity.first_round == 1 and activity.last_round == total_rounds:
                full_session.append(guid)
            
            if activity.first_round > 1:
                late_joiners.append(guid)
            
            if activity.last_round < total_rounds:
                early_leavers.append(guid)
        
        # Detect substitutions (player leaves, another joins same round/next)
        substitutions = self._detect_substitutions(roster_changes)
        
        result = {
            'player_activity': player_activity,
            'roster_changes': roster_changes,
            'full_session_players': full_session,
            'late_joiners': late_joiners,
            'early_leavers': early_leavers,
            'substitutions': substitutions,
            'round_rosters': round_rosters,
            'total_rounds': total_rounds,
            'summary': self._generate_summary(
                player_activity, roster_changes, 
                full_session, late_joiners, early_leavers, substitutions
            )
        }
        
        logger.info(f"✅ Analysis complete: {len(full_session)} full-session, "
                   f"{len(late_joiners)} late joiners, "
                   f"{len(early_leavers)} early leavers, "
                   f"{len(substitutions)} substitutions")
        
        return result
    
    def _get_player_activity(
        self,
        db: sqlite3.Connection,
        session_date: str
    ) -> Dict[str, PlayerActivity]:
        """Get detailed player activity for session"""
        cursor = db.cursor()
        
        query = """
            SELECT 
                player_guid,
                player_name,
                round_number,
                team
            FROM player_comprehensive_stats
            WHERE session_date LIKE ?
            ORDER BY round_number, player_guid
        """
        
        cursor.execute(query, (f"{session_date}%",))
        rows = cursor.fetchall()
        
        # Build activity records
        activity = {}
        
        for guid, name, round_num, game_team in rows:
            if guid not in activity:
                activity[guid] = PlayerActivity(
                    player_guid=guid,
                    player_name=name,
                    first_round=round_num,
                    last_round=round_num,
                    rounds_played=set(),
                    game_teams={}
                )
            
            activity[guid].last_round = max(activity[guid].last_round, round_num)
            activity[guid].rounds_played.add(round_num)
            activity[guid].game_teams[round_num] = game_team
        
        return activity
    
    def _get_round_rosters(
        self,
        db: sqlite3.Connection,
        session_date: str
    ) -> Dict[int, Dict]:
        """Get rosters for each round"""
        cursor = db.cursor()
        
        query = """
            SELECT DISTINCT
                round_number,
                team,
                player_guid,
                player_name
            FROM player_comprehensive_stats
            WHERE session_date LIKE ?
            ORDER BY round_number, team, player_guid
        """
        
        cursor.execute(query, (f"{session_date}%",))
        rows = cursor.fetchall()
        
        rosters = defaultdict(lambda: {'team1': set(), 'team2': set()})
        
        for round_num, game_team, guid, name in rows:
            team_key = 'team1' if game_team == 1 else 'team2'
            # Use set to avoid duplicates, store tuples
            rosters[round_num][team_key].add((guid, name))
        
        # Convert sets to lists of dicts
        result = {}
        for round_num, teams in rosters.items():
            result[round_num] = {
                'team1': [{'guid': g, 'name': n} for g, n in sorted(teams['team1'])],
                'team2': [{'guid': g, 'name': n} for g, n in sorted(teams['team2'])]
            }
        
        return result
    
    def _detect_roster_changes(
        self,
        round_rosters: Dict[int, Dict],
        player_activity: Dict[str, PlayerActivity]
    ) -> List[RosterChange]:
        """Detect changes between rounds"""
        changes = []
        
        rounds = sorted(round_rosters.keys())
        
        for i in range(len(rounds) - 1):
            current_round = rounds[i]
            next_round = rounds[i + 1]
            
            # Check each game team
            for game_team_num, team_key in [(1, 'team1'), (2, 'team2')]:
                current_guids = {p['guid'] for p in round_rosters[current_round][team_key]}
                next_guids = {p['guid'] for p in round_rosters[next_round][team_key]}
                
                # Players who left
                departed = current_guids - next_guids
                for guid in departed:
                    name = player_activity[guid].player_name
                    changes.append(RosterChange(
                        round_number=next_round,
                        change_type='departure',
                        game_team=game_team_num,
                        player_out=name,
                        guid_out=guid
                    ))
                
                # Players who joined
                joined = next_guids - current_guids
                for guid in joined:
                    name = player_activity[guid].player_name
                    changes.append(RosterChange(
                        round_number=next_round,
                        change_type='addition',
                        game_team=game_team_num,
                        player_in=name,
                        guid_in=guid
                    ))
        
        return changes
    
    def _detect_substitutions(
        self,
        roster_changes: List[RosterChange]
    ) -> List[Tuple[str, str, int]]:
        """
        Detect likely substitutions (player leaves, another joins same round/next)
        
        Returns: [(guid_out, guid_in, round_number)]
        """
        substitutions = []
        
        # Group changes by round and team
        by_round_team = defaultdict(lambda: {'departures': [], 'additions': []})
        
        for change in roster_changes:
            key = (change.round_number, change.game_team)
            if change.change_type == 'departure':
                by_round_team[key]['departures'].append(change)
            elif change.change_type == 'addition':
                by_round_team[key]['additions'].append(change)
        
        # Find matching departures and additions
        for (round_num, team), changes in by_round_team.items():
            deps = changes['departures']
            adds = changes['additions']
            
            # If same number left and joined, likely substitutions
            if len(deps) > 0 and len(adds) > 0:
                for dep, add in zip(deps, adds):
                    substitutions.append((
                        dep.guid_out,
                        add.guid_in,
                        round_num
                    ))
        
        return substitutions
    
    def _generate_summary(
        self,
        player_activity: Dict,
        roster_changes: List[RosterChange],
        full_session: List[str],
        late_joiners: List[str],
        early_leavers: List[str],
        substitutions: List
    ) -> str:
        """Generate human-readable summary"""
        lines = []
        
        lines.append(f"Total Players: {len(player_activity)}")
        lines.append(f"Full Session: {len(full_session)}")
        
        if late_joiners:
            lines.append(f"Late Joiners: {len(late_joiners)}")
            for guid in late_joiners[:3]:
                activity = player_activity[guid]
                lines.append(f"  - {activity.player_name} (joined round {activity.first_round})")
            if len(late_joiners) > 3:
                lines.append(f"  ...and {len(late_joiners) - 3} more")
        
        if early_leavers:
            lines.append(f"Early Leavers: {len(early_leavers)}")
            for guid in early_leavers[:3]:
                activity = player_activity[guid]
                lines.append(f"  - {activity.player_name} (left after round {activity.last_round})")
            if len(early_leavers) > 3:
                lines.append(f"  ...and {len(early_leavers) - 3} more")
        
        if substitutions:
            lines.append(f"Substitutions: {len(substitutions)}")
        
        return "\n".join(lines)
    
    def adjust_team_detection_for_substitutions(
        self,
        team_assignments: Dict[str, str],
        substitution_analysis: Dict
    ) -> Dict[str, str]:
        """
        Adjust team assignments based on substitution analysis
        
        Strategy: If player B replaced player A, assign player B 
        to the same team as player A.
        
        Args:
            team_assignments: {guid: 'A' or 'B'}
            substitution_analysis: Result from analyze_session_roster_changes
            
        Returns:
            Adjusted team assignments
        """
        if not substitution_analysis or 'substitutions' not in substitution_analysis:
            return team_assignments
        
        adjusted = team_assignments.copy()
        substitutions = substitution_analysis['substitutions']
        
        for guid_out, guid_in, round_num in substitutions:
            # If we know the outgoing player's team, assign incoming to same team
            if guid_out in adjusted and guid_in in adjusted:
                logger.info(f"Substitution detected: Assigning {guid_in} to same team as {guid_out}")
                adjusted[guid_in] = adjusted[guid_out]
        
        return adjusted


def demonstrate_substitution_detection(session_date: str, db_path: str = "bot/etlegacy_production.db"):
    """Demo function to show substitution detection in action"""
    import sqlite3
    
    db = sqlite3.connect(db_path)
    detector = SubstitutionDetector()
    
    print("=" * 80)
    print("🔄 SUBSTITUTION DETECTION ANALYSIS")
    print("=" * 80)
    print(f"Session: {session_date}")
    print()
    
    result = detector.analyze_session_roster_changes(db, session_date)
    
    if not result:
        print("❌ No data found")
        db.close()
        return
    
    print("📊 SESSION OVERVIEW")
    print("-" * 80)
    print(result['summary'])
    print()
    
    # Show round-by-round rosters
    print("🔍 ROUND-BY-ROUND ROSTERS")
    print("-" * 80)
    round_rosters = result['round_rosters']
    
    for round_num in sorted(round_rosters.keys())[:5]:  # Show first 5 rounds
        roster = round_rosters[round_num]
        print(f"\nRound {round_num}:")
        print(f"  Team 1 ({len(roster['team1'])} players): {', '.join(p['name'] for p in roster['team1'][:5])}")
        if len(roster['team1']) > 5:
            print(f"         ...and {len(roster['team1']) - 5} more")
        print(f"  Team 2 ({len(roster['team2'])} players): {', '.join(p['name'] for p in roster['team2'][:5])}")
        if len(roster['team2']) > 5:
            print(f"         ...and {len(roster['team2']) - 5} more")
    
    if len(round_rosters) > 5:
        print(f"\n  ...and {len(round_rosters) - 5} more rounds")
    
    print()
    
    # Show roster changes
    if result['roster_changes']:
        print("📝 ROSTER CHANGES")
        print("-" * 80)
        for change in result['roster_changes'][:10]:  # Show first 10
            print(f"  {change}")
        
        if len(result['roster_changes']) > 10:
            print(f"  ...and {len(result['roster_changes']) - 10} more changes")
        print()
    
    # Show substitutions
    if result['substitutions']:
        print("🔄 DETECTED SUBSTITUTIONS")
        print("-" * 80)
        player_activity = result['player_activity']
        for guid_out, guid_in, round_num in result['substitutions']:
            name_out = player_activity[guid_out].player_name
            name_in = player_activity[guid_in].player_name
            print(f"  Round {round_num}: {name_out} → {name_in}")
        print()
    
    print("=" * 80)
    
    db.close()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        demonstrate_substitution_detection(sys.argv[1])
    else:
        print("Usage: python substitution_detector.py <session_date>")
        print("Example: python substitution_detector.py 2025-11-01")
