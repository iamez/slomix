#!/usr/bin/env python3
"""
Test using Cog pattern for command registration
"""
import discord
from discord.ext import commands
import asyncio

class TestCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command()
    async def test_ping(self, ctx):
        """Test ping from cog"""
        await ctx.send("Cog pong!")

class CogBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)
    
    async def setup_hook(self):
        # Add the cog
        await self.add_cog(TestCog(self))
        print(f"Setup hook - commands: {[cmd.name for cmd in self.commands]}")

async def main():
    bot = CogBot()
    print(f"Before setup: {[cmd.name for cmd in bot.commands]}")
    await bot.setup_hook()
    print(f"After setup: {[cmd.name for cmd in bot.commands]}")

if __name__ == "__main__":
    asyncio.run(main())