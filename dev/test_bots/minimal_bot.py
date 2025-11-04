#!/usr/bin/env python3
"""
Minimal bot to test command registration issue
"""
import discord
from discord.ext import commands

class MinimalBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)
    
    @commands.command()
    async def test_ping(self, ctx):
        """Test ping command"""
        await ctx.send("Pong!")

# Test it
if __name__ == "__main__":
    bot = MinimalBot()
    print(f"Minimal bot commands: {[cmd.name for cmd in bot.commands]}")
    
    # If this works, the problem is in the main bot file
    if bot.commands:
        print("✅ Command registration works in minimal bot")
    else:
        print("❌ Command registration fails even in minimal bot")