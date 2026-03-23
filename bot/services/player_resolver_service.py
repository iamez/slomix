"""
Unified player name-to-GUID resolution.

Replaces 3 duplicate implementations across analytics_cog, matchup_cog,
and synergy_analytics with a single canonical lookup chain:
  1. Exact GUID match
  2. Exact player_name match (case-insensitive)
  3. Partial player_name LIKE match
  4. player_aliases match
"""

import logging
from typing import Optional, List

from bot.core.utils import escape_like_pattern

logger = logging.getLogger(__name__)


async def resolve_player_guid(db_adapter, identifier: str) -> Optional[str]:
    """
    Resolve a player identifier (GUID or name) to a canonical GUID.

    Lookup chain:
      1. Exact GUID match in player_comprehensive_stats
      2. Exact player_name match (case-insensitive)
      3. Partial player_name LIKE match (most recent)
      4. player_aliases match (most recent)

    Returns None if no match found.
    """
    if not identifier or not identifier.strip():
        return None

    identifier = identifier.strip()

    # 1. Exact GUID
    row = await db_adapter.fetch_one(
        "SELECT player_guid FROM player_comprehensive_stats WHERE player_guid = ? LIMIT 1",
        (identifier,),
    )
    if row and row[0]:
        return row[0]

    # 2. Exact name (case-insensitive)
    row = await db_adapter.fetch_one(
        """SELECT player_guid FROM player_comprehensive_stats
           WHERE LOWER(player_name) = LOWER(?)
           GROUP BY player_guid ORDER BY MAX(round_date) DESC LIMIT 1""",
        (identifier,),
    )
    if row and row[0]:
        return row[0]

    # 3. Partial name LIKE (escaped to prevent wildcard injection)
    escaped = escape_like_pattern(identifier)
    row = await db_adapter.fetch_one(
        """SELECT player_guid FROM player_comprehensive_stats
           WHERE LOWER(player_name) LIKE LOWER(?)
           GROUP BY player_guid ORDER BY MAX(round_date) DESC LIMIT 1""",
        (f"%{escaped}%",),
    )
    if row and row[0]:
        return row[0]

    # 4. Aliases
    try:
        row = await db_adapter.fetch_one(
            """SELECT guid FROM player_aliases
               WHERE LOWER(alias) LIKE LOWER(?)
               ORDER BY last_seen DESC LIMIT 1""",
            (f"%{escaped}%",),
        )
        if row and row[0]:
            return row[0]
    except Exception:
        logger.debug("player_aliases lookup unavailable")

    return None


async def resolve_player_guids(db_adapter, names: List[str]) -> List[str]:
    """
    Batch-resolve a list of player names to GUIDs.
    Returns only successfully resolved GUIDs (list may be shorter than input).
    """
    guids = []
    for name in names:
        guid = await resolve_player_guid(db_adapter, name)
        if guid:
            guids.append(guid)
    return guids
