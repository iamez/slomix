#!/usr/bin/env python3
"""
Minimal test bot to verify command registration works
"""
import discord
from discord.ext import commands

class TestBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)
    
    @commands.command()
    async def test(self, ctx):
        await ctx.send("Test command works!")

if __name__ == "__main__":
    bot = TestBot()
    print(f"Test bot commands: {[cmd.name for cmd in bot.commands]}")
    print(f"All commands: {list(bot.all_commands.keys())}")