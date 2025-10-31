# ============================================================================
# UPDATED LAST_SESSION COMMAND - SPLIT INTO SUMMARY AND DETAILED VIEWS
# ============================================================================
"""
This replaces the existing last_session command in ultimate_bot.py

Changes:
1. !last_session - Shows only Session Summary (embed1) + help note
2. !last_session more - Shows all detailed analytics
3. Weapon Mastery field truncated to avoid 1024 char limit
"""

@commands.command(name='last_session', aliases=['last', 'latest', 'recent'])
async def last_session(self, ctx, subcommand: str = None):
    """🎮 Show the most recent session/match

    Usage:
    - !last_session      → Quick session summary
    - !last_session more → Detailed analytics (graphs, weapons, DPM)

    Displays stats for the latest played session (full day).
    A session = one day of gaming with all maps/rounds.
    """
    try:
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

            # =========================================================================
            # IF NO SUBCOMMAND: SHOW ONLY SESSION SUMMARY
            # =========================================================================
            if not subcommand:
                # Get unique player count
                query = f'''
                    SELECT COUNT(DISTINCT player_guid)
                    FROM player_comprehensive_stats
                    WHERE session_id IN ({session_ids_str})
                '''
                async with db.execute(query, session_ids) as cursor:
                    player_count = (await cursor.fetchone())[0]

                # Calculate total maps and rounds
                query = f'''
                    SELECT COUNT(DISTINCT session_id) / 2 as total_maps,
                           COUNT(DISTINCT session_id) as total_rounds
                    FROM player_comprehensive_stats
                    WHERE session_id IN ({session_ids_str})
                '''
                async with db.execute(query, session_ids) as cursor:
                    result = await cursor.fetchone()
                    total_maps, total_rounds = result

                # Get hardcoded teams and calculate scores
                hardcoded_teams = await self.get_hardcoded_teams(db, latest_date)
                team_1_name, team_2_name, team_1_score, team_2_score = "Team 1", "Team 2", 0, 0
                
                if hardcoded_teams:
                    team_1_name = hardcoded_teams[0][0] if hardcoded_teams else "Team 1"
                    team_2_name = hardcoded_teams[0][1] if len(hardcoded_teams[0]) > 1 else "Team 2"
                    
                    # Calculate map wins
                    async with db.execute(f'''
                        SELECT map_name, round_number, team
                        FROM player_comprehensive_stats
                        WHERE session_id IN ({session_ids_str})
                        AND map_name IS NOT NULL
                        GROUP BY session_id, team
                    ''', session_ids) as cursor:
                        round_results = await cursor.fetchall()
                    
                    # Count map wins (implementation depends on your scoring logic)
                    # This is a simplified version - adjust based on your actual scoring
                    for map_name, round_num, team in round_results:
                        if team == 1:
                            team_1_score += 0.5
                        elif team == 2:
                            team_2_score += 0.5

                # Get ALL players (aggregated)
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

                # Calculate map counts
                maps_played = total_maps
                rounds_played = len(sessions)

                # Build description with team scores
                description = (
                    f"**{maps_played} maps** • **{rounds_played} rounds** • "
                    f"**{player_count} players**"
                )
                
                if team_1_score > 0 or team_2_score > 0:
                    winner_icon = "🏆" if team_1_score > team_2_score else ("🏆" if team_2_score > team_1_score else "🤝")
                    description += f"\n\n**🎯 FINAL SCORE:** {winner_icon}\n"
                    description += f"**{team_1_name}:** {team_1_score} points\n"
                    description += f"**{team_2_name}:** {team_2_score} points"
                    if team_1_score == team_2_score:
                        description += " *(TIE)*"
                
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

                # Top players (show all, but format compactly)
                if all_players:
                    medals = ["🥇", "🥈", "🥉"]
                    top_text = ""
                    
                    for i, player in enumerate(all_players):
                        name, kills, deaths, dpm, hits, shots, total_hs, hsk, total_seconds, total_time_dead = player
                        
                        kd_ratio = kills / deaths if deaths and deaths > 0 else (kills or 0)
                        acc = (hits / shots * 100) if shots and shots > 0 else 0
                        hsk_rate = (hsk / kills * 100) if kills and kills > 0 else 0
                        hs_rate = (total_hs / hits * 100) if hits and hits > 0 else 0
                        
                        # Format time
                        hours = total_seconds // 3600
                        minutes = (total_seconds % 3600) // 60
                        if hours > 0:
                            time_display = f"{hours}h{minutes}m"
                        else:
                            time_display = f"{minutes}m"
                        
                        # Format time dead
                        dead_hours = total_time_dead // 3600
                        dead_minutes = (total_time_dead % 3600) // 60
                        if dead_hours > 0:
                            time_dead_display = f"{dead_hours}h{dead_minutes}m"
                        else:
                            time_dead_display = f"{dead_minutes}m"
                        
                        medal = medals[i] if i < 3 else f"{i+1}."
                        top_text += f"{medal} **{name}**\n"
                        top_text += (
                            f"`{kills}K/{deaths}D ({kd_ratio:.2f})` • "
                            f"`{dpm:.0f} DPM` • "
                            f"`{acc:.1f}% ACC ({hits}/{shots})`\n"
                        )
                        top_text += (
                            f"`{hsk} HSK ({hsk_rate:.1f}%)` • "
                            f"`{total_hs} HS ({hs_rate:.1f}%)` • "
                            f"⏱️ `{time_display}` • 💀 `{time_dead_display}`\n\n"
                        )

                    embed1.add_field(name="🏆 All Players", value=top_text.rstrip(), inline=False)

                embed1.set_footer(text="💡 Use !last_session more for detailed analytics (graphs, weapons, DPM)")
                await ctx.send(embed=embed1)
                return

            # =========================================================================
            # IF SUBCOMMAND = "more": SHOW DETAILED ANALYTICS
            # =========================================================================
            if subcommand.lower() == "more":
                await ctx.send("🔄 **Loading detailed analytics...**")
                
                # Get all the data we need
                query = f'''
                    SELECT COUNT(DISTINCT player_guid)
                    FROM player_comprehensive_stats
                    WHERE session_id IN ({session_ids_str})
                '''
                async with db.execute(query, session_ids) as cursor:
                    player_count = (await cursor.fetchone())[0]

                # Get all players data
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
                           CAST(SUM(p.time_played_seconds * p.time_dead_ratio / 100.0) AS INTEGER) as total_time_dead,
                           SUM(p.damage_given) as total_damage,
                           SUM(p.time_played_seconds * (100 - p.time_dead_ratio) / 100.0) as time_alive,
                           SUM(p.denied_playtime) as denied_playtime
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
                    all_players_detailed = await cursor.fetchall()

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

                # Get DPM leaderboard
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

                # Get team data
                hardcoded_teams = await self.get_hardcoded_teams(db, latest_date)
                team_1_name = hardcoded_teams[0][0] if hardcoded_teams else "Team 1"
                team_2_name = hardcoded_teams[0][1] if hardcoded_teams and len(hardcoded_teams[0]) > 1 else "Team 2"

                # Get team stats
                query = f'''
                    SELECT team,
                           SUM(kills) as kills,
                           SUM(deaths) as deaths,
                           SUM(damage_given) as damage
                    FROM player_comprehensive_stats
                    WHERE session_id IN ({session_ids_str})
                    AND team IN (1, 2)
                    GROUP BY team
                    ORDER BY team
                '''
                async with db.execute(query, session_ids) as cursor:
                    team_stats = await cursor.fetchall()

                # ═════════════════════════════════════════════════════════════
                # EMBED 1: DPM ANALYTICS
                # ═════════════════════════════════════════════════════════════
                embed_dpm = discord.Embed(
                    title="💥 DPM Analytics - Damage Per Minute",
                    description="Enhanced DPM with Kill/Death Details",
                    color=0xFEE75C,
                    timestamp=datetime.now(),
                )

                if dpm_leaders:
                    dpm_text = ""
                    for i, (player, dpm, kills, deaths) in enumerate(dpm_leaders[:10], 1):
                        kd = kills / deaths if deaths else kills
                        dpm_text += f"{i}. **{player}**\n"
                        dpm_text += f"   💥 `{dpm:.0f} DPM` • 💀 `{kd:.1f} K/D` ({kills}K/{deaths}D)\n"

                    embed_dpm.add_field(
                        name="🏆 Enhanced DPM Leaderboard", value=dpm_text.rstrip(), inline=False
                    )

                    # DPM Insights
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
                    embed_dpm.add_field(name="💥 DPM Insights", value=insights, inline=False)

                embed_dpm.set_footer(text=f"Session: {latest_date}")
                await ctx.send(embed=embed_dpm)
                await asyncio.sleep(4)

                # ═════════════════════════════════════════════════════════════
                # EMBED 2: WEAPON MASTERY BREAKDOWN
                # ═════════════════════════════════════════════════════════════
                
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

                # Get player revives
                query = f'''
                    SELECT player_name, SUM(times_revived) as revives
                    FROM player_comprehensive_stats
                    WHERE session_id IN ({session_ids_str})
                    GROUP BY player_name
                '''
                async with db.execute(query, session_ids) as cursor:
                    player_revives_raw = await cursor.fetchall()
                
                player_revives = {player: revives for player, revives in player_revives_raw}

                # Sort players by total kills
                sorted_players = sorted(
                    player_weapon_map.items(),
                    key=lambda x: sum(w[1] for w in x[1]),
                    reverse=True
                )

                # Create embeds for weapon mastery (split if needed)
                weapon_embeds = []
                current_embed = discord.Embed(
                    title="🎯 Weapon Mastery Breakdown",
                    description=f"Complete weapon statistics for all {len(sorted_players)} players",
                    color=0x57F287,
                    timestamp=datetime.now(),
                )
                
                current_field_count = 0
                current_char_count = 0
                
                for player, weapons in sorted_players:
                    # Calculate player stats
                    total_kills = sum(w[1] for w in weapons)
                    total_shots = sum(w[6] for w in weapons)
                    total_hits = sum(w[5] for w in weapons)
                    overall_acc = (total_hits / total_shots * 100) if total_shots > 0 else 0
                    revives = player_revives.get(player, 0)
                    
                    # Build weapon breakdown text
                    weapon_text = f"**{total_kills} kills** • **{overall_acc:.1f}% ACC**"
                    if revives > 0:
                        weapon_text += f" • 💉 **{revives} revived**"
                    weapon_text += "\n"
                    
                    # Add top 3 weapons only
                    for weapon, kills, acc, hs_pct, hs, hits, shots in weapons[:3]:
                        weapon_text += f"• {weapon}: `{kills}K` `{acc:.0f}% ACC` `{hs} HS ({hs_pct:.0f}%)`\n"
                    
                    if len(weapons) > 3:
                        weapon_text += f"*...+{len(weapons)-3} more weapons*\n"
                    
                    # Check if adding this field would exceed limits
                    # Discord limits: 25 fields per embed, 1024 chars per field value, 6000 chars total
                    if (current_field_count >= 24 or 
                        len(weapon_text) > 1024 or
                        current_char_count + len(weapon_text) > 5000):
                        # Start new embed
                        weapon_embeds.append(current_embed)
                        current_embed = discord.Embed(
                            title="🎯 Weapon Mastery Breakdown (continued)",
                            description=f"Part {len(weapon_embeds) + 1}",
                            color=0x57F287,
                            timestamp=datetime.now(),
                        )
                        current_field_count = 0
                        current_char_count = 0
                    
                    current_embed.add_field(
                        name=f"⚔️ {player}",
                        value=weapon_text.rstrip(),
                        inline=False
                    )
                    current_field_count += 1
                    current_char_count += len(weapon_text)
                
                # Add the last embed
                if current_field_count > 0:
                    weapon_embeds.append(current_embed)
                
                # Send all weapon embeds
                for i, embed in enumerate(weapon_embeds):
                    embed.set_footer(text=f"Session: {latest_date} • Page {i+1}/{len(weapon_embeds)}")
                    await ctx.send(embed=embed)
                    if i < len(weapon_embeds) - 1:
                        await asyncio.sleep(2)

                await asyncio.sleep(4)

                # ═════════════════════════════════════════════════════════════
                # GRAPHS: VISUAL PERFORMANCE ANALYTICS
                # ═════════════════════════════════════════════════════════════
                try:
                    import matplotlib.pyplot as plt
                    import io
                    
                    # Prepare data for graphs
                    player_names = [p[0] for p in all_players_detailed[:6]]  # Top 6 players
                    kills = [p[1] for p in all_players_detailed[:6]]
                    deaths = [p[2] for p in all_players_detailed[:6]]
                    dpm = [p[3] for p in all_players_detailed[:6]]
                    time_played = [p[8] / 60 for p in all_players_detailed[:6]]  # Convert to minutes
                    time_dead = [p[9] / 60 for p in all_players_detailed[:6]]  # Convert to minutes
                    denied = [p[12] for p in all_players_detailed[:6]]
                    
                    # Create figure with subplots
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
                    
                    # Send graph
                    file = discord.File(buf, filename='performance_analytics.png')
                    await ctx.send("📊 **Visual Performance Analytics**", file=file)
                    
                except ImportError:
                    logger.warning("⚠️ matplotlib not installed - skipping graphs")
                except Exception as e:
                    logger.error(f"❌ Error generating graphs: {e}", exc_info=True)

                # Final message
                final_embed = discord.Embed(
                    title="✅ Detailed Analytics Complete",
                    description="All detailed statistics have been displayed above.",
                    color=0x00FF00
                )
                await ctx.send(embed=final_embed)
                return

            # If unknown subcommand
            await ctx.send(
                "❌ Unknown option. Use:\n"
                "• `!last_session` - Quick summary\n"
                "• `!last_session more` - Detailed analytics"
            )

    except Exception as e:
        logger.error(f"Error in last_session command: {e}", exc_info=True)
        await ctx.send(f"❌ Error retrieving last session: {e}")
