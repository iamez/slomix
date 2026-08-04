"""
Bot Services Package
====================

This package contains the service layer for the ET:Legacy Discord Bot.
Services handle complex business logic, data aggregation, and external integrations.

Service Categories:
    Session Services:
        - session_data_service: Fetches and structures session data from database
        - session_stats_aggregator: Aggregates player statistics across rounds
        - session_embed_builder: Constructs Discord embeds for session displays
        - session_graph_generator: Generates performance graphs and visualizations
        - session_view_handlers: Handles interactive Discord views for sessions

    Player Services:
        - player_badge_service: Manages achievement badges for players
        - player_display_name_service: Resolves player GUID to display names
        - player_formatter: Formats player data for Discord display

    Game Services:
        - prediction_engine: AI-powered match prediction system
        - prediction_embed_builder: Builds Discord embeds for predictions
        - stopwatch_scoring_service: Handles stopwatch mode team scoring
        - voice_session_service: Tracks voice channel activity for team detection

    Publishing Services:
        - round_publisher_service: Auto-posts round statistics to Discord

Usage:
    from bot.services import SessionDataService
    from bot.services.player_badge_service import PlayerBadgeService

Architecture Notes:
    - All services use the bot's database_adapter for async DB operations
    - Services should be stateless where possible
    - Use 5-minute TTL cache from bot.core.stats_cache for expensive queries
    - GROUP BY player_guid (never player_name) for aggregations
"""


# Re-exports are LAZY (PEP 562). Importing any submodule runs this file first,
# so the eager `from bot.services.X import Y` block that used to live here made
# every one of the 101 modules that import a submodule pay for all 16 services.
# Two of them are heavy and Discord-only:
#
#   prediction_embed_builder -> discord
#   session_graph_generator  -> matplotlib
#
# That is how the WEBSITE ended up importing discord.py at startup. Its chain is
# main.py -> middleware -> services -> website_session_data_service ->
# shared/services/session_data_service.py -> bot.services.session_data_service,
# and that last import alone dragged in the whole package. session_data_service
# itself imports nothing but the standard library.
#
# Nothing in the repo actually used `from bot.services import X` — every caller
# imports the submodule directly — so this block was pure cost. It is kept
# rather than deleted because the package docstring documents it as the API,
# and __getattr__ makes it free.
from typing import TYPE_CHECKING

_EXPORTS = {
    "EndstatsAggregator": "endstats_aggregator",
    "PlayerBadgeService": "player_badge_service",
    "PlayerDisplayNameService": "player_display_name_service",
    "PlayerFormatter": "player_formatter",
    "PredictionEmbedBuilder": "prediction_embed_builder",
    "PredictionEngine": "prediction_engine",
    "RoundCorrelationService": "round_correlation_service",
    "RoundPublisherService": "round_publisher_service",
    "SessionDataService": "session_data_service",
    "SessionEmbedBuilder": "session_embed_builder",
    "SessionGraphGenerator": "session_graph_generator",
    "SessionStatsAggregator": "session_stats_aggregator",
    "SessionViewHandlers": "session_view_handlers",
    "StopwatchScoringService": "stopwatch_scoring_service",
    "TimingDebugService": "timing_debug_service",
    "VoiceSessionService": "voice_session_service",
}

if TYPE_CHECKING:  # pragma: no cover - import-time cost is the whole point
    from bot.services.endstats_aggregator import EndstatsAggregator
    from bot.services.player_badge_service import PlayerBadgeService
    from bot.services.player_display_name_service import PlayerDisplayNameService
    from bot.services.player_formatter import PlayerFormatter
    from bot.services.prediction_embed_builder import PredictionEmbedBuilder
    from bot.services.prediction_engine import PredictionEngine
    from bot.services.round_correlation_service import RoundCorrelationService
    from bot.services.round_publisher_service import RoundPublisherService
    from bot.services.session_data_service import SessionDataService
    from bot.services.session_embed_builder import SessionEmbedBuilder
    from bot.services.session_graph_generator import SessionGraphGenerator
    from bot.services.session_stats_aggregator import SessionStatsAggregator
    from bot.services.session_view_handlers import SessionViewHandlers
    from bot.services.stopwatch_scoring_service import StopwatchScoringService
    from bot.services.timing_debug_service import TimingDebugService
    from bot.services.voice_session_service import VoiceSessionService


def __getattr__(name: str):
    """Import a service module on first attribute access (PEP 562)."""
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from importlib import import_module

    value = getattr(import_module(f"{__name__}.{module_name}"), name)
    globals()[name] = value  # subsequent lookups skip __getattr__ entirely
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_EXPORTS))

__all__ = [
    # Session services
    'SessionDataService',
    'SessionStatsAggregator',
    'SessionEmbedBuilder',
    'SessionGraphGenerator',
    'SessionViewHandlers',
    'EndstatsAggregator',
    # Player services
    'PlayerBadgeService',
    'PlayerDisplayNameService',
    'PlayerFormatter',
    # Game services
    'PredictionEngine',
    'PredictionEmbedBuilder',
    'StopwatchScoringService',
    'VoiceSessionService',
    # Publishing services
    'RoundPublisherService',
    # Debug services
    'TimingDebugService',
    # Correlation services
    'RoundCorrelationService',
]
