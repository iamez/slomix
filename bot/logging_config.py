"""
Comprehensive Logging Configuration for ET:Legacy Discord Bot
Implements rotating file handlers, multiple log levels, and structured logging
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from datetime import datetime

# Create logs directory if it doesn't exist
LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Custom formatter with more context
class DetailedFormatter(logging.Formatter):
    """Custom formatter with color support for console and detailed info for files"""

    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'
    }

    def __init__(self, use_colors=False):
        super().__init__()
        self.use_colors = use_colors

    def format(self, record):
        # Add custom attributes if they don't exist
        if not hasattr(record, 'user_id'):
            record.user_id = 'N/A'
        if not hasattr(record, 'command'):
            record.command = 'N/A'
        if not hasattr(record, 'guild_id'):
            record.guild_id = 'N/A'

        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')

        # Base format
        if self.use_colors:
            color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
            reset = self.COLORS['RESET']
            log_fmt = f"{timestamp} | {color}{record.levelname:8}{reset} | {record.name:25} | {record.getMessage()}"
        else:
            log_fmt = f"{timestamp} | {record.levelname:8} | {record.name:25} | {record.getMessage()}"

        # Add exception info if present
        if record.exc_info:
            log_fmt += f"\n{self.formatException(record.exc_info)}"

        return log_fmt


def setup_logging(log_level=logging.INFO):
    """
    Setup comprehensive logging with multiple handlers

    Creates 5 log files:
    - bot.log: All logs (INFO and above)
    - errors.log: Warnings, errors, and critical issues (WARNING and above)
    - commands.log: Command execution tracking
    - database.log: Database operations
    - webhook.log: Webhook notifications and processing

    Each file rotates at 10MB with 5 backups (max 50MB per log type)
    """

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture everything, handlers will filter

    # Remove any existing handlers
    root_logger.handlers.clear()

    # ==================== CONSOLE HANDLER ====================
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(DetailedFormatter(use_colors=True))
    root_logger.addHandler(console_handler)

    # ==================== MAIN BOT LOG FILE ====================
    # Rotating file handler - 10MB per file, keep 5 backups
    bot_log_file = LOGS_DIR / "bot.log"
    bot_file_handler = logging.handlers.RotatingFileHandler(
        bot_log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    bot_file_handler.setLevel(logging.INFO)
    bot_file_handler.setFormatter(DetailedFormatter(use_colors=False))
    root_logger.addHandler(bot_file_handler)

    # ==================== ERROR LOG FILE ====================
    # Warnings, errors, and critical issues (WARNING+)
    error_log_file = LOGS_DIR / "errors.log"
    error_file_handler = logging.handlers.RotatingFileHandler(
        error_log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    error_file_handler.setLevel(logging.WARNING)  # Changed from ERROR to WARNING
    error_file_handler.setFormatter(DetailedFormatter(use_colors=False))
    root_logger.addHandler(error_file_handler)

    # ==================== COMMAND LOG FILE ====================
    # Track all command executions
    command_logger = logging.getLogger('bot.commands')
    command_log_file = LOGS_DIR / "commands.log"
    command_file_handler = logging.handlers.RotatingFileHandler(
        command_log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    command_file_handler.setLevel(logging.INFO)
    command_file_handler.setFormatter(DetailedFormatter(use_colors=False))
    command_logger.addHandler(command_file_handler)

    # ==================== DATABASE LOG FILE ====================
    # Track database operations
    db_logger = logging.getLogger('bot.database')
    db_log_file = LOGS_DIR / "database.log"
    db_file_handler = logging.handlers.RotatingFileHandler(
        db_log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    db_file_handler.setLevel(logging.DEBUG)
    db_file_handler.setFormatter(DetailedFormatter(use_colors=False))
    db_logger.addHandler(db_file_handler)

    # ==================== WEBHOOK LOG FILE ====================
    # Track webhook notifications and processing
    webhook_logger = logging.getLogger('bot.webhook')
    webhook_log_file = LOGS_DIR / "webhook.log"
    webhook_file_handler = logging.handlers.RotatingFileHandler(
        webhook_log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    webhook_file_handler.setLevel(logging.DEBUG)
    webhook_file_handler.setFormatter(DetailedFormatter(use_colors=False))
    webhook_logger.addHandler(webhook_file_handler)

    # ==================== SILENCE NOISY LIBRARIES ====================
    # Reduce noise from discord.py and other libraries
    logging.getLogger('discord').setLevel(logging.WARNING)
    logging.getLogger('discord.http').setLevel(logging.WARNING)
    logging.getLogger('discord.gateway').setLevel(logging.WARNING)
    logging.getLogger('discord.client').setLevel(logging.INFO)
    logging.getLogger('asyncio').setLevel(logging.WARNING)

    # Log startup message
    logger = logging.getLogger('bot.core')
    logger.info("=" * 80)
    logger.info(f"Logging system initialized - Level: {logging.getLevelName(log_level)}")
    logger.info(f"Log directory: {LOGS_DIR.absolute()}")
    logger.info("Log files: bot.log, errors.log (WARNING+), commands.log, database.log, webhook.log")
    logger.info("Rotation: 10MB per file, 5 backups each (max 50MB per log type)")
    logger.info("=" * 80)

    return root_logger


def log_command_execution(ctx, command_name, start_time=None, end_time=None, error=None):
    """
    Log command execution with full context

    Args:
        ctx: Discord context
        command_name: Name of the command
        start_time: When command started (optional)
        end_time: When command finished (optional)
        error: Exception if command failed (optional)
    """
    logger = logging.getLogger('bot.commands')

    # Build context info
    # Note: Discord removed discriminators in 2023, use display_name instead
    user = f"{ctx.author.display_name} ({ctx.author.id})"
    guild = f"{ctx.guild.name} ({ctx.guild.id})" if ctx.guild else "DM"
    channel = f"#{ctx.channel.name} ({ctx.channel.id})" if hasattr(ctx.channel, 'name') else f"DM ({ctx.channel.id})"

    # Calculate execution time
    duration = ""
    if start_time and end_time:
        elapsed = end_time - start_time
        duration = f" [{elapsed:.2f}s]"

    # Log based on success/failure
    if error:
        logger.error(
            f"❌ FAILED: {command_name}{duration} | User: {user} | Guild: {guild} | Channel: {channel} | Error: {error}",
            exc_info=True
        )
    else:
        logger.info(
            f"✓ SUCCESS: {command_name}{duration} | User: {user} | Guild: {guild} | Channel: {channel}"
        )


def log_database_operation(operation, details, duration=None, error=None):
    """
    Log database operations

    Args:
        operation: Type of operation (SELECT, INSERT, UPDATE, etc.)
        details: Description of the operation
        duration: How long it took in seconds (optional)
        error: Exception if operation failed (optional)
    """
    logger = logging.getLogger('bot.database')

    duration_str = f" [{duration:.3f}s]" if duration else ""

    if error:
        logger.error(f"❌ DB {operation} FAILED{duration_str}: {details} | Error: {error}", exc_info=True)
    else:
        logger.debug(f"✓ DB {operation}{duration_str}: {details}")


def log_stats_import(filename, round_count=0, player_count=0, weapon_count=0, duration=None, error=None):
    """
    Log stats file import

    Args:
        filename: Name of the stats file
        round_count: Number of rounds imported
        player_count: Number of player stats imported
        weapon_count: Number of weapon stats imported
        duration: How long import took (optional)
        error: Exception if import failed (optional)
    """
    logger = logging.getLogger('bot.database')

    duration_str = f" [{duration:.2f}s]" if duration else ""

    if error:
        logger.error(f"❌ IMPORT FAILED{duration_str}: {filename} | Error: {error}", exc_info=True)
    else:
        logger.info(
            f"✓ IMPORTED{duration_str}: {filename} | "
            f"Rounds: {round_count}, Players: {player_count}, Weapons: {weapon_count}"
        )


def log_performance_warning(operation, duration, threshold=1.0):
    """
    Log slow operations that exceed threshold

    Args:
        operation: Description of the operation
        duration: How long it took in seconds
        threshold: Threshold in seconds (default 1.0)
    """
    if duration > threshold:
        logger = logging.getLogger('bot.performance')
        logger.warning(f"⚠️ SLOW OPERATION [{duration:.2f}s]: {operation}")


def log_automation_event(event_type, details, success=True, error=None):
    """
    Log automation events (SSH monitor, file tracker, etc.)

    Args:
        event_type: Type of event (e.g., 'SSH_DOWNLOAD', 'FILE_PROCESS', 'STATS_IMPORT')
        details: Description of the event
        success: Whether the event succeeded
        error: Exception if event failed (optional)
    """
    logger = logging.getLogger('bot.automation')

    if error:
        logger.error(f"❌ {event_type} FAILED: {details} | Error: {error}", exc_info=True)
    elif success:
        logger.info(f"✓ {event_type}: {details}")
    else:
        logger.warning(f"⚠️ {event_type}: {details}")


def get_logger(name):
    """
    Get a logger with the given name

    Args:
        name: Logger name (e.g., 'bot.cogs.stats')

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
