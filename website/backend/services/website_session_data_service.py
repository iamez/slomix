from typing import List, Dict
from bot.services.session_data_service import SessionDataService


class WebsiteSessionDataService(SessionDataService):
    """
    Extended SessionDataService for website-specific functionality.
    Inherits from the bot's SessionDataService to reuse existing logic
    while adding website-specific methods without modifying production code.
    """

    async def get_recent_matches(self, limit: int = 10) -> List[Dict]:
        """
        Get recent matches (rounds) with basic info.
        """
        query = """
            SELECT id, map_name, round_number, actual_time, winner_team, round_outcome, round_date
            FROM rounds
            WHERE round_number IN (1, 2)
              AND (round_status IN ('completed', 'cancelled', 'substitution') OR round_status IS NULL)
            ORDER BY
                round_date DESC,
                CAST(REPLACE(round_time, ':', '') AS INTEGER) DESC
            LIMIT ?
        """
        rows = await self.db_adapter.fetch_all(query, (limit,))

        matches = []
        for row in rows:
            matches.append(
                {
                    "id": row[0],
                    "map_name": row[1],
                    "round_number": row[2],
                    "duration": row[3],
                    "winner": row[4],
                    "outcome": row[5],
                    "date": row[6],
                }
            )

        return matches

    async def get_session_matches(self, date: str) -> List[Dict]:
        """
        Get all matches for a specific session date.
        """
        query = """
            SELECT id, map_name, round_number, actual_time, winner_team, round_outcome, round_date
            FROM rounds
            WHERE round_date = ?
              AND round_number IN (1, 2)
              AND (round_status IN ('completed', 'cancelled', 'substitution') OR round_status IS NULL)
            ORDER BY
                CAST(REPLACE(round_time, ':', '') AS INTEGER) ASC
        """
        rows = await self.db_adapter.fetch_all(query, (date,))

        matches = []
        for row in rows:
            matches.append(
                {
                    "id": row[0],
                    "map_name": row[1],
                    "round_number": row[2],
                    "duration": row[3],
                    "winner": row[4],
                    "outcome": row[5],
                    "date": row[6],
                }
            )

        return matches
