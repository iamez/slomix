"""
Match Prediction Embed Builder
===============================
Creates Discord embeds for match predictions

Phase 4: Database Tables & Live Scoring
"""

import discord
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class PredictionEmbedBuilder:
    """
    Builds Discord embeds for match predictions.
    """

    # Color scheme
    COLOR_HIGH_CONFIDENCE = 0x00FF00  # Green
    COLOR_MEDIUM_CONFIDENCE = 0xFFA500  # Orange
    COLOR_LOW_CONFIDENCE = 0xFF0000  # Red
    COLOR_NEUTRAL = 0x3498DB  # Blue

    def __init__(self):
        """Initialize embed builder."""
        logger.info("✅ PredictionEmbedBuilder initialized")

    def build_prediction_embed(
        self,
        prediction: Dict,
        split_data: Dict,
        player_names: Optional[Dict[str, str]] = None
    ) -> discord.Embed:
        """
        Build Discord embed for match prediction.

        Args:
            prediction: Result from PredictionEngine.predict_match()
            split_data: Team split data from voice service
            player_names: Optional dict mapping GUIDs to player names

        Returns:
            discord.Embed: Formatted prediction embed
        """
        # Determine embed color based on confidence
        confidence = prediction['confidence']
        if confidence == 'high':
            color = self.COLOR_HIGH_CONFIDENCE
        elif confidence == 'medium':
            color = self.COLOR_MEDIUM_CONFIDENCE
        else:
            color = self.COLOR_LOW_CONFIDENCE

        # Create embed
        embed = discord.Embed(
            title="🔮 Match Prediction",
            description=f"**{split_data['format']}** Competitive Match",
            color=color,
            timestamp=datetime.now()
        )

        # Add prediction probabilities
        team_a_prob = prediction['team_a_win_probability']
        team_b_prob = prediction['team_b_win_probability']

        # Create visual probability bars
        team_a_bar = self._create_probability_bar(team_a_prob)
        team_b_bar = self._create_probability_bar(team_b_prob)

        embed.add_field(
            name=f"🔵 Team A - {team_a_prob:.0%}",
            value=f"{team_a_bar}\n{self._format_team_roster(split_data['team_a_guids'], player_names)}",
            inline=False
        )

        embed.add_field(
            name=f"🔴 Team B - {team_b_prob:.0%}",
            value=f"{team_b_bar}\n{self._format_team_roster(split_data['team_b_guids'], player_names)}",
            inline=False
        )

        # Add confidence indicator
        confidence_emoji = {
            'high': '✅',
            'medium': '⚠️',
            'low': '❓'
        }

        embed.add_field(
            name="📊 Confidence",
            value=f"{confidence_emoji.get(confidence, '❓')} **{confidence.upper()}** ({prediction['confidence_score']:.0%})",
            inline=True
        )

        # Add format
        embed.add_field(
            name="🎮 Format",
            value=split_data['format'],
            inline=True
        )

        # Add GUID coverage
        guid_coverage = split_data.get('guid_coverage', 0.0)
        embed.add_field(
            name="🔗 Linked Players",
            value=f"{guid_coverage:.0%}",
            inline=True
        )

        # Add key insight
        embed.add_field(
            name="💡 Key Insight",
            value=prediction['key_insight'],
            inline=False
        )

        # Add factor breakdown
        factors = prediction['factors']
        factor_text = self._format_factor_breakdown(factors)
        embed.add_field(
            name="📈 Analysis Factors",
            value=factor_text,
            inline=False
        )

        # Footer
        embed.set_footer(text="Competitive Analytics • Prediction accuracy tracked")

        return embed

    def build_prediction_result_embed(
        self,
        prediction: Dict,
        split_data: Dict,
        actual_winner: int,
        team_a_score: int,
        team_b_score: int,
        player_names: Optional[Dict[str, str]] = None
    ) -> discord.Embed:
        """
        Build Discord embed for prediction result (after match completes).

        Args:
            prediction: Original prediction data
            split_data: Team split data
            actual_winner: 1 = Team A, 2 = Team B, 0 = draw
            team_a_score: Rounds won by Team A
            team_b_score: Rounds won by Team B
            player_names: Optional dict mapping GUIDs to player names

        Returns:
            discord.Embed: Formatted result embed
        """
        # Determine if prediction was correct
        team_a_prob = prediction['team_a_win_probability']
        team_b_prob = prediction['team_b_win_probability']
        predicted_winner = 1 if team_a_prob > team_b_prob else 2

        was_correct = (predicted_winner == actual_winner)

        # Color: Green if correct, Red if wrong
        color = 0x00FF00 if was_correct else 0xFF0000

        # Create embed
        embed = discord.Embed(
            title="🏆 Match Result",
            description=f"**{split_data['format']}** Match Complete",
            color=color,
            timestamp=datetime.now()
        )

        # Add result
        winner_text = "Team A" if actual_winner == 1 else "Team B" if actual_winner == 2 else "Draw"
        embed.add_field(
            name="🎯 Winner",
            value=f"**{winner_text}**",
            inline=True
        )

        embed.add_field(
            name="📊 Score",
            value=f"{team_a_score} - {team_b_score}",
            inline=True
        )

        # Add prediction accuracy
        accuracy_emoji = "✅" if was_correct else "❌"
        embed.add_field(
            name="🔮 Prediction",
            value=f"{accuracy_emoji} **{'CORRECT' if was_correct else 'INCORRECT'}**",
            inline=True
        )

        # Add predicted vs actual
        embed.add_field(
            name="📈 Predicted Probabilities",
            value=f"Team A: {team_a_prob:.0%}\nTeam B: {team_b_prob:.0%}",
            inline=True
        )

        embed.add_field(
            name="🏁 Actual Result",
            value=f"Team A: {team_a_score} rounds\nTeam B: {team_b_score} rounds",
            inline=True
        )

        # Footer
        embed.set_footer(text="Competitive Analytics • Building better predictions")

        return embed

    def _create_probability_bar(self, probability: float, length: int = 10) -> str:
        """
        Create visual probability bar.

        Args:
            probability: 0.0 to 1.0
            length: Number of blocks

        Returns:
            String with filled/empty blocks
        """
        filled = int(probability * length)
        empty = length - filled
        return f"{'█' * filled}{'░' * empty} {probability:.0%}"

    def _format_team_roster(
        self,
        guids: List[str],
        player_names: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Format team roster for display.

        Args:
            guids: List of player GUIDs
            player_names: Optional mapping of GUID to player name

        Returns:
            Formatted roster string
        """
        if not player_names:
            return f"{len(guids)} players"

        names = []
        for guid in guids:
            if guid in player_names:
                names.append(player_names[guid])
            else:
                names.append(f"Player_{guid[:8]}")

        # Limit to first 6 players to avoid embed size limits
        if len(names) > 6:
            names = names[:6] + [f"...+{len(names) - 6} more"]

        return ", ".join(names)

    def _format_factor_breakdown(self, factors: Dict) -> str:
        """
        Format factor breakdown for display.

        Args:
            factors: Factor analysis from prediction

        Returns:
            Formatted string with factor scores
        """
        lines = []

        # H2H
        h2h = factors['h2h']
        h2h_bar = self._create_mini_bar(h2h['score'], 5)
        lines.append(f"**Head-to-Head:** {h2h_bar} {h2h.get('details', 'N/A')}")

        # Form
        form = factors['form']
        form_bar = self._create_mini_bar(form['score'], 5)
        lines.append(f"**Recent Form:** {form_bar} {form.get('details', 'N/A')}")

        # Map
        map_perf = factors['map']
        map_bar = self._create_mini_bar(map_perf['score'], 5)
        lines.append(f"**Map Performance:** {map_bar} {map_perf.get('details', 'N/A')}")

        # Subs
        subs = factors['subs']
        subs_bar = self._create_mini_bar(subs['score'], 5)
        lines.append(f"**Substitutions:** {subs_bar} {subs.get('details', 'N/A')}")

        return "\n".join(lines)

    def _create_mini_bar(self, score: float, length: int = 5) -> str:
        """
        Create a small visual bar for factor scores.

        Args:
            score: 0.0 to 1.0
            length: Number of blocks

        Returns:
            String with blocks
        """
        # Normalize around 0.5 (neutral)
        # < 0.5 = Team B favored (red), > 0.5 = Team A favored (blue)
        filled = int(score * length)
        empty = length - filled

        if filled == empty or abs(filled - empty) <= 1:
            # Neutral
            return '⚪' * length
        elif filled > empty:
            # Team A favored
            return '🔵' * filled + '⚪' * empty
        else:
            # Team B favored
            return '🔴' * filled + '⚪' * empty

    def build_prediction_history_embed(
        self,
        predictions: List[Dict],
        title: str = "📊 Prediction History"
    ) -> discord.Embed:
        """
        Build embed showing prediction history and accuracy.

        Args:
            predictions: List of prediction records from database
            title: Embed title

        Returns:
            discord.Embed: Formatted history embed
        """
        embed = discord.Embed(
            title=title,
            color=self.COLOR_NEUTRAL,
            timestamp=datetime.now()
        )

        if not predictions:
            embed.description = "No predictions recorded yet."
            return embed

        # Calculate overall accuracy
        total = len(predictions)
        correct = sum(1 for p in predictions if p.get('prediction_correct'))
        accuracy_rate = (correct / total) if total > 0 else 0.0

        embed.add_field(
            name="📈 Overall Accuracy",
            value=f"**{accuracy_rate:.1%}** ({correct}/{total} correct)",
            inline=False
        )

        # Group by confidence level
        by_confidence = {
            'high': [],
            'medium': [],
            'low': []
        }

        for p in predictions:
            conf = p.get('confidence', 'low')
            if conf in by_confidence:
                by_confidence[conf].append(p)

        # Show accuracy by confidence
        for conf in ['high', 'medium', 'low']:
            preds = by_confidence[conf]
            if not preds:
                continue

            conf_total = len(preds)
            conf_correct = sum(1 for p in preds if p.get('prediction_correct'))
            conf_accuracy = (conf_correct / conf_total) if conf_total > 0 else 0.0

            emoji = {'high': '✅', 'medium': '⚠️', 'low': '❓'}[conf]

            embed.add_field(
                name=f"{emoji} {conf.title()} Confidence",
                value=f"{conf_accuracy:.1%} ({conf_correct}/{conf_total})",
                inline=True
            )

        embed.set_footer(text="Competitive Analytics")

        return embed
