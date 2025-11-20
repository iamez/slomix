"""
Channel Permission Checks for Discord Commands
================================================

Provides decorators for restricting commands to specific channels.

Usage:
    from bot.core.checks import is_admin_channel, is_public_channel

    @is_admin_channel()
    @commands.command()
    async def admin_command(self, ctx):
        # Only works in admin channel
        pass

    @is_public_channel()
    @commands.command()
    async def stats_command(self, ctx):
        # Only works in public stats channels
        pass
"""

from discord.ext import commands
import logging

logger = logging.getLogger("bot.core.checks")


class ChannelCheckFailure(commands.CheckFailure):
    """Custom exception for channel check failures with a user-friendly message."""
    pass


def is_admin_channel():
    """
    Decorator: Restrict command to admin channel only.

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
                logger.debug("Admin channel not configured, allowing command from any channel")
                return True
            admin_channels = [admin_channel_id]

        # Check if command is in an admin channel
        if ctx.channel.id not in admin_channels:
            # Format channel mentions for error message
            channel_mentions = [f"<#{ch}>" for ch in admin_channels]
            channels_str = " or ".join(channel_mentions)
            raise ChannelCheckFailure(f"❌ This command only works in {channels_str}")

        logger.debug(f"Admin command allowed from admin channel for {ctx.author}")
        return True

    return commands.check(predicate)


def is_public_channel():
    """
    Decorator: Restrict command to public stats channels.

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
            # Format channel mentions for error message
            channel_mentions = []
            for ch_id in ctx.bot.public_channels:
                if ch_id != 0:
                    channel_mentions.append(f"<#{ch_id}>")

            if channel_mentions:
                channels_str = " or ".join(channel_mentions)
                raise ChannelCheckFailure(f"❌ This command only works in {channels_str}")
            else:
                raise ChannelCheckFailure("❌ This command is not available in this channel")

        logger.debug(f"Public command allowed from channel {ctx.channel.id} for {ctx.author}")
        return True

    return commands.check(predicate)


def is_allowed_channel(allowed_channel_ids: list):
    """
    Decorator: Restrict command to specific channel IDs.

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
            channel_mentions = " or ".join([f"<#{ch}>" for ch in allowed_channel_ids])
            await ctx.send(f"❌ This command only works in {channel_mentions}")
            return False
        return True

    return commands.check(predicate)
