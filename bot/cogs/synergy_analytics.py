"""
FIVEEYES Synergy Analytics Cog
Discord bot integration with safe error handling

This cog is ISOLATED - errors here won't crash the main bot
"""

import discord
from discord.ext import commands, tasks
import sys
import os
import logging
from typing import Optional, List
from datetime import datetime
import asyncio
# import aiosqlite  # Removed - using database adapter

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from bot.core.checks import is_public_channel, is_admin_channel
from bot.core.utils import sanitize_error_message
from analytics.synergy_detector import SynergyDetector, SynergyMetrics
from analytics.config import config, is_enabled, is_command_enabled
from bot.services.player_formatter import PlayerFormatter

logger = logging.getLogger(__name__)

# Prediction engine for team outcome predictions
try:
    from bot.services.prediction_engine import PredictionEngine
    PREDICTION_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ PredictionEngine not available for SynergyAnalytics")
    PREDICTION_AVAILABLE = False


class SynergyAnalytics(commands.Cog):
    """
    Player chemistry and team synergy analysis

    Commands:
    - !synergy @Player1 @Player2 - Show duo chemistry
    - !best_duos [limit] - Show top player pairs
    - !team_builder @P1 @P2... - Suggest balanced teams
    - !player_impact [@Player] - Show best/worst teammates
    """

    def __init__(self, bot):
        self.bot = bot
        self.db_path = 'etlegacy_production.db'  # Database path
        self.detector = SynergyDetector(self.db_path)
        self.cache = {}  # Simple in-memory cache
        self.player_formatter = PlayerFormatter(bot.db_adapter)
        
        # Initialize prediction engine if available
        if PREDICTION_AVAILABLE:
            self.prediction_engine = PredictionEngine(bot.db_adapter)
            logger.info("✅ PredictionEngine enabled for SynergyAnalytics")
        else:
            self.prediction_engine = None
        
        # Voting system for team suggestions
        # Format: {message_id: {'options': [...], 'votes': {user_id: option}, 
        #                       'channel_id': id, 'expires': timestamp}}
        self.active_suggestions = {}
        self.VOTE_EMOJIS = ['1️⃣', '2️⃣', '3️⃣']
        self.CONFIRM_EMOJI = '✅'

        # Start background tasks if enabled
        if config.get('synergy_analytics.auto_recalculate'):
            self.recalculate_synergies_task.start()
    
    def cog_unload(self):
        """Cleanup when cog is unloaded"""
        if self.recalculate_synergies_task.is_running():
            self.recalculate_synergies_task.cancel()
    
    async def cog_check(self, ctx):
        """Global check - is analytics enabled?"""
        if not is_enabled():
            await ctx.send(
                "🔒 Synergy analytics is currently disabled.\n"
                "Contact an admin to enable this feature."
            )
            return False
        return True
    
    async def cog_command_error(self, ctx, error):
        """Handle errors in this cog without crashing bot"""
        logger.error(f"Error in SynergyAnalytics: {error}", exc_info=True)
        
        if config.get('error_handling.fail_silently'):
            await ctx.send(
                "⚠️ An error occurred while processing synergy data.\n"
                "The bot is still running - this feature is temporarily unavailable."
            )
        else:
            raise error
    
    # =========================================================================
    # VOTING SYSTEM FOR TEAM SUGGESTIONS
    # =========================================================================
    
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """Handle votes on team suggestion messages"""
        # Ignore bot reactions
        if payload.user_id == self.bot.user.id:
            return
        
        # Check if this is an active suggestion
        if payload.message_id not in self.active_suggestions:
            return
        
        suggestion = self.active_suggestions[payload.message_id]
        emoji = str(payload.emoji)
        
        # Handle voting (1️⃣, 2️⃣, 3️⃣)
        if emoji in self.VOTE_EMOJIS:
            option_num = self.VOTE_EMOJIS.index(emoji)
            if option_num < len(suggestion['options']):
                # Record vote (one vote per user, can change)
                suggestion['votes'][payload.user_id] = option_num
                logger.debug(
                    f"Vote recorded: User {payload.user_id} -> Option {option_num + 1}"
                )
        
        # Handle confirm (✅) - show results
        elif emoji == self.CONFIRM_EMOJI:
            await self._show_vote_results(payload)
    
    async def _show_vote_results(self, payload):
        """Display final vote tally and winning team split"""
        if payload.message_id not in self.active_suggestions:
            return
        
        suggestion = self.active_suggestions[payload.message_id]
        votes = suggestion['votes']
        options = suggestion['options']
        
        # Count votes per option
        vote_counts = [0] * len(options)
        for user_id, option in votes.items():
            if option < len(vote_counts):
                vote_counts[option] += 1
        
        # Find winner (highest votes, tie = first option wins)
        max_votes = max(vote_counts) if vote_counts else 0
        winner_idx = vote_counts.index(max_votes) if max_votes > 0 else 0
        winner = options[winner_idx] if options else None
        
        # Build results embed
        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            return
        
        embed = discord.Embed(
            title="🏆 Team Suggestion Results",
            description="Voting complete! Here are the results:",
            color=0xFFD700  # Gold
        )
        
        # Show vote breakdown
        vote_summary = []
        for i, count in enumerate(vote_counts):
            emoji = self.VOTE_EMOJIS[i] if i < len(self.VOTE_EMOJIS) else f"{i+1}."
            winner_mark = " 🏆" if i == winner_idx else ""
            vote_summary.append(f"{emoji} Option {i+1}: **{count}** votes{winner_mark}")
        
        embed.add_field(
            name="📊 Vote Breakdown",
            value="\n".join(vote_summary) if vote_summary else "No votes",
            inline=False
        )
        
        # Show winning team
        if winner:
            team_a_names = winner.get('team_a_names', [])
            team_b_names = winner.get('team_b_names', [])
            
            embed.add_field(
                name="🔵 Winning Team 1",
                value="\n".join(f"• {name}" for name in team_a_names) or "Empty",
                inline=True
            )
            embed.add_field(
                name="🔴 Winning Team 2",
                value="\n".join(f"• {name}" for name in team_b_names) or "Empty",
                inline=True
            )
            
            # Show prediction for winner
            pred = winner.get('prediction', {})
            prob_a = pred.get('team_a_win_probability', 0.5)
            prob_b = pred.get('team_b_win_probability', 0.5)
            embed.add_field(
                name="🎯 Match Prediction",
                value=f"Team 1: **{prob_a:.0%}** vs Team 2: **{prob_b:.0%}**",
                inline=False
            )
        
        total_votes = sum(vote_counts)
        embed.set_footer(text=f"Total votes: {total_votes}")
        
        await channel.send(embed=embed)
        
        # Clean up this suggestion
        del self.active_suggestions[payload.message_id]
        logger.info(f"Team suggestion {payload.message_id} resolved with {total_votes} votes")

    # =========================================================================
    # COMMAND: !synergy
    # =========================================================================
    
    @is_public_channel()
    @commands.command(name='synergy', aliases=['chemistry', 'duo'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def synergy_command(
        self,
        ctx,
        player1: Optional[str] = None,
        player2: Optional[str] = None
    ):
        """
        Show synergy analysis between two players
        
        Usage:
            !synergy @Player1 @Player2
            !synergy PlayerName1 PlayerName2
        """
        if not is_command_enabled('synergy'):
            await ctx.send("🔒 This command is currently disabled.")
            return
        
        try:
            # Parse player mentions or names
            players = await self._parse_players(ctx, player1, player2)
            
            if not players or len(players) != 2:
                await ctx.send(
                    "❌ Please mention or name exactly 2 players.\n"
                    "**Usage:** `!synergy @Player1 @Player2`"
                )
                return
            
            player_a_guid, player_a_name = players[0]
            player_b_guid, player_b_name = players[1]
            
            # Calculate or fetch from cache
            cache_key = f"{player_a_guid}_{player_b_guid}"
            
            if cache_key in self.cache:
                synergy = self.cache[cache_key]
            else:
                # Show typing indicator
                async with ctx.typing():
                    synergy = await self.detector.calculate_synergy(
                        player_a_guid,
                        player_b_guid
                    )
                
                if synergy and config.get('synergy_analytics.cache_results'):
                    self.cache[cache_key] = synergy
            
            if not synergy:
                await ctx.send(
                    f"📊 **Insufficient data for {player_a_name} + {player_b_name}**\n\n"
                    f"These players need at least {config.get('synergy_analytics.min_games_threshold')} "
                    "games together on the same team to calculate synergy."
                )
                return
            
            # Create beautiful embed
            embed = await self._create_synergy_embed(synergy)
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in synergy_command: {e}", exc_info=True)
            await ctx.send(
                "⚠️ Could not calculate synergy. Please try again later."
            )
    
    # =========================================================================
    # COMMAND: !best_duos
    # =========================================================================
    
    @is_public_channel()
    @commands.command(name='best_duos', aliases=['top_duos', 'best_pairs'])
    @commands.cooldown(1, 10, commands.BucketType.channel)
    async def best_duos_command(self, ctx, limit: int = 10):
        """
        Show top player combinations by synergy score
        
        Usage:
            !best_duos          # Top 10
            !best_duos 20       # Top 20
        """
        if not is_command_enabled('best_duos'):
            await ctx.send("🔒 This command is currently disabled.")
            return
        
        try:
            # Validate limit
            if limit < 1 or limit > 50:
                await ctx.send("❌ Limit must be between 1 and 50")
                return
            
            async with ctx.typing():
                duos = await self.detector.get_best_duos(limit)
            
            if not duos:
                await ctx.send(
                    "📊 No synergy data available yet.\n"
                    "Play some games and synergies will be calculated!"
                )
                return
            
            # Format player names with badges (batch processing for efficiency)
            player_tuples = []
            for duo in duos:
                player_tuples.append((duo.player_a_guid, duo.player_a_name))
                player_tuples.append((duo.player_b_guid, duo.player_b_name))

            # Remove duplicates while preserving order
            seen = set()
            unique_players = []
            for guid, name in player_tuples:
                if guid not in seen:
                    seen.add(guid)
                    unique_players.append((guid, name))

            try:
                formatted_names = await self.player_formatter.format_players_batch(
                    unique_players, include_badges=True
                )
            except Exception as e:
                print(f"Error formatting player names: {e}")
                formatted_names = {guid: name for guid, name in unique_players}

            # Create embed
            embed = discord.Embed(
                title=f"🏆 Top {len(duos)} Player Duos",
                description="Best performing player combinations • Achievement badges shown",
                color=0xFFD700,  # Gold
                timestamp=datetime.now()
            )

            for idx, duo in enumerate(duos, 1):
                # Determine rating emoji
                if duo.synergy_score > 0.15:
                    rating = "🔥 Excellent"
                elif duo.synergy_score > 0.08:
                    rating = "✅ Good"
                elif duo.synergy_score > 0.03:
                    rating = "📊 Positive"
                else:
                    rating = "📉 Neutral"

                # Get formatted names with badges
                player_a = formatted_names.get(duo.player_a_guid, duo.player_a_name)
                player_b = formatted_names.get(duo.player_b_guid, duo.player_b_name)

                # Medal emojis for top 3
                if idx == 1:
                    medal = "🥇"
                elif idx == 2:
                    medal = "🥈"
                elif idx == 3:
                    medal = "🥉"
                else:
                    medal = f"`#{idx}`"

                embed.add_field(
                    name=f"{medal} {player_a} **+** {player_b}",
                    value=(
                        f"**{rating}**\n"
                        f"📊 Synergy: `{duo.synergy_score:.3f}` • "
                        f"🎮 Games: `{duo.games_same_team}` • "
                        f"📈 Boost: `{duo.performance_boost_avg:+.1f}%`\n"
                        f"🎯 Confidence: `{duo.confidence:.0%}`"
                    ),
                    inline=False
                )

            embed.set_footer(text="💡 Higher synergy = better performance together • Based on actual game data")
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in best_duos_command: {e}", exc_info=True)
            await ctx.send(
                "⚠️ Could not fetch best duos. Please try again later."
            )
    
    # =========================================================================
    # COMMAND: !team_builder
    # =========================================================================
    
    @commands.command(name='team_builder', aliases=['tb', 'build_teams'])
    @commands.cooldown(1, 15, commands.BucketType.channel)
    async def team_builder_command(self, ctx, *players):
        """
        Suggest balanced teams based on synergies
        
        Usage:
            !team_builder @P1 @P2 @P3 @P4 @P5 @P6
        """
        if not is_command_enabled('team_builder'):
            await ctx.send("🔒 This command is currently disabled.")
            return
        
        try:
            # Parse players (mentions or names)
            player_list = []
            
            # Get mentions
            for member in ctx.message.mentions:
                # Find their GUID from database
                guid = await self._get_player_guid(member.display_name)
                if guid:
                    player_list.append((guid, member.display_name))
            
            # Get names from text
            for name in players:
                if not name.startswith('<@'):  # Skip mentions
                    guid = await self._get_player_guid(name)
                    if guid and (guid, name) not in player_list:
                        player_list.append((guid, name))
            
            if len(player_list) < 4:
                await ctx.send(
                    "❌ Need at least 4 players for team balancing.\n"
                    "**Usage:** `!team_builder @P1 @P2 @P3 @P4 @P5 @P6`"
                )
                return
            
            max_players = config.get('synergy_analytics.max_team_size', 6) * 2
            if len(player_list) > max_players:
                await ctx.send(
                    f"❌ Maximum {max_players} players allowed."
                )
                return
            
            async with ctx.typing():
                # Optimize team split based on synergies
                result = await self._optimize_teams(player_list)
            
            if not result:
                await ctx.send("⚠️ Could not find optimal team split.")
                return
            
            # Format player names with badges
            all_players = result['team_a'] + result['team_b']
            try:
                formatted_names = await self.player_formatter.format_players_batch(
                    all_players, include_badges=True
                )
            except Exception as e:
                print(f"Error formatting player names: {e}")
                formatted_names = {guid: name for guid, name in all_players}

            # Create embed
            embed = discord.Embed(
                title="🎮 Optimized Team Split",
                description="Balanced teams based on synergy analysis • Achievement badges shown",
                color=0xFFD700,  # Gold
                timestamp=datetime.now()
            )

            # Team A with badges
            team_a_players = "\n".join([
                f"• {formatted_names.get(guid, name)}"
                for guid, name in result['team_a']
            ])
            embed.add_field(
                name=f"🔵 Team A • Synergy: `{result['team_a_synergy']:.3f}`",
                value=team_a_players or "No players",
                inline=True
            )

            # Team B with badges
            team_b_players = "\n".join([
                f"• {formatted_names.get(guid, name)}"
                for guid, name in result['team_b']
            ])
            embed.add_field(
                name=f"🔴 Team B • Synergy: `{result['team_b_synergy']:.3f}`",
                value=team_b_players or "No players",
                inline=True
            )

            # Balance analysis
            balance = result['balance_rating']
            if balance > 0.9:
                balance_text = "🟢 **Excellent balance!**"
                balance_emoji = "✨"
            elif balance > 0.7:
                balance_text = "🟡 **Good balance**"
                balance_emoji = "👍"
            else:
                balance_text = "🟠 **Fair balance**"
                balance_emoji = "📊"

            embed.add_field(
                name="⚖️ Balance Rating",
                value=f"{balance_emoji} {balance_text}\n```\n{balance:.1%}\n```",
                inline=False
            )

            embed.set_footer(
                text=f"✅ Analyzed {result['combinations_checked']} possible splits • Requested by {ctx.author.name}"
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in team_builder_command: {e}", exc_info=True)
            await ctx.send(
                "⚠️ Could not build teams. Please try again later."
            )

    # =========================================================================
    # COMMAND: !suggest_teams
    # =========================================================================
    
    @commands.command(name='suggest_teams', aliases=['suggest', 'balance', 'st'])
    @commands.cooldown(1, 30, commands.BucketType.channel)
    async def suggest_teams_command(self, ctx):
        """
        Auto-suggest balanced teams based on players in voice channels.
        Shows 3 options with predictions. Vote with 1️⃣2️⃣3️⃣, confirm with ✅.
        
        Usage:
            !suggest_teams
        
        Detects players in monitored voice channels and suggests balanced teams.
        """
        if not is_command_enabled('team_builder'):
            await ctx.send("🔒 Team suggestions are currently disabled.")
            return
        
        try:
            # Get monitored voice channels
            monitored_channels = ['Fireteam Triglav', 'Fireteam Barje']
            
            # Collect all members in monitored voice channels
            voice_members = []
            channel_info = []
            
            for guild in self.bot.guilds:
                for vc in guild.voice_channels:
                    if vc.name in monitored_channels:
                        for member in vc.members:
                            if not member.bot:
                                voice_members.append(member)
                        if vc.members:
                            non_bot = len([m for m in vc.members if not m.bot])
                            channel_info.append(f"{vc.name}: {non_bot}")
            
            if len(voice_members) < 4:
                await ctx.send(
                    f"❌ Need at least 4 players in voice for team balancing.\n"
                    f"**Current:** {', '.join(channel_info) or 'No players'}\n"
                    f"**Tip:** Join: {', '.join(monitored_channels)}"
                )
                return
            
            async with ctx.typing():
                # Resolve Discord IDs to GUIDs using player_links table
                player_list = []
                unlinked_players = []
                
                # Batch lookup all Discord IDs at once
                discord_ids = [member.id for member in voice_members]
                
                # Query player_links for all Discord IDs
                placeholders = ', '.join(['?' for _ in discord_ids])
                rows = await self.bot.db_adapter.fetch_all(f"""
                    SELECT discord_id, player_guid, player_name
                    FROM player_links
                    WHERE discord_id IN ({placeholders})
                """, tuple(discord_ids))
                
                # Build mapping from results
                linked_ids = set()
                for discord_id, guid, player_name in rows:
                    linked_ids.add(int(discord_id))
                    player_list.append((guid, player_name))
                
                # Find unlinked players
                for member in voice_members:
                    if member.id not in linked_ids:
                        unlinked_players.append(member.display_name)
                
                if len(player_list) < 4:
                    await ctx.send(
                        f"❌ Not enough linked players for team balancing.\n"
                        f"**Linked:** {len(player_list)} • "
                        f"**Unlinked:** {len(unlinked_players)}\n"
                        f"**Unlinked:** {', '.join(unlinked_players)}\n"
                        f"💡 Use `!link <player_name>` to link accounts."
                    )
                    return
                
                # Get top 3 diverse team splits
                options = await self._optimize_teams_top_n(player_list, n=3)
                
                if not options:
                    await ctx.send("⚠️ Could not find team splits.")
                    return
                
                # Add predictions to each option
                options = await self._add_predictions_to_options(options)
                
                # Format player names with badges
                all_players = []
                for opt in options:
                    all_players.extend(opt['team_a'])
                    all_players.extend(opt['team_b'])
                
                try:
                    formatted = await self.player_formatter.format_players_batch(
                        all_players, include_badges=True
                    )
                except Exception as e:
                    logger.warning(f"Error formatting names: {e}")
                    formatted = {guid: name for guid, name in all_players}
            
            # Create main embed with all 3 options
            embed = discord.Embed(
                title="🎮 Team Suggestions - Vote for your pick!",
                description=(
                    f"**{len(voice_members)}** players in voice • "
                    f"**{len(player_list)}** linked\n"
                    f"Vote with 1️⃣2️⃣3️⃣ then ✅ to confirm"
                ),
                color=0x00D166,
                timestamp=datetime.now()
            )
            
            # Add each option
            for i, opt in enumerate(options):
                emoji = self.VOTE_EMOJIS[i] if i < len(self.VOTE_EMOJIS) else f"{i+1}."
                
                # Team names
                team_a_str = ", ".join([
                    formatted.get(guid, name)[:15] 
                    for guid, name in opt['team_a']
                ])
                team_b_str = ", ".join([
                    formatted.get(guid, name)[:15] 
                    for guid, name in opt['team_b']
                ])
                
                # Prediction
                pred = opt.get('prediction', {})
                prob_a = pred.get('team_a_win_probability', 0.5)
                prob_b = pred.get('team_b_win_probability', 0.5)
                confidence = pred.get('confidence', 'unknown')
                
                # Balance info
                balance = opt.get('balance_rating', 0)
                if balance > 0.9:
                    balance_emoji = "🟢"
                elif balance > 0.7:
                    balance_emoji = "🟡"
                else:
                    balance_emoji = "🟠"
                
                option_text = (
                    f"🔵 **Team 1:** {team_a_str}\n"
                    f"🔴 **Team 2:** {team_b_str}\n"
                    f"📊 **Prediction:** {prob_a:.0%} vs {prob_b:.0%} "
                    f"({confidence})\n"
                    f"{balance_emoji} **Balance:** {balance:.0%}"
                )
                
                embed.add_field(
                    name=f"{emoji} Option {i + 1}",
                    value=option_text,
                    inline=False
                )
            
            # Show unlinked players warning
            if unlinked_players:
                embed.add_field(
                    name="⚠️ Unlinked (not included)",
                    value=", ".join(unlinked_players[:5]) + (
                        f"... +{len(unlinked_players)-5}" 
                        if len(unlinked_players) > 5 else ""
                    ),
                    inline=False
                )
            
            embed.set_footer(
                text=f"Analyzed {options[0].get('combinations_checked', 0)} combinations"
            )
            
            # Send and add reactions
            message = await ctx.send(embed=embed)
            
            # Add voting reactions
            for i in range(min(len(options), len(self.VOTE_EMOJIS))):
                await message.add_reaction(self.VOTE_EMOJIS[i])
            await message.add_reaction(self.CONFIRM_EMOJI)
            
            # Store for vote tracking
            self.active_suggestions[message.id] = {
                'options': options,
                'votes': {},
                'channel_id': ctx.channel.id,
                'created_at': datetime.now(),
                'author_id': ctx.author.id
            }
            
            logger.info(
                f"Team suggestion created: {message.id} with {len(options)} options"
            )
            
        except Exception as e:
            logger.error(f"Error in suggest_teams_command: {e}", exc_info=True)
            await ctx.send(
                "⚠️ Could not generate team suggestions. Please try again later."
            )
    
    # =========================================================================
    # COMMAND: !player_impact
    # =========================================================================
    
    @is_public_channel()
    @commands.command(name='player_impact', aliases=['teammates', 'partners'])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def player_impact_command(self, ctx, player: Optional[str] = None):
        """
        Show which teammates a player performs best/worst with
        
        Usage:
            !player_impact          # Your impact
            !player_impact @Player  # Someone's impact
        """
        if not is_command_enabled('player_impact'):
            await ctx.send("🔒 This command is currently disabled.")
            return
        
        try:
            # Get player GUID
            if player:
                # Try mention first
                if ctx.message.mentions:
                    player_name = ctx.message.mentions[0].display_name
                    player_guid = await self._get_player_guid(player_name)
                else:
                    player_name = player
                    player_guid = await self._get_player_guid(player)
            else:
                # Use command author
                player_name = ctx.author.display_name
                player_guid = await self._get_player_guid(player_name)
            
            if not player_guid:
                await ctx.send(f"❌ Could not find player: {player_name}")
                return
            
            async with ctx.typing():
                # Get all synergies for this player
                partners = await self._get_player_partners(player_guid)
            
            if not partners:
                await ctx.send(
                    f"📊 No synergy data available for **{player_name}**\n"
                    "Need at least 10 games with teammates to show impact."
                )
                return
            
            # Sort by synergy score
            partners.sort(key=lambda x: x['synergy_score'], reverse=True)

            # Get best and worst
            best_partners = partners[:5]
            worst_partners = partners[-5:] if len(partners) > 5 else []

            # Format all partner names with badges
            all_partner_guids = [(p['partner_guid'], p['partner_name']) for p in partners]
            try:
                formatted_partner_names = await self.player_formatter.format_players_batch(
                    all_partner_guids, include_badges=True
                )
            except Exception as e:
                print(f"Error formatting partner names: {e}")
                formatted_partner_names = {guid: name for guid, name in all_partner_guids}

            # Format the main player's name with badges
            try:
                player_formatted = await self.player_formatter.format_player(
                    player_guid, player_name, include_badges=True
                )
            except Exception as e:
                print(f"Error formatting player name: {e}")
                player_formatted = player_name

            # Create embed
            embed = discord.Embed(
                title="🤝 Player Impact Analysis",
                description=f"{player_formatted}\n\nTeammate chemistry analysis • `{len(partners)}` partners analyzed",
                color=0x9B59B6,  # Purple
                timestamp=datetime.now()
            )

            # Best teammates with badges
            if best_partners:
                best_text = ""
                for idx, partner in enumerate(best_partners, 1):
                    score = partner['synergy_score']
                    games = partner['games']
                    guid = partner['partner_guid']
                    formatted_name = formatted_partner_names.get(guid, partner['partner_name'])

                    # Emoji based on synergy
                    if score > 0.15:
                        emoji = "🔥"
                    elif score > 0.08:
                        emoji = "✅"
                    else:
                        emoji = "📊"

                    best_text += f"{idx}. {emoji} {formatted_name}\n"
                    best_text += f"   Synergy: `{score:.3f}` • Games: `{games}`\n"

                embed.add_field(
                    name="🏆 Best Teammates",
                    value=best_text.strip(),
                    inline=False
                )

            # Worst teammates (only if there are enough)
            if worst_partners and len(partners) > 5:
                worst_text = ""
                for idx, partner in enumerate(worst_partners, 1):
                    score = partner['synergy_score']
                    games = partner['games']
                    guid = partner['partner_guid']
                    formatted_name = formatted_partner_names.get(guid, partner['partner_name'])

                    worst_text += f"{idx}. {formatted_name}\n"
                    worst_text += f"   Synergy: `{score:.3f}` • Games: `{games}`\n"

                embed.add_field(
                    name="📉 Challenging Partnerships",
                    value=worst_text.strip(),
                    inline=False
                )

            # Average synergy
            avg_synergy = sum(p['synergy_score'] for p in partners) / len(partners)
            embed.add_field(
                name="📊 Average Synergy",
                value=f"```\n{avg_synergy:.3f}\n```",
                inline=True
            )

            embed.add_field(
                name="👥 Unique Partners",
                value=f"```\n{len(partners)}\n```",
                inline=True
            )

            # Most games with
            most_games_partner = max(partners, key=lambda x: x['games'])
            most_games_name = formatted_partner_names.get(
                most_games_partner['partner_guid'],
                most_games_partner['partner_name']
            )
            embed.add_field(
                name="🎮 Most Games With",
                value=f"{most_games_name}\n`{most_games_partner['games']}` games",
                inline=True
            )

            embed.set_footer(
                text=f"💡 Based on games with 10+ matches together • Requested by {ctx.author.name}"
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in player_impact_command: {e}", exc_info=True)
            await ctx.send(
                "⚠️ Could not calculate player impact. Please try again later."
            )
    
    # =========================================================================
    # ADMIN COMMANDS
    # =========================================================================
    
    @is_admin_channel()
    @commands.command(name='fiveeyes_enable')
    @commands.has_permissions(administrator=True)
    async def enable_command(self, ctx):
        """Enable FIVEEYES synergy analytics (Admin only)"""
        config.enable()
        await ctx.send("✅ **FIVEEYES synergy analytics enabled!**")

    @is_admin_channel()
    @commands.command(name='fiveeyes_disable')
    @commands.has_permissions(administrator=True)
    async def disable_command(self, ctx):
        """Disable FIVEEYES synergy analytics (Admin only)"""
        config.disable()
        await ctx.send("⚠️ **FIVEEYES synergy analytics disabled.**")

    @is_admin_channel()
    @commands.command(name='recalculate_synergies')
    @commands.has_permissions(administrator=True)
    async def recalculate_command(self, ctx):
        """Manually trigger synergy recalculation (Admin only)"""
        await ctx.send("🔄 Starting synergy recalculation... This may take a few minutes.")
        
        try:
            count = await self.detector.calculate_all_synergies()
            self.cache.clear()  # Clear cache
            await ctx.send(f"✅ Recalculated {count} player synergies successfully!")
        except Exception as e:
            await ctx.send(
                f"❌ Error during recalculation: {sanitize_error_message(e)}")
    
    # =========================================================================
    # BACKGROUND TASKS
    # =========================================================================
    
    @tasks.loop(hours=24)
    async def recalculate_synergies_task(self):
        """Recalculate synergies once per day"""
        print("🔄 Starting daily synergy recalculation...")
        try:
            count = await self.detector.calculate_all_synergies()
            self.cache.clear()
            print(f"✅ Recalculated {count} synergies")
        except Exception as e:
            print(f"❌ Error in daily recalculation: {e}")
    
    @recalculate_synergies_task.before_loop
    async def before_recalculate(self):
        """Wait for bot to be ready"""
        await self.bot.wait_until_ready()
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    async def _parse_players(self, ctx, player1, player2):
        """Parse player mentions or names"""
        players = []
        
        # Check mentions first
        if len(ctx.message.mentions) >= 2:
            for member in ctx.message.mentions[:2]:
                guid = await self._get_player_guid(member.display_name)
                if guid:
                    players.append((guid, member.display_name))
        
        # Fall back to text names
        if len(players) < 2 and player1:
            guid = await self._get_player_guid(player1)
            if guid:
                players.append((guid, player1))
        
        if len(players) < 2 and player2:
            guid = await self._get_player_guid(player2)
            if guid:
                players.append((guid, player2))
        
        return players if len(players) == 2 else None
    
    async def _get_player_guid(self, player_name: str) -> Optional[str]:
        """Get player GUID from name"""
        try:
            row = await self.bot.db_adapter.fetch_one("""
                SELECT guid
                FROM player_aliases
                WHERE LOWER(alias) LIKE LOWER(?)
                ORDER BY last_seen DESC
                LIMIT 1
            """, (f"%{player_name}%",))
            
            return row[0] if row else None
        except Exception as e:
            print(f"Error getting player GUID: {e}")
            return None
    
    async def _optimize_teams(self, player_list: List[tuple]) -> dict:
        """
        Optimize team split based on synergies
        Tries all combinations and finds most balanced split
        """
        from itertools import combinations
        
        num_players = len(player_list)
        team_size = num_players // 2
        
        # For odd numbers, one team gets extra player
        if num_players % 2 == 1:
            team_size = (num_players + 1) // 2
        
        # Try all possible team combinations
        best_balance = 0
        best_split = None
        combinations_checked = 0
        
        for team_a_indices in combinations(range(num_players), team_size):
            team_b_indices = [i for i in range(num_players) if i not in team_a_indices]
            
            team_a = [player_list[i] for i in team_a_indices]
            team_b = [player_list[i] for i in team_b_indices]
            
            # Calculate team synergies
            team_a_synergy = await self._calculate_team_synergy(team_a)
            team_b_synergy = await self._calculate_team_synergy(team_b)
            
            # Balance = how similar the synergies are (1.0 = perfectly balanced)
            if team_a_synergy > 0 and team_b_synergy > 0:
                min_syn = min(team_a_synergy, team_b_synergy)
                max_syn = max(team_a_synergy, team_b_synergy)
                balance = min_syn / max_syn if max_syn > 0 else 0
            else:
                balance = 0.5
            
            combinations_checked += 1
            
            if balance > best_balance:
                best_balance = balance
                best_split = {
                    'team_a': team_a,
                    'team_b': team_b,
                    'team_a_synergy': team_a_synergy,
                    'team_b_synergy': team_b_synergy,
                    'balance_rating': balance
                }
        
        if best_split:
            best_split['combinations_checked'] = combinations_checked
            best_split['team_a_names'] = [name for _, name in best_split['team_a']]
            best_split['team_b_names'] = [name for _, name in best_split['team_b']]
        
        return best_split
    
    async def _optimize_teams_top_n(self, player_list: List[tuple], n: int = 3) -> List[dict]:
        """
        Generate top N diverse balanced team splits.
        Returns multiple options with different compositions.
        
        Args:
            player_list: List of (guid, player_name) tuples
            n: Number of options to return (default 3)
            
        Returns:
            List of split dictionaries sorted by balance rating
        """
        from itertools import combinations
        import heapq
        
        num_players = len(player_list)
        team_size = num_players // 2
        
        # For odd numbers, one team gets extra player
        if num_players % 2 == 1:
            team_size = (num_players + 1) // 2
        
        # Collect ALL splits with their scores
        all_splits = []
        combinations_checked = 0
        
        for team_a_indices in combinations(range(num_players), team_size):
            team_b_indices = tuple(i for i in range(num_players) if i not in team_a_indices)
            
            team_a = [player_list[i] for i in team_a_indices]
            team_b = [player_list[i] for i in team_b_indices]
            
            # Calculate team synergies
            team_a_synergy = await self._calculate_team_synergy(team_a)
            team_b_synergy = await self._calculate_team_synergy(team_b)
            
            # Balance = how similar the synergies are (1.0 = perfectly balanced)
            if team_a_synergy > 0 and team_b_synergy > 0:
                min_syn = min(team_a_synergy, team_b_synergy)
                max_syn = max(team_a_synergy, team_b_synergy)
                balance = min_syn / max_syn if max_syn > 0 else 0
            else:
                balance = 0.5
            
            combinations_checked += 1
            
            split = {
                'team_a': team_a,
                'team_b': team_b,
                'team_a_synergy': team_a_synergy,
                'team_b_synergy': team_b_synergy,
                'balance_rating': balance,
                'team_a_indices': frozenset(team_a_indices),
                'team_b_indices': frozenset(team_b_indices),
            }
            all_splits.append(split)
        
        if not all_splits:
            return []
        
        # Sort by balance (highest first)
        all_splits.sort(key=lambda x: x['balance_rating'], reverse=True)
        
        # Pick diverse options - ensure team compositions differ significantly
        selected = []
        selected_indices = []  # Track indices separately for diversity check
        used_compositions = set()
        
        for split in all_splits:
            # Create a canonical representation (smaller set first for uniqueness)
            comp_key = (split['team_a_indices'], split['team_b_indices'])
            reverse_key = (split['team_b_indices'], split['team_a_indices'])
            
            # Check if this is too similar to already selected options
            if comp_key in used_compositions or reverse_key in used_compositions:
                continue
            
            # Check diversity: at least 2 players must be different from previous selections
            is_diverse = True
            for prev_indices in selected_indices:
                overlap_a = len(split['team_a_indices'] & prev_indices)
                # If more than half are the same, it's not diverse enough
                if overlap_a > len(split['team_a_indices']) - 1:
                    is_diverse = False
                    break
            
            if is_diverse or len(selected) == 0:
                # Remove internal tracking keys before adding
                split_clean = {k: v for k, v in split.items() 
                              if k not in ('team_a_indices', 'team_b_indices')}
                split_clean['combinations_checked'] = combinations_checked
                split_clean['team_a_names'] = [name for _, name in split['team_a']]
                split_clean['team_b_names'] = [name for _, name in split['team_b']]
                split_clean['option_number'] = len(selected) + 1
                selected.append(split_clean)
                selected_indices.append(split['team_a_indices'])  # Track for diversity
                used_compositions.add(comp_key)
                used_compositions.add(reverse_key)
            
            if len(selected) >= n:
                break
        
        # If we couldn't find n diverse options, fill with remaining best
        if len(selected) < n:
            for split in all_splits:
                comp_key = (split['team_a_indices'], split['team_b_indices'])
                reverse_key = (split['team_b_indices'], split['team_a_indices'])
                if comp_key not in used_compositions and reverse_key not in used_compositions:
                    split_clean = {k: v for k, v in split.items() 
                                  if k not in ('team_a_indices', 'team_b_indices')}
                    split_clean['combinations_checked'] = combinations_checked
                    split_clean['team_a_names'] = [name for _, name in split['team_a']]
                    split_clean['team_b_names'] = [name for _, name in split['team_b']]
                    split_clean['option_number'] = len(selected) + 1
                    selected.append(split_clean)
                    used_compositions.add(comp_key)
                    if len(selected) >= n:
                        break
        
        return selected

    async def _add_predictions_to_options(
        self, options: List[dict]
    ) -> List[dict]:
        """
        Add match predictions to each team option.
        
        Args:
            options: List of team split options from _optimize_teams_top_n
            
        Returns:
            Options with 'prediction' field added to each
        """
        if not self.prediction_engine:
            # No prediction engine - add placeholder predictions
            for opt in options:
                opt['prediction'] = {
                    'team_a_win_probability': 0.50,
                    'team_b_win_probability': 0.50,
                    'confidence': 'unavailable',
                    'key_insight': 'Prediction engine not available'
                }
            return options
        
        for opt in options:
            try:
                team_a_guids = [guid for guid, _ in opt['team_a']]
                team_b_guids = [guid for guid, _ in opt['team_b']]
                
                prediction = await self.prediction_engine.predict_match(
                    team_a_guids, team_b_guids
                )
                opt['prediction'] = prediction
            except Exception as e:
                logger.warning(f"Prediction failed for option {opt.get('option_number')}: {e}")
                opt['prediction'] = {
                    'team_a_win_probability': 0.50,
                    'team_b_win_probability': 0.50,
                    'confidence': 'error',
                    'key_insight': 'Could not generate prediction'
                }
        
        return options

    async def _calculate_team_synergy(self, team: List[tuple]) -> float:
        """Calculate average synergy within a team"""
        if len(team) < 2:
            return 0.0
        
        synergies = []
        
        # Check all pairs within team
        for i in range(len(team)):
            for j in range(i + 1, len(team)):
                guid_a = team[i][0]
                guid_b = team[j][0]
                
                # Get synergy from database
                try:
                    # Try both orderings
                    row = await self.bot.db_adapter.fetch_one("""
                        SELECT synergy_score
                        FROM player_synergies
                        WHERE (player_a_guid = ? AND player_b_guid = ?)
                           OR (player_a_guid = ? AND player_b_guid = ?)
                    """, (guid_a, guid_b, guid_b, guid_a))
                    
                    if row:
                        synergies.append(row[0])
                except Exception as e:
                    print(f"Error getting synergy: {e}")
        
        # Return average synergy (or 0 if no synergies found)
        return sum(synergies) / len(synergies) if synergies else 0.0
    
    async def _get_player_partners(self, player_guid: str) -> List[dict]:
        """Get all partners for a player with their synergy scores"""
        partners = []
        
        try:
            # Get all synergies involving this player
            rows = await self.bot.db_adapter.fetch_all("""
                SELECT 
                    CASE 
                        WHEN player_a_guid = ? THEN player_b_guid
                        ELSE player_a_guid
                    END as partner_guid,
                    CASE
                        WHEN player_a_guid = ? THEN player_b_name
                        ELSE player_a_name
                    END as partner_name,
                    synergy_score,
                    games_same_team
                FROM player_synergies
                WHERE player_a_guid = ? OR player_b_guid = ?
                ORDER BY synergy_score DESC
            """, (player_guid, player_guid, player_guid, player_guid))
            
            for row in rows:
                partners.append({
                    'partner_guid': row[0],
                    'partner_name': row[1],
                    'synergy_score': row[2],
                    'games': row[3]
                })
        
        except Exception as e:
            print(f"Error getting partners: {e}")
        
        return partners
    
    async def _create_synergy_embed(self, synergy: SynergyMetrics) -> discord.Embed:
        """Create beautiful synergy embed with player badges"""
        # Determine rating
        if synergy.synergy_score > 0.15:
            rating = "🔥 Excellent"
            color = 0x57F287  # Green
        elif synergy.synergy_score > 0.08:
            rating = "✅ Good"
            color = 0x5865F2  # Blurple
        elif synergy.synergy_score > 0.03:
            rating = "📊 Positive"
            color = 0xFFD700  # Gold
        elif synergy.synergy_score > -0.03:
            rating = "📉 Neutral"
            color = 0x99AAB5  # Gray
        else:
            rating = "⚠️ Poor"
            color = 0xED4245  # Red

        # Format player names with badges
        try:
            player_a_formatted = await self.player_formatter.format_player(
                synergy.player_a_guid, synergy.player_a_name, include_badges=True
            )
            player_b_formatted = await self.player_formatter.format_player(
                synergy.player_b_guid, synergy.player_b_name, include_badges=True
            )
        except Exception as e:
            print(f"Error formatting player names: {e}")
            player_a_formatted = synergy.player_a_name
            player_b_formatted = synergy.player_b_name

        embed = discord.Embed(
            title="⚔️ Player Synergy Analysis",
            description=f"{player_a_formatted} **+** {player_b_formatted}\n\n**Overall Rating:** {rating}",
            color=color,
            timestamp=datetime.now()
        )

        # Stats with better formatting
        embed.add_field(
            name="📊 Games Together",
            value=f"```\n{synergy.games_same_team} games\n```",
            inline=True
        )

        embed.add_field(
            name="📈 Performance Boost",
            value=f"```\n{synergy.performance_boost_avg:+.1f}%\n```",
            inline=True
        )

        embed.add_field(
            name="💯 Synergy Score",
            value=f"```\n{synergy.synergy_score:.3f}\n```",
            inline=True
        )

        embed.add_field(
            name="🎯 Confidence Level",
            value=f"```\n{synergy.confidence:.0%}\n```",
            inline=True
        )

        # Analysis with better formatting
        if synergy.synergy_score > 0.08:
            analysis = "🎯 **These players perform significantly better together!**"
        elif synergy.synergy_score > 0.03:
            analysis = "👍 **These players work well together.**"
        elif synergy.synergy_score > -0.03:
            analysis = "📊 **No significant synergy detected yet.**"
        else:
            analysis = "⚠️ **These players may work better with different teammates.**"

        embed.add_field(name="═══ Analysis ═══", value=analysis, inline=False)

        embed.set_footer(text="💡 Based on historical performance data • Higher score = better chemistry")

        return embed


# Setup function for bot to load this cog
async def setup(bot):
    """Add SynergyAnalytics cog to bot"""
    await bot.add_cog(SynergyAnalytics(bot))
    print("✅ SynergyAnalytics cog loaded (disabled by default)")
