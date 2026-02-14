"""
Achievement System - Player Milestone Tracking
==============================================
Extracted from: bot/ultimate_bot.py (Lines 134-357)
Extraction Date: 2025-11-01
Part of: Option B Refactoring (Extraction #3)

Tracks and notifies players when they hit major milestones in kills, games, and K/D ratio.
Sends beautiful Discord embed notifications with @mentions.

Milestone Categories:
- Kill milestones: 100, 500, 1K, 2.5K, 5K, 10K
- Game milestones: 10, 50, 100, 250, 500, 1K
- K/D milestones: 1.0, 1.5, 2.0, 3.0 (requires 20+ games)
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Set
import discord
from bot.services.player_display_name_service import PlayerDisplayNameService
from bot.core.database_adapter import ensure_player_name_alias

logger = logging.getLogger(__name__)


class AchievementSystem:
    """
    Track and notify players when they hit major milestones.

    This system monitors player progress and sends celebratory notifications
    to Discord when they reach significant achievement thresholds.

    Milestones Tracked:
    - Kill milestones: 100, 500, 1000, 2500, 5000, 10000
    - Game milestones: 10, 50, 100, 250, 500, 1000
    - K/D milestones: 1.0, 1.5, 2.0, 3.0 (requires 20+ games minimum)

    Features:
    - @mention notifications in stats channel
    - Prevents duplicate notifications (per session)
    - Beautiful embed formatting with color coding
    - Automatic Discord user linking

    Usage:
        achievements = AchievementSystem(bot)
        new_unlocks = await achievements.check_player_achievements(
            player_guid="ABC123...",
            channel=stats_channel
        )

    Attributes:
        bot: Discord bot instance
        notified_achievements (set): Tracks already-notified achievements this session
        KILL_MILESTONES (dict): Kill count thresholds and their achievements
        GAME_MILESTONES (dict): Games played thresholds and their achievements
        KD_MILESTONES (dict): K/D ratio thresholds and their achievements
    """

    # Define all achievement thresholds
    KILL_MILESTONES = {
        100: {"emoji": "🎯", "title": "First Blood Century", "color": 0x95A5A6},
        500: {"emoji": "💥", "title": "Killing Machine", "color": 0x3498DB},
        1000: {"emoji": "💀", "title": "Thousand Killer", "color": 0x9B59B6},
        2500: {"emoji": "⚔️", "title": "Elite Warrior", "color": 0xE74C3C},
        5000: {"emoji": "☠️", "title": "Death Incarnate", "color": 0xC0392B},
        10000: {"emoji": "👑", "title": "Legendary Slayer", "color": 0xF39C12},
    }

    GAME_MILESTONES = {
        10: {"emoji": "🎮", "title": "Getting Started", "color": 0x95A5A6},
        50: {"emoji": "🎯", "title": "Regular Player", "color": 0x3498DB},
        100: {"emoji": "🏆", "title": "Dedicated Gamer", "color": 0x9B59B6},
        250: {"emoji": "⭐", "title": "Community Veteran", "color": 0xE74C3C},
        500: {"emoji": "💎", "title": "Hardcore Legend", "color": 0xF39C12},
        1000: {"emoji": "👑", "title": "Ultimate Champion", "color": 0xF1C40F},
    }

    KD_MILESTONES = {
        1.0: {"emoji": "⚖️", "title": "Balanced Fighter", "color": 0x95A5A6},
        1.5: {"emoji": "📈", "title": "Above Average", "color": 0x3498DB},
        2.0: {"emoji": "🔥", "title": "Elite Killer", "color": 0xE74C3C},
        3.0: {"emoji": "💯", "title": "Unstoppable", "color": 0xF39C12},
    }

    def __init__(self, bot):
        """
        Initialize the AchievementSystem.

        Args:
            bot: Discord bot instance (used for database access and user lookups)

        Note:
            notified_achievements is cleared on bot restart. This prevents
            spam but means achievements could be re-notified after restart.
        """
        self.bot = bot
        self.notified_achievements: Set[str] = set()  # Track what we've already notified
        logger.info("🏆 AchievementSystem initialized")

    async def check_player_achievements(
        self, 
        player_guid: str, 
        channel: Optional[discord.TextChannel] = None
    ) -> List[Dict[str, Any]]:
        """
        Check if player hit any milestones and notify if needed.

        This method queries the player's lifetime stats and checks them against
        all achievement thresholds. New achievements are added to the notification
        tracking set and sent to Discord if a channel is provided.

        Args:
            player_guid: Player's GUID to check (ET:Legacy GUID)
            channel: Discord channel to send notifications (optional)
                    If None, achievements are detected but not announced

        Returns:
            List of newly unlocked achievements (dicts with type, threshold, achievement data)

        Example:
            >>> achievements = AchievementSystem(bot)
            >>> new = await achievements.check_player_achievements(
            ...     "ABC123DEF456...",
            ...     stats_channel
            ... )
            >>> print(f"Unlocked {len(new)} achievements!")
        """
        try:
            new_achievements = []

            try:
                await ensure_player_name_alias(self.bot.db_adapter, self.bot.config)
            except (OSError, RuntimeError, ValueError):
                pass  # Alias table may not exist

            stats = await self.bot.db_adapter.fetch_one(
                """
                SELECT
                    SUM(p.kills) as total_kills,
                    SUM(p.deaths) as total_deaths,
                    COUNT(DISTINCT p.round_id) as total_games,
                    CASE
                        WHEN SUM(p.deaths) > 0
                        THEN CAST(SUM(p.kills) AS REAL) / SUM(p.deaths)
                        ELSE SUM(p.kills)
                    END as overall_kd
                FROM player_comprehensive_stats p
                JOIN rounds r ON p.round_id = r.id
                WHERE p.player_guid = ?
                  AND r.round_number IN (1, 2)
                  AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
                """,
                (player_guid,),
            )

            if not stats or stats[0] is None:
                return []

            kills, deaths, games, kd_ratio = stats

            # Use proper name resolution service (works for all players)
            display_name_service = PlayerDisplayNameService(self.bot.db_adapter)
            player_name = await display_name_service.get_display_name(player_guid)

            # Still need discord_id for @mention in achievement embed
            link = await self.bot.db_adapter.fetch_one(
                "SELECT discord_id FROM player_links WHERE player_guid = ?",
                (player_guid,),
            )
            discord_id = link[0] if link else None

            # Check kill milestones
            for threshold, achievement in self.KILL_MILESTONES.items():
                achievement_id = f"{player_guid}_kills_{threshold}"
                if (
                    kills >= threshold
                    and achievement_id not in self.notified_achievements
                ):
                    new_achievements.append(
                        {
                            "type": "kills",
                            "threshold": threshold,
                            "achievement": achievement,
                            "player_name": player_name,
                            "discord_id": discord_id,
                            "value": kills,
                        }
                    )
                    self.notified_achievements.add(achievement_id)

            # Check game milestones
            for threshold, achievement in self.GAME_MILESTONES.items():
                achievement_id = f"{player_guid}_games_{threshold}"
                if (
                    games >= threshold
                    and achievement_id not in self.notified_achievements
                ):
                    new_achievements.append(
                        {
                            "type": "games",
                            "threshold": threshold,
                            "achievement": achievement,
                            "player_name": player_name,
                            "discord_id": discord_id,
                            "value": games,
                        }
                    )
                    self.notified_achievements.add(achievement_id)

            # Check K/D milestones (only if player has 20+ games)
            if games >= 20:
                for threshold, achievement in self.KD_MILESTONES.items():
                    achievement_id = f"{player_guid}_kd_{threshold}"
                    if (
                        kd_ratio >= threshold
                        and achievement_id not in self.notified_achievements
                    ):
                        new_achievements.append(
                            {
                                "type": "kd",
                                "threshold": threshold,
                                "achievement": achievement,
                                "player_name": player_name,
                                "discord_id": discord_id,
                                "value": kd_ratio,
                            }
                        )
                        self.notified_achievements.add(achievement_id)

            # Send notifications for new achievements
            if new_achievements and channel:
                for ach in new_achievements:
                    await self._send_achievement_notification(ach, channel)

            return new_achievements

        except Exception as e:
            logger.error(
                f"Error checking achievements for {player_guid}: {e}",
                exc_info=True,
            )
            return []

    async def _send_achievement_notification(
        self, 
        achievement: Dict[str, Any], 
        channel: discord.TextChannel
    ) -> None:
        """
        Send a beautiful achievement notification to Discord.

        Creates a rich embed with color coding, emojis, and @mentions (if player is linked).

        Args:
            achievement: Achievement data dict with keys:
                        type, threshold, achievement, player_name, discord_id, value
            channel: Discord text channel to send the notification to

        Note:
            Errors are logged but don't raise to avoid breaking the achievement check flow.
        """
        try:
            ach_data = achievement["achievement"]

            # Build description with @mention if available
            if achievement["discord_id"]:
                user = self.bot.get_user(int(achievement["discord_id"]))
                mention = user.mention if user else achievement["player_name"]
            else:
                mention = achievement["player_name"]

            # Format value based on type
            if achievement["type"] == "kills":
                value_text = f"{achievement['value']:,} kills"
            elif achievement["type"] == "games":
                value_text = f"{achievement['value']:,} games played"
            elif achievement["type"] == "kd":
                value_text = f"{achievement['value']:.2f} K/D ratio"
            else:
                value_text = str(achievement["value"])

            embed = discord.Embed(
                title=f"{ach_data['emoji']} Achievement Unlocked!",
                description=f"**{ach_data['title']}**",
                color=ach_data["color"],
                timestamp=datetime.now(),
            )

            embed.add_field(name="Player", value=mention, inline=True)
            embed.add_field(name="Milestone", value=value_text, inline=True)
            embed.set_footer(text="🎮 ET:Legacy Stats Bot")

            await channel.send(embed=embed)
            logger.info(
                f"🏆 Achievement notification sent: {achievement['player_name']} - {ach_data['title']}"
            )

        except Exception as e:
            logger.error(
                f"Error sending achievement notification: {e}", exc_info=True
            )

