"""The web service must start without importing discord.py or matplotlib.

Both are Discord-only, and neither website/ nor shared/ references them. They
were reaching the web process purely through package __init__ side effects:

  website/backend/dependencies.py -> shared/database_adapter.py
    -> bot/core/__init__.py -> achievement_system.py -> import discord

  website/backend/middleware -> services -> website_session_data_service
    -> shared/services/session_data_service.py
    -> bot/services/__init__.py -> prediction_embed_builder -> import discord
                               -> session_graph_generator  -> import matplotlib

Both package __init__ files re-export lazily (PEP 562) so importing a submodule
no longer drags in its siblings. This test is what stops a future eager import
from silently putting them back: nothing else would fail, the web venv would
just quietly need discord.py again.

Runs in a SUBPROCESS with a minimal explicit environment, matching
tests/security/test_real_stack_security.py — main.py reads env at import and
fails fast without secrets, and the heavyweight import must not pollute the
test runner's own sys.modules (which pytest has already filled with bot
imports from other tests).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Packages that must NOT be present after importing the web app. cryptography
# and aiosqlite are deliberately absent from this list: the first is pulled in
# by the redis client itself (redis/utils.py), the second by the website's own
# local_database_adapter for its SQLite dev fallback. Both are genuinely the
# web service's dependencies, unlike these two.
_FORBIDDEN = ("discord", "matplotlib")

_SUBPROCESS_SCRIPT = f'''
import sys
import dotenv

dotenv.load_dotenv = lambda *args, **kwargs: False

import website.backend.main  # noqa: F401

leaked = [name for name in {_FORBIDDEN!r} if name in sys.modules]
if leaked:
    print("LEAKED:" + ",".join(leaked))
else:
    print("CLEAN")
'''


def test_web_app_starts_without_discord_or_matplotlib():
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(REPO_ROOT),
        "SESSION_SECRET": "decoupling-test-secret-0123456789",
        "INTERNAL_API_SECRET": "decoupling-test-internal-0123456789",
        "TRUSTED_HOSTS": "localhost,127.0.0.1",
        "WEB_LOG_DIR": os.environ.get("WEB_LOG_DIR", "/tmp"),
        "BOT_LOG_DIR": os.environ.get("BOT_LOG_DIR", "/tmp"),
    }

    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _SUBPROCESS_SCRIPT],
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        cwd=str(REPO_ROOT),
    )

    assert "CLEAN" in result.stdout, (
        "the web app imported a Discord-only package at startup — check for a "
        "new eager import in bot/core/__init__.py or bot/services/__init__.py, "
        f"or a new bot.* import in website/ or shared/.\n\n"
        f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr[-2000:]}"
    )


def test_lazy_packages_still_export_their_documented_names():
    """The re-exports are the documented API (bot/services/CLAUDE.md tells you
    to verify with `from bot.services import SessionDataService`), and
    bot/ultimate_bot.py:24 actually uses bot.core's. Deferring must not drop
    them."""
    script = (
        "from bot.services import SessionDataService\n"
        "from bot.core import AchievementSystem, SeasonManager, StatsCache\n"
        "import bot.services, bot.core\n"
        "assert set(bot.services.__all__) <= set(dir(bot.services))\n"
        "assert set(bot.core.__all__) <= set(dir(bot.core))\n"
        "try:\n"
        "    bot.services.NoSuchService\n"
        "except AttributeError:\n"
        "    pass\n"
        "else:\n"
        "    raise SystemExit('unknown attribute must raise AttributeError')\n"
        "print('EXPORTS_OK')\n"
    )
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script],
        env={"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(REPO_ROOT)},
        capture_output=True,
        text=True,
        timeout=180,
        cwd=str(REPO_ROOT),
    )
    assert "EXPORTS_OK" in result.stdout, (
        f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr[-2000:]}"
    )
