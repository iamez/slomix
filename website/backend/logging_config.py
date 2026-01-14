"""
Logging Configuration Module

Industry-standard logging setup with:
- Log rotation (size and time-based)
- Separate log files by severity
- Security-aware filtering (redacts sensitive data)
- Structured JSON logging for production
- Request correlation IDs
"""

import os
import re
import sys
import json
import logging
import logging.handlers
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# =============================================================================
# Configuration
# =============================================================================

# Log directory - relative to project root
LOG_DIR = Path(__file__).parent.parent / "logs"

# Log levels for different files
LOG_FILES = {
    "app": {
        "filename": "app.log",
        "level": logging.INFO,
        "max_bytes": 10 * 1024 * 1024,  # 10 MB
        "backup_count": 5,
    },
    "error": {
        "filename": "error.log",
        "level": logging.ERROR,
        "max_bytes": 10 * 1024 * 1024,  # 10 MB
        "backup_count": 10,  # Keep more error logs
    },
    "debug": {
        "filename": "debug.log",
        "level": logging.DEBUG,
        "max_bytes": 50 * 1024 * 1024,  # 50 MB (debug is verbose)
        "backup_count": 3,
    },
    "security": {
        "filename": "security.log",
        "level": logging.INFO,
        "max_bytes": 10 * 1024 * 1024,  # 10 MB
        "backup_count": 30,  # Keep security logs longer
    },
    "access": {
        "filename": "access.log",
        "level": logging.INFO,
        "max_bytes": 20 * 1024 * 1024,  # 20 MB
        "backup_count": 7,
    },
}

# Patterns to redact from logs (security)
SENSITIVE_PATTERNS = [
    # Tokens and secrets
    (r'(Bearer\s+)[A-Za-z0-9\-_]+\.?[A-Za-z0-9\-_]*\.?[A-Za-z0-9\-_]*', r'\1[REDACTED]'),
    (r'(token["\s:=]+)["\']?[A-Za-z0-9\-_\.]+["\']?', r'\1[REDACTED]'),
    (r'(access_token["\s:=]+)["\']?[A-Za-z0-9\-_\.]+["\']?', r'\1[REDACTED]'),
    (r'(refresh_token["\s:=]+)["\']?[A-Za-z0-9\-_\.]+["\']?', r'\1[REDACTED]'),

    # Passwords and secrets
    (r'(password["\s:=]+)["\']?[^"\s,}\]]+["\']?', r'\1[REDACTED]'),
    (r'(secret["\s:=]+)["\']?[^"\s,}\]]+["\']?', r'\1[REDACTED]'),
    (r'(api_key["\s:=]+)["\']?[^"\s,}\]]+["\']?', r'\1[REDACTED]'),

    # Session IDs
    (r'(session[_-]?id["\s:=]+)["\']?[A-Za-z0-9\-_]+["\']?', r'\1[REDACTED]'),

    # Discord OAuth
    (r'(client_secret["\s:=]+)["\']?[^"\s,}\]]+["\']?', r'\1[REDACTED]'),
    (r'(code["\s:=]+)["\']?[A-Za-z0-9]+["\']?', r'\1[REDACTED]'),

    # Cookie values
    (r'(Cookie:\s*)[^\n]+', r'\1[REDACTED]'),
    (r'(Set-Cookie:\s*)[^\n]+', r'\1[REDACTED]'),
]

# Compile patterns for efficiency
COMPILED_PATTERNS = [(re.compile(p, re.IGNORECASE), r) for p, r in SENSITIVE_PATTERNS]


# =============================================================================
# Security Filter
# =============================================================================

class SensitiveDataFilter(logging.Filter):
    """Filter that redacts sensitive information from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact sensitive data from the log message."""
        if hasattr(record, 'msg') and record.msg:
            record.msg = self._redact(str(record.msg))

        if hasattr(record, 'args') and record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._redact(str(v)) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self._redact(str(arg)) for arg in record.args)

        return True

    def _redact(self, text: str) -> str:
        """Apply all redaction patterns to text."""
        for pattern, replacement in COMPILED_PATTERNS:
            text = pattern.sub(replacement, text)
        return text


# =============================================================================
# Formatters
# =============================================================================

class JSONFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.
    Ideal for log aggregation systems (ELK, Loki, CloudWatch, etc.)
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields (request_id, user_id, etc.)
        for key in ['request_id', 'user_id', 'client_ip', 'method', 'path', 'status_code', 'duration_ms']:
            if hasattr(record, key):
                log_data[key] = getattr(record, key)

        return json.dumps(log_data, default=str)


class ColoredFormatter(logging.Formatter):
    """Colored console formatter for development."""

    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)

        # Format timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Build message
        msg = f"{color}{timestamp} | {record.levelname:8}{self.RESET} | {record.name} | {record.getMessage()}"

        # Add exception if present
        if record.exc_info:
            msg += f"\n{self.formatException(record.exc_info)}"

        return msg


class StandardFormatter(logging.Formatter):
    """Standard file formatter with consistent structure."""

    def __init__(self):
        super().__init__(
            fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )


# =============================================================================
# Logger Setup
# =============================================================================

def setup_logging(
    log_level: str = "INFO",
    json_logs: bool = False,
    console_output: bool = True,
) -> logging.Logger:
    """
    Configure application logging.

    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_logs: Use JSON format for file logs (recommended for production)
        console_output: Also output to console

    Returns:
        Root logger instance
    """
    # Create log directory with secure permissions
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Set directory permissions (owner read/write/execute only)
    try:
        os.chmod(LOG_DIR, 0o750)
    except OSError:
        pass  # May fail on some systems, continue anyway

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture all, filter at handler level

    # Clear existing handlers
    root_logger.handlers.clear()

    # Create security filter
    security_filter = SensitiveDataFilter()

    # Select formatter
    file_formatter = JSONFormatter() if json_logs else StandardFormatter()

    # Setup file handlers
    for log_name, config in LOG_FILES.items():
        handler = logging.handlers.RotatingFileHandler(
            filename=LOG_DIR / config["filename"],
            maxBytes=config["max_bytes"],
            backupCount=config["backup_count"],
            encoding="utf-8",
        )
        handler.setLevel(config["level"])
        handler.setFormatter(file_formatter)
        handler.addFilter(security_filter)

        # Set file permissions (owner read/write only)
        log_file = LOG_DIR / config["filename"]
        if log_file.exists():
            try:
                os.chmod(log_file, 0o640)
            except OSError:
                pass

        root_logger.addHandler(handler)

    # Console handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level.upper()))
        console_handler.setFormatter(ColoredFormatter())
        console_handler.addFilter(security_filter)
        root_logger.addHandler(console_handler)

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncpg").setLevel(logging.WARNING)

    return root_logger


# =============================================================================
# Specialized Loggers
# =============================================================================

def get_security_logger() -> logging.Logger:
    """Get logger for security-related events (auth, access control, etc.)."""
    return logging.getLogger("security")


def get_access_logger() -> logging.Logger:
    """Get logger for HTTP access logs."""
    return logging.getLogger("access")


def get_app_logger(name: str = "app") -> logging.Logger:
    """Get logger for application events."""
    return logging.getLogger(name)


# =============================================================================
# Context Manager for Request Logging
# =============================================================================

class LogContext:
    """
    Context manager for adding contextual data to log records.

    Usage:
        with LogContext(request_id="abc123", user_id="user456"):
            logger.info("Processing request")  # Will include request_id and user_id
    """

    _context: dict = {}

    def __init__(self, **kwargs):
        self.data = kwargs
        self._old_factory = None

    def __enter__(self):
        self._old_factory = logging.getLogRecordFactory()
        context_data = self.data

        def factory(*args, **kwargs):
            record = self._old_factory(*args, **kwargs)
            for key, value in context_data.items():
                setattr(record, key, value)
            return record

        logging.setLogRecordFactory(factory)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        logging.setLogRecordFactory(self._old_factory)
        return False
