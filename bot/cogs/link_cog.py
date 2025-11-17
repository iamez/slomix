"""
Link Cog - Player-Discord Account Linking
==========================================
Extracted from: bot/ultimate_bot.py (Phase 2 - Cog Extraction)
Extraction Date: 2025-11-01

Player linking system connecting Discord accounts to in-game profiles (GUIDs).
Supports smart self-linking, name search, GUID direct linking, and admin linking.

Commands:
- !link - Smart self-linking with top 3 suggestions
- !link <name> - Search by player name
- !link <GUID> - Direct link by GUID
- !link @user <GUID> - Admin link another user
- !unlink - Remove your link
- !select <1-3> - Alternative to reaction selection
- !find_player <name> - Helper: Search for players with GUIDs and aliases (NEW!)
- !list_players - Browse all players with pagination

Enhanced Features:
- Interactive reactions (1️⃣/2️⃣/3️⃣) for easy selection
- Shows up to 3 aliases per player
- GUID validation and confirmation
- Admin linking with permissions check
- Fuzzy name matching
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

import discord
from discord.ext import commands

# Import pagination view for interactive button navigation
from bot.core.pagination_view import PaginationView
from bot.stats import StatsCalculator

logger = logging.getLogger(__name__)


class LinkCog(commands.Cog, name="Link"):
    """🔗 Player-Discord Account Linking"""

    def __init__(self, bot):
        """
        Initialize the Link Cog.

        Args:
            bot: The main bot instance with database access
        """
        self.bot = bot
        logger.info("🔗 LinkCog loaded")

    async def _ensure_player_name_alias(self, db_adapter) -> None:
        """Create TEMP VIEW aliasing for player_name column compatibility."""
        try:
            # Check if player_name column exists using adapter
            result = await db_adapter.fetch_all("SELECT * FROM player_comprehensive_stats LIMIT 1")
            if result and hasattr(result[0], 'player_name'):
                # Column exists, no alias needed
                return
            elif result and hasattr(result[0], 'name'):
                # Create alias view if needed (SQLite only)
                if self.bot.config.database_type == 'sqlite':
                    await db_adapter.execute("""
                        CREATE TEMP VIEW IF NOT EXISTS player_comprehensive_stats_view AS
                        SELECT *, name AS player_name FROM player_comprehensive_stats
                    """)
                    logger.debug("Created temporary player_name alias view")
        except Exception as e:
            logger.warning(f"Could not create player_name alias: {e}")

    @commands.command(name="list_players", aliases=["players", "lp"])
    async def list_players(self, ctx, filter_type: Optional[str] = None, page: int = 1):
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
            await self._ensure_player_name_alias(self.bot.db_adapter)
            
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

            # Apply filter
            filter_clause = ""
            if filter_type:
                filter_lower = filter_type.lower()
                if filter_lower in ["linked", "link"]:
                    filter_clause = " HAVING pl.discord_id IS NOT NULL"
                elif filter_lower in ["unlinked", "nolink"]:
                    filter_clause = " HAVING pl.discord_id IS NULL"
                elif filter_lower in ["active", "recent"]:
                    # Use database-compatible date arithmetic
                    if self.bot.config.database_type == 'sqlite':
                        filter_clause = " HAVING MAX(p.round_date) >= date('now', '-30 days')"
                    else:
                        filter_clause = " HAVING MAX(p.round_date) >= CURRENT_DATE - INTERVAL '30 days'"

            # PERFORMANCE OPTIMIZATION: Get counts first with lightweight query
            count_query = f"""
                SELECT
                    COUNT(*) as total_players,
                    SUM(CASE WHEN discord_id IS NOT NULL THEN 1 ELSE 0 END) as linked_count
                FROM ({base_query + filter_clause}) as players_subq
            """

            counts = await self.bot.db_adapter.fetch_one(count_query)
            total_players = counts[0] if counts else 0
            linked_count = counts[1] if counts and counts[1] else 0

            if total_players == 0:
                await ctx.send(
                    f"❌ No players found" + (f" with filter: {filter_type}" if filter_type else "")
                )
                return

            unlinked_count = total_players - linked_count

            # Pagination settings
            players_per_page = 15
            total_pages = (total_players + players_per_page - 1) // players_per_page

            # Generate ONLY requested pages for button navigation (lazy loading)
            # Pre-generate first 5 pages for immediate navigation
            max_pregenerate = min(5, total_pages)
            pages = []

            for page_num in range(1, max_pregenerate + 1):
                offset = (page_num - 1) * players_per_page
                page_query = base_query + filter_clause + f" ORDER BY sessions_played DESC, total_kills DESC LIMIT {players_per_page} OFFSET {offset}"
                page_players = await self.bot.db_adapter.fetch_all(page_query)

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

                # Format player list (compact single-line per player)
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

                    # Format last played date compactly
                    try:
                        last_date = datetime.fromisoformat(
                            last_played.replace("Z", "+00:00") if "Z" in last_played else last_played
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

                    player_lines.append(
                        f"{link_icon} **{name[:20]}** • "
                        f"{sessions}s • {kills}K/{deaths}D ({kd:.1f}) • {last_str}"
                    )

                embed.add_field(
                    name=f"Players {start_idx+1}-{end_idx}",
                    value="\n".join(player_lines),
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
            await ctx.send(f"❌ Error listing players: {e}")

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
            # Database-specific placeholder
            placeholder = "?" if self.bot.config.database_type == 'sqlite' else "$1"
            
            # Search in player_aliases (uses 'guid' and 'alias' columns)
            alias_guids = await self.bot.db_adapter.fetch_all(
                f"""
                SELECT DISTINCT pa.guid, MAX(pa.last_seen) as last_seen
                FROM player_aliases pa
                WHERE LOWER(pa.alias) LIKE LOWER({placeholder})
                GROUP BY pa.guid
                ORDER BY last_seen DESC
                LIMIT 10
            """,
                (f"%{search_term}%",),
            )
            alias_guids = [row[0] for row in alias_guids]

            # Also search main stats table
            stats_guids = await self.bot.db_adapter.fetch_all(
                f"""
                SELECT DISTINCT player_guid, MAX(round_date) as max_date
                FROM player_comprehensive_stats
                WHERE LOWER(player_name) LIKE LOWER({placeholder})
                GROUP BY player_guid
                ORDER BY max_date DESC
                LIMIT 10
            """,
                (f"%{search_term}%",),
            )
            stats_guids = [row[0] for row in stats_guids]

            # Combine and deduplicate
            guid_set = set(alias_guids + stats_guids)

            if not guid_set:
                await ctx.send(
                    f"❌ No players found matching **'{search_term}'**\n\n"
                    f"💡 **Tips:**\n"
                    f"   • Try a shorter/partial name\n"
                    f"   • Use `!list_players` to browse all players\n"
                    f"   • Check spelling - search is case-insensitive"
                )
                return

            # Limit to 5 results for cleaner display
            guid_list = list(guid_set)[:5]

            # Build detailed results
            embed = discord.Embed(
                title=f"🔍 Player Search Results: '{search_term}'",
                description=f"Found **{len(guid_set)}** matching players (showing top {len(guid_list)})",
                color=0x3498DB,
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
                    WHERE et_guid = ?
                """,
                    (guid,),
                )

                # Format data
                if aliases:
                    primary_name = aliases[0][0]
                    alias_list = [f"**{a[0]}**" for a in aliases]
                    alias_str = ", ".join(alias_list)
                    if len(aliases) < 3:
                        alias_str += " _(only known name)_" if len(aliases) == 1 else ""
                else:
                    primary_name = "Unknown"
                    alias_str = "_(No aliases found)_"

                if stats:
                    kills, deaths, games, last_seen = stats
                    kd = kills / deaths if deaths and deaths > 0 else (kills if kills else 0)
                    stats_str = f"**{kills:,}** K / **{deaths:,}** D / **{kd:.2f}** K/D\n**Games:** {games:,}"
                else:
                    stats_str = "_(No stats found)_"
                    last_seen = "Never"

                link_status = f"🔗 **Linked** to {link_row[0]}" if link_row else "❌ **Unlinked**"

                # Calculate days ago for last_seen
                try:
                    from datetime import datetime
                    last_date = datetime.fromisoformat(
                        last_seen.replace("Z", "+00:00") if "Z" in last_seen else last_seen
                    )
                    days_ago = (datetime.now() - last_date).days
                    if days_ago == 0:
                        last_str = "Today"
                    elif days_ago == 1:
                        last_str = "Yesterday"
                    elif days_ago < 7:
                        last_str = f"{days_ago} days ago"
                    elif days_ago < 30:
                        weeks = days_ago // 7
                        last_str = f"{weeks} week{'s' if weeks > 1 else ''} ago"
                    elif days_ago < 365:
                        months = days_ago // 30
                        last_str = f"{months} month{'s' if months > 1 else ''} ago"
                    else:
                        years = days_ago // 365
                        last_str = f"{years} year{'s' if years > 1 else ''} ago"
                except Exception:
                    last_str = last_seen

                # Add field to embed
                embed.add_field(
                    name=f"🎮 {primary_name}",
                    value=(
                        f"**GUID:** `{guid}` _(use this for !link)_\n"
                        f"**Known as:** {alias_str}\n"
                        f"{stats_str}\n"
                        f"**Last Seen:** {last_str}\n"
                        f"**Status:** {link_status}"
                    ),
                    inline=False,
                )

            # Add footer with usage hints
                embed.set_footer(
                    text=(
                        f"💡 To link: !link {guid_list[0]} | "
                        f"Admin link: !link @user {guid_list[0]} | "
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
                f"💡 Try: `!list_players` to browse all players"
            )

    @commands.command(name="link")
    async def link(self, ctx, target: Optional[str] = None, *, guid: Optional[str] = None):
        """
        🔗 Link your Discord account to your in-game profile.

        Multiple usage modes with smart detection:

        **Self-Linking:**
        - `!link` → Smart search with top 3 suggestions (interactive)
        - `!link YourName` → Search by name (fuzzy matching)
        - `!link <GUID>` → Direct link by GUID (8 hex chars)

        **Admin Linking (requires Manage Server):**
        - `!link @user <GUID>` → Link another user's Discord to a GUID

        **Finding GUIDs:**
        - `!find_player <name>` → Search for players with full details

        Features:
        - Interactive selection with reactions (1️⃣/2️⃣/3️⃣)
        - Shows player stats, aliases, and last seen
        - Confirmation required for all links
        - Prevents duplicate links

        Examples:
            !link
            → Shows top 3 unlinked players

            !link john
            → Searches for players named "john"

            !link D8423F90
            → Links directly to GUID D8423F90 (with confirmation)

            !find_player john
            → Shows all "john" players with GUIDs and aliases

            !link @user D8423F90
            → Admin: Links @user to GUID D8423F90
        """
        try:
            # === SCENARIO 0: ADMIN LINKING (@mention + GUID) ===
            if ctx.message.mentions and guid:
                await self._admin_link(ctx, ctx.message.mentions[0], guid.upper())
                return

            # For self-linking
            discord_id = int(ctx.author.id)  # BIGINT in PostgreSQL

            # Check if already linked
            placeholder = '$1' if self.bot.config.database_type == 'postgresql' else '?'
            existing = await self.bot.db_adapter.fetch_one(
                f"""
                SELECT player_name, player_guid FROM player_links
                WHERE discord_id = {placeholder}
            """,
                (discord_id,),
            )

            if existing:
                await ctx.send(
                    f"⚠️ You're already linked to **{existing[0]}** (GUID: `{existing[1]}`)\n\n"
                    f"Use `!unlink` first to change your linked account.\n"
                    f"Use `!stats` to see your stats!"
                )
                return

            # === SCENARIO 1: NO ARGUMENTS - Smart Self-Linking ===
            if not target:
                await self._smart_self_link(ctx, discord_id)
                return

            # === SCENARIO 2: GUID Direct Link ===
            # Check if it's a GUID (8 hex characters)
            if len(target) == 8 and all(c in "0123456789ABCDEFabcdef" for c in target):
                await self._link_by_guid(ctx, discord_id, target.upper())
                return

            # === SCENARIO 3: Name Search ===
            await self._link_by_name(ctx, discord_id, target)

        except Exception as e:
            logger.error(f"Error in link command: {e}", exc_info=True)
            await ctx.send(
                f"❌ Error linking account: {e}\n\n"
                f"💡 Try: `!find_player <name>` to search for players with GUIDs"
            )

    async def _smart_self_link(self, ctx, discord_id: str):
        """Smart self-linking: show top 3 unlinked GUIDs with aliases."""
        try:
            # Get top 3 unlinked players by recent activity and total stats
            top_players = await self.bot.db_adapter.fetch_all(
                """
                SELECT
                    p.player_guid,
                    MAX(p.round_date) as last_played,
                    SUM(p.kills) as total_kills,
                    SUM(p.deaths) as total_deaths,
                    COUNT(DISTINCT p.round_id) as games
                FROM player_comprehensive_stats p
                JOIN rounds r ON p.round_id = r.id
                WHERE p.player_guid NOT IN (
                    SELECT player_guid FROM player_links WHERE player_guid IS NOT NULL
                )
                  AND r.round_number IN (1, 2)
                  AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
                GROUP BY p.player_guid
                ORDER BY last_played DESC, total_kills DESC
                LIMIT 3
            """,
            )

            if not top_players:
                await ctx.send(
                    "❌ No available players found!\n\n"
                    "**Reasons:**\n"
                    "• All players are already linked\n"
                    "• No games have been recorded yet\n\n"
                    "💡 **Try:** `!list_players unlinked` to see all unlinked players"
                )
                return

            # Build embed with top 3 options
            embed = discord.Embed(
                title="🔍 Link Your Account",
                description=(
                    f"Found **{len(top_players)}** potential matches!\n\n"
                    f"**Select your account:**\n"
                    f"• React with 1️⃣/2️⃣/3️⃣ below\n"
                    f"• Or use `!select <number>` within 60 seconds\n"
                    f"• Or use `!find_player <name>` to search"
                ),
                color=0x3498DB,
            )

            options_data = []
            for idx, (guid, last_date, kills, deaths, games) in enumerate(top_players, 1):
                # Get top 3 aliases for this GUID
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

                # Format aliases
                if aliases:
                    primary_name = aliases[0][0]
                    alias_list = [a[0] for a in aliases[:3]]
                    alias_str = ", ".join(alias_list)
                    if len(aliases) == 1:
                        alias_str += " _(only name)_"
                else:
                    # Fallback to most recent name
                    name_row = await self.bot.db_adapter.fetch_one(
                        """
                        SELECT player_name 
                        FROM player_comprehensive_stats 
                        WHERE player_guid = ? 
                        ORDER BY round_date DESC 
                        LIMIT 1
                    """,
                        (guid,),
                    )
                    primary_name = name_row[0] if name_row else "Unknown"
                    alias_str = primary_name

                kd_ratio = kills / deaths if deaths > 0 else kills

                emoji = ["1️⃣", "2️⃣", "3️⃣"][idx - 1]
                embed.add_field(
                    name=f"{emoji} **{primary_name}**",
                    value=(
                        f"**GUID:** `{guid}`\n"
                        f"**Stats:** {kills:,} K / {deaths:,} D / **{kd_ratio:.2f}** K/D\n"
                        f"**Games:** {games:,} | **Last Seen:** {last_date}\n"
                        f"**Also known as:** {alias_str}"
                    ),
                    inline=False,
                )

                options_data.append({
                    "guid": guid,
                    "name": primary_name,
                    "kills": kills,
                    "games": games,
                })

            embed.set_footer(
                text=f"💡 Or use: !link <GUID> to link directly | Requested by {ctx.author.display_name}"
            )

            message = await ctx.send(embed=embed)

            # Add reaction emojis
            emojis = ["1️⃣", "2️⃣", "3️⃣"][:len(top_players)]
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
                reaction, user = await self.bot.wait_for(
                    "reaction_add", timeout=60.0, check=check
                )

                # Get selected index
                selected_idx = emojis.index(str(reaction.emoji))
                selected = options_data[selected_idx]

                # Link the account (database-specific syntax)
                if self.bot.config.database_type == 'sqlite':
                    await self.bot.db_adapter.execute(
                        """
                        INSERT OR REPLACE INTO player_links
                        (discord_id, discord_username, et_guid, et_name, linked_date, verified)
                        VALUES (?, ?, ?, ?, datetime('now'), 1)
                        """,
                        (discord_id, str(ctx.author), selected["guid"], selected["name"]),
                    )
                else:  # PostgreSQL
                    await self.bot.db_adapter.execute(
                        """
                        INSERT INTO player_links
                        (discord_id, discord_username, et_guid, et_name, linked_date, verified)
                        VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP, true)
                        ON CONFLICT (discord_id) DO UPDATE SET
                            discord_username = EXCLUDED.discord_username,
                            et_guid = EXCLUDED.et_guid,
                            et_name = EXCLUDED.et_name,
                            linked_date = EXCLUDED.linked_date,
                            verified = EXCLUDED.verified
                        """,
                        (discord_id, str(ctx.author), selected["guid"], selected["name"]),
                    )

                # Success!
                await message.clear_reactions()
                success_embed = discord.Embed(
                    title="✅ Account Linked Successfully!",
                    description=f"You're now linked to **{selected['name']}**",
                    color=0x00FF00,
                )
                success_embed.add_field(
                    name="Your Stats",
                    value=f"**Games:** {selected['games']:,}\n**Kills:** {selected['kills']:,}",
                    inline=True,
                )
                success_embed.add_field(
                    name="Quick Access",
                    value="• Use `!stats` (no arguments)\n• Your stats are now tracked!",
                    inline=False,
                )
                success_embed.set_footer(text=f"GUID: {selected['guid']}")
                await ctx.send(embed=success_embed)

                logger.info(
                    f"✅ Self-link: {ctx.author} linked to {selected['name']} (GUID: {selected['guid']})"
                )

            except asyncio.TimeoutError:
                await message.clear_reactions()
                await ctx.send(
                    "⏱️ Link request timed out (60s expired).\n\n"
                    "💡 Try again with `!link` or use `!find_player <name>` to search"
                )

        except Exception as e:
            logger.error(f"Error in smart self-link: {e}", exc_info=True)
            await ctx.send(f"❌ Error during self-linking: {e}")

    async def _link_by_guid(self, ctx, discord_id: str, guid: str):
        """Direct GUID linking with confirmation."""
        try:
            # Check if GUID exists
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

            if not stats or stats[0] is None:
                await ctx.send(
                    f"❌ GUID `{guid}` not found in database.\n\n"
                    f"💡 **Try:**\n"
                    f"   • `!find_player <name>` to search by name\n"
                    f"   • `!list_players` to browse all players\n"
                    f"   • Double-check the GUID spelling"
                )
                return

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

            if aliases:
                primary_name = aliases[0][0]
                alias_list = [a[0] for a in aliases[:3]]
                alias_str = ", ".join(alias_list)
            else:
                # Fallback
                name_row = await self.bot.db_adapter.fetch_one(
                    """
                    SELECT player_name 
                    FROM player_comprehensive_stats 
                    WHERE player_guid = ? 
                    ORDER BY round_date DESC 
                    LIMIT 1
                """,
                    (guid,),
                )
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
                value=f"`{guid}`",
                inline=False,
            )
            embed.add_field(
                name="Known Names (top 3 aliases)",
                value=alias_str,
                inline=False,
            )
            embed.add_field(
                name="Stats",
                value=f"**{kills:,}** K / **{deaths:,}** D / **{kd_ratio:.2f}** K/D",
                inline=True,
            )
            embed.add_field(
                name="Activity",
                value=f"**{games:,}** games | Last: {last_seen}",
                inline=True,
            )
            embed.set_footer(text="React ✅ to confirm or ❌ to cancel (60s)")

            message = await ctx.send(embed=embed)
            await message.add_reaction("✅")
            await message.add_reaction("❌")

            def check(reaction, user):
                return (
                    user == ctx.author
                    and str(reaction.emoji) in ["✅", "❌"]
                    and reaction.message.id == message.id
                )

            try:
                reaction, user = await self.bot.wait_for(
                    "reaction_add", timeout=60.0, check=check
                )

                if str(reaction.emoji) == "✅":
                    # Confirmed - link it (database-specific syntax)
                    if self.bot.config.database_type == 'sqlite':
                        await self.bot.db_adapter.execute(
                            """
                            INSERT OR REPLACE INTO player_links
                            (discord_id, discord_username, et_guid, et_name, linked_date, verified)
                            VALUES (?, ?, ?, ?, datetime('now'), 1)
                            """,
                            (discord_id, str(ctx.author), guid, primary_name),
                        )
                    else:  # PostgreSQL
                        await self.bot.db_adapter.execute(
                            """
                            INSERT INTO player_links
                            (discord_id, discord_username, et_guid, et_name, linked_date, verified)
                            VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP, true)
                            ON CONFLICT (discord_id) DO UPDATE SET
                                discord_username = EXCLUDED.discord_username,
                                et_guid = EXCLUDED.et_guid,
                                et_name = EXCLUDED.et_name,
                                linked_date = EXCLUDED.linked_date,
                                verified = EXCLUDED.verified
                            """,
                            (discord_id, str(ctx.author), guid, primary_name),
                        )

                    await message.clear_reactions()
                    await ctx.send(
                        f"✅ Successfully linked to **{primary_name}** (GUID: `{guid}`)\n\n"
                        f"💡 Use `!stats` to see your stats!"
                    )

                    logger.info(f"✅ GUID link: {ctx.author} linked to {primary_name} (GUID: {guid})")
                else:
                    await message.clear_reactions()
                    await ctx.send("❌ Link cancelled.")

            except asyncio.TimeoutError:
                await message.clear_reactions()
                await ctx.send("⏱️ Confirmation timed out.")

        except Exception as e:
            logger.error(f"Error in GUID link: {e}", exc_info=True)
            await ctx.send(f"❌ Error linking by GUID: {e}")

    async def _link_by_name(self, ctx, discord_id: str, player_name: str):
        """Name search linking with fuzzy matching."""
        try:
            # Search in player_aliases first
            alias_rows = await self.bot.db_adapter.fetch_all(
                """
                SELECT DISTINCT pa.guid
                FROM player_aliases pa
                WHERE LOWER(pa.alias) LIKE LOWER(?)
                ORDER BY pa.last_seen DESC
                LIMIT 5
            """,
                (f"%{player_name}%",),
            )
            alias_guids = [row[0] for row in alias_rows]

            # Also search main stats table
            matches = await self.bot.db_adapter.fetch_all(
                """
                SELECT p.player_guid, p.player_name,
                       SUM(p.kills) as total_kills,
                       COUNT(DISTINCT p.round_id) as games,
                       MAX(p.round_date) as last_seen
                FROM player_comprehensive_stats p
                JOIN rounds r ON p.round_id = r.id
                WHERE LOWER(p.player_name) LIKE LOWER(?)
                  AND r.round_number IN (1, 2)
                  AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
                GROUP BY p.player_guid, p.player_name
                ORDER BY last_seen DESC, games DESC
                LIMIT 5
            """,
                (f"%{player_name}%",),
            )

            # Combine and deduplicate
            guid_set = set(alias_guids)
            for match in matches:
                guid_set.add(match[0])

            if not guid_set:
                await ctx.send(
                    f"❌ No player found matching **'{player_name}'**\n\n"
                    f"💡 **Try:**\n"
                    f"   • `!find_player {player_name}` for detailed search\n"
                    f"   • `!link` (no arguments) to see top players\n"
                    f"   • `!list_players` to browse all players"
                )
                return

            # Get full data for found GUIDs
            guid_list = list(guid_set)[:3]  # Limit to 3

            if len(guid_list) == 1:
                # Single match - link directly with confirmation
                await self._link_by_guid(ctx, discord_id, guid_list[0])
            else:
                # Multiple matches - show options
                embed = discord.Embed(
                    title=f"🔍 Multiple Matches for '{player_name}'",
                    description="React with 1️⃣/2️⃣/3️⃣ to select your account:",
                    color=0x3498DB,
                )

                options_data = []
                for idx, guid in enumerate(guid_list, 1):
                    # Get stats and aliases
                    stats = await self.bot.db_adapter.fetch_one(
                        """
                        SELECT SUM(p.kills), SUM(p.deaths), COUNT(DISTINCT p.round_id), MAX(p.round_date)
                        FROM player_comprehensive_stats p
                        JOIN rounds r ON p.round_id = r.id
                        WHERE p.player_guid = ?
                          AND r.round_number IN (1, 2)
                          AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
                    """,
                        (guid,),
                    )

                    alias_rows = await self.bot.db_adapter.fetch_all(
                        """
                        SELECT alias FROM player_aliases
                        WHERE guid = ?
                        ORDER BY last_seen DESC LIMIT 3
                    """,
                        (guid,),
                    )
                    name = alias_rows[0][0] if alias_rows else "Unknown"
                    aliases_str = ", ".join([a[0] for a in alias_rows[:3]])

                    kills, deaths, games, last_seen = stats
                    kd = kills / deaths if deaths > 0 else kills

                    emoji = ["1️⃣", "2️⃣", "3️⃣"][idx - 1]
                    embed.add_field(
                        name=f"{emoji} **{name}**",
                        value=(
                            f"**GUID:** `{guid}`\n"
                            f"**Aliases:** {aliases_str}\n"
                            f"**Stats:** {kills:,} K / {kd:.2f} K/D | {games:,} games\n"
                            f"**Last:** {last_seen}"
                        ),
                        inline=False,
                    )

                    options_data.append({
                        "guid": guid,
                        "name": name,
                        "kills": kills,
                        "games": games,
                    })

                embed.set_footer(text=f"Or use: !link <GUID> | Requested by {ctx.author.display_name}")

                message = await ctx.send(embed=embed)

                emojis = ["1️⃣", "2️⃣", "3️⃣"][:len(guid_list)]
                for emoji in emojis:
                    await message.add_reaction(emoji)

                def check(reaction, user):
                    return (
                        user == ctx.author
                        and str(reaction.emoji) in emojis
                        and reaction.message.id == message.id
                    )

                try:
                    reaction, user = await self.bot.wait_for(
                        "reaction_add", timeout=60.0, check=check
                    )
                    selected_idx = emojis.index(str(reaction.emoji))
                    selected = options_data[selected_idx]

                    # Link it (database-specific syntax)
                    if self.bot.config.database_type == 'sqlite':
                        await self.bot.db_adapter.execute(
                            """
                            INSERT OR REPLACE INTO player_links
                            (discord_id, discord_username, et_guid, et_name, linked_date, verified)
                            VALUES (?, ?, ?, ?, datetime('now'), 1)
                            """,
                            (discord_id, str(ctx.author), selected["guid"], selected["name"]),
                        )
                    else:  # PostgreSQL
                        await self.bot.db_adapter.execute(
                            """
                            INSERT INTO player_links
                            (discord_id, discord_username, et_guid, et_name, linked_date, verified)
                            VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP, true)
                            ON CONFLICT (discord_id) DO UPDATE SET
                                discord_username = EXCLUDED.discord_username,
                                et_guid = EXCLUDED.et_guid,
                                et_name = EXCLUDED.et_name,
                                linked_date = EXCLUDED.linked_date,
                                verified = EXCLUDED.verified
                            """,
                            (discord_id, str(ctx.author), selected["guid"], selected["name"]),
                        )

                    await message.clear_reactions()
                    await ctx.send(
                        f"✅ Successfully linked to **{selected['name']}** (GUID: `{selected['guid']}`)\n\n"
                        f"💡 Use `!stats` to see your stats!"
                    )

                    logger.info(f"✅ Name link: {ctx.author} linked to {selected['name']} (GUID: {selected['guid']})")

                except asyncio.TimeoutError:
                    await message.clear_reactions()
                    await ctx.send("⏱️ Selection timed out.")

        except Exception as e:
            logger.error(f"Error in name link: {e}", exc_info=True)
            await ctx.send(f"❌ Error linking by name: {e}")

    async def _admin_link(self, ctx, target_user: discord.User, guid: str):
        """Admin linking: Link another user's Discord to a GUID."""
        try:
            # Check permissions
            if not ctx.author.guild_permissions.manage_guild:
                await ctx.send(
                    "❌ You don't have permission to link other users.\n\n"
                    "**Required:** Manage Server permission"
                )
                logger.warning(
                    f"⚠️ Unauthorized admin link attempt by {ctx.author} (ID: {ctx.author.id})"
                )
                return

            # Validate GUID format (8 hex characters)
            if len(guid) != 8 or not all(c in "0123456789ABCDEFabcdef" for c in guid):
                await ctx.send(
                    f"❌ Invalid GUID format: `{guid}`\n\n"
                    f"**GUIDs must be exactly 8 hexadecimal characters** (e.g., `D8423F90`)\n\n"
                    f"💡 **Find the GUID:**\n"
                    f"   • `!find_player {guid}` to search by name\n"
                    f"   • `!list_players` to browse all players\n"
                    f"   • Then use: `!link @user <GUID>`"
                )
                return

            target_discord_id = int(target_user.id)  # BIGINT in PostgreSQL

            # Check if target already linked
            existing = await self.bot.db_adapter.fetch_one(
                f"""
                SELECT player_name, player_guid FROM player_links
                WHERE discord_id = ?
            """,
                (target_discord_id,),
            )

            if existing:
                await ctx.send(
                    f"⚠️ {target_user.mention} is already linked to "
                    f"**{existing[0]}** (GUID: `{existing[1]}`)\n\n"
                    f"They need to `!unlink` first."
                )
                return

            # Validate GUID exists
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

            if not stats or stats[0] is None:
                await ctx.send(
                    f"❌ GUID `{guid}` not found in database.\n\n"
                    f"💡 Use `!find_player <name>` to search for the correct GUID."
                )
                return

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

            if aliases:
                primary_name = aliases[0][0]
                alias_list = [a[0] for a in aliases[:3]]
                alias_str = ", ".join(alias_list)
            else:
                # Fallback
                name_row = await self.bot.db_adapter.fetch_one(
                    """
                    SELECT player_name 
                    FROM player_comprehensive_stats 
                    WHERE player_guid = ? 
                    ORDER BY round_date DESC 
                    LIMIT 1
                """,
                    (guid,),
                )
                primary_name = name_row[0] if name_row else "Unknown"
                alias_str = primary_name

            kills, deaths, games, last_seen = stats
            kd_ratio = kills / deaths if deaths > 0 else kills

            # Admin confirmation embed
            embed = discord.Embed(
                    title="🔗 Admin Link Confirmation",
                    description=(
                        f"Link {target_user.mention} to **{primary_name}**?\n\n"
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
                value=f"`{guid}`",
                inline=True,
            )
            embed.add_field(
                name="Known Names (top 3)",
                value=alias_str,
                inline=False,
            )
            embed.add_field(
                name="Stats",
                value=(
                    f"**Kills:** {kills:,} | **Deaths:** {deaths:,}\n"
                    f"**K/D:** {kd_ratio:.2f} | **Games:** {games:,}"
                ),
                inline=True,
            )
            embed.add_field(
                name="Last Seen",
                value=last_seen,
                inline=True,
            )
            embed.set_footer(text="React ✅ (admin) to confirm or ❌ to cancel (60s)")

            message = await ctx.send(embed=embed)
            await message.add_reaction("✅")
            await message.add_reaction("❌")

            def check(reaction, user):
                return (
                    user == ctx.author  # Only admin can confirm
                    and str(reaction.emoji) in ["✅", "❌"]
                    and reaction.message.id == message.id
                )

            try:
                reaction, user = await self.bot.wait_for(
                    "reaction_add", timeout=60.0, check=check
                )

                if str(reaction.emoji) == "✅":
                    # Confirmed - link it (database-specific syntax)
                    if self.bot.config.database_type == 'sqlite':
                        await self.bot.db_adapter.execute(
                            """
                            INSERT OR REPLACE INTO player_links
                            (discord_id, discord_username, et_guid, et_name, linked_date, verified)
                            VALUES (?, ?, ?, ?, datetime('now'), 1)
                            """,
                            (target_discord_id, str(target_user), guid, primary_name),
                        )
                    else:  # PostgreSQL
                        await self.bot.db_adapter.execute(
                            """
                            INSERT INTO player_links
                            (discord_id, discord_username, et_guid, et_name, linked_date, verified)
                            VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP, true)
                            ON CONFLICT (discord_id) DO UPDATE SET
                                discord_username = EXCLUDED.discord_username,
                                et_guid = EXCLUDED.et_guid,
                                et_name = EXCLUDED.et_name,
                                linked_date = EXCLUDED.linked_date,
                                verified = EXCLUDED.verified
                            """,
                            (target_discord_id, str(target_user), guid, primary_name),
                        )

                    await message.clear_reactions()

                    # Success message
                    success_embed = discord.Embed(
                        title="✅ Admin Link Successful",
                        description=(
                            f"{target_user.mention} is now linked to **{primary_name}**"
                        ),
                        color=0x00FF00,
                    )
                    success_embed.add_field(
                        name="GUID",
                        value=f"`{guid}`",
                        inline=True,
                    )
                    success_embed.add_field(
                        name="Linked By",
                        value=ctx.author.mention,
                        inline=True,
                    )
                    success_embed.set_footer(
                        text=f"💡 {target_user.name} can now use !stats to see their stats"
                    )

                    await ctx.send(embed=success_embed)

                    # Log admin action
                    logger.info(
                        f"🔗 Admin link: {ctx.author} (ID: {ctx.author.id}) "
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

    @commands.command(name="unlink")
    async def unlink(self, ctx):
        """
        🔓 Unlink your Discord account from your in-game profile.

        Removes the connection between your Discord and your ET:Legacy account.
        You can re-link at any time using `!link`.

        Usage:
            !unlink

        Note:
            Your game stats are not deleted, only the Discord link is removed.
        """
        try:
            discord_id = int(ctx.author.id)  # BIGINT in PostgreSQL

            # Check if linked
            placeholder = '$1' if self.bot.config.database_type == 'postgresql' else '?'
            existing = await self.bot.db_adapter.fetch_one(
                f"""
                SELECT player_name, player_guid FROM player_links
                WHERE discord_id = ?
            """,
                (discord_id,),
            )

            if not existing:
                await ctx.send(
                    "❌ You don't have a linked account.\n\n"
                    "💡 Use `!link` to link your account!"
                )
                return

            player_name, guid = existing

            # Remove link
            await self.bot.db_adapter.execute(
                """
                DELETE FROM player_links
                WHERE discord_id = ?
            """,
                (discord_id,),
            )

            await ctx.send(
                f"✅ Successfully unlinked from **{player_name}** (GUID: `{guid}`)\n\n"
                f"💡 Your stats are still saved. Use `!link` to re-link anytime!"
            )

            logger.info(f"🔓 Unlink: {ctx.author} unlinked from {player_name} (GUID: {guid})")

        except Exception as e:
            logger.error(f"Error in unlink command: {e}", exc_info=True)
            await ctx.send(f"❌ Error unlinking account: {e}")

    @commands.command(name="select")
    async def select_option(self, ctx, selection: Optional[int] = None):
        """
        🔢 Select an option from a link prompt (alternative to reactions).

        This command provides a text-based alternative to clicking reaction emojis.
        Must be used within 60 seconds of a `!link` command showing options.

        Usage:
            !select <1-3>

        Args:
            selection: Option number (1, 2, or 3)

        Examples:
            !select 1  → Select first option
            !select 2  → Select second option

        Note:
            Currently requires using reactions on the link message.
            Future update will add persistent selection state.
        """
        if selection is None:
            await ctx.send(
                "❌ Please specify a number!\n\n"
                "**Usage:** `!select 1`, `!select 2`, or `!select 3`\n\n"
                "💡 This works with link prompts that show 1️⃣/2️⃣/3️⃣ reactions"
            )
            return

        if selection not in [1, 2, 3]:
            await ctx.send("❌ Please select 1, 2, or 3.")
            return

        await ctx.send(
            f"💡 You selected option **{selection}**!\n\n"
            f"**Note:** The `!select` command currently requires integration "
            f"with the link workflow.\n\n"
            f"**For now:**\n"
            f"• Use the reaction emojis (1️⃣/2️⃣/3️⃣) on the link message\n"
            f"• Or use `!link <GUID>` to link directly\n"
            f"• Or use `!find_player <name>` to find GUIDs\n\n"
            f"**Tip:** React to the message above within 60 seconds!"
        )

        # TODO: Implement persistent selection state
        # This would require storing pending link requests per user
        # and checking if they have an active selection window


async def setup(bot):
    """Load the Link Cog."""
    await bot.add_cog(LinkCog(bot))
