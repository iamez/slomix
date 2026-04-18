"""GUID utilities — canonical short/display forms for ET:Legacy player GUIDs.

ET:Legacy GUIDs come in two forms in the codebase:
- **Full** (32-char hex) — stored in most DB tables (player_comprehensive_stats, etc.)
- **Short** (first 8 chars) — used for display fallback when the player_name is
  missing, for OMNIBOT0 prefixes, and for LEFT(guid, 8) joins across legacy
  data.

This module centralises the handful of ``guid[:8]`` ``(guid or "?")[:8]``
``f"Player_{guid[:8]}"`` patterns that were duplicated across ~10 sites.
"""
from __future__ import annotations

GUID_SHORT_LEN: int = 8
GUID_MISSING_PLACEHOLDER: str = "?"


def short_guid(guid: str | None) -> str:
    """Return the 8-char display form of a GUID, tolerating None/empty input.

    >>> short_guid("abcdef0123456789abcdef0123456789")
    'abcdef01'
    >>> short_guid("")
    '?'
    >>> short_guid(None)
    '?'
    >>> short_guid("short")
    'short'
    """
    if not guid:
        return GUID_MISSING_PLACEHOLDER
    return guid[:GUID_SHORT_LEN]


def name_or_short_guid(name: str | None, guid: str | None) -> str:
    """Return a display name if present, else the short GUID form.

    Used by routers/services that render rows with ``COALESCE(name, guid[:8])``
    semantics in Python when the SQL COALESCE isn't available.

    >>> name_or_short_guid("Dmon", "abcdef0123456789")
    'Dmon'
    >>> name_or_short_guid("", "abcdef0123456789")
    'abcdef01'
    >>> name_or_short_guid(None, None)
    '?'
    """
    if name:
        return name
    return short_guid(guid)
