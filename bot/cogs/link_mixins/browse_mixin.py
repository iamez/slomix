"""LinkCog mixin: Player browse commands: list_players (paginated), find_player (search).

Extracted from bot/cogs/link_cog.py in Mega Audit v4 / Sprint 4.

All methods live on LinkCog via mixin inheritance.
"""
from __future__ import annotations

import logging
from datetime import datetime

import discord
from discord.ext import commands

from bot.core.checks import is_public_channel
from bot.core.database_adapter import ensure_player_name_alias
from bot.core.pagination_view import PaginationView
from bot.core.utils import escape_like_pattern_for_query, sanitize_error_message
from bot.stats import StatsCalculator

logger = logging.getLogger("bot.cogs.link")


class _LinkBrowseMixin:
    """Player browse commands: list_players (paginated), find_player (search) for LinkCog."""

    @is_public_channel()
    @commands.command(name="list_players", aliases=["players", "lp"])
    async def list_players(self, ctx, filter_type: str | None = None, page: int = 1):
        """
        👥 List all players with pagination.

        Browse all players in the database with stats, link status, and activity.
        Supports filtering and pagination for easy navigation.

        Usage:
            !list_players              → Show all players (page 1)
            !list_players 2            → Show page 2
            !list_players linked       → Show only linked players
            !list_players unlinked     → Show only unlinked players
            !list_players active       → Show players from last 30 days
            !list_players linked 2     → Show linked players, page 2

        Args:
            filter_type: Optional filter (linked/unlinked/active)
            page: Page number (default: 1, 15 players per page)

        Returns:
            Embed showing players with:
            - Link status icon (🔗 linked / ❌ unlinked)
            - Player name, sessions, kills/deaths, K/D ratio
            - Last played date (relative)
            - Navigation footer with page numbers
        """
        try:
            # Ensure player_name alias compatibility
            await ensure_player_name_alias(self.bot.db_adapter, self.bot.config)

            # Base query to get all players with their link status
            base_query = """
                SELECT
                    p.player_guid,
                    p.player_name,
                    pl.discord_id,
                    COUNT(DISTINCT p.round_date) as sessions_played,
                    MAX(p.round_date) as last_played,
                    SUM(p.kills) as total_kills,
                    SUM(p.deaths) as total_deaths
                FROM player_comprehensive_stats p
                JOIN rounds r ON p.round_id = r.id
                LEFT JOIN player_links pl ON p.player_guid = pl.player_guid
                WHERE r.round_number IN (1, 2)
                  AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
                GROUP BY p.player_guid, p.player_name, pl.discord_id
            """

            # Handle case where user passed page as first arg (e.g., !lp 2)
            if filter_type and filter_type.isdigit():
                page = int(filter_type)
                filter_type = None

            # Apply filter - whitelist validation for security
            # Note: We use string concatenation here ONLY because filter_type is validated
            # against a strict whitelist. The filter_clause contains NO user input.
            filter_clause = ""
            if filter_type:
                filter_lower = filter_type.lower()
                # Whitelist validation - only these exact values are allowed
                if filter_lower in ["linked", "link"]:
                    filter_clause = " HAVING pl.discord_id IS NOT NULL"
                elif filter_lower in ["unlinked", "nolink"]:
                    filter_clause = " HAVING pl.discord_id IS NULL"
                elif filter_lower in ["active", "recent"]:
                    filter_clause = " HAVING MAX(p.round_date) >= CURRENT_DATE - INTERVAL '30 days'"
                # If filter_type doesn't match whitelist, filter_clause stays empty (no filter applied)

            # Safe string concatenation: filter_clause is built from whitelisted constants only
            final_query = base_query + filter_clause + " ORDER BY sessions_played DESC, total_kills DESC"  # nosec B608

            players = await self.bot.db_adapter.fetch_all(final_query)

            # Calculate player counts from results
            total_players = len(players)
            linked_count = sum(1 for p in players if p[2] is not None)  # p[2] is discord_id

            if total_players == 0:
                await ctx.send(
                    "❌ No players found" + (f" with filter: {filter_type}" if filter_type else "")
                )
                return

            unlinked_count = total_players - linked_count

            # Pagination settings - reduced to 10 to stay under 1024 char limit
            players_per_page = 10
            total_pages = (total_players + players_per_page - 1) // players_per_page

            # Build page embeds from the in-memory result set to avoid redundant DB queries.
            max_pregenerate = total_pages
            pages = []

            for page_num in range(1, max_pregenerate + 1):
                offset = (page_num - 1) * players_per_page
                page_players = players[offset: offset + players_per_page]

                # Create embed for this page
                start_idx = offset
                end_idx = min(offset + len(page_players), total_players)

                filter_text = f" - {filter_type.upper()}" if filter_type else ""
                embed = discord.Embed(
                    title=f"👥 Players List{filter_text}",
                    description=(
                        f"**Total**: {total_players} players • "
                        f"🔗 {linked_count} linked • ❌ {unlinked_count} unlinked\n"
                        f"**Page {page_num}/{total_pages}** (showing {start_idx+1}-{end_idx})"
                    ),
                    color=discord.Color.green(),
                )

                # Format player list (compact single-line per player with badges)
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
                    link_icon = "🔗" if discord_id else "❌"
                    kd = StatsCalculator.calculate_kd(kills, deaths)

                    # Get formatted name with badges
                    formatted_name = await self.player_formatter.format_player(
                        guid, name, include_badges=True
                    )

                    # Format last played date compactly
                    try:
                        if last_played is None:
                            last_str = "?"
                        else:
                            last_played_str = str(last_played)
                            last_date = datetime.fromisoformat(
                                last_played_str.replace("Z", "+00:00") if "Z" in last_played_str else last_played_str
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
                    except (ValueError, TypeError, AttributeError):
                        last_str = "?"

                    player_lines.append(
                        f"{link_icon} **{formatted_name[:20]}** `{guid}` "
                        f"{sessions}s {kills}K/{deaths}D ({kd:.1f}) {last_str}"
                    )

                # Ensure field value doesn't exceed 1024 characters
                field_value = "\n".join(player_lines)
                if len(field_value) > 1024:
                    # Truncate and add indicator
                    field_value = field_value[:1000] + "\n... (truncated)"

                embed.add_field(
                    name=f"Players {start_idx+1}-{end_idx}",
                    value=field_value,
                    inline=False,
                )

                # Footer with button hint
                embed.set_footer(
                    text="Use ⏮️ ◀️ ▶️ ⏭️ buttons to navigate • !link to link"
                )

                pages.append(embed)

            # Handle requested page number (if user specified page as arg)
            initial_page = 0
            if filter_type and filter_type.isdigit():
                requested_page = int(filter_type)
                initial_page = max(0, min(requested_page - 1, total_pages - 1))
            elif page > 0:
                initial_page = max(0, min(page - 1, total_pages - 1))

            # Send with interactive pagination (or single page if only 1 page)
            if total_pages == 1:
                await ctx.send(embed=pages[0])
            else:
                view = PaginationView(ctx, pages)
                view.current_page = initial_page  # Start on requested page
                view._update_buttons()
                message = await ctx.send(embed=pages[initial_page], view=view)
                view.message = message  # Store message ref for timeout handling

        except Exception as e:
            logger.error(f"Error in list_players command: {e}", exc_info=True)
            await ctx.send(f"❌ Error listing players: {sanitize_error_message(e)}")

    @is_public_channel()
    @commands.command(name="find_player", aliases=["findplayer", "fp", "search_player"])
    async def find_player(self, ctx, *, search_term: str):
        """
        🔍 Find players by name with GUIDs and aliases (Helper for linking).

        This command helps admins and users find the exact GUID and aliases
        for a player they want to link. Shows up to 5 matches with full details.

        Usage:
            !find_player <name>
            !fp <name>

        Args:
            search_term: Player name or partial name to search for

        Example:
            !find_player john
            → Shows all players with "john" in their name/aliases
            → Displays GUID, top 3 aliases, stats, last seen

        Returns:
            Embed with up to 5 matching players showing:
            - GUID (for !link command)
            - Top 3 aliases
            - Stats (kills/deaths/K/D/games)
            - Last seen date
            - Link status (linked/unlinked)
        """
        try:
            # Escape LIKE pattern to prevent injection
            safe_pattern = escape_like_pattern_for_query(search_term)

            # Search in player_aliases (uses 'guid' and 'alias' columns)
            alias_guids = await self.bot.db_adapter.fetch_all(
                """
                SELECT DISTINCT pa.guid, MAX(pa.last_seen) as last_seen
                FROM player_aliases pa
                WHERE LOWER(pa.alias) LIKE LOWER(?) ESCAPE '\\'
                GROUP BY pa.guid
                ORDER BY last_seen DESC
                LIMIT 10
            """,
                (safe_pattern,),
            )
            alias_guids = [row[0] for row in alias_guids]

            # Also search main stats table
            stats_guids = await self.bot.db_adapter.fetch_all(
                """
                SELECT DISTINCT player_guid, MAX(round_date) as max_date
                FROM player_comprehensive_stats
                WHERE LOWER(player_name) LIKE LOWER(?) ESCAPE '\\'
                GROUP BY player_guid
                ORDER BY max_date DESC
                LIMIT 10
            """,
                (safe_pattern,),
            )
            stats_guids = [row[0] for row in stats_guids]

            # Combine and deduplicate
            guid_set = set(alias_guids + stats_guids)

            if not guid_set:
                await ctx.send(
                    f"❌ No players found matching **'{search_term}'**\n\n"
                    "💡 **Tips:**\n"
                    "   • Try a shorter/partial name\n"
                    "   • Use `!list_players` to browse all players\n"
                    "   • Check spelling - search is case-insensitive"
                )
                return

            # Limit to 5 results for cleaner display
            guid_list = list(guid_set)[:5]

            # Build detailed results
            embed = discord.Embed(
                title="🔍 Player Search Results",
                description=f"Search: **'{search_term}'** • Found **{len(guid_set)}** players (showing top {len(guid_list)})",
                color=0x5865F2,  # Discord Blurple
                timestamp=datetime.now()
            )

            for guid in guid_list:
                # Get stats
                stats = await self.bot.db_adapter.fetch_one(
                    """
                    SELECT
                        SUM(p.kills) as total_kills,
                        SUM(p.deaths) as total_deaths,
                        COUNT(DISTINCT p.round_id) as games,
                        MAX(p.round_date) as last_seen
                    FROM player_comprehensive_stats p
                    JOIN rounds r ON p.round_id = r.id
                    WHERE p.player_guid = ?
                      AND r.round_number IN (1, 2)
                      AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
                """,
                    (guid,),
                )

                # Get top 3 aliases
                aliases = await self.bot.db_adapter.fetch_all(
                    """
                    SELECT alias, last_seen, times_seen
                    FROM player_aliases
                    WHERE guid = ?
                    ORDER BY last_seen DESC, times_seen DESC
                    LIMIT 3
                """,
                    (guid,),
                )

                # Get link status
                link_row = await self.bot.db_adapter.fetch_one(
                    """
                    SELECT discord_username
                    FROM player_links
                    WHERE player_guid = ?
                """,
                    (guid,),
                )

                # Format data with badges
                if aliases:
                    primary_name = aliases[0][0]
                    # Get formatted name with badges
                    formatted_name = await self.player_formatter.format_player(
                        guid, primary_name, include_badges=True
                    )
                    alias_list = [f"`{a[0]}`" for a in aliases]
                    alias_str = " • ".join(alias_list)
                else:
                    formatted_name = "Unknown"
                    alias_str = "_(No aliases found)_"

                if stats:
                    kills, deaths, games, last_seen = stats
                    kd = StatsCalculator.calculate_kd(kills, deaths)
                    stats_str = (
                        f"**Stats:** `{kills:,}K` / `{deaths:,}D` / `{kd:.2f}` K/D\n"
                        f"**Games:** `{games:,}` • **Last Seen:** `{last_seen[:10] if last_seen else 'Never'}`"
                    )
                else:
                    stats_str = "_(No stats found)_"

                link_status = f"🔗 Linked to `{link_row[0]}`" if link_row else "❌ Not linked"

                # Add field to embed with formatted name and badges
                embed.add_field(
                    name=f"{formatted_name}",
                    value=(
                        f"**GUID:** `{guid}`\n"
                        f"**Aliases:** {alias_str}\n"
                        f"{stats_str}\n"
                        f"**Status:** {link_status}"
                    ),
                    inline=False,
                )

            # Add footer with usage hints
            embed.set_footer(
                text=(
                    f"💡 Link: !link {guid_list[0]} | "
                    f"Admin: !link @user {guid_list[0]} | "
                    f"Requested by {ctx.author.display_name}"
                )
            )

            await ctx.send(embed=embed)

            # Log search for debugging
            logger.info(
                f"🔍 Player search by {ctx.author}: '{search_term}' → {len(guid_set)} results"
            )

        except Exception as e:
            logger.error(f"Error in find_player command: {e}", exc_info=True)
            await ctx.send(
                f"❌ Error searching for players: {e}\n\n"
                "💡 Try: `!list_players` to browse all players"
            )
