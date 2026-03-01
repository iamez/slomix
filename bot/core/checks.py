"""
Channel Permission Checks for Discord Commands
================================================

Provides decorators for restricting commands to specific channels.
Commands in wrong channels are SILENTLY IGNORED (no error message sent).

Usage:
    from bot.core.checks import is_admin_channel, is_public_channel

    @is_admin_channel()
    @commands.command()
    async def admin_command(self, ctx):
        # Only works in admin channel - silently ignored elsewhere
        pass

    @is_public_channel()
    @commands.command()
    async def stats_command(self, ctx):
        # Only works in public stats channels - silently ignored elsewhere
        pass
"""

from discord.ext import commands
import logging

logger = logging.getLogger("bot.core.checks")


class ChannelCheckFailure(commands.CheckFailure):
    """Custom exception for channel check failures (kept for backward compatibility)."""
    pass


def is_admin_channel():
    """
    Decorator: Restrict command to admin channel only.
    Commands in wrong channels are SILENTLY IGNORED.

    If ADMIN_CHANNEL_ID is configured, the command will only work in that channel.
    Anyone posting in the admin channel is treated as an admin (no role checks).
    If not configured, allows command from any channel.

    Usage:
        @is_admin_channel()
        @commands.command()
        async def admin_refresh(self, ctx):
            await ctx.send("Refreshing cache...")
    """
    async def predicate(ctx):
        # Check if bot has admin channels configured
        admin_channels = getattr(ctx.bot, 'admin_channels', [])
        if not admin_channels:
            # Fallback to single admin_channel_id for backward compatibility
            admin_channel_id = getattr(ctx.bot, 'admin_channel_id', 0)
            if admin_channel_id == 0:
                logger.warning("Admin channel not configured, denying command (fail-closed)")
                return False
            admin_channels = [admin_channel_id]

        # Check if command is in an admin channel
        if ctx.channel.id not in admin_channels:
            # SILENTLY IGNORE - return False without sending error message
            logger.debug(f"Command ignored in channel {ctx.channel.id} (not admin channel)")
            return False

        logger.debug(f"Admin command allowed from admin channel for {ctx.author}")
        return True

    return commands.check(predicate)


def is_public_channel():
    """
    Decorator: Restrict command to public stats channels.
    Commands in wrong channels are SILENTLY IGNORED.

    Public channels include:
    - Production channel (regular match stats)
    - Gather channel (3v3/6v6 matches)
    - General channel (everything else)

    If public channels are configured, commands will only work in those channels.
    If not configured, allows commands from any channel.

    Usage:
        @is_public_channel()
        @commands.command()
        async def last_session(self, ctx):
            # Show latest session stats
            pass
    """
    async def predicate(ctx):
        # Check if bot has public channels configured
        if not hasattr(ctx.bot, 'public_channels') or not ctx.bot.public_channels:
            logger.debug("Public channels not configured, allowing command from any channel")
            return True

        # Check if command is in a public channel
        if ctx.channel.id not in ctx.bot.public_channels:
            # SILENTLY IGNORE - return False without sending error message
            logger.debug(f"Command ignored in channel {ctx.channel.id} (not public channel)")
            return False

        logger.debug(f"Public command allowed from channel {ctx.channel.id} for {ctx.author}")
        return True

    return commands.check(predicate)


def is_allowed_channel(allowed_channel_ids: list):
    """
    Decorator: Restrict command to specific channel IDs.
    Commands in wrong channels are SILENTLY IGNORED.

    This is a generic version for custom channel restrictions.

    Args:
        allowed_channel_ids: List of channel IDs where command is allowed

    Usage:
        @is_allowed_channel([123456789, 987654321])
        @commands.command()
        async def special_command(self, ctx):
            # Only works in specified channels
            pass
    """
    async def predicate(ctx):
        if ctx.channel.id not in allowed_channel_ids:
            # SILENTLY IGNORE - return False without sending error message
            logger.debug(f"Command ignored in channel {ctx.channel.id} (not in allowed list)")
            return False
        return True

    return commands.check(predicate)


# ============================================================================
# USER ID-BASED PERMISSION DECORATORS
# ============================================================================
# Security: User ID whitelist (immune to Discord role exploits)
# Tiers: Root (1) → Admin (many) → Moderator (many)
# Database: user_permissions table
# ============================================================================


def is_owner():
    """
    Decorator: Restrict command to bot root user only.
    Root user is defined in OWNER_USER_ID environment variable.

    Security: Highest permission tier - only for dangerous operations
    Examples: !reload (reloads bot code), permission management

    Note: Function named "is_owner" for compatibility, but tier is "root"

    Usage:
        @is_owner()
        @commands.command()
        async def reload(self, ctx):
            # Only root can reload bot code
            pass
    """
    async def predicate(ctx):
        owner_id = getattr(ctx.bot, 'owner_user_id', 0)

        if ctx.author.id != owner_id:
            logger.warning(f"⚠️ Unauthorized root command attempt by {ctx.author} ({ctx.author.id})")
            raise commands.CheckFailure("This command is restricted to the bot root user.")

        logger.info(f"✅ Root command authorized: {ctx.author}")
        return True

    return commands.check(predicate)


def is_admin():
    """
    Decorator: Restrict command to admin tier or higher (admin + root).
    Checks user_permissions table in database.

    Security: Mid-level permissions for server control and bot management
    Examples: !server_restart, !backup_db, !sync_stats

    Usage:
        @is_admin()
        @commands.command()
        async def server_restart(self, ctx):
            # Admin or root can restart server
            pass
    """
    async def predicate(ctx):
        # Root always has admin access
        owner_id = getattr(ctx.bot, 'owner_user_id', 0)
        if ctx.author.id == owner_id:
            logger.info(f"✅ Admin command authorized (root): {ctx.author}")
            return True

        # Check database for admin/moderator tier
        try:
            db = ctx.bot.db_adapter
            result = await db.fetch_one(
                "SELECT tier FROM user_permissions WHERE discord_id = $1",
                (ctx.author.id,)
            )

            if result and result[0] in ['admin', 'moderator']:
                logger.info(f"✅ Admin command authorized ({result[0]}): {ctx.author}")
                return True

            logger.warning(f"⚠️ Unauthorized admin command by {ctx.author} ({ctx.author.id})")
            raise commands.CheckFailure("This command requires admin permissions.")

        except commands.CheckFailure:
            raise  # Re-raise CheckFailure, don't catch it
        except Exception as e:
            logger.error(f"Error checking admin permissions: {e}")
            raise commands.CheckFailure("Permission check failed.")

    return commands.check(predicate)


def is_moderator():
    """
    Decorator: Restrict command to moderator tier or higher (moderator + admin + root).
    Checks user_permissions table in database.

    Security: Basic permissions for game metadata and analytics
    Examples: !enable_analytics, !weapon_diag

    Usage:
        @is_moderator()
        @commands.command()
        async def enable_analytics(self, ctx):
            # Moderator, admin, or root can enable analytics
            pass
    """
    async def predicate(ctx):
        # Root always has moderator access
        owner_id = getattr(ctx.bot, 'owner_user_id', 0)
        if ctx.author.id == owner_id:
            logger.info(f"✅ Moderator command authorized (root): {ctx.author}")
            return True

        # Check database for any tier
        try:
            db = ctx.bot.db_adapter
            result = await db.fetch_one(
                "SELECT tier FROM user_permissions WHERE discord_id = $1",
                (ctx.author.id,)
            )

            if result and result[0] in ['admin', 'moderator']:
                logger.info(f"✅ Moderator command authorized ({result[0]}): {ctx.author}")
                return True

            logger.warning(f"⚠️ Unauthorized moderator command by {ctx.author} ({ctx.author.id})")
            raise commands.CheckFailure("This command requires moderator permissions.")

        except commands.CheckFailure:
            raise  # Re-raise CheckFailure, don't catch it
        except Exception as e:
            logger.error(f"Error checking moderator permissions: {e}")
            raise commands.CheckFailure("Permission check failed.")

    return commands.check(predicate)
