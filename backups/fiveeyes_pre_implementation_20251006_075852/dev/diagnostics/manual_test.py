#!/usr/bin/env python3
"""
Test script to manually register commands in the main bot
"""
import sys
sys.path.append('.')

from bot.ultimate_bot import UltimateETLegacyBot
from discord.ext import commands

# Create the bot
bot = UltimateETLegacyBot()
print(f"Original commands: {[cmd.name for cmd in bot.commands]}")

# Define a simple command function (not a method)
@commands.command(name='manual_ping')
async def manual_ping_cmd(ctx):
    """Manual ping test"""
    await ctx.send("Manual pong!")

# Add it manually
bot.add_command(manual_ping_cmd)
print(f"After manual add: {[cmd.name for cmd in bot.commands]}")

# Try to manually register one of the existing methods as a command
if hasattr(bot, 'ping'):
    print(f"Bot has ping method: {type(bot.ping)}")
    # Remove the current ping and re-add it
    try:
        if 'ping' in bot.all_commands:
            bot.remove_command('ping')
        
        # Re-add the ping method as a command
        ping_cmd = commands.Command(bot.ping, name='ping')
        bot.add_command(ping_cmd)
        print(f"After re-adding ping: {[cmd.name for cmd in bot.commands]}")
    except Exception as e:
        print(f"Error re-adding ping: {e}")