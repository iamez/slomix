"""
Rare Achievements Service - Detects and announces exceptional performances

This service monitors game rounds and automatically posts alerts when players
achieve rare or exceptional feats during matches.
"""

import logging
from typing import List, Dict, Optional, Tuple
import discord
from datetime import datetime

logger = logging.getLogger(__name__)


class RareAchievementsService:
    """Service for detecting and announcing rare achievements"""

    def __init__(self, db_adapter, channel_id: int = None):
        """
        Initialize the rare achievements service

        Args:
            db_adapter: Database adapter for queries
            channel_id: Discord channel ID for posting alerts
        """
        self.db_adapter = db_adapter
        self.channel_id = channel_id
        logger.info("🏆 RareAchievementsService initialized")

    async def check_and_announce(self, bot, round_id: int, round_num: int, player_stats: List[Dict]) -> List[str]:
        """
        Check for rare achievements in a round and post announcements

        Args:
            bot: Discord bot instance
            round_id: Round ID from database
            round_num: Round number (1 or 2)
            player_stats: List of player stat dictionaries

        Returns:
            List of achievement messages that were detected
        """
        if not self.channel_id:
            return []

        channel = bot.get_channel(self.channel_id)
        if not channel:
            logger.warning(f"⚠️ Rare achievements channel {self.channel_id} not found")
            return []

        achievements = []

        # Check each player's performance
        for player in player_stats:
            player_achievements = await self._check_player_achievements(player, round_id, round_num)
            achievements.extend(player_achievements)

        # Post achievements to Discord
        for achievement in achievements:
            try:
                embed = self._create_achievement_embed(achievement)
                await channel.send(embed=embed)
                logger.info(f"🎉 Posted rare achievement: {achievement['type']} by {achievement['player']}")
            except Exception as e:
                logger.error(f"❌ Failed to post achievement: {e}")

        return achievements

    async def _check_player_achievements(self, player: Dict, round_id: int, round_num: int) -> List[Dict]:
        """
        Check if a player achieved any rare feats in this round

        Args:
            player: Player stats dictionary
            round_id: Round ID
            round_num: Round number

        Returns:
            List of achievement dictionaries
        """
        achievements = []
        player_name = player.get('name', 'Unknown')

        # 1. Pentakill (5+ kills in short time / multikill stat)
        # Note: We use 'multikills' field which tracks multi-kill events
        # For now, we'll use high kill counts as a proxy
        kills = player.get('kills', 0)
        deaths = player.get('deaths', 0)
        kd = player.get('kd_ratio', 0)
        headshots = player.get('headshots', 0)
        accuracy = player.get('accuracy', 0)
        damage = player.get('damage_given', 0)

        # Exceptional kill count (relative to typical performance)
        if kills >= 40:
            achievements.append({
                'type': '🔥 Absolute Domination',
                'player': player_name,
                'description': f'{kills} kills in a single round!',
                'stats': player,
                'rarity': 'legendary'
            })
        elif kills >= 30:
            achievements.append({
                'type': '💀 Killing Spree',
                'player': player_name,
                'description': f'{kills} kills - unstoppable!',
                'stats': player,
                'rarity': 'epic'
            })

        # Perfect or near-perfect accuracy on significant shots
        if accuracy >= 95 and kills >= 10:
            achievements.append({
                'type': '🎯 Deadeye',
                'player': player_name,
                'description': f'{accuracy:.1f}% accuracy with {kills} kills!',
                'stats': player,
                'rarity': 'legendary'
            })
        elif accuracy >= 85 and kills >= 15:
            achievements.append({
                'type': '🎯 Sharpshooter',
                'player': player_name,
                'description': f'{accuracy:.1f}% accuracy with {kills} kills',
                'stats': player,
                'rarity': 'epic'
            })

        # Extreme headshot rate
        if kills >= 15:
            hs_rate = (headshots / kills * 100) if kills > 0 else 0
            if hs_rate >= 80:
                achievements.append({
                    'type': '💥 Headshot Master',
                    'player': player_name,
                    'description': f'{headshots}/{kills} headshots ({hs_rate:.1f}%)',
                    'stats': player,
                    'rarity': 'legendary'
                })
            elif hs_rate >= 60:
                achievements.append({
                    'type': '🎯 Headshot Artist',
                    'player': player_name,
                    'description': f'{headshots}/{kills} headshots ({hs_rate:.1f}%)',
                    'stats': player,
                    'rarity': 'epic'
                })

        # Flawless victory (no deaths or very few deaths with high kills)
        if kills >= 20 and deaths == 0:
            achievements.append({
                'type': '👑 Flawless Victory',
                'player': player_name,
                'description': f'{kills} kills with ZERO deaths!',
                'stats': player,
                'rarity': 'legendary'
            })
        elif kills >= 15 and deaths <= 1:
            achievements.append({
                'type': '⭐ Near Flawless',
                'player': player_name,
                'description': f'{kills}-{deaths} K/D ratio',
                'stats': player,
                'rarity': 'epic'
            })

        # Extreme K/D ratio
        if kd >= 10 and kills >= 20:
            achievements.append({
                'type': '🌟 God Mode',
                'player': player_name,
                'description': f'{kd:.1f} K/D ratio ({kills}-{deaths})',
                'stats': player,
                'rarity': 'legendary'
            })
        elif kd >= 5 and kills >= 15:
            achievements.append({
                'type': '🔥 On Fire',
                'player': player_name,
                'description': f'{kd:.1f} K/D ratio ({kills}-{deaths})',
                'stats': player,
                'rarity': 'epic'
            })

        # Massive damage dealer
        if damage >= 8000:
            achievements.append({
                'type': '💥 Destruction Incarnate',
                'player': player_name,
                'description': f'{damage:,} damage dealt!',
                'stats': player,
                'rarity': 'legendary'
            })
        elif damage >= 6000:
            achievements.append({
                'type': '⚡ Heavy Hitter',
                'player': player_name,
                'description': f'{damage:,} damage dealt',
                'stats': player,
                'rarity': 'epic'
            })

        # Support hero (revives)
        revives = player.get('revives', 0)
        if revives >= 20:
            achievements.append({
                'type': '⚕️ Guardian Angel',
                'player': player_name,
                'description': f'{revives} revives - true hero!',
                'stats': player,
                'rarity': 'epic'
            })

        # Check for personal records
        if achievements:  # Only check if player did something noteworthy
            records = await self._check_personal_records(player_name, player)
            achievements.extend(records)

        return achievements

    async def _check_personal_records(self, player_name: str, current_stats: Dict) -> List[Dict]:
        """
        Check if player broke any of their personal records

        Args:
            player_name: Player's name
            current_stats: Current round stats

        Returns:
            List of record-breaking achievements
        """
        achievements = []

        try:
            # Get player GUID
            player_guid_row = await self.db_adapter.fetch_one(
                "SELECT player_guid FROM player_comprehensive_stats WHERE player_name = ? LIMIT 1",
                (player_name,)
            )

            if not player_guid_row:
                return achievements

            player_guid = player_guid_row[0]

            # Get historical max stats
            historical = await self.db_adapter.fetch_one(
                """
                SELECT
                    MAX(kills) as max_kills,
                    MAX(damage_given) as max_damage,
                    MAX(headshots) as max_headshots
                FROM player_comprehensive_stats p
                JOIN rounds r ON p.round_id = r.id
                WHERE p.player_guid = ?
                    AND r.round_number IN (1, 2)
                """,
                (player_guid,)
            )

            if historical:
                max_kills_ever = historical[0] or 0
                max_damage_ever = historical[1] or 0
                max_hs_ever = historical[2] or 0

                current_kills = current_stats.get('kills', 0)
                current_damage = current_stats.get('damage_given', 0)
                current_hs = current_stats.get('headshots', 0)

                # New personal record for kills
                if current_kills > max_kills_ever and current_kills >= 25:
                    achievements.append({
                        'type': '📈 New Personal Record',
                        'player': player_name,
                        'description': f'Career-best {current_kills} kills (previous: {max_kills_ever})',
                        'stats': current_stats,
                        'rarity': 'epic'
                    })

                # New personal record for damage
                if current_damage > max_damage_ever and current_damage >= 4000:
                    achievements.append({
                        'type': '📈 Damage Record',
                        'player': player_name,
                        'description': f'Career-best {current_damage:,} damage (previous: {max_damage_ever:,})',
                        'stats': current_stats,
                        'rarity': 'epic'
                    })

        except Exception as e:
            logger.error(f"❌ Error checking personal records: {e}")

        return achievements

    def _create_achievement_embed(self, achievement: Dict) -> discord.Embed:
        """
        Create a Discord embed for an achievement

        Args:
            achievement: Achievement dictionary

        Returns:
            Discord embed
        """
        rarity = achievement.get('rarity', 'common')

        # Color based on rarity
        colors = {
            'legendary': 0xFFD700,  # Gold
            'epic': 0x9B59B6,       # Purple
            'rare': 0x3498DB,       # Blue
            'common': 0x95A5A6      # Gray
        }
        color = colors.get(rarity, 0x95A5A6)

        # Emoji based on rarity
        rarity_emoji = {
            'legendary': '⭐⭐⭐',
            'epic': '⭐⭐',
            'rare': '⭐',
            'common': ''
        }

        embed = discord.Embed(
            title=f"{achievement['type']} {rarity_emoji.get(rarity, '')}",
            description=f"**{achievement['player']}** {achievement['description']}",
            color=color,
            timestamp=datetime.utcnow()
        )

        # Add detailed stats if available
        stats = achievement.get('stats', {})
        if stats:
            stats_text = []
            if stats.get('kills'):
                stats_text.append(f"Kills: {stats['kills']}")
            if stats.get('deaths') is not None:
                stats_text.append(f"Deaths: {stats['deaths']}")
            if stats.get('kd_ratio'):
                stats_text.append(f"K/D: {stats['kd_ratio']:.2f}")
            if stats.get('damage_given'):
                stats_text.append(f"Damage: {stats['damage_given']:,}")

            if stats_text:
                embed.add_field(
                    name="📊 Stats",
                    value=" • ".join(stats_text),
                    inline=False
                )

        embed.set_footer(text="Rare Achievement Unlocked! 🎉")

        return embed


async def create_rare_achievements_service(db_adapter, channel_id: int = None) -> RareAchievementsService:
    """
    Factory function to create a RareAchievementsService instance

    Args:
        db_adapter: Database adapter
        channel_id: Discord channel ID for posting alerts

    Returns:
        RareAchievementsService instance
    """
    return RareAchievementsService(db_adapter, channel_id)
