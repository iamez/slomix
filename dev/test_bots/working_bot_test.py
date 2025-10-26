#!/usr/bin/env python3
"""
Test bot to verify proper command registration pattern
"""
import discord
from discord.ext import commands
import asyncio
import aiosqlite
import os

class WorkingBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)
        self.db_path = './test.db'
    
    async def setup_hook(self):
        print(f"Setup hook - commands: {[cmd.name for cmd in self.commands]}")
    
    @commands.command()
    async def test_ping(self, ctx):
        """Test ping command"""
        await ctx.send("Test pong!")
    
    @commands.command()
    async def test_stats(self, ctx, player: str = "Unknown"):
        """Test stats command"""
        await ctx.send(f"Stats for {player}")

async def main():
    bot = WorkingBot()
    print(f"Before setup: {[cmd.name for cmd in bot.commands]}")
    await bot.setup_hook()
    print(f"After setup: {[cmd.name for cmd in bot.commands]}")
    
    # Test command callback binding
    ping_cmd = bot.get_command('test_ping')
    if ping_cmd:
        print(f"Ping callback: {ping_cmd.callback}")
        if hasattr(ping_cmd.callback, '__self__'):
            print("✅ Commands are properly bound!")
        else:
            print("❌ Commands are unbound")

if __name__ == "__main__":
    asyncio.run(main())