"""
Bot Configuration System
Supports PostgreSQL (primary) with environment variables or config file.
SQLite settings are retained for legacy/fallback compatibility only.
Consolidates all configuration from environment variables into a single object.
"""
import os
import json
import logging
from typing import Optional, Dict, Any, List

# Load .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()  # Load .env file into environment variables
except ImportError:  # nosec B110
    pass  # python-dotenv not installed, skip

logger = logging.getLogger('BotConfig')


def _strip_inline_env_comment(value: str) -> str:
    """
    Normalize .env values that may include inline comments.

    Example: "27960  # ET:Legacy game port" -> "27960"
    """
    trimmed = value.strip()
    comment_start = trimmed.find("#")
    if comment_start <= 0:
        return trimmed
    if not trimmed[comment_start - 1].isspace():
        return trimmed
    return trimmed[:comment_start].strip()


class BotConfig:
    """
    Centralized bot configuration supporting multiple database backends.

    Configuration Priority:
    1. Environment variables
    2. bot_config.json file
    3. Default values (SQLite fallback)

    This class consolidates ALL configuration attributes from ultimate_bot.py
    and services, eliminating scattered os.getenv() calls throughout the codebase.
    """

    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize bot configuration.

        Args:
            config_file: Optional path to JSON config file
        """
        self.config_file = config_file or "bot_config.json"
        self._config_data = {}

        # Load config file if exists
        if os.path.exists(self.config_file):
            self._load_config_file()

        # ==================== LOGGING ====================
        self.log_level: str = self._get_config('LOG_LEVEL', 'INFO').upper()

        # ==================== DATABASE CONFIGURATION ====================
        self.database_type = self._get_config('DATABASE_TYPE', 'postgresql')

        # SQLite settings
        self.sqlite_db_path = self._get_config('SQLITE_DB_PATH', 'bot/etlegacy_production.db')

        # PostgreSQL settings
        self.postgres_host = self._get_config('POSTGRES_HOST', 'localhost')
        self.postgres_port = int(self._get_config('POSTGRES_PORT', '5432'))
        self.postgres_database = self._get_config('POSTGRES_DATABASE', 'etlegacy_stats')
        self.postgres_user = self._get_config('POSTGRES_USER', 'etlegacy')
        self.postgres_password = self._get_config('POSTGRES_PASSWORD', '')
        # Increased pool size for 14 cogs + 4 background tasks
        self.postgres_min_pool = int(self._get_config('POSTGRES_MIN_POOL', '10'))
        self.postgres_max_pool = int(self._get_config('POSTGRES_MAX_POOL', '30'))

        # PostgreSQL SSL Configuration (optional, for remote databases)
        self.postgres_ssl_mode = self._get_config('POSTGRES_SSL_MODE', 'disable')  # disable, require, verify-ca, verify-full
        self.postgres_ssl_cert = self._get_config('POSTGRES_SSL_CERT', '')
        self.postgres_ssl_key = self._get_config('POSTGRES_SSL_KEY', '')
        self.postgres_ssl_root_cert = self._get_config('POSTGRES_SSL_ROOT_CERT', '')

        # ==================== DISCORD CONFIGURATION ====================
        self.discord_token: str = self._get_config('DISCORD_BOT_TOKEN', '')
        self.discord_guild_id: str = self._get_config('DISCORD_GUILD_ID', '')

        # ==================== DISCORD CHANNEL IDS ====================
        # Stats and monitoring channels
        self.stats_channel_id: int = int(self._get_config('STATS_CHANNEL_ID', '0'))
        self.discord_stats_channel_id: str = self._get_config('DISCORD_STATS_CHANNEL_ID', '')  # Backward compat

        # Routing channels
        self.production_channel_id: int = int(self._get_config('PRODUCTION_CHANNEL_ID', '0'))
        self.gather_channel_id: int = int(self._get_config('GATHER_CHANNEL_ID', '0'))
        self.general_channel_id: int = int(self._get_config('GENERAL_CHANNEL_ID', '0'))

        # Admin channels (supports comma-separated list)
        admin_channels_str = self._get_config('ADMIN_CHANNEL_ID', '0')
        self.admin_channels: List[int] = [
            int(ch.strip()) for ch in admin_channels_str.split(",") if ch.strip().isdigit()
        ]
        self.admin_channel_id: int = self.admin_channels[0] if self.admin_channels else 0

        # Root User ID (for highest permission tier - user ID whitelist)
        self.owner_user_id: int = int(self._get_config('OWNER_USER_ID', '0'))
        if self.owner_user_id == 0:
            logger.warning("⚠️ OWNER_USER_ID not configured! Root-only commands will fail.")
        else:
            logger.info(f"✅ Bot root user: {self.owner_user_id}")

        # Voice channels for monitoring (comma-separated)
        gaming_channels_str = self._get_config('GAMING_VOICE_CHANNELS', '')
        self.gaming_voice_channels: List[int] = (
            [int(ch.strip()) for ch in gaming_channels_str.split(",") if ch.strip()]
            if gaming_channels_str else []
        )

        # Bot command channels (comma-separated)
        bot_channels_str = self._get_config('BOT_COMMAND_CHANNELS', '')
        self.bot_command_channels: List[int] = (
            [int(ch.strip()) for ch in bot_channels_str.split(",") if ch.strip()]
            if bot_channels_str else []
        )

        # Dev timing comparison channel (for Lua vs Stats file analysis)
        self.dev_timing_channel_id: int = int(self._get_config('DEV_TIMING_CHANNEL_ID', '0'))
        self.timing_comparison_enabled: bool = self._get_config('TIMING_COMPARISON_ENABLED', 'true').lower() == 'true'

        # Live achievement notifications:
        # - off: disabled (prevents channel spam)
        # - summary: one compact embed per round
        # - individual: one embed per achievement unlock
        self.live_achievement_mode: str = self._get_config('LIVE_ACHIEVEMENT_MODE', 'off').strip().lower()
        if self.live_achievement_mode not in {'off', 'summary', 'individual'}:
            logger.warning(
                f"⚠️ Invalid LIVE_ACHIEVEMENT_MODE='{self.live_achievement_mode}', falling back to 'off'"
            )
            self.live_achievement_mode = 'off'

        # Derived channel lists (computed from above)
        self.public_channels: List[int] = [
            ch for ch in [self.production_channel_id, self.gather_channel_id, self.general_channel_id]
            if ch != 0
        ]
        self.all_allowed_channels: List[int] = list(set(self.public_channels + self.admin_channels))

        # ==================== SESSION DETECTION ====================
        self.session_start_threshold: int = int(self._get_config('SESSION_START_THRESHOLD', '6'))
        self.session_end_threshold: int = int(self._get_config('SESSION_END_THRESHOLD', '2'))
        self.session_end_delay: int = int(self._get_config('SESSION_END_DELAY', '300'))  # seconds
        self.session_gap_minutes: int = int(self._get_config('SESSION_GAP_MINUTES', '60'))  # minutes between gaming sessions

        # ==================== ROUND MATCHING & MONITORING ====================
        # R1-R2 matching window: How long after R1 can R2 be matched
        # Default 45 min - rounds typically 5-15 min, but allow for longer games
        # MUST be less than session_gap_minutes to avoid cross-session matching
        self.round_match_window_minutes: int = int(self._get_config('ROUND_MATCH_WINDOW_MINUTES', '45'))

        # Monitoring grace period: Keep checking for files after voice channel empties
        # Default matches round_match_window_minutes for consistency
        self.monitoring_grace_period_minutes: int = int(self._get_config('MONITORING_GRACE_PERIOD_MINUTES', '45'))

        # ==================== WEBSITE MONITORING (SERVER + VOICE HISTORY) ====================
        self.monitoring_enabled: bool = self._get_config('MONITORING_ENABLED', 'true').lower() == 'true'
        self.server_host: str = self._get_config('SERVER_HOST', 'puran.hehe.si')
        self.server_port: int = int(self._get_config('SERVER_PORT', '27960'))
        self.monitoring_server_interval_seconds: int = int(
            self._get_config('MONITORING_SERVER_INTERVAL_SECONDS', '300')
        )
        self.monitoring_voice_interval_seconds: int = int(
            self._get_config('MONITORING_VOICE_INTERVAL_SECONDS', '60')
        )

        # ==================== AUTOMATION SYSTEM ====================
        self.automation_enabled: bool = self._get_config('AUTOMATION_ENABLED', 'false').lower() == 'true'

        # File processing startup lookback window (hours)
        # When bot restarts, only process files within this window before startup time
        # Default: 168 hours (7 days) - prevents re-importing ancient history while
        # allowing recovery of recent files created while bot was offline
        self.STARTUP_LOOKBACK_HOURS: int = int(self._get_config('STARTUP_LOOKBACK_HOURS', '168'))

        # ==================== HEALTH MONITOR CONFIGURATION ====================
        self.health_error_threshold: int = int(self._get_config('HEALTH_ERROR_THRESHOLD', '10'))
        self.health_ssh_error_threshold: int = int(self._get_config('HEALTH_SSH_ERROR_THRESHOLD', '5'))
        self.health_db_error_threshold: int = int(self._get_config('HEALTH_DB_ERROR_THRESHOLD', '5'))
        self.health_alert_cooldown: int = int(self._get_config('HEALTH_ALERT_COOLDOWN', '300'))  # seconds

        # ==================== SSH CONFIGURATION ====================
        self.ssh_enabled: bool = self._get_config('SSH_ENABLED', 'false').lower() == 'true'
        self.ssh_host: str = self._get_config('SSH_HOST', '')
        self.ssh_port: int = int(self._get_config('SSH_PORT', '22'))
        self.ssh_user: str = self._get_config('SSH_USER', '')
        self.ssh_key_path: str = self._get_config('SSH_KEY_PATH', '')
        self.ssh_remote_path: str = self._get_config('REMOTE_STATS_PATH', '')

        # SSH monitoring behavior
        self.ssh_check_interval: int = int(self._get_config('SSH_CHECK_INTERVAL', '60'))  # seconds
        self.ssh_startup_lookback_hours: int = int(self._get_config('SSH_STARTUP_LOOKBACK_HOURS', '24'))
        self.ssh_voice_conditional: bool = self._get_config('SSH_VOICE_CONDITIONAL', 'true').lower() == 'true'
        self.ssh_grace_period_minutes: int = int(self._get_config('SSH_GRACE_PERIOD_MINUTES', '10'))

        # ==================== GAMETIMES (LUA FALLBACK) ====================
        # Optional ingestion of Lua gametimes JSON files if Discord webhook fails
        self.gametimes_enabled: bool = self._get_config('GAMETIMES_ENABLED', 'false').lower() == 'true'
        self.gametimes_remote_path: str = self._get_config('REMOTE_GAMETIMES_PATH', '')
        self.gametimes_local_path: str = self._get_config('LOCAL_GAMETIMES_PATH', 'local_gametimes')
        self.gametimes_startup_lookback_hours: int = int(
            self._get_config('GAMETIMES_STARTUP_LOOKBACK_HOURS', str(self.ssh_startup_lookback_hours))
        )

        # ==================== FILE PATHS ====================
        self.stats_directory: str = self._get_config('STATS_DIRECTORY', 'local_stats')
        self.local_stats_path: str = self._get_config('LOCAL_STATS_PATH', './local_stats')
        self.backup_directory: str = self._get_config('BACKUP_DIRECTORY', 'processed_stats')
        self.metrics_db_path: str = self._get_config('METRICS_DB_PATH', 'bot/logs/metrics/metrics.db')

        # ==================== RCON (REMOTE CONSOLE) ====================
        self.rcon_enabled: bool = self._get_config('RCON_ENABLED', 'false').lower() == 'true'
        self.rcon_host: str = self._get_config('RCON_HOST', 'localhost')
        self.rcon_port: int = int(self._get_config('RCON_PORT', '27960'))
        self.rcon_password: str = self._get_config('RCON_PASSWORD', '')

        # ==================== COMPETITIVE ANALYTICS FEATURE FLAGS ====================
        # Phase 2: Team split detection
        self.enable_team_split_detection: bool = self._get_config('ENABLE_TEAM_SPLIT_DETECTION', 'false').lower() == 'true'

        # Phase 3: Match predictions
        self.enable_match_predictions: bool = self._get_config('ENABLE_MATCH_PREDICTIONS', 'false').lower() == 'true'

        # Optional: H2H results lookup from session_results (kept OFF by default until validated)
        self.enable_h2h_results_lookup: bool = self._get_config('ENABLE_H2H_RESULTS_LOOKUP', 'false').lower() == 'true'

        # Phase 4: Live scoring
        self.enable_live_scoring: bool = self._get_config('ENABLE_LIVE_SCORING', 'false').lower() == 'true'

        # Logging and debugging
        self.enable_prediction_logging: bool = self._get_config('ENABLE_PREDICTION_LOGGING', 'true').lower() == 'true'

        # Thresholds and limits
        self.prediction_cooldown_minutes: int = int(self._get_config('PREDICTION_COOLDOWN_MINUTES', '5'))
        self.min_players_for_prediction: int = int(self._get_config('MIN_PLAYERS_FOR_PREDICTION', '6'))
        self.min_guid_coverage: float = float(self._get_config('MIN_GUID_COVERAGE', '0.5'))  # 50% must have linked GUIDs

        # ==================== WEBHOOK TRIGGER NOTIFICATIONS ====================
        # VPS sends webhook to Discord, bot listens and processes
        self.webhook_trigger_channel_id: int = int(self._get_config('WEBHOOK_TRIGGER_CHANNEL_ID', '0'))
        self.webhook_trigger_username: str = self._get_config('WEBHOOK_TRIGGER_USERNAME', 'ET:Legacy Stats')

        # Webhook ID whitelist (REQUIRED for security)
        webhook_whitelist_raw = self._get_config('WEBHOOK_TRIGGER_WHITELIST', '')
        self.webhook_trigger_whitelist: list = [
            id.strip() for id in webhook_whitelist_raw.split(',') if id.strip()
        ]

        # ==================== LINKING FEATURES ====================
        # Enable !select persistent selection cache (in-memory, TTL controlled)
        self.enable_link_selection_state: bool = self._get_config('ENABLE_LINK_SELECTION_STATE', 'false').lower() == 'true'
        self.link_selection_ttl_seconds: int = int(self._get_config('LINK_SELECTION_TTL_SECONDS', '60'))

        # ==================== VOICE SESSION SUMMARY ====================
        # Enable automatic session summary embeds after voice session ends
        self.enable_voice_auto_summary: bool = self._get_config('ENABLE_VOICE_AUTO_SUMMARY', 'false').lower() == 'true'

        # ==================== AVAILABILITY POLL ====================
        # Daily "Who can play tonight?" poll system
        self.availability_poll_enabled: bool = self._get_config('AVAILABILITY_POLL_ENABLED', 'false').lower() == 'true'
        self.availability_poll_channel_id: int = int(self._get_config('AVAILABILITY_POLL_CHANNEL_ID', '0'))
        self.availability_poll_post_time: str = self._get_config('AVAILABILITY_POLL_POST_TIME', '10:00')
        self.availability_poll_timezone: str = self._get_config('AVAILABILITY_POLL_TIMEZONE', 'Europe/Ljubljana')
        self.availability_poll_threshold: int = int(self._get_config('AVAILABILITY_POLL_THRESHOLD', '6'))
        self.availability_poll_reminder_times: str = self._get_config('AVAILABILITY_POLL_REMINDER_TIMES', '20:45,21:00')
        self.availability_multichannel_enabled: bool = (
            self._get_config('AVAILABILITY_MULTICHANNEL_ENABLED', 'true').lower() == 'true'
        )
        self.availability_daily_reminder_time: str = self._get_config(
            'AVAILABILITY_DAILY_REMINDER_TIME',
            '16:00'
        )

        # ==================== AVAILABILITY NOTIFICATIONS (MULTI-CHANNEL) ====================
        # Session-ready scheduler threshold override (falls back to poll threshold)
        self.availability_session_ready_threshold: int = int(
            self._get_config('AVAILABILITY_SESSION_READY_THRESHOLD', str(self.availability_poll_threshold))
        )
        # Singleton scheduler lock key for advisory lock
        self.availability_scheduler_lock_key: int = int(
            self._get_config('AVAILABILITY_SCHEDULER_LOCK_KEY', '875211')
        )
        # Notification ledger retry behavior
        self.availability_notification_max_attempts: int = int(
            self._get_config('AVAILABILITY_NOTIFICATION_MAX_ATTEMPTS', '5')
        )
        self.availability_notification_retry_backoff_seconds: int = int(
            self._get_config('AVAILABILITY_NOTIFICATION_RETRY_BACKOFF_SECONDS', '120')
        )
        self.availability_notification_max_retry_backoff_seconds: int = int(
            self._get_config('AVAILABILITY_NOTIFICATION_MAX_RETRY_BACKOFF_SECONDS', '900')
        )
        self.availability_notification_claim_timeout_seconds: int = int(
            self._get_config('AVAILABILITY_NOTIFICATION_CLAIM_TIMEOUT_SECONDS', '300')
        )

        # Discord notification channels
        self.availability_discord_dm_enabled: bool = (
            self._get_config('AVAILABILITY_DISCORD_DM_ENABLED', 'true').lower() == 'true'
        )
        self.availability_discord_channel_announce_enabled: bool = (
            self._get_config('AVAILABILITY_DISCORD_CHANNEL_ANNOUNCE_ENABLED', 'false').lower() == 'true'
        )
        self.availability_discord_announce_channel_id: int = int(
            self._get_config(
                'AVAILABILITY_DISCORD_ANNOUNCE_CHANNEL_ID',
                str(self.availability_poll_channel_id or 0)
            )
        )

        # Link-token flow for Telegram/Signal subscription commands
        self.availability_link_token_ttl_minutes: int = int(
            self._get_config('AVAILABILITY_LINK_TOKEN_TTL_MINUTES', '30')
        )

        # Telegram connector (feature-flagged)
        self.availability_telegram_enabled: bool = (
            self._get_config('AVAILABILITY_TELEGRAM_ENABLED', 'false').lower() == 'true'
        )
        self.availability_telegram_bot_token: str = self._get_config(
            'AVAILABILITY_TELEGRAM_BOT_TOKEN',
            self._get_config('TELEGRAM_BOT_TOKEN', '')
        )
        self.availability_telegram_api_base_url: str = self._get_config(
            'AVAILABILITY_TELEGRAM_API_BASE_URL',
            'https://api.telegram.org'
        )
        self.availability_telegram_min_interval_seconds: float = float(
            self._get_config('AVAILABILITY_TELEGRAM_MIN_INTERVAL_SECONDS', '0.25')
        )
        self.availability_telegram_max_retries: int = int(
            self._get_config('AVAILABILITY_TELEGRAM_MAX_RETRIES', '3')
        )
        self.availability_telegram_request_timeout_seconds: int = int(
            self._get_config('AVAILABILITY_TELEGRAM_REQUEST_TIMEOUT_SECONDS', '15')
        )

        # Signal connector (feature-flagged)
        self.availability_signal_enabled: bool = (
            self._get_config('AVAILABILITY_SIGNAL_ENABLED', 'false').lower() == 'true'
        )
        self.availability_signal_mode: str = self._get_config('AVAILABILITY_SIGNAL_MODE', 'cli').strip().lower()
        self.availability_signal_cli_path: str = self._get_config('AVAILABILITY_SIGNAL_CLI_PATH', 'signal-cli')
        self.availability_signal_sender: str = self._get_config('AVAILABILITY_SIGNAL_SENDER', '')
        self.availability_signal_daemon_url: str = self._get_config(
            'AVAILABILITY_SIGNAL_DAEMON_URL',
            'http://127.0.0.1:8080'
        )
        self.availability_signal_min_interval_seconds: float = float(
            self._get_config('AVAILABILITY_SIGNAL_MIN_INTERVAL_SECONDS', '0.25')
        )
        self.availability_signal_max_retries: int = int(
            self._get_config('AVAILABILITY_SIGNAL_MAX_RETRIES', '2')
        )
        self.availability_signal_request_timeout_seconds: int = int(
            self._get_config('AVAILABILITY_SIGNAL_REQUEST_TIMEOUT_SECONDS', '20')
        )

        # Promotion campaign scheduler
        self.availability_promotion_enabled: bool = (
            self._get_config('AVAILABILITY_PROMOTION_ENABLED', 'true').lower() == 'true'
        )
        self.availability_promotion_timezone: str = self._get_config(
            'AVAILABILITY_PROMOTION_TIMEZONE',
            self.availability_poll_timezone,
        )
        self.availability_promotion_reminder_time: str = self._get_config(
            'AVAILABILITY_PROMOTION_REMINDER_TIME',
            '20:45',
        )
        self.availability_promotion_start_time: str = self._get_config(
            'AVAILABILITY_PROMOTION_START_TIME',
            '21:00',
        )
        self.availability_promotion_followup_channel_id: int = int(
            self._get_config(
                'AVAILABILITY_PROMOTION_FOLLOWUP_CHANNEL_ID',
                str(self.availability_discord_announce_channel_id or self.availability_poll_channel_id or 0),
            )
        )
        self.availability_promotion_voice_check_enabled: bool = (
            self._get_config('AVAILABILITY_PROMOTION_VOICE_CHECK_ENABLED', 'true').lower() == 'true'
        )
        self.availability_promotion_server_check_enabled: bool = (
            self._get_config('AVAILABILITY_PROMOTION_SERVER_CHECK_ENABLED', 'true').lower() == 'true'
        )
        self.availability_promotion_job_max_attempts: int = int(
            self._get_config('AVAILABILITY_PROMOTION_JOB_MAX_ATTEMPTS', '5')
        )

        # ==================== TEAM MAP PERFORMANCE ====================
        # Enable TeamManager.get_map_performance (experimental)
        self.enable_team_map_performance: bool = self._get_config('ENABLE_TEAM_MAP_PERFORMANCE', 'false').lower() == 'true'

        # ==================== WEBSOCKET PUSH NOTIFICATIONS (DEPRECATED) ====================
        # Bot connects OUT to VPS WebSocket server (no ports needed on bot machine)
        # NOTE: Replaced by webhook trigger approach (Dec 2025)
        self.ws_enabled: bool = self._get_config('WS_ENABLED', 'false').lower() == 'true'
        self.ws_scheme: str = self._get_config('WS_SCHEME', 'wss').strip().lower()  # wss (recommended) or ws
        self.ws_host: str = self._get_config('WS_HOST', '')  # VPS hostname/IP
        self.ws_port: int = int(self._get_config('WS_PORT', '8765'))
        self.ws_auth_token: str = self._get_config('WS_AUTH_TOKEN', '')  # Shared secret for authentication
        self.ws_reconnect_delay: int = int(self._get_config('WS_RECONNECT_DELAY', '5'))  # seconds between reconnect attempts

        # ==================== VOICE CHANNEL LOGGING ====================
        # Log when players join/leave gaming voice channels
        self.enable_voice_logging: bool = self._get_config('ENABLE_VOICE_LOGGING', 'false').lower() == 'true'

        # ==================== PROXIMITY TRACKER ====================
        # Combat engagement analytics (crossfire detection, teamplay stats)
        self.proximity_enabled: bool = self._get_config('PROXIMITY_ENABLED', 'false').lower() == 'true'
        self.proximity_auto_import: bool = self._get_config('PROXIMITY_AUTO_IMPORT', 'true').lower() == 'true'
        self.proximity_debug_log: bool = self._get_config('PROXIMITY_DEBUG_LOG', 'false').lower() == 'true'
        self.proximity_discord_commands: bool = self._get_config('PROXIMITY_DISCORD_COMMANDS', 'false').lower() == 'true'
        self.proximity_remote_path: str = self._get_config('PROXIMITY_REMOTE_PATH', '')
        self.proximity_local_path: str = self._get_config('PROXIMITY_LOCAL_PATH', 'local_proximity')
        self.proximity_startup_lookback_hours: int = int(
            self._get_config('PROXIMITY_STARTUP_LOOKBACK_HOURS', str(self.ssh_startup_lookback_hours))
        )

        # ==================== SESSION TIMING DUAL MODE ====================
        # Show legacy (old) and shadow-corrected (new) timing side-by-side in last_session views/graphs
        self.show_timing_dual: bool = self._get_config('SHOW_TIMING_DUAL', 'false').lower() == 'true'

        # ==================== TIMING DEBUG ====================
        # Compare stats file timing vs Lua webhook timing for validation
        self.timing_debug_enabled: bool = self._get_config('TIMING_DEBUG_ENABLED', 'true').lower() == 'true'
        self.timing_debug_channel_id: int = int(self._get_config('TIMING_DEBUG_CHANNEL_ID', '1424620499975274496'))

        logger.info(f"🔧 Configuration loaded: database_type={self.database_type}")

    def _load_config_file(self):
        """Load configuration from JSON file."""
        try:
            with open(self.config_file, 'r') as f:
                self._config_data = json.load(f)
            logger.info(f"📄 Config file loaded: {self.config_file}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to load config file {self.config_file}: {e}")
            self._config_data = {}

    def _get_config(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value with priority: ENV > config file > default.

        Args:
            key: Configuration key
            default: Default value if not found

        Returns:
            Configuration value
        """
        # 1. Check environment variables
        env_value = os.getenv(key)
        if env_value is not None:
            return _strip_inline_env_comment(env_value)

        # 2. Check config file
        if key in self._config_data:
            return self._config_data[key]

        # 3. Return default
        return default

    def get_database_adapter_kwargs(self) -> Dict[str, Any]:
        """
        Get kwargs for creating database adapter.

        Returns:
            Dictionary of parameters for create_adapter()
        """
        if self.database_type.lower() == 'sqlite':
            return {
                'db_type': 'sqlite',
                'db_path': self.sqlite_db_path
            }
        elif self.database_type.lower() in ('postgresql', 'postgres'):
            return {
                'db_type': 'postgresql',
                'host': self.postgres_host,
                'port': self.postgres_port,
                'database': self.postgres_database,
                'user': self.postgres_user,
                'password': self.postgres_password,
                'min_pool_size': self.postgres_min_pool,
                'max_pool_size': self.postgres_max_pool,
                'ssl_mode': self.postgres_ssl_mode,
                'ssl_cert': self.postgres_ssl_cert,
                'ssl_key': self.postgres_ssl_key,
                'ssl_root_cert': self.postgres_ssl_root_cert
            }
        else:
            raise ValueError(f"Unsupported database type: {self.database_type}")

    def get_postgres_connection_url(self) -> str:
        """
        Build PostgreSQL connection URL.

        Returns:
            PostgreSQL connection string
        """
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_database}"
        )

    def save_example_config(self, output_path: str = "bot_config.example.json"):
        """
        Save example configuration file with all available options.

        Args:
            output_path: Path to save example config
        """
        example = {
            "DATABASE_TYPE": "sqlite",
            "SQLITE_DB_PATH": "bot/etlegacy_production.db",
            "POSTGRES_HOST": "localhost",
            "POSTGRES_PORT": "5432",
            "POSTGRES_DATABASE": "etlegacy_stats",
            "POSTGRES_USER": "etlegacy",
            "POSTGRES_PASSWORD": "your_secure_password_here",
            "POSTGRES_MIN_POOL": "5",
            "POSTGRES_MAX_POOL": "20",
            "DISCORD_BOT_TOKEN": "your_discord_bot_token_here",
            "DISCORD_GUILD_ID": "your_guild_id_here",
            "DISCORD_STATS_CHANNEL_ID": "your_stats_channel_id_here",
            "STATS_DIRECTORY": "local_stats",
            "BACKUP_DIRECTORY": "processed_stats"
        }

        with open(output_path, 'w') as f:
            json.dump(example, f, indent=2)

        logger.info(f"📝 Example config saved: {output_path}")

    def validate(self) -> List[str]:
        """
        Validate configuration and return list of errors.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Discord token is required
        if not self.discord_token:
            errors.append("DISCORD_BOT_TOKEN is required")

        # Database configuration
        if self.database_type.lower() == 'postgresql':
            if not self.postgres_host:
                errors.append("POSTGRES_HOST is required for PostgreSQL")
            if not self.postgres_user:
                errors.append("POSTGRES_USER is required for PostgreSQL")
            if not self.postgres_password:
                errors.append("POSTGRES_PASSWORD is required for PostgreSQL")
            if not self.postgres_database:
                errors.append("POSTGRES_DATABASE is required for PostgreSQL")

        # SSH configuration (if enabled)
        if self.ssh_enabled:
            if not self.ssh_host:
                errors.append("SSH_HOST is required when SSH_ENABLED=true")
            if not self.ssh_user:
                errors.append("SSH_USER is required when SSH_ENABLED=true")
            if not self.ssh_key_path:
                errors.append("SSH_KEY_PATH is required when SSH_ENABLED=true")
            if not self.ssh_remote_path:
                errors.append("REMOTE_STATS_PATH is required when SSH_ENABLED=true")

        # Monitoring configuration (if enabled)
        if self.monitoring_enabled:
            if not self.server_host:
                errors.append("SERVER_HOST is required when MONITORING_ENABLED=true")

        # RCON configuration (if enabled)
        if self.rcon_enabled:
            if not self.rcon_host:
                errors.append("RCON_HOST is required when RCON_ENABLED=true")
            if not self.rcon_password:
                errors.append("RCON_PASSWORD is required when RCON_ENABLED=true")

        # Availability connector configuration (if enabled)
        if self.availability_telegram_enabled and not self.availability_telegram_bot_token:
            errors.append("AVAILABILITY_TELEGRAM_BOT_TOKEN is required when AVAILABILITY_TELEGRAM_ENABLED=true")

        if self.availability_signal_enabled and not self.availability_signal_sender:
            errors.append("AVAILABILITY_SIGNAL_SENDER is required when AVAILABILITY_SIGNAL_ENABLED=true")

        return errors

    def log_configuration(self):
        """Log the current configuration (for debugging)."""
        logger.info("=" * 80)
        logger.info("📋 CONFIGURATION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"  Database: {self.database_type}")
        if self.database_type.lower() == 'postgresql':
            logger.info(f"  PostgreSQL: {self.postgres_host}:{self.postgres_port}/{self.postgres_database}")
        logger.info(f"  Automation: {'ENABLED' if self.automation_enabled else 'DISABLED'}")
        logger.info(f"  SSH Monitoring: {'ENABLED' if self.ssh_enabled else 'DISABLED'}")
        logger.info(f"  Activity Monitoring: {'ENABLED' if self.monitoring_enabled else 'DISABLED'}")
        if self.monitoring_enabled:
            logger.info(
                f"  Monitor Server: {self.server_host}:{self.server_port} "
                f"every {self.monitoring_server_interval_seconds}s"
            )
            logger.info(
                f"  Monitor Voice: every {self.monitoring_voice_interval_seconds}s"
            )
        if self.gaming_voice_channels:
            logger.info(f"  Voice Channels: {len(self.gaming_voice_channels)} monitored")
        logger.info(f"  Session Thresholds: {self.session_start_threshold}+ to start, <{self.session_end_threshold} to end")
        logger.info("=" * 80)

    def __repr__(self):
        """String representation (hides passwords)."""
        return (
            f"BotConfig(database_type={self.database_type}, "
            f"automation={self.automation_enabled}, "
            f"ssh={self.ssh_enabled}, "
            f"channels={len(self.gaming_voice_channels)} voice)"
        )


# Convenience function for quick config loading
def load_config(config_file: Optional[str] = None) -> BotConfig:
    """
    Load bot configuration.

    Args:
        config_file: Optional path to config file

    Returns:
        BotConfig instance
    """
    return BotConfig(config_file)
