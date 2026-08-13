"""
Bolniška (Sick Leave) Cog — self-service identity attribution.

A player who picks up a fresh cl_guid during an injury / off-form stretch (a new
PC, a reinstall, or — carniee — playing from bed on a laptop) can mark it as a
"sick leave" alt of their main identity. The new guid is then ATTRIBUTED to them
(profile / movers 🩹 badge) WITHOUT merging the off-form stats into their main
record. See TOK F / migration 073 (player_identity_links).

Commands:
- !bolniska                     — show your current sick-leave status
- !bolniska start <GUID>        — mark <GUID> as your sick-leave alt (you must be linked)
- !bolniska end                 — close your open sick-leave period
- !bolniska merge <GUID>        — opt in to folding <GUID> into your main identity (Phase 3)
- !bolniska set @user <PRIMARY> <ALT>  — admin: set a link for anyone (Manage Server)
"""

import logging

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


def _valid_guid(g: str | None) -> bool:
    """ET GUIDs are stored as 8 hex characters."""
    return bool(g) and len(g) == 8 and all(c in "0123456789ABCDEFabcdef" for c in g)


class BolniskaCog(commands.Cog, name="Bolniska"):
    """🩹 Sick-leave identity attribution."""

    def __init__(self, bot):
        self.bot = bot
        logger.info("🩹 BolniskaCog loaded")

    # ── helpers ────────────────────────────────────────────────────────────
    async def _linked_guids(self, discord_id: int) -> list[str]:
        """Every guid linked to this Discord user (user_player_links, then the
        legacy player_links)."""
        rows = await self.bot.db_adapter.fetch_all(
            "SELECT player_guid FROM user_player_links WHERE user_id = $1",
            (discord_id,),
        ) or []
        guids = [r[0] for r in rows if r[0]]
        if not guids:
            rows = await self.bot.db_adapter.fetch_all(
                "SELECT player_guid FROM player_links WHERE discord_id = $1",
                (discord_id,),
            ) or []
            guids = [r[0] for r in rows if r[0]]
        return guids

    async def _main_guid(self, discord_id: int, exclude: str | None = None) -> str | None:
        """The invoker's main guid: the linked guid with the most rounds
        (excluding the candidate alt)."""
        guids = [g for g in await self._linked_guids(discord_id) if g != exclude]
        if not guids:
            return None
        if len(guids) == 1:
            return guids[0]
        row = await self.bot.db_adapter.fetch_one(
            "SELECT player_guid FROM player_comprehensive_stats "
            "WHERE player_guid = ANY($1) GROUP BY player_guid "
            "ORDER BY COUNT(*) DESC LIMIT 1",
            (guids,),
        )
        return row[0] if row else guids[0]

    async def _existing_link(self, alt_guid: str):
        return await self.bot.db_adapter.fetch_one(
            "SELECT primary_guid, alt_guid, link_type, period_end "
            "FROM player_identity_links WHERE alt_guid = $1",
            (alt_guid,),
        )

    async def _guid_seen(self, guid: str) -> bool:
        row = await self.bot.db_adapter.fetch_one(
            "SELECT 1 FROM player_comprehensive_stats WHERE player_guid = $1 LIMIT 1",
            (guid,),
        )
        return row is not None

    # ── commands ───────────────────────────────────────────────────────────
    @commands.group(name="bolniska", aliases=["sickleave"], invoke_without_command=True)
    async def bolniska(self, ctx):
        """Show your current sick-leave status."""
        guids = await self._linked_guids(ctx.author.id)
        if not guids:
            await ctx.send(
                "🩹 **Bolniška** keeps an injury / off-form stretch on a fresh "
                "cl_guid SEPARATE from your main stats, while still attributing it "
                "to you.\n\nYou have no linked guids yet — run `!link` first, then "
                "`!bolniska start <GUID>`."
            )
            return
        rows = await self.bot.db_adapter.fetch_all(
            "SELECT primary_guid, alt_guid, link_type, reason, period_start, period_end "
            "FROM player_identity_links "
            "WHERE primary_guid = ANY($1) OR alt_guid = ANY($1) "
            "ORDER BY period_start DESC NULLS LAST",
            (guids,),
        ) or []
        if not rows:
            await ctx.send(
                "🩹 No sick-leave links on your account. Start one with "
                "`!bolniska start <GUID>` (mark a new/injured cl_guid)."
            )
            return
        lines = []
        for r in rows:
            primary, alt, ltype, reason, p_start, p_end = r
            state = "OPEN" if p_end is None else f"ended {p_end}"
            lines.append(
                f"• `{alt}` → main `{primary}` — **{ltype}**"
                + (f" ({reason})" if reason else "")
                + f" · since {p_start or '?'} · {state}"
            )
        await ctx.send("🩹 **Your sick-leave links:**\n" + "\n".join(lines))

    @bolniska.command(name="start")
    async def bolniska_start(self, ctx, guid: str | None = None):
        """Mark <GUID> as your sick-leave alt (kept separate from your main stats)."""
        if not _valid_guid(guid):
            await ctx.send("❌ Usage: `!bolniska start <GUID>` — GUID is 8 hex chars.")
            return
        guid = guid.upper()
        primary = await self._main_guid(ctx.author.id, exclude=guid)
        if not primary:
            await ctx.send(
                "❌ You need a linked main identity first. Run `!link` to link your "
                "primary guid, then `!bolniska start <GUID>`. (Admins can use "
                "`!bolniska set @user <PRIMARY> <ALT>` for unlinked players.)"
            )
            return
        if primary == guid:
            await ctx.send("❌ The sick-leave guid must differ from your main guid.")
            return
        if not await self._guid_seen(guid):
            await ctx.send(f"❌ No stats found for `{guid}` — is that the right cl_guid?")
            return
        existing = await self._existing_link(guid)
        if existing:
            await ctx.send(
                f"⚠️ `{guid}` is already linked to main `{existing[0]}` "
                f"({existing[2]}). Use `!bolniska end` to close it, or ask an admin."
            )
            return
        await self.bot.db_adapter.execute(
            "INSERT INTO player_identity_links "
            "(primary_guid, alt_guid, link_type, reason, period_start, created_by) "
            "VALUES ($1, $2, 'sick_leave', 'injury', CURRENT_DATE, $3) "
            "ON CONFLICT (alt_guid) DO NOTHING",
            (primary, guid, int(ctx.author.id)),
        )
        await ctx.send(
            f"🩹 On sick leave — `{guid}` is now attributed to your main `{primary}`, "
            "kept SEPARATE from your main stats. Close it with `!bolniska end` when "
            "you're back, or `!bolniska merge {guid}` to fold it in."
        )

    @bolniska.command(name="end")
    async def bolniska_end(self, ctx):
        """Close your open sick-leave period."""
        guids = await self._linked_guids(ctx.author.id)
        if not guids:
            await ctx.send("❌ No linked guids. Run `!link` first.")
            return
        row = await self.bot.db_adapter.fetch_one(
            "SELECT alt_guid FROM player_identity_links "
            "WHERE (primary_guid = ANY($1) OR alt_guid = ANY($1)) "
            "AND link_type = 'sick_leave' AND period_end IS NULL "
            "ORDER BY period_start DESC LIMIT 1",
            (guids,),
        )
        if not row:
            await ctx.send("🩹 You have no open sick-leave period.")
            return
        await self.bot.db_adapter.execute(
            "UPDATE player_identity_links SET period_end = CURRENT_DATE WHERE alt_guid = $1",
            (row[0],),
        )
        await ctx.send(
            f"🩹 Sick leave for `{row[0]}` closed. It stays a linked, separate "
            "identity — use `!bolniska merge {guid}` if you want to fold it into your main."
        )

    @bolniska.command(name="merge")
    async def bolniska_merge(self, ctx, guid: str | None = None):
        """Opt in to folding <GUID>'s stats into your main identity (Phase 3)."""
        if not _valid_guid(guid):
            await ctx.send("❌ Usage: `!bolniska merge <GUID>`.")
            return
        guid = guid.upper()
        guids = await self._linked_guids(ctx.author.id)
        existing = await self._existing_link(guid)
        if not existing or (existing[0] not in guids and guid not in guids):
            await ctx.send(
                f"❌ `{guid}` isn't one of your sick-leave links. Start it with "
                "`!bolniska start <GUID>` first."
            )
            return
        await self.bot.db_adapter.execute(
            "UPDATE player_identity_links SET link_type = 'merged', "
            "period_end = COALESCE(period_end, CURRENT_DATE) WHERE alt_guid = $1",
            (guid,),
        )
        await ctx.send(
            f"🔗 `{guid}` marked to MERGE into main `{existing[0]}`. Once merge "
            "resolution ships (Phase 3), your histories count as one everywhere."
        )

    @bolniska.command(name="set")
    @commands.has_permissions(manage_guild=True)
    async def bolniska_set(self, ctx, target: discord.User | None = None,
                           primary: str | None = None, alt: str | None = None):
        """Admin: set a sick-leave link for anyone (e.g. an unlinked player)."""
        if not _valid_guid(primary) or not _valid_guid(alt):
            await ctx.send("❌ Usage: `!bolniska set @user <PRIMARY_GUID> <ALT_GUID>`.")
            return
        primary, alt = primary.upper(), alt.upper()
        if primary == alt:
            await ctx.send("❌ PRIMARY and ALT must differ.")
            return
        existing = await self._existing_link(alt)
        if existing:
            await ctx.send(f"⚠️ `{alt}` already links to `{existing[0]}` ({existing[2]}).")
            return
        await self.bot.db_adapter.execute(
            "INSERT INTO player_identity_links "
            "(primary_guid, alt_guid, link_type, reason, period_start, created_by, notes) "
            "VALUES ($1, $2, 'sick_leave', 'injury', CURRENT_DATE, $3, $4) "
            "ON CONFLICT (alt_guid) DO NOTHING",
            (primary, alt, int(ctx.author.id),
             f"admin set by {ctx.author} for {target}" if target else f"admin set by {ctx.author}"),
        )
        await ctx.send(f"🩹 Set sick-leave: `{alt}` → main `{primary}`.")

    @bolniska_set.error
    async def _set_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ `!bolniska set` needs the **Manage Server** permission.")


async def setup(bot):
    """Load the Bolniška Cog."""
    await bot.add_cog(BolniskaCog(bot))
