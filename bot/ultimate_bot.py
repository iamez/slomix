#!/usr/bin/env python3
"""
🚀 ULTIMATE ET:LEGACY DISCORD BOT - COG-BASED VERSION
====================================================

Fixed version using proper Cog patt          embed.add_field(
            name="📊 Stats Commands",
            value=(
                "• `!stats [player]` - Player statistics\\n"
                "• `!leaderboard [type]` - Rankings (kills/kd/dpm/acc/hs)\\n"
                "• `!session [date]` - Match details"
            ),
            inline=False
        )

        embed.add_field(
            name="🔗 Account",
            value="• `!link <name>` - Link your account\\n• `!unlink` - Unlink",
            inline=False
        )

        embed.add_field(
            name="🔧 System",
            value="• `!ping` - Bot status\\n• `!session_start/end` - Manage sessions",
            inline=False
        )

        await ctx.send(embed=embed)ld(
            name="📊 Stats Commands",
            value=(
                "• `!stats [player]` - Player statistics\\n"
                "• `!leaderboard [type]` - Top players (kills/kd/dpm/acc/hs)\\n"
                "• `!session [date]` - Session details"
            ),
            inline=False
        )or discord.py 2.3.x
All commands now properly register and work correctly.
"""

import asyncio
import datetime
import logging
import os
import time
from datetime import datetime
import sqlite3

import aiosqlite
import discord
from discord.ext import commands, tasks

# Load environment variables
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    print("⚠️  python-dotenv not installed. Using environment variables directly.")

# Setup comprehensive logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/ultimate_bot.log', encoding='utf-8'),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger('UltimateBot')


class ETLegacyCommands(commands.Cog):
    """🎮 ET:Legacy Bot Commands Cog"""

    def __init__(self, bot):
        self.bot = bot

    # 🎮 SESSION MANAGEMENT COMMANDS

    @commands.command(name='session_start')
    async def session_start(self, ctx, *, map_name: str = "Unknown"):
        """🎬 Start a new gaming session"""
        try:
            if self.bot.current_session:
                await ctx.send("❌ A session is already active. End it first with `!session_end`")
                return

            now = datetime.now()
            date_str = now.strftime('%Y-%m-%d')
            time_str = now.strftime('%H:%M:%S')

            async with aiosqlite.connect(self.bot.db_path) as db:
                cursor = await db.execute(
                    '''
                    INSERT INTO sessions (start_time, date, map_name, status)
                    VALUES (?, ?, ?, 'active')
                ''',
                    (time_str, date_str, map_name),
                )

                session_id = cursor.lastrowid
                self.bot.current_session = session_id
                await db.commit()

            embed = discord.Embed(
                title="🎬 Session Started!",
                description=f"**Map:** {map_name}\\n**Started:** {time_str}\\n**Session ID:** {session_id}",
                color=0x00FF00,
                timestamp=now,
            )
            await ctx.send(embed=embed)
            logger.info(f"Session {session_id} started on {map_name}")

        except Exception as e:
            logger.error(f"Error starting session: {e}")
            await ctx.send(f"❌ Error starting session: {e}")

    @commands.command(name='sync_stats', aliases=['syncstats', 'sync_logs'])
    async def sync_stats(self, ctx):
        """🔄 Manually sync and process unprocessed stats files from server"""
        try:
            if not self.bot.ssh_enabled:
                await ctx.send(
                    "❌ SSH monitoring is not enabled. "
                    "Set `SSH_ENABLED=true` in .env file."
                )
                return
            
            # Send initial message
            status_msg = await ctx.send(
                "🔄 Checking remote server for new stats files..."
            )
            
            # Build SSH config
            ssh_config = {
                'host': os.getenv('SSH_HOST'),
                'port': int(os.getenv('SSH_PORT', 22)),
                'user': os.getenv('SSH_USER'),
                'key_path': os.getenv('SSH_KEY_PATH', ''),
                'remote_path': os.getenv('REMOTE_STATS_PATH')
            }
            
            # List remote files
            remote_files = await self.bot.ssh_list_remote_files(ssh_config)
            
            if not remote_files:
                await status_msg.edit(
                    content="❌ Could not connect to server or no files found."
                )
                return
            
            # Check which files need processing
            files_to_process = []
            for filename in remote_files:
                if await self.bot.should_process_file(filename):
                    files_to_process.append(filename)
            
            if not files_to_process:
                await status_msg.edit(
                    content="✅ All files are already processed! Nothing new to sync."
                )
                return
            
            # Sort files: Round 1 before Round 2, chronologically
            # Format: YYYY-MM-DD-HHMMSS-mapname-round-N.txt
            def sort_key(filename):
                parts = filename.split('-')
                if len(parts) >= 7:
                    date = '-'.join(parts[:3])  # YYYY-MM-DD
                    time = parts[3]  # HHMMSS
                    round_num = parts[-1].replace('.txt', '')  # N from round-N
                    return (date, time, round_num)  # Sort by date, time, then round
                return (filename, '', '99')  # Fallback
            
            files_to_process.sort(key=sort_key)
            
            # Phase 1: Download ALL files first
            await status_msg.edit(
                content=f"📥 Downloading {len(files_to_process)} file(s)..."
            )
            
            downloaded_files = []
            download_failed = 0
            
            for i, filename in enumerate(files_to_process):
                try:
                    # Download file
                    local_path = await self.bot.ssh_download_file(
                        ssh_config, filename, 'local_stats'
                    )
                    
                    if local_path:
                        downloaded_files.append((filename, local_path))
                        
                        # Update progress every 50 files
                        if (i + 1) % 50 == 0:
                            await status_msg.edit(
                                content=f"📥 Downloading... {i + 1}/{len(files_to_process)}"
                            )
                    else:
                        download_failed += 1
                        logger.warning(f"Failed to download {filename}")
                        
                except Exception as e:
                    logger.error(f"Download error for {filename}: {e}")
                    download_failed += 1
            
            # Phase 2: Verify downloads
            await status_msg.edit(
                content=f"🔍 Verifying downloads... {len(downloaded_files)} files"
            )
            
            local_files = set(os.listdir('local_stats'))
            verified_files = []
            
            for filename, local_path in downloaded_files:
                if os.path.basename(local_path) in local_files:
                    verified_files.append((filename, local_path))
                else:
                    logger.error(f"Downloaded file missing: {filename}")
                    download_failed += 1
            
            logger.info(
                f"✅ Downloaded {len(verified_files)} files, "
                f"{download_failed} failed"
            )
            
            if not verified_files:
                await status_msg.edit(
                    content="❌ No files were successfully downloaded."
                )
                return
            
            # Phase 3: Process/parse files for database import
            await status_msg.edit(
                content=f"⚙️ Processing {len(verified_files)} file(s) for database import..."
            )
            
            processed = 0
            process_failed = 0
            
            for i, (filename, local_path) in enumerate(verified_files):
                try:
                    # Process the file (parse + import)
                    result = await self.bot.process_gamestats_file(
                        local_path, filename
                    )
                    
                    if result.get('success'):
                        processed += 1
                    else:
                        process_failed += 1
                        logger.error(f"Processing failed for {filename}: {result.get('error')}")
                    
                    # Update progress every 50 files
                    if (i + 1) % 50 == 0:
                        await status_msg.edit(
                            content=f"⚙️ Processing... {i + 1}/{len(verified_files)}"
                        )
                        
                except Exception as e:
                    logger.error(f"Failed to process {filename}: {e}")
                    process_failed += 1
            
            # Final status
            embed = discord.Embed(
                title="✅ Stats Sync Complete!",
                color=0x00FF00,
                timestamp=datetime.now()
            )
            embed.add_field(
                name="� Download Phase",
                value=(
                    f"✅ Downloaded: **{len(verified_files)}** file(s)\n"
                    f"❌ Failed: **{download_failed}** file(s)"
                ),
                inline=False
            )
            embed.add_field(
                name="⚙️ Processing Phase",
                value=(
                    f"✅ Processed: **{processed}** file(s)\n"
                    f"❌ Failed: **{process_failed}** file(s)"
                ),
                inline=False
            )
            
            if processed > 0:
                embed.add_field(
                    name="💡 What's Next?",
                    value=(
                        "Round summaries have been posted above!\n"
                        "Use `!last_session` to see full session details."
                    ),
                    inline=False
                )
            
            await status_msg.edit(content=None, embed=embed)
            logger.info(
                f"✅ Manual sync complete: {len(verified_files)} downloaded, "
                f"{processed} processed, {process_failed} failed"
            )
            
        except Exception as e:
            logger.error(f"Error in sync_stats: {e}")
            await ctx.send(f"❌ Sync error: {e}")

    @commands.command(name='session_end')
    async def session_end(self, ctx):
        """🏁 Stop SSH monitoring"""
        try:
            if not self.bot.monitoring:
                await ctx.send("❌ Monitoring is not currently active.")
                return

            # Disable monitoring flag
            self.bot.monitoring = False

            embed = discord.Embed(
                title="🏁 Monitoring Stopped",
                description=(
                    "SSH monitoring has been disabled.\n\n"
                    "Use `!session_start` to re-enable automatic monitoring."
                ),
                color=0xFF0000,
                timestamp=datetime.now(),
            )

            await ctx.send(embed=embed)
            logger.info("✅ Monitoring manually stopped via !session_end")

        except Exception as e:
            logger.error(f"Error ending session: {e}")
            await ctx.send(f"❌ Error ending session: {e}")

    @commands.command(name='ping')
    async def ping(self, ctx):
        """🏓 Check bot status and performance"""
        try:
            start_time = time.time()

            # Test database connection
            async with aiosqlite.connect(self.bot.db_path) as db:
                await db.execute('SELECT 1')

            db_latency = (time.time() - start_time) * 1000

            embed = discord.Embed(title="🏓 Ultimate Bot Status", color=0x00FF00)
            embed.add_field(
                name="Bot Latency",
                value=f"{
                    round(
                        self.bot.latency *
                        1000)}ms",
                inline=True,
            )
            embed.add_field(name="DB Latency", value=f"{round(db_latency)}ms", inline=True)
            embed.add_field(
                name="Active Session",
                value="Yes" if self.bot.current_session else "No",
                inline=True,
            )
            embed.add_field(name="Commands", value=f"{len(list(self.bot.commands))}", inline=True)

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in ping command: {e}")
            await ctx.send(f"❌ Bot error: {e}")

    @commands.command(name='help_command')
    async def help_command(self, ctx):
        """📚 Show all available commands"""
        embed = discord.Embed(
            title="🚀 Ultimate ET:Legacy Bot Commands",
            description="**Use `!` prefix for all commands** (e.g., `!ping`, not `/ping`)",
            color=0x0099FF,
        )

        embed.add_field(
            name="🎬 Session Management",
            value="• `!session_start [map]` - Start new session\\n• `!session_end` - End current session",
            inline=False,
        )

        embed.add_field(
            name="� Stats Commands",
            value="• `!stats [player]` - Player statistics\\n• `!leaderboard [type]` - Top players\\n• `!session [date]` - Session details",
            inline=False,
        )

        embed.add_field(
            name="�🔧 System",
            value="• `!ping` - Bot status\\n• `!help_command` - This help",
            inline=False,
        )

        await ctx.send(embed=embed)

    @commands.command(name='stats')
    async def stats(self, ctx, *, player_name: str = None):
        """📊 Show detailed player statistics
        
        Usage:
        - !stats              → Your stats (if linked)
        - !stats playerName   → Search by name
        - !stats @user        → Stats for mentioned Discord user
        """
        try:
            player_guid = None
            primary_name = None
            
            # Open ONE database connection for the entire command
            async with aiosqlite.connect(self.bot.db_path) as db:
                # === SCENARIO 1: @MENTION - Look up linked Discord user ===
                if ctx.message.mentions:
                    mentioned_user = ctx.message.mentions[0]
                    mentioned_id = str(mentioned_user.id)
                    
                    async with db.execute(
                        '''
                        SELECT et_guid, et_name FROM player_links
                        WHERE discord_id = ?
                    ''',
                        (mentioned_id,),
                    ) as cursor:
                        link = await cursor.fetchone()
                    
                    if not link:
                        # User not linked - helpful message
                        embed = discord.Embed(
                            title="⚠️ Account Not Linked",
                            description=(
                                f"{mentioned_user.mention} hasn't linked their "
                                f"ET:Legacy account yet!"
                            ),
                            color=0xFFA500,
                        )
                        embed.add_field(
                            name="How to Link",
                            value=(
                                "• `!link` - Search for your player\n"
                                "• `!link <name>` - Link by name\n"
                                "• `!link <GUID>` - Link with GUID"
                            ),
                            inline=False,
                        )
                        embed.add_field(
                            name="Admin Help",
                            value=(
                                f"Admins can help link with:\n"
                                f"`!link {mentioned_user.mention} <GUID>`"
                            ),
                            inline=False,
                        )
                        await ctx.send(embed=embed)
                        return
                    
                    player_guid = link[0]
                    primary_name = link[1]
                    logger.info(
                        f"Stats via @mention: {ctx.author} looked up "
                        f"{mentioned_user} (GUID: {player_guid})"
                    )
                
                # === SCENARIO 2: NO ARGS - Use author's linked account ===
                elif not player_name:
                    discord_id = str(ctx.author.id)
                    async with db.execute(
                        '''
                        SELECT et_guid, et_name FROM player_links
                        WHERE discord_id = ?
                    ''',
                        (discord_id,),
                    ) as cursor:
                        link = await cursor.fetchone()
                    
                    if not link:
                        await ctx.send(
                            "❌ Please specify a player name or link your "
                            "account with `!link`"
                        )
                        return
                    
                    player_guid = link[0]
                    primary_name = link[1]

                # === SCENARIO 3: NAME SEARCH - Traditional lookup ===
                else:
                    # Try exact match in player_links first
                    async with db.execute(
                        '''
                        SELECT et_guid, et_name FROM player_links
                        WHERE LOWER(et_name) = LOWER(?)
                        LIMIT 1
                    ''',
                        (player_name,),
                    ) as cursor:
                        link = await cursor.fetchone()

                    if link:
                        player_guid = link[0]
                        primary_name = link[1]
                    else:
                        # Search in player_aliases
                        async with db.execute(
                            '''
                            SELECT player_guid, player_name
                            FROM player_aliases
                            WHERE LOWER(clean_name) LIKE LOWER(?)
                            ORDER BY last_seen DESC
                            LIMIT 1
                        ''',
                            (f'%{player_name}%',),
                        ) as cursor:
                            alias_result = await cursor.fetchone()
                        
                        if alias_result:
                            player_guid = alias_result[0]
                            primary_name = alias_result[1]
                        else:
                            # Fallback to player_comprehensive_stats
                            async with db.execute(
                                '''
                                SELECT player_guid, player_name
                                FROM player_comprehensive_stats
                                WHERE LOWER(player_name) LIKE LOWER(?)
                                GROUP BY player_guid
                                LIMIT 1
                            ''',
                                (f'%{player_name}%',),
                            ) as cursor:
                                result = await cursor.fetchone()
                                if not result:
                                    await ctx.send(
                                        f"❌ Player '{player_name}' not found."
                                    )
                                    return
                                player_guid = result[0]
                                primary_name = result[1]
                
                # === NOW WE HAVE player_guid AND primary_name - Get Stats ===

                # Get overall stats
                async with db.execute(
                    '''
                    SELECT
                        COUNT(DISTINCT session_id) as total_games,
                        SUM(kills) as total_kills,
                        SUM(deaths) as total_deaths,
                        SUM(damage_given) as total_damage,
                        SUM(damage_received) as total_damage_received,
                        SUM(headshot_kills) as total_headshots,
                        CASE
                            WHEN SUM(time_played_seconds) > 0
                            THEN (SUM(damage_given) * 60.0) / SUM(time_played_seconds)
                            ELSE 0
                        END as weighted_dpm,
                        AVG(kd_ratio) as avg_kd
                    FROM player_comprehensive_stats
                    WHERE player_guid = ?
                ''',
                    (player_guid,),
                ) as cursor:
                    overall = await cursor.fetchone()

                # Get weapon stats with accuracy
                async with db.execute(
                    '''
                    SELECT
                        SUM(w.hits) as total_hits,
                        SUM(w.shots) as total_shots,
                        SUM(w.headshots) as total_hs
                    FROM weapon_comprehensive_stats w
                    WHERE w.player_guid = ?
                ''',
                    (player_guid,),
                ) as cursor:
                    weapon_overall = await cursor.fetchone()

                # Get favorite weapons
                async with db.execute(
                    '''
                    SELECT weapon_name, SUM(kills) as total_kills
                    FROM weapon_comprehensive_stats
                    WHERE player_guid = ?
                    GROUP BY weapon_name
                    ORDER BY total_kills DESC
                    LIMIT 3
                ''',
                    (player_guid,),
                ) as cursor:
                    fav_weapons = await cursor.fetchall()

                # Get recent activity
                async with db.execute(
                    '''
                    SELECT s.session_date, s.map_name, p.kills, p.deaths
                    FROM player_comprehensive_stats p
                    JOIN sessions s ON p.session_id = s.id
                    WHERE p.player_guid = ?
                    ORDER BY s.session_date DESC
                    LIMIT 3
                ''',
                    (player_guid,),
                ) as cursor:
                    recent = await cursor.fetchall()

                # Calculate stats
                games, kills, deaths, dmg, dmg_recv, hs, avg_dpm, avg_kd = overall
                hits, shots, hs_weapon = weapon_overall if weapon_overall else (0, 0, 0)

                kd_ratio = kills / deaths if deaths > 0 else kills
                accuracy = (hits / shots * 100) if shots > 0 else 0
                hs_pct = (hs / hits * 100) if hits > 0 else 0

                # Build embed
                embed = discord.Embed(
                    title=f"📊 Stats for {primary_name}",
                    color=0x0099FF,
                    timestamp=datetime.now(),
                )

                embed.add_field(
                    name="🎮 Overview",
                    value=(
                        f"**Games Played:** {games:,}\\n**K/D Ratio:** {kd_ratio:.2f}\\n**Avg DPM:** {avg_dpm:.1f}"
                        if avg_dpm
                        else "0.0"
                    ),
                    inline=True,
                )

                embed.add_field(
                    name="⚔️ Combat",
                    value=f"**Kills:** {kills:,}\\n**Deaths:** {deaths:,}\\n**Headshots:** {hs:,} ({hs_pct:.1f}%)",
                    inline=True,
                )

                embed.add_field(
                    name="🎯 Accuracy",
                    value=f"**Overall:** {accuracy:.1f}%\\n**Damage Given:** {dmg:,}\\n**Damage Taken:** {dmg_recv:,}",
                    inline=True,
                )

                if fav_weapons:
                    weapons_text = "\\n".join(
                        [f"**{w[0].replace('WS_', '').title()}:** {w[1]:,} kills" for w in fav_weapons]
                    )
                    embed.add_field(name="🔫 Favorite Weapons", value=weapons_text, inline=False)

                if recent:
                    recent_text = "\\n".join([f"`{r[0]}` **{r[1]}** - {r[2]}K/{r[3]}D" for r in recent])
                    embed.add_field(name="📅 Recent Matches", value=recent_text, inline=False)

                # Get aliases for footer
                async with db.execute(
                    '''
                    SELECT player_name
                    FROM player_aliases
                    WHERE player_guid = ? AND LOWER(player_name) != LOWER(?)
                    ORDER BY last_seen DESC, times_used DESC
                    LIMIT 3
                ''',
                    (player_guid, primary_name),
                ) as cursor:
                    aliases = await cursor.fetchall()

                # Build footer with GUID and aliases
                footer_text = f"GUID: {player_guid}"
                if aliases:
                    alias_names = ", ".join([a[0] for a in aliases])
                    footer_text += f" | Also known as: {alias_names}"
                
                embed.set_footer(text=footer_text)
                await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in stats command: {e}", exc_info=True)
            await ctx.send(f"❌ Error retrieving stats: {e}")

    @commands.command(name='leaderboard', aliases=['lb', 'top'])
    async def leaderboard(self, ctx, stat_type: str = 'kills', page: int = 1):
        """🏆 Show players leaderboard with pagination

        Usage:
        - !lb              → First page (kills)
        - !lb 2            → Page 2 (kills)
        - !lb dpm          → First page (DPM)
        - !lb dpm 2        → Page 2 (DPM)

        Available stat types:
        - kills: Total kills
        - kd: Kill/Death ratio
        - dpm: Damage per minute
        - accuracy/acc: Overall accuracy
        - headshots/hs: Headshot percentage
        - games: Games played
        - revives: Most revives given (medic)
        - gibs: Most gibs (finishing moves)
        - objectives/obj: Most objectives completed
        - efficiency/eff: Highest efficiency rating
        - teamwork: Best teamwork (lowest team damage %)
        - multikills: Most multikills (doubles, triples, etc)
        - grenades/nades: Top grenadiers (grenade kills + accuracy)
        """
        try:
            # Handle case where user passes page number as first arg
            # e.g., !lb 2 should be interpreted as page 2 of kills
            if stat_type.isdigit():
                page = int(stat_type)
                stat_type = 'kills'
            else:
                stat_type = stat_type.lower()
            
            # Ensure page is at least 1
            page = max(1, page)
            
            # 10 players per page
            players_per_page = 10
            offset = (page - 1) * players_per_page

            # Map aliases to stat types
            stat_aliases = {
                'k': 'kills',
                'kill': 'kills',
                'kd': 'kd',
                'ratio': 'kd',
                'dpm': 'dpm',
                'damage': 'dpm',
                'acc': 'accuracy',
                'accuracy': 'accuracy',
                'hs': 'headshots',
                'headshot': 'headshots',
                'headshots': 'headshots',
                'games': 'games',
                'played': 'games',
                'revives': 'revives',
                'revive': 'revives',
                'medic': 'revives',
                'gibs': 'gibs',
                'gib': 'gibs',
                'obj': 'objectives',
                'objective': 'objectives',
                'objectives': 'objectives',
                'eff': 'efficiency',
                'efficiency': 'efficiency',
                'teamwork': 'teamwork',
                'team': 'teamwork',
                'multikill': 'multikills',
                'multikills': 'multikills',
                'multi': 'multikills',
                'grenade': 'grenades',
                'grenades': 'grenades',
                'nades': 'grenades',
                'nade': 'grenades',
            }

            stat_type = stat_aliases.get(stat_type, 'kills')

            async with aiosqlite.connect(self.bot.db_path) as db:
                # Get total count for pagination
                count_query = '''
                    SELECT COUNT(DISTINCT player_guid) 
                    FROM player_comprehensive_stats
                '''
                async with db.execute(count_query) as cursor:
                    total_players = (await cursor.fetchone())[0]
                
                total_pages = (total_players + players_per_page - 1) // players_per_page
                
                if stat_type == 'kills':
                    query = f'''
                        SELECT 
                            (SELECT player_name FROM player_comprehensive_stats 
                             WHERE player_guid = p.player_guid 
                             GROUP BY player_name 
                             ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                            SUM(p.kills) as total_kills,
                            SUM(p.deaths) as total_deaths,
                            COUNT(DISTINCT p.session_id) as games,
                            p.player_guid
                        FROM player_comprehensive_stats p
                        GROUP BY p.player_guid
                        HAVING games > 10
                        ORDER BY total_kills DESC
                        LIMIT {players_per_page} OFFSET {offset}
                    '''
                    title = f"🏆 Top Players by Kills (Page {page}/{total_pages})"

                elif stat_type == 'kd':
                    query = f'''
                        SELECT 
                            (SELECT player_name FROM player_comprehensive_stats 
                             WHERE player_guid = p.player_guid 
                             GROUP BY player_name 
                             ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                            SUM(p.kills) as total_kills,
                            SUM(p.deaths) as total_deaths,
                            COUNT(DISTINCT p.session_id) as games,
                            p.player_guid
                        FROM player_comprehensive_stats p
                        GROUP BY p.player_guid
                        HAVING games > 50 AND total_deaths > 0
                        ORDER BY (CAST(total_kills AS FLOAT) / total_deaths) DESC
                        LIMIT {players_per_page} OFFSET {offset}
                    '''
                    title = f"🏆 Top Players by K/D Ratio (Page {page}/{total_pages})"

                elif stat_type == 'dpm':
                    query = f'''
                        SELECT 
                            (SELECT player_name FROM player_comprehensive_stats 
                             WHERE player_guid = p.player_guid 
                             GROUP BY player_name 
                             ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                            CASE
                                WHEN SUM(p.time_played_seconds) > 0
                                THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
                                ELSE 0
                            END as weighted_dpm,
                            SUM(p.kills) as total_kills,
                            COUNT(DISTINCT p.session_id) as games,
                            p.player_guid
                        FROM player_comprehensive_stats p
                        GROUP BY p.player_guid
                        HAVING games > 50
                        ORDER BY weighted_dpm DESC
                        LIMIT {players_per_page} OFFSET {offset}
                    '''
                    title = f"🏆 Top Players by DPM (Page {page}/{total_pages})"

                elif stat_type == 'accuracy':
                    query = f'''
                        SELECT 
                            (SELECT player_name FROM player_comprehensive_stats 
                             WHERE player_guid = p.player_guid 
                             GROUP BY player_name 
                             ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                            SUM(w.hits) as total_hits,
                            SUM(w.shots) as total_shots,
                            SUM(p.kills) as total_kills,
                            COUNT(DISTINCT p.session_id) as games,
                            p.player_guid
                        FROM player_comprehensive_stats p
                        JOIN weapon_comprehensive_stats w
                            ON p.session_id = w.session_id
                            AND p.player_guid = w.player_guid
                        GROUP BY p.player_guid
                        HAVING games > 50 AND total_shots > 1000
                        ORDER BY (CAST(total_hits AS FLOAT) / total_shots) DESC
                        LIMIT {players_per_page} OFFSET {offset}
                    '''
                    title = f"🏆 Top Players by Accuracy (Page {page}/{total_pages})"

                elif stat_type == 'headshots':
                    query = f'''
                        SELECT 
                            (SELECT player_name FROM player_comprehensive_stats 
                             WHERE player_guid = p.player_guid 
                             GROUP BY player_name 
                             ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                            SUM(p.headshot_kills) as total_hs,
                            SUM(w.hits) as total_hits,
                            SUM(p.kills) as total_kills,
                            COUNT(DISTINCT p.session_id) as games,
                            p.player_guid
                        FROM player_comprehensive_stats p
                        JOIN weapon_comprehensive_stats w
                            ON p.session_id = w.session_id
                            AND p.player_guid = w.player_guid
                        GROUP BY p.player_guid
                        HAVING games > 50 AND total_hits > 1000
                        ORDER BY (CAST(total_hs AS FLOAT) / total_hits) DESC
                        LIMIT {players_per_page} OFFSET {offset}
                    '''
                    title = f"🏆 Top Players by Headshot % (Page {page}/{total_pages})"

                elif stat_type == 'games':
                    query = f'''
                        SELECT 
                            (SELECT player_name FROM player_comprehensive_stats 
                             WHERE player_guid = p.player_guid 
                             GROUP BY player_name 
                             ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                            COUNT(DISTINCT p.session_id) as games,
                            SUM(p.kills) as total_kills,
                            SUM(p.deaths) as total_deaths,
                            p.player_guid
                        FROM player_comprehensive_stats p
                        GROUP BY p.player_guid
                        ORDER BY games DESC
                        LIMIT {players_per_page} OFFSET {offset}
                    '''
                    title = f"🏆 Most Active Players (Page {page}/{total_pages})"

                elif stat_type == 'revives':
                    query = f'''
                        SELECT 
                            (SELECT player_name FROM player_comprehensive_stats 
                             WHERE player_guid = p.player_guid 
                             GROUP BY player_name 
                             ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                            SUM(p.times_revived) as total_revives,
                            SUM(p.kills) as total_kills,
                            COUNT(DISTINCT p.session_id) as games,
                            p.player_guid
                        FROM player_comprehensive_stats p
                        GROUP BY p.player_guid
                        HAVING games > 10
                        ORDER BY total_revives DESC
                        LIMIT {players_per_page} OFFSET {offset}
                    '''
                    title = f"💉 Top Medics - Teammates Revived (Page {page}/{total_pages})"

                elif stat_type == 'gibs':
                    query = f'''
                        SELECT 
                            (SELECT player_name FROM player_comprehensive_stats 
                             WHERE player_guid = p.player_guid 
                             GROUP BY player_name 
                             ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                            SUM(p.gibs) as total_gibs,
                            SUM(p.kills) as total_kills,
                            COUNT(DISTINCT p.session_id) as games,
                            p.player_guid
                        FROM player_comprehensive_stats p
                        GROUP BY p.player_guid
                        HAVING games > 10
                        ORDER BY total_gibs DESC
                        LIMIT {players_per_page} OFFSET {offset}
                    '''
                    title = f"💀 Top Gibbers (Page {page}/{total_pages})"

                elif stat_type == 'objectives':
                    query = f'''
                        SELECT 
                            (SELECT player_name FROM player_comprehensive_stats 
                             WHERE player_guid = p.player_guid 
                             GROUP BY player_name 
                             ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                            SUM(p.objectives_completed + p.objectives_destroyed + p.objectives_stolen + p.objectives_returned) as total_obj,
                            SUM(p.objectives_completed) as completed,
                            COUNT(DISTINCT p.session_id) as games,
                            p.player_guid
                        FROM player_comprehensive_stats p
                        GROUP BY p.player_guid
                        HAVING games > 10
                        ORDER BY total_obj DESC
                        LIMIT {players_per_page} OFFSET {offset}
                    '''
                    title = f"🎯 Top Objective Players (Page {page}/{total_pages})"

                elif stat_type == 'efficiency':
                    query = f'''
                        SELECT 
                            (SELECT player_name FROM player_comprehensive_stats 
                             WHERE player_guid = p.player_guid 
                             GROUP BY player_name 
                             ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                            AVG(p.efficiency) as avg_eff,
                            SUM(p.kills) as total_kills,
                            COUNT(DISTINCT p.session_id) as games,
                            p.player_guid
                        FROM player_comprehensive_stats p
                        GROUP BY p.player_guid
                        HAVING games > 50
                        ORDER BY avg_eff DESC
                        LIMIT {players_per_page} OFFSET {offset}
                    '''
                    title = f"⚡ Highest Efficiency (Page {page}/{total_pages})"

                elif stat_type == 'teamwork':
                    query = f'''
                        SELECT 
                            (SELECT player_name FROM player_comprehensive_stats 
                             WHERE player_guid = p.player_guid 
                             GROUP BY player_name 
                             ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                            SUM(p.team_damage_given) as total_team_dmg,
                            SUM(p.damage_given) as total_dmg,
                            COUNT(DISTINCT p.session_id) as games,
                            p.player_guid
                        FROM player_comprehensive_stats p
                        GROUP BY p.player_guid
                        HAVING games > 50 AND total_dmg > 0
                        ORDER BY (CAST(total_team_dmg AS FLOAT) / total_dmg) ASC
                        LIMIT {players_per_page} OFFSET {offset}
                    '''
                    title = f"🤝 Best Teamwork (Lowest Team Damage %) (Page {page}/{total_pages})"

                elif stat_type == 'multikills':
                    query = f'''
                        SELECT 
                            (SELECT player_name FROM player_comprehensive_stats 
                             WHERE player_guid = p.player_guid 
                             GROUP BY player_name 
                             ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                            SUM(p.double_kills + p.triple_kills + p.quad_kills + p.multi_kills + p.mega_kills) as total_multi,
                            SUM(p.mega_kills) as megas,
                            COUNT(DISTINCT p.session_id) as games,
                            p.player_guid
                        FROM player_comprehensive_stats p
                        GROUP BY p.player_guid
                        HAVING games > 10
                        ORDER BY total_multi DESC
                        LIMIT {players_per_page} OFFSET {offset}
                    '''
                    title = f"🔥 Most Multikills (Page {page}/{total_pages})"

                elif stat_type == 'grenades':
                    query = f'''
                        SELECT 
                            (SELECT player_name FROM player_comprehensive_stats 
                             WHERE player_guid = w.player_guid 
                             GROUP BY player_name 
                             ORDER BY COUNT(*) DESC LIMIT 1) as primary_name,
                            SUM(w.kills) as total_kills,
                            SUM(w.shots) as total_throws,
                            SUM(w.hits) as total_hits,
                            CASE 
                                WHEN SUM(w.kills) > 0 
                                THEN ROUND(CAST(SUM(w.hits) AS FLOAT) / SUM(w.kills), 2)
                                ELSE 0 
                            END as aoe_ratio,
                            COUNT(DISTINCT w.session_id) as games,
                            w.player_guid
                        FROM weapon_comprehensive_stats w
                        WHERE w.weapon_name = 'WS_GRENADE'
                        GROUP BY w.player_guid
                        HAVING games > 10
                        ORDER BY total_kills DESC
                        LIMIT {players_per_page} OFFSET {offset}
                    '''
                    title = f"💣 Top Grenadiers - AOE Masters (Page {page}/{total_pages})"

                async with db.execute(query) as cursor:
                    results = await cursor.fetchall()

            if not results:
                await ctx.send(f"❌ No data found for leaderboard type: {stat_type}")
                return

            # Build embed
            embed = discord.Embed(
                title=title, color=0xFFD700, timestamp=datetime.now()  # Gold color
            )

            # Format results based on stat type
            leaderboard_text = ""
            medals = ["🥇", "🥈", "🥉"]

            for i, row in enumerate(results):
                # Calculate actual rank (based on page)
                rank = offset + i + 1
                
                # Use medal for top 3 overall, otherwise show rank number
                if rank <= 3:
                    medal = medals[rank - 1]
                else:
                    medal = f"{rank}."
                
                name = row[0]
                
                # Add dev badge for ciril (bot developer)
                player_guid = row[-1]  # GUID is always last column
                if player_guid == 'E587CA5F':
                    name = f"{name} 👑"  # Crown emoji for dev

                if stat_type == 'kills':
                    kills, deaths, games = row[1], row[2], row[3]
                    kd = kills / deaths if deaths > 0 else kills
                    leaderboard_text += f"{medal} **{name}** - {kills:,}K ({kd:.2f} K/D, {games} games)\n"

                elif stat_type == 'kd':
                    kills, deaths, games = row[1], row[2], row[3]
                    kd = kills / deaths if deaths > 0 else kills
                    leaderboard_text += f"{medal} **{name}** - {kd:.2f} K/D ({kills:,}K/{deaths:,}D, {games} games)\n"

                elif stat_type == 'dpm':
                    avg_dpm, kills, games = row[1], row[2], row[3]
                    leaderboard_text += f"{medal} **{name}** - {avg_dpm:.1f} DPM ({kills:,}K, {games} games)\n"

                elif stat_type == 'accuracy':
                    hits, shots, kills, games = row[1], row[2], row[3], row[4]
                    acc = (hits / shots * 100) if shots > 0 else 0
                    leaderboard_text += f"{medal} **{name}** - {acc:.1f}% Acc ({kills:,}K, {games} games)\n"

                elif stat_type == 'headshots':
                    hs, hits, kills, games = row[1], row[2], row[3], row[4]
                    hs_pct = (hs / hits * 100) if hits > 0 else 0
                    leaderboard_text += f"{medal} **{name}** - {hs_pct:.1f}% HS ({hs:,} HS, {games} games)\n"

                elif stat_type == 'games':
                    games, kills, deaths = row[1], row[2], row[3]
                    kd = kills / deaths if deaths > 0 else kills
                    leaderboard_text += f"{medal} **{name}** - {games:,} games ({kills:,}K, {kd:.2f} K/D)\n"

                elif stat_type == 'revives':
                    revives, kills, games = row[1], row[2], row[3]
                    leaderboard_text += f"{medal} **{name}** - {revives:,} teammates revived ({kills:,}K, {games} games)\n"

                elif stat_type == 'gibs':
                    gibs, kills, games = row[1], row[2], row[3]
                    leaderboard_text += f"{medal} **{name}** - {gibs:,} gibs ({kills:,}K, {games} games)\n"

                elif stat_type == 'objectives':
                    total_obj, completed, games = row[1], row[2], row[3]
                    leaderboard_text += f"{medal} **{name}** - {total_obj:,} objectives ({completed} completed, {games} games)\n"

                elif stat_type == 'efficiency':
                    avg_eff, kills, games = row[1], row[2], row[3]
                    leaderboard_text += f"{medal} **{name}** - {avg_eff:.1f} efficiency ({kills:,}K, {games} games)\n"

                elif stat_type == 'teamwork':
                    team_dmg, total_dmg, games = row[1], row[2], row[3]
                    team_pct = (team_dmg / total_dmg * 100) if total_dmg > 0 else 0
                    leaderboard_text += f"{medal} **{name}** - {team_pct:.2f}% team damage ({games} games)\n"

                elif stat_type == 'multikills':
                    total_multi, megas, games = row[1], row[2], row[3]
                    leaderboard_text += f"{medal} **{name}** - {total_multi:,} multikills ({megas} mega, {games} games)\n"

                elif stat_type == 'grenades':
                    kills, throws, hits, aoe_ratio, games = row[1], row[2], row[3], row[4], row[5]
                    accuracy = (hits / throws * 100) if throws > 0 else 0
                    aoe_emoji = "🔥" if aoe_ratio >= 3.0 else ""
                    leaderboard_text += f"{medal} **{name}** - {kills:,} kills • {accuracy:.1f}% acc • {aoe_ratio:.2f} AOE {aoe_emoji} ({games} games)\n"

            embed.description = leaderboard_text

            # Add usage footer with pagination info
            if page < total_pages:
                next_page_hint = f" | Next: !lb {stat_type} {page + 1}"
            else:
                next_page_hint = ""
            
            footer_text = f"💡 Use !lb [stat] [page]{next_page_hint}"
            embed.set_footer(text=footer_text)

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in leaderboard command: {e}", exc_info=True)
            await ctx.send(f"❌ Error retrieving leaderboard: {e}")

    @commands.command(name='session', aliases=['match', 'game'])
    async def session(self, ctx, *date_parts):
        """📅 Show detailed session/match statistics for a full day

        Usage:
        - !session 2025-09-30  (show session from specific date)
        - !session 2025 9 30   (alternative format)
        - !session             (show most recent session)
        
        Shows aggregated stats for entire day (all maps/rounds combined).
        """
        try:
            # Parse date from arguments
            if date_parts:
                # Join parts: "2025 9 30" or "2025-09-30"
                date_str = '-'.join(str(p) for p in date_parts)
                # Normalize format: ensure YYYY-MM-DD
                parts = date_str.replace('-', ' ').split()
                if len(parts) >= 3:
                    year, month, day = parts[0], parts[1], parts[2]
                    date_filter = f"{year}-{int(month):02d}-{int(day):02d}"
                else:
                    date_filter = date_str
            else:
                # Get most recent date
                async with aiosqlite.connect(self.bot.db_path) as db:
                    async with db.execute(
                        '''
                        SELECT DISTINCT DATE(session_date) as date
                        FROM player_comprehensive_stats
                        ORDER BY date DESC LIMIT 1
                    '''
                    ) as cursor:
                        result = await cursor.fetchone()
                        if not result:
                            await ctx.send("❌ No sessions found in database")
                            return
                        date_filter = result[0]

            # Now use the same logic as !last_session but for the specified date
            # Just call last_session logic with date filter
            await ctx.send(f"📅 Loading session data for **{date_filter}**...")
            
            # Query aggregated stats for the full day
            async with aiosqlite.connect(self.bot.db_path) as db:
                # Get session metadata
                query = f'''
                    SELECT 
                        COUNT(DISTINCT session_id) / 2 as total_maps,
                        COUNT(DISTINCT session_id) as total_rounds,
                        COUNT(DISTINCT player_guid) as player_count,
                        MIN(session_date) as first_round,
                        MAX(session_date) as last_round
                    FROM player_comprehensive_stats
                    WHERE DATE(session_date) = ?
                '''
                
                async with db.execute(query, (date_filter,)) as cursor:
                    result = await cursor.fetchone()
                    if not result or result[0] == 0:
                        await ctx.send(f"❌ No session found for date: {date_filter}")
                        return
                    
                    total_maps, total_rounds, player_count, first_round, last_round = result
                
                # Get unique maps played
                async with db.execute('''
                    SELECT DISTINCT map_name
                    FROM player_comprehensive_stats
                    WHERE DATE(session_date) = ?
                    ORDER BY session_date
                ''', (date_filter,)) as cursor:
                    maps = await cursor.fetchall()
                    maps_list = [m[0] for m in maps]
                
                # Build header embed
                embed = discord.Embed(
                    title=f"� Session Summary: {date_filter}",
                    description=f"**{int(total_maps)} maps** • **{total_rounds} rounds** • **{player_count} players**",
                    color=0x00FF88
                )
                
                # Add maps played
                maps_text = ", ".join(maps_list)
                if len(maps_text) > 900:
                    maps_text = ", ".join(maps_list[:8]) + f" (+{len(maps_list) - 8} more)"
                embed.add_field(name="🗺️ Maps Played", value=maps_text, inline=False)
                
                # Get top players aggregated
                async with db.execute('''
                    SELECT 
                        p.player_name,
                        SUM(p.kills) as kills,
                        SUM(p.deaths) as deaths,
                        CASE
                            WHEN SUM(p.time_played_seconds) > 0
                            THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
                            ELSE 0
                        END as dpm
                    FROM player_comprehensive_stats p
                    WHERE DATE(p.session_date) = ?
                    GROUP BY p.player_name
                    ORDER BY kills DESC
                    LIMIT 5
                ''', (date_filter,)) as cursor:
                    top_players = await cursor.fetchall()
                
                # Add top 5 players
                if top_players:
                    player_text = ""
                    medals = ["🥇", "🥈", "🥉", "4.", "5."]
                    for i, (name, kills, deaths, dpm) in enumerate(top_players):
                        kd = kills / deaths if deaths > 0 else kills
                        player_text += f"{medals[i]} **{name}** - {kills}K/{deaths}D ({kd:.2f} KD, {dpm:.0f} DPM)\n"
                    embed.add_field(name="🏆 Top Players", value=player_text, inline=False)
                
                embed.set_footer(text="💡 Use !last_session for the most recent session with full details")
                await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in session command: {e}", exc_info=True)
            await ctx.send(f"❌ Error retrieving session: {e}")

    @commands.command(name='last_session', aliases=['last', 'latest', 'recent'])
    async def last_session(self, ctx):
        """🎮 Show the most recent session/match

        Displays detailed stats for the latest played session (full day).
        A session = one day of gaming with all maps/rounds.
        """
        try:
            async with aiosqlite.connect(self.bot.db_path) as db:
                # Get the most recent date (using SUBSTR to handle both "2025-10-02" and "2025-10-02-221711" formats)
                async with db.execute(
                    '''
                    SELECT DISTINCT SUBSTR(session_date, 1, 10) as date
                    FROM sessions
                    ORDER BY date DESC
                    LIMIT 1
                '''
                ) as cursor:
                    result = await cursor.fetchone()

                if not result:
                    await ctx.send("❌ No sessions found in database")
                    return

                latest_date = result[0]

                # Get all session IDs for this date (chronologically)
                async with db.execute(
                    '''
                    SELECT id, map_name, round_number, actual_time
                    FROM sessions
                    WHERE SUBSTR(session_date, 1, 10) = ?
                    ORDER BY id ASC
                ''',
                    (latest_date,),
                ) as cursor:
                    sessions = await cursor.fetchall()

                if not sessions:
                    await ctx.send("❌ No sessions found for latest date")
                    return

                session_ids = [s[0] for s in sessions]
                session_ids_str = ','.join('?' * len(session_ids))

                # Get unique player count across all sessions
                query = f'''
                    SELECT COUNT(DISTINCT player_guid)
                    FROM player_comprehensive_stats
                    WHERE session_id IN ({session_ids_str})
                '''
                async with db.execute(query, session_ids) as cursor:
                    player_count = (await cursor.fetchone())[0]

                # Get ALL players (aggregated across all rounds)
                # Calculate WEIGHTED DPM using actual playtime per round
                query = f'''
                    SELECT p.player_name,
                           SUM(p.kills) as kills,
                           SUM(p.deaths) as deaths,
                           CASE
                               WHEN SUM(p.time_played_seconds) > 0
                               THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
                               ELSE 0
                           END as weighted_dpm,
                           COALESCE(SUM(w.hits), 0) as total_hits,
                           COALESCE(SUM(w.shots), 0) as total_shots,
                           COALESCE(SUM(w.headshots), 0) as total_headshots,
                           SUM(p.headshot_kills) as headshot_kills,
                           SUM(p.time_played_seconds) as total_seconds,
                           CAST(SUM(p.time_played_seconds * p.time_dead_ratio / 100.0) AS INTEGER) as total_time_dead
                    FROM player_comprehensive_stats p
                    LEFT JOIN (
                        SELECT session_id, player_guid,
                               SUM(hits) as hits,
                               SUM(shots) as shots,
                               SUM(headshots) as headshots
                        FROM weapon_comprehensive_stats
                        WHERE weapon_name NOT IN ('WS_GRENADE', 'WS_SYRINGE', 'WS_DYNAMITE', 'WS_AIRSTRIKE', 'WS_ARTILLERY', 'WS_SATCHEL', 'WS_LANDMINE')
                        GROUP BY session_id, player_guid
                    ) w ON p.session_id = w.session_id AND p.player_guid = w.player_guid
                    WHERE p.session_id IN ({session_ids_str})
                    GROUP BY p.player_name
                    ORDER BY kills DESC
                '''
                async with db.execute(query, session_ids) as cursor:
                    all_players = await cursor.fetchall()

                # Get team stats (aggregated)
                query = f'''
                    SELECT team,
                           SUM(kills) as total_kills,
                           SUM(deaths) as total_deaths,
                           SUM(damage_given) as total_damage
                    FROM player_comprehensive_stats
                    WHERE session_id IN ({session_ids_str})
                    GROUP BY team
                '''
                async with db.execute(query, session_ids) as cursor:
                    team_stats = await cursor.fetchall()

                # Get detailed weapon stats (individual weapons)
                query = f'''
                    SELECT weapon_name,
                           SUM(kills) as total_kills,
                           SUM(deaths) as total_deaths,
                           SUM(hits) as total_hits,
                           SUM(shots) as total_shots,
                           SUM(headshots) as total_headshots
                    FROM weapon_comprehensive_stats
                    WHERE session_id IN ({session_ids_str})
                    GROUP BY weapon_name
                    HAVING total_kills > 0
                    ORDER BY total_kills DESC
                '''
                async with db.execute(query, session_ids) as cursor:
                    await cursor.fetchall()

                # Get per-player weapon mastery
                query = f'''
                    SELECT p.player_name,
                           w.weapon_name,
                           SUM(w.kills) as weapon_kills,
                           SUM(w.hits) as weapon_hits,
                           SUM(w.shots) as weapon_shots,
                           SUM(w.headshots) as weapon_headshots
                    FROM weapon_comprehensive_stats w
                    JOIN player_comprehensive_stats p
                        ON w.session_id = p.session_id
                        AND w.player_guid = p.player_guid
                    WHERE w.session_id IN ({session_ids_str})
                    GROUP BY p.player_name, w.weapon_name
                    HAVING weapon_kills > 0
                    ORDER BY p.player_name, weapon_kills DESC
                '''
                async with db.execute(query, session_ids) as cursor:
                    player_weapons = await cursor.fetchall()

                # Get DPM leaderboard (weighted by actual playtime)
                query = f'''
                    SELECT player_name,
                           CASE
                               WHEN SUM(time_played_seconds) > 0
                               THEN (SUM(damage_given) * 60.0) / SUM(time_played_seconds)
                               ELSE 0
                           END as weighted_dpm,
                           SUM(kills) as total_kills,
                           SUM(deaths) as total_deaths
                    FROM player_comprehensive_stats
                    WHERE session_id IN ({session_ids_str})
                    GROUP BY player_name
                    ORDER BY weighted_dpm DESC
                    LIMIT 10
                '''
                async with db.execute(query, session_ids) as cursor:
                    dpm_leaders = await cursor.fetchall()

                # 🎯 TRY TO GET HARDCODED TEAMS FIRST
                hardcoded_teams = await self.get_hardcoded_teams(db, latest_date)
                
                # 📊 Get total maps and rounds played
                # Query for map and round counts
                # Note: COUNT(map_name) counts all plays, including duplicates
                # Example: If te_escape2 is played twice, it counts as 2 maps
                query = f'''
                    SELECT COUNT(DISTINCT session_id) / 2 as total_maps,
                           COUNT(DISTINCT session_id) as total_rounds
                    FROM player_comprehensive_stats
                    WHERE session_id IN ({session_ids_str})
                '''
                async with db.execute(query, session_ids) as cursor:
                    map_stats = await cursor.fetchone()
                    total_maps = map_stats[0] if map_stats else 0
                    total_rounds = map_stats[1] if map_stats else 0
                
                # 🏆 Calculate team scores (maps won)
                # TODO: Implement dynamic Stopwatch scoring
                # TODO: Store match results in database (new table: match_results)
                # For now, manually set for October 2nd based on detailed analysis
                team_1_score = 0
                team_2_score = 0
                
                if hardcoded_teams and latest_date.startswith('2025-10-02'):
                    # Verified from detailed_round_breakdown.py:
                    # Stopwatch scoring: Winner takes 2 pts (or count as 1 map won)
                    # Team A won: adlernest, delivery, escape2(1), brewdog, braundorf
                    # Team B won: supply, escape2(2), goldrush, frostbite, erdenberg
                    # Result: 5 maps won each = PERFECT TIE
                    team_names_list = list(hardcoded_teams.keys())
                    if len(team_names_list) >= 2:
                        team_1_score = 5  # Team A: 5 maps won
                        team_2_score = 5  # Team B: 5 maps won (TIE!)
                
                if hardcoded_teams:
                    # ✅ We have hardcoded teams! Use them for accurate team tracking
                    logger.info("✅ Using hardcoded teams from session_teams table")
                    
                    # Extract team names and create GUID-to-team mapping
                    team_names_list = list(hardcoded_teams.keys())
                    team_1_name = team_names_list[0] if len(team_names_list) > 0 else 'Team A'
                    team_2_name = team_names_list[1] if len(team_names_list) > 1 else 'Team B'
                    
                    # Create GUID -> team_name mapping
                    guid_to_team = {}
                    for team_name, team_data in hardcoded_teams.items():
                        for guid in team_data['guids']:
                            guid_to_team[guid] = team_name
                    
                    # Get player GUIDs to map names to teams
                    query = f'''
                        SELECT DISTINCT player_name, player_guid
                        FROM player_comprehensive_stats
                        WHERE session_id IN ({session_ids_str})
                    '''
                    async with db.execute(query, session_ids) as cursor:
                        player_guid_map = await cursor.fetchall()
                    
                    # Build name -> team mapping
                    name_to_team = {}
                    for player_name, player_guid in player_guid_map:
                        if player_guid in guid_to_team:
                            name_to_team[player_name] = guid_to_team[player_guid]
                    
                    # Organize players by hardcoded team
                    team_1_players_list = [name for name, team in name_to_team.items() if team == team_1_name]
                    team_2_players_list = [name for name, team in name_to_team.items() if team == team_2_name]
                    
                    # No team swappers when using hardcoded teams (they stay consistent)
                    team_swappers = {}
                    player_teams = {name: [(team, 1)] for name, team in name_to_team.items()}
                    
                else:
                    # ❌ No hardcoded teams - fall back to old Axis/Allies detection
                    logger.info("⚠️  No hardcoded teams found, using Axis/Allies (may be inaccurate)")
                    
                    # Get team composition - who played for which team
                    query = f'''
                        SELECT player_name, team, COUNT(*) as rounds_played
                        FROM player_comprehensive_stats
                        WHERE session_id IN ({session_ids_str})
                        GROUP BY player_name, team
                        ORDER BY player_name, rounds_played DESC
                    '''
                    async with db.execute(query, session_ids) as cursor:
                        team_composition = await cursor.fetchall()

                    # Assign random team names
                    import random

                    team_name_pool = ['puran', 'insAne', 'sWat', 'maDdogs', 'slomix', 'slo']

                    # Get all unique players and their primary team
                    player_primary_teams = {}
                    for player, team, rounds in team_composition:
                        if player not in player_primary_teams:
                            player_primary_teams[player] = team

                    # Separate players by team
                    team_1_players_list = [p for p, t in player_primary_teams.items() if t == 1]
                    team_2_players_list = [p for p, t in player_primary_teams.items() if t == 2]

                    # Randomly assign team names
                    random.shuffle(team_name_pool)
                    team_1_name = team_name_pool[0] if team_name_pool else 'Team 1'
                    team_2_name = team_name_pool[1] if len(team_name_pool) > 1 else 'Team 2'

                    # Detect team swaps - players who played for multiple teams
                    player_teams = {}
                    for player, team, rounds in team_composition:
                        if player not in player_teams:
                            player_teams[player] = []
                        player_teams[player].append((team, rounds))

                    team_swappers = {
                        player: teams for player, teams in player_teams.items() if len(teams) > 1
                    }

                # 🎯 GET MVP PER TEAM (using hardcoded teams if available)
                team_mvps = {}
                
                if hardcoded_teams:
                    # ✅ Calculate MVP per hardcoded team (by GUID)
                    for team_name, team_data in hardcoded_teams.items():
                        team_guids = team_data['guids']
                        team_guids_placeholders = ','.join('?' * len(team_guids))
                        
                        query = f'''
                            SELECT player_name, SUM(kills) as total_kills, player_guid
                            FROM player_comprehensive_stats
                            WHERE session_id IN ({session_ids_str})
                            AND player_guid IN ({team_guids_placeholders})
                            GROUP BY player_name, player_guid
                            ORDER BY total_kills DESC
                            LIMIT 1
                        '''
                        params = session_ids + team_guids
                        async with db.execute(query, params) as cursor:
                            result = await cursor.fetchone()
                            if result:
                                player_name, kills, guid = result
                                team_mvps[team_name] = (player_name, kills)
                else:
                    # ❌ Fall back to old Axis/Allies MVP calculation
                    query = f'''
                        SELECT team, player_name, SUM(kills) as total_kills
                        FROM player_comprehensive_stats
                        WHERE session_id IN ({session_ids_str})
                        GROUP BY team, player_name
                        ORDER BY team, total_kills DESC
                    '''
                    async with db.execute(query, session_ids) as cursor:
                        team_mvps_raw = await cursor.fetchall()

                    # Get top player per team
                    for team, player, kills in team_mvps_raw:
                        if team not in team_mvps:
                            team_mvps[team] = (player, kills)

                # 🎯 GET DETAILED MVP STATS (using hardcoded teams if available)
                team_1_mvp_stats = None
                team_2_mvp_stats = None

                if hardcoded_teams:
                    # ✅ Get MVP stats for hardcoded teams
                    for team_name in [team_1_name, team_2_name]:
                        if team_name in team_mvps:
                            player, kills = team_mvps[team_name]
                            team_guids = hardcoded_teams[team_name]['guids']
                            team_guids_placeholders = ','.join('?' * len(team_guids))
                            
                            query = f'''
                                SELECT
                                    CASE
                                        WHEN SUM(time_played_seconds) > 0
                                        THEN (SUM(damage_given) * 60.0) / SUM(time_played_seconds)
                                        ELSE 0
                                    END as weighted_dpm,
                                    SUM(deaths),
                                    SUM(times_revived),
                                    SUM(gibs)
                                FROM player_comprehensive_stats
                                WHERE session_id IN ({session_ids_str})
                                AND player_name = ?
                                AND player_guid IN ({team_guids_placeholders})
                            '''
                            params = session_ids + [player] + team_guids
                            async with db.execute(query, params) as cursor:
                                result = await cursor.fetchone()
                                if result:
                                    mvp_stats = (player, kills, result[0], result[1], result[2], result[3])
                                    if team_name == team_1_name:
                                        team_1_mvp_stats = mvp_stats
                                    else:
                                        team_2_mvp_stats = mvp_stats
                else:
                    # ❌ Fall back to old Axis/Allies MVP stats
                    if 1 in team_mvps:
                        player, kills = team_mvps[1]
                        query = f'''
                            SELECT
                                CASE
                                    WHEN SUM(time_played_seconds) > 0
                                    THEN (SUM(damage_given) * 60.0) / SUM(time_played_seconds)
                                    ELSE 0
                                END as weighted_dpm,
                                SUM(deaths),
                                SUM(times_revived),
                                SUM(gibs)
                            FROM player_comprehensive_stats
                            WHERE session_id IN ({session_ids_str})
                            AND player_name = ? AND team = 1
                        '''
                        async with db.execute(query, session_ids + [player]) as cursor:
                            result = await cursor.fetchone()
                            if result:
                                team_1_mvp_stats = (
                                    player,
                                    kills,
                                    result[0],
                                    result[1],
                                    result[2],
                                    result[3],
                                )

                    if 2 in team_mvps:
                        player, kills = team_mvps[2]
                        query = f'''
                            SELECT
                                CASE
                                    WHEN SUM(time_played_seconds) > 0
                                    THEN (SUM(damage_given) * 60.0) / SUM(time_played_seconds)
                                    ELSE 0
                                END as weighted_dpm,
                                SUM(deaths),
                                SUM(times_revived),
                                SUM(gibs)
                            FROM player_comprehensive_stats
                            WHERE session_id IN ({session_ids_str})
                            AND player_name = ? AND team = 2
                        '''
                        async with db.execute(query, session_ids + [player]) as cursor:
                            result = await cursor.fetchone()
                            if result:
                                team_2_mvp_stats = (
                                    player,
                                    kills,
                                    result[0],
                                    result[1],
                                    result[2],
                                    result[3],
                                )

                # Count rounds won by each team (winners determined by session data)
                # For now, we'll count based on team performance
                # This is a simplified version - you might want to track actual round winners
                axis_rounds = sum(1 for s in sessions if s[2] % 2 == 1)  # Odd rounds
                allies_rounds = sum(1 for s in sessions if s[2] % 2 == 0)  # Even rounds

                # Fetch awards/objective stats data (MUST BE BEFORE CONNECTION CLOSES)
                query = f'''
                    SELECT clean_name, xp, kill_assists, objectives_stolen, objectives_returned,
                           dynamites_planted, dynamites_defused, times_revived,
                           double_kills, triple_kills, quad_kills, multi_kills, mega_kills,
                           denied_playtime, most_useful_kills, useless_kills, gibs,
                           killing_spree_best, death_spree_worst
                    FROM player_comprehensive_stats
                    WHERE session_id IN ({session_ids_str})
                '''
                async with db.execute(query, session_ids) as cursor:
                    awards_data = await cursor.fetchall()

                # Fetch player revives for weapon mastery embed
                query = f'''
                    SELECT player_name, SUM(times_revived) as revives
                    FROM player_comprehensive_stats
                    WHERE session_id IN ({session_ids_str})
                    GROUP BY player_name
                '''
                async with db.execute(query, session_ids) as cursor:
                    player_revives_raw = await cursor.fetchall()

                # Fetch per-map breakdown data for Graph 3
                query = f'''
                    SELECT
                        s.map_name,
                        p.clean_name,
                        SUM(p.kills) as kills,
                        SUM(p.deaths) as deaths,
                        AVG(p.dpm) as avg_dpm
                    FROM player_comprehensive_stats p
                    JOIN sessions s ON p.session_id = s.id
                    WHERE p.session_id IN ({session_ids_str})
                    GROUP BY s.map_name, p.clean_name
                    ORDER BY s.map_name, kills DESC
                '''
                async with db.execute(query, session_ids) as cursor:
                    per_map_data = await cursor.fetchall()

                # Fetch additional stats for Graph 2 (Revives, Gibs, Useful Kills)
                query = f'''
                    SELECT
                        clean_name,
                        SUM(revives_given) as total_revives,
                        SUM(gibs) as total_gibs,
                        SUM(most_useful_kills) as total_useful_kills,
                        SUM(damage_given) as total_damage
                    FROM player_comprehensive_stats
                    WHERE session_id IN ({session_ids_str})
                    GROUP BY clean_name
                    ORDER BY total_damage DESC
                    LIMIT 6
                '''
                async with db.execute(query, session_ids) as cursor:
                    advanced_graph_data = await cursor.fetchall()

                # Fetch chaos/awards stats (teamkills, self-kills, efficiency, etc)
                query = f'''
                    SELECT
                        clean_name,
                        SUM(team_kills) as total_teamkills,
                        SUM(self_kills) as total_selfkills,
                        SUM(kill_steals) as total_steals,
                        SUM(bullets_fired) as total_bullets,
                        SUM(kills) as total_kills,
                        SUM(deaths) as total_deaths,
                        SUM(damage_given) as total_dmg_given,
                        SUM(damage_received) as total_dmg_received,
                        SUM(constructions) as total_constructions,
                        SUM(tank_meatshield) as total_tank,
                        SUM(useless_kills) as total_useless_kills,
                        MAX(death_spree_worst) as worst_death_spree,
                        SUM(time_played_seconds) as total_time
                    FROM player_comprehensive_stats
                    WHERE session_id IN ({session_ids_str})
                    GROUP BY clean_name
                '''
                async with db.execute(query, session_ids) as cursor:
                    chaos_awards_data = await cursor.fetchall()

            # ═══════════════════════════════════════════════════════
            # All database queries complete - connection closed
            # Now build and send embeds
            # ═══════════════════════════════════════════════════════

            # ═══════════════════════════════════════════════════════
            # MESSAGE 1: Session Overview
            # ═══════════════════════════════════════════════════════
            # Use total_maps from earlier query (counts te_escape2 twice if played twice)
            maps_played = total_maps  # This correctly counts duplicate maps
            rounds_played = len(sessions)

            embed1 = discord.Embed(
                title=f"📊 Session Summary: {latest_date}",
                description=(
                    f"**{maps_played} maps** • **{rounds_played} rounds** • "
                    f"**{player_count} players**"
                ),
                color=0x5865F2,
                timestamp=datetime.now(),
            )

            # Maps list - count ALL round 2 completions for each map
            maps_text = ""
            map_play_counts = {}
            for session_id, map_name, round_num, actual_time in sessions:
                # Count EVERY time we see round 2 (completes a 2-round map play)
                if round_num == 2:
                    map_play_counts[map_name] = map_play_counts.get(map_name, 0) + 1

            for map_name, plays in map_play_counts.items():
                rounds = plays * 2
                maps_text += f"• **{map_name}** ({rounds} rounds)\n"

            if maps_text:
                embed1.add_field(name="🗺️ Maps Played", value=maps_text, inline=False)

            # All players on embed1
            if all_players:
                top_text = ""
                medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
                for i, player in enumerate(all_players):
                    name, kills, deaths, dpm, hits, shots = player[0:6]
                    total_hs, hsk, total_seconds, total_time_dead = player[6:10]

                    # Handle NULL values from database
                    kills = kills or 0
                    deaths = deaths or 0
                    dpm = dpm or 0
                    hits = hits or 0
                    shots = shots or 0
                    total_hs = total_hs or 0
                    hsk = hsk or 0
                    total_seconds = total_seconds or 0

                    # Convert seconds to MM:SS format
                    minutes = int(total_seconds // 60)
                    seconds = int(total_seconds % 60)
                    time_display = f"{minutes}:{seconds:02d}"

                    # Calculate time dead
                    time_dead_seconds = int(total_time_dead or 0)
                    dead_minutes = int(time_dead_seconds // 60)
                    dead_seconds = int(time_dead_seconds % 60)
                    time_dead_display = f"{dead_minutes}:{dead_seconds:02d}"

                    # Calculate metrics
                    kd_ratio = kills / deaths if deaths > 0 else kills
                    acc = (hits / shots * 100) if shots and shots > 0 else 0
                    # HSK rate = headshot kills / total kills
                    hsk_rate = (hsk / kills * 100) if kills and kills > 0 else 0
                    # HS rate = headshots / hits
                    hs_rate = (total_hs / hits * 100) if hits and hits > 0 else 0

                    medal = medals[i] if i < len(medals) else f"{i + 1}."
                    top_text += f"{medal} **{name}**\n"
                    # Line 1: Core combat stats
                    top_text += (
                        f"`{kills}K/{deaths}D ({kd_ratio:.2f})` • "
                        f"`{dpm:.0f} DPM` • "
                        f"`{acc:.1f}% ACC ({hits}/{shots})`\n"
                    )
                    # Line 2: Advanced stats with time alive and time dead
                    top_text += (
                        f"`{hsk} HSK ({hsk_rate:.1f}%)` • "
                        f"`{total_hs} HS ({hs_rate:.1f}%)` • "
                        f"⏱️ `{time_display}` • 💀 `{time_dead_display}`\n\n"
                    )

                embed1.add_field(name="🏆 All Players", value=top_text.rstrip(), inline=False)

            embed1.set_footer(text=f"Session: {latest_date}")
            await ctx.send(embed=embed1)
            await asyncio.sleep(2)  # Rate limit protection

            # ═══════════════════════════════════════════════════════
            # GENERATE BEAUTIFUL SESSION OVERVIEW IMAGE
            # ═══════════════════════════════════════════════════════
            try:
                from image_generator import StatsImageGenerator

                generator = StatsImageGenerator()

                # Prepare session data
                session_info = {
                    'date': latest_date,
                    'maps': maps_played,
                    'rounds': rounds_played,
                    'players': player_count,
                }

                # Prepare all players data (use top 5 for image)
                top_players_data = []
                for player in all_players[:5]:
                    name, kills, deaths, dpm, hits, shots = player[0:6]
                    total_hs, hsk, total_seconds, total_time_dead = player[6:10]

                    kd_ratio = kills / deaths if deaths and deaths > 0 else (kills or 0)
                    acc = (hits / shots * 100) if shots and shots > 0 else 0
                    hsk_rate = (hsk / kills * 100) if kills and kills > 0 else 0
                    hs_rate = (total_hs / hits * 100) if hits and hits > 0 else 0

                    # Convert seconds to minutes for playtime display
                    playtime_minutes = (total_seconds or 0) / 60.0

                    top_players_data.append(
                        {
                            'name': name,
                            'kills': kills,
                            'deaths': deaths,
                            'kd': kd_ratio,
                            'dpm': dpm,
                            'acc': acc,
                            'hits': hits,
                            'shots': shots,
                            'hsk': hsk,
                            'hsk_rate': hsk_rate,
                            'hs': total_hs,
                            'hs_rate': hs_rate,
                            'playtime': playtime_minutes,
                        }
                    )

                # Prepare team data for image
                team_data_for_img = {'team1': {}, 'team2': {}}

                for team, kills, deaths, damage in team_stats:
                    kd = kills / deaths if deaths > 0 else kills
                    team_info = {'kills': kills, 'deaths': deaths, 'kd': kd, 'damage': damage}

                    if team == 1:
                        team_data_for_img['team1'] = team_info
                        if team_1_mvp_stats:
                            p, k, dpm, d, revived, gibs = team_1_mvp_stats
                            team_data_for_img['team1']['mvp'] = {
                                'name': p,
                                'kd': k / d if d else k,
                                'dpm': dpm,
                            }
                    elif team == 2:
                        team_data_for_img['team2'] = team_info
                        if team_2_mvp_stats:
                            p, k, dpm, d, revived, gibs = team_2_mvp_stats
                            team_data_for_img['team2']['mvp'] = {
                                'name': p,
                                'kd': k / d if d else k,
                                'dpm': dpm,
                            }

                # Generate the beautiful image!
                img_buf = generator.create_session_overview(
                    session_info, top_players_data, team_data_for_img, (team_1_name, team_2_name)
                )

                file = discord.File(img_buf, filename='session_overview.png')
                await ctx.send("🎨 **Session Overview**", file=file)

            except Exception as e:
                logger.error(f"Error generating session image: {e}", exc_info=True)

            # ═══════════════════════════════════════════════════════
            # MESSAGE 2: Team Analytics
            # ═══════════════════════════════════════════════════════
            # Build description with match score if available
            analytics_desc = "Comprehensive team performance comparison"
            if hardcoded_teams and team_1_score + team_2_score > 0:
                if team_1_score == team_2_score:
                    analytics_desc += f"\n\n🤝 **Maps Won: {team_1_score} - {team_2_score} (PERFECT TIE)**"
                else:
                    analytics_desc += f"\n\n🏆 **Maps Won: {team_1_score} - {team_2_score}**"
            
            embed2 = discord.Embed(
                title=f"⚔️ Team Analytics - {team_1_name} vs {team_2_name}",
                description=analytics_desc,
                color=0xED4245,
                timestamp=datetime.now(),
            )

            # Team stats - separate fields for each team for better readability
            if len(team_stats) > 1:
                for team, kills, deaths, damage in team_stats:
                    if team == 1:
                        current_team_name = team_1_name
                        emoji = "🔴"
                    elif team == 2:
                        current_team_name = team_2_name
                        emoji = "🔵"
                    else:
                        continue

                    kd_ratio = kills / deaths if deaths > 0 else kills

                    team_text = (
                        f"**Total Kills:** `{kills:,}`\n"
                        f"**Total Deaths:** `{deaths:,}`\n"
                        f"**K/D Ratio:** `{kd_ratio:.2f}`\n"
                        f"**Total Damage:** `{damage:,}`\n"
                    )

                    embed2.add_field(
                        name=f"{emoji} {current_team_name} Team Stats", value=team_text, inline=True
                    )

            # Team MVPs (using pre-fetched stats)
            if team_1_mvp_stats:
                player, kills, dpm, deaths, revives, gibs = team_1_mvp_stats
                kd = kills / deaths if deaths else kills
                team_1_mvp_text = (
                    f"**{player}**\n"
                    f"💀 `{kd:.1f} K/D` ({kills}K/{deaths}D)\n"
                    f"💥 `{dpm:.0f} DPM`\n"
                    f"💉 `{revives} Teammates Revived` • 🦴 `{gibs} Gibs`"
                )
                embed2.add_field(name=f"🔴 {team_1_name} MVP", value=team_1_mvp_text, inline=True)

            if team_2_mvp_stats:
                player, kills, dpm, deaths, revives, gibs = team_2_mvp_stats
                kd = kills / deaths if deaths else kills
                team_2_mvp_text = (
                    f"**{player}**\n"
                    f"💀 `{kd:.1f} K/D` ({kills}K/{deaths}D)\n"
                    f"💥 `{dpm:.0f} DPM`\n"
                    f"💉 `{revives} Teammates Revived` • 🦴 `{gibs} Gibs`"
                )
                embed2.add_field(name=f"🔵 {team_2_name} MVP", value=team_2_mvp_text, inline=True)

            embed2.set_footer(text=f"Session: {latest_date}")
            await ctx.send(embed=embed2)
            await asyncio.sleep(4)  # Rate limit protection

            # ═══════════════════════════════════════════════════════
            # MESSAGE 3: Team Composition
            # ═══════════════════════════════════════════════════════
            embed3 = discord.Embed(
                title="👥 Team Composition",
                description=(
                    f"Player roster for {team_1_name} vs {team_2_name}\n"
                    f"🔄 indicates players who swapped teams during session"
                ),
                color=0x57F287,
                timestamp=datetime.now(),
            )

            # 🎯 Organize players by team (using hardcoded teams if available)
            team_1_players = []
            team_2_players = []

            if hardcoded_teams:
                # ✅ Use hardcoded team assignments
                team_1_players = [(name, 1, False) for name in team_1_players_list]
                team_2_players = [(name, 1, False) for name in team_2_players_list]
            else:
                # ❌ Fall back to Axis/Allies grouping
                for player, teams in player_teams.items():
                    primary_team, primary_rounds = teams[0]

                    if primary_team == 1:
                        team_1_players.append((player, primary_rounds, len(teams) > 1))
                    elif primary_team == 2:
                        team_2_players.append((player, primary_rounds, len(teams) > 1))

                team_1_players.sort(key=lambda x: x[1], reverse=True)
                team_2_players.sort(key=lambda x: x[1], reverse=True)

            # Team 1 roster
            if team_1_players:
                team_1_text = f"**{len(team_1_players)} players**\n\n"
                for i, (player, rounds, swapped) in enumerate(team_1_players[:15], 1):
                    swap_indicator = " 🔄" if swapped else ""
                    team_1_text += f"{i}. {player}{swap_indicator}\n"
                if len(team_1_players) > 15:
                    more_count = len(team_1_players) - 15
                    team_1_text += f"\n*...and {more_count} more*"
                embed3.add_field(
                    name=f"🔴 {team_1_name} Roster", value=team_1_text.rstrip(), inline=True
                )

            # Team 2 roster
            if team_2_players:
                team_2_text = f"**{len(team_2_players)} players**\n\n"
                for i, (player, rounds, swapped) in enumerate(team_2_players[:15], 1):
                    swap_indicator = " 🔄" if swapped else ""
                    team_2_text += f"{i}. {player}{swap_indicator}\n"
                if len(team_2_players) > 15:
                    more_count = len(team_2_players) - 15
                    team_2_text += f"\n*...and {more_count} more*"
                embed3.add_field(
                    name=f"🔵 {team_2_name} Roster", value=team_2_text.rstrip(), inline=True
                )

            # Team swaps (only show if NOT using hardcoded teams OR if actual swaps detected)
            if team_swappers and not hardcoded_teams:
                swap_text = ""
                for player, teams in list(team_swappers.items())[:10]:
                    team_names = []
                    for team, rounds in teams:
                        if team == 1:
                            team_names.append(f"🔴({rounds}r)")
                        elif team == 2:
                            team_names.append(f"🔵({rounds}r)")
                    swap_text += f"• **{player}**: {' → '.join(team_names)}\n"
                embed3.add_field(name="🔄 Team Swaps", value=swap_text.rstrip(), inline=False)
            elif hardcoded_teams and not team_swappers:
                # Show confirmation that no swaps occurred
                embed3.add_field(
                    name="✅ Team Consistency",
                    value="No mid-session player swaps detected",
                    inline=False
                )
            
            # 📊 Add session statistics with match score
            # Note: total_maps already calculated correctly (counts duplicates)
            unique_map_names = len(set(s[1] for s in sessions))
            session_info = f"📍 **{total_rounds} rounds** played ({total_maps} maps)\n"
            session_info += f"🎮 **Format**: Stopwatch (2 rounds per map)\n"
            session_info += f"🗺️ **Unique map names**: {unique_map_names}\n"
            
            # Add match score if we have hardcoded teams
            if hardcoded_teams and team_1_score + team_2_score > 0:
                if team_1_score == team_2_score:
                    session_info += f"\n🤝 **Maps Won**: {team_1_name} {team_1_score} - {team_2_score} {team_2_name} (TIE)"
                else:
                    session_info += f"\n🏆 **Maps Won**: {team_1_name} {team_1_score} - {team_2_score} {team_2_name}"
            
            embed3.add_field(
                name="📊 Session Info",
                value=session_info,
                inline=False
            )

            embed3.set_footer(text=f"Session: {latest_date}")
            await ctx.send(embed=embed3)
            await asyncio.sleep(8)  # Rate limit protection

            # ═══════════════════════════════════════════════════════
            # MESSAGE 4: DPM Analytics
            # ═══════════════════════════════════════════════════════
            embed4 = discord.Embed(
                title="💥 DPM Analytics - Damage Per Minute",
                description="Enhanced DPM with Kill/Death Details",
                color=0xFEE75C,
                timestamp=datetime.now(),
            )

            # DPM Leaderboard with calculation details
            if dpm_leaders:
                dpm_text = ""
                # Get time played for each player to show calculation
                for i, (player, dpm, kills, deaths) in enumerate(dpm_leaders[:10], 1):
                    kd = kills / deaths if deaths else kills
                    dpm_text += f"{i}. **{player}**\n"
                    dpm_text += f"   💥 `{dpm:.0f} DPM` • 💀 `{kd:.1f} K/D` ({kills}K/{deaths}D)\n"

                embed4.add_field(
                    name="🏆 Enhanced DPM Leaderboard", value=dpm_text.rstrip(), inline=False
                )

            # DPM Insights with calculation formula
            if dpm_leaders:
                avg_dpm = sum(p[1] for p in dpm_leaders) / len(dpm_leaders)
                highest_dpm = dpm_leaders[0][1] if dpm_leaders else 0
                leader_name = dpm_leaders[0][0] if dpm_leaders else "N/A"

                insights = (
                    f"📊 **Enhanced Session DPM Stats:**\n"
                    f"• Average DPM: `{avg_dpm:.1f}`\n"
                    f"• Highest DPM: `{highest_dpm:.0f}`\n"
                    f"• DPM Leader: **{leader_name}**\n"
                    f"• Formula: `(Total Damage × 60) / Time Played (seconds)`"
                )
                embed4.add_field(name="💥 DPM Insights", value=insights, inline=False)

            embed4.set_footer(text="💥 Enhanced with Kill/Death Details")
            await ctx.send(embed=embed4)
            await asyncio.sleep(16)  # Rate limit protection

            # ═══════════════════════════════════════════════════════
            # MESSAGE 5: Weapon Mastery Breakdown (Text)
            # ═══════════════════════════════════════════════════════

            # Group by player and get their top weapons
            player_weapon_map = {}
            for player, weapon, kills, hits, shots, hs in player_weapons:
                if player not in player_weapon_map:
                    player_weapon_map[player] = []
                acc = (hits / shots * 100) if shots > 0 else 0
                hs_pct = (hs / hits * 100) if hits > 0 else 0
                weapon_clean = weapon.replace('WS_', '').replace('_', ' ').title()
                player_weapon_map[player].append(
                    (weapon_clean, kills, acc, hs_pct, hs, hits, shots)
                )

            # Convert revives data (already fetched before connection closed)
            player_revives = {player: revives for player, revives in player_revives_raw}

            # Sort players by total kills - SHOW ALL PLAYERS
            player_totals = []
            for player, weapons in player_weapon_map.items():
                total_kills = sum(w[1] for w in weapons)
                player_totals.append((player, total_kills))
            player_totals.sort(key=lambda x: x[1], reverse=True)

            # Create text-based weapon breakdown
            embed5 = discord.Embed(
                title="🔫 Weapon Mastery Breakdown",
                description="Top weapons and combat statistics",
                color=0x5865F2,
                timestamp=datetime.now(),
            )

            # Show ALL players and ALL their weapons (not just top 3)
            for player, total_kills in player_totals:
                weapons = player_weapon_map[player]  # ALL weapons
                revives = player_revives.get(player, 0)

                weapon_text = ""
                for weapon, kills, acc, hs_pct, hs, hits, shots in weapons:
                    weapon_text += f"**{weapon}**: `{kills}K` • `{
                        acc:.1f}% ACC` • `{hs} HS ({
                        hs_pct:.1f}%)`\n"

                # Add revives info
                if revives > 0:
                    weapon_text += f"\n💉 **Teammates Revived**: `{revives}`"

                embed5.add_field(
                    name=f"{player} ({total_kills} total kills)", value=weapon_text, inline=False
                )

            embed5.set_footer(text=f"Session: {latest_date}")
            await ctx.send(embed=embed5)
            await asyncio.sleep(2)

            # ═══════════════════════════════════════════════════════
            # MESSAGE 6: Objective & Support Stats
            # ═══════════════════════════════════════════════════════
            # Use awards_data that was already fetched before connection closed
            if awards_data:
                embed6 = discord.Embed(
                    title="🎯 Objective & Support Stats",
                    description="Comprehensive battlefield contributions",
                    color=0x00D166,
                    timestamp=datetime.now(),
                )

                # Aggregate stats across all rounds per player
                # awards_data format: (clean_name, xp, kill_assists, obj_stolen, obj_returned,
                #                      dyn_planted, dyn_defused, times_revived, double, triple, quad,
                #                      multi, mega, denied_time, useful_kills, useless_kills, gibs,
                #                      best_spree, worst_spree)
                player_objectives = {}
                for row in awards_data:
                    player_name = row[0]
                    if player_name not in player_objectives:
                        player_objectives[player_name] = {
                            'xp': 0,
                            'assists': 0,
                            'obj_stolen': 0,
                            'obj_returned': 0,
                            'dyn_planted': 0,
                            'dyn_defused': 0,
                            'revived': 0,
                            'multi_2x': 0,
                            'multi_3x': 0,
                            'multi_4x': 0,
                            'multi_5x': 0,
                            'multi_6x': 0,
                            'denied_time': 0,
                            'useful_kills': 0,
                            'useless_kills': 0,
                            'gibs': 0,
                            'best_spree': 0,
                            'worst_spree': 0,
                        }

                    # Accumulate stats from each round
                    player_objectives[player_name]['xp'] += row[1] or 0
                    player_objectives[player_name]['assists'] += row[2] or 0
                    player_objectives[player_name]['obj_stolen'] += row[3] or 0
                    player_objectives[player_name]['obj_returned'] += row[4] or 0
                    player_objectives[player_name]['dyn_planted'] += row[5] or 0
                    player_objectives[player_name]['dyn_defused'] += row[6] or 0
                    player_objectives[player_name]['revived'] += row[7] or 0
                    player_objectives[player_name]['multi_2x'] += row[8] or 0
                    player_objectives[player_name]['multi_3x'] += row[9] or 0
                    player_objectives[player_name]['multi_4x'] += row[10] or 0
                    player_objectives[player_name]['multi_5x'] += row[11] or 0
                    player_objectives[player_name]['multi_6x'] += row[12] or 0
                    player_objectives[player_name]['denied_time'] += row[13] or 0
                    player_objectives[player_name]['useful_kills'] += row[14] or 0
                    player_objectives[player_name]['useless_kills'] += row[15] or 0
                    player_objectives[player_name]['gibs'] += row[16] or 0
                    # Track best spree (max) and worst spree (max deaths)
                    player_objectives[player_name]['best_spree'] = max(
                        player_objectives[player_name]['best_spree'], row[17] or 0
                    )
                    player_objectives[player_name]['worst_spree'] = max(
                        player_objectives[player_name]['worst_spree'], row[18] or 0
                    )

                # Sort players by XP and show top 6
                sorted_players = sorted(
                    player_objectives.items(), key=lambda x: x[1]['xp'], reverse=True
                )[:6]

                for i, (player, stats) in enumerate(sorted_players, 1):
                    obj_text = f"**XP:** `{stats['xp']}`\n"
                    obj_text += f"**Assists:** `{stats['assists']}`\n"

                    # Objectives
                    if stats['obj_stolen'] > 0 or stats['obj_returned'] > 0:
                        obj_text += (
                            f"**Objectives:** `{stats['obj_stolen']}/{stats['obj_returned']}` S/R\n"
                        )

                    # Dynamites
                    if stats['dyn_planted'] > 0 or stats['dyn_defused'] > 0:
                        obj_text += (
                            f"**Dynamites:** `{stats['dyn_planted']}/{stats['dyn_defused']}` P/D\n"
                        )

                    # Revived
                    if stats['revived'] > 0:
                        obj_text += f"**Revived:** `{stats['revived']}` times\n"

                    # 🔥 ADVANCED STATS 🔥
                    # Killing spree
                    if stats['best_spree'] >= 3:
                        obj_text += f"🔥 **Best Spree:** `{stats['best_spree']}` kills\n"

                    # Death spree (embarrassing!)
                    if stats['worst_spree'] >= 3:
                        obj_text += f"💀 **Death Spree:** `{stats['worst_spree']}` deaths\n"

                    # Gibs
                    if stats['gibs'] > 0:
                        obj_text += f"🦴 **Gibs:** `{stats['gibs']}`\n"

                    # Useful kills
                    if stats['useful_kills'] > 0:
                        obj_text += f"✅ **Useful Kills:** `{stats['useful_kills']}`\n"

                    # Useless kills (with clown emoji!)
                    if stats['useless_kills'] > 0:
                        obj_text += f"🤡 **Useless Kills:** `{stats['useless_kills']}`\n"

                    # Denied playtime (convert seconds to MM:SS)
                    if stats['denied_time'] > 0:
                        denied_mins = stats['denied_time'] // 60
                        denied_secs = stats['denied_time'] % 60
                        obj_text += f"⏱️ **Enemy Denied:** `{denied_mins}:{denied_secs:02d}`\n"

                    # Multikills with fancy emojis
                    multikills = []
                    if stats['multi_2x'] > 0:
                        multikills.append(f"2️⃣✖️ {stats['multi_2x']}")
                    if stats['multi_3x'] > 0:
                        multikills.append(f"3️⃣✖️ {stats['multi_3x']}")
                    if stats['multi_4x'] > 0:
                        multikills.append(f"4️⃣✖️ {stats['multi_4x']}")
                    if stats['multi_5x'] > 0:
                        multikills.append(f"5️⃣✖️ {stats['multi_5x']}")
                    if stats['multi_6x'] > 0:
                        multikills.append(f"6️⃣✖️ {stats['multi_6x']}")
                    if multikills:
                        obj_text += f"💥 **Multikills:** {' '.join(multikills)}\n"

                    embed6.add_field(name=f"{i}. {player}", value=obj_text.rstrip(), inline=True)

                embed6.set_footer(text="🎯 S/R = Stolen/Returned | P/D = Planted/Defused")
                await ctx.send(embed=embed6)
                await asyncio.sleep(2)  # Rate limit before awards

            # ═══════════════════════════════════════════════════════
            # MESSAGE 7: SPECIAL AWARDS 🏆
            # ═══════════════════════════════════════════════════════
            logger.info("🏆 Calculating Special Awards...")

            # Calculate awards from chaos_awards_data
            awards = {
                'teamkill_king': {'player': None, 'value': 0},
                'selfkill_master': {'player': None, 'value': 0},
                'kill_thief': {'player': None, 'value': 0},
                'spray_pray': {'player': None, 'value': 0},
                'trigger_shy': {'player': None, 'value': 999999},
                'damage_king': {'player': None, 'value': 0},
                'glass_cannon': {'player': None, 'value': 0},
                'engineer': {'player': None, 'value': 0},
                'tank_shield': {'player': None, 'value': 0},
                'respawn_king': {'player': None, 'value': 0},
                'useless_king': {'player': None, 'value': 0},
                'death_magnet': {'player': None, 'value': 0},
                'worst_spree': {'player': None, 'value': 0},
            }

            for row in chaos_awards_data:
                name = row[0]
                teamkills, selfkills, steals, bullets = row[1:5]
                kills, deaths, dmg_given, dmg_received = row[5:9]
                constructions, tank, useless = row[9:12]
                worst_spree, play_time = row[12:14]

                # Teamkill King
                if teamkills > awards['teamkill_king']['value']:
                    awards['teamkill_king'] = {'player': name, 'value': teamkills}

                # Self-Kill Master
                if selfkills > awards['selfkill_master']['value']:
                    awards['selfkill_master'] = {'player': name, 'value': selfkills}

                # Kill Thief
                if steals > awards['kill_thief']['value']:
                    awards['kill_thief'] = {'player': name, 'value': steals}

                # Spray & Pray (most bullets per kill)
                if kills > 0:
                    bpk = bullets / kills
                    if bpk > awards['spray_pray']['value']:
                        awards['spray_pray'] = {'player': name, 'value': bpk}

                # Too Scared to Shoot (fewest bullets, min 5 kills)
                if kills >= 5 and bullets < awards['trigger_shy']['value']:
                    awards['trigger_shy'] = {'player': name, 'value': bullets}

                # Damage Efficiency King (best dmg given/received ratio)
                if dmg_received > 0:
                    eff = dmg_given / dmg_received
                    if eff > awards['damage_king']['value']:
                        awards['damage_king'] = {'player': name, 'value': eff}

                # Glass Cannon (most damage taken)
                if dmg_received > awards['glass_cannon']['value']:
                    awards['glass_cannon'] = {'player': name, 'value': dmg_received}

                # Chief Engineer
                if constructions > awards['engineer']['value']:
                    awards['engineer'] = {'player': name, 'value': constructions}

                # Tank Shield
                if tank > awards['tank_shield']['value']:
                    awards['tank_shield'] = {'player': name, 'value': tank}

                # Respawn King (most deaths)
                if deaths > awards['respawn_king']['value']:
                    awards['respawn_king'] = {'player': name, 'value': deaths}

                # Most Useless Kills
                if useless > awards['useless_king']['value']:
                    awards['useless_king'] = {'player': name, 'value': useless}

                # Death Magnet (most total deaths)
                if deaths > awards['death_magnet']['value']:
                    awards['death_magnet'] = {'player': name, 'value': deaths}

                # Worst Death Spree
                if worst_spree > awards['worst_spree']['value']:
                    awards['worst_spree'] = {'player': name, 'value': worst_spree}

            # Build awards embed
            embed7 = discord.Embed(
                title="🏆 SESSION SPECIAL AWARDS 🏆",
                description="*Celebrating excellence... and chaos!*",
                color=0xFFD700,  # Gold
            )

            awards_text = []

            # Positive awards
            if awards['damage_king']['value'] > 1.5:
                player = awards['damage_king']['player']
                ratio = awards['damage_king']['value']
                awards_text.append(
                    f"💥 **Damage Efficiency King:** `{player}` ({ratio:.2f}x ratio)"
                )

            if awards['engineer']['value'] >= 1:
                player = awards['engineer']['player']
                count = int(awards['engineer']['value'])
                awards_text.append(f"🔧 **Chief Engineer:** `{player}` ({count} repairs)")

            # Funny/Chaos awards
            if awards['teamkill_king']['value'] >= 2:
                player = awards['teamkill_king']['player']
                count = int(awards['teamkill_king']['value'])
                awards_text.append(f"🔥 **Friendly Fire King:** `{player}` ({count} teamkills)")

            if awards['selfkill_master']['value'] >= 3:
                player = awards['selfkill_master']['player']
                count = int(awards['selfkill_master']['value'])
                awards_text.append(f"🤦 **Self-Destruct Master:** `{player}` ({count} self-kills!)")

            if awards['kill_thief']['value'] >= 2:
                player = awards['kill_thief']['player']
                count = int(awards['kill_thief']['value'])
                awards_text.append(f"🥷 **Kill Thief:** `{player}` ({count} steals)")

            if awards['spray_pray']['value'] >= 100:
                player = awards['spray_pray']['player']
                bpk = awards['spray_pray']['value']
                awards_text.append(f"🎯 **Spray & Pray:** `{player}` ({bpk:.0f} bullets/kill)")

            if awards['trigger_shy']['value'] < 999999:
                player = awards['trigger_shy']['player']
                bullets = int(awards['trigger_shy']['value'])
                awards_text.append(
                    f"🙈 **Trigger Discipline:** `{player}` ({bullets} bullets only)"
                )

            if awards['respawn_king']['value'] >= 15:
                player = awards['respawn_king']['player']
                count = int(awards['respawn_king']['value'])
                awards_text.append(f"💀 **Respawn Champion:** `{player}` ({count} deaths)")

            if awards['worst_spree']['value'] >= 5:
                player = awards['worst_spree']['player']
                count = int(awards['worst_spree']['value'])
                awards_text.append(
                    f"⚰️ **Death Spree Record:** `{player}` ({count} deaths in a row)"
                )

            if awards['useless_king']['value'] >= 3:
                player = awards['useless_king']['player']
                count = int(awards['useless_king']['value'])
                awards_text.append(f"🤡 **Most Useless Kills:** `{player}` ({count} useless)")

            if awards['glass_cannon']['value'] >= 1000:
                player = awards['glass_cannon']['player']
                dmg = int(awards['glass_cannon']['value'])
                awards_text.append(f"🩹 **Damage Sponge:** `{player}` ({dmg:,} dmg taken)")

            if awards['tank_shield']['value'] > 0:
                player = awards['tank_shield']['player']
                val = awards['tank_shield']['value']
                awards_text.append(f"🛡️ **Tank Shield:** `{player}` ({val:.1f} tank hits)")

            if awards_text:
                embed7.description = "\n".join(awards_text)
            else:
                embed7.description = "*No notable awards this session*"

            embed7.set_footer(text="🎉 Keep up the good work... or not!")
            await ctx.send(embed=embed7)
            await asyncio.sleep(2)

            # ═══════════════════════════════════════════════════════
            # MESSAGE 8: CHAOS STATS LEADERBOARDS 💀
            # ═══════════════════════════════════════════════════════
            logger.info("💀 Building Chaos Stats Leaderboards...")

            # Sort chaos_awards_data for leaderboards
            teamkill_leaders = sorted(
                [(r[0], r[1]) for r in chaos_awards_data if r[1] > 0],
                key=lambda x: x[1],
                reverse=True,
            )[:3]

            selfkill_leaders = sorted(
                [(r[0], r[2]) for r in chaos_awards_data if r[2] > 0],
                key=lambda x: x[1],
                reverse=True,
            )[:3]

            killsteal_leaders = sorted(
                [(r[0], r[3]) for r in chaos_awards_data if r[3] > 0],
                key=lambda x: x[1],
                reverse=True,
            )[:3]

            useless_leaders = sorted(
                [(r[0], r[12]) for r in chaos_awards_data if r[12] > 0],
                key=lambda x: x[1],
                reverse=True,
            )[:3]

            death_leaders = sorted(
                [(r[0], r[6]) for r in chaos_awards_data if r[6] > 0],
                key=lambda x: x[1],
                reverse=True,
            )[:3]

            embed8 = discord.Embed(
                title="💀 CHAOS & MAYHEM STATS 💀",
                description="*The good, the bad, and the ugly*",
                color=0xFF0000,  # Red
            )

            # Teamkills Leaderboard
            if teamkill_leaders:
                tk_text = "\n".join(
                    [
                        f"{'🥇🥈🥉'[i]} `{name:20s}` - {count} teamkill{'s' if count > 1 else ''}"
                        for i, (name, count) in enumerate(teamkill_leaders)
                    ]
                )
                embed8.add_field(name="🔥 Friendly Fire Leaderboard", value=tk_text, inline=False)

            # Self-Kills Leaderboard
            if selfkill_leaders:
                sk_text = "\n".join(
                    [
                        f"{'🥇🥈🥉'[i]} `{name:20s}` - {count} self-kill{'s' if count > 1 else ''}"
                        for i, (name, count) in enumerate(selfkill_leaders)
                    ]
                )
                embed8.add_field(name="🤦 Self-Destruction Champions", value=sk_text, inline=False)

            # Kill Steals Leaderboard
            if killsteal_leaders:
                ks_text = "\n".join(
                    [
                        f"{'🥇🥈🥉'[i]} `{name:20s}` - {count} steal{'s' if count > 1 else ''}"
                        for i, (name, count) in enumerate(killsteal_leaders)
                    ]
                )
                embed8.add_field(name="🥷 Kill Thieves", value=ks_text, inline=False)

            # Useless Kills Leaderboard
            if useless_leaders:
                ul_text = "\n".join(
                    [
                        f"{'🥇🥈🥉'[i]} `{name:20s}` - {count} useless kill{'s' if count > 1 else ''}"
                        for i, (name, count) in enumerate(useless_leaders)
                    ]
                )
                embed8.add_field(name="🤡 Most Useless Kills", value=ul_text, inline=False)

            # Most Deaths Leaderboard
            if death_leaders:
                dl_text = "\n".join(
                    [
                        f"{'🥇🥈🥉'[i]} `{name:20s}` - {count} death{'s' if count > 1 else ''}"
                        for i, (name, count) in enumerate(death_leaders)
                    ]
                )
                embed8.add_field(
                    name="💀 Respawn Champions (Most Deaths)", value=dl_text, inline=False
                )

            embed8.set_footer(text="😈 Embrace the chaos!")
            await ctx.send(embed=embed8)
            await asyncio.sleep(2)  # Rate limit before graphs

            # ═══════════════════════════════════════════════════════
            # MESSAGE 9: Visual Stats Graph
            # ═══════════════════════════════════════════════════════
            logger.info("🎨 Generating visual performance graphs...")
            try:
                import matplotlib

                matplotlib.use('Agg')  # Non-interactive backend
                import io

                import matplotlib.pyplot as plt

                # Create a figure with 2 subplots
                fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
                fig.patch.set_facecolor('#2b2d31')

                # Get top 6 players for graphs from all_players data
                # all_players is already sorted by kills DESC
                graph_data = []
                for player in all_players[:6]:  # Top 6 players
                    # Unpack player data
                    # Structure: name, kills, deaths, dpm, hits, shots, total_hs, hs_kills,
                    # seconds, time_dead
                    name = player[0]
                    kills = player[1] or 0
                    deaths = player[2] or 0
                    dpm = player[3] or 0
                    hits = player[4] or 0
                    shots = player[5] or 0

                    acc = (hits / shots * 100) if shots > 0 else 0
                    graph_data.append(
                        {
                            'name': name,
                            'kills': kills,
                            'deaths': deaths,
                            'dpm': dpm,
                            'accuracy': acc,
                        }
                    )

                if graph_data:
                    logger.info(f"📊 Graph data prepared for {len(graph_data)} players")
                    names = [d['name'] for d in graph_data]
                    kills_data = [d['kills'] for d in graph_data]
                    deaths_data = [d['deaths'] for d in graph_data]
                    dpm_data = [d['dpm'] for d in graph_data]

                    # Graph 1: Kills vs Deaths vs DPM
                    x = range(len(names))
                    width = 0.25

                    ax1.bar(
                        [i - width for i in x],
                        kills_data,
                        width,
                        label='Kills',
                        color='#5865f2',
                        alpha=0.8,
                    )
                    ax1.bar(x, deaths_data, width, label='Deaths', color='#ed4245', alpha=0.8)
                    ax1.bar(
                        [i + width for i in x],
                        dpm_data,
                        width,
                        label='DPM',
                        color='#fee75c',
                        alpha=0.8,
                    )

                    ax1.set_ylabel('Value', color='white', fontsize=12)
                    ax1.set_title(
                        'Player Performance - Kills, Deaths, DPM',
                        color='white',
                        fontsize=14,
                        fontweight='bold',
                    )
                    ax1.set_xticks(x)
                    ax1.set_xticklabels(names, rotation=15, ha='right', color='white')
                    ax1.legend(facecolor='#1e1f22', edgecolor='white', labelcolor='white')
                    ax1.set_facecolor('#1e1f22')
                    ax1.tick_params(colors='white')
                    ax1.spines['bottom'].set_color('white')
                    ax1.spines['left'].set_color('white')
                    ax1.spines['top'].set_visible(False)
                    ax1.spines['right'].set_visible(False)
                    ax1.grid(True, alpha=0.2, color='white')

                    # Add value labels on bars
                    for i, (k, d, dpm) in enumerate(zip(kills_data, deaths_data, dpm_data)):
                        ax1.text(
                            i - width,
                            k,
                            str(int(k)),
                            ha='center',
                            va='bottom',
                            color='white',
                            fontsize=9,
                        )
                        ax1.text(
                            i, d, str(int(d)), ha='center', va='bottom', color='white', fontsize=9
                        )
                        ax1.text(
                            i + width,
                            dpm,
                            str(int(dpm)),
                            ha='center',
                            va='bottom',
                            color='white',
                            fontsize=9,
                        )

                    # Graph 2: K/D Ratio and Accuracy
                    kd_ratios = [
                        d['kills'] / d['deaths'] if d['deaths'] > 0 else d['kills']
                        for d in graph_data
                    ]
                    accuracy_data = [d['accuracy'] for d in graph_data]

                    ax2_twin = ax2.twinx()

                    bars1 = ax2.bar(
                        [i - width / 2 for i in x],
                        kd_ratios,
                        width,
                        label='K/D Ratio',
                        color='#57f287',
                        alpha=0.8,
                    )
                    bars2 = ax2_twin.bar(
                        [i + width / 2 for i in x],
                        accuracy_data,
                        width,
                        label='Accuracy %',
                        color='#eb459e',
                        alpha=0.8,
                    )

                    ax2.set_ylabel('K/D Ratio', color='white', fontsize=12)
                    ax2_twin.set_ylabel('Accuracy %', color='white', fontsize=12)
                    ax2.set_title(
                        'Player Efficiency - K/D and Accuracy',
                        color='white',
                        fontsize=14,
                        fontweight='bold',
                    )
                    ax2.set_xticks(x)
                    ax2.set_xticklabels(names, rotation=15, ha='right', color='white')

                    # Combine legends
                    lines1, labels1 = ax2.get_legend_handles_labels()
                    lines2, labels2 = ax2_twin.get_legend_handles_labels()
                    ax2.legend(
                        lines1 + lines2,
                        labels1 + labels2,
                        facecolor='#1e1f22',
                        edgecolor='white',
                        labelcolor='white',
                    )

                    ax2.set_facecolor('#1e1f22')
                    ax2.tick_params(colors='white')
                    ax2_twin.tick_params(colors='white')
                    ax2.spines['bottom'].set_color('white')
                    ax2.spines['left'].set_color('white')
                    ax2_twin.spines['right'].set_color('white')
                    ax2.spines['top'].set_visible(False)
                    ax2.grid(True, alpha=0.2, color='white', axis='y')

                    # Add value labels
                    for i, (kd, acc) in enumerate(zip(kd_ratios, accuracy_data)):
                        ax2.text(
                            i - width / 2,
                            kd,
                            f'{kd:.2f}',
                            ha='center',
                            va='bottom',
                            color='white',
                            fontsize=9,
                        )
                        ax2_twin.text(
                            i + width / 2,
                            acc,
                            f'{acc:.1f}%',
                            ha='center',
                            va='bottom',
                            color='white',
                            fontsize=9,
                        )

                    plt.tight_layout()

                    # Save to bytes buffer
                    buf = io.BytesIO()
                    plt.savefig(
                        buf, format='png', facecolor='#2b2d31', dpi=100, bbox_inches='tight'
                    )
                    buf.seek(0)
                    plt.close()

                    # Send as Discord file
                    file = discord.File(buf, filename='session_stats.png')
                    logger.info("📊 Sending Graph 1 to Discord...")
                    await ctx.send("📊 **Visual Performance Analytics - Part 1**", file=file)
                    logger.info("✅ Graph 1 sent successfully!")
                    await asyncio.sleep(1)

                    # ═══════════════════════════════════════════════════════
                    # GRAPH 2: Advanced Combat Stats (Gibs and Damage Only)
                    # NOTE: Revives and Useful Kills disabled - parser not capturing data
                    # ═══════════════════════════════════════════════════════
                    if advanced_graph_data and len(advanced_graph_data) > 0:
                        logger.info("🎨 Generating Graph 2 (Advanced Combat Stats)...")
                        fig2, (ax4, ax6) = plt.subplots(1, 2, figsize=(14, 6))
                        fig2.patch.set_facecolor('#2b2d31')

                        # Extract data (only gibs and damage for now)
                        adv_names = [row[0] for row in advanced_graph_data]
                        gibs = [row[2] or 0 for row in advanced_graph_data]
                        total_damage = [row[4] or 0 for row in advanced_graph_data]

                        x_adv = range(len(adv_names))

                        # Subplot 1: Gibs
                        ax4.barh(x_adv, gibs, color='#ed4245', alpha=0.8)
                        ax4.set_yticks(x_adv)
                        ax4.set_yticklabels(adv_names, color='white')
                        ax4.set_xlabel('Gibs', color='white', fontsize=11)
                        ax4.set_title(
                            '🦴 Gib Masters', color='white', fontsize=12, fontweight='bold'
                        )
                        ax4.set_facecolor('#1e1f22')
                        ax4.tick_params(colors='white')
                        ax4.spines['bottom'].set_color('white')
                        ax4.spines['left'].set_color('white')
                        ax4.spines['top'].set_visible(False)
                        ax4.spines['right'].set_visible(False)
                        ax4.grid(True, alpha=0.2, color='white', axis='x')
                        for i, v in enumerate(gibs):
                            ax4.text(v, i, f' {int(v)}', va='center', color='white', fontsize=9)

                        # Subplot 2: Total Damage
                        ax6.barh(x_adv, total_damage, color='#5865f2', alpha=0.8)
                        ax6.set_yticks(x_adv)
                        ax6.set_yticklabels(adv_names, color='white')
                        ax6.set_xlabel('Total Damage', color='white', fontsize=11)
                        ax6.set_title(
                            '💥 Damage Dealers', color='white', fontsize=12, fontweight='bold'
                        )
                        ax6.set_facecolor('#1e1f22')
                        ax6.tick_params(colors='white')
                        ax6.spines['bottom'].set_color('white')
                        ax6.spines['left'].set_color('white')
                        ax6.spines['top'].set_visible(False)
                        ax6.spines['right'].set_visible(False)
                        ax6.grid(True, alpha=0.2, color='white', axis='x')
                        for i, v in enumerate(total_damage):
                            ax6.text(v, i, f' {int(v)}', va='center', color='white', fontsize=9)

                        plt.tight_layout()

                        # Save and send Graph 2
                        buf2 = io.BytesIO()
                        plt.savefig(
                            buf2, format='png', facecolor='#2b2d31', dpi=100, bbox_inches='tight'
                        )
                        buf2.seek(0)
                        plt.close()

                        file2 = discord.File(buf2, filename='advanced_stats.png')
                        logger.info("📊 Sending Graph 2 to Discord...")
                        await ctx.send("📊 **Advanced Combat Stats - Part 2**", file=file2)
                        logger.info("✅ Graph 2 sent successfully!")
                        await asyncio.sleep(1)

                    # ═══════════════════════════════════════════════════════
                    # GRAPH 3: Per-Map Breakdown
                    # ═══════════════════════════════════════════════════════
                    if per_map_data and len(per_map_data) > 0:
                        logger.info("🎨 Generating Graph 3 (Per-Map Breakdown)...")

                        # Group data by map
                        map_stats = {}
                        for row in per_map_data:
                            map_name = row[0]
                            if map_name not in map_stats:
                                map_stats[map_name] = []
                            map_stats[map_name].append(
                                {
                                    'name': row[1],
                                    'kills': row[2] or 0,
                                    'deaths': row[3] or 0,
                                    'dpm': row[4] or 0,
                                }
                            )

                        # Create figure with subplots for each map (max 4 maps)
                        num_maps = min(len(map_stats), 4)
                        if num_maps > 0:
                            fig3, axes = plt.subplots(2, 2, figsize=(16, 12))
                            fig3.patch.set_facecolor('#2b2d31')
                            axes_flat = axes.flatten() if num_maps > 1 else [axes]

                            for idx, (map_name, players) in enumerate(list(map_stats.items())[:4]):
                                ax = axes_flat[idx]

                                # Get top 5 players for this map
                                top_players = sorted(
                                    players, key=lambda x: x['kills'], reverse=True
                                )[:5]
                                map_player_names = [p['name'] for p in top_players]
                                map_kills = [p['kills'] for p in top_players]
                                map_deaths = [p['deaths'] for p in top_players]
                                map_dpm = [p['dpm'] for p in top_players]

                                x_map = range(len(map_player_names))
                                width_map = 0.25

                                # Triple bar chart (Kills, Deaths, DPM)
                                ax.bar(
                                    [i - width_map for i in x_map],
                                    map_kills,
                                    width_map,
                                    label='Kills',
                                    color='#5865f2',
                                    alpha=0.8,
                                )
                                ax.bar(
                                    x_map,
                                    map_deaths,
                                    width_map,
                                    label='Deaths',
                                    color='#ed4245',
                                    alpha=0.8,
                                )
                                ax.bar(
                                    [i + width_map for i in x_map],
                                    map_dpm,
                                    width_map,
                                    label='DPM',
                                    color='#fee75c',
                                    alpha=0.8,
                                )

                                ax.set_title(
                                    f'🗺️ {map_name}', color='white', fontsize=12, fontweight='bold'
                                )
                                ax.set_xticks(x_map)
                                ax.set_xticklabels(
                                    map_player_names,
                                    rotation=20,
                                    ha='right',
                                    color='white',
                                    fontsize=8,
                                )
                                ax.set_facecolor('#1e1f22')
                                ax.tick_params(colors='white')
                                ax.spines['bottom'].set_color('white')
                                ax.spines['left'].set_color('white')
                                ax.spines['top'].set_visible(False)
                                ax.spines['right'].set_visible(False)
                                ax.grid(True, alpha=0.2, color='white', axis='y')
                                ax.legend(
                                    facecolor='#1e1f22',
                                    edgecolor='white',
                                    labelcolor='white',
                                    fontsize=8,
                                )

                            # Hide unused subplots
                            for idx in range(num_maps, 4):
                                axes_flat[idx].set_visible(False)

                            plt.tight_layout()

                            # Save and send Graph 3
                            buf3 = io.BytesIO()
                            plt.savefig(
                                buf3,
                                format='png',
                                facecolor='#2b2d31',
                                dpi=100,
                                bbox_inches='tight',
                            )
                            buf3.seek(0)
                            plt.close()

                            file3 = discord.File(buf3, filename='per_map_breakdown.png')
                            logger.info("📊 Sending Graph 3 to Discord...")
                            await ctx.send(
                                "📊 **Per-Map Performance Breakdown - Part 3**", file=file3
                            )
                            logger.info("✅ Graph 3 sent successfully!")
                            await asyncio.sleep(1)

                    # ═══════════════════════════════════════════════════════
                    # GRAPH 4: Combat Efficiency & Bullets Analysis
                    # ═══════════════════════════════════════════════════════
                    if chaos_awards_data and len(chaos_awards_data) > 0:
                        logger.info("🎨 Generating Graph 4 (Combat Efficiency)...")

                        # Get top 8 players by total kills for efficiency analysis
                        efficiency_players = sorted(
                            chaos_awards_data, key=lambda x: x[5], reverse=True  # total_kills
                        )[:8]

                        if efficiency_players:
                            fig4, ((ax7, ax8), (ax9, ax10)) = plt.subplots(2, 2, figsize=(16, 12))
                            fig4.patch.set_facecolor('#2b2d31')

                            # Extract data
                            eff_names = [row[0] for row in efficiency_players]
                            eff_dmg_given = [row[7] or 0 for row in efficiency_players]
                            eff_dmg_received = [row[8] or 0 for row in efficiency_players]
                            eff_bullets = [row[4] or 0 for row in efficiency_players]
                            eff_kills = [row[5] or 0 for row in efficiency_players]

                            # Calculate ratios
                            eff_damage_ratio = [
                                (g / r) if r > 0 else g
                                for g, r in zip(eff_dmg_given, eff_dmg_received)
                            ]
                            eff_bullets_per_kill = [
                                (b / k) if k > 0 else 0 for b, k in zip(eff_bullets, eff_kills)
                            ]

                            x_eff = range(len(eff_names))
                            width_eff = 0.35

                            # Subplot 1: Damage Given vs Received
                            ax7.bar(
                                [i - width_eff / 2 for i in x_eff],
                                eff_dmg_given,
                                width_eff,
                                label='Damage Given',
                                color='#5865f2',
                                alpha=0.8,
                            )
                            ax7.bar(
                                [i + width_eff / 2 for i in x_eff],
                                eff_dmg_received,
                                width_eff,
                                label='Damage Received',
                                color='#ed4245',
                                alpha=0.8,
                            )
                            ax7.set_xticks(x_eff)
                            ax7.set_xticklabels(
                                eff_names, rotation=20, ha='right', color='white', fontsize=9
                            )
                            ax7.set_ylabel('Damage', color='white', fontsize=11)
                            ax7.set_title(
                                'Damage Given vs Received',
                                color='white',
                                fontsize=12,
                                fontweight='bold',
                            )
                            ax7.set_facecolor('#1e1f22')
                            ax7.tick_params(colors='white')
                            ax7.spines['bottom'].set_color('white')
                            ax7.spines['left'].set_color('white')
                            ax7.spines['top'].set_visible(False)
                            ax7.spines['right'].set_visible(False)
                            ax7.grid(True, alpha=0.2, color='white', axis='y')
                            ax7.legend(
                                facecolor='#1e1f22',
                                edgecolor='white',
                                labelcolor='white',
                                fontsize=9,
                            )

                            # Subplot 2: Damage Efficiency Ratio
                            colors_ratio = [
                                '#57f287' if r > 1.5 else '#fee75c' if r > 1.0 else '#ed4245'
                                for r in eff_damage_ratio
                            ]
                            ax8.bar(x_eff, eff_damage_ratio, color=colors_ratio, alpha=0.8)
                            ax8.axhline(
                                y=1.0, color='white', linestyle='--', alpha=0.5, linewidth=1
                            )
                            ax8.set_xticks(x_eff)
                            ax8.set_xticklabels(
                                eff_names, rotation=20, ha='right', color='white', fontsize=9
                            )
                            ax8.set_ylabel('Ratio (Given/Received)', color='white', fontsize=11)
                            ax8.set_title(
                                'Damage Efficiency Ratio',
                                color='white',
                                fontsize=12,
                                fontweight='bold',
                            )
                            ax8.set_facecolor('#1e1f22')
                            ax8.tick_params(colors='white')
                            ax8.spines['bottom'].set_color('white')
                            ax8.spines['left'].set_color('white')
                            ax8.spines['top'].set_visible(False)
                            ax8.spines['right'].set_visible(False)
                            ax8.grid(True, alpha=0.2, color='white', axis='y')
                            for i, v in enumerate(eff_damage_ratio):
                                ax8.text(
                                    i,
                                    v,
                                    f'{v:.2f}x',
                                    ha='center',
                                    va='bottom',
                                    color='white',
                                    fontsize=8,
                                )

                            # Subplot 3: Total Bullets Fired
                            ax9.bar(x_eff, eff_bullets, color='#fee75c', alpha=0.8)
                            ax9.set_xticks(x_eff)
                            ax9.set_xticklabels(
                                eff_names, rotation=20, ha='right', color='white', fontsize=9
                            )
                            ax9.set_ylabel('Bullets Fired', color='white', fontsize=11)
                            ax9.set_title(
                                'Total Ammunition Fired',
                                color='white',
                                fontsize=12,
                                fontweight='bold',
                            )
                            ax9.set_facecolor('#1e1f22')
                            ax9.tick_params(colors='white')
                            ax9.spines['bottom'].set_color('white')
                            ax9.spines['left'].set_color('white')
                            ax9.spines['top'].set_visible(False)
                            ax9.spines['right'].set_visible(False)
                            ax9.grid(True, alpha=0.2, color='white', axis='y')
                            for i, v in enumerate(eff_bullets):
                                ax9.text(
                                    i,
                                    v,
                                    f'{int(v):,}',
                                    ha='center',
                                    va='bottom',
                                    color='white',
                                    fontsize=8,
                                )

                            # Subplot 4: Bullets per Kill
                            colors_bpk = [
                                '#57f287' if b < 100 else '#fee75c' if b < 200 else '#ed4245'
                                for b in eff_bullets_per_kill
                            ]
                            ax10.bar(x_eff, eff_bullets_per_kill, color=colors_bpk, alpha=0.8)
                            ax10.set_xticks(x_eff)
                            ax10.set_xticklabels(
                                eff_names, rotation=20, ha='right', color='white', fontsize=9
                            )
                            ax10.set_ylabel('Bullets per Kill', color='white', fontsize=11)
                            ax10.set_title(
                                'Accuracy Metric (Lower = Better)',
                                color='white',
                                fontsize=12,
                                fontweight='bold',
                            )
                            ax10.set_facecolor('#1e1f22')
                            ax10.tick_params(colors='white')
                            ax10.spines['bottom'].set_color('white')
                            ax10.spines['left'].set_color('white')
                            ax10.spines['top'].set_visible(False)
                            ax10.spines['right'].set_visible(False)
                            ax10.grid(True, alpha=0.2, color='white', axis='y')
                            for i, v in enumerate(eff_bullets_per_kill):
                                ax10.text(
                                    i,
                                    v,
                                    f'{v:.0f}',
                                    ha='center',
                                    va='bottom',
                                    color='white',
                                    fontsize=8,
                                )

                            plt.tight_layout()

                            # Save and send Graph 4
                            buf4 = io.BytesIO()
                            plt.savefig(
                                buf4,
                                format='png',
                                facecolor='#2b2d31',
                                dpi=100,
                                bbox_inches='tight',
                            )
                            buf4.seek(0)
                            plt.close()

                            file4 = discord.File(buf4, filename='combat_efficiency.png')
                            logger.info("📊 Sending Graph 4 to Discord...")
                            await ctx.send(
                                "📊 **Combat Efficiency & Bullets Analysis - Part 4**", file=file4
                            )
                            logger.info("✅ Graph 4 sent successfully!")

                else:
                    logger.warning("⚠️ No graph data available - empty graph_data list")

            except ImportError as e:
                logger.warning(f"⚠️ matplotlib not installed: {e}")
            except Exception as e:
                logger.error(f"❌ Error generating graphs: {e}", exc_info=True)
                # Send error message to user
                await ctx.send(f"⚠️ Could not generate graphs: {str(e)[:100]}")

        except Exception as e:
            logger.error(f"Error in last_session command: {e}", exc_info=True)
            await ctx.send(f"❌ Error retrieving last session: {e}")

    @commands.command(name='sessions', aliases=['list_sessions', 'ls'])
    async def list_sessions(self, ctx, *, month: str = None):
        """📅 List all gaming sessions, optionally filtered by month

        Usage:
        - !sessions              → List all sessions (last 20)
        - !sessions 10           → List sessions from October (current year)
        - !sessions 2025-10      → List sessions from October 2025
        - !sessions october      → List sessions from October (current year)
        - !sessions oct          → Same as above
        """
        try:
            conn = sqlite3.connect(self.bot.db_path)
            cursor = conn.cursor()
            
            # Build query based on month filter
            if month:
                # Handle different month formats
                month_lower = month.strip().lower()
                month_names = {
                    'january': '01', 'jan': '01',
                    'february': '02', 'feb': '02',
                    'march': '03', 'mar': '03',
                    'april': '04', 'apr': '04',
                    'may': '05',
                    'june': '06', 'jun': '06',
                    'july': '07', 'jul': '07',
                    'august': '08', 'aug': '08',
                    'september': '09', 'sep': '09',
                    'october': '10', 'oct': '10',
                    'november': '11', 'nov': '11',
                    'december': '12', 'dec': '12'
                }
                
                if month_lower in month_names:
                    # Month name provided - use current year
                    from datetime import datetime
                    current_year = datetime.now().year
                    month_filter = f"{current_year}-{month_names[month_lower]}"
                elif '-' in month:
                    # Full YYYY-MM format
                    month_filter = month
                elif month.isdigit() and len(month) <= 2:
                    # Just month number - use current year
                    from datetime import datetime
                    current_year = datetime.now().year
                    month_filter = f"{current_year}-{int(month):02d}"
                else:
                    await ctx.send(f"❌ Invalid month format: `{month}`\nUse: `!sessions 10` or `!sessions october`")
                    conn.close()
                    return
                
                query = '''
                    SELECT 
                        DATE(session_date) as date,
                        COUNT(DISTINCT session_id) / 2 as maps,
                        COUNT(DISTINCT session_id) as rounds,
                        COUNT(DISTINCT player_guid) as players,
                        MIN(session_date) as first_round,
                        MAX(session_date) as last_round
                    FROM player_comprehensive_stats
                    WHERE session_date LIKE ?
                    GROUP BY DATE(session_date)
                    ORDER BY date DESC
                '''
                cursor.execute(query, (f"{month_filter}%",))
                filter_text = month_filter
            else:
                query = '''
                    SELECT 
                        DATE(session_date) as date,
                        COUNT(DISTINCT session_id) / 2 as maps,
                        COUNT(DISTINCT session_id) as rounds,
                        COUNT(DISTINCT player_guid) as players,
                        MIN(session_date) as first_round,
                        MAX(session_date) as last_round
                    FROM player_comprehensive_stats
                    GROUP BY DATE(session_date)
                    ORDER BY date DESC
                    LIMIT 20
                '''
                cursor.execute(query)
                filter_text = "all time (last 20)"
            
            sessions = cursor.fetchall()
            conn.close()
            
            if not sessions:
                await ctx.send(f"❌ No sessions found for {filter_text}")
                return
            
            # Create embed
            embed = discord.Embed(
                title="📅 Gaming Sessions",
                description=f"Showing sessions from **{filter_text}**",
                color=discord.Color.blue()
            )
            
            session_list = []
            for date, maps, rounds, players, first, last in sessions:
                # Calculate duration
                from datetime import datetime
                try:
                    first_dt = datetime.fromisoformat(first.replace('Z', '+00:00') if 'Z' in first else first)
                    last_dt = datetime.fromisoformat(last.replace('Z', '+00:00') if 'Z' in last else last)
                    duration = last_dt - first_dt
                    hours = duration.total_seconds() / 3600
                    duration_str = f"{hours:.1f}h"
                except:
                    duration_str = "N/A"
                
                session_list.append(
                    f"**{date}**\n"
                    f"└ {int(maps)} maps • {rounds} rounds • {players} players • {duration_str}"
                )
            
            # Split into chunks if too long
            chunk_size = 10
            for i in range(0, len(session_list), chunk_size):
                chunk = session_list[i:i+chunk_size]
                embed.add_field(
                    name=f"Sessions {i+1}-{min(i+chunk_size, len(session_list))}",
                    value="\n\n".join(chunk),
                    inline=False
                )
            
            embed.set_footer(text=f"Total: {len(sessions)} sessions • Use !last_session or !session YYYY-MM-DD for details")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in list_sessions command: {e}", exc_info=True)
            await ctx.send(f"❌ Error listing sessions: {e}")

    @commands.command(name='list_players', aliases=['players', 'lp'])
    async def list_players(self, ctx, filter_type: str = None):
        """👥 List all players with their Discord link status

        Usage:
        - !list_players         → Show all players
        - !list_players linked  → Show only linked players
        - !list_players unlinked → Show only unlinked players
        - !list_players active  → Show players from last 30 days
        """
        try:
            conn = sqlite3.connect(self.bot.db_path)
            cursor = conn.cursor()
            
            # Base query to get all players with their link status
            base_query = '''
                SELECT 
                    p.player_guid,
                    p.player_name,
                    pl.discord_id,
                    COUNT(DISTINCT p.session_date) as sessions_played,
                    MAX(p.session_date) as last_played,
                    SUM(p.kills) as total_kills,
                    SUM(p.deaths) as total_deaths
                FROM player_comprehensive_stats p
                LEFT JOIN player_links pl ON p.player_guid = pl.et_guid
                GROUP BY p.player_guid, p.player_name, pl.discord_id
            '''
            
            # Apply filter
            if filter_type:
                filter_lower = filter_type.lower()
                if filter_lower in ['linked', 'link']:
                    base_query += " HAVING pl.discord_id IS NOT NULL"
                elif filter_lower in ['unlinked', 'nolink']:
                    base_query += " HAVING pl.discord_id IS NULL"
                elif filter_lower in ['active', 'recent']:
                    base_query += " HAVING MAX(p.session_date) >= date('now', '-30 days')"
            
            base_query += " ORDER BY sessions_played DESC, total_kills DESC"
            
            cursor.execute(base_query)
            players = cursor.fetchall()
            conn.close()
            
            if not players:
                await ctx.send(f"❌ No players found with filter: {filter_type}")
                return
            
            # Count linked vs unlinked
            linked_count = sum(1 for p in players if p[2])
            unlinked_count = len(players) - linked_count
            
            # Create embed
            filter_text = ""
            if filter_type:
                filter_text = f" ({filter_type})"
            
            embed = discord.Embed(
                title=f"👥 Players List{filter_text}",
                description=f"**Total**: {len(players)} players • 🔗 {linked_count} linked • ❌ {unlinked_count} unlinked",
                color=discord.Color.green()
            )
            
            # Format player list
            player_lines = []
            for guid, name, discord_id, sessions, last_played, kills, deaths in players:
                # Link status icon
                link_icon = "🔗" if discord_id else "❌"
                
                # Discord mention if linked
                discord_info = f"<@{discord_id}>" if discord_id else "Not linked"
                
                # KD ratio
                kd = kills / deaths if deaths > 0 else kills
                
                # Format last played date
                try:
                    from datetime import datetime
                    last_date = datetime.fromisoformat(last_played.replace('Z', '+00:00') if 'Z' in last_played else last_played)
                    days_ago = (datetime.now() - last_date).days
                    if days_ago == 0:
                        last_str = "today"
                    elif days_ago == 1:
                        last_str = "yesterday"
                    else:
                        last_str = f"{days_ago}d ago"
                except:
                    last_str = "N/A"
                
                player_lines.append(
                    f"{link_icon} **{name}**\n"
                    f"└ {discord_info}\n"
                    f"└ {sessions} sessions • {kills}K/{deaths}D ({kd:.2f} KD) • Last: {last_str}"
                )
            
            # Split into chunks (Discord has 1024 char limit per field, ~25 fields per embed)
            chunk_size = 10
            for i in range(0, len(player_lines), chunk_size):
                chunk = player_lines[i:i+chunk_size]
                embed.add_field(
                    name=f"Players {i+1}-{min(i+chunk_size, len(player_lines))}",
                    value="\n\n".join(chunk),
                    inline=False
                )
                
                # Discord embed limit is 6000 chars total or 25 fields
                if len(embed.fields) >= 20:
                    embed.set_footer(text=f"Showing first {min(i+chunk_size, len(player_lines))} of {len(players)} players")
                    break
            
            if len(embed.fields) < 20:
                embed.set_footer(text=f"Use !link to link your Discord • !list_players [linked|unlinked|active]")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in list_players command: {e}", exc_info=True)
            await ctx.send(f"❌ Error listing players: {e}")

    @commands.command(name='link')
    async def link(self, ctx, target: str = None, *, guid: str = None):
        """🔗 Link your Discord account to your in-game profile

        Usage: 
        - !link                        → Smart search with top 3 suggestions
        - !link YourPlayerName         → Search by name
        - !link GUID                   → Direct link by GUID
        - !link @user GUID             → Admin: Link another user (requires permissions)
        """
        try:
            # === SCENARIO 0: ADMIN LINKING (@mention + GUID) ===
            if ctx.message.mentions and guid:
                await self._admin_link(ctx, ctx.message.mentions[0], guid.upper())
                return

            # For self-linking
            discord_id = str(ctx.author.id)

            # Check if already linked
            async with aiosqlite.connect(self.bot.db_path) as db:
                async with db.execute(
                    '''
                    SELECT et_name, et_guid FROM player_links
                    WHERE discord_id = ?
                ''',
                    (discord_id,),
                ) as cursor:
                    existing = await cursor.fetchone()

                if existing:
                    await ctx.send(
                        f"⚠️ You're already linked to **{existing[0]}** (GUID: {existing[1]})\\n"
                        f"Use `!unlink` first to change your linked account."
                    )
                    return

                # === SCENARIO 1: NO ARGUMENTS - Smart Self-Linking ===
                if not target:
                    await self._smart_self_link(ctx, discord_id, db)
                    return

                # === SCENARIO 2: GUID Direct Link ===
                # Check if it's a GUID (8 hex characters)
                if len(target) == 8 and all(c in '0123456789ABCDEFabcdef' for c in target):
                    await self._link_by_guid(ctx, discord_id, target.upper(), db)
                    return

                # === SCENARIO 3: Name Search ===
                await self._link_by_name(ctx, discord_id, target, db)

        except Exception as e:
            logger.error(f"Error in link command: {e}", exc_info=True)
            await ctx.send(f"❌ Error linking account: {e}")

    async def _smart_self_link(self, ctx, discord_id: str, db):
        """Smart self-linking: show top 3 unlinked GUIDs with aliases"""
        try:
            # Get top 3 unlinked players by recent activity and total stats
            async with db.execute(
                '''
                SELECT 
                    player_guid,
                    MAX(session_date) as last_played,
                    SUM(kills) as total_kills,
                    SUM(deaths) as total_deaths,
                    COUNT(DISTINCT session_id) as games
                FROM player_comprehensive_stats
                WHERE player_guid NOT IN (SELECT et_guid FROM player_links WHERE et_guid IS NOT NULL)
                GROUP BY player_guid
                ORDER BY last_played DESC, total_kills DESC
                LIMIT 3
            ''',
            ) as cursor:
                top_players = await cursor.fetchall()

            if not top_players:
                await ctx.send(
                    "❌ No available players found!\\n"
                    "All players are already linked or no games recorded."
                )
                return

            # Build embed with top 3 options
            embed = discord.Embed(
                title="🔍 Link Your Account",
                description=(
                    f"Found **{len(top_players)}** potential matches!\\n"
                    f"React with 1️⃣/2️⃣/3️⃣ or use `!select <number>` within 60 seconds."
                ),
                color=0x3498db,
            )

            options_data = []
            for idx, (guid, last_date, kills, deaths, games) in enumerate(top_players, 1):
                # Get aliases for this GUID
                async with db.execute(
                    '''
                    SELECT player_name, last_seen, times_used
                    FROM player_aliases
                    WHERE player_guid = ?
                    ORDER BY last_seen DESC, times_used DESC
                    LIMIT 3
                ''',
                    (guid,),
                ) as cursor:
                    aliases = await cursor.fetchall()

                # Format aliases
                if aliases:
                    primary_name = aliases[0][0]
                    alias_str = ", ".join([a[0] for a in aliases[:3]])
                    if len(aliases) > 3:
                        alias_str += "..."
                else:
                    # Fallback to most recent name
                    async with db.execute(
                        '''
                        SELECT player_name 
                        FROM player_comprehensive_stats 
                        WHERE player_guid = ? 
                        ORDER BY session_date DESC 
                        LIMIT 1
                    ''',
                        (guid,),
                    ) as cursor:
                        name_row = await cursor.fetchone()
                        primary_name = name_row[0] if name_row else "Unknown"
                        alias_str = primary_name

                kd_ratio = kills / deaths if deaths > 0 else kills
                
                emoji = ["1️⃣", "2️⃣", "3️⃣"][idx - 1]
                embed.add_field(
                    name=f"{emoji} **{primary_name}**",
                    value=(
                        f"**GUID:** {guid}\\n"
                        f"**Stats:** {kills:,} kills / {deaths:,} deaths / {kd_ratio:.2f} K/D\\n"
                        f"**Games:** {games:,} | **Last Seen:** {last_date}\\n"
                        f"**Also:** {alias_str}"
                    ),
                    inline=False,
                )

                options_data.append({
                    'guid': guid,
                    'name': primary_name,
                    'kills': kills,
                    'games': games
                })

            embed.set_footer(text=f"💡 Tip: Use !link <GUID> to link directly | Requested by {ctx.author.display_name}")

            message = await ctx.send(embed=embed)

            # Add reaction emojis
            emojis = ['1️⃣', '2️⃣', '3️⃣'][:len(top_players)]
            for emoji in emojis:
                await message.add_reaction(emoji)

            # Wait for reaction
            def check(reaction, user):
                return (
                    user == ctx.author
                    and str(reaction.emoji) in emojis
                    and reaction.message.id == message.id
                )

            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
                
                # Get selected index
                selected_idx = emojis.index(str(reaction.emoji))
                selected = options_data[selected_idx]

                # Link the account
                await db.execute(
                    '''
                    INSERT OR REPLACE INTO player_links
                    (discord_id, discord_username, et_guid, et_name, linked_date, verified)
                    VALUES (?, ?, ?, ?, datetime('now'), 1)
                ''',
                    (discord_id, str(ctx.author), selected['guid'], selected['name']),
                )
                await db.commit()

                # Success!
                await message.clear_reactions()
                success_embed = discord.Embed(
                    title="✅ Account Linked!",
                    description=f"Successfully linked to **{selected['name']}**",
                    color=0x00FF00,
                )
                success_embed.add_field(
                    name="Stats Preview",
                    value=f"**Games:** {selected['games']:,}\\n**Kills:** {selected['kills']:,}",
                    inline=True,
                )
                success_embed.add_field(
                    name="Quick Access",
                    value="Use `!stats` without arguments to see your stats!",
                    inline=False,
                )
                success_embed.set_footer(text=f"GUID: {selected['guid']}")
                await ctx.send(embed=success_embed)

            except asyncio.TimeoutError:
                await message.clear_reactions()
                await ctx.send("⏱️ Link request timed out. Try again with `!link`")

        except Exception as e:
            logger.error(f"Error in smart self-link: {e}", exc_info=True)
            await ctx.send(f"❌ Error during self-linking: {e}")

    async def _link_by_guid(self, ctx, discord_id: str, guid: str, db):
        """Direct GUID linking with confirmation"""
        try:
            # Check if GUID exists
            async with db.execute(
                '''
                SELECT 
                    SUM(kills) as total_kills,
                    SUM(deaths) as total_deaths,
                    COUNT(DISTINCT session_id) as games,
                    MAX(session_date) as last_seen
                FROM player_comprehensive_stats
                WHERE player_guid = ?
            ''',
                (guid,),
            ) as cursor:
                stats = await cursor.fetchone()

            if not stats or stats[0] is None:
                await ctx.send(f"❌ GUID `{guid}` not found in database.")
                return

            # Get aliases
            async with db.execute(
                '''
                SELECT player_name, last_seen, times_used
                FROM player_aliases
                WHERE player_guid = ?
                ORDER BY last_seen DESC, times_used DESC
                LIMIT 3
            ''',
                (guid,),
            ) as cursor:
                aliases = await cursor.fetchall()

            if aliases:
                primary_name = aliases[0][0]
                alias_str = ", ".join([a[0] for a in aliases[:3]])
            else:
                # Fallback
                async with db.execute(
                    '''
                    SELECT player_name 
                    FROM player_comprehensive_stats 
                    WHERE player_guid = ? 
                    ORDER BY session_date DESC 
                    LIMIT 1
                ''',
                    (guid,),
                ) as cursor:
                    name_row = await cursor.fetchone()
                    primary_name = name_row[0] if name_row else "Unknown"
                    alias_str = primary_name

            kills, deaths, games, last_seen = stats
            kd_ratio = kills / deaths if deaths > 0 else kills

            # Confirmation embed
            embed = discord.Embed(
                title="🔗 Confirm Account Link",
                description=f"Link your Discord to **{primary_name}**?",
                color=0xFFA500,
            )
            embed.add_field(
                name="GUID",
                value=guid,
                inline=False,
            )
            embed.add_field(
                name="Known Names",
                value=alias_str,
                inline=False,
            )
            embed.add_field(
                name="Stats",
                value=f"{kills:,} kills / {deaths:,} deaths / {kd_ratio:.2f} K/D",
                inline=True,
            )
            embed.add_field(
                name="Activity",
                value=f"{games:,} games | Last: {last_seen}",
                inline=True,
            )
            embed.set_footer(text="React ✅ to confirm or ❌ to cancel (60s)")

            message = await ctx.send(embed=embed)
            await message.add_reaction('✅')
            await message.add_reaction('❌')

            def check(reaction, user):
                return (
                    user == ctx.author
                    and str(reaction.emoji) in ['✅', '❌']
                    and reaction.message.id == message.id
                )

            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)

                if str(reaction.emoji) == '✅':
                    # Confirmed - link it
                    await db.execute(
                        '''
                        INSERT OR REPLACE INTO player_links
                        (discord_id, discord_username, et_guid, et_name, linked_date, verified)
                        VALUES (?, ?, ?, ?, datetime('now'), 1)
                    ''',
                        (discord_id, str(ctx.author), guid, primary_name),
                    )
                    await db.commit()

                    await message.clear_reactions()
                    await ctx.send(f"✅ Successfully linked to **{primary_name}** (GUID: {guid})")
                else:
                    await message.clear_reactions()
                    await ctx.send("❌ Link cancelled.")

            except asyncio.TimeoutError:
                await message.clear_reactions()
                await ctx.send("⏱️ Confirmation timed out.")

        except Exception as e:
            logger.error(f"Error in GUID link: {e}", exc_info=True)
            await ctx.send(f"❌ Error linking by GUID: {e}")

    async def _link_by_name(self, ctx, discord_id: str, player_name: str, db):
        """Name search linking (existing functionality enhanced)"""
        try:
            # Search in player_aliases first for better matching
            async with db.execute(
                '''
                SELECT DISTINCT pa.player_guid
                FROM player_aliases pa
                WHERE LOWER(pa.clean_name) LIKE LOWER(?)
                ORDER BY pa.last_seen DESC
                LIMIT 5
            ''',
                (f'%{player_name}%',),
            ) as cursor:
                alias_guids = [row[0] for row in await cursor.fetchall()]

            # Also search main stats table
            async with db.execute(
                '''
                SELECT player_guid, player_name,
                       SUM(kills) as total_kills,
                       COUNT(DISTINCT session_id) as games,
                       MAX(session_date) as last_seen
                FROM player_comprehensive_stats
                WHERE LOWER(player_name) LIKE LOWER(?)
                GROUP BY player_guid
                ORDER BY last_seen DESC, games DESC
                LIMIT 5
            ''',
                (f'%{player_name}%',),
            ) as cursor:
                matches = await cursor.fetchall()

            # Combine and deduplicate
            guid_set = set(alias_guids)
            for match in matches:
                guid_set.add(match[0])

            if not guid_set:
                await ctx.send(
                    f"❌ No player found matching '{player_name}'\\n"
                    f"💡 Try: `!link` (no arguments) to see all available players"
                )
                return

            # Get full data for found GUIDs
            guid_list = list(guid_set)[:3]  # Limit to 3
            
            if len(guid_list) == 1:
                # Single match - link directly with confirmation
                await self._link_by_guid(ctx, discord_id, guid_list[0], db)
            else:
                # Multiple matches - show options (similar to smart self-link)
                embed = discord.Embed(
                    title=f"🔍 Multiple Matches for '{player_name}'",
                    description="React with 1️⃣/2️⃣/3️⃣ to select:",
                    color=0x3498db,
                )

                options_data = []
                for idx, guid in enumerate(guid_list, 1):
                    # Get stats and aliases
                    async with db.execute(
                        '''
                        SELECT SUM(kills), SUM(deaths), COUNT(DISTINCT session_id), MAX(session_date)
                        FROM player_comprehensive_stats
                        WHERE player_guid = ?
                    ''',
                        (guid,),
                    ) as cursor:
                        stats = await cursor.fetchone()

                    async with db.execute(
                        '''
                        SELECT player_name FROM player_aliases
                        WHERE player_guid = ?
                        ORDER BY last_seen DESC LIMIT 1
                    ''',
                        (guid,),
                    ) as cursor:
                        name_row = await cursor.fetchone()
                        name = name_row[0] if name_row else "Unknown"

                    kills, deaths, games, last_seen = stats
                    kd = kills / deaths if deaths > 0 else kills

                    emoji = ["1️⃣", "2️⃣", "3️⃣"][idx - 1]
                    embed.add_field(
                        name=f"{emoji} **{name}**",
                        value=f"**GUID:** {guid}\\n{kills:,} kills | {games:,} games | Last: {last_seen}",
                        inline=False,
                    )

                    options_data.append({'guid': guid, 'name': name, 'kills': kills, 'games': games})

                message = await ctx.send(embed=embed)

                emojis = ['1️⃣', '2️⃣', '3️⃣'][:len(guid_list)]
                for emoji in emojis:
                    await message.add_reaction(emoji)

                def check(reaction, user):
                    return user == ctx.author and str(reaction.emoji) in emojis and reaction.message.id == message.id

                try:
                    reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
                    selected_idx = emojis.index(str(reaction.emoji))
                    selected = options_data[selected_idx]

                    await db.execute(
                        '''
                        INSERT OR REPLACE INTO player_links
                        (discord_id, discord_username, et_guid, et_name, linked_date, verified)
                        VALUES (?, ?, ?, ?, datetime('now'), 1)
                    ''',
                        (discord_id, str(ctx.author), selected['guid'], selected['name']),
                    )
                    await db.commit()

                    await message.clear_reactions()
                    await ctx.send(f"✅ Successfully linked to **{selected['name']}** (GUID: {selected['guid']})")

                except asyncio.TimeoutError:
                    await message.clear_reactions()
                    await ctx.send("⏱️ Selection timed out.")

        except Exception as e:
            logger.error(f"Error in name link: {e}", exc_info=True)
            await ctx.send(f"❌ Error linking by name: {e}")

    async def _admin_link(self, ctx, target_user: discord.User, guid: str):
        """Admin linking: Link another user's Discord to a GUID"""
        try:
            # Check permissions
            if not ctx.author.guild_permissions.manage_guild:
                await ctx.send(
                    "❌ You don't have permission to link other users.\\n"
                    "**Required:** Manage Server permission"
                )
                logger.warning(
                    f"Unauthorized admin link attempt by {ctx.author} "
                    f"(ID: {ctx.author.id})"
                )
                return

            # Validate GUID format (8 hex characters)
            if len(guid) != 8 or not all(c in '0123456789ABCDEFabcdef' for c in guid):
                await ctx.send(
                    f"❌ Invalid GUID format: `{guid}`\\n"
                    f"**GUIDs must be exactly 8 hexadecimal characters** (e.g., `D8423F90`)\\n\\n"
                    f"💡 To link by player name instead:\\n"
                    f"   • Ask {target_user.mention} to use `!link {guid}` (searches by name)\\n"
                    f"   • Or use `!stats {guid}` to find their GUID first"
                )
                return

            target_discord_id = str(target_user.id)

            async with aiosqlite.connect(self.bot.db_path) as db:
                # Check if target already linked
                async with db.execute(
                    '''
                    SELECT et_name, et_guid FROM player_links
                    WHERE discord_id = ?
                ''',
                    (target_discord_id,),
                ) as cursor:
                    existing = await cursor.fetchone()

                if existing:
                    await ctx.send(
                        f"⚠️ {target_user.mention} is already linked to "
                        f"**{existing[0]}** (GUID: {existing[1]})\\n"
                        f"They need to `!unlink` first, or you can overwrite "
                        f"with force (react ⚠️ to confirm)."
                    )
                    # For now, just block. Future: Add force option
                    return

                # Validate GUID exists
                async with db.execute(
                    '''
                    SELECT 
                        SUM(kills) as total_kills,
                        SUM(deaths) as total_deaths,
                        COUNT(DISTINCT session_id) as games,
                        MAX(session_date) as last_seen
                    FROM player_comprehensive_stats
                    WHERE player_guid = ?
                ''',
                    (guid,),
                ) as cursor:
                    stats = await cursor.fetchone()

                if not stats or stats[0] is None:
                    await ctx.send(
                        f"❌ GUID `{guid}` not found in database.\\n"
                        f"💡 Use `!link` (no args) to see available players."
                    )
                    return

                # Get aliases
                async with db.execute(
                    '''
                    SELECT player_name, last_seen, times_used
                    FROM player_aliases
                    WHERE player_guid = ?
                    ORDER BY last_seen DESC, times_used DESC
                    LIMIT 3
                ''',
                    (guid,),
                ) as cursor:
                    aliases = await cursor.fetchall()

                if aliases:
                    primary_name = aliases[0][0]
                    alias_str = ", ".join([a[0] for a in aliases[:3]])
                else:
                    # Fallback
                    async with db.execute(
                        '''
                        SELECT player_name 
                        FROM player_comprehensive_stats 
                        WHERE player_guid = ? 
                        ORDER BY session_date DESC 
                        LIMIT 1
                    ''',
                        (guid,),
                    ) as cursor:
                        name_row = await cursor.fetchone()
                        primary_name = name_row[0] if name_row else "Unknown"
                        alias_str = primary_name

                kills, deaths, games, last_seen = stats
                kd_ratio = kills / deaths if deaths > 0 else kills

                # Admin confirmation embed
                embed = discord.Embed(
                    title="🔗 Admin Link Confirmation",
                    description=(
                        f"Link {target_user.mention} to **{primary_name}**?\\n\\n"
                        f"**Requested by:** {ctx.author.mention}"
                    ),
                    color=0xFF6B00,  # Orange for admin action
                )
                embed.add_field(
                    name="Target User",
                    value=f"{target_user.mention} ({target_user.name})",
                    inline=True,
                )
                embed.add_field(
                    name="GUID",
                    value=guid,
                    inline=True,
                )
                embed.add_field(
                    name="Known Names",
                    value=alias_str,
                    inline=False,
                )
                embed.add_field(
                    name="Stats",
                    value=(
                        f"**Kills:** {kills:,} | **Deaths:** {deaths:,}\\n"
                        f"**K/D:** {kd_ratio:.2f} | **Games:** {games:,}"
                    ),
                    inline=True,
                )
                embed.add_field(
                    name="Last Seen",
                    value=last_seen,
                    inline=True,
                )
                embed.set_footer(
                    text="React ✅ (admin) to confirm or ❌ to cancel (60s)"
                )

                message = await ctx.send(embed=embed)
                await message.add_reaction('✅')
                await message.add_reaction('❌')

                def check(reaction, user):
                    return (
                        user == ctx.author  # Only admin can confirm
                        and str(reaction.emoji) in ['✅', '❌']
                        and reaction.message.id == message.id
                    )

                try:
                    reaction, user = await self.bot.wait_for(
                        'reaction_add', timeout=60.0, check=check
                    )

                    if str(reaction.emoji) == '✅':
                        # Confirmed - link it
                        await db.execute(
                            '''
                            INSERT OR REPLACE INTO player_links
                            (discord_id, discord_username, et_guid, et_name, 
                             linked_date, verified)
                            VALUES (?, ?, ?, ?, datetime('now'), 1)
                        ''',
                            (
                                target_discord_id,
                                str(target_user),
                                guid,
                                primary_name,
                            ),
                        )
                        await db.commit()

                        await message.clear_reactions()
                        
                        # Success message
                        success_embed = discord.Embed(
                            title="✅ Admin Link Successful",
                            description=(
                                f"{target_user.mention} is now linked to "
                                f"**{primary_name}**"
                            ),
                            color=0x00FF00,
                        )
                        success_embed.add_field(
                            name="GUID",
                            value=guid,
                            inline=True,
                        )
                        success_embed.add_field(
                            name="Linked By",
                            value=ctx.author.mention,
                            inline=True,
                        )
                        success_embed.set_footer(
                            text=(
                                f"💡 {target_user.name} can now use "
                                f"!stats to see their stats"
                            )
                        )
                        
                        await ctx.send(embed=success_embed)
                        
                        # Log admin action
                        logger.info(
                            f"Admin link: {ctx.author} (ID: {ctx.author.id}) "
                            f"linked {target_user} (ID: {target_user.id}) "
                            f"to GUID {guid} ({primary_name})"
                        )
                        
                    else:
                        await message.clear_reactions()
                        await ctx.send("❌ Admin link cancelled.")

                except asyncio.TimeoutError:
                    await message.clear_reactions()
                    await ctx.send("⏱️ Admin link confirmation timed out.")

        except Exception as e:
            logger.error(f"Error in admin link: {e}", exc_info=True)
            await ctx.send(f"❌ Error during admin linking: {e}")

    @commands.command(name='unlink')
    async def unlink(self, ctx):
        """🔓 Unlink your Discord account from your in-game profile"""
        try:
            discord_id = str(ctx.author.id)

            async with aiosqlite.connect(self.bot.db_path) as db:
                # Check if linked
                async with db.execute(
                    '''
                    SELECT player_name FROM player_links
                    WHERE discord_id = ?
                ''',
                    (discord_id,),
                ) as cursor:
                    existing = await cursor.fetchone()

                if not existing:
                    await ctx.send("❌ You don't have a linked account.")
                    return

                # Remove link
                await db.execute(
                    '''
                    UPDATE player_links
                    SET discord_id = NULL
                    WHERE discord_id = ?
                ''',
                    (discord_id,),
                )

                await db.commit()

            await ctx.send(f"✅ Unlinked from **{existing[0]}**")

        except Exception as e:
            logger.error(f"Error in unlink command: {e}", exc_info=True)
            await ctx.send(f"❌ Error unlinking account: {e}")

    @commands.command(name='select')
    async def select_option(self, ctx, selection: int = None):
        """🔢 Select an option from a link prompt (alternative to reactions)

        Usage: !select <1-3>
        
        Note: This works as an alternative to clicking reaction emojis.
        Must be used within 60 seconds of a !link command.
        """
        if selection is None:
            await ctx.send(
                "❌ Please specify a number!\\n"
                "Usage: `!select 1`, `!select 2`, or `!select 3`"
            )
            return

        if selection not in [1, 2, 3]:
            await ctx.send("❌ Please select 1, 2, or 3.")
            return

        await ctx.send(
            f"💡 You selected option **{selection}**!\\n\\n"
            f"**Note:** The `!select` command currently requires integration with the link workflow.\\n"
            f"For now, please use the reaction emojis (1️⃣/2️⃣/3️⃣) on the link message, "
            f"or use `!link <GUID>` to link directly.\\n\\n"
            f"**Tip:** To find your GUID, use `!link` (no arguments) and check the GUID field."
        )
        
        # TODO: Implement persistent selection state
        # This would require storing pending link requests per user
        # and checking if they have an active selection window

    async def get_hardcoded_teams(self, db, session_date):
        """🎯 Get hardcoded teams from session_teams table if available
        
        Returns dict with team info or None if not available:
        {
            'Team A': {
                'guids': ['GUID1', 'GUID2', ...],
                'names': ['Name1', 'Name2', ...],
                'maps': ['map1', 'map2', ...]
            },
            'Team B': { ... }
        }
        """
        try:
            import json
            
            # Check if session_teams table exists
            async with db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='session_teams'"
            ) as cursor:
                if not await cursor.fetchone():
                    return None
            
            # Get all teams for this session date
            async with db.execute(
                '''
                SELECT team_name, player_guids, player_names, map_name
                FROM session_teams
                WHERE session_start_date LIKE ?
                ORDER BY team_name
                ''',
                (f"{session_date}%",)
            ) as cursor:
                rows = await cursor.fetchall()
            
            if not rows:
                return None
            
            # Organize by team name
            teams = {}
            for team_name, guids_json, names_json, map_name in rows:
                if team_name not in teams:
                    teams[team_name] = {
                        'guids': set(json.loads(guids_json)),
                        'names': set(json.loads(names_json)),
                        'maps': []
                    }
                teams[team_name]['maps'].append(map_name)
            
            # Convert sets to sorted lists for consistency
            for team_name in teams:
                teams[team_name]['guids'] = sorted(list(teams[team_name]['guids']))
                teams[team_name]['names'] = sorted(list(teams[team_name]['names']))
            
            logger.info(f"✅ Found hardcoded teams for {session_date}: {list(teams.keys())}")
            return teams
            
        except Exception as e:
            logger.error(f"Error getting hardcoded teams: {e}", exc_info=True)
            return None


class UltimateETLegacyBot(commands.Bot):
    """🚀 Ultimate consolidated ET:Legacy Discord bot with proper Cog structure"""

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)

        # 📊 Database Configuration - Try multiple locations
        import os

        bot_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(bot_dir)
        
        # ✅ Try multiple database locations
        possible_paths = [
            os.path.join(parent_dir, 'etlegacy_production.db'),  # Project root
            os.path.join(bot_dir, 'etlegacy_production.db'),     # Bot directory
            'etlegacy_production.db',                             # Current dir
        ]
        
        self.db_path = None
        for path in possible_paths:
            if os.path.exists(path):
                self.db_path = path
                logger.info(f"✅ Database found: {path}")
                break
        
        if not self.db_path:
            error_msg = (
                f"❌ DATABASE NOT FOUND!\n"
                f"Tried: {possible_paths}\n"
                f"Run: python create_unified_database.py"
            )
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        # 🎮 Bot State
        self.current_session = None
        self.monitoring = False
        self.processed_files = set()
        self.auto_link_enabled = True
        self.gather_queue = {"3v3": [], "6v6": []}


        # 🤖 Automation System Flags (OFF by default for dev/testing)
        self.automation_enabled = os.getenv('AUTOMATION_ENABLED', 'false').lower() == 'true'
        self.ssh_enabled = os.getenv('SSH_ENABLED', 'false').lower() == 'true'
        
        if self.automation_enabled:
            logger.info("✅ Automation system ENABLED")
        else:
            logger.warning("⚠️ Automation system DISABLED (set AUTOMATION_ENABLED=true to enable)")
        # �️ Voice Channel Session Detection
        self.session_active = False
        self.session_start_time = None
        self.session_participants = set()  # Discord user IDs
        self.session_end_timer = None  # For 5-minute buffer
        self.gaming_sessions_db_id = None  # Link to gaming_sessions table
        
        # Load gaming voice channel IDs from .env
        gaming_channels_str = os.getenv('GAMING_VOICE_CHANNELS', '')
        self.gaming_voice_channels = [
            int(ch.strip()) for ch in gaming_channels_str.split(',') if ch.strip()
        ] if gaming_channels_str else []
        
        # Session thresholds
        self.session_start_threshold = int(os.getenv('SESSION_START_THRESHOLD', '6'))
        self.session_end_threshold = int(os.getenv('SESSION_END_THRESHOLD', '2'))
        self.session_end_delay = int(os.getenv('SESSION_END_DELAY', '300'))  # 5 minutes
        
        if self.gaming_voice_channels:
            logger.info(f"🎙️ Voice monitoring enabled for channels: {self.gaming_voice_channels}")
            logger.info(f"📊 Thresholds: {self.session_start_threshold}+ to start, <{self.session_end_threshold} for {self.session_end_delay}s to end")
        else:
            logger.warning("⚠️ No gaming voice channels configured - voice detection disabled")

        # �🏆 Awards and achievements tracking
        self.awards_cache = {}
        self.mvp_cache = {}

        # 📈 Performance tracking
        self.command_stats = {}
        self.error_count = 0

    async def validate_database_schema(self):
        """
        ✅ CRITICAL: Validate database has correct unified schema (53 columns)
        Prevents silent failures if wrong schema is used
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Check player_comprehensive_stats has 53 columns
                cursor = await db.execute(
                    "PRAGMA table_info(player_comprehensive_stats)"
                )
                columns = await cursor.fetchall()
                
                expected_columns = 53
                actual_columns = len(columns)
                
                if actual_columns != expected_columns:
                    error_msg = (
                        f"❌ DATABASE SCHEMA MISMATCH!\n"
                        f"Expected: {expected_columns} columns (UNIFIED)\n"
                        f"Found: {actual_columns} columns\n\n"
                        f"Schema: {'SPLIT (deprecated)' if actual_columns == 35 else 'UNKNOWN'}\n\n"
                        f"Solution:\n"
                        f"1. Backup: cp etlegacy_production.db backup.db\n"
                        f"2. Create: python create_unified_database.py\n"
                        f"3. Import: python tools/simple_bulk_import.py local_stats/*.txt\n"
                    )
                    
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)
                
                # Verify objective stats columns exist
                column_names = [col[1] for col in columns]
                required_stats = [
                    'kill_assists', 'dynamites_planted', 'times_revived',
                    'revives_given', 'most_useful_kills', 'useless_kills'
                ]
                
                missing = [col for col in required_stats if col not in column_names]
                if missing:
                    logger.error(f"❌ MISSING COLUMNS: {missing}")
                    raise RuntimeError(f"Missing objective stats: {missing}")
                
                logger.info(f"✅ Schema validated: {actual_columns} columns (UNIFIED)")
                
        except Exception as e:
            logger.error(f"❌ Schema validation failed: {e}")
            raise

    def safe_divide(self, numerator, denominator, default=0.0):
        """✅ NULL-safe division"""
        try:
            if numerator is None or denominator is None or denominator == 0:
                return default
            return numerator / denominator
        except (TypeError, ZeroDivisionError):
            return default

    def safe_percentage(self, part, total, default=0.0):
        """✅ NULL-safe percentage (returns 0-100)"""
        result = self.safe_divide(part, total, default)
        return result * 100 if result != default else default

    def safe_dpm(self, damage, time_seconds, default=0.0):
        """✅ NULL-safe DPM calculation: (damage * 60) / time_seconds"""
        try:
            if damage is None or time_seconds is None or time_seconds == 0:
                return default
            return (damage * 60) / time_seconds
        except (TypeError, ZeroDivisionError):
            return default

    async def send_with_delay(self, ctx, *args, delay=0.5, **kwargs):
        """✅ Send message with rate limit delay"""
        await ctx.send(*args, **kwargs)
        await asyncio.sleep(delay)

    async def setup_hook(self):
        """🔧 Initialize all bot components"""
        logger.info("🚀 Initializing Ultimate ET:Legacy Bot...")

        # ✅ CRITICAL: Validate schema FIRST
        await self.validate_database_schema()

        # Add the commands cog
        await self.add_cog(ETLegacyCommands(self))

        # 🎯 FIVEEYES: Load synergy analytics cog (SAFE - disabled by default)
        try:
            await self.load_extension('cogs.synergy_analytics')
            logger.info("✅ FIVEEYES synergy analytics cog loaded (disabled by default)")
        except Exception as e:
            logger.warning(f"⚠️  Could not load FIVEEYES cog: {e}")
            logger.warning("Bot will continue without synergy analytics features")

        # Initialize database
        await self.initialize_database()
        
        # Sync existing local files to processed_files table
        await self.sync_local_files_to_processed_table()

        # Start background tasks
        self.endstats_monitor.start()
        self.cache_refresher.start()
        self.scheduled_monitoring_check.start()
        self.voice_session_monitor.start()
        logger.info("✅ Background tasks started")

        logger.info("✅ Ultimate Bot initialization complete!")
        logger.info(f"📋 Commands available: {[cmd.name for cmd in self.commands]}")

    async def initialize_database(self):
        """📊 Verify database tables exist (created by recreate_database.py)"""
        async with aiosqlite.connect(self.db_path) as db:
            # Verify critical tables exist
            required_tables = [
                'sessions',
                'player_comprehensive_stats',
                'weapon_comprehensive_stats',
                'player_links',
                'processed_files',
            ]

            cursor = await db.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name IN (?, ?, ?, ?, ?)
            """,
                tuple(required_tables),
            )

            existing_tables = [row[0] for row in await cursor.fetchall()]

            missing_tables = set(required_tables) - set(existing_tables)

            if missing_tables:
                logger.error(f"❌ Missing required tables: {missing_tables}")
                logger.error("   Run: python recreate_database.py")
                logger.error("   Then: python tools/simple_bulk_import.py")
                raise Exception(f"Database missing required tables: {missing_tables}")

            logger.info(f"✅ Database verified - all {len(required_tables)} required tables exist")

    # 🎙️ VOICE CHANNEL SESSION DETECTION

    async def on_voice_state_update(self, member, before, after):
        """🎙️ Detect gaming sessions based on voice channel activity"""
        if not self.automation_enabled:
            return  # Automation disabled
        
        if not self.gaming_voice_channels:
            return  # Voice detection disabled
        
        try:
            # Count players in gaming voice channels
            total_players = 0
            current_participants = set()
            
            for channel_id in self.gaming_voice_channels:
                channel = self.get_channel(channel_id)
                if channel and isinstance(channel, discord.VoiceChannel):
                    total_players += len(channel.members)
                    current_participants.update([m.id for m in channel.members])
            
            logger.debug(f"🎙️ Voice update: {total_players} players in gaming channels")
            
            # Session Start Detection
            if total_players >= self.session_start_threshold and not self.session_active:
                await self._start_gaming_session(current_participants)
            
            # Session End Detection
            elif total_players < self.session_end_threshold and self.session_active:
                # Cancel existing timer if any
                if self.session_end_timer:
                    self.session_end_timer.cancel()
                
                # Start 5-minute countdown
                self.session_end_timer = asyncio.create_task(
                    self._delayed_session_end(current_participants)
                )
            
            # Update participants if session active
            elif self.session_active:
                # Add new participants
                new_participants = current_participants - self.session_participants
                if new_participants:
                    self.session_participants.update(new_participants)
                    logger.info(f"👥 New participants joined: {len(new_participants)}")
                
                # Cancel end timer if people came back
                if self.session_end_timer and total_players >= self.session_end_threshold:
                    self.session_end_timer.cancel()
                    self.session_end_timer = None
                    logger.info(f"⏰ Session end cancelled - players returned ({total_players} in voice)")
        
        except Exception as e:
            logger.error(f"Voice state update error: {e}", exc_info=True)

    async def _start_gaming_session(self, participants):
        """🎮 Start a gaming session when 6+ players in voice"""
        try:
            self.session_active = True
            self.session_start_time = discord.utils.utcnow()
            self.session_participants = participants.copy()
            
            # Enable monitoring
            self.monitoring = True
            
            # Create database entry
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute('''
                    INSERT INTO gaming_sessions (
                        start_time, participant_count, participants, status
                    ) VALUES (?, ?, ?, 'active')
                ''', (
                    self.session_start_time.isoformat(),
                    len(participants),
                    ','.join(str(uid) for uid in participants)
                ))
                self.gaming_sessions_db_id = cursor.lastrowid
                await db.commit()
            
            logger.info(f"🎮 GAMING SESSION STARTED! {len(participants)} players detected")
            logger.info(f"📊 Session ID: {self.gaming_sessions_db_id}")
            logger.info(f"🔄 Monitoring enabled")
            
            # Post to Discord if stats channel configured
            stats_channel_id = os.getenv('STATS_CHANNEL_ID')
            if stats_channel_id:
                channel = self.get_channel(int(stats_channel_id))
                if channel:
                    embed = discord.Embed(
                        title="🎮 Gaming Session Started!",
                        description=f"{len(participants)} players detected in voice channels",
                        color=0x00FF00,
                        timestamp=self.session_start_time
                    )
                    embed.add_field(
                        name="Status",
                        value="Monitoring enabled automatically",
                        inline=False
                    )
                    embed.set_footer(text="Good luck and have fun! �")
                    await channel.send(embed=embed)
        
        except Exception as e:
            logger.error(f"Error starting gaming session: {e}", exc_info=True)

    async def _delayed_session_end(self, last_participants):
        """⏰ Wait 5 minutes before ending session (allows bathroom breaks)"""
        try:
            logger.info(f"⏰ Session end timer started - waiting {self.session_end_delay}s...")
            await asyncio.sleep(self.session_end_delay)
            
            # Re-check player count after delay
            total_players = 0
            for channel_id in self.gaming_voice_channels:
                channel = self.get_channel(channel_id)
                if channel and isinstance(channel, discord.VoiceChannel):
                    total_players += len(channel.members)
            
            if total_players >= self.session_end_threshold:
                logger.info(f"⏰ Session end cancelled - players returned ({total_players} in voice)")
                return
            
            # Still empty after delay - end session
            await self._end_gaming_session()
        
        except asyncio.CancelledError:
            logger.debug("⏰ Session end timer cancelled")
        except Exception as e:
            logger.error(f"Error in delayed session end: {e}", exc_info=True)

    async def _end_gaming_session(self):
        """🏁 End gaming session and post summary"""
        try:
            if not self.session_active:
                return
            
            end_time = discord.utils.utcnow()
            duration = end_time - self.session_start_time
            
            # Update database
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    UPDATE gaming_sessions
                    SET end_time = ?, duration_seconds = ?, status = 'ended'
                    WHERE session_id = ?
                ''', (
                    end_time.isoformat(),
                    int(duration.total_seconds()),
                    self.gaming_sessions_db_id
                ))
                await db.commit()
            
            # Disable monitoring
            self.monitoring = False
            
            logger.info(f"🏁 GAMING SESSION ENDED!")
            logger.info(f"⏱️ Duration: {duration}")
            logger.info(f"👥 Participants: {len(self.session_participants)}")
            logger.info(f"�🔄 Monitoring disabled")
            
            # Post session summary (will be implemented in next todo)
            stats_channel_id = os.getenv('STATS_CHANNEL_ID')
            if stats_channel_id:
                channel = self.get_channel(int(stats_channel_id))
                if channel:
                    # TODO: Post comprehensive session summary
                    embed = discord.Embed(
                        title="🏁 Gaming Session Complete!",
                        description=f"Duration: {self._format_duration(duration)}",
                        color=0xFFD700,
                        timestamp=end_time
                    )
                    embed.add_field(
                        name="👥 Participants",
                        value=f"{len(self.session_participants)} players",
                        inline=True
                    )
                    embed.set_footer(text="Thanks for playing! GG! 🎮")
                    await channel.send(embed=embed)
            
            # Reset session state
            self.session_active = False
            self.session_start_time = None
            self.session_participants = set()
            self.session_end_timer = None
            self.gaming_sessions_db_id = None
        
        except Exception as e:
            logger.error(f"Error ending gaming session: {e}", exc_info=True)

    def _format_duration(self, duration):
        """Format timedelta as human-readable string"""
        total_seconds = int(duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        
        if hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"

    # � SSH MONITORING HELPER METHODS
    
    def parse_gamestats_filename(self, filename):
        """
        Parse gamestats filename to extract metadata
        
        Format: YYYY-MM-DD-HHMMSS-<map_name>-round-<N>.txt
        Example: 2025-10-02-232818-erdenberg_t2-round-2.txt
        
        Returns:
            dict with keys: date, time, map_name, round_number, etc.
        """
        import re
        pattern = r'^(\d{4}-\d{2}-\d{2})-(\d{6})-(.+?)-round-(\d+)\.txt$'
        match = re.match(pattern, filename)
        
        if not match:
            return None
        
        date, time, map_name, round_num = match.groups()
        round_number = int(round_num)
        
        return {
            'date': date,
            'time': time,
            'map_name': map_name,
            'round_number': round_number,
            'is_round_1': round_number == 1,
            'is_round_2': round_number == 2,
            'is_map_complete': round_number == 2,
            'full_timestamp': f"{date} {time[:2]}:{time[2:4]}:{time[4:6]}",
            'filename': filename
        }
    
    async def ssh_list_remote_files(self, ssh_config):
        """List .txt files on remote SSH server"""
        try:
            import paramiko
            
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            files = await loop.run_in_executor(
                None,
                self._ssh_list_files_sync,
                ssh_config
            )
            return files
            
        except Exception as e:
            logger.error(f"❌ SSH list files failed: {e}")
            return []
    
    def _ssh_list_files_sync(self, ssh_config):
        """Synchronous SSH file listing"""
        import paramiko
        
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        key_path = os.path.expanduser(ssh_config['key_path'])
        
        ssh.connect(
            hostname=ssh_config['host'],
            port=ssh_config['port'],
            username=ssh_config['user'],
            key_filename=key_path,
            timeout=10
        )
        
        sftp = ssh.open_sftp()
        files = sftp.listdir(ssh_config['remote_path'])
        # Filter: only .txt files, exclude obsolete _ws.txt files
        txt_files = [
            f for f in files 
            if f.endswith('.txt') and not f.endswith('_ws.txt')
        ]
        
        sftp.close()
        ssh.close()
        
        return txt_files
    
    async def ssh_download_file(self, ssh_config, filename,
                                local_dir='local_stats'):
        """Download a single file from remote server"""
        try:
            # Ensure local directory exists
            os.makedirs(local_dir, exist_ok=True)
            
            # Run in executor
            loop = asyncio.get_event_loop()
            local_path = await loop.run_in_executor(
                None,
                self._ssh_download_file_sync,
                ssh_config,
                filename,
                local_dir
            )
            return local_path
            
        except Exception as e:
            logger.error(f"❌ SSH download failed for {filename}: {e}")
            return None
    
    def _ssh_download_file_sync(self, ssh_config, filename, local_dir):
        """Synchronous SSH file download"""
        import paramiko
        
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        key_path = os.path.expanduser(ssh_config['key_path'])
        
        ssh.connect(
            hostname=ssh_config['host'],
            port=ssh_config['port'],
            username=ssh_config['user'],
            key_filename=key_path,
            timeout=10
        )
        
        sftp = ssh.open_sftp()
        
        remote_file = f"{ssh_config['remote_path']}/{filename}"
        local_file = os.path.join(local_dir, filename)
        
        logger.info(f"📥 Downloading {filename}...")
        sftp.get(remote_file, local_file)
        
        sftp.close()
        ssh.close()
        
        return local_file
    
    async def process_gamestats_file(self, local_path, filename):
        """
        Process a gamestats file: parse and import to database
        
        Returns:
            dict with keys: success, session_id, player_count, error
        """
        try:
            from community_stats_parser import C0RNP0RN3StatsParser
            
            logger.info(f"⚙️ Processing {filename}...")
            
            # Parse using existing parser (it reads the file itself)
            parser = C0RNP0RN3StatsParser()
            stats_data = parser.parse_stats_file(local_path)
            
            if not stats_data or stats_data.get('error'):
                error_msg = stats_data.get('error') if stats_data else "No data"
                raise Exception(f"Parser error: {error_msg}")
            
            # Import to database using existing import logic
            session_id = await self._import_stats_to_db(
                stats_data,
                filename
            )
            
            return {
                'success': True,
                'session_id': session_id,
                'player_count': len(stats_data.get('players', [])),
                'error': None,
                'stats_data': stats_data
            }
            
        except Exception as e:
            logger.error(f"❌ Processing failed: {e}")
            return {
                'success': False,
                'session_id': None,
                'player_count': 0,
                'error': str(e),
                'stats_data': None
            }
    
    async def _import_stats_to_db(self, stats_data, filename):
        """Import parsed stats to database"""
        try:
            logger.info(f"📊 Importing {len(stats_data.get('players', []))} "
                       f"players to database...")
            
            # Extract date from filename: YYYY-MM-DD-HHMMSS-mapname-round-N.txt
            timestamp = '-'.join(filename.split('-')[:4])  # Full timestamp
            date_part = '-'.join(filename.split('-')[:3])  # Date for stats
            
            async with aiosqlite.connect(self.db_path) as db:
                # Insert session
                cursor = await db.execute('''
                    SELECT id FROM sessions
                    WHERE session_date = ? AND map_name = ? AND round_number = ?
                ''', (timestamp, stats_data['map_name'], stats_data['round_num']))
                
                existing = await cursor.fetchone()
                if existing:
                    logger.info(f"⚠️ Session already exists (ID: {existing[0]})")
                    return existing[0]
                
                # Insert new session
                cursor = await db.execute('''
                    INSERT INTO sessions (
                        session_date, map_name, round_number,
                        time_limit, actual_time
                    ) VALUES (?, ?, ?, ?, ?)
                ''', (
                    timestamp,
                    stats_data['map_name'],
                    stats_data['round_num'],
                    stats_data.get('map_time', ''),
                    stats_data.get('actual_time', '')
                ))
                
                session_id = cursor.lastrowid
                
                # Insert player stats
                for player in stats_data.get('players', []):
                    await self._insert_player_stats(
                        db, session_id, date_part, stats_data, player
                    )
                
                await db.commit()
                
                logger.info(f"✅ Imported session {session_id} with "
                           f"{len(stats_data.get('players', []))} players")
                
                return session_id
                
        except Exception as e:
            logger.error(f"❌ Database import failed: {e}")
            raise
    
    async def _insert_player_stats(self, db, session_id, session_date,
                                   result, player):
        """Insert player comprehensive stats"""
        obj_stats = player.get('objective_stats', {})
        
        # Time fields - seconds is primary
        time_seconds = player.get('time_played_seconds', 0)
        time_minutes = time_seconds / 60.0 if time_seconds > 0 else 0.0
        
        # DPM already calculated by parser
        dpm = player.get('dpm', 0.0)
        
        # K/D ratio
        kills = player.get('kills', 0)
        deaths = player.get('deaths', 0)
        kd_ratio = kills / deaths if deaths > 0 else float(kills)
        
        # Efficiency
        bullets_fired = obj_stats.get('bullets_fired', 0)
        accuracy = (kills / bullets_fired * 100) if bullets_fired > 0 else 0.0
        
        # Time dead
        time_dead_mins = obj_stats.get('time_dead_ratio', 0) * time_minutes
        time_dead_ratio = obj_stats.get('time_dead_ratio', 0)
        
        values = (
            session_id, session_date, result['map_name'],
            result['round_num'],
            player.get('guid', 'UNKNOWN'),
            player.get('name', 'Unknown'),
            player.get('name', 'Unknown'),  # clean_name
            player.get('team', 0),
            kills, deaths,
            player.get('damage_given', 0),
            player.get('damage_received', 0),
            player.get('team_damage_given', 0),
            player.get('team_damage_received', 0),
            obj_stats.get('gibs', 0),
            obj_stats.get('self_kills', 0),
            obj_stats.get('team_kills', 0),
            obj_stats.get('team_gibs', 0),
            player.get('headshots', 0),
            time_seconds, time_minutes,
            time_dead_mins, time_dead_ratio,
            obj_stats.get('xp', 0),
            kd_ratio, dpm, accuracy,
            bullets_fired, accuracy,
            obj_stats.get('kill_assists', 0),
            0, 0,  # objectives_completed, objectives_destroyed
            obj_stats.get('objectives_stolen', 0),
            obj_stats.get('objectives_returned', 0),
            obj_stats.get('dynamites_planted', 0),
            obj_stats.get('dynamites_defused', 0),
            obj_stats.get('times_revived', 0),
            obj_stats.get('revives_given', 0),
            obj_stats.get('most_useful_kills', 0),
            obj_stats.get('useless_kills', 0),
            obj_stats.get('kill_steals', 0),
            obj_stats.get('denied_playtime', 0),
            0,  # constructions
            obj_stats.get('tank_meatshield', 0),
            obj_stats.get('double_kills', 0),
            obj_stats.get('triple_kills', 0),
            obj_stats.get('quad_kills', 0),
            obj_stats.get('multi_kills', 0),
            obj_stats.get('mega_kills', 0),
            obj_stats.get('killing_spree', 0),
            obj_stats.get('death_spree', 0)
        )
        
        await db.execute('''
            INSERT INTO player_comprehensive_stats (
                session_id, session_date, map_name, round_number,
                player_guid, player_name, clean_name, team,
                kills, deaths, damage_given, damage_received,
                team_damage_given, team_damage_received,
                gibs, self_kills, team_kills, team_gibs, headshot_kills,
                time_played_seconds, time_played_minutes,
                time_dead_minutes, time_dead_ratio,
                xp, kd_ratio, dpm, efficiency,
                bullets_fired, accuracy,
                kill_assists,
                objectives_completed, objectives_destroyed,
                objectives_stolen, objectives_returned,
                dynamites_planted, dynamites_defused,
                times_revived, revives_given,
                most_useful_kills, useless_kills, kill_steals,
                denied_playtime, constructions, tank_meatshield,
                double_kills, triple_kills, quad_kills,
                multi_kills, mega_kills,
                killing_spree_best, death_spree_worst
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        ''', values)
    
    async def post_round_summary(self, file_info, result):
        """
        Post round summary to Discord channel
        
        Handles:
        - Round 1 complete (single embed)
        - Round 2 complete (2 embeds: round summary + map summary)
        """
        try:
            channel = self.get_channel(self.stats_channel_id)
            if not channel:
                logger.error("❌ Stats channel not found")
                return
            
            stats_data = result.get('stats_data')
            if not stats_data:
                return
            
            # Round summary embed
            round_embed = discord.Embed(
                title=f"🎯 {file_info['map_name']} - "
                      f"Round {file_info['round_number']} Complete",
                color=0x00FF00,
                timestamp=datetime.now()
            )
            
            # Add top 3 players
            players = stats_data.get('players', [])[:3]
            top_players_text = "\n".join([
                f"**{i+1}.** {p['name']} - "
                f"{p.get('kills', 0)}K/{p.get('deaths', 0)}D "
                f"({p.get('dpm', 0):.0f} DPM)"
                for i, p in enumerate(players)
            ])
            
            round_embed.add_field(
                name="🏆 Top Performers",
                value=top_players_text or "No data",
                inline=False
            )
            
            await channel.send(embed=round_embed)
            
            # If round 2, also post map summary
            if file_info['is_map_complete']:
                await self.post_map_summary(file_info, stats_data)
            
            logger.info(f"✅ Posted round summary for "
                       f"{file_info['map_name']} R{file_info['round_number']}")
            
        except Exception as e:
            logger.error(f"❌ Failed to post round summary: {e}")
    
    async def post_map_summary(self, file_info, stats_data):
        """Post map summary after round 2 completes"""
        try:
            channel = self.get_channel(self.stats_channel_id)
            if not channel:
                return
            
            map_embed = discord.Embed(
                title=f"🗺️ {file_info['map_name']} - MAP COMPLETE",
                description="Both rounds finished!",
                color=0xFFD700,
                timestamp=datetime.now()
            )
            
            map_embed.add_field(
                name="📊 Status",
                value="Map completed - Check stats above for details",
                inline=False
            )
            
            await channel.send(embed=map_embed)
            
        except Exception as e:
            logger.error(f"❌ Failed to post map summary: {e}")


    async def should_process_file(self, filename):
        """
        Smart file processing decision (Hybrid Approach)
        
        Checks multiple sources to avoid re-processing:
        1. In-memory cache (fastest)
        2. Local file exists (fast)
        3. Processed files table (fast, persistent)
        4. Sessions table (slower, definitive)
        
        Returns:
            bool: True if file should be processed, False if already done
        """
        try:
            # 1. Check in-memory cache
            if filename in self.processed_files:
                return False
            
            # 2. Check if local file exists
            local_path = os.path.join('local_stats', filename)
            if os.path.exists(local_path):
                logger.debug(f"⏭️ {filename} exists locally, marking processed")
                self.processed_files.add(filename)
                await self._mark_file_processed(filename, success=True)
                return False
            
            # 3. Check processed_files table
            if await self._is_in_processed_files_table(filename):
                logger.debug(f"⏭️ {filename} in processed_files table")
                self.processed_files.add(filename)
                return False
            
            # 4. Check if session exists in database
            if await self._session_exists_in_db(filename):
                logger.debug(f"⏭️ {filename} session exists in DB")
                self.processed_files.add(filename)
                await self._mark_file_processed(filename, success=True)
                return False
            
            # File is truly new!
            return True
            
        except Exception as e:
            logger.error(f"Error checking if should process {filename}: {e}")
            return False  # Skip on error to be safe
    
    async def _is_in_processed_files_table(self, filename):
        """Check if filename exists in processed_files table"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    '''SELECT 1 FROM processed_files 
                       WHERE filename = ? AND success = 1''',
                    (filename,)
                )
                result = await cursor.fetchone()
                return result is not None
        except Exception as e:
            logger.debug(f"Error checking processed_files table: {e}")
            return False
    
    async def _session_exists_in_db(self, filename):
        """
        Check if session exists in database by parsing filename
        
        Filename format: YYYY-MM-DD-HHMMSS-mapname-round-N.txt
        """
        try:
            file_info = self.parse_gamestats_filename(filename)
            if not file_info:
                return False
            
            # Use full timestamp for unique identification
            timestamp = '-'.join(filename.split('-')[:4])
            
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute('''
                    SELECT 1 FROM sessions
                    WHERE session_date = ? 
                      AND map_name = ? 
                      AND round_number = ?
                    LIMIT 1
                ''', (timestamp, 
                      file_info['map_name'], 
                      file_info['round_number']))
                
                result = await cursor.fetchone()
                return result is not None
                
        except Exception as e:
            logger.debug(f"Error checking session in DB: {e}")
            return False
    
    async def _mark_file_processed(self, filename, success=True, 
                                    error_msg=None):
        """
        Mark a file as processed in the processed_files table
        
        Args:
            filename: Name of the processed file
            success: Whether processing was successful
            error_msg: Error message if processing failed
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT OR REPLACE INTO processed_files 
                    (filename, success, error_message, processed_at)
                    VALUES (?, ?, ?, ?)
                ''', (
                    filename,
                    1 if success else 0,
                    error_msg,
                    datetime.now().isoformat()
                ))
                await db.commit()
                
        except Exception as e:
            logger.debug(f"Error marking file as processed: {e}")
    
    async def sync_local_files_to_processed_table(self):
        """
        One-time sync: Add existing local_stats files to processed_files
        
        Call this during bot startup to populate the table with 
        already-downloaded files
        """
        try:
            local_dir = 'local_stats'
            if not os.path.exists(local_dir):
                return
            
            files = [f for f in os.listdir(local_dir) if f.endswith('.txt')]
            
            if not files:
                return
            
            logger.info(
                f"🔄 Syncing {len(files)} local files to "
                f"processed_files table..."
            )
            
            synced = 0
            async with aiosqlite.connect(self.db_path) as db:
                for filename in files:
                    # Check if already in table
                    cursor = await db.execute(
                        'SELECT 1 FROM processed_files WHERE filename = ?',
                        (filename,)
                    )
                    if await cursor.fetchone():
                        continue  # Already tracked
                    
                    # Add to table
                    await db.execute('''
                        INSERT INTO processed_files 
                        (filename, success, error_message, processed_at)
                        VALUES (?, 1, NULL, ?)
                    ''', (filename, datetime.now().isoformat()))
                    
                    self.processed_files.add(filename)
                    synced += 1
                
                await db.commit()
            
            if synced > 0:
                logger.info(
                    f"✅ Synced {synced} local files to "
                    f"processed_files table"
                )
            
        except Exception as e:
            logger.error(f"Error syncing local files: {e}")
    
    async def _auto_end_session(self):
        """Auto-end session and post summary"""
        try:
            logger.info("🏁 Auto-ending gaming session...")
            
            # Mark session as ended
            self.session_active = False
            self.session_end_timer = None
            
            # Post session summary to Discord
            channel = self.get_channel(self.stats_channel_id)
            if not channel:
                logger.error("❌ Stats channel not found")
                return
            
            # Create session end notification
            embed = discord.Embed(
                title="🏁 Gaming Session Ended",
                description=(
                    "All players have left voice channels.\n"
                    "Generating session summary..."
                ),
                color=0xFF8800,
                timestamp=datetime.now()
            )
            await channel.send(embed=embed)
            
            # Generate and post !last_session summary
            # (Reuse the last_session command logic)
            try:
                # Query database for most recent session
                async with aiosqlite.connect(self.db_path) as db:
                    # Get most recent session data
                    cursor = await db.execute('''
                        SELECT DISTINCT DATE(session_date) as date
                        FROM player_comprehensive_stats
                        ORDER BY date DESC
                        LIMIT 1
                    ''')
                    row = await cursor.fetchone()
                    
                    if row:
                        session_date = row[0]
                        logger.info(
                            f"📊 Posting auto-summary for {session_date}"
                        )
                        
                        # Use last_session logic to generate embeds
                        # (This would call the existing last_session code)
                        await channel.send(
                            f"📊 **Session Summary for {session_date}**\n"
                            f"Use `!last_session` for full details!"
                        )
                
                logger.info("✅ Session auto-ended successfully")
                
            except Exception as e:
                logger.error(f"❌ Failed to generate session summary: {e}")
                await channel.send(
                    "⚠️ Session ended but summary generation failed. "
                    "Use `!last_session` for details."
                )
        
        except Exception as e:
            logger.error(f"Auto-end session error: {e}")

    # ==================== BACKGROUND TASKS ====================

    @tasks.loop(seconds=30)
    async def endstats_monitor(self):
        """
        🔄 SSH Monitoring Task - Runs every 30 seconds
        
        Monitors remote game server for new stats files:
        1. Lists files on remote server via SSH
        2. Compares with processed_files tracking
        3. Downloads new files
        4. Parses and imports to database
        5. Posts Discord round summaries
        """
        if not self.monitoring or not self.ssh_enabled:
            return
        
        try:
            # Build SSH config
            ssh_config = {
                'host': os.getenv('SSH_HOST'),
                'port': int(os.getenv('SSH_PORT', 22)),
                'user': os.getenv('SSH_USER'),
                'key_path': os.getenv('SSH_KEY_PATH', ''),
                'remote_path': os.getenv('REMOTE_STATS_PATH')
            }
            
            # Validate SSH config
            if not all([ssh_config['host'], ssh_config['user'],
                       ssh_config['key_path'], ssh_config['remote_path']]):
                logger.warning("⚠️ SSH config incomplete - monitoring disabled")
                return
            
            # List remote files
            remote_files = await self.ssh_list_remote_files(ssh_config)
            
            if not remote_files:
                return
            
            # Check each file
            for filename in remote_files:
                # Check if already processed (4-layer check)
                if await self.should_process_file(filename):
                    logger.info(f"📥 New file detected: {filename}")
                    
                    # Download file
                    local_path = await self.ssh_download_file(
                        ssh_config, filename, 'local_stats'
                    )
                    
                    if local_path:
                        # Wait 3 seconds for file to fully write
                        await asyncio.sleep(3)
                        
                        # Process the file
                        await self.process_gamestats_file(local_path, filename)
                    
        except Exception as e:
            logger.error(f"❌ endstats_monitor error: {e}")
    
    @endstats_monitor.before_loop
    async def before_endstats_monitor(self):
        """Wait for bot to be ready before starting SSH monitoring"""
        await self.wait_until_ready()
        logger.info("✅ SSH monitoring task ready")

    @tasks.loop(seconds=30)
    async def cache_refresher(self):
        """
        🔄 Cache Refresh Task - Runs every 30 seconds
        
        Keeps in-memory cache in sync with database
        """
        try:
            # Refresh processed files cache
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    'SELECT filename FROM processed_files WHERE success = 1'
                )
                rows = await cursor.fetchall()
                self.processed_files = {row[0] for row in rows}
                
        except Exception as e:
            logger.debug(f"Cache refresh error: {e}")
    
    @cache_refresher.before_loop
    async def before_cache_refresher(self):
        """Wait for bot to be ready"""
        await self.wait_until_ready()

    @tasks.loop(minutes=1)
    async def scheduled_monitoring_check(self):
        """
        ⏰ Scheduled Monitoring - Runs every 1 minute
        
        Auto-starts monitoring at 20:00 CET daily
        No manual !session_start needed!
        """
        if not self.ssh_enabled:
            return
        
        try:
            import pytz
            cet = pytz.timezone('Europe/Paris')
            now = datetime.now(cet)
            
            # Check if it's 20:00 CET
            if now.hour == 20 and now.minute == 0:
                if not self.monitoring:
                    logger.info("⏰ 20:00 CET - Auto-starting monitoring!")
                    self.monitoring = True
                    
                    # Post notification to Discord
                    channel = self.get_channel(self.stats_channel_id)
                    if channel:
                        embed = discord.Embed(
                            title="🎮 Monitoring Started",
                            description=(
                                "Automatic monitoring enabled at 20:00 CET!\n\n"
                                "Round summaries will be posted automatically "
                                "when games are played."
                            ),
                            color=0x00FF00,
                            timestamp=datetime.now()
                        )
                        await channel.send(embed=embed)
                    
                    logger.info("✅ Monitoring auto-started at 20:00 CET")
                    
        except Exception as e:
            logger.error(f"Scheduled monitoring error: {e}")
    
    @scheduled_monitoring_check.before_loop
    async def before_scheduled_monitoring(self):
        """Wait for bot to be ready"""
        await self.wait_until_ready()

    @tasks.loop(seconds=30)
    async def voice_session_monitor(self):
        """
        🎙️ Voice Session Monitor - Runs every 30 seconds
        
        Monitors voice channels for session end:
        - Counts players in gaming voice channels
        - Starts 3-minute timer when players drop below threshold
        - Auto-ends session and posts summary
        - Cancels timer if players return
        """
        if not self.automation_enabled:
            return
        
        try:
            # Count players in gaming voice channels
            total_players = 0
            for channel_id in self.gaming_voice_channels:
                channel = self.get_channel(channel_id)
                if channel and hasattr(channel, 'members'):
                    # Count non-bot members
                    total_players += sum(
                        1 for m in channel.members if not m.bot
                    )
            
            # Check if below threshold
            if total_players < self.session_end_threshold:
                if self.session_active and not self.session_end_timer:
                    # Start timer
                    self.session_end_timer = datetime.now()
                    logger.info(
                        f"⏱️ Session end timer started "
                        f"({total_players} < {self.session_end_threshold})"
                    )
                    
                elif self.session_end_timer:
                    # Check if timer expired
                    elapsed = (datetime.now() - self.session_end_timer).seconds
                    if elapsed >= self.session_end_delay:
                        logger.info("🏁 3 minutes elapsed - auto-ending session")
                        await self._auto_end_session()
            else:
                # Players returned - cancel timer
                if self.session_end_timer:
                    logger.info(
                        f"⏰ Session end cancelled - players returned "
                        f"({total_players})"
                    )
                    self.session_end_timer = None
                    
        except Exception as e:
            logger.error(f"Voice monitor error: {e}")
    
    @voice_session_monitor.before_loop
    async def before_voice_monitor(self):
        """Wait for bot to be ready"""
        await self.wait_until_ready()

    # ==================== BOT EVENTS ====================

    async def on_ready(self):
        """✅ Bot startup message"""
        logger.info(f'🚀 Ultimate ET:Legacy Bot logged in as {self.user}')
        logger.info(f'📊 Connected to database: {self.db_path}')
        logger.info(f'🎮 Bot ready with {len(list(self.commands))} commands!')

        # Clear any old slash commands to avoid confusion
        try:
            self.tree.clear_commands(guild=None)
            await self.tree.sync()
            logger.info("🧹 Cleared old slash commands")
        except Exception as e:
            logger.warning(f"Could not clear slash commands: {e}")

    async def on_command_error(self, ctx, error):
        """🚨 Handle command errors"""
        self.error_count += 1

        if isinstance(error, commands.CommandNotFound):
            await ctx.send("❌ Command not found. Use `!help_command` for available commands.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Missing argument: {error.param}. Use `!help_command` for usage.")
        else:
            logger.error(f"Command error: {error}")
            await ctx.send(f"❌ An error occurred: {error}")


# 🚀 BOT STARTUP
def main():
    """🚀 Start the Ultimate ET:Legacy Discord Bot"""

    # Get Discord token
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        logger.error("❌ DISCORD_BOT_TOKEN not found in environment variables!")
        logger.info("Please set your Discord bot token in the .env file")
        return

    # Create and run bot
    bot = UltimateETLegacyBot()

    try:
        logger.info("🚀 Starting Ultimate ET:Legacy Bot...")
        bot.run(token)
    except discord.LoginFailure:
        logger.error("❌ Invalid Discord token!")
    except Exception as e:
        logger.error(f"❌ Bot startup failed: {e}")


if __name__ == "__main__":
    main()

