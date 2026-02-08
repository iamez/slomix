"""
Player Analytics Service

Advanced player analytics beyond basic stats:
- Consistency Score (reliability/variance)
- Map Affinity (performance by map)
- Session Fatigue (performance over time)
- Attack vs Defense Preference
- Fun Stats / Awards
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from collections import defaultdict
import statistics

logger = logging.getLogger(__name__)


@dataclass
class ConsistencyStats:
    """Player consistency metrics."""
    player_guid: str
    player_name: str

    # Core metrics
    avg_dpm: float = 0.0
    std_dev_dpm: float = 0.0
    consistency_score: float = 0.0  # 0-100, higher = more consistent

    # Classification
    consistency_tier: str = "Unknown"  # Consistent, Average, Streaky

    rounds_analyzed: int = 0

    # Recent trend
    recent_variance: str = "stable"  # improving, stable, declining


@dataclass
class MapAffinityStats:
    """Player's performance breakdown by map."""
    player_guid: str
    player_name: str

    overall_dpm: float = 0.0

    # Map -> stats
    map_stats: Dict[str, Dict] = field(default_factory=dict)
    # {map_name: {dpm, delta_percent, rounds, kills, deaths}}

    best_map: Optional[str] = None
    best_map_delta: float = 0.0

    worst_map: Optional[str] = None
    worst_map_delta: float = 0.0


@dataclass
class PlaystyleStats:
    """Attack vs Defense preference analysis."""
    player_guid: str
    player_name: str

    attack_rounds: int = 0
    defense_rounds: int = 0

    attack_dpm: float = 0.0
    defense_dpm: float = 0.0

    attack_kd: float = 0.0
    defense_kd: float = 0.0

    preference: str = "balanced"  # attacker, defender, balanced
    preference_strength: float = 0.0  # How strong the preference is (%)


@dataclass
class SessionFatigueStats:
    """Performance trend within a session."""
    session_date: str
    gaming_session_id: int

    # DPM by session third
    early_dpm: float = 0.0
    mid_dpm: float = 0.0
    late_dpm: float = 0.0

    # Change metrics
    fatigue_index: float = 0.0  # Negative = fatiguing, Positive = warming up
    trend: str = "stable"  # warming_up, stable, fatiguing

    total_rounds: int = 0
    session_duration_minutes: float = 0.0


@dataclass
class FunAward:
    """A fun/celebratory stat award."""
    award_name: str
    emoji: str
    player_guid: str
    player_name: str
    value: float
    description: str


class PlayerAnalyticsService:
    """
    Advanced player analytics service.

    Provides insights beyond basic stats using existing data.
    """

    def __init__(self, db_adapter):
        self.db = db_adapter

    # =========================================================================
    # CONSISTENCY SCORE
    # =========================================================================

    async def get_consistency_score(
        self,
        player_guid: str,
        days_back: int = 30,
        min_rounds: int = 10
    ) -> Optional[ConsistencyStats]:
        """
        Calculate a player's consistency score.

        Consistency = 1 - (coefficient of variation of DPM)
        Higher score = more reliable performance.

        Args:
            player_guid: Player GUID
            days_back: How far back to look
            min_rounds: Minimum rounds required

        Returns:
            ConsistencyStats or None if not enough data
        """
        try:
            query = """
                SELECT player_name, dpm
                FROM player_comprehensive_stats
                WHERE player_guid = $1
                  AND round_date >= (CURRENT_DATE - $2 * INTERVAL '1 day')::text
                  AND round_number IN (1, 2)
                  AND time_played_seconds > 60
                ORDER BY round_date DESC, id DESC
            """
            rows = await self.db.fetch_all(query, (player_guid, days_back))

            if len(rows) < min_rounds:
                return None

            player_name = rows[0][0]
            dpm_values = [float(row[1] or 0) for row in rows]

            # Calculate statistics
            avg_dpm = statistics.mean(dpm_values)
            std_dev = statistics.stdev(dpm_values) if len(dpm_values) > 1 else 0

            # Coefficient of variation (CV)
            cv = std_dev / avg_dpm if avg_dpm > 0 else 1

            # Consistency score: 0-100 scale
            # CV of 0.3 (30%) = about 70 consistency
            # CV of 0.5 (50%) = about 50 consistency
            consistency_score = max(0, min(100, (1 - cv) * 100))

            # Classification
            if consistency_score >= 70:
                tier = "Consistent"
            elif consistency_score >= 50:
                tier = "Average"
            else:
                tier = "Streaky"

            # Recent trend (compare last 5 vs previous 5)
            if len(dpm_values) >= 10:
                recent_5 = dpm_values[:5]
                prev_5 = dpm_values[5:10]
                recent_var = statistics.stdev(recent_5) if len(recent_5) > 1 else 0
                prev_var = statistics.stdev(prev_5) if len(prev_5) > 1 else 0

                if recent_var < prev_var * 0.8:
                    trend = "improving"
                elif recent_var > prev_var * 1.2:
                    trend = "declining"
                else:
                    trend = "stable"
            else:
                trend = "stable"

            return ConsistencyStats(
                player_guid=player_guid,
                player_name=player_name,
                avg_dpm=avg_dpm,
                std_dev_dpm=std_dev,
                consistency_score=consistency_score,
                consistency_tier=tier,
                rounds_analyzed=len(rows),
                recent_variance=trend
            )

        except Exception as e:
            logger.error(f"Failed to calculate consistency: {e}", exc_info=True)
            return None

    # =========================================================================
    # MAP AFFINITY
    # =========================================================================

    async def get_map_affinity(
        self,
        player_guid: str,
        days_back: int = 90,
        min_rounds_per_map: int = 3
    ) -> Optional[MapAffinityStats]:
        """
        Calculate player's performance delta by map.

        Shows which maps a player overperforms/underperforms on.

        Args:
            player_guid: Player GUID
            days_back: How far back to look
            min_rounds_per_map: Minimum rounds on a map to include

        Returns:
            MapAffinityStats or None if not enough data
        """
        try:
            query = """
                SELECT MAX(player_name) as player_name, map_name,
                       AVG(dpm) as avg_dpm,
                       COUNT(*) as rounds,
                       SUM(kills) as total_kills,
                       SUM(deaths) as total_deaths
                FROM player_comprehensive_stats
                WHERE player_guid = $1
                  AND round_date >= (CURRENT_DATE - $2 * INTERVAL '1 day')::text
                  AND round_number IN (1, 2)
                  AND time_played_seconds > 60
                GROUP BY player_guid, map_name
                HAVING COUNT(*) >= $3
                ORDER BY avg_dpm DESC
            """
            rows = await self.db.fetch_all(query, (player_guid, days_back, min_rounds_per_map))

            if not rows:
                return None

            player_name = rows[0][0]

            # Calculate overall DPM
            overall_query = """
                SELECT AVG(dpm) FROM player_comprehensive_stats
                WHERE player_guid = $1
                  AND round_date >= (CURRENT_DATE - $2 * INTERVAL '1 day')::text
                  AND round_number IN (1, 2)
                  AND time_played_seconds > 60
            """
            overall_result = await self.db.fetch_one(overall_query, (player_guid, days_back))
            overall_dpm = float(overall_result[0] or 0) if overall_result else 0

            stats = MapAffinityStats(
                player_guid=player_guid,
                player_name=player_name,
                overall_dpm=overall_dpm
            )

            best_delta = -999
            worst_delta = 999

            for row in rows:
                _, map_name, avg_dpm, rounds, kills, deaths = row
                avg_dpm = float(avg_dpm or 0)

                delta_percent = ((avg_dpm - overall_dpm) / overall_dpm * 100) if overall_dpm > 0 else 0

                kills_val = int(kills or 0)
                deaths_val = int(deaths or 0)
                stats.map_stats[map_name] = {
                    'dpm': avg_dpm,
                    'delta_percent': delta_percent,
                    'rounds': int(rounds),
                    'kills': kills_val,
                    'deaths': deaths_val,
                    'kd': kills_val / max(deaths_val, 1)  # Consistent float return
                }

                if delta_percent > best_delta:
                    best_delta = delta_percent
                    stats.best_map = map_name
                    stats.best_map_delta = delta_percent

                if delta_percent < worst_delta:
                    worst_delta = delta_percent
                    stats.worst_map = map_name
                    stats.worst_map_delta = delta_percent

            return stats

        except Exception as e:
            logger.error(f"Failed to calculate map affinity: {e}", exc_info=True)
            return None

    # =========================================================================
    # ATTACK VS DEFENSE PREFERENCE
    # =========================================================================

    async def get_playstyle_preference(
        self,
        player_guid: str,
        days_back: int = 90
    ) -> Optional[PlaystyleStats]:
        """
        Analyze player's attack vs defense performance.

        Uses team assignment and defender_team to determine role.

        Args:
            player_guid: Player GUID
            days_back: How far back to look

        Returns:
            PlaystyleStats or None if not enough data
        """
        try:
            # Get player stats with round context
            query = """
                SELECT p.player_name, p.team, r.defender_team,
                       p.dpm, p.kills, p.deaths, p.round_number
                FROM player_comprehensive_stats p
                JOIN rounds r ON p.round_id = r.id
                WHERE p.player_guid = $1
                  AND p.round_date >= (CURRENT_DATE - $2 * INTERVAL '1 day')::text
                  AND p.round_number IN (1, 2)
                  AND p.time_played_seconds > 60
            """
            rows = await self.db.fetch_all(query, (player_guid, days_back))

            if len(rows) < 10:
                return None

            player_name = rows[0][0]

            attack_dpms = []
            defense_dpms = []
            attack_kills = 0
            attack_deaths = 0
            defense_kills = 0
            defense_deaths = 0

            for row in rows:
                _, team, defender_team, dpm, kills, deaths, round_num = row

                # Determine if player was attacking or defending
                # defender_team tells us which side (1 or 2) was defending
                is_defending = (team == defender_team)

                dpm = float(dpm or 0)
                kills = int(kills or 0)
                deaths = int(deaths or 0)

                if is_defending:
                    defense_dpms.append(dpm)
                    defense_kills += kills
                    defense_deaths += deaths
                else:
                    attack_dpms.append(dpm)
                    attack_kills += kills
                    attack_deaths += deaths

            if not attack_dpms or not defense_dpms:
                return None

            attack_dpm = statistics.mean(attack_dpms)
            defense_dpm = statistics.mean(defense_dpms)
            attack_kd = attack_kills / attack_deaths if attack_deaths > 0 else attack_kills
            defense_kd = defense_kills / defense_deaths if defense_deaths > 0 else defense_kills

            # Determine preference
            dpm_diff = attack_dpm - defense_dpm
            avg_dpm = (attack_dpm + defense_dpm) / 2
            preference_strength = abs(dpm_diff) / avg_dpm * 100 if avg_dpm > 0 else 0

            if preference_strength < 10:
                preference = "balanced"
            elif dpm_diff > 0:
                preference = "attacker"
            else:
                preference = "defender"

            return PlaystyleStats(
                player_guid=player_guid,
                player_name=player_name,
                attack_rounds=len(attack_dpms),
                defense_rounds=len(defense_dpms),
                attack_dpm=attack_dpm,
                defense_dpm=defense_dpm,
                attack_kd=attack_kd,
                defense_kd=defense_kd,
                preference=preference,
                preference_strength=preference_strength
            )

        except Exception as e:
            logger.error(f"Failed to calculate playstyle: {e}", exc_info=True)
            return None

    # =========================================================================
    # SESSION FATIGUE
    # =========================================================================

    async def get_session_fatigue(
        self,
        player_guid: str,
        gaming_session_id: int
    ) -> Optional[SessionFatigueStats]:
        """
        Analyze player's performance trend within a session.

        Splits session into thirds and compares DPM.

        Args:
            player_guid: Player GUID
            gaming_session_id: Gaming session to analyze

        Returns:
            SessionFatigueStats or None if not enough data
        """
        try:
            query = """
                SELECT p.round_date, p.dpm, r.round_time
                FROM player_comprehensive_stats p
                JOIN rounds r ON p.round_id = r.id
                WHERE p.player_guid = $1
                  AND r.gaming_session_id = $2
                  AND p.round_number IN (1, 2)
                  AND p.time_played_seconds > 60
                ORDER BY r.round_date, r.round_time
            """
            rows = await self.db.fetch_all(query, (player_guid, gaming_session_id))

            if len(rows) < 6:  # Need at least 6 rounds for meaningful thirds
                return None

            session_date = rows[0][0]
            dpm_values = [float(row[1] or 0) for row in rows]

            # Split into thirds
            n = len(dpm_values)
            third = n // 3

            early = dpm_values[:third]
            mid = dpm_values[third:2*third]
            late = dpm_values[2*third:]

            early_dpm = statistics.mean(early) if early else 0
            mid_dpm = statistics.mean(mid) if mid else 0
            late_dpm = statistics.mean(late) if late else 0

            # Fatigue index: % change from early to late
            fatigue_index = ((late_dpm - early_dpm) / early_dpm * 100) if early_dpm > 0 else 0

            if fatigue_index > 10:
                trend = "warming_up"
            elif fatigue_index < -10:
                trend = "fatiguing"
            else:
                trend = "stable"

            return SessionFatigueStats(
                session_date=session_date,
                gaming_session_id=gaming_session_id,
                early_dpm=early_dpm,
                mid_dpm=mid_dpm,
                late_dpm=late_dpm,
                fatigue_index=fatigue_index,
                trend=trend,
                total_rounds=len(rows)
            )

        except Exception as e:
            logger.error(f"Failed to calculate session fatigue: {e}", exc_info=True)
            return None

    # =========================================================================
    # FUN STATS / AWARDS
    # =========================================================================

    async def get_session_fun_awards(
        self,
        session_ids: List[int]
    ) -> List[FunAward]:
        """
        Generate fun/celebratory awards for a session.

        Non-toxic stats that celebrate different playstyles.

        Args:
            session_ids: List of round IDs in the session

        Returns:
            List of FunAward objects
        """
        try:
            if not session_ids:
                return []

            placeholders = ','.join(['$' + str(i+1) for i in range(len(session_ids))])

            # Aggregate all players' stats for this session
            query = f"""
                SELECT
                    player_guid,
                    MAX(player_name) as name,
                    SUM(times_revived) as total_revived,
                    SUM(revives_given) as total_revives,
                    SUM(gibs) as total_gibs,
                    SUM(headshot_kills) as total_hs_kills,
                    SUM(headshots) as total_hs,
                    SUM(dynamites_planted) as total_planted,
                    SUM(dynamites_defused) as total_defused,
                    MAX(killing_spree_best) as best_spree,
                    SUM(most_useful_kills) as useful_kills,
                    SUM(kills) as total_kills,
                    SUM(deaths) as total_deaths,
                    CASE WHEN SUM(time_played_seconds) > 0
                         THEN (SUM(damage_given) * 60.0) / SUM(time_played_seconds)
                         ELSE 0 END as dpm,
                    SUM(damage_given) as total_damage,
                    SUM(damage_received) as total_received
                FROM player_comprehensive_stats
                WHERE round_id IN ({placeholders})
                GROUP BY player_guid
                HAVING SUM(time_played_seconds) > 120
            """

            rows = await self.db.fetch_all(query, tuple(session_ids))

            if not rows:
                return []

            awards = []

            # Convert to dicts for easier processing
            # Each row: guid, name, revived, revives, gibs, hs_kills, hs, planted, defused, spree, useful, kills, deaths, dpm, damage, received
            players = []
            for row in rows:
                players.append({
                    'guid': row[0],
                    'name': row[1],
                    'revived': int(row[2] or 0),
                    'revives': int(row[3] or 0),
                    'gibs': int(row[4] or 0),
                    'hs_kills': int(row[5] or 0),
                    'hs': int(row[6] or 0),
                    'planted': int(row[7] or 0),
                    'defused': int(row[8] or 0),
                    'spree': int(row[9] or 0),
                    'useful': int(row[10] or 0),
                    'kills': int(row[11] or 0),
                    'deaths': int(row[12] or 0),
                    'dpm': float(row[13] or 0),
                    'damage': int(row[14] or 0),
                    'received': int(row[15] or 0)
                })

            # Safety check: need at least 1 player for awards
            if not players:
                logger.debug("No qualifying players for awards (all <120s played)")
                return []

            # 1. Zombie Mode - Most times revived
            zombie = max(players, key=lambda p: p['revived'])
            if zombie['revived'] >= 3:
                awards.append(FunAward(
                    award_name="Zombie Mode",
                    emoji="🧟",
                    player_guid=zombie['guid'],
                    player_name=zombie['name'],
                    value=zombie['revived'],
                    description=f"Revived {zombie['revived']} times - kept getting back up!"
                ))

            # 2. Team Dad - Most revives given
            medic = max(players, key=lambda p: p['revives'])
            if medic['revives'] >= 5:
                awards.append(FunAward(
                    award_name="Team Dad",
                    emoji="💉",
                    player_guid=medic['guid'],
                    player_name=medic['name'],
                    value=medic['revives'],
                    description=f"Revived teammates {medic['revives']} times"
                ))

            # 3. Cleanup Crew - Most gibs
            gibber = max(players, key=lambda p: p['gibs'])
            if gibber['gibs'] >= 5:
                awards.append(FunAward(
                    award_name="Cleanup Crew",
                    emoji="💀",
                    player_guid=gibber['guid'],
                    player_name=gibber['name'],
                    value=gibber['gibs'],
                    description=f"{gibber['gibs']} gibs - making sure they stay down"
                ))

            # 4. Silent Assassin - Best headshot kill ratio
            for p in players:
                p['hs_ratio'] = p['hs_kills'] / p['kills'] * 100 if p['kills'] > 5 else 0
            sniper = max(players, key=lambda p: p['hs_ratio'])
            if sniper['hs_ratio'] >= 20 and sniper['hs_kills'] >= 3:
                awards.append(FunAward(
                    award_name="Silent Assassin",
                    emoji="🎯",
                    player_guid=sniper['guid'],
                    player_name=sniper['name'],
                    value=sniper['hs_ratio'],
                    description=f"{sniper['hs_ratio']:.0f}% headshot kills ({sniper['hs_kills']} HS kills)"
                ))

            # 5. Demolition Expert - Most dynamites planted
            demo = max(players, key=lambda p: p['planted'])
            if demo['planted'] >= 2:
                awards.append(FunAward(
                    award_name="Demolition Expert",
                    emoji="💣",
                    player_guid=demo['guid'],
                    player_name=demo['name'],
                    value=demo['planted'],
                    description=f"Planted {demo['planted']} dynamites"
                ))

            # 6. Bomb Squad - Most dynamites defused
            defuser = max(players, key=lambda p: p['defused'])
            if defuser['defused'] >= 2:
                awards.append(FunAward(
                    award_name="Bomb Squad",
                    emoji="🛡️",
                    player_guid=defuser['guid'],
                    player_name=defuser['name'],
                    value=defuser['defused'],
                    description=f"Defused {defuser['defused']} dynamites"
                ))

            # 7. Hot Streak - Best killing spree
            streaker = max(players, key=lambda p: p['spree'])
            if streaker['spree'] >= 5:
                awards.append(FunAward(
                    award_name="Hot Streak",
                    emoji="🔥",
                    player_guid=streaker['guid'],
                    player_name=streaker['name'],
                    value=streaker['spree'],
                    description=f"Best killing spree: {streaker['spree']} kills"
                ))

            # 8. Glass Cannon - High DPM but also high deaths (dies more than kills)
            for p in players:
                # Glass cannon = high damage output, high risk (more deaths than kills)
                if p['deaths'] > 0 and p['kills'] > 0:
                    death_ratio = p['deaths'] / p['kills']
                    p['glass_score'] = p['dpm'] * death_ratio if death_ratio >= 1.0 else 0
                else:
                    p['glass_score'] = 0
            glass = max(players, key=lambda p: p['glass_score']) if players else None
            if glass and glass['dpm'] >= 150 and glass['deaths'] >= glass['kills']:
                awards.append(FunAward(
                    award_name="Glass Cannon",
                    emoji="💥",
                    player_guid=glass['guid'],
                    player_name=glass['name'],
                    value=glass['dpm'],
                    description=f"High risk, high reward: {glass['dpm']:.0f} DPM with {glass['deaths']} deaths"
                ))

            # 9. Useful Fragger - Best useful kill ratio
            for p in players:
                p['useful_ratio'] = p['useful'] / p['kills'] * 100 if p['kills'] > 5 else 0
            useful = max(players, key=lambda p: p['useful_ratio'])
            if useful['useful_ratio'] >= 30 and useful['useful'] >= 5:
                awards.append(FunAward(
                    award_name="Impactful Fragger",
                    emoji="⭐",
                    player_guid=useful['guid'],
                    player_name=useful['name'],
                    value=useful['useful_ratio'],
                    description=f"{useful['useful_ratio']:.0f}% useful kills ({useful['useful']} impact frags)"
                ))

            # 10. Tank - Most damage received and survived
            tank = max(players, key=lambda p: p['received'])
            if tank['received'] >= 2000:
                awards.append(FunAward(
                    award_name="The Tank",
                    emoji="🛡️",
                    player_guid=tank['guid'],
                    player_name=tank['name'],
                    value=tank['received'],
                    description=f"Absorbed {tank['received']:,} damage"
                ))

            return awards

        except Exception as e:
            logger.error(f"Failed to generate fun awards: {e}", exc_info=True)
            return []

    # =========================================================================
    # FORMATTING
    # =========================================================================

    def format_consistency(self, stats: ConsistencyStats) -> str:
        """Format consistency stats for Discord."""
        emoji = {"Consistent": "🟢", "Average": "🟡", "Streaky": "🔴"}

        return (
            f"**{stats.player_name}** - Consistency Analysis\n"
            f"• Score: {stats.consistency_score:.0f}/100 ({stats.consistency_tier})\n"
            f"• Avg DPM: {stats.avg_dpm:.1f} (±{stats.std_dev_dpm:.1f})\n"
            f"• Trend: {stats.recent_variance}\n"
            f"• Rounds analyzed: {stats.rounds_analyzed}"
        )

    def format_map_affinity(self, stats: MapAffinityStats) -> str:
        """Format map affinity for Discord."""
        lines = [f"**{stats.player_name}** - Map Performance\n"]
        lines.append(f"Overall DPM: {stats.overall_dpm:.1f}\n")

        # Sort by delta
        sorted_maps = sorted(
            stats.map_stats.items(),
            key=lambda x: x[1]['delta_percent'],
            reverse=True
        )

        for map_name, data in sorted_maps[:6]:  # Top 6 maps
            sign = "+" if data['delta_percent'] >= 0 else ""
            emoji = "🟢" if data['delta_percent'] > 10 else ("🔴" if data['delta_percent'] < -10 else "⚪")
            lines.append(
                f"{emoji} `{map_name}`: {data['dpm']:.1f} DPM ({sign}{data['delta_percent']:.0f}%) - {data['rounds']} rounds"
            )

        return '\n'.join(lines)

    def format_playstyle(self, stats: PlaystyleStats) -> str:
        """Format playstyle for Discord."""
        pref_emoji = {
            "attacker": "⚔️",
            "defender": "🛡️",
            "balanced": "⚖️"
        }

        return (
            f"**{stats.player_name}** - Playstyle Analysis\n"
            f"• Preference: {pref_emoji.get(stats.preference, '')} {stats.preference.title()} "
            f"({stats.preference_strength:.0f}% lean)\n"
            f"• Attack: {stats.attack_dpm:.1f} DPM, {stats.attack_kd:.2f} K/D ({stats.attack_rounds} rounds)\n"
            f"• Defense: {stats.defense_dpm:.1f} DPM, {stats.defense_kd:.2f} K/D ({stats.defense_rounds} rounds)"
        )

    def format_awards(self, awards: List[FunAward]) -> str:
        """Format awards for Discord embed."""
        if not awards:
            return "No awards this session"

        lines = []
        for award in awards:
            lines.append(f"{award.emoji} **{award.award_name}**: {award.player_name}")
            lines.append(f"   {award.description}")

        return '\n'.join(lines)
