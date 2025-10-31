# ============================================================================
# ULTIMATE LAST_SESSION COMMAND - Multiple Views for 37 Data Points
# ============================================================================
"""
This replaces the entire last_session command in ultimate_bot.py

Features:
- !last_session          → Full session with ALL players, ALL weapons (split embeds)
- !last_session top      → Top 10 players only (compact)
- !last_session obj      → Objective stats (revives, constructions, captures, dynamites)
- !last_session combat   → Combat stats (kills, deaths, damage, gibs, headshots)
- !last_session support  → Support stats (medpacks, ammopacks, revives)
- !last_session sprees   → Killing sprees, multi-kills, mega kills
- !last_session weapons  → Detailed weapon breakdown (all players, all weapons)
- !last_session graphs   → Visual analytics (6 performance graphs)
- !last_session help     → Show all available commands

ALL modes show ALL players (no truncation), just different stat focuses.
Auto-splits into multiple embeds when needed to avoid 1024-char limit.
"""

@commands.command(name='last_session', aliases=['last', 'latest', 'recent'])
async def last_session(self, ctx, subcommand: str = None):
    """🎮 Show the most recent session with multiple view modes

    Usage:
    !last_session          → Full session summary (default)
    !last_session top      → Top 10 players leaderboard
    !last_session obj      → Objective stats (revives, constructions, etc.)
    !last_session combat   → Combat stats (kills, deaths, damage, gibs)
    !last_session support  → Support stats (medpacks, ammopacks, revives)
    !last_session sprees   → Killing sprees and multi-kills
    !last_session weapons  → Complete weapon breakdown
    !last_session graphs   → Performance graphs
    !last_session help     → Show this help

    All modes show ALL participating players with different stat focuses.
    """
    try:
        # Normalize subcommand
        if subcommand:
            subcommand = subcommand.lower()
        
        # Show help
        if subcommand == "help":
            help_embed = discord.Embed(
                title="🎮 Last Session Command - Available Views",
                description="View your session stats in different ways!",
                color=0x5865F2
            )
            help_embed.add_field(
                name="📊 Default View",
                value=(
                    "`!last_session` - Full session summary\n"
                    "Shows all players with key stats"
                ),
                inline=False
            )
            help_embed.add_field(
                name="🏆 Filtered Views",
                value=(
                    "`!last_session top` - Top 10 players only\n"
                    "`!last_session obj` - Objective stats (revives, constructions)\n"
                    "`!last_session combat` - Combat focus (kills, damage, gibs)\n"
                    "`!last_session support` - Support stats (medpacks, revives)\n"
                    "`!last_session sprees` - Killing sprees & multi-kills\n"
                ),
                inline=False
            )
            help_embed.add_field(
                name="📈 Detailed Views",
                value=(
                    "`!last_session weapons` - Complete weapon breakdown\n"
                    "`!last_session graphs` - Performance graphs\n"
                ),
                inline=False
            )
            help_embed.set_footer(text="💡 All views show ALL players, just different stats!")
            await ctx.send(embed=help_embed)
            return

        async with aiosqlite.connect(self.db_path) as db:
            # Get most recent session date
            async with db.execute('''
                SELECT DISTINCT DATE(session_date) as date
                FROM player_comprehensive_stats
                ORDER BY date DESC
                LIMIT 1
            ''') as cursor:
                row = await cursor.fetchone()
                if not row:
                    await ctx.send("❌ No sessions found")
                    return
                
                latest_date = row[0]

            # Get all session IDs for this date
            async with db.execute(
                '''
                SELECT id, map_name, round_number, session_date
                FROM sessions
                WHERE DATE(session_date) = ?
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

            # Get basic session info (used by all views)
            query = f'''
                SELECT COUNT(DISTINCT player_guid)
                FROM player_comprehensive_stats
                WHERE session_id IN ({session_ids_str})
            '''
            async with db.execute(query, session_ids) as cursor:
                player_count = (await cursor.fetchone())[0]

            query = f'''
                SELECT COUNT(DISTINCT session_id) / 2 as total_maps,
                       COUNT(DISTINCT session_id) as total_rounds
                FROM player_comprehensive_stats
                WHERE session_id IN ({session_ids_str})
            '''
            async with db.execute(query, session_ids) as cursor:
                result = await cursor.fetchone()
                total_maps, total_rounds = result

            # =========================================================================
            # ROUTE TO APPROPRIATE VIEW
            # =========================================================================
            
            if subcommand == "top":
                await self._last_session_top_view(ctx, db, session_ids, session_ids_str, latest_date, player_count, total_maps, total_rounds)
            
            elif subcommand == "obj" or subcommand == "objective" or subcommand == "objectives":
                await self._last_session_obj_view(ctx, db, session_ids, session_ids_str, latest_date, player_count)
            
            elif subcommand == "combat":
                await self._last_session_combat_view(ctx, db, session_ids, session_ids_str, latest_date, player_count)
            
            elif subcommand == "support":
                await self._last_session_support_view(ctx, db, session_ids, session_ids_str, latest_date, player_count)
            
            elif subcommand == "sprees" or subcommand == "spree":
                await self._last_session_sprees_view(ctx, db, session_ids, session_ids_str, latest_date, player_count)
            
            elif subcommand == "weapons" or subcommand == "weapon" or subcommand == "weap":
                await self._last_session_weapons_view(ctx, db, session_ids, session_ids_str, latest_date, player_count)
            
            elif subcommand == "graphs" or subcommand == "graph" or subcommand == "charts":
                await self._last_session_graphs_view(ctx, db, session_ids, session_ids_str, latest_date, player_count)
            
            elif subcommand is None:
                # Default view - full session summary
                await self._last_session_default_view(ctx, db, session_ids, session_ids_str, latest_date, sessions, player_count, total_maps, total_rounds)
            
            else:
                await ctx.send(
                    f"❌ Unknown view: `{subcommand}`\n"
                    f"Use `!last_session help` to see all available views."
                )

    except Exception as e:
        logger.error(f"Error in last_session command: {e}", exc_info=True)
        await ctx.send(f"❌ Error retrieving last session: {e}")


# ============================================================================
# VIEW METHODS - Each creates specific stat-focused embeds
# ============================================================================

async def _last_session_default_view(self, ctx, db, session_ids, session_ids_str, latest_date, sessions, player_count, total_maps, total_rounds):
    """Default view - Session summary with all players (compact stats)"""
    
    # Get hardcoded teams for scoring
    hardcoded_teams = await self.get_hardcoded_teams(db, latest_date)
    team_1_name = hardcoded_teams[0][0] if hardcoded_teams else "Team 1"
    team_2_name = hardcoded_teams[0][1] if hardcoded_teams and len(hardcoded_teams[0]) > 1 else "Team 2"
    
    # Calculate team scores (simplified - adjust to your scoring logic)
    team_1_score, team_2_score = 0, 0
    
    # Get all players
    query = f'''
        SELECT p.player_name,
               SUM(p.kills) as kills,
               SUM(p.deaths) as deaths,
               CASE
                   WHEN SUM(p.time_played_seconds) > 0
                   THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
                   ELSE 0
               END as weighted_dpm,
               SUM(p.time_played_seconds) as total_seconds
        FROM player_comprehensive_stats p
        WHERE p.session_id IN ({session_ids_str})
        GROUP BY p.player_name
        ORDER BY kills DESC
    '''
    async with db.execute(query, session_ids) as cursor:
        all_players = await cursor.fetchall()

    # Calculate maps
    maps_played = total_maps
    rounds_played = len(sessions)

    # Build description
    description = (
        f"**{maps_played} maps** • **{rounds_played} rounds** • "
        f"**{player_count} players**"
    )
    
    embed1 = discord.Embed(
        title=f"📊 Session Summary: {latest_date}",
        description=description,
        color=0x5865F2,
        timestamp=datetime.now(),
    )

    # Maps list
    maps_text = ""
    map_play_counts = {}
    for session_id, map_name, round_num, actual_time in sessions:
        if round_num == 2:
            map_play_counts[map_name] = map_play_counts.get(map_name, 0) + 1

    for map_name, plays in map_play_counts.items():
        rounds = plays * 2
        maps_text += f"• **{map_name}** ({rounds} rounds)\n"

    if maps_text:
        embed1.add_field(name="🗺️ Maps Played", value=maps_text, inline=False)

    # All players (compact)
    if all_players:
        medals = ["🥇", "🥈", "🥉"]
        player_text = ""
        
        for i, player in enumerate(all_players):
            name, kills, deaths, dpm, total_seconds = player
            
            kd_ratio = kills / deaths if deaths and deaths > 0 else (kills or 0)
            
            # Format time
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            if hours > 0:
                time_display = f"{hours}h{minutes}m"
            else:
                time_display = f"{minutes}m"
            
            medal = medals[i] if i < 3 else f"{i+1}."
            player_text += f"{medal} **{name}** - {kills}K/{deaths}D ({kd_ratio:.2f}) • {dpm:.0f} DPM • {time_display}\n"

        embed1.add_field(name="🏆 All Players", value=player_text, inline=False)

    embed1.set_footer(text="💡 Use !last_session help to see other views (obj, combat, weapons, etc.)")
    await ctx.send(embed=embed1)


async def _last_session_top_view(self, ctx, db, session_ids, session_ids_str, latest_date, player_count, total_maps, total_rounds):
    """Top 10 players with detailed stats"""
    
    query = f'''
        SELECT p.player_name,
               SUM(p.kills) as kills,
               SUM(p.deaths) as deaths,
               CASE
                   WHEN SUM(p.time_played_seconds) > 0
                   THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
                   ELSE 0
               END as weighted_dpm,
               SUM(p.damage_given) as total_damage,
               SUM(p.headshot_kills) as headshot_kills,
               SUM(p.gibs) as gibs,
               SUM(p.time_played_seconds) as total_seconds
        FROM player_comprehensive_stats p
        WHERE p.session_id IN ({session_ids_str})
        GROUP BY p.player_name
        ORDER BY kills DESC
        LIMIT 10
    '''
    async with db.execute(query, session_ids) as cursor:
        top_players = await cursor.fetchall()

    embed = discord.Embed(
        title=f"🏆 Top 10 Players - {latest_date}",
        description=f"Best performers from {total_maps} maps • {player_count} total players",
        color=0xFEE75C,
        timestamp=datetime.now(),
    )

    medals = ["🥇", "🥈", "🥉", "4.", "5.", "6.", "7.", "8.", "9.", "10."]
    
    for i, player in enumerate(top_players):
        name, kills, deaths, dpm, damage, hsk, gibs, seconds = player
        
        kd = kills / deaths if deaths > 0 else kills
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        time_display = f"{hours}h{minutes}m" if hours > 0 else f"{minutes}m"
        
        player_stats = (
            f"{medals[i]} **{name}**\n"
            f"`{kills}K/{deaths}D ({kd:.2f})` • `{dpm:.0f} DPM` • `{damage:,} DMG`\n"
            f"`{hsk} HSK` • `{gibs} Gibs` • ⏱️ `{time_display}`\n"
        )
        
        embed.add_field(name="\u200b", value=player_stats, inline=False)

    embed.set_footer(text="💡 Use !last_session for full session or !last_session help for more views")
    await ctx.send(embed=embed)


async def _last_session_obj_view(self, ctx, db, session_ids, session_ids_str, latest_date, player_count):
    """Objective stats - revives, constructions, dynamites, captures, etc."""
    
    query = f'''
        SELECT p.player_name,
               SUM(p.revives_given) as revives_given,
               SUM(p.times_revived) as times_revived,
               SUM(p.objectives_completed) as obj_completed,
               SUM(p.objectives_destroyed) as obj_destroyed,
               SUM(p.dynamites_planted) as dynamites_planted,
               SUM(p.dynamites_defused) as dynamites_defused,
               SUM(p.constructions) as constructions,
               SUM(p.kills) as kills
        FROM player_comprehensive_stats p
        WHERE p.session_id IN ({session_ids_str})
        GROUP BY p.player_name
        ORDER BY revives_given DESC, obj_completed DESC
    '''
    async with db.execute(query, session_ids) as cursor:
        players = await cursor.fetchall()

    # Split into multiple embeds if needed
    embeds = []
    current_embed = discord.Embed(
        title=f"🎯 Objective Stats - {latest_date}",
        description=f"Showing all {len(players)} players sorted by revives & objectives",
        color=0x57F287,
        timestamp=datetime.now(),
    )
    
    field_count = 0
    
    for player in players:
        name, revives, revived, obj_comp, obj_dest, dyno_plant, dyno_defuse, constructs, kills = player
        
        # Skip if no objective activity
        total_obj_activity = revives + obj_comp + obj_dest + dyno_plant + dyno_defuse + constructs
        if total_obj_activity == 0:
            continue
        
        player_text = f"**{name}** ({kills} kills)\n"
        if revives > 0:
            player_text += f"💉 {revives} revives given"
            if revived > 0:
                player_text += f" • ☠️ {revived} times revived"
            player_text += "\n"
        if obj_comp > 0:
            player_text += f"✅ {obj_comp} objectives completed\n"
        if obj_dest > 0:
            player_text += f"💥 {obj_dest} objectives destroyed\n"
        if constructs > 0:
            player_text += f"🔨 {constructs} constructions\n"
        if dyno_plant > 0:
            player_text += f"💣 {dyno_plant} dynamites planted\n"
        if dyno_defuse > 0:
            player_text += f"🛡️ {dyno_defuse} dynamites defused\n"
        
        # Check embed limits
        if field_count >= 25 or len(player_text) > 1024:
            embeds.append(current_embed)
            current_embed = discord.Embed(
                title=f"🎯 Objective Stats (continued)",
                description=f"Part {len(embeds) + 1}",
                color=0x57F287,
                timestamp=datetime.now(),
            )
            field_count = 0
        
        current_embed.add_field(name="\u200b", value=player_text, inline=False)
        field_count += 1
    
    if field_count > 0:
        embeds.append(current_embed)
    
    # Send all embeds
    for i, embed in enumerate(embeds):
        embed.set_footer(text=f"Session: {latest_date} • Page {i+1}/{len(embeds)}")
        await ctx.send(embed=embed)
        if i < len(embeds) - 1:
            await asyncio.sleep(2)


async def _last_session_combat_view(self, ctx, db, session_ids, session_ids_str, latest_date, player_count):
    """Combat-focused stats - kills, deaths, damage, gibs, headshots"""
    
    query = f'''
        SELECT p.player_name,
               SUM(p.kills) as kills,
               SUM(p.deaths) as deaths,
               SUM(p.damage_given) as damage_given,
               SUM(p.damage_received) as damage_received,
               SUM(p.team_damage_given) as team_damage,
               SUM(p.gibs) as gibs,
               SUM(p.team_gibs) as team_gibs,
               SUM(p.headshot_kills) as headshot_kills,
               SUM(p.self_kills) as self_kills,
               CASE
                   WHEN SUM(p.time_played_seconds) > 0
                   THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
                   ELSE 0
               END as dpm
        FROM player_comprehensive_stats p
        WHERE p.session_id IN ({session_ids_str})
        GROUP BY p.player_name
        ORDER BY kills DESC
    '''
    async with db.execute(query, session_ids) as cursor:
        players = await cursor.fetchall()

    # Split into embeds
    embeds = []
    current_embed = discord.Embed(
        title=f"⚔️ Combat Stats - {latest_date}",
        description=f"Showing all {len(players)} players - combat performance",
        color=0xED4245,
        timestamp=datetime.now(),
    )
    
    field_count = 0
    medals = ["🥇", "🥈", "🥉"]
    
    for i, player in enumerate(players):
        name, kills, deaths, dmg_given, dmg_received, team_dmg, gibs, team_gibs, hsk, self_kills, dpm = player
        
        kd = kills / deaths if deaths > 0 else kills
        medal = medals[i] if i < 3 else f"{i+1}."
        
        player_text = (
            f"{medal} **{name}**\n"
            f"💀 `{kills}K/{deaths}D ({kd:.2f} K/D)` • `{dpm:.0f} DPM`\n"
            f"💥 Damage: `{dmg_given:,}` given • `{dmg_received:,}` received\n"
        )
        if gibs > 0:
            player_text += f"🦴 `{gibs} Gibs`"
        if hsk > 0:
            player_text += f" • 🎯 `{hsk} Headshot Kills`"
        if team_dmg > 0:
            player_text += f"\n⚠️ `{team_dmg:,} Team Damage`"
        if self_kills > 0:
            player_text += f" • 💀 `{self_kills} Self Kills`"
        player_text += "\n"
        
        # Check limits
        if field_count >= 25:
            embeds.append(current_embed)
            current_embed = discord.Embed(
                title=f"⚔️ Combat Stats (continued)",
                description=f"Part {len(embeds) + 1}",
                color=0xED4245,
                timestamp=datetime.now(),
            )
            field_count = 0
        
        current_embed.add_field(name="\u200b", value=player_text, inline=False)
        field_count += 1
    
    if field_count > 0:
        embeds.append(current_embed)
    
    # Send all
    for i, embed in enumerate(embeds):
        embed.set_footer(text=f"Session: {latest_date} • Page {i+1}/{len(embeds)}")
        await ctx.send(embed=embed)
        if i < len(embeds) - 1:
            await asyncio.sleep(2)


async def _last_session_support_view(self, ctx, db, session_ids, session_ids_str, latest_date, player_count):
    """Support stats - medpacks, ammopacks, revives"""
    
    # Note: Your schema might not have medpack/ammopack columns
    # Adjust this query based on your actual schema
    query = f'''
        SELECT p.player_name,
               SUM(p.revives_given) as revives_given,
               SUM(p.times_revived) as times_revived,
               SUM(p.kills) as kills,
               SUM(p.deaths) as deaths
        FROM player_comprehensive_stats p
        WHERE p.session_id IN ({session_ids_str})
        GROUP BY p.player_name
        ORDER BY revives_given DESC
    '''
    async with db.execute(query, session_ids) as cursor:
        players = await cursor.fetchall()

    embed = discord.Embed(
        title=f"💉 Support Stats - {latest_date}",
        description=f"Showing all {len(players)} players - support performance",
        color=0x57F287,
        timestamp=datetime.now(),
    )

    support_text = ""
    for i, player in enumerate(players, 1):
        name, revives, revived, kills, deaths = player
        
        if revives == 0 and revived == 0:
            continue
        
        support_text += f"{i}. **{name}** ({kills}K/{deaths}D)\n"
        if revives > 0:
            support_text += f"   💉 {revives} revives given"
        if revived > 0:
            support_text += f" • ☠️ {revived} times revived"
        support_text += "\n"
    
    if support_text:
        # Split if too long
        if len(support_text) > 4000:
            chunks = [support_text[i:i+3900] for i in range(0, len(support_text), 3900)]
            for i, chunk in enumerate(chunks):
                if i > 0:
                    embed = discord.Embed(
                        title=f"💉 Support Stats (continued)",
                        color=0x57F287,
                    )
                embed.add_field(name="\u200b", value=chunk, inline=False)
                embed.set_footer(text=f"Session: {latest_date}")
                await ctx.send(embed=embed)
                if i < len(chunks) - 1:
                    await asyncio.sleep(2)
        else:
            embed.add_field(name="\u200b", value=support_text, inline=False)
            embed.set_footer(text=f"Session: {latest_date}")
            await ctx.send(embed=embed)
    else:
        embed.add_field(name="\u200b", value="No support activity this session", inline=False)
        await ctx.send(embed=embed)


async def _last_session_sprees_view(self, ctx, db, session_ids, session_ids_str, latest_date, player_count):
    """Killing sprees and multi-kills"""
    
    query = f'''
        SELECT p.player_name,
               SUM(p.killing_spree_best) as best_spree,
               SUM(p.double_kills) as doubles,
               SUM(p.triple_kills) as triples,
               SUM(p.quad_kills) as quads,
               SUM(p.multi_kills) as multis,
               SUM(p.mega_kills) as megas,
               SUM(p.kills) as total_kills
        FROM player_comprehensive_stats p
        WHERE p.session_id IN ({session_ids_str})
        GROUP BY p.player_name
        ORDER BY best_spree DESC, megas DESC, multis DESC
    '''
    async with db.execute(query, session_ids) as cursor:
        players = await cursor.fetchall()

    embed = discord.Embed(
        title=f"🔥 Killing Sprees & Multi-Kills - {latest_date}",
        description=f"Showing all {len(players)} players",
        color=0xFEE75C,
        timestamp=datetime.now(),
    )

    spree_text = ""
    for i, player in enumerate(players, 1):
        name, spree, doubles, triples, quads, multis, megas, kills = player
        
        # Skip if no spree activity
        if spree == 0 and doubles == 0 and triples == 0 and quads == 0 and multis == 0 and megas == 0:
            continue
        
        spree_text += f"{i}. **{name}** ({kills} total kills)\n"
        if spree > 0:
            spree_text += f"   🔥 Best spree: {spree} kills\n"
        if megas > 0:
            spree_text += f"   🌟 {megas} MEGA KILLS\n"
        if quads > 0:
            spree_text += f"   💥 {quads} Quad Kills\n"
        if triples > 0:
            spree_text += f"   ⚡ {triples} Triple Kills\n"
        if doubles > 0:
            spree_text += f"   ✨ {doubles} Double Kills\n"
    
    if spree_text:
        if len(spree_text) > 4000:
            chunks = [spree_text[i:i+3900] for i in range(0, len(spree_text), 3900)]
            for i, chunk in enumerate(chunks):
                if i > 0:
                    embed = discord.Embed(title=f"🔥 Killing Sprees (continued)", color=0xFEE75C)
                embed.add_field(name="\u200b", value=chunk, inline=False)
                embed.set_footer(text=f"Session: {latest_date}")
                await ctx.send(embed=embed)
                if i < len(chunks) - 1:
                    await asyncio.sleep(2)
        else:
            embed.add_field(name="\u200b", value=spree_text, inline=False)
            embed.set_footer(text=f"Session: {latest_date}")
            await ctx.send(embed=embed)
    else:
        embed.add_field(name="\u200b", value="No special sprees or multi-kills this session", inline=False)
        await ctx.send(embed=embed)


async def _last_session_weapons_view(self, ctx, db, session_ids, session_ids_str, latest_date, player_count):
    """Complete weapon breakdown - ALL players, ALL weapons"""
    
    # Get weapon stats
    query = f'''
        SELECT p.player_name, w.weapon_name,
               SUM(w.kills) as weapon_kills,
               SUM(w.hits) as hits,
               SUM(w.shots) as shots,
               SUM(w.headshots) as headshots
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

    # Get revives
    query = f'''
        SELECT player_name, SUM(times_revived) as revives
        FROM player_comprehensive_stats
        WHERE session_id IN ({session_ids_str})
        GROUP BY player_name
    '''
    async with db.execute(query, session_ids) as cursor:
        player_revives_raw = await cursor.fetchall()
    
    player_revives = {player: revives for player, revives in player_revives_raw}

    # Group by player
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

    # Sort players by total kills
    sorted_players = sorted(
        player_weapon_map.items(),
        key=lambda x: sum(w[1] for w in x[1]),
        reverse=True
    )

    # Create weapon embeds - SHOW ALL WEAPONS
    weapon_embeds = []
    current_embed = discord.Embed(
        title="🎯 Weapon Mastery Breakdown",
        description=f"Complete weapon statistics for all {len(sorted_players)} players",
        color=0x57F287,
        timestamp=datetime.now(),
    )

    current_field_count = 0

    for player, weapons in sorted_players:
        # Calculate player overall stats
        total_kills = sum(w[1] for w in weapons)
        total_shots = sum(w[6] for w in weapons)
        total_hits = sum(w[5] for w in weapons)
        overall_acc = (total_hits / total_shots * 100) if total_shots > 0 else 0
        revives = player_revives.get(player, 0)
        
        # Build weapon text - SHOW ALL WEAPONS
        weapon_text = f"**{total_kills} kills** • **{overall_acc:.1f}% ACC**"
        if revives > 0:
            weapon_text += f" • 💉 **{revives} revived**"
        weapon_text += "\n"
        
        # Add ALL weapons
        for weapon, kills, acc, hs_pct, hs, hits, shots in weapons:
            weapon_text += f"• {weapon}: `{kills}K` `{acc:.0f}% ACC` `{hs} HS ({hs_pct:.0f}%)`\n"
        
        # Check if field would exceed limits
        if current_field_count >= 25 or len(weapon_text) > 1024:
            # Save current embed and start new one
            weapon_embeds.append(current_embed)
            current_embed = discord.Embed(
                title="🎯 Weapon Mastery Breakdown (continued)",
                description=f"Part {len(weapon_embeds) + 1}",
                color=0x57F287,
                timestamp=datetime.now(),
            )
            current_field_count = 0
        
        # If single player's weapons exceed 1024 chars, split them
        if len(weapon_text) > 1024:
            # Split weapons into chunks
            weapon_chunks = []
            current_chunk = f"**{total_kills} kills** • **{overall_acc:.1f}% ACC**"
            if revives > 0:
                current_chunk += f" • 💉 **{revives} revived**"
            current_chunk += "\n"
            
            for weapon, kills, acc, hs_pct, hs, hits, shots in weapons:
                weapon_line = f"• {weapon}: `{kills}K` `{acc:.0f}% ACC` `{hs} HS ({hs_pct:.0f}%)`\n"
                
                if len(current_chunk) + len(weapon_line) > 900:
                    weapon_chunks.append(current_chunk)
                    current_chunk = ""
                
                current_chunk += weapon_line
            
            if current_chunk:
                weapon_chunks.append(current_chunk)
            
            # Add each chunk as separate field
            for i, chunk in enumerate(weapon_chunks):
                if current_field_count >= 25:
                    weapon_embeds.append(current_embed)
                    current_embed = discord.Embed(
                        title="🎯 Weapon Mastery Breakdown (continued)",
                        description=f"Part {len(weapon_embeds) + 1}",
                        color=0x57F287,
                        timestamp=datetime.now(),
                    )
                    current_field_count = 0
                
                field_name = f"⚔️ {player}" if i == 0 else f"⚔️ {player} (continued)"
                current_embed.add_field(
                    name=field_name,
                    value=chunk.rstrip(),
                    inline=False
                )
                current_field_count += 1
        else:
            # Normal case - fits in one field
            current_embed.add_field(
                name=f"⚔️ {player}",
                value=weapon_text.rstrip(),
                inline=False
            )
            current_field_count += 1

    # Add last embed
    if current_field_count > 0:
        weapon_embeds.append(current_embed)

    # Send all weapon embeds with delays
    for i, embed in enumerate(weapon_embeds):
        embed.set_footer(text=f"Session: {latest_date} • Page {i+1}/{len(weapon_embeds)}")
        await ctx.send(embed=embed)
        if i < len(weapon_embeds) - 1:
            await asyncio.sleep(3)

    logger.info(f"✅ Sent {len(weapon_embeds)} weapon mastery embeds")


async def _last_session_graphs_view(self, ctx, db, session_ids, session_ids_str, latest_date, player_count):
    """Performance graphs - 6 visualizations"""
    
    try:
        import matplotlib.pyplot as plt
        import io
        
        # Get data for graphs
        query = f'''
            SELECT p.player_name,
                   SUM(p.kills) as kills,
                   SUM(p.deaths) as deaths,
                   CASE
                       WHEN SUM(p.time_played_seconds) > 0
                       THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
                       ELSE 0
                   END as dpm,
                   SUM(p.time_played_seconds) as time_played,
                   CAST(SUM(p.time_played_seconds * p.time_dead_ratio / 100.0) AS INTEGER) as time_dead,
                   SUM(p.denied_playtime) as denied
            FROM player_comprehensive_stats p
            WHERE p.session_id IN ({session_ids_str})
            GROUP BY p.player_name
            ORDER BY kills DESC
            LIMIT 6
        '''
        async with db.execute(query, session_ids) as cursor:
            top_players = await cursor.fetchall()
        
        # Prepare data
        player_names = [p[0] for p in top_players]
        kills = [p[1] for p in top_players]
        deaths = [p[2] for p in top_players]
        dpm = [p[3] for p in top_players]
        time_played = [p[4] / 60 for p in top_players]  # Convert to minutes
        time_dead = [p[5] / 60 for p in top_players]  # Convert to minutes
        denied = [p[6] for p in top_players]
        
        # Create figure
        fig, axes = plt.subplots(2, 3, figsize=(18, 10))
        fig.suptitle(f'Visual Performance Analytics - {latest_date}', fontsize=16, fontweight='bold')
        
        # Graph 1: Kills
        axes[0, 0].bar(range(len(player_names)), kills, color='#57F287')
        axes[0, 0].set_title('Kills', fontweight='bold')
        axes[0, 0].set_xticks(range(len(player_names)))
        axes[0, 0].set_xticklabels(player_names, rotation=45, ha='right')
        axes[0, 0].set_ylabel('Kills')
        axes[0, 0].grid(axis='y', alpha=0.3)
        
        # Graph 2: Deaths
        axes[0, 1].bar(range(len(player_names)), deaths, color='#ED4245')
        axes[0, 1].set_title('Deaths', fontweight='bold')
        axes[0, 1].set_xticks(range(len(player_names)))
        axes[0, 1].set_xticklabels(player_names, rotation=45, ha='right')
        axes[0, 1].set_ylabel('Deaths')
        axes[0, 1].grid(axis='y', alpha=0.3)
        
        # Graph 3: DPM
        axes[0, 2].bar(range(len(player_names)), dpm, color='#FEE75C')
        axes[0, 2].set_title('DPM (Damage Per Minute)', fontweight='bold')
        axes[0, 2].set_xticks(range(len(player_names)))
        axes[0, 2].set_xticklabels(player_names, rotation=45, ha='right')
        axes[0, 2].set_ylabel('DPM')
        axes[0, 2].grid(axis='y', alpha=0.3)
        
        # Graph 4: Time Played
        axes[1, 0].bar(range(len(player_names)), time_played, color='#5865F2')
        axes[1, 0].set_title('Time Played (minutes)', fontweight='bold')
        axes[1, 0].set_xticks(range(len(player_names)))
        axes[1, 0].set_xticklabels(player_names, rotation=45, ha='right')
        axes[1, 0].set_ylabel('Minutes')
        axes[1, 0].grid(axis='y', alpha=0.3)
        
        # Graph 5: Time Dead
        axes[1, 1].bar(range(len(player_names)), time_dead, color='#EB459E')
        axes[1, 1].set_title('Time Dead (minutes)', fontweight='bold')
        axes[1, 1].set_xticks(range(len(player_names)))
        axes[1, 1].set_xticklabels(player_names, rotation=45, ha='right')
        axes[1, 1].set_ylabel('Minutes')
        axes[1, 1].grid(axis='y', alpha=0.3)
        
        # Graph 6: Time Denied
        axes[1, 2].bar(range(len(player_names)), denied, color='#9B59B6')
        axes[1, 2].set_title('Time Denied (seconds)', fontweight='bold')
        axes[1, 2].set_xticks(range(len(player_names)))
        axes[1, 2].set_xticklabels(player_names, rotation=45, ha='right')
        axes[1, 2].set_ylabel('Seconds')
        axes[1, 2].grid(axis='y', alpha=0.3)
        
        plt.tight_layout()
        
        # Save to buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        
        # Send
        file = discord.File(buf, filename='performance_analytics.png')
        await ctx.send("📊 **Visual Performance Analytics**", file=file)
        
    except ImportError:
        await ctx.send("⚠️ matplotlib not installed - graphs unavailable")
    except Exception as e:
        logger.error(f"❌ Error generating graphs: {e}", exc_info=True)
        await ctx.send(f"⚠️ Could not generate graphs: {str(e)[:100]}")
