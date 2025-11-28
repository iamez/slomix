"""
Match Prediction Engine
=======================
Predicts match outcomes based on:
- Head-to-head history (40% weight)
- Recent form (25% weight)
- Map performance (20% weight)
- Substitution impact (15% weight)

Phase 3: Competitive Analytics
"""

import logging
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class PredictionEngine:
    """
    Weighted prediction engine for ET:Legacy matches.

    Weights (configurable):
    - H2H_WEIGHT: 0.40 (head-to-head history)
    - FORM_WEIGHT: 0.25 (recent performance)
    - MAP_WEIGHT: 0.20 (map-specific performance)
    - SUB_WEIGHT: 0.15 (substitution impact)
    """

    # Configurable weights
    H2H_WEIGHT = 0.40
    FORM_WEIGHT = 0.25
    MAP_WEIGHT = 0.20
    SUB_WEIGHT = 0.15

    # Minimum data thresholds
    MIN_H2H_MATCHES = 3  # Need 3+ matches for H2H to count
    MIN_FORM_MATCHES = 5  # Need 5+ recent matches for form

    def __init__(self, db_adapter):
        """
        Initialize prediction engine.

        Args:
            db_adapter: DatabaseAdapter instance for async database queries
        """
        self.db = db_adapter
        logger.info("✅ PredictionEngine initialized")

    async def predict_match(
        self,
        team_a_guids: List[str],
        team_b_guids: List[str],
        map_name: Optional[str] = None
    ) -> Dict:
        """
        Generate match prediction with confidence scoring.

        Args:
            team_a_guids: List of player GUIDs for Team A
            team_b_guids: List of player GUIDs for Team B
            map_name: Optional map name for map-specific analysis

        Returns:
            {
                'team_a_win_probability': 0.65,
                'team_b_win_probability': 0.35,
                'confidence': 'high',  # high/medium/low
                'confidence_score': 0.85,
                'factors': {
                    'h2h': {'score': 0.7, 'details': '...', 'matches': 5},
                    'form': {'score': 0.6, 'details': '...'},
                    'map': {'score': 0.5, 'details': '...'},
                    'subs': {'score': 0.5, 'details': '...'}
                },
                'key_insight': 'Team A has won 4 of last 5 head-to-head matches'
            }
        """
        logger.info(f"🔮 Generating prediction: {len(team_a_guids)}v{len(team_b_guids)}")

        # Analyze each factor
        h2h = await self._analyze_head_to_head(team_a_guids, team_b_guids)
        form = await self._analyze_recent_form(team_a_guids, team_b_guids)
        map_perf = await self._analyze_map_performance(team_a_guids, team_b_guids, map_name)
        subs = await self._analyze_substitution_impact(team_a_guids, team_b_guids)

        # Calculate weighted score
        # Score > 0.5 means Team A favored, < 0.5 means Team B favored
        weighted_score = (
            h2h['score'] * self.H2H_WEIGHT +
            form['score'] * self.FORM_WEIGHT +
            map_perf['score'] * self.MAP_WEIGHT +
            subs['score'] * self.SUB_WEIGHT
        )

        # Convert to win probabilities
        # Apply sigmoid-like scaling to keep probabilities reasonable (30-70% range)
        team_a_prob = 0.3 + (weighted_score * 0.4)  # Maps 0-1 to 0.3-0.7
        team_b_prob = 1.0 - team_a_prob

        # Calculate confidence based on data availability
        confidence_score = self._calculate_confidence(h2h, form, map_perf, subs)
        confidence = self._score_to_confidence_label(confidence_score)

        # Generate key insight
        key_insight = self._generate_key_insight(h2h, form, map_perf, subs)

        logger.info(
            f"📊 Prediction complete: Team A {team_a_prob:.0%} vs Team B {team_b_prob:.0%} "
            f"(Confidence: {confidence})"
        )

        return {
            'team_a_win_probability': round(team_a_prob, 2),
            'team_b_win_probability': round(team_b_prob, 2),
            'confidence': confidence,
            'confidence_score': round(confidence_score, 2),
            'factors': {
                'h2h': h2h,
                'form': form,
                'map': map_perf,
                'subs': subs
            },
            'key_insight': key_insight,
            'weighted_score': round(weighted_score, 3)
        }

    async def store_prediction(
        self,
        prediction: Dict,
        split_data: Dict,
        session_date: str,
        discord_channel_id: Optional[int] = None,
        discord_message_id: Optional[int] = None
    ) -> int:
        """
        Store prediction in database for accuracy tracking.

        Args:
            prediction: Result from predict_match()
            split_data: Team split data from voice service
            session_date: Date of gaming session (YYYY-MM-DD)
            discord_channel_id: Optional Discord channel where prediction was posted
            discord_message_id: Optional Discord message ID for editing

        Returns:
            prediction_id: Database ID of stored prediction
        """
        try:
            # Extract factor details
            h2h = prediction['factors']['h2h']
            form = prediction['factors']['form']
            map_perf = prediction['factors']['map']
            subs = prediction['factors']['subs']

            # Prepare JSON fields
            team_a_guids_json = json.dumps(split_data['team_a_guids'])
            team_b_guids_json = json.dumps(split_data['team_b_guids'])
            team_a_discord_ids_json = json.dumps([int(id) for id in split_data['team_a_discord_ids']])
            team_b_discord_ids_json = json.dumps([int(id) for id in split_data['team_b_discord_ids']])

            # Prepare details JSON
            h2h_details_json = json.dumps({
                'matches': h2h.get('matches', 0),
                'team_a_wins': h2h.get('team_a_wins', 0),
                'team_b_wins': h2h.get('team_b_wins', 0),
                'details': h2h.get('details', '')
            })

            form_details_json = json.dumps({
                'team_a_form': form.get('team_a_form', '?-?'),
                'team_b_form': form.get('team_b_form', '?-?'),
                'details': form.get('details', '')
            })

            map_details_json = json.dumps({
                'details': map_perf.get('details', '')
            })

            subs_details_json = json.dumps({
                'team_a_subs': subs.get('team_a_subs', 0),
                'team_b_subs': subs.get('team_b_subs', 0),
                'details': subs.get('details', '')
            })

            query = """
                INSERT INTO match_predictions (
                    session_date,
                    map_name,
                    format,
                    team_a_channel_id,
                    team_b_channel_id,
                    team_a_guids,
                    team_b_guids,
                    team_a_discord_ids,
                    team_b_discord_ids,
                    team_a_win_probability,
                    team_b_win_probability,
                    confidence,
                    confidence_score,
                    h2h_score,
                    form_score,
                    map_score,
                    subs_score,
                    weighted_score,
                    key_insight,
                    h2h_details,
                    form_details,
                    map_details,
                    subs_details,
                    discord_channel_id,
                    discord_message_id,
                    guid_coverage
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                    $11, $12, $13, $14, $15, $16, $17, $18, $19, $20,
                    $21, $22, $23, $24, $25, $26
                )
                RETURNING id
            """

            params = (
                session_date,
                split_data.get('map_name'),
                split_data['format'],
                split_data['team_a_channel_id'],
                split_data['team_b_channel_id'],
                team_a_guids_json,
                team_b_guids_json,
                team_a_discord_ids_json,
                team_b_discord_ids_json,
                prediction['team_a_win_probability'],
                prediction['team_b_win_probability'],
                prediction['confidence'],
                prediction['confidence_score'],
                h2h['score'],
                form['score'],
                map_perf['score'],
                subs['score'],
                prediction['weighted_score'],
                prediction['key_insight'],
                h2h_details_json,
                form_details_json,
                map_details_json,
                subs_details_json,
                discord_channel_id,
                discord_message_id,
                split_data['guid_coverage']
            )

            result = await self.db.fetch_one(query, params)
            prediction_id = result[0]

            logger.info(f"💾 Prediction stored: ID={prediction_id}")
            return prediction_id

        except Exception as e:
            logger.error(f"❌ Failed to store prediction: {e}", exc_info=True)
            raise

    async def update_prediction_outcome(
        self,
        prediction_id: int,
        actual_winner: int,
        team_a_score: int,
        team_b_score: int
    ) -> None:
        """
        Update prediction with actual match outcome.

        Args:
            prediction_id: Database ID of prediction
            actual_winner: 1 = Team A won, 2 = Team B won, 0 = draw
            team_a_score: Rounds won by Team A
            team_b_score: Rounds won by Team B
        """
        try:
            # Get original prediction
            query_get = """
                SELECT team_a_win_probability, team_b_win_probability
                FROM match_predictions
                WHERE id = $1
            """
            result = await self.db.fetch_one(query_get, (prediction_id,))

            if not result:
                logger.warning(f"⚠️ Prediction {prediction_id} not found")
                return

            team_a_prob, team_b_prob = result

            # Determine if prediction was correct
            predicted_winner = 1 if team_a_prob > team_b_prob else 2
            if team_a_prob == team_b_prob:
                predicted_winner = 0  # Toss-up

            prediction_correct = (predicted_winner == actual_winner)

            # Calculate accuracy (Brier score: lower is better, 0 = perfect)
            # For binary outcomes, Brier score = (p - actual)^2
            if actual_winner == 1:
                brier_score = (1.0 - team_a_prob) ** 2
            elif actual_winner == 2:
                brier_score = (1.0 - team_b_prob) ** 2
            else:
                brier_score = 0.5  # Draw case

            # Convert to accuracy (higher is better, 1 = perfect)
            prediction_accuracy = 1.0 - brier_score

            # Update database
            query_update = """
                UPDATE match_predictions
                SET actual_winner = $1,
                    team_a_actual_score = $2,
                    team_b_actual_score = $3,
                    prediction_correct = $4,
                    prediction_accuracy = $5,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $6
            """

            await self.db.execute(query_update, (
                actual_winner,
                team_a_score,
                team_b_score,
                prediction_correct,
                prediction_accuracy,
                prediction_id
            ))

            logger.info(
                f"✅ Prediction {prediction_id} updated: "
                f"{'CORRECT' if prediction_correct else 'WRONG'} "
                f"(Accuracy: {prediction_accuracy:.2%})"
            )

        except Exception as e:
            logger.error(f"❌ Failed to update prediction outcome: {e}", exc_info=True)
            raise

    async def _analyze_head_to_head(
        self,
        team_a_guids: List[str],
        team_b_guids: List[str]
    ) -> Dict:
        """
        Analyze historical head-to-head matchups between these lineups.

        Returns score: >0.5 = Team A favored, <0.5 = Team B favored
        """
        # Find sessions where these teams (or similar) played each other
        # Use overlap percentage to find matches

        query = """
            WITH team_sessions AS (
                SELECT DISTINCT
                    DATE(round_date) as session_date,
                    player_guid,
                    team
                FROM player_comprehensive_stats
                WHERE round_number IN (1, 2)
                  AND round_date > $1
            )
            SELECT session_date, team, array_agg(DISTINCT player_guid) as guids
            FROM team_sessions
            GROUP BY session_date, team
            ORDER BY session_date DESC
        """

        # Look back 90 days
        cutoff = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')

        try:
            rows = await self.db.fetch_all(query, (cutoff,))

            # Find sessions with significant overlap
            # Group by session_date to match teams
            sessions_by_date = {}
            for session_date, team, guids in rows:
                if session_date not in sessions_by_date:
                    sessions_by_date[session_date] = []
                sessions_by_date[session_date].append((team, guids))

            # Calculate overlap for each historical session
            team_a_wins = 0
            team_b_wins = 0
            total_matches = 0

            team_a_set = set(team_a_guids)
            team_b_set = set(team_b_guids)

            for session_date, teams in sessions_by_date.items():
                if len(teams) != 2:
                    continue  # Skip sessions without 2 teams

                team_1_guids, team_2_guids = set(teams[0][1]), set(teams[1][1])

                # Calculate overlap with current teams
                overlap_1a = len(team_1_guids & team_a_set) / max(len(team_a_set), 1)
                overlap_1b = len(team_1_guids & team_b_set) / max(len(team_b_set), 1)
                overlap_2a = len(team_2_guids & team_a_set) / max(len(team_a_set), 1)
                overlap_2b = len(team_2_guids & team_b_set) / max(len(team_b_set), 1)

                # Need >50% overlap to count as same team
                if overlap_1a > 0.5 and overlap_2b > 0.5:
                    # Team 1 = Team A, Team 2 = Team B
                    # TODO: Get actual winner from session results (Phase 4)
                    total_matches += 1
                elif overlap_1b > 0.5 and overlap_2a > 0.5:
                    # Team 1 = Team B, Team 2 = Team A
                    total_matches += 1

            # Not enough H2H data
            if total_matches < self.MIN_H2H_MATCHES:
                return {
                    'score': 0.5,
                    'details': f'Insufficient H2H data ({total_matches} matches)',
                    'matches': total_matches,
                    'team_a_wins': 0,
                    'team_b_wins': 0,
                    'confidence': 'low'
                }

            # Calculate score
            # NOTE: Without session_results table, we can't determine winner yet
            # This will be completed in Phase 4
            score = 0.5  # Neutral until we have results

            return {
                'score': score,
                'details': f'Found {total_matches} H2H matches (results tracking in Phase 4)',
                'matches': total_matches,
                'team_a_wins': team_a_wins,
                'team_b_wins': team_b_wins,
                'confidence': 'medium' if total_matches >= 5 else 'low'
            }

        except Exception as e:
            logger.error(f"❌ H2H analysis failed: {e}", exc_info=True)
            return {
                'score': 0.5,
                'details': 'H2H analysis unavailable',
                'matches': 0,
                'confidence': 'low'
            }

    async def _analyze_recent_form(
        self,
        team_a_guids: List[str],
        team_b_guids: List[str]
    ) -> Dict:
        """
        Analyze recent form (last 5 sessions, regardless of opponent).

        Returns score: >0.5 = Team A has better form
        """
        # Placeholder - will be implemented when we have session results (Phase 4)
        logger.debug("Form analysis not yet implemented (Phase 4 dependency)")
        return {
            'score': 0.5,
            'details': 'Form analysis requires session results (Phase 4)',
            'team_a_form': '?-?',
            'team_b_form': '?-?',
            'confidence': 'low'
        }

    async def _analyze_map_performance(
        self,
        team_a_guids: List[str],
        team_b_guids: List[str],
        map_name: Optional[str]
    ) -> Dict:
        """
        Analyze map-specific performance.

        Returns score: >0.5 = Team A better on this map
        """
        if not map_name:
            return {
                'score': 0.5,
                'details': 'Map not specified',
                'confidence': 'low'
            }

        # Placeholder - will be implemented with map_performance table (Phase 4)
        logger.debug(f"Map performance analysis for {map_name} not yet implemented")
        return {
            'score': 0.5,
            'details': f'Map performance on {map_name} not yet tracked (Phase 4)',
            'confidence': 'low'
        }

    async def _analyze_substitution_impact(
        self,
        team_a_guids: List[str],
        team_b_guids: List[str]
    ) -> Dict:
        """
        Analyze impact of roster changes compared to typical lineups.

        Returns score: >0.5 = Team A has more consistent lineup
        """
        # Placeholder - check if teams have their regular players
        logger.debug("Substitution analysis not yet implemented")
        return {
            'score': 0.5,
            'details': 'Substitution analysis not yet implemented',
            'team_a_subs': 0,
            'team_b_subs': 0,
            'confidence': 'low'
        }

    def _calculate_confidence(
        self,
        h2h: Dict,
        form: Dict,
        map_perf: Dict,
        subs: Dict
    ) -> float:
        """
        Calculate overall prediction confidence (0-1).

        Weights each factor's confidence by its importance.
        """
        # Weight confidence by factor importance
        conf_scores = [
            (h2h.get('confidence', 'low'), self.H2H_WEIGHT),
            (form.get('confidence', 'low'), self.FORM_WEIGHT),
            (map_perf.get('confidence', 'low'), self.MAP_WEIGHT),
            (subs.get('confidence', 'low'), self.SUB_WEIGHT)
        ]

        conf_map = {'high': 1.0, 'medium': 0.6, 'low': 0.3}

        total = sum(conf_map.get(c, 0.3) * w for c, w in conf_scores)
        return total

    def _score_to_confidence_label(self, score: float) -> str:
        """Convert confidence score to human-readable label."""
        if score >= 0.7:
            return 'high'
        elif score >= 0.5:
            return 'medium'
        else:
            return 'low'

    def _generate_key_insight(
        self,
        h2h: Dict,
        form: Dict,
        map_perf: Dict,
        subs: Dict
    ) -> str:
        """Generate the most important insight for display."""
        insights = []

        # Prioritize H2H if we have data
        if h2h.get('matches', 0) >= 3:
            insights.append(h2h.get('details', ''))

        # Then form
        if form.get('confidence') == 'high':
            insights.append(form.get('details', ''))

        # Default message
        if not insights:
            return "Limited historical data - prediction may be less accurate"

        return insights[0]
