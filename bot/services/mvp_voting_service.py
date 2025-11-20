"""
MVP Voting Service - Community voting for session MVPs

This service handles post-session MVP voting where players can vote
for the most valuable player of the gaming session.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import discord
from discord import ui

logger = logging.getLogger(__name__)


class MVPVoteView(ui.View):
    """Interactive voting view with buttons for each top player"""

    def __init__(self, candidates: List[Dict], session_id: str, timeout: int = 300):
        """
        Initialize MVP voting view

        Args:
            candidates: List of top player dictionaries
            session_id: Session ID for tracking votes
            timeout: Voting timeout in seconds (default 5 minutes)
        """
        super().__init__(timeout=timeout)
        self.candidates = candidates
        self.session_id = session_id
        self.votes: Dict[str, List[int]] = {c['guid']: [] for c in candidates}
        self.voted_users: set = set()

        # Create buttons for each candidate
        for i, candidate in enumerate(candidates[:5]):  # Max 5 candidates
            button = ui.Button(
                label=f"{candidate['name']} ({candidate['kills']}K/{candidate['deaths']}D)",
                style=discord.ButtonStyle.primary,
                custom_id=f"mvp_{candidate['guid']}_{i}"
            )
            button.callback = self._create_vote_callback(candidate['guid'])
            self.add_item(button)

    def _create_vote_callback(self, player_guid: str):
        """Create a callback function for voting"""
        async def callback(interaction: discord.Interaction):
            user_id = interaction.user.id

            # Check if user already voted
            if user_id in self.voted_users:
                await interaction.response.send_message(
                    "❌ You've already voted!",
                    ephemeral=True
                )
                return

            # Record vote
            self.votes[player_guid].append(user_id)
            self.voted_users.add(user_id)

            # Find player name
            player_name = next(
                (c['name'] for c in self.candidates if c['guid'] == player_guid),
                "Unknown"
            )

            await interaction.response.send_message(
                f"✅ Voted for **{player_name}**!",
                ephemeral=True
            )

            logger.info(f"MVP vote: {interaction.user.name} voted for {player_name}")

        return callback

    def get_results(self) -> List[Tuple[str, str, int]]:
        """
        Get voting results

        Returns:
            List of (player_guid, player_name, vote_count) sorted by votes
        """
        results = []
        for candidate in self.candidates:
            guid = candidate['guid']
            name = candidate['name']
            vote_count = len(self.votes.get(guid, []))
            results.append((guid, name, vote_count))

        return sorted(results, key=lambda x: x[2], reverse=True)


class MVPVotingService:
    """Service for managing MVP voting"""

    def __init__(self, db_adapter):
        """
        Initialize MVP voting service

        Args:
            db_adapter: Database adapter for storing MVP results
        """
        self.db_adapter = db_adapter
        self.active_votes: Dict[str, MVPVoteView] = {}
        logger.info("🏆 MVPVotingService initialized")

    async def create_mvp_table(self):
        """Create the MVP votes table if it doesn't exist"""
        try:
            # Check if using PostgreSQL or SQLite
            create_table_query = """
                CREATE TABLE IF NOT EXISTS mvp_votes (
                    id SERIAL PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    player_guid TEXT NOT NULL,
                    player_name TEXT NOT NULL,
                    vote_count INTEGER NOT NULL,
                    total_votes INTEGER NOT NULL,
                    voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(session_id, player_guid)
                )
            """
            await self.db_adapter.execute(create_table_query)
            logger.info("✅ MVP votes table ready")
        except Exception as e:
            logger.error(f"❌ Failed to create MVP votes table: {e}")

    async def start_voting(
        self,
        bot,
        channel: discord.TextChannel,
        session_id: str,
        top_players: List[Dict]
    ) -> Optional[MVPVoteView]:
        """
        Start MVP voting for a session

        Args:
            bot: Discord bot instance
            channel: Channel to post voting message
            session_id: Session ID
            top_players: List of top player dictionaries with keys: guid, name, kills, deaths

        Returns:
            MVPVoteView instance or None
        """
        try:
            # Create voting view
            view = MVPVoteView(
                candidates=top_players,
                session_id=session_id,
                timeout=300  # 5 minutes
            )

            # Create voting embed
            embed = discord.Embed(
                title="🏆 MVP Voting - Who Was The Session MVP?",
                description="Vote for the player who made the biggest impact this session!",
                color=0xFFD700  # Gold
            )

            # Add candidates
            candidates_text = []
            for i, player in enumerate(top_players[:5], 1):
                kd = player['kills'] / player['deaths'] if player['deaths'] > 0 else player['kills']
                candidates_text.append(
                    f"**{i}. {player['name']}**\n"
                    f"└ {player['kills']}K/{player['deaths']}D • {kd:.2f} K/D"
                )

            embed.add_field(
                name="🎯 Candidates",
                value="\n".join(candidates_text),
                inline=False
            )

            embed.add_field(
                name="⏰ Voting Time",
                value="5 minutes",
                inline=True
            )

            embed.set_footer(text="Click a button below to vote!")
            embed.timestamp = datetime.utcnow()

            # Send voting message
            message = await channel.send(embed=embed, view=view)

            # Store active vote
            self.active_votes[session_id] = view

            # Wait for voting to complete
            await asyncio.sleep(300)  # 5 minutes

            # Get results and announce
            await self._announce_results(channel, message, view, session_id)

            # Remove from active votes
            self.active_votes.pop(session_id, None)

            return view

        except Exception as e:
            logger.error(f"❌ Error starting MVP voting: {e}", exc_info=True)
            return None

    async def _announce_results(
        self,
        channel: discord.TextChannel,
        message: discord.Message,
        view: MVPVoteView,
        session_id: str
    ):
        """
        Announce voting results

        Args:
            channel: Channel to post results
            message: Original voting message
            view: MVPVoteView instance
            session_id: Session ID
        """
        try:
            results = view.get_results()
            total_votes = len(view.voted_users)

            if total_votes == 0:
                await channel.send("❌ No votes were cast for this session.")
                return

            # Determine winner
            winner_guid, winner_name, winner_votes = results[0]

            # Create results embed
            embed = discord.Embed(
                title="🏆 MVP Voting Results",
                description=f"**Session MVP: {winner_name}**",
                color=0xFFD700
            )

            # Add vote breakdown
            results_text = []
            for i, (guid, name, votes) in enumerate(results[:5], 1):
                percentage = (votes / total_votes * 100) if total_votes > 0 else 0
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "📊"
                results_text.append(
                    f"{medal} **{name}**: {votes} votes ({percentage:.1f}%)"
                )

            embed.add_field(
                name="📊 Results",
                value="\n".join(results_text),
                inline=False
            )

            embed.add_field(
                name="🗳️ Total Votes",
                value=str(total_votes),
                inline=True
            )

            embed.set_footer(text=f"Session ID: {session_id}")
            embed.timestamp = datetime.utcnow()

            await channel.send(embed=embed)

            # Store results in database
            await self._store_results(session_id, results, total_votes)

            # Update original message
            try:
                view.stop()
                await message.edit(content="✅ Voting has ended!", view=None)
            except Exception as e:
                logger.error(f"Failed to update voting message: {e}")

        except Exception as e:
            logger.error(f"❌ Error announcing MVP results: {e}", exc_info=True)

    async def _store_results(self, session_id: str, results: List[Tuple], total_votes: int):
        """
        Store voting results in database

        Args:
            session_id: Session ID
            results: List of (player_guid, player_name, vote_count)
            total_votes: Total number of votes
        """
        try:
            for player_guid, player_name, vote_count in results:
                # Use parameterized query
                query = """
                    INSERT INTO mvp_votes (session_id, player_guid, player_name, vote_count, total_votes)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(session_id, player_guid) DO UPDATE SET
                        vote_count = excluded.vote_count,
                        total_votes = excluded.total_votes,
                        voted_at = CURRENT_TIMESTAMP
                """
                await self.db_adapter.execute(
                    query,
                    (session_id, player_guid, player_name, vote_count, total_votes)
                )

            logger.info(f"✅ Stored MVP voting results for session {session_id}")

        except Exception as e:
            logger.error(f"❌ Error storing MVP results: {e}", exc_info=True)

    async def get_mvp_history(self, player_guid: str, limit: int = 10) -> List[Dict]:
        """
        Get MVP voting history for a player

        Args:
            player_guid: Player GUID
            limit: Number of results to return

        Returns:
            List of MVP result dictionaries
        """
        try:
            query = """
                SELECT session_id, player_name, vote_count, total_votes, voted_at
                FROM mvp_votes
                WHERE player_guid = ?
                ORDER BY voted_at DESC
                LIMIT ?
            """
            rows = await self.db_adapter.fetch_all(query, (player_guid, limit))

            results = []
            for row in rows:
                results.append({
                    'session_id': row[0],
                    'player_name': row[1],
                    'vote_count': row[2],
                    'total_votes': row[3],
                    'voted_at': row[4]
                })

            return results

        except Exception as e:
            logger.error(f"❌ Error getting MVP history: {e}")
            return []

    async def get_mvp_wins(self, player_guid: str) -> int:
        """
        Get number of MVP wins for a player

        Args:
            player_guid: Player GUID

        Returns:
            Number of MVP wins
        """
        try:
            # Get sessions where this player had the most votes
            query = """
                SELECT COUNT(*) FROM mvp_votes m1
                WHERE m1.player_guid = ?
                AND m1.vote_count = (
                    SELECT MAX(m2.vote_count)
                    FROM mvp_votes m2
                    WHERE m2.session_id = m1.session_id
                )
            """
            row = await self.db_adapter.fetch_one(query, (player_guid,))
            return row[0] if row else 0

        except Exception as e:
            logger.error(f"❌ Error getting MVP wins: {e}")
            return 0


async def create_mvp_voting_service(db_adapter) -> MVPVotingService:
    """
    Factory function to create MVPVotingService

    Args:
        db_adapter: Database adapter

    Returns:
        MVPVotingService instance
    """
    service = MVPVotingService(db_adapter)
    await service.create_mvp_table()
    return service
