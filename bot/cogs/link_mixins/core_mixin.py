"""LinkCog mixin: Link dispatcher + selection state helpers + smart/guid/name/admin link flows.

Extracted from bot/cogs/link_cog.py in Mega Audit v4 / Sprint 4.

All methods live on LinkCog via mixin inheritance.
"""
from __future__ import annotations

import logging
from datetime import datetime

import discord
from discord.ext import commands

from bot.core.checks import is_public_channel
from bot.core.utils import sanitize_error_message

logger = logging.getLogger("bot.cogs.link")


class _LinkCoreMixin:
    """Link dispatcher + selection state helpers + smart/guid/name/admin link flows for LinkCog."""

    def _store_link_selection(self, discord_id: int, message_id: int, options: list[dict]):
        """Store pending link selection (in-memory, experimental)."""
        if not self.enable_link_selection_state:
            return
        expires_at = datetime.utcnow().timestamp() + self.selection_ttl_seconds
        self.pending_link_selections[discord_id] = {
            "message_id": message_id,
            "options": options,
            "expires_at": expires_at,
        }

    def _get_link_selection(self, discord_id: int) -> dict | None:
        """Get pending link selection if valid."""
        pending = self.pending_link_selections.get(discord_id)
        if not pending:
            return None
        if pending.get("expires_at", 0) < datetime.utcnow().timestamp():
            self.pending_link_selections.pop(discord_id, None)
            return None
        return pending

    def _clear_link_selection(self, discord_id: int) -> None:
        """Clear pending selection for a user."""
        if discord_id in self.pending_link_selections:
            del self.pending_link_selections[discord_id]

    async def _apply_link_selection(self, ctx, discord_id: int, selected: dict):
        """Apply a selected link option (shared by reactions and !select)."""
        existing = await self.bot.db_adapter.fetch_one(
            """
            SELECT player_name, player_guid FROM player_links
            WHERE discord_id = ?
            """,
            (discord_id,),
        )
        if existing:
            await ctx.send(
                f"⚠️ You're already linked to **{existing[0]}** (GUID: `{existing[1]}`)\n\n"
                "Use `!unlink` first to change your linked account."
            )
            return

        await self.bot.db_adapter.execute(
            """
            INSERT INTO player_links
            (discord_id, discord_username, player_guid, player_name, linked_at)
            VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP)
            ON CONFLICT (discord_id) DO UPDATE SET
                discord_username = EXCLUDED.discord_username,
                player_guid = EXCLUDED.player_guid,
                player_name = EXCLUDED.player_name,
                linked_at = EXCLUDED.linked_at
            """,
            (discord_id, str(ctx.author), selected["guid"], selected["name"]),
        )

        success_embed = discord.Embed(
            title="✅ Account Linked Successfully!",
            description=f"You're now linked to **{selected['name']}**",
            color=0x00FF00,
        )
        if "games" in selected and "kills" in selected:
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

    @is_public_channel()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.command(name="link")
    async def link(self, ctx, target: str | None = None, *, guid: str | None = None):
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
            existing = await self.bot.db_adapter.fetch_one(
                """
                SELECT player_name, player_guid FROM player_links
                WHERE discord_id = ?
            """,
                (discord_id,),
            )

            if existing:
                await ctx.send(
                    f"⚠️ You're already linked to **{existing[0]}** (GUID: `{existing[1]}`)\n\n"
                    "Use `!unlink` first to change your linked account.\n"
                    "Use `!stats` to see your stats!"
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
                "💡 Try: `!find_player <name>` to search for players with GUIDs"
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
                    "**Select your account:**\n"
                    "• React with 1️⃣/2️⃣/3️⃣ below\n"
                    "• Or use `!select <number>` within 60 seconds\n"
                    "• Or use `!find_player <name>` to search"
                ),
                color=0x3498DB,
            )

            # Optimize: Fetch all aliases in a single query (avoid N+1 problem)
            all_guids = [player[0] for player in top_players]
            # Safe: placeholders are generated strings ($1, $2, $3), not user input
            placeholders = ', '.join([f'${i+1}' for i in range(len(all_guids))])
            alias_query = f"""
                SELECT guid, alias, last_seen, times_seen
                FROM player_aliases
                WHERE guid IN ({placeholders})
                ORDER BY guid, last_seen DESC, times_seen DESC
            """

            all_aliases = await self.bot.db_adapter.fetch_all(alias_query, all_guids)

            # Group aliases by GUID
            aliases_by_guid = {}
            for alias_row in all_aliases:
                guid_key = alias_row[0]
                if guid_key not in aliases_by_guid:
                    aliases_by_guid[guid_key] = []
                aliases_by_guid[guid_key].append((alias_row[1], alias_row[2], alias_row[3]))

            options_data = []
            for idx, (guid, last_date, kills, deaths, games) in enumerate(top_players, 1):
                # Get aliases from pre-fetched data
                aliases = aliases_by_guid.get(guid, [])[:3]

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
            cancel_emoji = "❌"

            for emoji in emojis:
                await message.add_reaction(emoji)
            await message.add_reaction(cancel_emoji)

            # Cache options for !select (optional feature flag)
            self._store_link_selection(discord_id, message.id, options_data)

            # Wait for reaction
            def check(reaction, user):
                return (
                    user == ctx.author
                    and str(reaction.emoji) in emojis + [cancel_emoji]
                    and reaction.message.id == message.id
                )

            try:
                reaction, user = await self.bot.wait_for(
                    "reaction_add", timeout=60.0, check=check
                )

                # Handle cancellation
                if str(reaction.emoji) == cancel_emoji:
                    await message.clear_reactions()
                    self._clear_link_selection(discord_id)
                    await ctx.send(
                        "❌ Link cancelled.\n\n"
                        "💡 Use `!link` to try again or `!find_player <name>` to search for a specific player"
                    )
                    return

                # Get selected index
                selected_idx = emojis.index(str(reaction.emoji))
                selected = options_data[selected_idx]

                await self._apply_link_selection(ctx, discord_id, selected)
                await message.clear_reactions()
                self._clear_link_selection(discord_id)

                logger.info(
                    f"✅ Self-link: {ctx.author} linked to {selected['name']} (GUID: {selected['guid']})"
                )

            except TimeoutError:
                await message.clear_reactions()
                self._clear_link_selection(discord_id)
                await ctx.send(
                    "⏱️ Link request timed out (60s expired).\n\n"
                    "💡 Try again with `!link` or use `!find_player <name>` to search"
                )

        except Exception as e:
            logger.error(f"Error in smart self-link: {e}", exc_info=True)
            await ctx.send(f"❌ Error during self-linking: {sanitize_error_message(e)}")

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
                    "💡 **Try:**\n"
                    "   • `!find_player <name>` to search by name\n"
                    "   • `!list_players` to browse all players\n"
                    "   • Double-check the GUID spelling"
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
                    # Confirmed - link it
                    await self.bot.db_adapter.execute(
                        """
                        INSERT INTO player_links
                        (discord_id, discord_username, player_guid, player_name, linked_at)
                        VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP)
                        ON CONFLICT (discord_id) DO UPDATE SET
                            discord_username = EXCLUDED.discord_username,
                            player_guid = EXCLUDED.player_guid,
                            player_name = EXCLUDED.player_name,
                            linked_at = EXCLUDED.linked_at
                        """,
                        (discord_id, str(ctx.author), guid, primary_name),
                    )

                    await message.clear_reactions()
                    await ctx.send(
                        f"✅ Successfully linked to **{primary_name}** (GUID: `{guid}`)\n\n"
                        "💡 Use `!stats` to see your stats!"
                    )

                    logger.info(f"✅ GUID link: {ctx.author} linked to {primary_name} (GUID: {guid})")
                else:
                    await message.clear_reactions()
                    await ctx.send("❌ Link cancelled.")

            except TimeoutError:
                await message.clear_reactions()
                await ctx.send("⏱️ Confirmation timed out.")

        except Exception as e:
            logger.error(f"Error in GUID link: {e}", exc_info=True)
            await ctx.send(f"❌ Error linking by GUID: {sanitize_error_message(e)}")

    async def _link_by_name(self, ctx, discord_id: str, player_name: str):
        """Name search linking with fuzzy matching."""
        try:
            # Search in player_aliases first
            alias_rows = await self.bot.db_adapter.fetch_all(
                """
                SELECT pa.guid, MAX(pa.last_seen) as max_last_seen
                FROM player_aliases pa
                WHERE LOWER(pa.alias) LIKE LOWER(?)
                GROUP BY pa.guid
                ORDER BY max_last_seen DESC
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
                    "💡 **Try:**\n"
                    f"   • `!find_player {player_name}` for detailed search\n"
                    "   • `!link` (no arguments) to see top players\n"
                    "   • `!list_players` to browse all players"
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

                # Cache options for !select (optional feature flag)
                self._store_link_selection(discord_id, message.id, options_data)

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

                    await self._apply_link_selection(ctx, discord_id, selected)
                    await message.clear_reactions()
                    self._clear_link_selection(discord_id)

                    logger.info(f"✅ Name link: {ctx.author} linked to {selected['name']} (GUID: {selected['guid']})")

                except TimeoutError:
                    await message.clear_reactions()
                    self._clear_link_selection(discord_id)
                    await ctx.send("⏱️ Selection timed out.")

        except Exception as e:
            logger.error(f"Error in name link: {e}", exc_info=True)
            await ctx.send(f"❌ Error linking by name: {sanitize_error_message(e)}")

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
                    "**GUIDs must be exactly 8 hexadecimal characters** (e.g., `D8423F90`)\n\n"
                    "💡 **Find the GUID:**\n"
                    f"   • `!find_player {guid}` to search by name\n"
                    "   • `!list_players` to browse all players\n"
                    "   • Then use: `!link @user <GUID>`"
                )
                return

            target_discord_id = int(target_user.id)  # BIGINT in PostgreSQL

            # Check if target already linked
            existing = await self.bot.db_adapter.fetch_one(
                """
                SELECT player_name, player_guid FROM player_links
                WHERE discord_id = ?
            """,
                (target_discord_id,),
            )

            if existing:
                await ctx.send(
                    f"⚠️ {target_user.mention} is already linked to "
                    f"**{existing[0]}** (GUID: `{existing[1]}`)\n\n"
                    "They need to `!unlink` first."
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
                    "💡 Use `!find_player <name>` to search for the correct GUID."
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
                    # Confirmed - link it
                    await self.bot.db_adapter.execute(
                        """
                        INSERT INTO player_links
                        (discord_id, discord_username, player_guid, player_name, linked_at)
                        VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP)
                        ON CONFLICT (discord_id) DO UPDATE SET
                            discord_username = EXCLUDED.discord_username,
                            player_guid = EXCLUDED.player_guid,
                            player_name = EXCLUDED.player_name,
                            linked_at = EXCLUDED.linked_at
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

            except TimeoutError:
                await message.clear_reactions()
                await ctx.send("⏱️ Admin link confirmation timed out.")

        except Exception as e:
            logger.error(f"Error in admin link: {e}", exc_info=True)
            await ctx.send(f"❌ Error during admin linking: {sanitize_error_message(e)}")
