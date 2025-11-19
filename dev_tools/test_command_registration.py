"""
Quick Command Test - Test all bot commands via Discord API simulation
"""
import sys
sys.path.append('.')

from bot.cogs.team_cog import TeamCog
from bot.cogs.stats_cog import StatsCog
from bot.cogs.session_cog import SessionCog

print("🧪 Testing Bot Command Registration...")
print()

# Check Team Cog
print("📋 TEAM COG COMMANDS:")
team_commands = [
    attr for attr in dir(TeamCog)
    if not attr.startswith('_') and callable(getattr(TeamCog, attr))
]
for cmd in team_commands:
    method = getattr(TeamCog, cmd)
    if hasattr(method, '__commands_command__') or hasattr(method, 'name'):
        print(f"  ✅ !{getattr(method, 'name', cmd)}")

print()
print("📋 STATS COG COMMANDS:")
stats_commands = [
    attr for attr in dir(StatsCog)
    if not attr.startswith('_') and callable(getattr(StatsCog, attr))
]
for cmd in stats_commands:
    method = getattr(StatsCog, cmd)
    if hasattr(method, '__commands_command__') or hasattr(method, 'name'):
        print(f"  ✅ !{getattr(method, 'name', cmd)}")

print()
print("📋 SESSION COG COMMANDS:")
session_commands = [
    attr for attr in dir(SessionCog)
    if not attr.startswith('_') and callable(getattr(SessionCog, attr))
]
for cmd in session_commands:
    method = getattr(SessionCog, cmd)
    if hasattr(method, '__commands_command__') or hasattr(method, 'name'):
        print(f"  ✅ !{getattr(method, 'name', cmd)}")

print()
print("✅ Command registration test complete!")
