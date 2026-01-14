from typing import List, Dict
from datetime import datetime
from bot.services.session_data_service import SessionDataService


class WebsiteSessionDataService(SessionDataService):
    """
    Extended SessionDataService for website-specific functionality.
    Inherits from the bot's SessionDataService to reuse existing logic
    while adding website-specific methods without modifying production code.
    """

    def _team_name(self, team_int) -> str:
        """Convert team integer to name"""
        if team_int == 1:
            return "Allies"
        elif team_int == 2:
            return "Axis"
        return "Unknown"

    def _time_ago(self, date_val) -> str:
        """Convert date to human-readable time ago string"""
        if not date_val:
            return "Unknown"
        try:
            if isinstance(date_val, str):
                dt = datetime.strptime(date_val, "%Y-%m-%d")
            else:
                dt = datetime.combine(date_val, datetime.min.time())
            now = datetime.now()
            diff = now - dt
            days = diff.days
            if days == 0:
                return "Today"
            elif days == 1:
                return "Yesterday"
            elif days < 7:
                return f"{days} days ago"
            elif days < 30:
                weeks = days // 7
                return f"{weeks} week{'s' if weeks > 1 else ''} ago"
            else:
                return dt.strftime("%b %d")
        except Exception:
            return str(date_val)

    async def get_recent_matches(self, limit: int = 10) -> List[Dict]:
        """
        Get recent matches with both teams' players.
        Groups by gaming_session_id and map for a full match view.
        """
        # Get recent rounds with player counts
        query = """
            SELECT
                r.id,
                r.map_name,
                r.round_number,
                r.actual_time,
                r.winner_team,
                r.round_outcome,
                r.round_date,
                r.gaming_session_id,
                r.round_time
            FROM rounds r
            WHERE r.round_number IN (1, 2)
              AND (r.round_status IN ('completed', 'cancelled', 'substitution')
                   OR r.round_status IS NULL)
            ORDER BY
                r.round_date DESC,
                CAST(REPLACE(r.round_time, ':', '') AS INTEGER) DESC
            LIMIT $1
        """
        rows = await self.db_adapter.fetch_all(query, (limit,))

        matches = []
        for row in rows:
            round_id = row[0]
            map_name = row[1]
            round_number = row[2]
            round_date = row[6]

            # Get players for this round grouped by team
            players_query = """
                SELECT DISTINCT player_name, team
                FROM player_comprehensive_stats
                WHERE round_date = $1
                  AND map_name = $2
                  AND round_number = $3
                ORDER BY team, player_name
            """
            player_rows = await self.db_adapter.fetch_all(
                players_query, (round_date, map_name, round_number)
            )

            team1_players = []
            team2_players = []
            for p in player_rows:
                if p[1] == 1:
                    team1_players.append(p[0])
                elif p[1] == 2:
                    team2_players.append(p[0])

            player_count = len(team1_players) + len(team2_players)
            format_tag = self._get_format_tag(player_count)

            matches.append(
                {
                    "id": round_id,
                    "map_name": map_name,
                    "round_number": round_number,
                    "duration": row[3],
                    "winner": self._team_name(row[4]),
                    "outcome": row[5],
                    "date": str(round_date),
                    "time_ago": self._time_ago(round_date),
                    "team1_players": team1_players,
                    "team2_players": team2_players,
                    "player_count": player_count,
                    "format": format_tag,
                }
            )

        return matches

    def _get_format_tag(self, player_count: int) -> str:
        """Determine match format based on player count"""
        if player_count <= 2:
            return "1v1"
        elif player_count <= 6:
            return "3v3"
        elif player_count <= 12:
            return "6v6"
        else:
            return f"{player_count // 2}v{player_count // 2}"

    async def get_session_matches(self, date: str) -> List[Dict]:
        """
        Get all matches for a specific session date.
        """
        query = """
            SELECT id, map_name, round_number, actual_time, winner_team, round_outcome, round_date
            FROM rounds
            WHERE round_date = $1
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
                    "winner": self._team_name(row[4]),
                    "outcome": row[5],
                    "date": row[6],
                }
            )

        return matches
