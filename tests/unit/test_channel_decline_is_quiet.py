"""⛔ THIS DISCORD RUNS MORE THAN ONE BOT.

`!teams` belongs to the team-building bot. Ours also registers `teams`, scoped
to public channels, so the command reaches us and is declined. What ours then
did was reply "❌ The check functions for command teams failed." into the
channel — interrupting a conversation it was not part of — and write an ERROR
with a traceback to errors.log, four times.

Both were bugs, and both had the same root: `ChannelCheckFailure` was defined
and never raised. The predicates returned False, discord.py converted that to a
plain `CheckFailure`, and the handler's `isinstance(..., ChannelCheckFailure)`
branch was dead code. Every channel decline fell through to the branch meant
for permission failures.

The docstrings said SILENTLY IGNORED the whole time.
"""
from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest
from discord.ext import commands

from bot.core.checks import ChannelCheckFailure, is_allowed_channel, is_public_channel
from bot.logging_config import _is_channel_decline

ROOT = Path(__file__).resolve().parents[2]


class _Ctx:
    """Minimal context: a channel id the bot does not allow."""

    def __init__(self, channel_id: int = 999, allowed: list[int] | None = None):
        self.channel = type("C", (), {"id": channel_id, "name": "elsewhere"})()
        self.bot = type("B", (), {"public_channels": allowed or [111]})()
        self.author = type("A", (), {"id": 1, "display_name": "someone"})()
        self.guild = None
        self.command = type("Cmd", (), {"name": "teams"})()


class TestTheDeclineIsTyped:
    @pytest.mark.asyncio
    async def test_public_channel_raises_channel_check_failure(self):
        """Not `return False` — that becomes a generic CheckFailure and the
        handler answers it out loud."""
        predicate = is_public_channel().predicate
        with pytest.raises(ChannelCheckFailure):
            await predicate(_Ctx())

    @pytest.mark.asyncio
    async def test_allowed_channel_raises_it_too(self):
        predicate = is_allowed_channel([111]).predicate
        with pytest.raises(ChannelCheckFailure):
            await predicate(_Ctx(channel_id=222))

    @pytest.mark.asyncio
    async def test_an_allowed_channel_still_passes(self):
        """The guard must not become a wall."""
        predicate = is_public_channel().predicate
        assert await predicate(_Ctx(channel_id=111)) is True

    def test_it_is_a_check_failure_so_discord_py_still_routes_it(self):
        assert issubclass(ChannelCheckFailure, commands.CheckFailure)


class TestTheLogStaysQuiet:
    def test_a_channel_decline_is_not_logged_as_a_failure(self):
        assert _is_channel_decline(ChannelCheckFailure("public channel only"))

    def test_a_permission_failure_still_is(self):
        """A user who asked THIS bot for something deserves the loud path."""
        assert not _is_channel_decline(commands.MissingPermissions(["admin"]))
        assert not _is_channel_decline(RuntimeError("boom"))


class TestTheHandlerSaysNothing:
    """Read from source: the handler needs a live bot to execute, but the shape
    of the branch is what regressed and the shape is checkable."""

    def _handler_source(self) -> str:
        text = (ROOT / "bot" / "ultimate_bot.py").read_text()
        match = re.search(
            r"elif isinstance\(error, commands\.CheckFailure\):(.*?)(?=\n        else:)",
            text, re.S)
        assert match, "the CheckFailure branch moved or was renamed"
        return match.group(1)

    def test_the_channel_branch_does_not_send(self):
        branch = self._handler_source()
        channel_part = branch.split("else:")[0]
        assert "ctx.send" not in channel_part, (
            "the bot replies to a command that was not addressed to it")

    def test_the_other_branch_still_does(self):
        branch = self._handler_source()
        assert "ctx.send" in branch.split("else:")[-1], (
            "permission failures went silent too — that is the opposite defect")


def test_no_channel_predicate_returns_a_bare_false():
    """The regression this whole file exists to prevent.

    A `return False` inside a channel check reads as 'deny quietly' and does the
    opposite. The one remaining False is a fail-closed on MISSING CONFIG, which
    is a different situation and should stay loud.
    """
    source = inspect.getsource(__import__("bot.core.checks", fromlist=["x"]))
    for name in ("not admin channel", "not public channel", "not in allowed list"):
        # the decline path for each predicate must raise, not return
        idx = source.find(name)
        assert idx != -1, f"decline path for {name!r} not found"
        following = source[idx:idx + 260]
        assert "raise ChannelCheckFailure" in following, (
            f"the {name!r} path does not raise — it will be answered out loud")
