"""
Predictions Cog - Commands for viewing and managing match predictions

Phase 5: Refinement & Polish

Commands:
- !predictions - View recent predictions
- !prediction_stats - View accuracy statistics
- !my_predictions - View predictions you participated in
"""

import discord
from discord.ext import commands
import logging
from typing import Optional
from datetime import datetime, timedelta

logger = logging.getLogger('PredictionsCog')


class PredictionsCog(commands.Cog, name="Predictions"):
    """Commands for viewing match predictions and accuracy statistics."""

    def __init__(self, bot):
        """
        Initialize Predictions cog.

        Args:
            bot: Discord bot instance
        """
        self.bot = bot
        self.config = bot.config
        self.db = bot.db_adapter

        # Import embed builder
        try:
            from bot.services.prediction_embed_builder import PredictionEmbedBuilder
            self.embed_builder = PredictionEmbedBuilder()
        except ImportError:
            self.embed_builder = None
            logger.warning("⚠️ PredictionEmbedBuilder not available")

        logger.info("✅ PredictionsCog loaded")

    @commands.command(name='predictions')
    async def predictions(self, ctx, limit: int = 5):
        """
        View recent match predictions.

        Usage:
            !predictions [limit]

        Examples:
            !predictions       - Show last 5 predictions
            !predictions 10    - Show last 10 predictions
        """
        try:
            # Validate limit
            if limit < 1 or limit > 20:
                await ctx.send("❌ Limit must be between 1 and 20")
                return

            # Fetch recent predictions
            query = """
                SELECT
                    id,
                    prediction_time,
                    format,
                    team_a_win_probability,
                    team_b_win_probability,
                    confidence,
                    key_insight,
                    actual_winner,
                    prediction_correct,
                    prediction_accuracy
                FROM match_predictions
                ORDER BY prediction_time DESC
                LIMIT $1
            """

            rows = await self.db.fetch_all(query, (limit,))

            if not rows:
                await ctx.send("📊 No predictions recorded yet. Play some matches to generate predictions!")
                return

            # Build embed
            embed = discord.Embed(
                title="🔮 Recent Match Predictions",
                description=f"Showing last {len(rows)} prediction(s)",
                color=0x3498DB,
                timestamp=datetime.now()
            )

            for row in rows:
                (pred_id, pred_time, format_str, team_a_prob, team_b_prob,
                 confidence, insight, actual_winner, pred_correct, pred_accuracy) = row

                # Format prediction info
                prob_bar = self._create_mini_bar(team_a_prob)

                # Status emoji
                if actual_winner is None:
                    status = "⏳ Pending"
                elif pred_correct:
                    status = f"✅ Correct ({pred_accuracy:.0%})"
                else:
                    status = f"❌ Incorrect ({pred_accuracy:.0%})"

                # Confidence emoji
                conf_emoji = {'high': '✅', 'medium': '⚠️', 'low': '❓'}.get(confidence, '❓')

                # Time ago
                time_ago = self._format_time_ago(pred_time)

                field_value = (
                    f"**{format_str}** Match - {time_ago}\n"
                    f"{prob_bar} Team A **{team_a_prob:.0%}** vs Team B **{team_b_prob:.0%}**\n"
                    f"{conf_emoji} {confidence.title()} Confidence\n"
                    f"{status}\n"
                    f"💡 _{insight}_"
                )

                embed.add_field(
                    name=f"Prediction #{pred_id}",
                    value=field_value,
                    inline=False
                )

            embed.set_footer(text="Use !prediction_stats for accuracy statistics")

            await ctx.send(embed=embed)
            logger.info(f"📊 {ctx.author} viewed {len(rows)} predictions")

        except Exception as e:
            logger.error(f"❌ Error in !predictions: {e}", exc_info=True)
            await ctx.send("❌ Failed to fetch predictions. Check logs for details.")

    @commands.command(name='prediction_stats')
    async def prediction_stats(self, ctx, days: int = 30):
        """
        View prediction accuracy statistics.

        Usage:
            !prediction_stats [days]

        Examples:
            !prediction_stats      - Last 30 days
            !prediction_stats 7    - Last 7 days
            !prediction_stats 90   - Last 90 days
        """
        try:
            # Validate days
            if days < 1 or days > 365:
                await ctx.send("❌ Days must be between 1 and 365")
                return

            cutoff_date = datetime.now() - timedelta(days=days)

            # Fetch statistics
            query = """
                SELECT
                    COUNT(*) as total_predictions,
                    COUNT(CASE WHEN actual_winner IS NOT NULL THEN 1 END) as completed,
                    COUNT(CASE WHEN prediction_correct = true THEN 1 END) as correct,
                    AVG(CASE WHEN actual_winner IS NOT NULL THEN prediction_accuracy END) as avg_accuracy,
                    COUNT(CASE WHEN confidence = 'high' THEN 1 END) as high_conf,
                    COUNT(CASE WHEN confidence = 'high' AND prediction_correct = true THEN 1 END) as high_correct,
                    COUNT(CASE WHEN confidence = 'medium' THEN 1 END) as medium_conf,
                    COUNT(CASE WHEN confidence = 'medium' AND prediction_correct = true THEN 1 END) as medium_correct,
                    COUNT(CASE WHEN confidence = 'low' THEN 1 END) as low_conf,
                    COUNT(CASE WHEN confidence = 'low' AND prediction_correct = true THEN 1 END) as low_correct
                FROM match_predictions
                WHERE prediction_time >= $1
            """

            row = await self.db.fetch_one(query, (cutoff_date,))

            if not row or row[0] == 0:
                await ctx.send(f"📊 No predictions found in the last {days} days.")
                return

            (total, completed, correct, avg_accuracy,
             high_conf, high_correct, medium_conf, medium_correct,
             low_conf, low_correct) = row

            # Calculate percentages
            completion_rate = (completed / total * 100) if total > 0 else 0
            accuracy_rate = (correct / completed * 100) if completed > 0 else 0
            avg_accuracy = avg_accuracy or 0.0

            high_accuracy = (high_correct / high_conf * 100) if high_conf > 0 else 0
            medium_accuracy = (medium_correct / medium_conf * 100) if medium_conf > 0 else 0
            low_accuracy = (low_correct / low_conf * 100) if low_conf > 0 else 0

            # Determine color based on accuracy
            if accuracy_rate >= 70:
                color = 0x00FF00  # Green
            elif accuracy_rate >= 50:
                color = 0xFFA500  # Orange
            else:
                color = 0xFF0000  # Red

            # Build embed
            embed = discord.Embed(
                title="📈 Prediction Accuracy Statistics",
                description=f"Analysis of last **{days} days**",
                color=color,
                timestamp=datetime.now()
            )

            # Overall stats
            embed.add_field(
                name="📊 Overall Performance",
                value=(
                    f"**Total Predictions:** {total}\n"
                    f"**Completed Matches:** {completed} ({completion_rate:.0f}%)\n"
                    f"**Correct Predictions:** {correct}/{completed}\n"
                    f"**Accuracy Rate:** **{accuracy_rate:.1f}%**\n"
                    f"**Avg Brier Score:** {avg_accuracy:.3f}"
                ),
                inline=False
            )

            # Confidence breakdown
            conf_value = []
            if high_conf > 0:
                conf_value.append(f"✅ **High:** {high_accuracy:.1f}% ({high_correct}/{high_conf})")
            if medium_conf > 0:
                conf_value.append(f"⚠️ **Medium:** {medium_accuracy:.1f}% ({medium_correct}/{medium_conf})")
            if low_conf > 0:
                conf_value.append(f"❓ **Low:** {low_accuracy:.1f}% ({low_correct}/{low_conf})")

            if conf_value:
                embed.add_field(
                    name="🎯 Accuracy by Confidence",
                    value="\n".join(conf_value),
                    inline=False
                )

            # Get recent trend (last 10 predictions)
            trend_query = """
                SELECT prediction_correct
                FROM match_predictions
                WHERE prediction_time >= $1
                  AND actual_winner IS NOT NULL
                ORDER BY prediction_time DESC
                LIMIT 10
            """

            trend_rows = await self.db.fetch_all(trend_query, (cutoff_date,))

            if trend_rows:
                trend = "".join(["✅" if r[0] else "❌" for r in reversed(trend_rows)])
                embed.add_field(
                    name="📉 Recent Trend (Last 10)",
                    value=f"`{trend}`",
                    inline=False
                )

            # Performance rating
            if accuracy_rate >= 70:
                rating = "🏆 Excellent"
            elif accuracy_rate >= 60:
                rating = "⭐ Good"
            elif accuracy_rate >= 50:
                rating = "👍 Average"
            else:
                rating = "📚 Learning"

            embed.add_field(
                name="🎖️ Performance Rating",
                value=rating,
                inline=False
            )

            embed.set_footer(text="Competitive Analytics • Building better predictions")

            await ctx.send(embed=embed)
            logger.info(f"📈 {ctx.author} viewed prediction stats (accuracy: {accuracy_rate:.1f}%)")

        except Exception as e:
            logger.error(f"❌ Error in !prediction_stats: {e}", exc_info=True)
            await ctx.send("❌ Failed to fetch statistics. Check logs for details.")

    @commands.command(name='my_predictions')
    async def my_predictions(self, ctx):
        """
        View predictions for matches you participated in.

        Usage:
            !my_predictions

        Shows all predictions where you were on one of the teams.
        """
        try:
            # Get user's Discord ID
            discord_id = ctx.author.id

            # Check if user has linked account
            link_query = """
                SELECT et_guid
                FROM player_links
                WHERE discord_id = $1
            """
            link_row = await self.db.fetch_one(link_query, (discord_id,))

            if not link_row:
                await ctx.send(
                    "❌ You haven't linked your account yet!\n"
                    f"Use `!link` to connect your Discord account to your ET:Legacy profile."
                )
                return

            player_guid = link_row[0]

            # Find predictions where this player participated
            query = """
                SELECT
                    id,
                    prediction_time,
                    format,
                    team_a_guids,
                    team_b_guids,
                    team_a_win_probability,
                    team_b_win_probability,
                    confidence,
                    actual_winner,
                    prediction_correct
                FROM match_predictions
                WHERE team_a_guids LIKE $1
                   OR team_b_guids LIKE $1
                ORDER BY prediction_time DESC
                LIMIT 10
            """

            rows = await self.db.fetch_all(query, (f'%{player_guid}%',))

            if not rows:
                await ctx.send(
                    f"📊 No predictions found for **{ctx.author.display_name}**.\n"
                    f"Play some competitive matches to generate predictions!"
                )
                return

            # Build embed
            embed = discord.Embed(
                title=f"🔮 Your Match Predictions",
                description=f"Predictions for **{ctx.author.display_name}** (last 10 matches)",
                color=0x3498DB,
                timestamp=datetime.now()
            )

            for row in rows:
                (pred_id, pred_time, format_str, team_a_guids, team_b_guids,
                 team_a_prob, team_b_prob, confidence, actual_winner, pred_correct) = row

                # Determine which team the player was on
                import json
                team_a_list = json.loads(team_a_guids)
                team_b_list = json.loads(team_b_guids)

                if player_guid in team_a_list:
                    your_team = "Team A"
                    your_prob = team_a_prob
                    your_team_won = (actual_winner == 1) if actual_winner else None
                else:
                    your_team = "Team B"
                    your_prob = team_b_prob
                    your_team_won = (actual_winner == 2) if actual_winner else None

                # Format status
                if actual_winner is None:
                    status = "⏳ Match Pending"
                elif your_team_won:
                    status = "🏆 Your Team Won!"
                else:
                    status = "💔 Your Team Lost"

                # Prediction status
                if actual_winner is None:
                    pred_status = f"Predicted: **{your_prob:.0%}** win chance"
                elif pred_correct:
                    pred_status = f"✅ Prediction Correct"
                else:
                    pred_status = f"❌ Prediction Incorrect"

                time_ago = self._format_time_ago(pred_time)

                field_value = (
                    f"**{format_str}** Match - {time_ago}\n"
                    f"You were on: **{your_team}** ({your_prob:.0%} win chance)\n"
                    f"{status}\n"
                    f"{pred_status}"
                )

                embed.add_field(
                    name=f"Match #{pred_id}",
                    value=field_value,
                    inline=False
                )

            embed.set_footer(text=f"Link verified for {player_guid[:16]}...")

            await ctx.send(embed=embed)
            logger.info(f"👤 {ctx.author} viewed their predictions ({len(rows)} found)")

        except Exception as e:
            logger.error(f"❌ Error in !my_predictions: {e}", exc_info=True)
            await ctx.send("❌ Failed to fetch your predictions. Check logs for details.")

    def _create_mini_bar(self, probability: float, length: int = 10) -> str:
        """Create visual probability bar."""
        filled = int(probability * length)
        empty = length - filled
        return f"{'█' * filled}{'░' * empty}"

    def _format_time_ago(self, timestamp: datetime) -> str:
        """Format timestamp as 'X hours/days ago'."""
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))

        now = datetime.now()
        if timestamp.tzinfo:
            # Make now timezone-aware if timestamp is
            from datetime import timezone
            now = now.replace(tzinfo=timezone.utc)

        delta = now - timestamp

        if delta.days > 0:
            return f"{delta.days}d ago"
        elif delta.seconds >= 3600:
            hours = delta.seconds // 3600
            return f"{hours}h ago"
        elif delta.seconds >= 60:
            minutes = delta.seconds // 60
            return f"{minutes}m ago"
        else:
            return "just now"

    @commands.command(name='prediction_help')
    async def prediction_help(self, ctx):
        """Show help for prediction commands."""
        embed = discord.Embed(
            title="🔮 Prediction Commands Help",
            description="View and analyze match predictions",
            color=0x3498DB
        )

        embed.add_field(
            name="!predictions [limit]",
            value="View recent predictions (default: 5, max: 20)",
            inline=False
        )

        embed.add_field(
            name="!prediction_stats [days]",
            value="View accuracy statistics (default: 30 days)",
            inline=False
        )

        embed.add_field(
            name="!my_predictions",
            value="View predictions for matches you played in",
            inline=False
        )

        embed.add_field(
            name="💡 How Predictions Work",
            value=(
                "When players split into 2 voice channels (3v3, 4v4, etc.), "
                "the bot automatically generates a match prediction based on:\n"
                "• Head-to-head history (40%)\n"
                "• Recent form (25%)\n"
                "• Map performance (20%)\n"
                "• Roster changes (15%)"
            ),
            inline=False
        )

        await ctx.send(embed=embed)


async def setup(bot):
    """Load the Predictions cog."""
    await bot.add_cog(PredictionsCog(bot))
