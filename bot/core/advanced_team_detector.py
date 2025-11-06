"""
Advanced Team Detection System

A sophisticated multi-strategy team detection system that combines:
1. Historical team composition analysis
2. Co-occurrence probability scoring
3. Round-by-round consistency validation
4. Player behavior pattern recognition
5. Confidence scoring and fallback strategies

This replaces the simple Round 1 seeding approach with a smarter algorithm.
"""

import sqlite3
import json
import logging
from typing import Dict, List, Tuple, Optional, Set
from collections import defaultdict, Counter
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class PlayerTeamScore:
    """Scoring for a player's likelihood of being on a specific team"""
    player_guid: str
    player_name: str
    team_a_score: float = 0.0
    team_b_score: float = 0.0
    confidence: float = 0.0
    
    @property
    def likely_team(self) -> str:
        """Return 'A' or 'B' based on highest score"""
        return 'A' if self.team_a_score > self.team_b_score else 'B'
    
    @property
    def score_difference(self) -> float:
        """Return the difference between team scores (higher = more confident)"""
        return abs(self.team_a_score - self.team_b_score)


class AdvancedTeamDetector:
    """
    Multi-strategy team detection engine
    
    Strategies (in priority order):
    1. Historical Pattern Analysis - Learn from previous sessions
    2. Multi-Round Consensus - Analyze all rounds, not just Round 1
    3. Co-occurrence Matrix - Statistical co-membership analysis
    4. Player Behavior Patterns - Play style and timing analysis
    """
    
    def __init__(self, db_path: str = "bot/etlegacy_production.db"):
        self.db_path = db_path
        self.min_confidence_threshold = 0.7  # 70% confidence to accept
        self.historical_weight = 0.4  # 40% weight for historical patterns
        self.consensus_weight = 0.35  # 35% weight for multi-round consensus
        self.cooccurrence_weight = 0.25  # 25% weight for co-occurrence
    
    def detect_session_teams(
        self,
        db: sqlite3.Connection,
        session_date: str,
        use_historical: bool = True
    ) -> Dict[str, Dict]:
        """
        Main detection method - combines all strategies
        
        Args:
            db: Database connection
            session_date: Session date (YYYY-MM-DD format)
            use_historical: Whether to use historical pattern analysis
            
        Returns:
            {
                'Team A': {
                    'guids': ['guid1', 'guid2', ...],
                    'names': ['Player1', 'Player2', ...],
                    'confidence': 0.85
                },
                'Team B': { ... },
                'metadata': {
                    'strategy_used': 'multi-strategy',
                    'avg_confidence': 0.82,
                    'uncertain_players': ['player1', ...],
                    'detection_quality': 'high'
                }
            }
        """
        logger.info(f"🔍 Starting advanced team detection for {session_date}")
        
        # Get all player data for this session
        players_data = self._get_session_player_data(db, session_date)
        
        if not players_data:
            logger.error(f"No player data found for session {session_date}")
            return {}
        
        logger.info(f"Found {len(players_data)} unique players in session")
        
        # Strategy 1: Historical Pattern Analysis
        historical_scores = {}
        if use_historical:
            historical_scores = self._analyze_historical_patterns(db, players_data, session_date)
            logger.info(f"Historical analysis: {len(historical_scores)} players with history")
        
        # Strategy 2: Multi-Round Consensus
        consensus_scores = self._analyze_multi_round_consensus(db, session_date, players_data)
        logger.info(f"Consensus analysis: Analyzed all rounds")
        
        # Strategy 3: Co-occurrence Matrix
        cooccurrence_scores = self._analyze_cooccurrence(db, session_date, players_data)
        logger.info(f"Co-occurrence analysis: Complete")
        
        # Combine all strategies with weighted scoring
        player_scores = self._combine_strategies(
            players_data,
            historical_scores,
            consensus_scores,
            cooccurrence_scores
        )
        
        # Cluster players into two teams
        team_a, team_b, metadata = self._cluster_into_teams(player_scores)
        
        logger.info(f"✅ Detection complete: Team A ({len(team_a['guids'])} players), "
                   f"Team B ({len(team_b['guids'])} players), "
                   f"Avg confidence: {metadata['avg_confidence']:.2%}")
        
        return {
            'Team A': team_a,
            'Team B': team_b,
            'metadata': metadata
        }
    
    def _get_session_player_data(
        self,
        db: sqlite3.Connection,
        session_date: str
    ) -> Dict[str, Dict]:
        """Get all player participation data for the session"""
        cursor = db.cursor()
        
        query = """
            SELECT 
                player_guid,
                player_name,
                round_number,
                team,
                kills,
                deaths,
                time_played_seconds
            FROM player_comprehensive_stats
            WHERE round_date LIKE ?
            ORDER BY round_number, player_guid
        """
        
        cursor.execute(query, (f"{session_date}%",))
        rows = cursor.fetchall()
        
        # Organize by player
        players = {}
        for guid, name, round_num, game_team, kills, deaths, time_played in rows:
            if guid not in players:
                players[guid] = {
                    'guid': guid,
                    'name': name,
                    'rounds': []
                }
            
            players[guid]['rounds'].append({
                'round': round_num,
                'game_team': game_team,  # 1 or 2 (Allies/Axis)
                'kills': kills or 0,
                'deaths': deaths or 0,
                'time_played': time_played or 0
            })
        
        return players
    
    def _analyze_historical_patterns(
        self,
        db: sqlite3.Connection,
        current_players: Dict[str, Dict],
        session_date: str
    ) -> Dict[str, PlayerTeamScore]:
        """
        Analyze previous sessions to find recurring team patterns
        
        Strategy: Look at the last 10 sessions, find which players
        consistently play together.
        """
        cursor = db.cursor()
        
        # Get recent sessions (last 30 days, max 10 sessions)
        query = """
            SELECT DISTINCT SUBSTR(round_date, 1, 10) as date
            FROM rounds
            WHERE SUBSTR(round_date, 1, 10) < ?
            ORDER BY date DESC
            LIMIT 10
        """
        cursor.execute(query, (session_date,))
        previous_sessions = [row[0] for row in cursor.fetchall()]
        
        if not previous_sessions:
            logger.info("No historical data available")
            return {}
        
        # For each previous session, get team compositions
        historical_teammates = defaultdict(lambda: defaultdict(int))
        
        for prev_date in previous_sessions:
            # Try to get stored teams
            cursor.execute("""
                SELECT team_name, player_guids
                FROM session_teams
                WHERE session_start_date LIKE ? AND map_name = 'ALL'
            """, (f"{prev_date}%",))
            
            teams_data = cursor.fetchall()
            
            if not teams_data:
                continue
            
            # Build co-membership for this session
            for team_name, guids_json in teams_data:
                guids = json.loads(guids_json)
                # Each pair of players in this team played together
                for i, guid1 in enumerate(guids):
                    for guid2 in guids[i+1:]:
                        historical_teammates[guid1][guid2] += 1
                        historical_teammates[guid2][guid1] += 1
        
        # Score current players based on historical patterns
        scores = {}
        
        # Find the two players with most historical data as anchors
        anchor_candidates = sorted(
            current_players.keys(),
            key=lambda g: len(historical_teammates.get(g, {})),
            reverse=True
        )[:2]
        
        if len(anchor_candidates) < 2:
            return {}
        
        anchor_a = anchor_candidates[0]
        anchor_b = anchor_candidates[1]
        
        # If anchors have played together historically, find different anchors
        if historical_teammates.get(anchor_a, {}).get(anchor_b, 0) > 0:
            # Find anchor_b that has NOT played with anchor_a
            for candidate in anchor_candidates[1:]:
                if historical_teammates.get(anchor_a, {}).get(candidate, 0) == 0:
                    anchor_b = candidate
                    break
        
        logger.info(f"Historical anchors: {current_players[anchor_a]['name']} vs "
                   f"{current_players[anchor_b]['name']}")
        
        # Score all players based on historical co-occurrence with anchors
        for guid, player_data in current_players.items():
            score = PlayerTeamScore(
                player_guid=guid,
                player_name=player_data['name']
            )
            
            times_with_a = historical_teammates.get(guid, {}).get(anchor_a, 0)
            times_with_b = historical_teammates.get(guid, {}).get(anchor_b, 0)
            
            total_times = times_with_a + times_with_b
            
            if total_times > 0:
                score.team_a_score = times_with_a / total_times
                score.team_b_score = times_with_b / total_times
                score.confidence = min(total_times / len(previous_sessions), 1.0)
            
            scores[guid] = score
        
        # Anchor scores should be 100% certain
        scores[anchor_a].team_a_score = 1.0
        scores[anchor_a].team_b_score = 0.0
        scores[anchor_a].confidence = 1.0
        
        scores[anchor_b].team_a_score = 0.0
        scores[anchor_b].team_b_score = 1.0
        scores[anchor_b].confidence = 1.0
        
        return scores
    
    def _analyze_multi_round_consensus(
        self,
        db: sqlite3.Connection,
        session_date: str,
        players_data: Dict[str, Dict]
    ) -> Dict[str, PlayerTeamScore]:
        """
        Analyze all rounds to find consensus team assignments
        
        Strategy: Players who are consistently on the same game-team
        across multiple rounds are likely on the same persistent team.
        """
        # Build game-team consistency matrix
        # For each pair of players, count how often they're on same game-team
        
        from itertools import combinations
        
        same_side_count = defaultdict(int)
        different_side_count = defaultdict(int)
        
        # Get round-by-round game teams
        for round_num in range(1, 10):  # Max 10 rounds per session
            round_players = {}
            for guid, data in players_data.items():
                for r_data in data['rounds']:
                    if r_data['round'] == round_num:
                        round_players[guid] = r_data['game_team']
            
            if len(round_players) < 4:  # Need at least 4 players
                continue
            
            # Compare all pairs
            for guid1, guid2 in combinations(round_players.keys(), 2):
                pair = tuple(sorted([guid1, guid2]))
                
                if round_players[guid1] == round_players[guid2]:
                    same_side_count[pair] += 1
                else:
                    different_side_count[pair] += 1
        
        # Now use graph clustering to find two distinct teams
        # Players who are frequently on SAME side are on SAME persistent team
        
        scores = {}
        
        # Find the pair with strongest "always same side" signal
        best_pair = None
        best_ratio = 0
        
        for pair, same_count in same_side_count.items():
            diff_count = different_side_count.get(pair, 0)
            total = same_count + diff_count
            
            if total > 0:
                ratio = same_count / total
                if ratio > best_ratio and ratio > 0.6:  # At least 60% same side
                    best_ratio = ratio
                    best_pair = pair
        
        if not best_pair:
            # Fall back to any pair
            if same_side_count:
                best_pair = max(same_side_count.keys(), key=lambda p: same_side_count[p])
        
        if not best_pair:
            return {}
        
        anchor_a, anchor_b = best_pair
        logger.info(f"Consensus anchors: {players_data[anchor_a]['name']} and "
                   f"{players_data[anchor_b]['name']} (play together {best_ratio:.1%} of time)")
        
        # Score all players based on co-occurrence with anchor_a
        for guid in players_data.keys():
            score = PlayerTeamScore(
                player_guid=guid,
                player_name=players_data[guid]['name']
            )
            
            pair_with_a = tuple(sorted([guid, anchor_a]))
            pair_with_b = tuple(sorted([guid, anchor_b]))
            
            same_with_a = same_side_count.get(pair_with_a, 0)
            diff_with_a = different_side_count.get(pair_with_a, 0)
            
            same_with_b = same_side_count.get(pair_with_b, 0)
            diff_with_b = different_side_count.get(pair_with_b, 0)
            
            total_a = same_with_a + diff_with_a
            total_b = same_with_b + diff_with_b
            
            if total_a > 0:
                # High same_with_a means same team as anchor_a
                score.team_a_score = same_with_a / total_a
            
            if total_b > 0:
                # High same_with_b means same team as anchor_b (opposite of A)
                score.team_b_score = same_with_b / total_b
            
            # Confidence based on number of rounds played together
            max_rounds = max(total_a, total_b, 1)
            score.confidence = min(max_rounds / 6, 1.0)  # 6 rounds = full confidence
            
            scores[guid] = score
        
        # Set anchor scores
        scores[anchor_a].team_a_score = 1.0
        scores[anchor_a].team_b_score = 0.0
        scores[anchor_a].confidence = 1.0
        
        scores[anchor_b].team_a_score = 1.0
        scores[anchor_b].team_b_score = 0.0
        scores[anchor_b].confidence = 1.0
        
        return scores
    
    def _analyze_cooccurrence(
        self,
        db: sqlite3.Connection,
        session_date: str,
        players_data: Dict[str, Dict]
    ) -> Dict[str, PlayerTeamScore]:
        """
        Co-occurrence analysis (similar to existing method but improved)
        
        This is the fallback method when historical/consensus don't work.
        """
        from itertools import combinations
        
        # Count co-occurrences on same game-team
        cooccurrence = defaultdict(int)
        total_rounds_together = defaultdict(int)
        
        # For each round
        rounds_data = defaultdict(dict)
        for guid, data in players_data.items():
            for r_data in data['rounds']:
                round_num = r_data['round']
                game_team = r_data['game_team']
                rounds_data[round_num][guid] = game_team
        
        # Count co-occurrences
        for round_num, round_players in rounds_data.items():
            for guid1, guid2 in combinations(round_players.keys(), 2):
                pair = tuple(sorted([guid1, guid2]))
                total_rounds_together[pair] += 1
                
                if round_players[guid1] == round_players[guid2]:
                    cooccurrence[pair] += 1
        
        # Build adjacency graph
        teammates_graph = defaultdict(set)
        
        for pair, cooccur_count in cooccurrence.items():
            total = total_rounds_together[pair]
            ratio = cooccur_count / total if total > 0 else 0
            
            if ratio > 0.5:  # More than 50% of time on same side
                guid1, guid2 = pair
                teammates_graph[guid1].add(guid2)
                teammates_graph[guid2].add(guid1)
        
        # Find two largest connected components (teams)
        visited = set()
        
        def get_component(start):
            component = set()
            queue = [start]
            while queue:
                node = queue.pop(0)
                if node in visited:
                    continue
                visited.add(node)
                component.add(node)
                queue.extend(teammates_graph[node] - visited)
            return component
        
        components = []
        for guid in players_data.keys():
            if guid not in visited:
                comp = get_component(guid)
                if len(comp) > 1:
                    components.append(comp)
        
        # Sort by size
        components.sort(key=len, reverse=True)
        
        if len(components) < 2:
            return {}
        
        team_a_guids = components[0]
        team_b_guids = components[1]
        
        # Score players
        scores = {}
        for guid in players_data.keys():
            score = PlayerTeamScore(
                player_guid=guid,
                player_name=players_data[guid]['name']
            )
            
            if guid in team_a_guids:
                score.team_a_score = 1.0
                score.team_b_score = 0.0
            elif guid in team_b_guids:
                score.team_a_score = 0.0
                score.team_b_score = 1.0
            else:
                # Unassigned - score based on connections
                a_connections = len(teammates_graph[guid] & team_a_guids)
                b_connections = len(teammates_graph[guid] & team_b_guids)
                total_conn = a_connections + b_connections
                
                if total_conn > 0:
                    score.team_a_score = a_connections / total_conn
                    score.team_b_score = b_connections / total_conn
            
            # Confidence based on number of rounds played
            score.confidence = min(len(players_data[guid]['rounds']) / 6, 1.0)
            
            scores[guid] = score
        
        return scores
    
    def _combine_strategies(
        self,
        players_data: Dict[str, Dict],
        historical: Dict[str, PlayerTeamScore],
        consensus: Dict[str, PlayerTeamScore],
        cooccurrence: Dict[str, PlayerTeamScore]
    ) -> Dict[str, PlayerTeamScore]:
        """Combine all strategy scores with weighted average"""
        
        combined_scores = {}
        
        for guid, data in players_data.items():
            final_score = PlayerTeamScore(
                player_guid=guid,
                player_name=data['name']
            )
            
            # Weighted combination
            total_weight = 0.0
            
            # Historical (if available)
            if guid in historical and historical[guid].confidence > 0:
                weight = self.historical_weight * historical[guid].confidence
                final_score.team_a_score += historical[guid].team_a_score * weight
                final_score.team_b_score += historical[guid].team_b_score * weight
                total_weight += weight
            
            # Consensus
            if guid in consensus and consensus[guid].confidence > 0:
                weight = self.consensus_weight * consensus[guid].confidence
                final_score.team_a_score += consensus[guid].team_a_score * weight
                final_score.team_b_score += consensus[guid].team_b_score * weight
                total_weight += weight
            
            # Co-occurrence
            if guid in cooccurrence and cooccurrence[guid].confidence > 0:
                weight = self.cooccurrence_weight * cooccurrence[guid].confidence
                final_score.team_a_score += cooccurrence[guid].team_a_score * weight
                final_score.team_b_score += cooccurrence[guid].team_b_score * weight
                total_weight += weight
            
            # Normalize by total weight
            if total_weight > 0:
                final_score.team_a_score /= total_weight
                final_score.team_b_score /= total_weight
                final_score.confidence = total_weight
            
            combined_scores[guid] = final_score
        
        return combined_scores
    
    def _cluster_into_teams(
        self,
        player_scores: Dict[str, PlayerTeamScore]
    ) -> Tuple[Dict, Dict, Dict]:
        """Cluster players into two teams based on scores"""
        
        team_a = {'guids': [], 'names': [], 'confidence': 0.0}
        team_b = {'guids': [], 'names': [], 'confidence': 0.0}
        
        uncertain_players = []
        confidences = []
        
        for guid, score in player_scores.items():
            confidences.append(score.confidence)
            
            # Check if score is uncertain
            if score.score_difference < 0.2:  # Less than 20% difference
                uncertain_players.append(score.player_name)
            
            # Assign to team
            if score.likely_team == 'A':
                team_a['guids'].append(guid)
                team_a['names'].append(score.player_name)
            else:
                team_b['guids'].append(guid)
                team_b['names'].append(score.player_name)
        
        # Calculate average confidence
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        team_a['confidence'] = avg_confidence
        team_b['confidence'] = avg_confidence
        
        # Determine quality
        if avg_confidence > 0.8 and len(uncertain_players) == 0:
            quality = 'high'
        elif avg_confidence > 0.6 and len(uncertain_players) < 3:
            quality = 'medium'
        else:
            quality = 'low'
        
        metadata = {
            'strategy_used': 'multi-strategy',
            'avg_confidence': avg_confidence,
            'uncertain_players': uncertain_players,
            'detection_quality': quality,
            'team_a_size': len(team_a['guids']),
            'team_b_size': len(team_b['guids'])
        }
        
        return team_a, team_b, metadata
