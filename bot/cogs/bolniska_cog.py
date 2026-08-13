"""
Bolniška (Sick Leave) Cog — self-service identity attribution.

A player who picks up a fresh cl_guid during an injury / off-form stretch (a new
PC, a reinstall, or — carniee — playing from bed on a laptop) can mark it as a
"sick leave" alt of their main identity. The new guid is then ATTRIBUTED to them
(profile / movers 🩹 badge) WITHOUT merging the off-form stats into their main
record. See TOK F / migration 073 (player_identity_links).

Commands:
- !bolniska                     — show your current sick-leave status
- !bolniska start <GUID>        — mark <GUID> (which you must have linked) as your
                                  sick-leave alt, kept separate from your main stats
- !bolniska end                 — close your open sick-leave period
- !bolniska merge <GUID>        — opt in to folding <GUID> into your main identity (Phase 3)
- !bolniska set @user <PRIMARY> <ALT>  — admin: set a link for anyone (Manage Server + admin channel)
"""

import logging

import discord
from discord.ext import commands

from bot.core.checks import is_admin_channel, is_public_channel

logger = logging.getLogger(__name__)


def _valid_guid(g: str | None) -> bool:
    """ET GUIDs are stored as 8 hex characters."""
    return bool(g) and len(g) == 8 and all(c in "0123456789ABCDEFabcdef" for c in g)


class BolniskaCog(commands.Cog, name="Bolniska"):
    """🩹 Sick-leave identity attribution."""

    def __init__(self, bot):
        self.bot = bot
        logger.info("🩹 BolniskaCog loaded")

    # ── helpers (all queries use ? placeholders — the adapter translates) ────
    async def _linked_guids(self, discord_id: int) -> list[str]:
        """Every guid linked to this Discord user (user_player_links, then the
        legacy player_links). This is the ownership source of truth."""
        rows = await self.bot.db_adapter.fetch_all(
            "SELECT player_guid FROM user_player_links WHERE user_id = ?",
            (discord_id,),
        ) or []
        guids = [r[0] for r in rows if r[0]]
        if not guids:
            rows = await self.bot.db_adapter.fetch_all(
                "SELECT player_guid FROM player_links WHERE discord_id = ?",
                (discord_id,),
            ) or []
            guids = [r[0] for r in rows if r[0]]
        return guids

    async def _main_guid(self, guids: list[str], exclude: str | None = None) -> str | None:
        """The player's main guid among ``guids``: the one with the most rounds
        (excluding the candidate alt)."""
        candidates = [g for g in guids if g != exclude]
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]
        row = await self.bot.db_adapter.fetch_one(
            "SELECT player_guid FROM player_comprehensive_stats "
            "WHERE player_guid = ANY(?) GROUP BY player_guid "
            "ORDER BY COUNT(*) DESC LIMIT 1",
            (candidates,),
        )
        return row[0] if row else candidates[0]

    async def _existing_link(self, alt_guid: str):
        return await self.bot.db_adapter.fetch_one(
            "SELECT primary_guid, alt_guid, link_type, period_end "
            "FROM player_identity_links WHERE alt_guid = ?",
            (alt_guid,),
        )

    async def _linked_to_other(self, guid: str, discord_id: int) -> bool:
        """True if ``guid`` is already linked to a DIFFERENT Discord account —
        the ownership guard: you may attribute an unclaimed guid to yourself, but
        not hijack a guid someone else has linked."""
        row = await self.bot.db_adapter.fetch_one(
            "SELECT user_id FROM user_player_links WHERE player_guid = ? "
            "AND user_id <> ? LIMIT 1",
            (guid, discord_id),
        )
        if row:
            return True
        row = await self.bot.db_adapter.fetch_one(
            "SELECT discord_id FROM player_links WHERE player_guid = ? "
            "AND discord_id <> ? LIMIT 1",
            (guid, discord_id),
        )
        return row is not None

    async def _guid_seen(self, guid: str) -> bool:
        row = await self.bot.db_adapter.fetch_one(
            "SELECT 1 FROM player_comprehensive_stats WHERE player_guid = ? LIMIT 1",
            (guid,),
        )
        return row is not None

    # ── commands ─────────────────────────────────────────────────────────────
    @commands.group(name="bolniska", aliases=["sickleave"], invoke_without_command=True)
    @is_public_channel()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def bolniska(self, ctx):
        """🩹 Sick-leave attribution. No args: your status. Subcommands: `start <GUID>`, `end`, `merge <GUID>`; admin `set @user <PRIMARY> <ALT>` (Manage Server + admin channel)."""
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
            "WHERE primary_guid = ANY(?) OR alt_guid = ANY(?) "
            "ORDER BY period_start DESC NULLS LAST",
            (guids, guids),
        ) or []
        if not rows:
            await ctx.send(
                "🩹 No sick-leave links on your account. Start one with "
                "`!bolniska start <GUID>` (mark a new/injured cl_guid you've linked)."
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
    @is_public_channel()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def bolniska_start(self, ctx, guid: str | None = None):
        """Mark a GUID YOU'VE LINKED as your sick-leave alt (kept separate)."""
        if not _valid_guid(guid):
            await ctx.send("❌ Usage: `!bolniska start <GUID>` — GUID is 8 hex chars.")
            return
        guid = guid.upper()
        # Ownership (stats presence is NOT ownership):
        #  1) the invoker must be a linked player — proves they're not anonymous;
        #  2) the alt must not already be linked to a DIFFERENT account — you may
        #     attribute an unclaimed new guid to yourself, but never hijack one
        #     someone else has claimed. created_by is recorded for admin review.
        linked = await self._linked_guids(ctx.author.id)
        if not linked:
            await ctx.send(
                "❌ Link your main identity first with `!link`, then "
                f"`!bolniska start {guid}`. (Admins: `!bolniska set @user <PRIMARY> <ALT>`.)"
            )
            return
        primary = await self._main_guid(linked, exclude=guid)
        if not primary:
            await ctx.send("❌ The sick-leave guid must differ from your linked main guid.")
            return
        if not await self._guid_seen(guid):
            await ctx.send(f"❌ No stats found for `{guid}` — is that the right cl_guid?")
            return
        if await self._linked_to_other(guid, ctx.author.id):
            await ctx.send(
                f"❌ `{guid}` is linked to another account — ask an admin if that's a mistake."
            )
            return
        existing = await self._existing_link(guid)
        if existing:
            await ctx.send(
                f"⚠️ `{guid}` is already linked to main `{existing[0]}` "
                f"({existing[2]}). Use `!bolniska end` to close it, or ask an admin."
            )
            return
        # INSERT ... RETURNING so a lost ON CONFLICT race is reported honestly.
        row = await self.bot.db_adapter.fetch_one(
            "INSERT INTO player_identity_links "
            "(primary_guid, alt_guid, link_type, reason, period_start, created_by) "
            "VALUES (?, ?, 'sick_leave', 'injury', CURRENT_DATE, ?) "
            "ON CONFLICT (alt_guid) DO NOTHING RETURNING id",
            (primary, guid, int(ctx.author.id)),
        )
        if not row:
            await ctx.send(f"⚠️ `{guid}` was just linked by another request — nothing to do.")
            return
        await ctx.send(
            f"🩹 On sick leave — `{guid}` is now attributed to your main `{primary}`, "
            f"kept SEPARATE from your main stats. Close it with `!bolniska end` when "
            f"you're back, or `!bolniska merge {guid}` to fold it in."
        )

    @bolniska.command(name="end")
    @is_public_channel()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def bolniska_end(self, ctx):
        """Close your open sick-leave period."""
        guids = await self._linked_guids(ctx.author.id)
        if not guids:
            await ctx.send("❌ No linked guids. Run `!link` first.")
            return
        row = await self.bot.db_adapter.fetch_one(
            "SELECT alt_guid FROM player_identity_links "
            "WHERE (primary_guid = ANY(?) OR alt_guid = ANY(?)) "
            "AND link_type = 'sick_leave' AND period_end IS NULL "
            "ORDER BY period_start DESC LIMIT 1",
            (guids, guids),
        )
        if not row:
            await ctx.send("🩹 You have no open sick-leave period.")
            return
        alt = row[0]
        await self.bot.db_adapter.execute(
            "UPDATE player_identity_links SET period_end = CURRENT_DATE WHERE alt_guid = ?",
            (alt,),
        )
        await ctx.send(
            f"🩹 Sick leave for `{alt}` closed. It stays a linked, separate "
            f"identity — use `!bolniska merge {alt}` if you want to fold it into your main."
        )

    @bolniska.command(name="merge")
    @is_public_channel()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def bolniska_merge(self, ctx, guid: str | None = None):
        """Opt in to folding a sick-leave GUID's stats into your main identity (Phase 3)."""
        if not _valid_guid(guid):
            await ctx.send("❌ Usage: `!bolniska merge <GUID>`.")
            return
        guid = guid.upper()
        guids = {g.upper() for g in await self._linked_guids(ctx.author.id)}
        existing = await self._existing_link(guid)
        # Ownership + only convert an actual sick-leave link (never an alias).
        if not existing or (existing[0].upper() not in guids and guid not in guids):
            await ctx.send(
                f"❌ `{guid}` isn't one of your sick-leave links. Start it with "
                "`!bolniska start <GUID>` first."
            )
            return
        if existing[2] != "sick_leave":
            await ctx.send(
                f"❌ `{guid}` is a `{existing[2]}` link, not a sick-leave one — "
                "nothing to merge."
            )
            return
        await self.bot.db_adapter.execute(
            "UPDATE player_identity_links SET link_type = 'merged', "
            "period_end = COALESCE(period_end, CURRENT_DATE) WHERE alt_guid = ?",
            (guid,),
        )
        await ctx.send(
            f"🔗 `{guid}` marked to MERGE into main `{existing[0]}`. Once merge "
            "resolution ships (Phase 3), your histories count as one everywhere."
        )

    @bolniska.command(name="set")
    @is_admin_channel()
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
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
        row = await self.bot.db_adapter.fetch_one(
            "INSERT INTO player_identity_links "
            "(primary_guid, alt_guid, link_type, reason, period_start, created_by, notes) "
            "VALUES (?, ?, 'sick_leave', 'injury', CURRENT_DATE, ?, ?) "
            "ON CONFLICT (alt_guid) DO NOTHING RETURNING id",
            (primary, alt, int(ctx.author.id),
             f"admin set by {ctx.author} for {target}" if target else f"admin set by {ctx.author}"),
        )
        if not row:
            await ctx.send(f"⚠️ `{alt}` was just linked by another request — nothing to do.")
            return
        await ctx.send(f"🩹 Set sick-leave: `{alt}` → main `{primary}`.")

    @bolniska_set.error
    async def _set_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ `!bolniska set` needs the **Manage Server** permission.")


async def setup(bot):
    """Load the Bolniška Cog."""
    await bot.add_cog(BolniskaCog(bot))
