"""
Voice Channel Activity Tracker

Similar to game_server_query.py, this tracks Discord voice channel activity
directly through the Discord API for historical analytics.
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class VoiceMember:
    """Represents a member in a voice channel"""

    discord_id: int
    username: str
    display_name: str
    joined_at: Optional[datetime] = None  # Will be tracked separately


@dataclass
class VoiceChannelStatus:
    """Current voice channel status"""

    active: bool
    member_count: int
    members: List[VoiceMember] = field(default_factory=list)
    channel_id: Optional[int] = None
    channel_name: Optional[str] = None
    error: Optional[str] = None


def get_voice_status_from_db(db_adapter) -> dict:
    """
    Fetch current voice channel status from database.

    The Discord bot populates the 'live_status' table with voice activity.
    This function reads that data for the website.

    Returns:
        {
            "count": 5,
            "members": [{"name": "Player1", "joined_at": "..."}, ...]
        }
    """
    # This will be implemented to read from live_status table
    # which the bot populates
    pass
