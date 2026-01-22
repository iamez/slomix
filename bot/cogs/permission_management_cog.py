"""
Permission Management Cog
========================
Commands for managing user permissions (root-only).

Security: User ID-based whitelist system (immune to Discord role exploits)
Tiers: Root (1) → Admin (many) → Moderator (many)
Database: user_permissions, permission_audit_log tables

Commands:
- !admin_add - Add user to permission whitelist (root-only)
- !admin_remove - Remove user from whitelist (root-only)
- !admin_list - List all users with permissions (admin+)
- !admin_audit - View permission change audit log (root-only)
"""

import logging
from datetime import datetime
from typing import Optional

import discord
from discord.ext import commands

from bot.core.checks import is_owner, is_admin

logger = logging.getLogger("PermissionManagement")


class PermissionManagement(commands.Cog):
    """🔒 User Permission Management Commands"""

    def __init__(self, bot):
        self.bot = bot
        logger.info("✅ Permission Management cog loaded")

    @is_owner()
    @commands.command(name='admin_add', aliases=['perm_add'])
    async def add_admin(self, ctx, user: discord.Member, tier: str, *, reason: Optional[str] = "No reason provided"):
        """➕ Add user to permission whitelist (Root only)

        Usage: !admin_add @user <tier> [reason]
        Tiers: admin, moderator
        Example: !admin_add @john admin Trusted community member
        """
        # Validate tier
        valid_tiers = ['admin', 'moderator']
        tier = tier.lower()

        if tier not in valid_tiers:
            await ctx.send(f"❌ Invalid tier. Use: {', '.join(valid_tiers)}")
            return

        # Prevent adding root tier (only one root)
        if tier == 'root':
            await ctx.send("❌ Cannot add additional root users. Only one bot root allowed.")
            return

        try:
            db = self.bot.db_adapter

            # Check if user already exists
            existing = await db.fetch_one(
                "SELECT tier FROM user_permissions WHERE discord_id = $1",
                user.id
            )

            if existing:
                existing_tier = existing[0]  # tuple access
                await ctx.send(f"⚠️ {user.mention} is already in the system as **{existing_tier}**. Use `!admin_promote` to change tier.")
                return

            # Insert into database
            await db.execute(
                """
                INSERT INTO user_permissions (discord_id, username, tier, added_by, reason)
                VALUES ($1, $2, $3, $4, $5)
                """,
                user.id, str(user), tier, ctx.author.id, reason
            )

            # Log to audit table
            await db.execute(
                """
                INSERT INTO permission_audit_log (target_discord_id, action, new_tier, changed_by, reason)
                VALUES ($1, $2, $3, $4, $5)
                """,
                user.id, 'add', tier, ctx.author.id, reason
            )

            # db_adapter auto-commits

            embed = discord.Embed(
                title="✅ User Added to Whitelist",
                description=f"{user.mention} has been granted **{tier}** permissions.",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Added By", value=ctx.author.mention, inline=True)
            embed.add_field(name="Tier", value=tier.upper(), inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)

            await ctx.send(embed=embed)
            logger.info(f"✅ {ctx.author} added {user} as {tier}: {reason}")

        except Exception as e:
            logger.error(f"Error adding admin: {e}", exc_info=True)
            await ctx.send(f"❌ Error adding user: {e}")

    @is_owner()
    @commands.command(name='admin_remove', aliases=['perm_remove'])
    async def remove_admin(self, ctx, user: discord.Member, *, reason: Optional[str] = "No reason provided"):
        """➖ Remove user from permission whitelist (Root only)

        Usage: !admin_remove @user [reason]
        Example: !admin_remove @john No longer active
        """
        # Prevent removing root
        if user.id == self.bot.owner_user_id:
            await ctx.send("❌ Cannot remove the bot root user.")
            return

        try:
            db = self.bot.db_adapter

            # Check if user exists
            existing = await db.fetch_one(
                "SELECT tier FROM user_permissions WHERE discord_id = $1",
                user.id
            )

            if not existing:
                await ctx.send(f"⚠️ {user.mention} is not in the permission system.")
                return

            # Remove from database
            await db.execute(
                "DELETE FROM user_permissions WHERE discord_id = $1",
                user.id
            )

            # Log to audit table - existing[0] is tier (tuple access)
            old_tier = existing[0]
            await db.execute(
                """
                INSERT INTO permission_audit_log (target_discord_id, action, old_tier, changed_by, reason)
                VALUES ($1, $2, $3, $4, $5)
                """,
                user.id, 'remove', old_tier, ctx.author.id, reason
            )

            # db_adapter auto-commits

            embed = discord.Embed(
                title="✅ User Removed from Whitelist",
                description=f"{user.mention} no longer has **{old_tier}** permissions.",
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Removed By", value=ctx.author.mention, inline=True)
            embed.add_field(name="Previous Tier", value=old_tier.upper(), inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)

            await ctx.send(embed=embed)
            logger.info(f"✅ {ctx.author} removed {user} ({old_tier}): {reason}")

        except Exception as e:
            logger.error(f"Error removing admin: {e}", exc_info=True)
            await ctx.send(f"❌ Error removing user: {e}")

    @is_admin()
    @commands.command(name='admin_list', aliases=['perm_list', 'admins'])
    async def list_admins(self, ctx):
        """📋 List all users with permissions (Admin+)

        Usage: !admin_list
        """
        try:
            db = self.bot.db_adapter

            users = await db.fetch_all(
                """
                SELECT discord_id, username, tier, added_at, reason
                FROM user_permissions
                ORDER BY
                    CASE tier
                        WHEN 'root' THEN 1
                        WHEN 'admin' THEN 2
                        WHEN 'moderator' THEN 3
                    END,
                    added_at ASC
                """
            )

            if not users:
                await ctx.send("📋 No users in permission system.")
                return

            # Group by tier
            # Query returns: discord_id(0), username(1), tier(2), added_at(3), reason(4)
            tiers = {'root': [], 'admin': [], 'moderator': []}
            for user in users:
                user_tier = user[2]  # tier is at index 2
                tiers[user_tier].append(user)

            embed = discord.Embed(
                title="🔒 User Permissions",
                description=f"Total: {len(users)} users",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )

            # Add fields for each tier
            for tier_name in ['root', 'admin', 'moderator']:
                tier_users = tiers[tier_name]
                if tier_users:
                    user_list = []
                    for u in tier_users:
                        discord_id = u[0]
                        username = u[1]
                        user_obj = ctx.guild.get_member(discord_id)
                        display = user_obj.mention if user_obj else f"`{username}`"
                        user_list.append(f"• {display}")

                    embed.add_field(
                        name=f"{tier_name.upper()} ({len(tier_users)})",
                        value='\n'.join(user_list),
                        inline=False
                    )

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error listing admins: {e}", exc_info=True)
            await ctx.send(f"❌ Error listing permissions: {e}")

    @is_owner()
    @commands.command(name='admin_audit', aliases=['perm_audit'])
    async def audit_log(self, ctx, limit: int = 10):
        """📜 View permission change audit log (Root only)

        Usage: !admin_audit [limit]
        Example: !admin_audit 20
        """
        try:
            db = self.bot.db_adapter

            logs = await db.fetch_all(
                """
                SELECT target_discord_id, action, old_tier, new_tier, changed_by, changed_at, reason
                FROM permission_audit_log
                ORDER BY changed_at DESC
                LIMIT $1
                """,
                min(limit, 50)  # Max 50 entries
            )

            if not logs:
                await ctx.send("📜 No audit log entries found.")
                return

            embed = discord.Embed(
                title="📜 Permission Audit Log",
                description=f"Showing last {len(logs)} changes",
                color=discord.Color.purple(),
                timestamp=datetime.now()
            )

            # Query returns: target_discord_id(0), action(1), old_tier(2), new_tier(3), changed_by(4), changed_at(5), reason(6)
            for log in logs[:10]:  # Show max 10 in embed
                target_discord_id = log[0]
                action = log[1]
                old_tier = log[2]
                new_tier = log[3]
                changed_by = log[4]
                changed_at = log[5]
                reason = log[6]

                target = ctx.guild.get_member(target_discord_id)
                changer = ctx.guild.get_member(changed_by)

                target_name = target.mention if target else f"<@{target_discord_id}>"
                changer_name = changer.mention if changer else f"<@{changed_by}>"

                action_emoji = {
                    'add': '➕',
                    'remove': '➖',
                    'promote': '⬆️',
                    'demote': '⬇️'
                }.get(action, '📝')

                tier_change = new_tier if action == 'add' else f"{old_tier} → {new_tier}" if new_tier else old_tier

                embed.add_field(
                    name=f"{action_emoji} {action.upper()} - {changed_at.strftime('%Y-%m-%d %H:%M')}",
                    value=f"**Target:** {target_name}\n**By:** {changer_name}\n**Tier:** {tier_change}\n**Reason:** {reason}",
                    inline=False
                )

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error viewing audit log: {e}", exc_info=True)
            await ctx.send(f"❌ Error viewing audit log: {e}")


async def setup(bot):
    """Load the cog"""
    await bot.add_cog(PermissionManagement(bot))
