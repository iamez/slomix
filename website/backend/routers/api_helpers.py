"""
Shared helper functions for API routers.

Extracted from api.py to enable reuse across domain-specific routers
without circular imports.
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple

from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.logging_config import get_app_logger

logger = get_app_logger("api.helpers")


# ── Normalization helpers ─────────────────────────────────────────────


def normalize_monitoring_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    ts = value
    if not isinstance(ts, datetime):
        try:
            ts = datetime.fromisoformat(str(ts))
        except ValueError:
            return None
    if ts.tzinfo is not None:
        ts = ts.astimezone(timezone.utc).replace(tzinfo=None)
    return ts


def normalize_weapon_key(weapon_name: Any) -> str:
    """Normalize weapon names for grouping/filtering (e.g. WS_MP40 -> mp40)."""
    if weapon_name is None:
        return "unknown"
    key = str(weapon_name).strip().lower()
    if key.startswith("ws_"):
        key = key[3:]
    elif key.startswith("ws "):
        key = key[3:]
    return key.replace("_", "").replace(" ", "")


def clean_weapon_name(weapon_name: Any) -> str:
    """Format weapon names for UI display (e.g. WS_GRENADE -> Grenade)."""
    if weapon_name is None:
        return "Unknown"
    clean_name = str(weapon_name).strip()
    lower_name = clean_name.lower()
    if lower_name.startswith("ws_"):
        clean_name = clean_name[3:]
    elif lower_name.startswith("ws "):
        clean_name = clean_name[3:]
    return clean_name.replace("_", " ").title()


def normalize_map_name(map_name: Any) -> str:
    """Normalize map names for stable grouping/display in trend responses."""
    if map_name is None:
        return ""

    normalized = str(map_name).strip()
    if not normalized:
        return ""

    normalized = normalized.replace("\\", "/")
    if "/" in normalized:
        normalized = normalized.rsplit("/", 1)[-1]

    lower = normalized.lower()
    for ext in (".bsp", ".pk3", ".arena"):
        if lower.endswith(ext):
            normalized = normalized[: -len(ext)]
            break

    return normalized.strip()


# ── Achievement system ────────────────────────────────────────────────

KILL_MILESTONES = {
    100: {"emoji": "🎯", "title": "First Blood Century", "color": "#95A5A6"},
    500: {"emoji": "💥", "title": "Killing Machine", "color": "#3498DB"},
    1000: {"emoji": "💀", "title": "Thousand Killer", "color": "#9B59B6"},
    2500: {"emoji": "⚔️", "title": "Elite Warrior", "color": "#E74C3C"},
    5000: {"emoji": "☠️", "title": "Death Incarnate", "color": "#C0392B"},
    10000: {"emoji": "👑", "title": "Legendary Slayer", "color": "#F39C12"},
}

GAME_MILESTONES = {
    10: {"emoji": "🎮", "title": "Getting Started", "color": "#95A5A6"},
    50: {"emoji": "🎯", "title": "Regular Player", "color": "#3498DB"},
    100: {"emoji": "🏆", "title": "Dedicated Gamer", "color": "#9B59B6"},
    250: {"emoji": "⭐", "title": "Community Veteran", "color": "#E74C3C"},
    500: {"emoji": "💎", "title": "Hardcore Legend", "color": "#F39C12"},
    1000: {"emoji": "👑", "title": "Ultimate Champion", "color": "#F1C40F"},
}

KD_MILESTONES = {
    1.0: {"emoji": "⚖️", "title": "Balanced Fighter", "color": "#95A5A6"},
    1.5: {"emoji": "📈", "title": "Above Average", "color": "#3498DB"},
    2.0: {"emoji": "🔥", "title": "Elite Killer", "color": "#E74C3C"},
    3.0: {"emoji": "💯", "title": "Unstoppable", "color": "#F39C12"},
}


def calculate_player_achievements(kills: int, games: int, kd: float) -> dict:
    """
    Calculate which achievements a player has earned based on their stats.

    Returns a dict with:
    - unlocked: list of earned achievements
    - next: the next achievement they're working toward (if any)
    - progress: overall achievement progress percentage
    """
    unlocked = []
    next_achievements = []

    # Check kill milestones
    for threshold, achievement in sorted(KILL_MILESTONES.items()):
        if kills >= threshold:
            unlocked.append(
                {
                    "type": "kills",
                    "threshold": threshold,
                    "emoji": achievement["emoji"],
                    "title": achievement["title"],
                    "color": achievement["color"],
                }
            )
        else:
            next_achievements.append(
                {
                    "type": "kills",
                    "threshold": threshold,
                    "emoji": achievement["emoji"],
                    "title": achievement["title"],
                    "current": kills,
                    "progress": round(kills / threshold * 100, 1),
                }
            )
            break

    # Check game milestones
    for threshold, achievement in sorted(GAME_MILESTONES.items()):
        if games >= threshold:
            unlocked.append(
                {
                    "type": "games",
                    "threshold": threshold,
                    "emoji": achievement["emoji"],
                    "title": achievement["title"],
                    "color": achievement["color"],
                }
            )
        else:
            next_achievements.append(
                {
                    "type": "games",
                    "threshold": threshold,
                    "emoji": achievement["emoji"],
                    "title": achievement["title"],
                    "current": games,
                    "progress": round(games / threshold * 100, 1),
                }
            )
            break

    # Check K/D milestones (only if player has 20+ games)
    if games >= 20:
        for threshold, achievement in sorted(KD_MILESTONES.items()):
            if kd >= threshold:
                unlocked.append(
                    {
                        "type": "kd",
                        "threshold": threshold,
                        "emoji": achievement["emoji"],
                        "title": achievement["title"],
                        "color": achievement["color"],
                    }
                )
            else:
                next_achievements.append(
                    {
                        "type": "kd",
                        "threshold": threshold,
                        "emoji": achievement["emoji"],
                        "title": achievement["title"],
                        "current": round(kd, 2),
                        "progress": round(kd / threshold * 100, 1),
                    }
                )
                break

    # Calculate overall progress
    total_possible = len(KILL_MILESTONES) + len(GAME_MILESTONES) + len(KD_MILESTONES)
    overall_progress = round(len(unlocked) / total_possible * 100, 1)

    return {
        "unlocked": unlocked,
        "next": next_achievements[:2],  # Show up to 2 next achievements
        "total_unlocked": len(unlocked),
        "total_possible": total_possible,
        "progress": overall_progress,
    }


# ── Player resolution ─────────────────────────────────────────────────


async def resolve_player_guid(
    db: DatabaseAdapter,
    identifier: str,
) -> Optional[str]:
    """
    Resolve a player GUID from either a GUID or a player name/alias.
    Returns None if no match is found.
    """
    if not identifier:
        return None

    guid_row = await db.fetch_one(
        "SELECT player_guid FROM player_comprehensive_stats WHERE player_guid = $1 LIMIT 1",
        (identifier,),
    )
    if guid_row and guid_row[0]:
        return guid_row[0]

    name_row = await db.fetch_one(
        "SELECT player_guid FROM player_comprehensive_stats WHERE player_name ILIKE $1 LIMIT 1",
        (identifier,),
    )
    if name_row and name_row[0]:
        return name_row[0]

    try:
        alias_row = await db.fetch_one(
            "SELECT guid FROM player_aliases WHERE alias ILIKE $1 ORDER BY last_seen DESC LIMIT 1",
            (identifier,),
        )
        if alias_row and alias_row[0]:
            return alias_row[0]
    except (OSError, RuntimeError):
        logger.debug("player_aliases lookup failed")

    return None


async def resolve_display_name(
    db: DatabaseAdapter,
    player_guid: str,
    fallback: str,
) -> str:
    """
    Pick a stable display name for a GUID.
    Prefer linked display name; fall back to a known alias.
    """
    # 1) Prefer explicit display_name from player_links (if column exists)
    try:
        link_row = await db.fetch_one(
            "SELECT COALESCE(display_name, player_name) FROM player_links WHERE player_guid = $1 LIMIT 1",
            (player_guid,),
        )
        if link_row and link_row[0]:
            return link_row[0]
    except (OSError, RuntimeError):
        # Fallback if display_name column doesn't exist or table is unavailable
        try:
            link_row = await db.fetch_one(
                "SELECT player_name FROM player_links WHERE player_guid = $1 LIMIT 1",
                (player_guid,),
            )
            if link_row and link_row[0]:
                return link_row[0]
        except (OSError, RuntimeError):
            logger.debug("player_links fallback query failed")

    # 2) Most recent alias, if alias table exists
    try:
        alias_row = await db.fetch_one(
            "SELECT alias FROM player_aliases WHERE guid = $1 ORDER BY last_seen DESC LIMIT 1",
            (player_guid,),
        )
        if alias_row and alias_row[0]:
            return alias_row[0]
    except (OSError, RuntimeError):
        logger.debug("player_aliases query failed")

    # 3) Fallback to most recent name in stats
    name_row = await db.fetch_one(
        "SELECT player_name FROM player_comprehensive_stats WHERE player_guid = $1 ORDER BY round_date DESC LIMIT 1",
        (player_guid,),
    )
    if name_row and name_row[0]:
        return name_row[0]

    return fallback


async def batch_resolve_display_names(
    db: DatabaseAdapter,
    guid_fallback_pairs: List[Tuple[str, str]],
) -> Dict[str, str]:
    """
    Batch-resolve display names for multiple GUIDs in minimal queries.
    Returns a dict mapping guid -> display_name.
    """
    if not guid_fallback_pairs:
        return {}

    guids = [g for g, _ in guid_fallback_pairs]
    fallback_map = {g: f for g, f in guid_fallback_pairs}
    result: Dict[str, str] = {}

    # 1) Batch from player_links
    try:
        placeholders = ", ".join(f"${i+1}" for i in range(len(guids)))
        rows = await db.fetch_all(
            f"SELECT player_guid, COALESCE(display_name, player_name) FROM player_links WHERE player_guid IN ({placeholders})",
            tuple(guids),
        )
        for row in rows:
            if row[1]:
                result[row[0]] = row[1]
    except (OSError, RuntimeError):
        # display_name column may not exist; try without it
        try:
            rows = await db.fetch_all(
                f"SELECT player_guid, player_name FROM player_links WHERE player_guid IN ({placeholders})",
                tuple(guids),
            )
            for row in rows:
                if row[1]:
                    result[row[0]] = row[1]
        except (OSError, RuntimeError):
            pass

    remaining = [g for g in guids if g not in result]
    if not remaining:
        return result

    # 2) Batch from player_aliases
    try:
        placeholders = ", ".join(f"${i+1}" for i in range(len(remaining)))
        rows = await db.fetch_all(
            f"SELECT DISTINCT ON (guid) guid, alias FROM player_aliases WHERE guid IN ({placeholders}) ORDER BY guid, last_seen DESC",
            tuple(remaining),
        )
        for row in rows:
            if row[1]:
                result[row[0]] = row[1]
    except (OSError, RuntimeError):
        pass

    remaining = [g for g in guids if g not in result]
    if not remaining:
        return result

    # 3) Batch from player_comprehensive_stats
    placeholders = ", ".join(f"${i+1}" for i in range(len(remaining)))
    rows = await db.fetch_all(
        f"SELECT DISTINCT ON (player_guid) player_guid, player_name FROM player_comprehensive_stats WHERE player_guid IN ({placeholders}) ORDER BY player_guid, round_date DESC",
        tuple(remaining),
    )
    for row in rows:
        if row[1]:
            result[row[0]] = row[1]

    # Fill any still-missing with fallbacks
    for g in guids:
        if g not in result:
            result[g] = fallback_map.get(g, "Unknown")

    return result


async def resolve_alias_guid_map(
    db: DatabaseAdapter,
    names: List[str],
) -> Dict[str, str]:
    """
    Resolve a map of lowercase alias -> guid for a list of player names.
    Uses player_aliases when available; returns empty dict on failure.
    """
    if not names:
        return {}

    lowered = list({n.lower() for n in names if n})
    if not lowered:
        return {}

    try:
        rows = await db.fetch_all(
            """
            SELECT DISTINCT ON (alias) alias, guid
            FROM player_aliases
            WHERE LOWER(alias) = ANY($1)
            ORDER BY alias, last_seen DESC
            """,
            (lowered,),
        )
        return {row[0].lower(): row[1] for row in rows if row and row[0]}
    except Exception as e:
        logger.warning("resolve_alias_guid_map failed: %s", e)
        return {}


async def resolve_name_guid_map(
    db: DatabaseAdapter,
    names: List[str],
) -> Dict[str, str]:
    """
    Resolve a map of lowercase name -> guid using player_comprehensive_stats.
    Matches against both player_name and clean_name; prefers most recent rows.
    """
    if not names:
        return {}

    lowered = list({n.lower() for n in names if n})
    if not lowered:
        return {}

    try:
        rows = await db.fetch_all(
            """
            SELECT player_guid, player_name, clean_name
            FROM player_comprehensive_stats
            WHERE LOWER(player_name) = ANY($1)
               OR LOWER(clean_name) = ANY($1)
            ORDER BY round_date DESC
            """,
            (lowered,),
        )
        mapping: Dict[str, str] = {}
        for guid, player_name, clean_name in rows:
            if player_name:
                key = player_name.lower()
                if key in lowered and key not in mapping:
                    mapping[key] = guid
            if clean_name:
                key = clean_name.lower()
                if key in lowered and key not in mapping:
                    mapping[key] = guid
        return mapping
    except Exception as e:
        logger.warning("resolve_name_guid_map failed: %s", e)
        return {}
