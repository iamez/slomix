"""
BOX Round Scoring Service — Oksii-style stopwatch scoring for variable-length sessions.

Scoring rules:
  - R2 winner wins the map -> +2 pts
  - Double fullhold -> +1 pt each (draw)
  - R1 fullhold: provisional +1 to defender

Side alternation:
  - Odd maps (1, 3, 5): R1 alpha=axis, R2 alpha=allies
  - Even maps (2, 4, 6): R1 alpha=allies, R2 alpha=axis
"""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RoundResult:
    map_number: int
    round_number: int
    map_name: str
    winner_team: int  # 1=Axis, 2=Allies, 0=unknown
    defender_team: int
    is_fullhold: bool
    actual_time_seconds: int
    time_limit_seconds: int
    round_id: int | None = None


@dataclass
class MapScore:
    map_number: int
    map_name: str
    alpha_points: int = 0
    beta_points: int = 0
    winner: str = "pending"  # alpha, beta, draw, pending, provisional
    is_fullhold_draw: bool = False
    r1_time: int = 0
    r2_time: int = 0


@dataclass
class SessionScore:
    gaming_session_id: int
    alpha_score: int = 0
    beta_score: int = 0
    maps_completed: int = 0
    maps: list = field(default_factory=list)
    alpha_team_name: str = "Team A"
    beta_team_name: str = "Team B"
    winner: str | None = None


class BOXScoringService:

    def __init__(self, db_adapter):
        self.db = db_adapter

    def get_expected_alpha_side(self, map_number: int, round_number: int) -> int:
        """Return the expected side (1=Axis, 2=Allies) for alpha team.

        Odd maps (1, 3, 5): R1 alpha=axis(1), R2 alpha=allies(2)
        Even maps (2, 4, 6): R1 alpha=allies(2), R2 alpha=axis(1)
        """
        if map_number % 2 == 1:
            return 1 if round_number == 1 else 2
        else:
            return 2 if round_number == 1 else 1

    def score_map(self, r1: RoundResult, r2: RoundResult | None,
                  alpha_side_r1: int, alpha_side_r2: int) -> MapScore:
        """Score a single map (R1 + optional R2) and return a MapScore."""
        ms = MapScore(map_number=r1.map_number, map_name=r1.map_name)
        ms.r1_time = r1.actual_time_seconds

        alpha_won_r1 = (r1.winner_team == alpha_side_r1) if r1.winner_team > 0 else None

        if r2 is None:
            # Only R1 played — provisional score if fullhold
            if r1.is_fullhold and alpha_won_r1 is not None:
                if alpha_won_r1:
                    ms.alpha_points = 1
                else:
                    ms.beta_points = 1
                ms.winner = "provisional"
            return ms

        ms.r2_time = r2.actual_time_seconds
        alpha_won_r2 = (r2.winner_team == alpha_side_r2) if r2.winner_team > 0 else None

        if r1.is_fullhold and r2.is_fullhold:
            # Double fullhold — draw, 1 point each
            ms.alpha_points = 1
            ms.beta_points = 1
            ms.winner = "draw"
            ms.is_fullhold_draw = True
        elif alpha_won_r2 is not None:
            # R2 winner takes the map — 2 points
            if alpha_won_r2:
                ms.alpha_points = 2
                ms.winner = "alpha"
            else:
                ms.beta_points = 2
                ms.winner = "beta"
        else:
            # Unknown R2 winner — split points
            ms.alpha_points = 1
            ms.beta_points = 1
            ms.winner = "draw"

        return ms

    async def calculate_session_score(self, gaming_session_id: int) -> SessionScore:
        """Calculate the full BOX score for a gaming session."""
        session = SessionScore(gaming_session_id=gaming_session_id)

        # Fetch team names
        team_names = await self._get_team_names(gaming_session_id)
        if team_names:
            session.alpha_team_name = team_names[0]
            if len(team_names) > 1:
                session.beta_team_name = team_names[1]

        # Fetch rounds
        rounds = await self._fetch_session_rounds(gaming_session_id)
        if not rounds:
            return session

        # Group into maps by map_number
        maps: dict[int, dict[int, RoundResult]] = {}
        for r in rounds:
            maps.setdefault(r.map_number, {})[r.round_number] = r

        # Score each map
        for map_num in sorted(maps.keys()):
            r1 = maps[map_num].get(1)
            r2 = maps[map_num].get(2)
            if not r1:
                continue

            alpha_side_r1 = self.get_expected_alpha_side(map_num, 1)
            alpha_side_r2 = self.get_expected_alpha_side(map_num, 2)

            map_score = self.score_map(r1, r2, alpha_side_r1, alpha_side_r2)
            session.alpha_score += map_score.alpha_points
            session.beta_score += map_score.beta_points
            if r2 is not None:
                session.maps_completed += 1
            session.maps.append(map_score)

        if session.maps_completed > 0:
            if session.alpha_score > session.beta_score:
                session.winner = "alpha"
            elif session.beta_score > session.alpha_score:
                session.winner = "beta"
            else:
                session.winner = "draw"

        return session

    def to_api_response(self, score: SessionScore) -> dict:
        """Convert to JSON-serializable API response."""
        return {
            "status": "ok",
            "gaming_session_id": score.gaming_session_id,
            "alpha_team": score.alpha_team_name,
            "beta_team": score.beta_team_name,
            "alpha_score": score.alpha_score,
            "beta_score": score.beta_score,
            "maps_completed": score.maps_completed,
            "winner": score.winner,
            "winner_name": (score.alpha_team_name if score.winner == "alpha"
                           else score.beta_team_name if score.winner == "beta"
                           else "Draw" if score.winner == "draw" else None),
            "maps": [
                {
                    "map_number": m.map_number,
                    "map_name": m.map_name,
                    "alpha_points": m.alpha_points,
                    "beta_points": m.beta_points,
                    "winner": m.winner,
                    "is_fullhold_draw": m.is_fullhold_draw,
                    "r1_time": m.r1_time,
                    "r2_time": m.r2_time,
                }
                for m in score.maps
            ],
        }

    # --- DB Helpers ---

    async def _get_team_names(self, gaming_session_id: int) -> list[str]:
        """Get team names from session_teams, ordered consistently."""
        rows = await self.db.fetch_all(
            "SELECT DISTINCT team_name FROM session_teams "
            "WHERE gaming_session_id = $1 ORDER BY team_name",
            (gaming_session_id,),
        )
        return [r[0] for r in (rows or [])]

    async def _fetch_session_rounds(self, gaming_session_id: int) -> list[RoundResult]:
        """Fetch all R1/R2 rounds for a session and assign sequential map numbers.

        Filters out round_number=0 (summary rows).
        Uses ``actual_duration_seconds`` (integer) for timing and
        ``round_outcome`` ('Fullhold') for fullhold detection — these are the
        columns that actually contain data in the ``rounds`` table.
        ``time_to_beat_seconds`` is included when present but may be NULL.
        """
        rows = await self.db.fetch_all(
            """
            SELECT id,
                   map_name,
                   round_number,
                   COALESCE(winner_team, 0),
                   COALESCE(defender_team, 0),
                   round_outcome,
                   COALESCE(actual_duration_seconds, 0),
                   COALESCE(time_to_beat_seconds, 0)
            FROM rounds
            WHERE gaming_session_id = $1
              AND round_number IN (1, 2)
            ORDER BY round_date, round_time, id
            """,
            (gaming_session_id,),
        )

        if not rows:
            return []

        # Assign map_number sequentially.
        # A new map starts when we see round_number=1 (a fresh R1).
        # This handles the same map_name appearing multiple times in a session.
        results: list[RoundResult] = []
        map_number = 0

        for r in rows:
            round_id = r[0]
            map_name = r[1]
            round_num = r[2]
            winner_team = r[3]
            defender_team = r[4]
            round_outcome = r[5] or ""
            actual_duration = r[6]
            time_to_beat = r[7]

            # New map whenever we encounter round_number 1
            if round_num == 1:
                map_number += 1

            is_fullhold = round_outcome.lower() == "fullhold" if round_outcome else False

            results.append(RoundResult(
                map_number=map_number,
                round_number=round_num,
                map_name=map_name,
                winner_team=winner_team,
                defender_team=defender_team,
                is_fullhold=is_fullhold,
                actual_time_seconds=actual_duration,
                time_limit_seconds=time_to_beat,
                round_id=round_id,
            ))

        return results
