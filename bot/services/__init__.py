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

# Core session services
from bot.services.session_data_service import SessionDataService
from bot.services.session_stats_aggregator import SessionStatsAggregator
from bot.services.session_embed_builder import SessionEmbedBuilder
from bot.services.session_graph_generator import SessionGraphGenerator
from bot.services.session_view_handlers import SessionViewHandlers
from bot.services.endstats_aggregator import EndstatsAggregator

# Player services
from bot.services.player_badge_service import PlayerBadgeService
from bot.services.player_display_name_service import PlayerDisplayNameService
from bot.services.player_formatter import PlayerFormatter

# Game services
from bot.services.prediction_engine import PredictionEngine
from bot.services.prediction_embed_builder import PredictionEmbedBuilder
from bot.services.stopwatch_scoring_service import StopwatchScoringService
from bot.services.voice_session_service import VoiceSessionService

# Publishing services
from bot.services.round_publisher_service import RoundPublisherService

# Debug services
from bot.services.timing_debug_service import TimingDebugService

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
]
