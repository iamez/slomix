"""
Core bot functionality modules.

This package contains essential classes extracted from ultimate_bot.py
during the modular refactoring to improve maintainability.

Modules:
    stats_cache: High-performance caching system for database queries
    season_manager: Quarterly season/competition management
    achievement_system: Player achievement tracking and milestone notifications
"""


# Lazy re-exports (PEP 562), for the same reason as bot/services/__init__.py.
# Importing ANY submodule runs this file first, and achievement_system imports
# discord — so `from bot.core.database_adapter import ...` pulled discord.py in
# too. The website does exactly that, via
# website/backend/dependencies.py -> shared/database_adapter.py.
#
# Unlike bot/services, this package's re-exports ARE used
# (bot/ultimate_bot.py:24), so they stay — __getattr__ just defers the cost to
# whoever actually wants the name. The bot needs discord anyway; the website
# does not.
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - deferring the import is the point
    from .achievement_system import AchievementSystem
    from .season_manager import SeasonManager
    from .stats_cache import StatsCache


def __getattr__(name: str):
    """Import a core module on first attribute access (PEP 562).

    Written as literal imports rather than importlib.import_module(name):
    a module path assembled from the argument is flagged as a dynamic-import
    sink by static analysis, and with three exports the branch is no less
    readable than a lookup table.
    """
    if name == "AchievementSystem":
        from .achievement_system import AchievementSystem as value
    elif name == "SeasonManager":
        from .season_manager import SeasonManager as value
    elif name == "StatsCache":
        from .stats_cache import StatsCache as value
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    globals()[name] = value  # subsequent lookups skip __getattr__ entirely
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))


__all__ = ["StatsCache", "SeasonManager", "AchievementSystem"]
