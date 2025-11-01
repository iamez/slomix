"""
Core bot functionality modules.

This package contains essential classes extracted from ultimate_bot.py
during the modular refactoring to improve maintainability.

Modules:
    stats_cache: High-performance caching system for database queries
    season_manager: Quarterly season/competition management (TODO)
    achievement_system: Player achievement tracking (TODO)
"""

from .stats_cache import StatsCache

__all__ = ["StatsCache"]
