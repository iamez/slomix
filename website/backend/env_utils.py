"""Helpers for robust parsing of environment variables."""

from __future__ import annotations

import os


def strip_inline_comment(value: str) -> str:
    """Trim whitespace and strip shell-style inline comments."""
    trimmed = value.strip()
    comment_start = trimmed.find("#")
    if comment_start <= 0:
        return trimmed
    if not trimmed[comment_start - 1].isspace():
        return trimmed
    return trimmed[:comment_start].strip()


def getenv_int(key: str, default: int) -> int:
    """
    Parse integer environment values safely.

    Accepts values like: "27960  # ET:Legacy game port".
    """
    raw_value = os.getenv(key)
    if raw_value is None:
        return default
    cleaned = strip_inline_comment(raw_value)
    if cleaned == "":
        return default
    return int(cleaned)
