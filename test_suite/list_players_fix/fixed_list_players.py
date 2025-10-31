#!/usr/bin/env python3
"""
Fixed list_players command with pagination
Replace the existing command at line 7508
"""

@commands.command(name="list_players", aliases=["players", "lp"])
async def list_players(self, ctx, filter_type: str = None, page: int = 1):
    """
    👥 List all players with their Discord link status
    
    Usage:
        !list_players              → Show all players (page 1)
        !list_players 2            → Show page 2
        !list_players linked       → Show only linked players
        !list_players unlinked     → Show only unlinked players
        !list_players active       → Show players from last 30 days
        !list_players linked 2     → Show linked players, page 2
    """
    try:
        conn = sqlite3.connect(self.bot.db_path)
        cursor = conn.cursor()

        # Base query to get all players with their link status
        base_query = """
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
        """

        # Apply filter
        if filter_type and not filter_type.isdigit():
            filter_lower = filter_type.lower()
            if filter_lower in ["linked", "link"]:
                base_query += " HAVING pl.discord_id IS NOT NULL"
            elif filter_lower in ["unlinked", "nolink"]:
                base_query += " HAVING pl.discord_id IS NULL"
            elif filter_lower in ["active", "recent"]:
                base_query += " HAVING MAX(p.session_date) >= date('now', '-30 days')"
        elif filter_type and filter_type.isdigit():
            # User passed page number as first arg
            page = int(filter_type)
            filter_type = None

        base_query += " ORDER BY sessions_played DESC, total_kills DESC"

        cursor.execute(base_query)
        players = cursor.fetchall()
        conn.close()

        if not players:
            await ctx.send(
                f"❌ No players found" + (f" with filter: {filter_type}" if filter_type else "")
            )
            return

        # Count linked vs unlinked
        linked_count = sum(1 for p in players if p[2])
        unlinked_count = len(players) - linked_count

        # Pagination settings
        players_per_page = 15  # Reduced from 10 to fit more compactly
        total_pages = (len(players) + players_per_page - 1) // players_per_page
        
        # Validate page number
        if page < 1:
            page = 1
        elif page > total_pages:
            page = total_pages

        # Calculate slice indices
        start_idx = (page - 1) * players_per_page
        end_idx = min(start_idx + players_per_page, len(players))
        page_players = players[start_idx:end_idx]

        # Create embed
        filter_text = f" - {filter_type.upper()}" if filter_type else ""
        
        embed = discord.Embed(
            title=f"👥 Players List{filter_text}",
            description=(
                f"**Total**: {len(players)} players • "
                f"🔗 {linked_count} linked • ❌ {unlinked_count} unlinked\n"
                f"**Page {page}/{total_pages}** (showing {start_idx+1}-{end_idx})"
            ),
            color=discord.Color.green(),
        )

        # Format player list (MORE COMPACT)
        player_lines = []
        for (
            guid,
            name,
            discord_id,
            sessions,
            last_played,
            kills,
            deaths,
        ) in page_players:
            # Link status icon
            link_icon = "🔗" if discord_id else "❌"

            # KD ratio
            kd = kills / deaths if deaths > 0 else kills

            # Format last played date
            try:
                from datetime import datetime

                last_date = datetime.fromisoformat(
                    last_played.replace("Z", "+00:00")
                    if "Z" in last_played
                    else last_played
                )
                days_ago = (datetime.now() - last_date).days
                if days_ago == 0:
                    last_str = "today"
                elif days_ago == 1:
                    last_str = "1d"
                elif days_ago < 7:
                    last_str = f"{days_ago}d"
                elif days_ago < 30:
                    last_str = f"{days_ago//7}w"
                else:
                    last_str = f"{days_ago//30}mo"
            except Exception:
                last_str = "?"

            # COMPACT FORMAT - Single line per player
            player_lines.append(
                f"{link_icon} **{name[:20]}** • "
                f"{sessions}s • {kills}K/{deaths}D ({kd:.1f}) • {last_str}"
            )

        # Add all players in ONE field (more compact)
        embed.add_field(
            name=f"Players {start_idx+1}-{end_idx}",
            value="\n".join(player_lines),
            inline=False,
        )

        # Navigation footer
        nav_text = ""
        if total_pages > 1:
            if page > 1:
                nav_text += f"⬅️ `!lp {filter_type or ''} {page-1}`.strip() • "
            nav_text += f"Page {page}/{total_pages}"
            if page < total_pages:
                nav_text += f" • `!lp {filter_type or ''} {page+1}`.strip() ➡️"
        
        if nav_text:
            embed.set_footer(text=nav_text)
        else:
            embed.set_footer(
                text="Use !link to link • !list_players [linked|unlinked|active]"
            )

        await ctx.send(embed=embed)

    except Exception as e:
        logger.error(f"Error in list_players command: {e}", exc_info=True)
        await ctx.send(f"❌ Error listing players: {e}")


# ============== ALTERNATIVE: SIMPLE TEXT VERSION ==============
# If pagination is still too complex, use this simpler version:

@commands.command(name="list_players_simple", aliases=["players_simple", "lps"])
async def list_players_simple(self, ctx, filter_type: str = None):
    """
    👥 List all players (simple text format, no embeds)
    
    Usage:
        !lps              → Show all players
        !lps linked       → Show only linked players
        !lps unlinked     → Show only unlinked players
        !lps active       → Show players from last 30 days
    """
    try:
        conn = sqlite3.connect(self.bot.db_path)
        cursor = conn.cursor()

        # Base query
        base_query = """
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
        """

        # Apply filter
        if filter_type:
            filter_lower = filter_type.lower()
            if filter_lower in ["linked", "link"]:
                base_query += " HAVING pl.discord_id IS NOT NULL"
            elif filter_lower in ["unlinked", "nolink"]:
                base_query += " HAVING pl.discord_id IS NULL"
            elif filter_lower in ["active", "recent"]:
                base_query += " HAVING MAX(p.session_date) >= date('now', '-30 days')"

        base_query += " ORDER BY sessions_played DESC, total_kills DESC LIMIT 50"

        cursor.execute(base_query)
        players = cursor.fetchall()
        conn.close()

        if not players:
            await ctx.send(f"❌ No players found")
            return

        # Count totals
        linked_count = sum(1 for p in players if p[2])
        unlinked_count = len(players) - linked_count

        # Build text output
        output = []
        output.append("```")
        output.append("═══════════════════════════════════════════════════")
        output.append(f"           👥 PLAYERS LIST {f'({filter_type.upper()})' if filter_type else ''}")
        output.append("═══════════════════════════════════════════════════")
        output.append(f"Total: {len(players)} • 🔗 {linked_count} linked • ❌ {unlinked_count} unlinked")
        output.append("═══════════════════════════════════════════════════")
        output.append("")

        for idx, (guid, name, discord_id, sessions, last_played, kills, deaths) in enumerate(players, 1):
            link_icon = "🔗" if discord_id else "❌"
            kd = kills / deaths if deaths > 0 else kills
            
            output.append(
                f"{idx:3d}. {link_icon} {name[:25]:25s} "
                f"│ {sessions:3d}s │ {kills:5d}K │ {kd:5.2f}KD"
            )

        output.append("```")
        
        # Split if too long (2000 char limit per message)
        full_text = "\n".join(output)
        
        if len(full_text) > 1900:
            # Split into multiple messages
            chunks = []
            current_chunk = ["```"]
            current_len = 3
            
            for line in output[1:-1]:  # Skip first and last ```
                if current_len + len(line) + 1 > 1900:
                    current_chunk.append("```")
                    chunks.append("\n".join(current_chunk))
                    current_chunk = ["```", line]
                    current_len = 3 + len(line) + 1
                else:
                    current_chunk.append(line)
                    current_len += len(line) + 1
            
            if len(current_chunk) > 1:
                current_chunk.append("```")
                chunks.append("\n".join(current_chunk))
            
            for chunk in chunks:
                await ctx.send(chunk)
        else:
            await ctx.send(full_text)

    except Exception as e:
        logger.error(f"Error in list_players_simple: {e}", exc_info=True)
        await ctx.send(f"❌ Error: {e}")
