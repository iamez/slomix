"""
Admin Predictions Cog - Administrative commands for managing predictions

Phase 5: Refinement & Polish

Admin Commands:
- !admin_predictions - View all predictions with filters
- !update_prediction_outcome - Manually update prediction result
- !recalculate_predictions - Recalculate accuracy for all predictions
- !prediction_performance - View system performance metrics
"""

import discord
from discord.ext import commands
import logging
import json
from typing import Optional
from datetime import datetime

logger = logging.getLogger('AdminPredictionsCog')


class AdminPredictionsCog(commands.Cog, name="Admin Predictions"):
    """Administrative commands for managing match predictions."""

    def __init__(self, bot):
        """
        Initialize Admin Predictions cog.

        Args:
            bot: Discord bot instance
        """
        self.bot = bot
        self.config = bot.config
        self.db = bot.db_adapter

        # Import prediction engine for recalculation
        try:
            from bot.services.prediction_engine import PredictionEngine
            self.prediction_engine = PredictionEngine(self.db)
        except ImportError:
            self.prediction_engine = None
            logger.warning("⚠️ PredictionEngine not available")

        logger.info("✅ AdminPredictionsCog loaded")

    def cog_check(self, ctx):
        """Check if user has permission to use admin commands."""
        # Check if user is in admin channels or has admin role
        if ctx.channel.id in self.config.admin_channels:
            return True

        # Check for admin/mod roles
        if hasattr(ctx.author, 'guild_permissions'):
            return ctx.author.guild_permissions.administrator

        return False

    @commands.command(name='admin_predictions')
    async def admin_predictions(self, ctx, status: str = "all", limit: int = 10):
        """
        View all predictions with filtering options.

        Usage:
            !admin_predictions [status] [limit]

        Status options: all, pending, completed, correct, incorrect

        Examples:
            !admin_predictions             - Show last 10 predictions (any status)
            !admin_predictions pending     - Show pending predictions
            !admin_predictions correct 20  - Show last 20 correct predictions
        """
        try:
            # Validate limit
            if limit < 1 or limit > 50:
                await ctx.send("❌ Limit must be between 1 and 50")
                return

            # Build query based on status filter
            base_query = """
                SELECT
                    id,
                    prediction_time,
                    session_date,
                    format,
                    team_a_win_probability,
                    team_b_win_probability,
                    confidence,
                    confidence_score,
                    key_insight,
                    actual_winner,
                    prediction_correct,
                    prediction_accuracy,
                    discord_message_id,
                    guid_coverage
                FROM match_predictions
            """

            where_clauses = []
            if status == "pending":
                where_clauses.append("actual_winner IS NULL")
            elif status == "completed":
                where_clauses.append("actual_winner IS NOT NULL")
            elif status == "correct":
                where_clauses.append("prediction_correct = true")
            elif status == "incorrect":
                where_clauses.append("prediction_correct = false")

            if where_clauses:
                base_query += " WHERE " + " AND ".join(where_clauses)

            query = base_query + " ORDER BY prediction_time DESC LIMIT $1"

            rows = await self.db.fetch_all(query, (limit,))

            if not rows:
                await ctx.send(f"📊 No predictions found with status: **{status}**")
                return

            # Build embed
            embed = discord.Embed(
                title="🔧 Admin: Prediction Management",
                description=f"Showing {len(rows)} prediction(s) - Filter: **{status}**",
                color=0xFF6B00,  # Orange for admin
                timestamp=datetime.now()
            )

            for row in rows:
                (pred_id, pred_time, session_date, format_str, team_a_prob, team_b_prob,
                 confidence, conf_score, insight, actual_winner, pred_correct,
                 pred_accuracy, discord_msg_id, guid_coverage) = row

                # Status indicator
                if actual_winner is None:
                    status_icon = "⏳ PENDING"
                elif pred_correct:
                    status_icon = f"✅ CORRECT ({pred_accuracy:.0%})"
                else:
                    status_icon = f"❌ INCORRECT ({pred_accuracy:.0%})"

                # Confidence color
                conf_emoji = {'high': '🟢', 'medium': '🟠', 'low': '🔴'}.get(confidence, '⚪')

                field_value = (
                    f"**Session:** {session_date} | **Format:** {format_str}\n"
                    f"**Prediction:** Team A {team_a_prob:.0%} vs Team B {team_b_prob:.0%}\n"
                    f"**Confidence:** {conf_emoji} {confidence.upper()} ({conf_score:.0%})\n"
                    f"**GUID Coverage:** {guid_coverage:.0%}\n"
                    f"**Status:** {status_icon}\n"
                    f"**Discord Msg:** {discord_msg_id or 'N/A'}\n"
                    f"💡 _{insight}_"
                )

                embed.add_field(
                    name=f"ID: {pred_id} | {pred_time.strftime('%Y-%m-%d %H:%M') if isinstance(pred_time, datetime) else pred_time[:16]}",
                    value=field_value,
                    inline=False
                )

            embed.set_footer(text=f"Use !update_prediction_outcome <id> <winner> to update results")

            await ctx.send(embed=embed)
            logger.info(f"🔧 {ctx.author} viewed admin predictions (status={status}, count={len(rows)})")

        except Exception as e:
            logger.error(f"❌ Error in !admin_predictions: {e}", exc_info=True)
            await ctx.send("❌ Failed to fetch predictions. Check logs for details.")

    @commands.command(name='update_prediction_outcome')
    async def update_prediction_outcome(self, ctx, prediction_id: int, winner: int, team_a_score: int = 0, team_b_score: int = 0):
        """
        Manually update a prediction outcome.

        Usage:
            !update_prediction_outcome <id> <winner> [team_a_score] [team_b_score]

        Winner: 1 = Team A, 2 = Team B, 0 = Draw/Cancelled

        Examples:
            !update_prediction_outcome 42 1 4 2     - Team A won 4-2
            !update_prediction_outcome 43 2 1 3     - Team B won 3-1
            !update_prediction_outcome 44 0         - Match cancelled/draw
        """
        try:
            if not self.prediction_engine:
                await ctx.send("❌ Prediction engine not available")
                return

            # Validate winner
            if winner not in [0, 1, 2]:
                await ctx.send("❌ Winner must be 0 (draw/cancelled), 1 (Team A), or 2 (Team B)")
                return

            # Check if prediction exists
            check_query = "SELECT id, actual_winner FROM match_predictions WHERE id = $1"
            pred_row = await self.db.fetch_one(check_query, (prediction_id,))

            if not pred_row:
                await ctx.send(f"❌ Prediction ID {prediction_id} not found")
                return

            existing_winner = pred_row[1]

            # Update the prediction
            await self.prediction_engine.update_prediction_outcome(
                prediction_id,
                winner,
                team_a_score,
                team_b_score
            )

            # Get updated prediction
            updated_query = """
                SELECT prediction_correct, prediction_accuracy
                FROM match_predictions
                WHERE id = $1
            """
            updated_row = await self.db.fetch_one(updated_query, (prediction_id,))
            pred_correct, pred_accuracy = updated_row

            # Build response embed
            embed = discord.Embed(
                title="✅ Prediction Outcome Updated",
                color=0x00FF00 if pred_correct else 0xFF0000,
                timestamp=datetime.now()
            )

            winner_text = {0: "Draw/Cancelled", 1: "Team A", 2: "Team B"}[winner]

            embed.add_field(name="Prediction ID", value=str(prediction_id), inline=True)
            embed.add_field(name="Winner", value=winner_text, inline=True)
            embed.add_field(name="Score", value=f"{team_a_score} - {team_b_score}", inline=True)

            embed.add_field(name="Prediction Status", value="✅ CORRECT" if pred_correct else "❌ INCORRECT", inline=True)
            embed.add_field(name="Accuracy Score", value=f"{pred_accuracy:.2%}", inline=True)
            embed.add_field(name="Previous Winner", value=winner_text if existing_winner else "None (was pending)", inline=True)

            embed.set_footer(text=f"Updated by {ctx.author.display_name}")

            await ctx.send(embed=embed)
            logger.info(f"🔧 {ctx.author} updated prediction {prediction_id}: winner={winner}, score={team_a_score}-{team_b_score}")

        except Exception as e:
            logger.error(f"❌ Error in !update_prediction_outcome: {e}", exc_info=True)
            await ctx.send(f"❌ Failed to update prediction: {str(e)}")

    @commands.command(name='recalculate_predictions')
    async def recalculate_predictions(self, ctx):
        """
        Recalculate accuracy for all completed predictions.

        This is useful if the accuracy calculation algorithm changes.

        Usage:
            !recalculate_predictions
        """
        try:
            if not self.prediction_engine:
                await ctx.send("❌ Prediction engine not available")
                return

            # Get all completed predictions
            query = """
                SELECT id, actual_winner, team_a_actual_score, team_b_actual_score
                FROM match_predictions
                WHERE actual_winner IS NOT NULL
            """

            rows = await self.db.fetch_all(query, ())

            if not rows:
                await ctx.send("📊 No completed predictions to recalculate")
                return

            # Send initial status
            status_msg = await ctx.send(f"🔄 Recalculating {len(rows)} predictions...")

            # Recalculate each one
            recalculated = 0
            errors = 0

            for pred_id, winner, team_a_score, team_b_score in rows:
                try:
                    await self.prediction_engine.update_prediction_outcome(
                        pred_id,
                        winner,
                        team_a_score or 0,
                        team_b_score or 0
                    )
                    recalculated += 1
                except Exception as e:
                    logger.error(f"Failed to recalculate prediction {pred_id}: {e}")
                    errors += 1

            # Update status message
            embed = discord.Embed(
                title="✅ Recalculation Complete",
                color=0x00FF00,
                timestamp=datetime.now()
            )

            embed.add_field(name="Total Predictions", value=str(len(rows)), inline=True)
            embed.add_field(name="Recalculated", value=str(recalculated), inline=True)
            embed.add_field(name="Errors", value=str(errors), inline=True)

            embed.set_footer(text=f"Requested by {ctx.author.display_name}")

            await status_msg.edit(content=None, embed=embed)
            logger.info(f"🔧 {ctx.author} recalculated {recalculated} predictions ({errors} errors)")

        except Exception as e:
            logger.error(f"❌ Error in !recalculate_predictions: {e}", exc_info=True)
            await ctx.send(f"❌ Failed to recalculate predictions: {str(e)}")

    @commands.command(name='prediction_performance')
    async def prediction_performance(self, ctx):
        """
        View system performance metrics for predictions.

        Shows database statistics, response times, and system health.

        Usage:
            !prediction_performance
        """
        try:
            # Database statistics
            stats_query = """
                SELECT
                    COUNT(*) as total_predictions,
                    COUNT(CASE WHEN actual_winner IS NOT NULL THEN 1 END) as completed,
                    COUNT(CASE WHEN discord_message_id IS NOT NULL THEN 1 END) as posted,
                    AVG(guid_coverage) as avg_coverage,
                    MIN(prediction_time) as first_prediction,
                    MAX(prediction_time) as latest_prediction
                FROM match_predictions
            """

            stats_row = await self.db.fetch_one(stats_query, ())

            (total, completed, posted, avg_coverage,
             first_pred, latest_pred) = stats_row

            # Calculate rates
            completion_rate = (completed / total * 100) if total > 0 else 0
            posting_rate = (posted / total * 100) if total > 0 else 0
            avg_coverage = avg_coverage or 0.0

            # Get table sizes
            size_query = """
                SELECT
                    pg_size_pretty(pg_total_relation_size('match_predictions')) as predictions_size,
                    pg_size_pretty(pg_total_relation_size('session_results')) as results_size,
                    pg_size_pretty(pg_total_relation_size('map_performance')) as map_perf_size
            """

            try:
                size_row = await self.db.fetch_one(size_query, ())
                pred_size, results_size, map_size = size_row
            except:
                pred_size = results_size = map_size = "N/A"

            # Build embed
            embed = discord.Embed(
                title="⚡ Prediction System Performance",
                description="System health and metrics",
                color=0x3498DB,
                timestamp=datetime.now()
            )

            embed.add_field(
                name="📊 Database Statistics",
                value=(
                    f"**Total Predictions:** {total}\n"
                    f"**Completed Matches:** {completed} ({completion_rate:.1f}%)\n"
                    f"**Posted to Discord:** {posted} ({posting_rate:.1f}%)\n"
                    f"**Avg GUID Coverage:** {avg_coverage:.1%}"
                ),
                inline=False
            )

            embed.add_field(
                name="📅 Timeline",
                value=(
                    f"**First Prediction:** {first_pred.strftime('%Y-%m-%d %H:%M') if first_pred else 'N/A'}\n"
                    f"**Latest Prediction:** {latest_pred.strftime('%Y-%m-%d %H:%M') if latest_pred else 'N/A'}"
                ),
                inline=False
            )

            embed.add_field(
                name="💾 Storage Usage",
                value=(
                    f"**match_predictions:** {pred_size}\n"
                    f"**session_results:** {results_size}\n"
                    f"**map_performance:** {map_size}"
                ),
                inline=False
            )

            # Feature flags status
            feature_status = []
            if self.config.enable_team_split_detection:
                feature_status.append("✅ Team Split Detection")
            if self.config.enable_match_predictions:
                feature_status.append("✅ Match Predictions")
            if self.config.enable_prediction_logging:
                feature_status.append("✅ Prediction Logging")

            if feature_status:
                embed.add_field(
                    name="🚀 Active Features",
                    value="\n".join(feature_status),
                    inline=False
                )

            # Configuration
            embed.add_field(
                name="⚙️ Configuration",
                value=(
                    f"**Cooldown:** {self.config.prediction_cooldown_minutes}min\n"
                    f"**Min Players:** {self.config.min_players_for_prediction}\n"
                    f"**Min GUID Coverage:** {self.config.min_guid_coverage:.0%}"
                ),
                inline=False
            )

            embed.set_footer(text="Competitive Analytics System")

            await ctx.send(embed=embed)
            logger.info(f"🔧 {ctx.author} viewed prediction performance metrics")

        except Exception as e:
            logger.error(f"❌ Error in !prediction_performance: {e}", exc_info=True)
            await ctx.send(f"❌ Failed to fetch performance metrics: {str(e)}")

    @commands.command(name='admin_prediction_help')
    async def admin_prediction_help(self, ctx):
        """Show help for admin prediction commands."""
        embed = discord.Embed(
            title="🔧 Admin Prediction Commands",
            description="Administrative tools for managing predictions",
            color=0xFF6B00
        )

        embed.add_field(
            name="!admin_predictions [status] [limit]",
            value="View all predictions with filtering (pending/completed/correct/incorrect)",
            inline=False
        )

        embed.add_field(
            name="!update_prediction_outcome <id> <winner> [score_a] [score_b]",
            value="Manually update prediction result (winner: 0/1/2)",
            inline=False
        )

        embed.add_field(
            name="!recalculate_predictions",
            value="Recalculate accuracy for all completed predictions",
            inline=False
        )

        embed.add_field(
            name="!prediction_performance",
            value="View system performance metrics and database statistics",
            inline=False
        )

        embed.set_footer(text="Admin commands only available in admin channels")

        await ctx.send(embed=embed)


async def setup(bot):
    """Load the Admin Predictions cog."""
    await bot.add_cog(AdminPredictionsCog(bot))
