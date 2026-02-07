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
        # Get recent rounds with player counts (legal rounds only)
        # Attempt to join Lua score table for axis/allies score.
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
                r.round_time,
                r.match_id,
                l.axis_score,
                l.allies_score
            FROM rounds r
            LEFT JOIN lua_round_teams l
                ON l.match_id = r.match_id
               AND l.round_number = r.round_number
            WHERE r.round_number IN (1, 2)
              AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
            ORDER BY
                r.round_date DESC,
                CAST(REPLACE(r.round_time, ':', '') AS INTEGER) DESC
            LIMIT $1
        """
        try:
            rows = await self.db_adapter.fetch_all(query, (limit,))
        except Exception:
            fallback_query = """
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
                  AND (r.round_status IN ('completed', 'substitution') OR r.round_status IS NULL)
                ORDER BY
                    r.round_date DESC,
                    CAST(REPLACE(r.round_time, ':', '') AS INTEGER) DESC
                LIMIT $1
            """
            rows = await self.db_adapter.fetch_all(fallback_query, (limit,))

        matches = []
        session_round_ids: Dict[int, List[int]] = {}
        for row in rows:
            gaming_session_id = row[7]
            if gaming_session_id is None:
                continue
            session_round_ids.setdefault(gaming_session_id, []).append(row[0])

        team_cache: Dict[int, Dict] = {}
        for row in rows:
            round_id = row[0]
            map_name = row[1]
            round_number = row[2]
            round_date = row[6]
            gaming_session_id = row[7]
            axis_score = row[10] if len(row) > 10 else None
            allies_score = row[11] if len(row) > 11 else None

            # Get players for this round grouped by team
            players_query = """
                SELECT DISTINCT player_name, player_guid, team
                FROM player_comprehensive_stats
                WHERE round_id = $1
                ORDER BY team, player_name
            """
            try:
                player_rows = await self.db_adapter.fetch_all(
                    players_query, (round_id,)
                )
            except Exception:
                fallback_players = """
                    SELECT DISTINCT player_name, player_guid, team
                    FROM player_comprehensive_stats
                    WHERE round_date = $1
                      AND map_name = $2
                      AND round_number = $3
                    ORDER BY team, player_name
                """
                player_rows = await self.db_adapter.fetch_all(
                    fallback_players, (round_date, map_name, round_number)
                )

            team1_players = []
            team2_players = []
            team1_name = "Allies"
            team2_name = "Axis"
            winner_team_name = None

            guid_to_team = {}
            if gaming_session_id is not None:
                if gaming_session_id not in team_cache:
                    session_ids = session_round_ids.get(gaming_session_id, [])
                    hardcoded = await self.get_hardcoded_teams(session_ids)
                    if hardcoded:
                        team_names = list(hardcoded.keys())
                        team1_name = team_names[0] if len(team_names) > 0 else team1_name
                        team2_name = team_names[1] if len(team_names) > 1 else team2_name
                        for t_name, data in hardcoded.items():
                            for guid in data.get("guids", []):
                                guid_to_team[guid] = t_name
                    team_cache[gaming_session_id] = {
                        "guid_to_team": guid_to_team,
                        "team1_name": team1_name,
                        "team2_name": team2_name,
                    }

                cached = team_cache[gaming_session_id]
                guid_to_team = cached.get("guid_to_team", {})
                team1_name = cached.get("team1_name", team1_name)
                team2_name = cached.get("team2_name", team2_name)

            side_counts = {
                team1_name: {1: 0, 2: 0},
                team2_name: {1: 0, 2: 0},
            }

            for name, guid, side in player_rows:
                team_name = guid_to_team.get(guid)
                if team_name == team1_name:
                    team1_players.append(name)
                elif team_name == team2_name:
                    team2_players.append(name)
                elif side == 1:
                    team1_players.append(name)
                elif side == 2:
                    team2_players.append(name)

                if team_name in (team1_name, team2_name) and side in (1, 2):
                    side_counts[team_name][side] += 1

            # Check if teams are imbalanced (difference > 2 players)
            team_diff = abs(len(team1_players) - len(team2_players))
            if team_diff > 2 and len(team1_players) + len(team2_players) >= 4:
                # Teams are imbalanced - redistribute evenly
                # This happens when team detection failed
                all_players = team1_players + team2_players
                mid_point = len(all_players) // 2
                team1_players = sorted(all_players)[:mid_point]
                team2_players = sorted(all_players)[mid_point:]
                team1_name = "Allies"
                team2_name = "Axis"

            player_count = len(team1_players) + len(team2_players)
            format_tag = self._get_format_tag(player_count)

            # Map winner side -> persistent team name if possible
            winner_side = row[4]
            side_to_team = {}
            if side_counts[team1_name][1] != side_counts[team2_name][1]:
                side_to_team[1] = team1_name if side_counts[team1_name][1] > side_counts[team2_name][1] else team2_name
            if side_counts[team1_name][2] != side_counts[team2_name][2]:
                side_to_team[2] = team1_name if side_counts[team1_name][2] > side_counts[team2_name][2] else team2_name
            winner_team_name = side_to_team.get(winner_side) if winner_side in (1, 2) else None

            allies_team_name = side_to_team.get(1) or "Allies"
            axis_team_name = side_to_team.get(2) or "Axis"
            score_display = None
            if axis_score is not None or allies_score is not None:
                a_score = int(allies_score or 0)
                x_score = int(axis_score or 0)
                score_display = f"{allies_team_name} {a_score} - {x_score} {axis_team_name}"

            matches.append(
                {
                    "id": round_id,
                    "map_name": map_name,
                    "round_number": round_number,
                    "duration": row[3],
                    "winner": winner_team_name or self._team_name(row[4]),
                    "outcome": row[5],
                    "date": str(round_date),
                    "time_ago": self._time_ago(round_date),
                    "gaming_session_id": gaming_session_id,
                    "match_id": row[9] if len(row) > 9 else None,
                    "team1_players": team1_players,
                    "team2_players": team2_players,
                    "team1_name": team1_name,
                    "team2_name": team2_name,
                    "player_count": player_count,
                    "format": format_tag,
                    "axis_score": axis_score,
                    "allies_score": allies_score,
                    "score_display": score_display,
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
              AND (round_status IN ('completed', 'substitution') OR round_status IS NULL)
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

    async def get_session_matches_by_round_ids(self, session_ids: List[int]) -> List[Dict]:
        """
        Get matches for a specific gaming session by round IDs.

        This avoids mixing multiple sessions that share the same date.
        """
        if not session_ids:
            return []

        placeholders = ",".join("?" * len(session_ids))
        query = f"""
            SELECT id, map_name, round_number, actual_time, winner_team, round_outcome, round_date
            FROM rounds
            WHERE id IN ({placeholders})
              AND round_number IN (1, 2)
              AND (round_status = 'completed' OR round_status IS NULL)
            ORDER BY
                round_date,
                CAST(REPLACE(round_time, ':', '') AS INTEGER),
                round_number
        """
        rows = await self.db_adapter.fetch_all(query, tuple(session_ids))

        return [
            {
                "id": row[0],
                "map_name": row[1],
                "round_number": row[2],
                "duration": row[3],
                "winner": self._team_name(row[4]),
                "outcome": row[5],
                "date": row[6],
            }
            for row in rows
        ]
