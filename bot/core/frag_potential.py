"""
Frag Potential & Playstyle Detection System
============================================

This module provides advanced player performance metrics:

1. FragPotential (FP) - Damage output while alive
   Formula: (damage_given / time_alive_seconds) * 60
   Where: time_alive = time_played - time_dead
   
   Interpretation:
   - Higher FP = More impactful while alive (dealing damage efficiently)
   - Measures "damage per minute while actually playing"
   - Unlike standard DPM, doesn't penalize dying as much
   
2. Playstyle Classification - Categorizes players based on their stats:
   - 🔥 Fragger    - High damage dealer, good K/D, efficient killer
   - 💀 Slayer     - Kill-focused, high kill count, aggressive
   - 🛡️ Tank       - Absorbs damage, high survival, team anchor
   - 💉 Medic      - Support-focused, high revives, team sustainer
   - 🎯 Sniper     - Precision player, high headshot %, patient
   - 🏃 Rusher     - Aggressive pusher, high deaths, high activity
   - 🎖️ Objective  - Objective-focused, completes/destroys objectives
   - ⚔️ Balanced   - Well-rounded player, no dominant trait
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple

logger = logging.getLogger("bot.core.frag_potential")


class Playstyle(Enum):
    """Player playstyle categories"""
    FRAGGER = ("🔥", "Fragger", "#FF6B35")      # Orange-red
    SLAYER = ("💀", "Slayer", "#FF4757")         # Red
    TANK = ("🛡️", "Tank", "#3498DB")             # Blue
    MEDIC = ("💉", "Medic", "#2ECC71")           # Green
    SNIPER = ("🎯", "Sniper", "#9B59B6")         # Purple
    RUSHER = ("🏃", "Rusher", "#F39C12")         # Orange
    OBJECTIVE = ("🎖️", "Objective", "#1ABC9C")   # Teal
    BALANCED = ("⚔️", "Balanced", "#95A5A6")     # Gray
    
    @property
    def emoji(self) -> str:
        return self.value[0]
    
    @property
    def name_display(self) -> str:
        return self.value[1]
    
    @property
    def color(self) -> str:
        return self.value[2]


@dataclass
class PlayerMetrics:
    """Comprehensive player metrics for analysis"""
    player_name: str
    player_guid: str
    
    # Core stats
    kills: int
    deaths: int
    damage_given: int
    damage_received: int
    
    # Time stats (in seconds)
    time_played_seconds: int
    time_dead_ratio: float  # Percentage (0-100)
    time_dead_seconds: float = 0.0
    time_dead_minutes: float = 0.0
    
    # Calculated time
    time_alive_seconds: float = 0.0
    
    # Support stats
    revives_given: int = 0
    headshot_kills: int = 0
    
    # Objective stats
    objectives_completed: int = 0
    objectives_destroyed: int = 0
    objectives_stolen: int = 0
    objectives_returned: int = 0
    
    # Computed metrics
    frag_potential: float = 0.0
    kd_ratio: float = 0.0
    damage_ratio: float = 0.0
    headshot_percentage: float = 0.0
    playstyle: Playstyle = Playstyle.BALANCED
    playstyle_confidence: float = 0.0
    
    def __post_init__(self):
        """Calculate derived metrics after initialization"""
        self.calculate_metrics()
    
    def calculate_metrics(self):
        """Calculate all derived metrics"""
        # Time alive calculation (prefer raw minutes/seconds over ratio)
        time_dead_seconds = 0.0
        if self.time_dead_seconds and self.time_dead_seconds > 0:
            time_dead_seconds = float(self.time_dead_seconds)
        elif self.time_dead_minutes and self.time_dead_minutes > 0:
            time_dead_seconds = float(self.time_dead_minutes) * 60.0
        elif self.time_dead_ratio and self.time_played_seconds > 0:
            time_dead_seconds = (self.time_dead_ratio / 100.0) * self.time_played_seconds

        # Clamp to sane bounds
        if time_dead_seconds < 0:
            time_dead_seconds = 0.0
        if self.time_played_seconds > 0 and time_dead_seconds > self.time_played_seconds:
            time_dead_seconds = float(self.time_played_seconds)

        # If we had raw dead time, recompute ratio for consistency
        if self.time_played_seconds > 0 and (self.time_dead_seconds or self.time_dead_minutes):
            self.time_dead_ratio = (time_dead_seconds / self.time_played_seconds) * 100.0

        self.time_alive_seconds = max(1, self.time_played_seconds - time_dead_seconds)
        
        # FragPotential: DPM while alive
        if self.time_alive_seconds > 0:
            self.frag_potential = (self.damage_given / self.time_alive_seconds) * 60
        else:
            self.frag_potential = 0.0
        
        # K/D Ratio
        self.kd_ratio = self.kills / max(1, self.deaths)
        
        # Damage Ratio (given/received)
        self.damage_ratio = self.damage_given / max(1, self.damage_received)
        
        # Headshot percentage
        if self.kills > 0:
            self.headshot_percentage = (self.headshot_kills / self.kills) * 100
        else:
            self.headshot_percentage = 0.0


class FragPotentialCalculator:
    """
    Calculates FragPotential and determines player playstyles
    """
    
    # Thresholds for playstyle detection (can be tuned)
    THRESHOLDS = {
        # FragPotential thresholds
        'fp_high': 900,        # High damage output while alive
        'fp_medium': 600,      # Medium damage output
        
        # K/D thresholds
        'kd_high': 1.5,        # Very good K/D
        'kd_good': 1.2,        # Good K/D
        'kd_low': 0.8,         # Below average K/D
        
        # Deaths ratio (compared to session average)
        'deaths_high_mult': 1.3,  # 30% more deaths than average
        
        # Support thresholds
        'revives_high': 10,    # High revive count for session
        'revives_per_round': 2, # Revives per round threshold
        
        # Headshot percentage
        'hs_high': 25,         # High headshot percentage
        'hs_sniper': 35,       # Sniper-level headshot percentage
        
        # Damage ratio
        'dmg_ratio_tank': 0.7,  # Takes more than gives (tank behavior)
        'dmg_ratio_high': 1.5,  # Gives much more than takes
        
        # Objective count
        'obj_high': 3,         # High objective interactions
    }
    
    @classmethod
    def calculate_frag_potential(
        cls,
        damage_given: int,
        time_played_seconds: int,
        time_dead_ratio: float = 0.0,
        time_dead_seconds: float = None,
        time_dead_minutes: float = None,
    ) -> float:
        """
        Calculate FragPotential for a player
        
        Args:
            damage_given: Total damage dealt
            time_played_seconds: Total time in round/session
            time_dead_ratio: Percentage of time spent dead (0-100)
            
        Returns:
            FragPotential value (damage per minute while alive)
        """
        if time_played_seconds <= 0:
            return 0.0
        
        # Prefer raw dead time when available (minutes/seconds)
        td_seconds = None
        if time_dead_seconds is not None and time_dead_seconds > 0:
            td_seconds = float(time_dead_seconds)
        elif time_dead_minutes is not None and time_dead_minutes > 0:
            td_seconds = float(time_dead_minutes) * 60.0

        # Fall back to ratio when raw values aren't provided
        if td_seconds is None:
            # Validate time_dead_ratio - game server can report buggy values > 100%
            # If ratio is invalid (> 100%) or extremely high (> 95%), return 0
            # because we can't calculate meaningful FP with < 5% alive time
            if time_dead_ratio > 95 or time_dead_ratio < 0:
                return 0.0
            td_seconds = (time_dead_ratio / 100.0) * time_played_seconds

        if td_seconds < 0:
            td_seconds = 0.0
        if td_seconds > time_played_seconds and time_played_seconds > 0:
            td_seconds = float(time_played_seconds)

        # Calculate time alive
        time_dead_seconds = td_seconds
        time_alive_seconds = max(1, time_played_seconds - time_dead_seconds)
        
        # FragPotential = DPM while alive
        frag_potential = (damage_given / time_alive_seconds) * 60
        
        return round(frag_potential, 1)
    
    @classmethod
    def determine_playstyle(
        cls,
        metrics: PlayerMetrics,
        session_avg_deaths: float = None,
        session_avg_revives: float = None,
        rounds_played: int = 1
    ) -> Tuple[Playstyle, float]:
        """
        Determine a player's playstyle based on their metrics
        
        Args:
            metrics: PlayerMetrics object with all stats
            session_avg_deaths: Average deaths in session (for comparison)
            session_avg_revives: Average revives in session
            rounds_played: Number of rounds played
            
        Returns:
            Tuple of (Playstyle, confidence_score 0.0-1.0)
        """
        scores = {style: 0.0 for style in Playstyle}
        
        fp = metrics.frag_potential
        kd = metrics.kd_ratio
        dmg_ratio = metrics.damage_ratio
        hs_pct = metrics.headshot_percentage
        revives = metrics.revives_given
        total_objectives = (
            metrics.objectives_completed + 
            metrics.objectives_destroyed + 
            metrics.objectives_stolen + 
            metrics.objectives_returned
        )
        
        # ═══════════════════════════════════════════════════════
        # FRAGGER: High damage dealer, efficient killer
        # ═══════════════════════════════════════════════════════
        if fp >= cls.THRESHOLDS['fp_high'] and kd >= cls.THRESHOLDS['kd_good']:
            scores[Playstyle.FRAGGER] += 0.4
        if fp >= cls.THRESHOLDS['fp_medium'] and kd >= cls.THRESHOLDS['kd_high']:
            scores[Playstyle.FRAGGER] += 0.3
        if dmg_ratio >= cls.THRESHOLDS['dmg_ratio_high']:
            scores[Playstyle.FRAGGER] += 0.2
        
        # ═══════════════════════════════════════════════════════
        # SLAYER: Kill-focused, high kill count
        # ═══════════════════════════════════════════════════════
        if metrics.kills >= 20 and kd >= cls.THRESHOLDS['kd_good']:
            scores[Playstyle.SLAYER] += 0.4
        if metrics.kills >= 30:
            scores[Playstyle.SLAYER] += 0.3
        if fp >= cls.THRESHOLDS['fp_medium']:
            scores[Playstyle.SLAYER] += 0.2
        
        # ═══════════════════════════════════════════════════════
        # TANK: Absorbs damage, high survival
        # ═══════════════════════════════════════════════════════
        if dmg_ratio <= cls.THRESHOLDS['dmg_ratio_tank']:
            scores[Playstyle.TANK] += 0.3
        if metrics.damage_received > metrics.damage_given:
            scores[Playstyle.TANK] += 0.2
        if metrics.time_dead_ratio < 20:  # Low death time
            scores[Playstyle.TANK] += 0.2
        if kd < cls.THRESHOLDS['kd_good'] and metrics.damage_received > 3000:
            scores[Playstyle.TANK] += 0.2
        
        # ═══════════════════════════════════════════════════════
        # MEDIC: Support-focused, high revives
        # ═══════════════════════════════════════════════════════
        revives_per_round = revives / max(1, rounds_played)
        if revives >= cls.THRESHOLDS['revives_high']:
            scores[Playstyle.MEDIC] += 0.5
        if revives_per_round >= cls.THRESHOLDS['revives_per_round']:
            scores[Playstyle.MEDIC] += 0.3
        if session_avg_revives and revives > session_avg_revives * 1.5:
            scores[Playstyle.MEDIC] += 0.2
        
        # ═══════════════════════════════════════════════════════
        # SNIPER: Precision player, high headshots
        # ═══════════════════════════════════════════════════════
        if hs_pct >= cls.THRESHOLDS['hs_sniper']:
            scores[Playstyle.SNIPER] += 0.5
        if hs_pct >= cls.THRESHOLDS['hs_high'] and kd >= cls.THRESHOLDS['kd_good']:
            scores[Playstyle.SNIPER] += 0.3
        if metrics.deaths < 10 and hs_pct >= cls.THRESHOLDS['hs_high']:
            scores[Playstyle.SNIPER] += 0.2
        
        # ═══════════════════════════════════════════════════════
        # RUSHER: Aggressive, high deaths, high activity
        # ═══════════════════════════════════════════════════════
        if session_avg_deaths:
            if metrics.deaths > session_avg_deaths * cls.THRESHOLDS['deaths_high_mult']:
                scores[Playstyle.RUSHER] += 0.3
        if metrics.deaths > 25 and fp >= cls.THRESHOLDS['fp_medium']:
            scores[Playstyle.RUSHER] += 0.3
        if kd < cls.THRESHOLDS['kd_low'] and metrics.damage_given > 2000:
            scores[Playstyle.RUSHER] += 0.2
        if metrics.time_dead_ratio > 35:  # High death time
            scores[Playstyle.RUSHER] += 0.2
        
        # ═══════════════════════════════════════════════════════
        # OBJECTIVE: Objective-focused player
        # ═══════════════════════════════════════════════════════
        if total_objectives >= cls.THRESHOLDS['obj_high']:
            scores[Playstyle.OBJECTIVE] += 0.5
        if metrics.objectives_completed >= 2:
            scores[Playstyle.OBJECTIVE] += 0.3
        if metrics.objectives_destroyed >= 2:
            scores[Playstyle.OBJECTIVE] += 0.2
        
        # ═══════════════════════════════════════════════════════
        # BALANCED: Default if no strong signals
        # ═══════════════════════════════════════════════════════
        # Always give balanced a base score
        scores[Playstyle.BALANCED] = 0.3
        
        # Find the dominant playstyle
        max_score = max(scores.values())
        dominant_style = max(scores, key=scores.get)
        
        # Calculate confidence (normalized)
        total_score = sum(scores.values())
        confidence = max_score / total_score if total_score > 0 else 0.0
        
        # If confidence is too low, default to balanced
        if confidence < 0.25 or max_score < 0.4:
            return Playstyle.BALANCED, 0.5
        
        return dominant_style, min(1.0, confidence)
    
    @classmethod
    async def analyze_session_players(
        cls,
        db_adapter,
        session_ids: List[int],
        session_ids_str: str = None
    ) -> List[PlayerMetrics]:
        """
        Analyze all players in a session and return their metrics

        Args:
            db_adapter: Database adapter for queries
            session_ids: List of round IDs in the session
            session_ids_str: Deprecated parameter (kept for compatibility)

        Returns:
            List of PlayerMetrics for all players, sorted by FragPotential
        """
        # Generate placeholders for parameterized query
        placeholders = ','.join(['?' for _ in session_ids])

        # Query all player stats for the session - using f-string for placeholder substitution
        query = f"""
            SELECT
                p.player_name,
                p.player_guid,
                SUM(p.kills) as kills,
                SUM(p.deaths) as deaths,
                SUM(p.damage_given) as damage_given,
                SUM(p.damage_received) as damage_received,
                SUM(p.time_played_seconds) as time_played,
                SUM(COALESCE(p.time_dead_minutes, 0)) as time_dead_minutes,
                SUM(p.revives_given) as revives,
                SUM(p.headshot_kills) as headshots,
                SUM(p.objectives_completed) as obj_completed,
                SUM(p.objectives_destroyed) as obj_destroyed,
                SUM(p.objectives_stolen) as obj_stolen,
                SUM(p.objectives_returned) as obj_returned,
                COUNT(DISTINCT p.round_id) as rounds_played
            FROM player_comprehensive_stats p
            WHERE p.round_id IN ({placeholders})
            GROUP BY p.player_guid, p.player_name
            ORDER BY SUM(p.damage_given) DESC
        """

        rows = await db_adapter.fetch_all(query, tuple(session_ids))
        
        if not rows:
            return []
        
        # Calculate session averages for comparison
        total_deaths = sum(row[3] or 0 for row in rows)
        total_revives = sum(row[8] or 0 for row in rows)
        player_count = len(rows)
        
        avg_deaths = total_deaths / player_count if player_count > 0 else 0
        avg_revives = total_revives / player_count if player_count > 0 else 0
        
        # Build PlayerMetrics for each player
        players = []
        for row in rows:
            time_played_seconds = row[6] or 0
            time_dead_minutes = row[7] or 0
            time_dead_seconds = time_dead_minutes * 60.0
            time_dead_ratio = (
                (time_dead_seconds / time_played_seconds) * 100.0
                if time_played_seconds > 0
                else 0.0
            )

            metrics = PlayerMetrics(
                player_name=row[0] or "Unknown",
                player_guid=row[1] or "",
                kills=row[2] or 0,
                deaths=row[3] or 0,
                damage_given=row[4] or 0,
                damage_received=row[5] or 0,
                time_played_seconds=time_played_seconds,
                time_dead_ratio=time_dead_ratio,
                time_dead_seconds=time_dead_seconds,
                time_dead_minutes=time_dead_minutes,
                revives_given=row[8] or 0,
                headshot_kills=row[9] or 0,
                objectives_completed=row[10] or 0,
                objectives_destroyed=row[11] or 0,
                objectives_stolen=row[12] or 0,
                objectives_returned=row[13] or 0,
            )
            
            rounds_played = row[14] or 1
            
            # Determine playstyle
            playstyle, confidence = cls.determine_playstyle(
                metrics,
                session_avg_deaths=avg_deaths,
                session_avg_revives=avg_revives,
                rounds_played=rounds_played
            )
            metrics.playstyle = playstyle
            metrics.playstyle_confidence = confidence
            
            players.append(metrics)
        
        # Sort by FragPotential (highest first)
        players.sort(key=lambda p: p.frag_potential, reverse=True)
        
        return players


def get_playstyle_description(playstyle: Playstyle) -> str:
    """Get a description of what each playstyle means"""
    descriptions = {
        Playstyle.FRAGGER: "High damage dealer with efficient kills",
        Playstyle.SLAYER: "Kill-focused player, stacks bodies",
        Playstyle.TANK: "Absorbs damage, anchors the team",
        Playstyle.MEDIC: "Support player, keeps team alive",
        Playstyle.SNIPER: "Precision player, high headshot rate",
        Playstyle.RUSHER: "Aggressive pusher, high activity",
        Playstyle.OBJECTIVE: "Mission-focused, completes objectives",
        Playstyle.BALANCED: "Well-rounded, adaptable player",
    }
    return descriptions.get(playstyle, "Unknown playstyle")
