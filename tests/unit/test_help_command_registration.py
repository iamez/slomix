"""!help must resolve to OUR categorized help, not discord.py's built-in.

Regression guard for the FIX 1 finding (2026-08-11 audit): the bot was
constructed without ``help_command=None``, so discord.py's default
HelpCommand answered ``!help`` (14 logged calls) while our categorized
help sat unreachable under ``!help_command`` (0 calls).

Two invariants:

1. The custom command is registered under ``help`` (with ``help_command``
   kept as an alias so old habits keep working).
2. ``UltimateETLegacyBot`` passes ``help_command=None`` to the Bot
   constructor — otherwise discord.py registers its own ``help`` first
   and loading StatsCog raises CommandRegistrationError at startup.
"""
from __future__ import annotations

import inspect

from bot.cogs.stats_cog import StatsCog
from bot.ultimate_bot import UltimateETLegacyBot


def test_custom_help_is_named_help():
    cmd = StatsCog.help_command
    assert cmd.name == "help"


def test_old_name_kept_as_alias():
    cmd = StatsCog.help_command
    assert "help_command" in cmd.aliases
    # Pre-existing aliases must survive the rename.
    for alias in ("commands", "cmds", "bothelp"):
        assert alias in cmd.aliases


def test_builtin_help_disabled_in_bot_constructor():
    # Instantiating the real bot needs config/DB, so assert on the source:
    # the super().__init__ call must disable the built-in help command.
    src = inspect.getsource(UltimateETLegacyBot.__init__)
    assert "help_command=None" in src, (
        "UltimateETLegacyBot must pass help_command=None to commands.Bot — "
        "otherwise discord.py's built-in help shadows our !help and "
        "StatsCog registration fails with a duplicate 'help' command."
    )
