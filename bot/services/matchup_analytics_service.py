"""
Matchup Analytics Service

Tracks and analyzes matchup statistics between specific player lineups.

Definitions:
- Lineup: A specific set of players (identified by sorted GUIDs)
- Matchup: Lineup A vs Lineup B (normalized so A vs B == B vs A)

Features:
- Track matchup frequency, win rates, performance deltas
- Calculate synergy/anti-synergy metrics
- Confidence-based insights (minimum sample size)
- Per-map and overall statistics
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Any
from datetime import datetime
from functools import lru_cache

logger = logging.getLogger(__name__)

# Simple TTL cache implementation (avoid external dependency)
class TTLCache:
    """Simple TTL cache with max size."""
    def __init__(self, maxsize: int = 500, ttl_seconds: int = 3600):
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._maxsize = maxsize
        self._ttl = ttl_seconds

    def get(self, key: str) -> Optional[Any]:
        import time
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self._ttl:
                return value
            del self._cache[key]
        return None

    def set(self, key: str, value: Any) -> None:
        import time
        # Evict oldest if at capacity
        if len(self._cache) >= self._maxsize:
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]
        self._cache[key] = (value, time.time())

# Minimum matches required for "high confidence" insights
MIN_MATCHES_HIGH_CONFIDENCE = 5
MIN_MATCHES_MEDIUM_CONFIDENCE = 3
MIN_MATCHES_LOW_CONFIDENCE = 1


@dataclass
class PlayerMatchupStats:
    """Per-player statistics within a matchup context."""
    player_guid: str
    player_name: str

    # Matchup-specific averages
    avg_kills: float = 0.0
    avg_deaths: float = 0.0
    avg_dpm: float = 0.0
    avg_kd: float = 0.0

    # Career baseline (for comparison)
    baseline_kills: float = 0.0
    baseline_deaths: float = 0.0
    baseline_dpm: float = 0.0
    baseline_kd: float = 0.0

    # Performance delta (matchup - baseline)
    delta_kills: float = 0.0
    delta_dpm: float = 0.0
    delta_kd: float = 0.0

    # Impact percentage (delta as % of baseline)
    impact_percent: float = 0.0

    matches_played: int = 0


@dataclass
class MatchupResult:
    """Result of a single matchup instance."""
    session_date: str
    gaming_session_id: int
    map_name: Optional[str] = None

    # Which lineup won (lineup_a_hash or lineup_b_hash)
    winner_lineup_hash: Optional[str] = None

    # Score if available
    lineup_a_score: int = 0
    lineup_b_score: int = 0

    # Player stats for this match (guid -> stats dict)
    player_stats: Dict[str, Dict] = field(default_factory=dict)


@dataclass
class MatchupStats:
    """Aggregated statistics for a specific matchup."""
    lineup_a_hash: str
    lineup_b_hash: str
    matchup_id: str  # Normalized: {lower_hash}:{higher_hash}

    # Lineup details
    lineup_a_guids: List[str] = field(default_factory=list)
    lineup_b_guids: List[str] = field(default_factory=list)
    lineup_a_names: List[str] = field(default_factory=list)
    lineup_b_names: List[str] = field(default_factory=list)

    # Aggregate stats
    total_matches: int = 0
    lineup_a_wins: int = 0
    lineup_b_wins: int = 0
    ties: int = 0

    # Win rates (from lineup A's perspective)
    lineup_a_winrate: float = 0.0
    lineup_b_winrate: float = 0.0

    # Per-player performance in this matchup
    player_stats: Dict[str, PlayerMatchupStats] = field(default_factory=dict)

    # Best/worst performers
    top_performer_guid: Optional[str] = None
    top_performer_impact: float = 0.0
    worst_performer_guid: Optional[str] = None
    worst_performer_impact: float = 0.0

    # Map breakdown (if tracking by map)
    map_stats: Dict[str, Dict] = field(default_factory=dict)

    # Confidence level
    confidence: str = "low"  # low, medium, high

    # Last played
    last_played: Optional[str] = None


class MatchupAnalyticsService:
    """
    Service for tracking and analyzing matchup statistics.

    A matchup is uniquely identified by the combination of two lineups.
    Lineups are identified by a hash of sorted player GUIDs.
    """

    def __init__(self, db_adapter):
        """
        Initialize the matchup analytics service.

        Args:
            db_adapter: Database adapter for queries
        """
        self.db = db_adapter
        self._player_baselines = TTLCache(maxsize=500, ttl_seconds=3600)  # 1 hour TTL

    # =========================================================================
    # LINEUP & MATCHUP IDENTIFICATION
    # =========================================================================

    @staticmethod
    def create_lineup_hash(player_guids: List[str]) -> str:
        """
        Create a deterministic hash for a lineup.

        Lineups are identified by sorting GUIDs and hashing.
        This ensures the same players always produce the same hash,
        regardless of order.

        Args:
            player_guids: List of player GUIDs

        Returns:
            MD5 hash of the sorted GUIDs (first 12 chars for readability)
        """
        sorted_guids = sorted(player_guids)
        lineup_string = '|'.join(sorted_guids)
        full_hash = hashlib.md5(lineup_string.encode()).hexdigest()
        return full_hash[:12]  # First 12 chars is enough for uniqueness

    @staticmethod
    def create_matchup_id(lineup_a_hash: str, lineup_b_hash: str) -> str:
        """
        Create a normalized matchup ID from two lineup hashes.

        Normalizes so that A vs B and B vs A produce the same ID.
        The lower hash alphabetically always comes first.

        Args:
            lineup_a_hash: Hash of lineup A
            lineup_b_hash: Hash of lineup B

        Returns:
            Normalized matchup ID: "{lower_hash}:{higher_hash}"
        """
        if lineup_a_hash <= lineup_b_hash:
            return f"{lineup_a_hash}:{lineup_b_hash}"
        else:
            return f"{lineup_b_hash}:{lineup_a_hash}"

    @staticmethod
    def get_confidence_level(match_count: int) -> str:
        """
        Determine confidence level based on sample size.

        Args:
            match_count: Number of matches in the sample

        Returns:
            Confidence level: "high", "medium", or "low"
        """
        if match_count >= MIN_MATCHES_HIGH_CONFIDENCE:
            return "high"
        elif match_count >= MIN_MATCHES_MEDIUM_CONFIDENCE:
            return "medium"
        else:
            return "low"

    # =========================================================================
    # PLAYER BASELINE CALCULATION
    # =========================================================================

    async def get_player_baseline(
        self,
        player_guid: str,
        days_back: int = 90
    ) -> Dict[str, float]:
        """
        Get a player's baseline (career average) statistics.

        Used to compare matchup-specific performance against overall performance.

        Args:
            player_guid: Player's GUID
            days_back: How far back to look for baseline calculation

        Returns:
            Dict with avg_kills, avg_deaths, avg_dpm, avg_kd, matches_played
        """
        # Check cache first
        cache_key = f"{player_guid}:{days_back}"
        cached = self._player_baselines.get(cache_key)
        if cached is not None:
            return cached

        query = """
            SELECT
                AVG(kills) as avg_kills,
                AVG(deaths) as avg_deaths,
                CASE WHEN SUM(time_played_seconds) > 0
                     THEN (SUM(damage_given) * 60.0) / SUM(time_played_seconds)
                     ELSE 0 END as avg_dpm,
                CASE WHEN SUM(deaths) > 0
                     THEN SUM(kills)::float / SUM(deaths)
                     ELSE SUM(kills) END as avg_kd,
                COUNT(DISTINCT round_id) as matches_played
            FROM player_comprehensive_stats
            WHERE player_guid = $1
              AND round_date >= (CURRENT_DATE - $2 * INTERVAL '1 day')::text
              AND round_number IN (1, 2)
        """

        row = await self.db.fetch_one(query, (player_guid, days_back))

        if row:
            baseline = {
                'avg_kills': float(row[0] or 0),
                'avg_deaths': float(row[1] or 0),
                'avg_dpm': float(row[2] or 0),
                'avg_kd': float(row[3] or 0),
                'matches_played': int(row[4] or 0)
            }
        else:
            baseline = {
                'avg_kills': 0.0,
                'avg_deaths': 0.0,
                'avg_dpm': 0.0,
                'avg_kd': 0.0,
                'matches_played': 0
            }

        # Cache the result
        self._player_baselines.set(cache_key, baseline)
        return baseline

    async def get_player_baselines_batch(
        self,
        player_guids: List[str],
        days_back: int = 90
    ) -> Dict[str, Dict[str, float]]:
        """
        Get baselines for multiple players efficiently.

        Args:
            player_guids: List of player GUIDs
            days_back: How far back to look

        Returns:
            Dict mapping guid -> baseline stats
        """
        baselines = {}
        for guid in player_guids:
            baselines[guid] = await self.get_player_baseline(guid, days_back)
        return baselines

    # =========================================================================
    # MATCHUP AGGREGATION
    # =========================================================================

    async def record_matchup(
        self,
        lineup_a_guids: List[str],
        lineup_b_guids: List[str],
        session_date: str,
        gaming_session_id: int,
        winner_lineup: Optional[str] = None,  # 'a', 'b', or None for tie
        lineup_a_score: int = 0,
        lineup_b_score: int = 0,
        map_name: Optional[str] = None,
        player_stats: Optional[Dict[str, Dict]] = None
    ) -> bool:
        """
        Record a matchup result to the database.

        Args:
            lineup_a_guids: List of GUIDs for lineup A
            lineup_b_guids: List of GUIDs for lineup B
            session_date: Date of the session
            gaming_session_id: Gaming session ID
            winner_lineup: 'a', 'b', or None for tie
            lineup_a_score: Score for lineup A
            lineup_b_score: Score for lineup B
            map_name: Optional map name
            player_stats: Optional dict of player stats {guid: {kills, deaths, dpm, ...}}

        Returns:
            True if recorded successfully
        """
        try:
            # Create hashes
            lineup_a_hash = self.create_lineup_hash(lineup_a_guids)
            lineup_b_hash = self.create_lineup_hash(lineup_b_guids)
            matchup_id = self.create_matchup_id(lineup_a_hash, lineup_b_hash)

            # Determine winner hash
            winner_hash = None
            if winner_lineup == 'a':
                winner_hash = lineup_a_hash
            elif winner_lineup == 'b':
                winner_hash = lineup_b_hash

            # Insert matchup record
            query = """
                INSERT INTO matchup_history (
                    matchup_id, lineup_a_hash, lineup_b_hash,
                    lineup_a_guids, lineup_b_guids,
                    session_date, gaming_session_id,
                    winner_lineup_hash, lineup_a_score, lineup_b_score,
                    map_name, player_stats
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12
                )
                ON CONFLICT (session_date, gaming_session_id, matchup_id) DO UPDATE SET
                    winner_lineup_hash = EXCLUDED.winner_lineup_hash,
                    lineup_a_score = EXCLUDED.lineup_a_score,
                    lineup_b_score = EXCLUDED.lineup_b_score,
                    player_stats = EXCLUDED.player_stats,
                    updated_at = NOW()
            """

            await self.db.execute(query, (
                matchup_id,
                lineup_a_hash,
                lineup_b_hash,
                json.dumps(sorted(lineup_a_guids)),
                json.dumps(sorted(lineup_b_guids)),
                session_date,
                gaming_session_id,
                winner_hash,
                lineup_a_score,
                lineup_b_score,
                map_name,
                json.dumps(player_stats) if player_stats else None
            ))

            logger.info(f"📊 Recorded matchup: {len(lineup_a_guids)}v{len(lineup_b_guids)} "
                       f"on {session_date} ({map_name or 'all maps'})")
            return True

        except Exception as e:
            logger.error(f"Failed to record matchup: {e}", exc_info=True)
            return False

    async def get_matchup_stats(
        self,
        lineup_a_guids: List[str],
        lineup_b_guids: List[str],
        map_name: Optional[str] = None,
        days_back: int = 365
    ) -> Optional[MatchupStats]:
        """
        Get aggregated statistics for a specific matchup.

        This is the main query interface for matchup analytics.

        Args:
            lineup_a_guids: List of GUIDs for lineup A
            lineup_b_guids: List of GUIDs for lineup B
            map_name: Optional map filter
            days_back: How far back to look

        Returns:
            MatchupStats object with all aggregated data, or None if no data
        """
        try:
            lineup_a_hash = self.create_lineup_hash(lineup_a_guids)
            lineup_b_hash = self.create_lineup_hash(lineup_b_guids)
            matchup_id = self.create_matchup_id(lineup_a_hash, lineup_b_hash)

            # Query all matches for this matchup
            if map_name:
                query = """
                    SELECT session_date, gaming_session_id, map_name,
                           winner_lineup_hash, lineup_a_score, lineup_b_score,
                           lineup_a_hash, lineup_b_hash, lineup_a_guids, lineup_b_guids,
                           player_stats
                    FROM matchup_history
                    WHERE matchup_id = $1
                      AND map_name = $2
                      AND session_date >= (CURRENT_DATE - $3 * INTERVAL '1 day')::text
                    ORDER BY session_date DESC
                """
                rows = await self.db.fetch_all(query, (matchup_id, map_name, days_back))
            else:
                query = """
                    SELECT session_date, gaming_session_id, map_name,
                           winner_lineup_hash, lineup_a_score, lineup_b_score,
                           lineup_a_hash, lineup_b_hash, lineup_a_guids, lineup_b_guids,
                           player_stats
                    FROM matchup_history
                    WHERE matchup_id = $1
                      AND session_date >= (CURRENT_DATE - $2 * INTERVAL '1 day')::text
                    ORDER BY session_date DESC
                """
                rows = await self.db.fetch_all(query, (matchup_id, days_back))

            if not rows:
                return None

            # Initialize stats
            stats = MatchupStats(
                lineup_a_hash=lineup_a_hash,
                lineup_b_hash=lineup_b_hash,
                matchup_id=matchup_id,
                lineup_a_guids=sorted(lineup_a_guids),
                lineup_b_guids=sorted(lineup_b_guids)
            )

            # Aggregate results
            player_match_stats: Dict[str, List[Dict]] = {}  # guid -> list of match stats

            for row in rows:
                (session_date, gaming_session_id, row_map, winner_hash,
                 a_score, b_score, row_a_hash, row_b_hash,
                 row_a_guids_json, row_b_guids_json, player_stats_json) = row

                stats.total_matches += 1
                stats.last_played = session_date if not stats.last_played else stats.last_played

                # Determine if our lineup A is the stored lineup A or B
                # (matchup_id is normalized, so we need to check)
                is_flipped = (row_a_hash != lineup_a_hash)

                if is_flipped:
                    # Our A is stored as B, swap perspective
                    actual_a_wins = (winner_hash == row_b_hash)
                    actual_b_wins = (winner_hash == row_a_hash)
                else:
                    actual_a_wins = (winner_hash == row_a_hash)
                    actual_b_wins = (winner_hash == row_b_hash)

                if actual_a_wins:
                    stats.lineup_a_wins += 1
                elif actual_b_wins:
                    stats.lineup_b_wins += 1
                else:
                    stats.ties += 1

                # Track map stats
                if row_map:
                    if row_map not in stats.map_stats:
                        stats.map_stats[row_map] = {'matches': 0, 'a_wins': 0, 'b_wins': 0}
                    stats.map_stats[row_map]['matches'] += 1
                    if actual_a_wins:
                        stats.map_stats[row_map]['a_wins'] += 1
                    elif actual_b_wins:
                        stats.map_stats[row_map]['b_wins'] += 1

                # Collect player stats
                if player_stats_json:
                    match_player_stats = json.loads(player_stats_json) if isinstance(player_stats_json, str) else player_stats_json
                    for guid, pstats in match_player_stats.items():
                        if guid not in player_match_stats:
                            player_match_stats[guid] = []
                        player_match_stats[guid].append(pstats)

            # Calculate win rates
            if stats.total_matches > 0:
                stats.lineup_a_winrate = stats.lineup_a_wins / stats.total_matches
                stats.lineup_b_winrate = stats.lineup_b_wins / stats.total_matches

            # Calculate per-player stats and deltas
            all_guids = set(lineup_a_guids) | set(lineup_b_guids)
            baselines = await self.get_player_baselines_batch(list(all_guids))

            for guid in all_guids:
                if guid not in player_match_stats:
                    continue

                match_list = player_match_stats[guid]
                baseline = baselines.get(guid, {})

                if not match_list:
                    continue

                # Calculate matchup averages
                avg_kills = sum(m.get('kills', 0) for m in match_list) / len(match_list)
                avg_deaths = sum(m.get('deaths', 0) for m in match_list) / len(match_list)
                avg_dpm = sum(m.get('dpm', 0) for m in match_list) / len(match_list)
                avg_kd = avg_kills / avg_deaths if avg_deaths > 0 else avg_kills

                # Calculate deltas
                delta_dpm = avg_dpm - baseline.get('avg_dpm', 0)
                baseline_dpm = baseline.get('avg_dpm', 1)  # Avoid division by zero
                impact_percent = (delta_dpm / baseline_dpm * 100) if baseline_dpm > 0 else 0

                # Get player name from first match
                player_name = match_list[0].get('name', guid[:8])

                player_stat = PlayerMatchupStats(
                    player_guid=guid,
                    player_name=player_name,
                    avg_kills=avg_kills,
                    avg_deaths=avg_deaths,
                    avg_dpm=avg_dpm,
                    avg_kd=avg_kd,
                    baseline_kills=baseline.get('avg_kills', 0),
                    baseline_deaths=baseline.get('avg_deaths', 0),
                    baseline_dpm=baseline.get('avg_dpm', 0),
                    baseline_kd=baseline.get('avg_kd', 0),
                    delta_dpm=delta_dpm,
                    impact_percent=impact_percent,
                    matches_played=len(match_list)
                )

                stats.player_stats[guid] = player_stat

                # Track top/worst performers
                if stats.top_performer_guid is None or impact_percent > stats.top_performer_impact:
                    stats.top_performer_guid = guid
                    stats.top_performer_impact = impact_percent

                if stats.worst_performer_guid is None or impact_percent < stats.worst_performer_impact:
                    stats.worst_performer_guid = guid
                    stats.worst_performer_impact = impact_percent

            # Get player names for lineups
            stats.lineup_a_names = [
                stats.player_stats.get(g, PlayerMatchupStats(g, g[:8])).player_name
                for g in lineup_a_guids
            ]
            stats.lineup_b_names = [
                stats.player_stats.get(g, PlayerMatchupStats(g, g[:8])).player_name
                for g in lineup_b_guids
            ]

            # Set confidence level
            stats.confidence = self.get_confidence_level(stats.total_matches)

            return stats

        except Exception as e:
            logger.error(f"Failed to get matchup stats: {e}", exc_info=True)
            return None

    # =========================================================================
    # SYNERGY & ANTI-SYNERGY ANALYSIS
    # =========================================================================

    async def get_player_synergy(
        self,
        player_guid: str,
        teammate_guid: str,
        days_back: int = 90
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate synergy between two players when on the same team.

        Compares a player's performance when playing WITH a specific teammate
        versus their overall baseline.

        Args:
            player_guid: The player to analyze
            teammate_guid: The teammate to check synergy with
            days_back: How far back to look

        Returns:
            Dict with synergy metrics, or None if not enough data
        """
        try:
            # Get player's baseline
            baseline = await self.get_player_baseline(player_guid, days_back)

            # Get player's stats when playing with teammate
            # They're teammates if they appear in the same lineup in matchup_history
            query = """
                SELECT m.player_stats
                FROM matchup_history m
                WHERE m.session_date >= (CURRENT_DATE - $1 * INTERVAL '1 day')::text
                  AND (
                    (m.lineup_a_guids::text LIKE $2 AND m.lineup_a_guids::text LIKE $3)
                    OR
                    (m.lineup_b_guids::text LIKE $4 AND m.lineup_b_guids::text LIKE $5)
                  )
            """

            # Use LIKE with % to find GUIDs in JSON arrays
            player_pattern = f'%{player_guid}%'
            teammate_pattern = f'%{teammate_guid}%'

            rows = await self.db.fetch_all(query, (
                days_back,
                player_pattern, teammate_pattern,
                player_pattern, teammate_pattern
            ))

            if not rows or len(rows) < MIN_MATCHES_LOW_CONFIDENCE:
                return None

            # Calculate stats when playing together
            together_stats = []
            for row in rows:
                if row[0]:
                    try:
                        player_stats = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                        if isinstance(player_stats, dict) and player_guid in player_stats:
                            together_stats.append(player_stats[player_guid])
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.warning(f"Invalid JSON in player_stats: {e}")
                        continue

            if not together_stats:
                return None

            # Calculate averages (safe division)
            count = len(together_stats)
            avg_dpm_together = sum(s.get('dpm', 0) for s in together_stats) / count if count > 0 else 0
            avg_kd_together = sum(s.get('kd', 0) for s in together_stats) / count if count > 0 else 0

            # Calculate synergy (delta from baseline)
            baseline_dpm = baseline.get('avg_dpm', 0)
            baseline_kd = baseline.get('avg_kd', 0)
            dpm_delta = avg_dpm_together - baseline_dpm
            kd_delta = avg_kd_together - baseline_kd

            # Safe synergy percent calculation
            synergy_percent = (dpm_delta / baseline_dpm * 100) if baseline_dpm > 0 else 0

            return {
                'player_guid': player_guid,
                'teammate_guid': teammate_guid,
                'matches_together': len(together_stats),
                'avg_dpm_together': avg_dpm_together,
                'avg_dpm_baseline': baseline.get('avg_dpm', 0),
                'dpm_delta': dpm_delta,
                'synergy_percent': synergy_percent,
                'confidence': self.get_confidence_level(len(together_stats))
            }

        except Exception as e:
            logger.error(f"Failed to calculate synergy: {e}", exc_info=True)
            return None

    async def get_player_anti_synergy(
        self,
        player_guid: str,
        opponent_guid: str,
        days_back: int = 90
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate anti-synergy (performance vs specific opponent).

        Compares a player's performance when playing AGAINST a specific opponent
        versus their overall baseline.

        Args:
            player_guid: The player to analyze
            opponent_guid: The opponent to check anti-synergy with
            days_back: How far back to look

        Returns:
            Dict with anti-synergy metrics, or None if not enough data
        """
        try:
            baseline = await self.get_player_baseline(player_guid, days_back)

            # Get matches where player and opponent were on opposite teams
            query = """
                SELECT m.player_stats, m.lineup_a_guids, m.lineup_b_guids
                FROM matchup_history m
                WHERE m.session_date >= (CURRENT_DATE - $1 * INTERVAL '1 day')::text
                  AND (
                    (m.lineup_a_guids::text LIKE $2 AND m.lineup_b_guids::text LIKE $3)
                    OR
                    (m.lineup_b_guids::text LIKE $4 AND m.lineup_a_guids::text LIKE $5)
                  )
            """

            player_pattern = f'%{player_guid}%'
            opponent_pattern = f'%{opponent_guid}%'

            rows = await self.db.fetch_all(query, (
                days_back,
                player_pattern, opponent_pattern,
                player_pattern, opponent_pattern
            ))

            if not rows or len(rows) < MIN_MATCHES_LOW_CONFIDENCE:
                return None

            # Calculate stats when facing opponent
            versus_stats = []
            for row in rows:
                if row[0]:
                    try:
                        player_stats = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                        if isinstance(player_stats, dict) and player_guid in player_stats:
                            versus_stats.append(player_stats[player_guid])
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.warning(f"Invalid JSON in player_stats: {e}")
                        continue

            if not versus_stats:
                return None

            # Safe division
            count = len(versus_stats)
            avg_dpm_versus = sum(s.get('dpm', 0) for s in versus_stats) / count if count > 0 else 0
            baseline_dpm = baseline.get('avg_dpm', 0)
            dpm_delta = avg_dpm_versus - baseline_dpm

            # Negative = opponent suppresses this player (safe division)
            suppression_percent = (dpm_delta / baseline_dpm * 100) if baseline_dpm > 0 else 0

            return {
                'player_guid': player_guid,
                'opponent_guid': opponent_guid,
                'matches_versus': len(versus_stats),
                'avg_dpm_versus': avg_dpm_versus,
                'avg_dpm_baseline': baseline.get('avg_dpm', 0),
                'dpm_delta': dpm_delta,
                'suppression_percent': suppression_percent,  # Negative = suppressed
                'confidence': self.get_confidence_level(len(versus_stats))
            }

        except Exception as e:
            logger.error(f"Failed to calculate anti-synergy: {e}", exc_info=True)
            return None

    # =========================================================================
    # DISCORD OUTPUT FORMATTING
    # =========================================================================

    def format_matchup_summary(
        self,
        stats: MatchupStats,
        perspective: str = 'a'  # 'a' or 'b' - which lineup's perspective
    ) -> str:
        """
        Format matchup stats for Discord display.

        Args:
            stats: MatchupStats object
            perspective: Which lineup's perspective to use ('a' or 'b')

        Returns:
            Formatted string for Discord
        """
        if perspective == 'b':
            our_names = stats.lineup_b_names
            their_names = stats.lineup_a_names
            our_wins = stats.lineup_b_wins
            our_winrate = stats.lineup_b_winrate
        else:
            our_names = stats.lineup_a_names
            their_names = stats.lineup_b_names
            our_wins = stats.lineup_a_wins
            our_winrate = stats.lineup_a_winrate

        # Format lineup names (max 3 shown)
        def format_lineup(names):
            if len(names) <= 3:
                return ', '.join(names)
            return f"{', '.join(names[:3])}..."

        our_lineup = format_lineup(our_names)
        their_lineup = format_lineup(their_names)

        # Build output
        lines = [
            f"**{our_lineup}** vs **{their_lineup}**",
            f"• Matches: {stats.total_matches}",
            f"• Winrate: {our_winrate * 100:.0f}% ({our_wins}W-{stats.total_matches - our_wins - stats.ties}L)",
        ]

        # Top performer
        if stats.top_performer_guid and stats.player_stats.get(stats.top_performer_guid):
            top = stats.player_stats[stats.top_performer_guid]
            sign = "+" if stats.top_performer_impact >= 0 else ""
            lines.append(f"• {top.player_name} {sign}{stats.top_performer_impact:.0f}% impact")

        # Worst performer (only show if significantly negative)
        if (stats.worst_performer_guid and
            stats.worst_performer_impact < -10 and
            stats.player_stats.get(stats.worst_performer_guid)):
            worst = stats.player_stats[stats.worst_performer_guid]
            lines.append(f"• {worst.player_name} {stats.worst_performer_impact:.0f}% impact")

        # Confidence
        confidence_emoji = {"high": "🟢", "medium": "🟡", "low": "🔴"}
        lines.append(f"• Confidence: {confidence_emoji.get(stats.confidence, '⚪')} {stats.confidence.title()}")

        return '\n'.join(lines)

    def format_synergy_summary(
        self,
        synergy: Dict[str, Any],
        player_name: str,
        teammate_name: str
    ) -> str:
        """
        Format synergy stats for Discord display.

        Args:
            synergy: Synergy dict from get_player_synergy()
            player_name: Name of the player
            teammate_name: Name of the teammate

        Returns:
            Formatted string for Discord
        """
        sign = "+" if synergy['synergy_percent'] >= 0 else ""

        lines = [
            f"**{player_name}** with **{teammate_name}**",
            f"• Matches together: {synergy['matches_together']}",
            f"• DPM together: {synergy['avg_dpm_together']:.1f} (baseline: {synergy['avg_dpm_baseline']:.1f})",
            f"• Synergy: {sign}{synergy['synergy_percent']:.1f}%",
            f"• Confidence: {synergy['confidence'].title()}"
        ]

        return '\n'.join(lines)


# =========================================================================
# DATABASE SCHEMA
# =========================================================================

MATCHUP_HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS matchup_history (
    id SERIAL PRIMARY KEY,
    matchup_id TEXT NOT NULL,  -- Normalized: {lower_hash}:{higher_hash}
    lineup_a_hash TEXT NOT NULL,
    lineup_b_hash TEXT NOT NULL,
    lineup_a_guids JSONB NOT NULL,
    lineup_b_guids JSONB NOT NULL,
    session_date TEXT NOT NULL,
    gaming_session_id INTEGER NOT NULL,
    winner_lineup_hash TEXT,  -- NULL for tie
    lineup_a_score INTEGER DEFAULT 0,
    lineup_b_score INTEGER DEFAULT 0,
    map_name TEXT,
    player_stats JSONB,  -- {guid: {kills, deaths, dpm, kd, name}}
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(session_date, gaming_session_id, matchup_id)
);

CREATE INDEX IF NOT EXISTS idx_matchup_history_matchup_id ON matchup_history(matchup_id);
CREATE INDEX IF NOT EXISTS idx_matchup_history_session_date ON matchup_history(session_date);
CREATE INDEX IF NOT EXISTS idx_matchup_history_map ON matchup_history(map_name);
"""
