"""LinkCog mixin: Interactive UI commands: unlink, select_option, setname, myaliases.

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


class _LinkInteractiveMixin:
    """Interactive UI commands: unlink, select_option, setname, myaliases for LinkCog."""

    @is_public_channel()
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
            existing = await self.bot.db_adapter.fetch_one(
                """
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
                "💡 Your stats are still saved. Use `!link` to re-link anytime!"
            )

            logger.info(f"🔓 Unlink: {ctx.author} unlinked from {player_name} (GUID: {guid})")

        except Exception as e:
            logger.error(f"Error in unlink command: {e}", exc_info=True)
            await ctx.send(f"❌ Error unlinking account: {sanitize_error_message(e)}")

    @is_public_channel()
    @commands.command(name="select")
    async def select_option(self, ctx, selection: int | None = None):
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

        if not self.enable_link_selection_state:
            await ctx.send(
                f"💡 You selected option **{selection}**!\n\n"
                "**Note:** The `!select` command is disabled until verified.\n\n"
                "**For now:**\n"
                "• Use the reaction emojis (1️⃣/2️⃣/3️⃣) on the link message\n"
                "• Or use `!link <GUID>` to link directly\n"
                "• Or use `!find_player <name>` to find GUIDs\n\n"
                "**Tip:** React to the message above within 60 seconds!"
            )
            return

        discord_id = int(ctx.author.id)
        pending = self._get_link_selection(discord_id)
        if not pending:
            await ctx.send(
                "❌ No active selection found (or it expired).\n\n"
                "💡 Use `!link` or `!link <name>` to start a new selection."
            )
            return

        options = pending.get("options", [])
        if selection < 1 or selection > len(options):
            await ctx.send(
                f"❌ Invalid selection. Choose 1-{len(options)}."
            )
            return

        selected = options[selection - 1]
        await self._apply_link_selection(ctx, discord_id, selected)
        self._clear_link_selection(discord_id)

    @is_public_channel()
    @commands.command(name="setname")
    async def setname(self, ctx, option: str = None, *, name: str = None):
        """
        ✏️ Set your custom display name

        Linked players can choose how their name appears in stats.
        Your display name will show instead of random aliases in !last_session.

        Usage:
            !setname <custom_name>       → Set a custom display name
            !setname alias <name>        → Use one of your aliases
            !setname reset               → Reset to automatic (most recent alias)

        Examples:
            !setname MyAwesomeName
            !setname alias PlayerOne
            !setname reset

        Requirements:
            - Must be linked (!link to link your account)
            - Custom names: 2-32 characters
            - Alias names: Must be from your existing aliases (!myaliases to view)
        """
        if not option:
            await ctx.send(
                "❌ Please specify what you want to do!\n\n"
                "**Usage:**\n"
                "`!setname <custom_name>` - Set custom name\n"
                "`!setname alias <name>` - Use one of your aliases\n"
                "`!setname reset` - Reset to automatic\n\n"
                "**Example:** `!setname MyAwesomeName`"
            )
            return

        # Handle reset
        if option.lower() == "reset":
            success, message = await self.display_name_service.reset_display_name(ctx.author.id)
            if success:
                await ctx.send(f"✅ {message}")
            else:
                await ctx.send(f"❌ {message}")
            return

        # Handle alias selection
        if option.lower() == "alias":
            if not name:
                await ctx.send(
                    "❌ Please specify which alias to use!\n\n"
                    "**Usage:** `!setname alias <name>`\n"
                    "**Example:** `!setname alias PlayerOne`\n\n"
                    "Use `!myaliases` to see your available aliases."
                )
                return

            success, message = await self.display_name_service.set_alias_display_name(
                ctx.author.id,
                name
            )
            if success:
                await ctx.send(f"✅ {message}")
            else:
                await ctx.send(f"❌ {message}")
            return

        # Handle custom name (option is the name if not 'reset' or 'alias')
        custom_name = f"{option} {name}" if name else option

        success, message = await self.display_name_service.set_custom_display_name(
            ctx.author.id,
            custom_name
        )

        if success:
            await ctx.send(f"✅ {message}")
        else:
            await ctx.send(f"❌ {message}")

    @is_public_channel()
    @commands.command(name="myaliases", aliases=["aliases", "mynames"])
    async def myaliases(self, ctx):
        """
        📝 View all your player aliases

        Shows all names you've used in-game, sorted by most recent.
        You can use any of these as your display name with `!setname alias <name>`.

        Usage:
            !myaliases

        Requirements:
            - Must be linked (!link to link your account)

        Tip:
            Use `!setname alias <name>` to set your display name to one of these aliases.
        """
        success, aliases = await self.display_name_service.get_player_aliases(ctx.author.id)

        if not success:
            await ctx.send(
                "❌ You must be linked to view your aliases.\n\n"
                "Use `!link` to link your Discord account to your in-game profile."
            )
            return

        if not aliases:
            await ctx.send("❌ No aliases found. Play some games to build your alias history!")
            return

        # Build embed
        embed = discord.Embed(
            title=f"📝 {ctx.author.display_name}'s Aliases",
            description=f"All names you've used in-game • `{len(aliases)}` total aliases",
            color=0x5865F2,
            timestamp=datetime.now()
        )

        # Group aliases for better display
        alias_lines = []
        for i, (alias, times_seen, last_seen) in enumerate(aliases[:20], 1):
            # Format last_seen
            try:
                last_seen_dt = datetime.fromisoformat(last_seen.replace("Z", "+00:00") if "Z" in last_seen else last_seen)
                last_seen_str = last_seen_dt.strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                last_seen_str = "Unknown"

            alias_lines.append(
                f"{i}. **{alias}** • Used `{times_seen}x` • Last: `{last_seen_str}`"
            )

        # Split into fields if too many
        chunk_size = 10
        for i in range(0, len(alias_lines), chunk_size):
            chunk = alias_lines[i:i+chunk_size]
            field_name = f"Aliases {i+1}-{min(i+chunk_size, len(alias_lines))}" if i > 0 else "Your Aliases"
            embed.add_field(
                name=field_name,
                value="\n".join(chunk),
                inline=False
            )

        if len(aliases) > 20:
            embed.add_field(
                name="💡 Note",
                value=f"Showing top 20 of {len(aliases)} aliases (sorted by most recent)",
                inline=False
            )

        embed.add_field(
            name="✏️ Set Display Name",
            value=(
                "Use any of these as your display name:\n"
                "`!setname alias <name>` - Use an alias\n"
                "`!setname <custom>` - Use a custom name\n"
                "`!setname reset` - Reset to automatic"
            ),
            inline=False
        )

        embed.set_footer(text=f"🎮 Your display name appears in !last_session • Requested by {ctx.author.name}")
        await ctx.send(embed=embed)
