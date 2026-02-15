"""
Common utility functions for the bot.

Contains shared helpers used across multiple cogs and modules.
"""

import re


def escape_like_pattern(pattern: str, escape_char: str = "\\") -> str:
    """
    Escape special characters in a LIKE pattern to prevent SQL injection.
    
    SQL LIKE patterns use % and _ as wildcards. If user input contains
    these characters, they must be escaped to match literally.
    
    Args:
        pattern: The user-provided search pattern
        escape_char: The escape character to use (default: backslash)
    
    Returns:
        Escaped pattern safe for use in LIKE queries
    
    Example:
        >>> escape_like_pattern("test%user")
        'test\\%user'
        >>> escape_like_pattern("user_name")
        'user\\_name'
        >>> escape_like_pattern("100% complete")
        '100\\% complete'
    
    Usage in queries:
        escaped = escape_like_pattern(user_input)
        query = f"SELECT * FROM players WHERE name LIKE '%{escaped}%' ESCAPE '\\'"
        
        Or with parameterized queries (preferred):
        escaped = escape_like_pattern(user_input)
        query = "SELECT * FROM players WHERE name LIKE $1 ESCAPE '\\'"
        params = [f"%{escaped}%"]
    """
    # Escape the escape character first, then wildcards
    pattern = pattern.replace(escape_char, escape_char + escape_char)
    pattern = pattern.replace("%", escape_char + "%")
    pattern = pattern.replace("_", escape_char + "_")
    return pattern


def escape_like_pattern_for_query(
    pattern: str,
    prefix: str = "%",
    suffix: str = "%"
) -> str:
    """
    Escape a LIKE pattern and wrap with wildcards for common search use.
    
    Args:
        pattern: The user-provided search pattern
        prefix: Wildcard prefix (default: % for contains search)
        suffix: Wildcard suffix (default: % for contains search)
    
    Returns:
        Ready-to-use LIKE pattern with proper escaping
    
    Example:
        >>> escape_like_pattern_for_query("test")
        '%test%'
        >>> escape_like_pattern_for_query("test%", prefix="", suffix="%")
        'test\\%%'
    """
    escaped = escape_like_pattern(pattern)
    return f"{prefix}{escaped}{suffix}"


def sanitize_error_message(error: Exception) -> str:
    """
    Create a safe error message for display to users.
    
    Removes potentially sensitive information like file paths,
    database details, or stack traces.
    
    Args:
        error: The exception to sanitize
    
    Returns:
        A user-friendly error message
    """
    error_str = str(error)
    
    # Remove database connection strings FIRST (before path regex catches them)
    error_str = re.sub(
        r'postgresql://[^\s\'"]+',
        '[database]',
        error_str
    )
    error_str = re.sub(
        r'postgres://[^\s\'"]+',
        '[database]',
        error_str
    )
    
    # Remove file paths (both Windows and Unix)
    error_str = re.sub(r'[A-Za-z]:\\[^\s\'"]+', '[path]', error_str)
    error_str = re.sub(r'/[^\s\'"]+/[^\s\'"]+', '[path]', error_str)
    
    # Remove IP addresses
    error_str = re.sub(
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?',
        '[host]',
        error_str
    )
    
    # Truncate long messages
    max_length = 200
    if len(error_str) > max_length:
        error_str = error_str[:max_length] + "..."
    
    return error_str


async def send_safe_error(
    ctx,
    error: Exception,
    user_message: str = "An error occurred while processing your request."
) -> None:
    """
    Send a safe error message to the user without exposing internals.
    
    Args:
        ctx: Discord context
        error: The exception that occurred
        user_message: Generic message to show the user
    """
    # Log the full error for debugging
    import logging
    logger = logging.getLogger(__name__)
    logger.error(f"Error in command: {error}", exc_info=True)
    
    # Send sanitized message to user
    await ctx.send(f"❌ {user_message}")


def format_duration(seconds: int) -> str:
    """
    Format a duration in seconds to a human-readable string.
    
    Args:
        seconds: Duration in seconds
    
    Returns:
        Formatted string like "2h 30m" or "45s"
    """
    if seconds < 60:
        return f"{seconds}s"
    
    minutes = seconds // 60
    remaining_seconds = seconds % 60
    
    if minutes < 60:
        if remaining_seconds:
            return f"{minutes}m {remaining_seconds}s"
        return f"{minutes}m"
    
    hours = minutes // 60
    remaining_minutes = minutes % 60
    
    if remaining_minutes:
        return f"{hours}h {remaining_minutes}m"
    return f"{hours}h"


def truncate_string(text: str, max_length: int = 100) -> str:
    """
    Truncate a string to a maximum length with ellipsis.
    
    Args:
        text: String to truncate
        max_length: Maximum length including ellipsis
    
    Returns:
        Truncated string
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def validate_stats_filename(filename: str) -> bool:
    """
    Strict validation for stats filenames.

    Valid format: YYYY-MM-DD-HHMMSS-mapname-round-N.txt
    Example: 2025-12-09-221829-etl_sp_delivery-round-1.txt

    Security: Prevents path traversal, injection, null bytes.

    This is a standalone version of the validation logic in
    ultimate_bot.py._validate_stats_filename(), kept in sync
    so it can be tested without instantiating the full bot.

    Args:
        filename: The filename to validate (basename only, no directory)

    Returns:
        True if the filename is valid, False otherwise
    """
    # Length check (prevent DoS)
    if len(filename) > 255:
        return False

    # Path traversal checks
    if any(char in filename for char in ['/', '\\', '\0']):
        return False

    if '..' in filename:
        return False

    # Strict pattern: YYYY-MM-DD-HHMMSS-mapname-round-N.txt
    pattern = r'^(\d{4})-(\d{2})-(\d{2})-(\d{6})-([a-zA-Z0-9_-]+)-round-(\d+)\.txt$'
    match = re.match(pattern, filename)

    if not match:
        return False

    # Validate components
    year, month, day, timestamp, map_name, round_num = match.groups()

    if not (2020 <= int(year) <= 2035):
        return False
    if not (1 <= int(month) <= 12):
        return False
    if not (1 <= int(day) <= 31):
        return False
    if not (1 <= int(round_num) <= 10):
        return False
    if len(map_name) > 50:
        return False

    # Validate timestamp (HHMMSS)
    hour = int(timestamp[0:2])
    minute = int(timestamp[2:4])
    second = int(timestamp[4:6])
    if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
        return False

    return True


def normalize_player_name(name: str) -> str:
    """
    Normalize a player name for consistent comparison.
    
    Removes ET color codes (^X) and normalizes whitespace.
    
    Args:
        name: Player name possibly with color codes
    
    Returns:
        Cleaned player name
    """
    # Remove ET color codes (^0 through ^9, ^a through ^z, ^^)
    cleaned = re.sub(r'\^[0-9a-zA-Z]', '', name)
    # Normalize whitespace
    cleaned = ' '.join(cleaned.split())
    return cleaned.strip()
