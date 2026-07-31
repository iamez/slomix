"""
Logging Configuration Module

Industry-standard logging setup with:
- Log rotation (size and time-based)
- Separate log files by severity
- Security-aware filtering (redacts sensitive data)
- Structured JSON logging for production
- Request correlation IDs
"""

import json
import logging
import logging.handlers
import os
import re
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# =============================================================================
# Configuration
# =============================================================================

# Log directory (default: repository root logs/). Override with WEB_LOG_DIR.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = Path(os.getenv("WEB_LOG_DIR", str(PROJECT_ROOT / "logs"))).resolve()

# Log levels for different files
LOG_FILES = {
    "app": {
        "filename": "web.log",
        "level": logging.INFO,
        "max_bytes": 10 * 1024 * 1024,  # 10 MB
        "backup_count": 5,
    },
    "error": {
        "filename": "errors.log",
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
    "client_error": {
        # Deliberately in a SUBDIRECTORY, not alongside the other five. The VM's
        # logrotate rule globs `${APP_DIR}/logs/*.log` (slomix_vm_setup.sh:
        # 1008-1016) and recreates each rotated file as `0640 ${BOT_USER}`.
        # That glob doesn't recurse, so nesting keeps this file out of it —
        # which matters because it's the one log that must stay 0600 and
        # web-owned: an external rotate would hand it to the bot user at 0640,
        # and the web process would go on writing to the renamed inode until
        # its own size-based rollover (Codex review on #578). Rotation here is
        # handled entirely by OwnerOnlyRotatingFileHandler.
        "filename": "client/client_errors.log",
        "level": logging.WARNING,
        "max_bytes": 10 * 1024 * 1024,  # 10 MB
        "backup_count": 5,
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
                record.args = {k: self._redact_value(v) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self._redact_value(arg) for arg in record.args)

        return True

    def _redact_value(self, value: Any) -> Any:
        """Redact sensitive data only from string values, preserving type of others."""
        if isinstance(value, str):
            return self._redact(value)
        return value

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
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # noqa: DTZ005 naive datetime for date-string arithmetic / SQL date filter / log timestamp display

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


class GroupWritableRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """RotatingFileHandler that re-applies 0660 after every rollover.

    The one-time chmod in setup_logging() only fixes the file that already
    exists at startup. doRollover() renames it aside and open()s a brand new
    file using the process umask, which does NOT preserve that chmod — the
    bot/web cross-process-group-write bug (see setup_logging()'s comment)
    reappears the moment the file first rotates, not just on service
    restart. Codex review on #568 caught this the one-time fix missed.
    """

    def doRollover(self) -> None:  # noqa: N802 - overriding stdlib's camelCase method name
        super().doRollover()
        try:
            # SUPPRESSION (py/overly-permissive-file) — see the identical note
            # in bot/logging_config.py. Group-write is the fix, not the defect:
            # 0640 crash-looped the bot twice on a log both services share. The
            # group is the private `slomix` service group, the directory stays
            # 0770, and the alternative is losing the guarantee on every
            # rollover — which is the exact regression review caught here once
            # already. Owner: iamez.
            # codeql[py/overly-permissive-file]
            os.chmod(self.baseFilename, 0o660)  # nosec B103 - group-write is intentional, see setup_logging()
        except OSError:
            # Best-effort by design: chmod can fail because the file is owned by
            # the bot's user (both services write this one file) or the
            # filesystem doesn't support POSIX modes. Raising here would break
            # rollover — i.e. break logging in order to fix a permission
            # nicety — and the bot's own handler applies the same chmod, so the
            # cross-user case is corrected from the other side.
            pass


class OwnerOnlyRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """RotatingFileHandler that keeps its file at 0600 across rollover.

    The owner-only counterpart to GroupWritableRotatingFileHandler above, for
    files with exactly one writer — unlike the shared bot/web files in
    setup_logging()'s main loop, which need 0660. Same underlying bug in both
    directions: a chmod applied once at setup time does not survive
    doRollover() opening a fresh file under the process umask (Codex review on
    #578, following the #568 fix for the group-writable case).
    """

    def fix_permissions(self) -> None:
        try:
            # No CodeQL suppression here, unlike the 0o660 handler above: 0600
            # is owner-only and py/overly-permissive-file does not fire on it.
            # (An earlier revision carried an `# lgtm[...]` marker; that form is
            # not honoured by code scanning and did nothing, so it is dropped
            # rather than left as decoration.)
            os.chmod(self.baseFilename, 0o600)  # nosec B103 - owner-only, deliberately restrictive
        except OSError:
            # Best-effort, same reasoning as the group-writable handler: some
            # filesystems don't support POSIX modes, and raising here would
            # break rollover to fix a permission nicety.
            pass

    def doRollover(self) -> None:  # noqa: N802 - overriding stdlib's camelCase method name
        super().doRollover()
        self.fix_permissions()


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

    # Set directory permissions to owner+group (rwx — the x bit is required
    # to traverse the directory); logs may contain request metadata, so deny
    # "other" access. Group access is required: the bot and web services run
    # as different OS users sharing one group (see slomix_vm_setup.sh
    # BOT_USER/WEB_USER/SLX_GROUP) and both need to create/rotate files in
    # this directory. Owner-only (0700) locks the other service out the next
    # time it needs to open a fresh or rotated file — this caused two
    # production incidents (2026-07-13, 2026-07-22: errors.log permission
    # bug crash-looped the bot).
    try:
        os.chmod(LOG_DIR, stat.S_IRWXU | stat.S_IRWXG)
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

    # Setup file handlers. "client_error" is deliberately excluded from this
    # loop: every handler here attaches to the root logger with no
    # logger-name filter, so (pre-existing behavior, not changed here) each
    # of these files ends up catching every INFO+ message from the whole
    # process, not just messages that match its own name. That's tolerable
    # for the existing five (general operational logs), but client_errors.log
    # needs to be genuinely dedicated to client error reports — see below.
    #
    # GroupWritableRotatingFileHandler (not the stdlib class) because these
    # five ARE the shared bot/web files: the 0660 mode has to be re-applied on
    # every rollover or the non-owning service loses write access to a fresh
    # file, which is what crash-looped the bot twice (#568). client_errors.log
    # is excluded here and gets the owner-only handler below instead.
    for name, config in LOG_FILES.items():
        if name == "client_error":
            continue
        handler = GroupWritableRotatingFileHandler(
            filename=LOG_DIR / config["filename"],
            maxBytes=config["max_bytes"],
            backupCount=config["backup_count"],
            encoding="utf-8",
        )
        handler.setLevel(config["level"])
        handler.setFormatter(file_formatter)
        handler.addFilter(security_filter)

        # Set file permissions (owner+group read/write). 0640 (group
        # read-only) blocks the bot service — a different OS user in the
        # same group — from writing/rotating this file once the web service
        # touches it, which is the root cause of the 2026-07-13 and
        # 2026-07-22 errors.log permission incidents.
        log_file = LOG_DIR / config["filename"]
        if log_file.exists():
            try:
                # SUPPRESSION (py/overly-permissive-file). Intentional per the
                # comment directly above: 0640 is what caused the 2026-07-13
                # and 2026-07-22 incidents. Group is the private `slomix`
                # service group; the directory is 0770. Owner: iamez.
                # codeql[py/overly-permissive-file]
                os.chmod(log_file, 0o660)  # nosec B103 - group-write is intentional here, see comment above
            except OSError:
                # Best-effort by design (same reasoning as the rollover handlers
                # above): a file already owned by the bot's user, or a
                # filesystem without POSIX modes, must not stop the web service
                # from starting up with working logging.
                pass

        root_logger.addHandler(handler)

    # client_error: attached only to the "client_error"-named logger, with
    # propagate=False, so this file holds *only* client error reports — not
    # every other log message in the process the way the loop above behaves
    # for the other five files.
    client_error_config = LOG_FILES["client_error"]
    client_error_path = LOG_DIR / client_error_config["filename"]
    client_error_path.parent.mkdir(parents=True, exist_ok=True)
    client_error_handler = OwnerOnlyRotatingFileHandler(
        filename=client_error_path,
        maxBytes=client_error_config["max_bytes"],
        backupCount=client_error_config["backup_count"],
        encoding="utf-8",
    )
    client_error_handler.setLevel(client_error_config["level"])
    client_error_handler.setFormatter(file_formatter)
    client_error_handler.addFilter(security_filter)
    client_error_handler.fix_permissions()
    client_error_logger = logging.getLogger("client_error")
    client_error_logger.handlers.clear()
    client_error_logger.propagate = False
    client_error_logger.setLevel(client_error_config["level"])
    client_error_logger.addHandler(client_error_handler)
    if console_output:
        # propagate=False means this logger's records never reach the root
        # logger's own console handler set up below. In the Docker deployment
        # the API container has no persistent log volume and container
        # logging only captures stdout/stderr, so without this, client error
        # reports were reachable ONLY at /app/logs/client_errors.log — absent
        # from `docker logs` and permanently lost the moment the container is
        # replaced, which is exactly when an operator would go looking
        # (Codex P2 review on #578).
        client_error_console_handler = logging.StreamHandler(sys.stdout)
        client_error_console_handler.setLevel(client_error_config["level"])
        client_error_console_handler.setFormatter(ColoredFormatter())
        client_error_console_handler.addFilter(security_filter)
        client_error_logger.addHandler(client_error_console_handler)

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
    logging.getLogger("multipart").setLevel(logging.WARNING)

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


def get_client_error_logger() -> logging.Logger:
    """Get logger for browser-reported client errors (logs/client_errors.log)."""
    return logging.getLogger("client_error")


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
