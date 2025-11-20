"""
Title/Badge System - Unlockable player titles and badges

Players unlock titles by achieving specific milestones and can display
them alongside their stats.
"""

import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class TitleSystem:
    """Manages player titles and badges"""

    # Define available titles with unlock requirements
    TITLES = {
        # Combat titles
        'sharpshooter': {
            'title': '🎯 Sharpshooter',
            'requirement': 'headshot_rate',
            'threshold': 35,
            'description': '35%+ headshot rate over 50+ games'
        },
        'fragger': {
            'title': '💀 Fragger',
            'requirement': 'kd_ratio',
            'threshold': 2.0,
            'description': '2.0+ K/D ratio over 50+ games'
        },
        'god_mode': {
            'title': '⚡ God Mode',
            'requirement': 'kd_ratio',
            'threshold': 3.0,
            'description': '3.0+ K/D ratio over 100+ games'
        },
        'deadeye': {
            'title': '👁️ Deadeye',
            'requirement': 'headshot_rate',
            'threshold': 50,
            'description': '50%+ headshot rate over 100+ games'
        },

        # Support titles
        'medic': {
            'title': '⚕️ Medic',
            'requirement': 'revives_per_game',
            'threshold': 3.0,
            'description': '3+ revives per game over 50+ games'
        },
        'guardian': {
            'title': '🛡️ Guardian',
            'requirement': 'revives_per_game',
            'threshold': 5.0,
            'description': '5+ revives per game over 100+ games'
        },

        # Objective titles
        'objective_runner': {
            'title': '🎖️ Objective Runner',
            'requirement': 'objectives_per_game',
            'threshold': 2.0,
            'description': '2+ objectives per game over 50+ games'
        },
        'mission_master': {
            'title': '⭐ Mission Master',
            'requirement': 'objectives_per_game',
            'threshold': 3.5,
            'description': '3.5+ objectives per game over 100+ games'
        },

        # Milestone titles
        'veteran': {
            'title': '🎖️ Veteran',
            'requirement': 'games_played',
            'threshold': 100,
            'description': 'Play 100 games'
        },
        'legend': {
            'title': '👑 Legend',
            'requirement': 'games_played',
            'threshold': 500,
            'description': 'Play 500 games'
        },
        'immortal': {
            'title': '🌟 Immortal',
            'requirement': 'games_played',
            'threshold': 1000,
            'description': 'Play 1000 games'
        },

        # Kill milestones
        'killer': {
            'title': '🔪 Killer',
            'requirement': 'total_kills',
            'threshold': 1000,
            'description': 'Get 1,000 total kills'
        },
        'slayer': {
            'title': '⚔️ Slayer',
            'requirement': 'total_kills',
            'threshold': 5000,
            'description': 'Get 5,000 total kills'
        },
        'destroyer': {
            'title': '💥 Destroyer',
            'requirement': 'total_kills',
            'threshold': 10000,
            'description': 'Get 10,000 total kills'
        },

        # Special titles
        'mvp': {
            'title': '🏆 MVP',
            'requirement': 'mvp_wins',
            'threshold': 1,
            'description': 'Win an MVP vote'
        },
        'champion': {
            'title': '👑 Champion',
            'requirement': 'mvp_wins',
            'threshold': 5,
            'description': 'Win 5 MVP votes'
        },
        'knife_master': {
            'title': '🗡️ Knife Master',
            'requirement': 'knife_kill_rate',
            'threshold': 5.0,
            'description': '5%+ knife kills over 50+ games'
        },
        'demolition': {
            'title': '💣 Demolition Expert',
            'requirement': 'grenades_per_game',
            'threshold': 3.0,
            'description': '3+ grenade kills per game over 50+ games'
        }
    }

    def __init__(self, db_adapter):
        """
        Initialize title system

        Args:
            db_adapter: Database adapter
        """
        self.db_adapter = db_adapter
        logger.info("🎖️ TitleSystem initialized")

    async def create_titles_table(self):
        """Create the player titles table if it doesn't exist"""
        try:
            create_table_query = """
                CREATE TABLE IF NOT EXISTS player_titles (
                    id SERIAL PRIMARY KEY,
                    player_guid TEXT NOT NULL,
                    title_id TEXT NOT NULL,
                    unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_equipped BOOLEAN DEFAULT FALSE,
                    UNIQUE(player_guid, title_id)
                )
            """
            await self.db_adapter.execute(create_table_query)

            # Create index for faster queries
            await self.db_adapter.execute(
                "CREATE INDEX IF NOT EXISTS idx_player_titles_guid ON player_titles(player_guid)"
            )
            logger.info("✅ Player titles table ready")
        except Exception as e:
            logger.error(f"❌ Failed to create player titles table: {e}")

    async def check_and_unlock_titles(self, player_guid: str) -> List[str]:
        """
        Check player stats and unlock any eligible titles

        Args:
            player_guid: Player GUID

        Returns:
            List of newly unlocked title IDs
        """
        try:
            # Get player stats
            stats = await self._get_player_stats(player_guid)
            if not stats:
                return []

            # Get MVP wins if available
            mvp_wins = 0
            try:
                mvp_query = """
                    SELECT COUNT(*) FROM mvp_votes m1
                    WHERE m1.player_guid = ?
                    AND m1.vote_count = (
                        SELECT MAX(m2.vote_count)
                        FROM mvp_votes m2
                        WHERE m2.session_id = m1.session_id
                    )
                """
                result = await self.db_adapter.fetch_one(mvp_query, (player_guid,))
                mvp_wins = result[0] if result else 0
            except Exception:
                pass

            # Get currently unlocked titles
            unlocked_query = "SELECT title_id FROM player_titles WHERE player_guid = ?"
            unlocked_rows = await self.db_adapter.fetch_all(unlocked_query, (player_guid,))
            unlocked_titles = {row[0] for row in unlocked_rows}

            # Check each title for eligibility
            newly_unlocked = []
            for title_id, title_info in self.TITLES.items():
                # Skip if already unlocked
                if title_id in unlocked_titles:
                    continue

                # Check requirement
                requirement = title_info['requirement']
                threshold = title_info['threshold']

                if self._meets_requirement(stats, requirement, threshold, mvp_wins):
                    # Unlock title
                    await self._unlock_title(player_guid, title_id)
                    newly_unlocked.append(title_id)
                    logger.info(f"🎖️ Unlocked '{title_info['title']}' for {player_guid}")

            return newly_unlocked

        except Exception as e:
            logger.error(f"❌ Error checking titles for {player_guid}: {e}")
            return []

    def _meets_requirement(self, stats: Dict, requirement: str, threshold: float, mvp_wins: int) -> bool:
        """Check if player meets a specific requirement"""
        games_played = stats.get('games_played', 0)

        # Most titles require minimum games played
        min_games = 50 if threshold < 3.0 or 'per_game' in requirement else 100

        if requirement == 'games_played':
            return games_played >= threshold

        if requirement == 'total_kills':
            return stats.get('total_kills', 0) >= threshold

        if requirement == 'mvp_wins':
            return mvp_wins >= threshold

        # Require minimum games for rate-based requirements
        if games_played < min_games:
            return False

        if requirement == 'kd_ratio':
            return stats.get('kd_ratio', 0) >= threshold

        if requirement == 'headshot_rate':
            return stats.get('headshot_rate', 0) >= threshold

        if requirement == 'revives_per_game':
            return stats.get('revives_per_game', 0) >= threshold

        if requirement == 'objectives_per_game':
            return stats.get('objectives_per_game', 0) >= threshold

        if requirement == 'knife_kill_rate':
            return stats.get('knife_kill_rate', 0) >= threshold

        if requirement == 'grenades_per_game':
            return stats.get('grenades_per_game', 0) >= threshold

        return False

    async def _get_player_stats(self, player_guid: str) -> Optional[Dict]:
        """Get comprehensive player stats"""
        try:
            query = """
                SELECT
                    COUNT(DISTINCT p.round_id) as games_played,
                    SUM(p.kills) as total_kills,
                    SUM(p.deaths) as total_deaths,
                    SUM(p.headshot_kills) as total_headshots,
                    SUM(p.revives) as total_revives,
                    SUM(p.objectives) as total_objectives,
                    SUM(p.knife_kills) as total_knife_kills,
                    SUM(p.grenades) as total_grenades
                FROM player_comprehensive_stats p
                JOIN rounds r ON p.round_id = r.id
                WHERE p.player_guid = ?
                    AND r.round_number IN (1, 2)
                    AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
            """
            row = await self.db_adapter.fetch_one(query, (player_guid,))

            if not row or row[0] == 0:
                return None

            games = row[0]
            total_kills = row[1] or 0
            total_deaths = row[2] or 0

            return {
                'games_played': games,
                'total_kills': total_kills,
                'total_deaths': total_deaths,
                'kd_ratio': total_kills / total_deaths if total_deaths > 0 else 0,
                'headshot_rate': (row[3] / total_kills * 100) if total_kills > 0 else 0,
                'revives_per_game': row[4] / games if games > 0 else 0,
                'objectives_per_game': row[5] / games if games > 0 else 0,
                'knife_kill_rate': (row[6] / total_kills * 100) if total_kills > 0 else 0,
                'grenades_per_game': row[7] / games if games > 0 else 0
            }

        except Exception as e:
            logger.error(f"Error getting player stats: {e}")
            return None

    async def _unlock_title(self, player_guid: str, title_id: str):
        """Unlock a title for a player"""
        try:
            query = """
                INSERT INTO player_titles (player_guid, title_id, unlocked_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(player_guid, title_id) DO NOTHING
            """
            await self.db_adapter.execute(query, (player_guid, title_id))
        except Exception as e:
            logger.error(f"Error unlocking title: {e}")

    async def get_unlocked_titles(self, player_guid: str) -> List[Dict]:
        """Get all unlocked titles for a player"""
        try:
            query = """
                SELECT title_id, unlocked_at, is_equipped
                FROM player_titles
                WHERE player_guid = ?
                ORDER BY unlocked_at DESC
            """
            rows = await self.db_adapter.fetch_all(query, (player_guid,))

            titles = []
            for row in rows:
                title_id = row[0]
                if title_id in self.TITLES:
                    titles.append({
                        'id': title_id,
                        'title': self.TITLES[title_id]['title'],
                        'description': self.TITLES[title_id]['description'],
                        'unlocked_at': row[1],
                        'is_equipped': row[2]
                    })

            return titles

        except Exception as e:
            logger.error(f"Error getting unlocked titles: {e}")
            return []

    async def equip_title(self, player_guid: str, title_id: str) -> bool:
        """
        Equip a title for a player

        Args:
            player_guid: Player GUID
            title_id: Title ID to equip

        Returns:
            True if successful
        """
        try:
            # First, unequip all titles
            await self.db_adapter.execute(
                "UPDATE player_titles SET is_equipped = FALSE WHERE player_guid = ?",
                (player_guid,)
            )

            # Then equip the selected title
            await self.db_adapter.execute(
                "UPDATE player_titles SET is_equipped = TRUE WHERE player_guid = ? AND title_id = ?",
                (player_guid, title_id)
            )

            logger.info(f"✅ Equipped title '{title_id}' for {player_guid}")
            return True

        except Exception as e:
            logger.error(f"Error equipping title: {e}")
            return False

    async def get_equipped_title(self, player_guid: str) -> Optional[str]:
        """Get the currently equipped title for a player"""
        try:
            query = """
                SELECT title_id
                FROM player_titles
                WHERE player_guid = ? AND is_equipped = TRUE
                LIMIT 1
            """
            row = await self.db_adapter.fetch_one(query, (player_guid,))

            if row and row[0] in self.TITLES:
                return self.TITLES[row[0]]['title']

            return None

        except Exception as e:
            logger.error(f"Error getting equipped title: {e}")
            return None


async def create_title_system(db_adapter) -> TitleSystem:
    """
    Factory function to create TitleSystem

    Args:
        db_adapter: Database adapter

    Returns:
        TitleSystem instance
    """
    system = TitleSystem(db_adapter)
    await system.create_titles_table()
    return system
