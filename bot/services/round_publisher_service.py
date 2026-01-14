"""
Round Publisher Service - Manages Discord auto-posting of round statistics

This service handles:
- Automatic posting of round statistics to Discord after file processing
- Comprehensive player stats from database (all fields)
- Map completion detection and aggregate summaries
- Rich Discord embeds with detailed statistics

Extracted from ultimate_bot.py as part of Week 9-10 refactoring.
"""

import discord
from datetime import datetime
import logging

logger = logging.getLogger('RoundPublisherService')


class RoundPublisherService:
    """
    Manages Discord posting of round and map statistics.

    Posting Flow:
    1. Round completes → File processed → publish_round_stats() called
    2. Fetch comprehensive stats from database (18+ fields per player)
    3. Build rich Discord embed with ALL players ranked by kills
    4. Post to production channel
    5. Check if map complete → Post aggregate map summary if last round
    """

    def __init__(self, bot, config, db_adapter):
        """
        Initialize round publisher service.

        Args:
            bot: Discord bot instance (for channel access)
            config: BotConfig instance (for production_channel_id)
            db_adapter: DatabaseAdapter instance (for database queries)
        """
        self.bot = bot
        self.config = config
        self.db_adapter = db_adapter

        logger.info("✅ RoundPublisherService initialized")

    async def publish_round_stats(self, filename: str, result: dict):
        """
        Auto-post round statistics to Discord after processing.

        Called automatically after successful file processing.
        Shows ALL players with detailed stats from database.

        Args:
            filename: Stats file name (for footer)
            result: Processing result dict containing:
                - round_id: Database round ID
                - stats_data: Parser output (used for fallback values only)
        """
        try:
            logger.debug(f"📤 Preparing Discord post for {filename}")

            # Get the production channel
            if not self.config.production_channel_id:
                logger.warning("⚠️ PRODUCTION_CHANNEL_ID not configured, skipping Discord post")
                return

            logger.debug(f"📡 Looking for production channel ID: {self.config.production_channel_id}")
            channel = self.bot.get_channel(self.config.production_channel_id)
            if not channel:
                logger.error(f"❌ Production channel {self.config.production_channel_id} not found")
                logger.error(f"   Available channels: {[c.id for c in self.bot.get_all_channels()][:10]}")
                return

            logger.debug(f"✅ Found channel: {channel.name}")

            # Get round_id from result
            round_id = result.get('round_id')
            stats_data = result.get('stats_data', {})

            if not round_id:
                logger.warning(f"⚠️ No round_id for {filename}, skipping post")
                return

            # Get basic round info from parser (for round outcome/winner)
            round_num = stats_data.get('round_num', stats_data.get('round', 1))
            map_name = stats_data.get('map_name', stats_data.get('map', 'Unknown'))
            winner_team = stats_data.get('winner_team', 'Unknown')
            round_outcome = stats_data.get('round_outcome', '')

            # 🔥 FETCH ALL PLAYER DATA FROM DATABASE (not from parser!)
            # This gives us access to ALL 54 fields, not just the limited parser output
            logger.debug(f"📊 Fetching full player data from database for session {round_id}, round {round_num}...")

            # Get round info (time limit, actual time)
            round_query = """
                SELECT time_limit, actual_time, winner_team, round_outcome
                FROM rounds
                WHERE id = ?
            """
            round_info = await self.db_adapter.fetch_one(round_query, (round_id,))

            time_limit = round_info[0] if round_info else 'Unknown'
            actual_time = round_info[1] if round_info else 'Unknown'
            db_winner_team = round_info[2] if round_info else winner_team
            db_round_outcome = round_info[3] if round_info else round_outcome

            # Get player stats (expanded to include multikills and time denied)
            players_query = """
                SELECT
                    player_name, team, kills, deaths, damage_given, damage_received,
                    team_damage_given, team_damage_received, gibs, headshots,
                    accuracy, revives_given, times_revived, time_dead_minutes,
                    efficiency, kd_ratio, time_played_minutes, dpm,
                    double_kills, triple_kills, quad_kills, multi_kills, mega_kills,
                    denied_playtime
                FROM player_comprehensive_stats
                WHERE round_id = ? AND round_number = ?
                ORDER BY kills DESC
            """
            rows = await self.db_adapter.fetch_all(players_query, (round_id, round_num))

            # Convert to dict format
            players = []
            for row in rows:
                    players.append({
                        'name': row[0],
                        'team': row[1],
                        'kills': row[2],
                        'deaths': row[3],
                        'damage_given': row[4],
                        'damage_received': row[5],
                        'team_damage_given': row[6],
                        'team_damage_received': row[7],
                        'gibs': row[8],
                        'headshots': row[9],
                        'accuracy': row[10],
                        'revives': row[11],
                        'times_revived': row[12],
                        'time_dead': row[13],
                        'efficiency': row[14],
                        'kd_ratio': row[15],
                        'time_played': row[16],
                        'dpm': row[17],
                        'double_kills': row[18] or 0,
                        'triple_kills': row[19] or 0,
                        'quad_kills': row[20] or 0,
                        'multi_kills': row[21] or 0,
                        'mega_kills': row[22] or 0,
                        'time_denied': row[23] or 0
                    })

            logger.info(f"📊 Fetched {len(players)} players with FULL stats from database")

            logger.info(f"📋 Creating embed: Round {round_num}, Map {map_name}, {len(players)} players")

            # Determine round type
            round_type = "Round 1" if round_num == 1 else "Round 2"

            # Build title - simple and clean
            title = f"🎮 {round_type} Complete - {map_name}"

            description_parts = []

            # Add time information (limit vs actual)
            if time_limit and actual_time and time_limit != 'Unknown' and actual_time != 'Unknown':
                description_parts.append(f"⏱️ **Time:** {actual_time} / {time_limit}")
            elif actual_time and actual_time != 'Unknown':
                description_parts.append(f"⏱️ **Duration:** {actual_time}")

            # Add round outcome - use DB values if available
            outcome_to_show = db_round_outcome if db_round_outcome else round_outcome
            winner_to_show = db_winner_team if db_winner_team and str(db_winner_team) != 'Unknown' else winner_team

            # Build outcome line
            outcome_line = ""
            if winner_to_show and str(winner_to_show) != 'Unknown':
                outcome_line = f"🏆 **Winner:** {winner_to_show}"
            if outcome_to_show:
                if outcome_line:
                    outcome_line += f" ({outcome_to_show})"
                else:
                    outcome_line = f"🏆 **Outcome:** {outcome_to_show}"

            if outcome_line:
                description_parts.append(outcome_line)

            # Determine embed color based on round type
            embed_color = discord.Color.blue() if round_num == 1 else discord.Color.red()

            # Create main embed
            embed = discord.Embed(
                title=title,
                description="\n".join(description_parts),
                color=embed_color,
                timestamp=datetime.now()
            )

            # Sort all players by kills
            players_sorted = sorted(players, key=lambda p: p.get('kills', 0), reverse=True)

            # Rank emoji/number helper
            def get_rank_display(rank):
                """Get rank emoji for top 3, number emojis for 4+"""
                if rank == 1:
                    return "🥇"
                elif rank == 2:
                    return "🥈"
                elif rank == 3:
                    return "🥉"
                else:
                    # Use number emojis for ranks 4+ (e.g., 4 → 4️⃣, 10 → 1️⃣0️⃣)
                    rank_str = str(rank)
                    emoji_digits = {'0': '0️⃣', '1': '1️⃣', '2': '2️⃣', '3': '3️⃣', '4': '4️⃣',
                                   '5': '5️⃣', '6': '6️⃣', '7': '7️⃣', '8': '8️⃣', '9': '9️⃣'}
                    return ''.join(emoji_digits[d] for d in rank_str)

            # Split into chunks for Discord field limits (1024 chars per field)
            chunk_size = 8
            for i in range(0, len(players_sorted), chunk_size):
                chunk = players_sorted[i:i + chunk_size]
                # Use invisible character for field name (required but hidden)
                field_name = '\u200b'

                player_lines = []
                for idx, player in enumerate(chunk):
                    rank = i + idx + 1  # Global rank across all chunks
                    rank_display = get_rank_display(rank)

                    name = player.get('name', 'Unknown')[:16]
                    kills = player.get('kills', 0)
                    deaths = player.get('deaths', 0)
                    gibs = player.get('gibs', 0)
                    kd_ratio = player.get('kd_ratio', 0) or 0
                    dpm = player.get('dpm', 0) or 0
                    dmg = player.get('damage_given', 0) or 0
                    dmg_recv = player.get('damage_received', 0) or 0
                    acc = player.get('accuracy', 0) or 0
                    hs = player.get('headshots', 0) or 0
                    revives = player.get('revives', 0) or 0
                    got_revived = player.get('times_revived', 0) or 0
                    team_dmg = player.get('team_damage_given', 0) or 0
                    time_dead = player.get('time_dead', 0) or 0
                    time_denied = player.get('time_denied', 0) or 0
                    time_played = player.get('time_played', 0) or 0

                    # Multikills
                    double_kills = player.get('double_kills', 0) or 0
                    triple_kills = player.get('triple_kills', 0) or 0
                    quad_kills = player.get('quad_kills', 0) or 0
                    multi_kills = player.get('multi_kills', 0) or 0
                    mega_kills = player.get('mega_kills', 0) or 0

                    # Format damage (K if over 1000)
                    if dmg >= 1000:
                        dmg_str = f"{dmg/1000:.1f}K"
                    else:
                        dmg_str = f"{int(dmg)}"

                    if dmg_recv >= 1000:
                        dmg_recv_str = f"{dmg_recv/1000:.1f}K"
                    else:
                        dmg_recv_str = f"{int(dmg_recv)}"

                    # Format times as M:SS
                    dead_min = int(time_dead)
                    dead_sec = int((time_dead % 1) * 60)
                    time_dead_str = f"{dead_min}:{dead_sec:02d}"

                    denied_min = int(time_denied // 60)
                    denied_sec = int(time_denied % 60)
                    time_denied_str = f"{denied_min}:{denied_sec:02d}"

                    played_min = int(time_played)
                    played_sec = int((time_played % 1) * 60)
                    time_played_str = f"{played_min}:{played_sec:02d}"

                    # Build multikills string (only if any)
                    multikills_parts = []
                    if double_kills > 0:
                        multikills_parts.append(f"{double_kills}x2")
                    if triple_kills > 0:
                        multikills_parts.append(f"{triple_kills}x3")
                    if quad_kills > 0:
                        multikills_parts.append(f"{quad_kills}x4")
                    if multi_kills > 0:
                        multikills_parts.append(f"{multi_kills}x5")
                    if mega_kills > 0:
                        multikills_parts.append(f"{mega_kills}x6")
                    multikills_str = " ".join(multikills_parts)

                    # Line 1: Rank + Name
                    line1 = f"{rank_display} **{name}**"

                    # Line 2: All combat stats (compact format like session_embed)
                    # K/D/G (ratio) • DPM • DMG↑/↓ • ACC • HS • Rev±
                    # Gibs TmDmg • ⏱Played 💀Dead ⏳Denied • Multikills
                    line2 = (
                        f"{kills}K/{deaths}D/{gibs}G ({kd_ratio:.2f}) "
                        f"DPM:{int(dpm)} {dmg_str}⬆/{dmg_recv_str}⬇ "
                        f"ACC:{acc:.1f}% HS:{hs} Rev:{revives}↑/{got_revived}↓"
                    )
                    line3 = (
                        f"TmDmg:{int(team_dmg)} "
                        f"⏱{time_played_str} 💀{time_dead_str} ⏳{time_denied_str}"
                    )
                    if multikills_str:
                        line3 += f" 🔥{multikills_str}"

                    # Combine: Name on line 1, stats on line 2+3 with indent
                    player_lines.append(f"{line1}\n↳ {line2}\n↳ {line3}")

                # Join with blank line between players for readability
                embed.add_field(
                    name=field_name,
                    value='\n\n'.join(player_lines) if player_lines else 'No stats',
                    inline=False
                )

            # Calculate round totals (comprehensive)
            total_kills = sum(p.get('kills', 0) for p in players)
            total_deaths = sum(p.get('deaths', 0) for p in players)
            total_dmg = sum(p.get('damage_given', 0) for p in players)
            total_hs = sum(p.get('headshots', 0) for p in players)
            total_team_dmg = sum(p.get('team_damage_given', 0) for p in players)
            avg_acc = sum(p.get('accuracy', 0) for p in players) / len(players) if players else 0
            avg_dpm = sum(p.get('dpm', 0) for p in players) / len(players) if players else 0
            avg_time_dead = sum(p.get('time_dead', 0) for p in players) / len(players) if players else 0

            embed.add_field(
                name="📊 Round Summary",
                value=(
                    f"**Totals:** Kills:`{total_kills}` Deaths:`{total_deaths}` HS:`{total_hs}` "
                    f"Damage:`{int(total_dmg):,}` TeamDmg:`{int(total_team_dmg):,}`\n"
                    f"**Averages:** Accuracy:`{avg_acc:.1f}%` DPM:`{int(avg_dpm)}` DeadTime:`{avg_time_dead:.1f}m`"
                ),
                inline=False
            )

            embed.set_footer(text=f"Round ID: {round_id} | {filename}")

            # Post to channel
            logger.info(f"📤 Sending detailed stats embed to #{channel.name}...")
            await channel.send(embed=embed)
            logger.info(f"✅ Successfully posted stats for {len(players)} players to Discord!")

            # 🗺️ Check if this was the last round for the map → post map summary
            await self._check_and_post_map_completion(round_id, map_name, round_num, channel)

            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"❌ Error posting round stats to Discord: {e}", exc_info=True)

    async def _check_and_post_map_completion(self, round_id: int, map_name: str, current_round: int, channel):
        """
        Check if we just finished the last round of a map.
        If so, post aggregate map statistics.

        Args:
            round_id: Database round/session ID
            map_name: Map name
            current_round: Current round number (1 or 2)
            channel: Discord channel to post to
        """
        try:
            # Check if there are any more rounds for this map in this session
            query = """
                SELECT MAX(round_number) as max_round, COUNT(DISTINCT round_number) as round_count
                FROM player_comprehensive_stats
                WHERE round_id = ? AND map_name = ?
            """
            row = await self.db_adapter.fetch_one(query, (round_id, map_name))

            if not row:
                return

            max_round, round_count = row

            logger.debug(f"🗺️ Map check: {map_name} - current round {current_round}, max in DB: {max_round}, total rounds: {round_count}")

            # If current round matches max round in DB, this is the last round for the map
            if current_round == max_round and round_count >= 2:
                logger.info(f"🏁 Map complete! {map_name} finished after {round_count} rounds. Posting map summary...")
                await self._post_map_summary(round_id, map_name, channel)
            else:
                logger.debug(f"⏳ Map {map_name} not complete yet (round {current_round}/{max_round})")

        except Exception as e:
            logger.error(f"❌ Error checking map completion: {e}", exc_info=True)

    async def _post_map_summary(self, round_id: int, map_name: str, channel):
        """
        Post aggregate statistics for all rounds of a completed map.

        Args:
            round_id: Database round/session ID
            map_name: Map name
            channel: Discord channel to post to
        """
        try:
            logger.info(f"📊 Generating map summary for {map_name}...")

            # Get map-level aggregate stats
            map_query = """
                SELECT
                    COUNT(DISTINCT round_number) as total_rounds,
                    COUNT(DISTINCT player_guid) as unique_players,
                    SUM(kills) as total_kills,
                    SUM(deaths) as total_deaths,
                    SUM(damage_given) as total_damage,
                    SUM(headshot_kills) as total_headshots,
                    AVG(accuracy) as avg_accuracy
                FROM player_comprehensive_stats
                WHERE round_id = ? AND map_name = ?
            """
            map_stats = await self.db_adapter.fetch_one(map_query, (round_id, map_name))

            if not map_stats:
                logger.warning(f"⚠️ No map stats found for {map_name}")
                return

            total_rounds, unique_players, total_kills, total_deaths, total_damage, total_headshots, avg_accuracy = map_stats

            # Get top 5 players across all rounds on this map
            top_players_query = """
                SELECT
                    player_name,
                    SUM(kills) as total_kills,
                    SUM(deaths) as total_deaths,
                    SUM(damage_given) as total_damage,
                    AVG(accuracy) as avg_accuracy
                FROM player_comprehensive_stats
                WHERE round_id = ? AND map_name = ?
                GROUP BY player_guid
                ORDER BY total_kills DESC
                LIMIT 5
            """
            top_players = await self.db_adapter.fetch_all(top_players_query, (round_id, map_name))

            # Create embed
            embed = discord.Embed(
                title=f"🗺️ {map_name.upper()} - Map Complete!",
                description=f"Aggregate stats from **{total_rounds} rounds**",
                color=discord.Color.gold(),
                timestamp=datetime.now()
            )

            # Map overview
            kd_ratio = total_kills / total_deaths if total_deaths > 0 else total_kills
            embed.add_field(
                    name="📊 Map Overview",
                    value=(
                        f"**Rounds Played:** {total_rounds}\n"
                        f"**Unique Players:** {unique_players}\n"
                        f"**Total Kills:** {total_kills:,}\n"
                        f"**Total Deaths:** {total_deaths:,}\n"
                        f"**K/D Ratio:** {kd_ratio:.2f}\n"
                        f"**Total Damage:** {int(total_damage):,}\n"
                        f"**Total Headshots:** {total_headshots}\n"
                        f"**Avg Accuracy:** {avg_accuracy:.1f}%"
                    ),
                    inline=False
            )

            # Top performers
            if top_players:
                top_lines = []
                for i, (name, kills, deaths, damage, acc) in enumerate(top_players, 1):
                    kd = kills / deaths if deaths > 0 else kills
                    top_lines.append(
                        f"{i}. **{name}** - {kills}/{deaths} K/D ({kd:.2f}) | {int(damage):,} DMG | {acc:.1f}% ACC"
                    )

                embed.add_field(
                    name="🏆 Top Performers (All Rounds)",
                    value="\n".join(top_lines),
                    inline=False
                )

            embed.set_footer(text=f"Round ID: {round_id}")

            # Post to channel
            logger.info(f"📤 Posting map summary to #{channel.name}...")
            await channel.send(embed=embed)
            logger.info(f"✅ Map summary posted for {map_name}!")

        except Exception as e:
            logger.error(f"❌ Error posting map summary: {e}", exc_info=True)

    async def publish_endstats(
        self,
        filename: str,
        endstats_data: dict,
        round_id: int,
        map_name: str,
        round_number: int
    ):
        """
        Post endstats (awards and VS stats) embed to Discord.

        Called after processing endstats file. Posts a follow-up embed
        with categorized awards and top VS performers.

        Args:
            filename: Endstats filename (for footer)
            endstats_data: Parsed endstats dict with 'awards' and 'vs_stats'
            round_id: Database round ID
            map_name: Map name
            round_number: Round number (1 or 2)
        """
        try:
            logger.info(f"🏆 Publishing endstats for {filename}")

            # Get production channel
            if not self.config.production_channel_id:
                logger.warning("⚠️ PRODUCTION_CHANNEL_ID not configured")
                return

            channel = self.bot.get_channel(self.config.production_channel_id)
            if not channel:
                logger.error("❌ Production channel not found")
                return

            awards = endstats_data.get('awards', [])
            vs_stats = endstats_data.get('vs_stats', [])

            # Import categorization helper
            from bot.endstats_parser import EndStatsParser

            parser = EndStatsParser()
            categorized = parser.categorize_awards(awards)

            # Create embed
            embed = discord.Embed(
                title=f"🏆 Round {round_number} Awards - {map_name}",
                color=discord.Color.gold(),
                timestamp=datetime.now()
            )

            # Category display info
            category_info = {
                'combat': ('⚔️ Combat', ''),
                'deaths': ('💀 Deaths & Mayhem', ''),
                'skills': ('🎯 Skills', ''),
                'weapons': ('🔫 Weapons', ''),
                'teamwork': ('🤝 Teamwork', ''),
                'objectives': ('🎯 Objectives', ''),
                'timing': ('⏱️ Timing', ''),
                'other': ('📋 Other', ''),
            }

            # Add categorized awards as fields
            for category, cat_awards in categorized.items():
                if not cat_awards:
                    continue

                cat_name, _ = category_info.get(category, (category.title(), ''))

                # Build award lines
                award_lines = []
                for award in cat_awards[:6]:  # Limit per category for embed size
                    name = award['name']
                    player = award['player']
                    value = award['value']

                    # Shorten long award names
                    if len(name) > 30:
                        name = name[:27] + "..."

                    award_lines.append(f"**{name}:** {player} ({value})")

                if award_lines:
                    embed.add_field(
                        name=cat_name,
                        value="\n".join(award_lines),
                        inline=True
                    )

            # Add VS stats summary if present
            if vs_stats:
                # Aggregate VS stats per player
                player_totals = {}
                for vs in vs_stats:
                    player = vs['player']
                    if player not in player_totals:
                        player_totals[player] = {'kills': 0, 'deaths': 0}
                    player_totals[player]['kills'] += vs['kills']
                    player_totals[player]['deaths'] += vs['deaths']

                # Sort by kills
                sorted_players = sorted(
                    player_totals.items(),
                    key=lambda x: x[1]['kills'],
                    reverse=True
                )[:5]  # Top 5

                if sorted_players:
                    vs_lines = []
                    for player, stats in sorted_players:
                        vs_lines.append(f"**{player}:** {stats['kills']}K/{stats['deaths']}D")

                    embed.add_field(
                        name="📊 VS Stats (Top 5)",
                        value="\n".join(vs_lines),
                        inline=False
                    )

            # Footer
            embed.set_footer(text=f"Round {round_number} | {filename}")

            # Post embed
            await channel.send(embed=embed)
            logger.info(f"✅ Endstats embed posted for {filename}")

        except Exception as e:
            logger.error(f"❌ Error publishing endstats: {e}", exc_info=True)
