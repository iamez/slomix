"""
FIVEEYES Synergy Analytics Cog
Discord bot integration with safe error handling

This cog is ISOLATED - errors here won't crash the main bot
"""

import discord
from discord.ext import commands, tasks
import sys
import os
import traceback
from typing import Optional, List
from datetime import datetime
import asyncio
# import aiosqlite  # Removed - using database adapter

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from analytics.synergy_detector import SynergyDetector, SynergyMetrics
from analytics.config import config, is_enabled, is_command_enabled


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
        print(f"❌ Error in SynergyAnalytics: {error}")
        traceback.print_exc()
        
        if config.get('error_handling.fail_silently'):
            await ctx.send(
                "⚠️ An error occurred while processing synergy data.\n"
                "The bot is still running - this feature is temporarily unavailable."
            )
        else:
            raise error
    
    # =========================================================================
    # COMMAND: !synergy
    # =========================================================================
    
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
                    f"games together on the same team to calculate synergy."
                )
                return
            
            # Create beautiful embed
            embed = await self._create_synergy_embed(synergy)
            await ctx.send(embed=embed)
            
        except Exception as e:
            print(f"Error in synergy_command: {e}")
            traceback.print_exc()
            await ctx.send(
                "⚠️ Could not calculate synergy. Please try again later."
            )
    
    # =========================================================================
    # COMMAND: !best_duos
    # =========================================================================
    
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
            
            # Create embed
            embed = discord.Embed(
                title=f"🏆 Top {len(duos)} Player Duos",
                description="Best performing player combinations",
                color=discord.Color.gold(),
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
                
                embed.add_field(
                    name=f"{idx}. {duo.player_a_name} + {duo.player_b_name}",
                    value=(
                        f"{rating}\n"
                        f"**Synergy:** {duo.synergy_score:.3f} | "
                        f"**Games:** {duo.games_same_team} | "
                        f"**Perf Boost:** {duo.performance_boost_avg:+.1f}%\n"
                        f"**Confidence:** {duo.confidence:.0%}"
                    ),
                    inline=False
                )
            
            embed.set_footer(text="💡 Higher synergy = better performance together")
            await ctx.send(embed=embed)
            
        except Exception as e:
            print(f"Error in best_duos_command: {e}")
            traceback.print_exc()
            await ctx.send(
                "⚠️ Could not fetch best duos. Please try again later."
            )
    
    # =========================================================================
    # COMMAND: !team_builder
    # =========================================================================
    
    @commands.command(name='team_builder', aliases=['balance_teams', 'suggest_teams'])
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
            
            # Create embed
            embed = discord.Embed(
                title="🎮 Optimized Team Split",
                description="Balanced teams based on synergy analysis",
                color=discord.Color.gold(),
                timestamp=datetime.now()
            )
            
            # Team A
            team_a_players = "\n".join([f"• {name}" for name in result['team_a_names']])
            embed.add_field(
                name=f"🔵 Team A (Synergy: {result['team_a_synergy']:.3f})",
                value=team_a_players,
                inline=True
            )
            
            # Team B
            team_b_players = "\n".join([f"• {name}" for name in result['team_b_names']])
            embed.add_field(
                name=f"🔴 Team B (Synergy: {result['team_b_synergy']:.3f})",
                value=team_b_players,
                inline=True
            )
            
            # Balance analysis
            balance = result['balance_rating']
            if balance > 0.9:
                balance_text = "🟢 Excellent balance!"
            elif balance > 0.7:
                balance_text = "🟡 Good balance"
            else:
                balance_text = "🟠 Fair balance"
            
            embed.add_field(
                name="⚖️ Balance Rating",
                value=f"{balance_text}\n{balance:.1%}",
                inline=False
            )
            
            embed.set_footer(text=f"✅ Analyzed {result['combinations_checked']} possible splits")
            await ctx.send(embed=embed)
            
        except Exception as e:
            print(f"Error in team_builder_command: {e}")
            traceback.print_exc()
            await ctx.send(
                "⚠️ Could not build teams. Please try again later."
            )
    
    # =========================================================================
    # COMMAND: !player_impact
    # =========================================================================
    
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
            
            # Create embed
            embed = discord.Embed(
                title=f"🤝 Player Impact: {player_name}",
                description=f"Teammate chemistry analysis ({len(partners)} partners)",
                color=discord.Color.purple(),
                timestamp=datetime.now()
            )
            
            # Best teammates
            if best_partners:
                best_text = ""
                for idx, partner in enumerate(best_partners, 1):
                    score = partner['synergy_score']
                    games = partner['games']
                    name = partner['partner_name']
                    
                    # Emoji based on synergy
                    if score > 0.15:
                        emoji = "🔥"
                    elif score > 0.08:
                        emoji = "✅"
                    else:
                        emoji = "📊"
                    
                    best_text += f"{idx}. {emoji} **{name}**\n"
                    best_text += f"   Synergy: {score:.3f} | {games} games\n"
                
                embed.add_field(
                    name="🏆 Best Teammates",
                    value=best_text,
                    inline=False
                )
            
            # Worst teammates (only if there are enough)
            if worst_partners and len(partners) > 5:
                worst_text = ""
                for idx, partner in enumerate(worst_partners, 1):
                    score = partner['synergy_score']
                    games = partner['games']
                    name = partner['partner_name']
                    
                    worst_text += f"{idx}. **{name}**\n"
                    worst_text += f"   Synergy: {score:.3f} | {games} games\n"
                
                embed.add_field(
                    name="📉 Challenging Partnerships",
                    value=worst_text,
                    inline=False
                )
            
            # Average synergy
            avg_synergy = sum(p['synergy_score'] for p in partners) / len(partners)
            embed.add_field(
                name="📊 Average Synergy",
                value=f"{avg_synergy:.3f}",
                inline=True
            )
            
            embed.add_field(
                name="👥 Unique Partners",
                value=str(len(partners)),
                inline=True
            )
            
            embed.set_footer(text="💡 Based on games with 10+ matches together")
            await ctx.send(embed=embed)
            
        except Exception as e:
            print(f"Error in player_impact_command: {e}")
            traceback.print_exc()
            await ctx.send(
                "⚠️ Could not calculate player impact. Please try again later."
            )
    
    # =========================================================================
    # ADMIN COMMANDS
    # =========================================================================
    
    @commands.command(name='fiveeyes_enable')
    @commands.has_permissions(administrator=True)
    async def enable_command(self, ctx):
        """Enable FIVEEYES synergy analytics (Admin only)"""
        config.enable()
        await ctx.send("✅ **FIVEEYES synergy analytics enabled!**")
    
    @commands.command(name='fiveeyes_disable')
    @commands.has_permissions(administrator=True)
    async def disable_command(self, ctx):
        """Disable FIVEEYES synergy analytics (Admin only)"""
        config.disable()
        await ctx.send("⚠️ **FIVEEYES synergy analytics disabled.**")
    
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
            await ctx.send(f"❌ Error during recalculation: {e}")
    
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
        """Create beautiful synergy embed"""
        # Determine rating
        if synergy.synergy_score > 0.15:
            rating = "🔥 Excellent"
            color = discord.Color.green()
        elif synergy.synergy_score > 0.08:
            rating = "✅ Good"
            color = discord.Color.blue()
        elif synergy.synergy_score > 0.03:
            rating = "📊 Positive"
            color = discord.Color.gold()
        elif synergy.synergy_score > -0.03:
            rating = "📉 Neutral"
            color = discord.Color.light_gray()
        else:
            rating = "⚠️ Poor"
            color = discord.Color.red()
        
        embed = discord.Embed(
            title=f"⚔️ Player Synergy: {synergy.player_a_name} + {synergy.player_b_name}",
            description=f"**Overall Rating:** {rating}",
            color=color,
            timestamp=datetime.now()
        )
        
        # Stats
        embed.add_field(
            name="📊 Games Together",
            value=f"{synergy.games_same_team} games on same team",
            inline=False
        )
        
        embed.add_field(
            name="📈 Performance Boost",
            value=f"{synergy.performance_boost_avg:+.1f}%",
            inline=True
        )
        
        embed.add_field(
            name="💯 Synergy Score",
            value=f"{synergy.synergy_score:.3f}",
            inline=True
        )
        
        embed.add_field(
            name="🎯 Confidence",
            value=f"{synergy.confidence:.0%}",
            inline=True
        )
        
        # Analysis
        if synergy.synergy_score > 0.08:
            analysis = "These players perform significantly better together! 🎯"
        elif synergy.synergy_score > 0.03:
            analysis = "These players work well together. 👍"
        elif synergy.synergy_score > -0.03:
            analysis = "No significant synergy detected yet."
        else:
            analysis = "These players may work better with different teammates."
        
        embed.add_field(name="📝 Analysis", value=analysis, inline=False)
        
        embed.set_footer(text="💡 Based on historical performance data")
        
        return embed


# Setup function for bot to load this cog
async def setup(bot):
    """Add SynergyAnalytics cog to bot"""
    await bot.add_cog(SynergyAnalytics(bot))
    print("✅ SynergyAnalytics cog loaded (disabled by default)")
