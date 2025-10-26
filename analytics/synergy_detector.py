"""
Synergy Detection Algorithm
Calculates how well two players perform together vs apart

This module analyzes historical match data to identify player pairs that
perform significantly better when playing together on the same team.
"""

import sqlite3
import aiosqlite
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import logging
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class PlayerPerformance:
    """Individual player performance metrics"""
    kills: float = 0.0
    deaths: float = 0.0
    damage: float = 0.0
    objectives: int = 0
    revives: int = 0
    kd_ratio: float = 0.0
    dpm: float = 0.0
    games_played: int = 0
    wins: int = 0
    win_rate: float = 0.0


@dataclass
class SynergyMetrics:
    """Synergy metrics between two players"""
    # Player identifiers
    player_a_guid: str
    player_b_guid: str
    player_a_name: str
    player_b_name: str
    
    # Games statistics
    games_together: int
    games_same_team: int
    wins_together: int
    losses_together: int
    
    # Win rate analysis
    win_rate_together: float
    player_a_solo_win_rate: float
    player_b_solo_win_rate: float
    expected_win_rate: float
    win_rate_boost: float
    
    # Performance analysis
    performance_boost_a: float
    performance_boost_b: float
    performance_boost_avg: float
    
    # Overall synergy
    synergy_score: float
    confidence: float
    
    # Timestamps
    last_played_together: Optional[datetime] = None


class SynergyDetector:
    """Detects player synergies from historical data"""
    
    def __init__(self, db_path: str = 'etlegacy_production.db'):
        self.db_path = db_path
        self.min_games_threshold = 10  # Minimum games together for valid synergy
        
    async def calculate_synergy(
        self, 
        player_a_guid: str, 
        player_b_guid: str
    ) -> Optional[SynergyMetrics]:
        """
        Calculate synergy between two players
        
        Args:
            player_a_guid: First player's GUID
            player_b_guid: Second player's GUID
            
        Returns:
            SynergyMetrics object or None if insufficient data
        """
        # Ensure alphabetical ordering for consistency
        if player_a_guid > player_b_guid:
            player_a_guid, player_b_guid = player_b_guid, player_a_guid
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Get player names
                player_a_name = await self._get_player_name(db, player_a_guid)
                player_b_name = await self._get_player_name(db, player_b_guid)
                
                if not player_a_name or not player_b_name:
                    logger.warning(f"Could not find player names for {player_a_guid}, {player_b_guid}")
                    return None
                
                # Get games together on same team
                games_together = await self._get_games_together(db, player_a_guid, player_b_guid)
                
                if len(games_together) < self.min_games_threshold:
                    logger.info(f"Insufficient games together: {len(games_together)} < {self.min_games_threshold}")
                    return None
                
                # Calculate win rate together
                wins_together = sum(1 for g in games_together if g['won'])
                win_rate_together = wins_together / len(games_together) if games_together else 0.0
                
                # Get solo performance for each player
                player_a_solo = await self._get_solo_performance(db, player_a_guid, player_b_guid)
                player_b_solo = await self._get_solo_performance(db, player_b_guid, player_a_guid)
                
                # Calculate expected win rate (average of solo win rates)
                expected_win_rate = (player_a_solo.win_rate + player_b_solo.win_rate) / 2
                
                # Calculate win rate boost
                win_rate_boost = win_rate_together - expected_win_rate
                
                # Get performance when together
                player_a_together = await self._get_performance_together(
                    db, player_a_guid, player_b_guid, games_together
                )
                player_b_together = await self._get_performance_together(
                    db, player_b_guid, player_a_guid, games_together
                )
                
                # Calculate performance boost (K/D ratio improvement)
                perf_boost_a = 0.0
                if player_a_solo.kd_ratio > 0:
                    perf_boost_a = ((player_a_together.kd_ratio - player_a_solo.kd_ratio) / 
                                   player_a_solo.kd_ratio) * 100
                
                perf_boost_b = 0.0
                if player_b_solo.kd_ratio > 0:
                    perf_boost_b = ((player_b_together.kd_ratio - player_b_solo.kd_ratio) / 
                                   player_b_solo.kd_ratio) * 100
                
                perf_boost_avg = (perf_boost_a + perf_boost_b) / 2
                
                # Calculate overall synergy score (weighted combination)
                # 60% win rate boost, 40% performance boost
                synergy_score = (win_rate_boost * 0.6) + ((perf_boost_avg / 100) * 0.4)
                
                # Calculate confidence level based on sample size
                confidence = min(len(games_together) / 50, 1.0)  # 50 games = 100% confidence
                
                # Get last time played together
                last_played = games_together[0]['timestamp'] if games_together else None
                
                return SynergyMetrics(
                    player_a_guid=player_a_guid,
                    player_b_guid=player_b_guid,
                    player_a_name=player_a_name,
                    player_b_name=player_b_name,
                    games_together=len(games_together),
                    games_same_team=len(games_together),
                    wins_together=wins_together,
                    losses_together=len(games_together) - wins_together,
                    win_rate_together=win_rate_together,
                    player_a_solo_win_rate=player_a_solo.win_rate,
                    player_b_solo_win_rate=player_b_solo.win_rate,
                    expected_win_rate=expected_win_rate,
                    win_rate_boost=win_rate_boost,
                    performance_boost_a=perf_boost_a,
                    performance_boost_b=perf_boost_b,
                    performance_boost_avg=perf_boost_avg,
                    synergy_score=synergy_score,
                    confidence=confidence,
                    last_played_together=last_played
                )
                
        except Exception as e:
            logger.error(f"Error calculating synergy: {e}", exc_info=True)
            return None
    
    async def _get_player_name(self, db: aiosqlite.Connection, guid: str) -> Optional[str]:
        """Get most recent player name from aliases"""
        cursor = await db.execute("""
            SELECT player_name 
            FROM player_aliases 
            WHERE player_guid = ? 
            ORDER BY last_seen DESC 
            LIMIT 1
        """, (guid,))
        
        row = await cursor.fetchone()
        return row[0] if row else None
    
    async def _get_games_together(
        self, 
        db: aiosqlite.Connection, 
        player_a_guid: str, 
        player_b_guid: str
    ) -> List[Dict]:
        """Get all games where both players were on same team"""
        cursor = await db.execute("""
            SELECT 
                s.id as session_id,
                s.session_date as timestamp,
                s.map_name,
                pa.team as player_a_team,
                pb.team as player_b_team
            FROM sessions s
            JOIN player_comprehensive_stats pa ON s.id = pa.session_id
            JOIN player_comprehensive_stats pb ON s.id = pb.session_id
            WHERE pa.player_guid = ?
              AND pb.player_guid = ?
              AND pa.team = pb.team
            ORDER BY s.session_date DESC
        """, (player_a_guid, player_b_guid))
        
        rows = await cursor.fetchall()
        
        games = []
        for row in rows:
            games.append({
                'session_id': row[0],
                'timestamp': datetime.fromisoformat(row[1]) if row[1] else None,
                'map_name': row[2],
                'team': row[3],
                'won': False  # TODO: Add win tracking in future
            })
        
        return games
    
    async def _get_solo_performance(
        self, 
        db: aiosqlite.Connection, 
        player_guid: str,
        exclude_with_guid: str
    ) -> PlayerPerformance:
        """Get player's performance when NOT playing with specified partner"""
        cursor = await db.execute("""
            SELECT 
                AVG(p.kills) as avg_kills,
                AVG(p.deaths) as avg_deaths,
                AVG(p.damage_given) as avg_damage,
                AVG(p.objectives_completed) as avg_objectives,
                AVG(p.revives_given) as avg_revives,
                AVG(p.kd_ratio) as avg_kd,
                AVG(p.dpm) as avg_dpm,
                COUNT(*) as games,
                0 as wins
            FROM player_comprehensive_stats p
            JOIN sessions s ON p.session_id = s.id
            WHERE p.player_guid = ?
              AND p.session_id NOT IN (
                  SELECT session_id 
                  FROM player_comprehensive_stats 
                  WHERE player_guid = ?
              )
        """, (player_guid, exclude_with_guid))
        
        row = await cursor.fetchone()
        
        if not row or not row[7]:  # No games found
            return PlayerPerformance()
        
        return PlayerPerformance(
            kills=row[0] or 0.0,
            deaths=row[1] or 0.0,
            damage=row[2] or 0.0,
            objectives=int(row[3] or 0),
            revives=int(row[4] or 0),
            kd_ratio=row[5] or 0.0,
            dpm=row[6] or 0.0,
            games_played=row[7] or 0,
            wins=row[8] or 0,
            win_rate=(row[8] / row[7]) if row[7] else 0.0
        )
    
    async def _get_performance_together(
        self,
        db: aiosqlite.Connection,
        player_guid: str,
        partner_guid: str,
        games_together: List[Dict]
    ) -> PlayerPerformance:
        """Get player's performance when playing WITH specified partner"""
        session_ids = [g['session_id'] for g in games_together]
        
        if not session_ids:
            return PlayerPerformance()
        
        placeholders = ','.join('?' * len(session_ids))
        
        cursor = await db.execute(f"""
            SELECT 
                AVG(kills) as avg_kills,
                AVG(deaths) as avg_deaths,
                AVG(damage_given) as avg_damage,
                AVG(objectives_completed) as avg_objectives,
                AVG(revives_given) as avg_revives,
                AVG(kd_ratio) as avg_kd,
                AVG(dpm) as avg_dpm,
                COUNT(*) as games
            FROM player_comprehensive_stats
            WHERE player_guid = ?
              AND session_id IN ({placeholders})
        """, (player_guid, *session_ids))
        
        row = await cursor.fetchone()
        
        if not row or not row[7]:
            return PlayerPerformance()
        
        return PlayerPerformance(
            kills=row[0] or 0.0,
            deaths=row[1] or 0.0,
            damage=row[2] or 0.0,
            objectives=int(row[3] or 0),
            revives=int(row[4] or 0),
            kd_ratio=row[5] or 0.0,
            dpm=row[6] or 0.0,
            games_played=row[7] or 0
        )
    
    async def save_synergy(self, synergy: SynergyMetrics) -> bool:
        """Save or update synergy metrics in database"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT OR REPLACE INTO player_synergies (
                        player_a_guid, player_b_guid,
                        games_together, games_same_team,
                        wins_together, losses_together,
                        win_rate_together,
                        player_a_solo_win_rate, player_b_solo_win_rate,
                        expected_win_rate, win_rate_boost,
                        player_a_performance_together, player_b_performance_together,
                        player_a_performance_solo, player_b_performance_solo,
                        performance_boost_a, performance_boost_b, performance_boost_avg,
                        synergy_score, confidence_level,
                        last_calculated, last_played_together
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                """, (
                    synergy.player_a_guid, synergy.player_b_guid,
                    synergy.games_together, synergy.games_same_team,
                    synergy.wins_together, synergy.losses_together,
                    synergy.win_rate_together,
                    synergy.player_a_solo_win_rate, synergy.player_b_solo_win_rate,
                    synergy.expected_win_rate, synergy.win_rate_boost,
                    0.0, 0.0, 0.0, 0.0,  # Placeholder performance values
                    synergy.performance_boost_a, synergy.performance_boost_b,
                    synergy.performance_boost_avg,
                    synergy.synergy_score, synergy.confidence,
                    synergy.last_played_together.isoformat() if synergy.last_played_together else None
                ))
                
                await db.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error saving synergy: {e}", exc_info=True)
            return False
    
    async def calculate_all_synergies(self, progress_callback=None) -> int:
        """
        Calculate synergies for all player pairs
        
        Args:
            progress_callback: Optional callback function(current, total, player_a, player_b)
            
        Returns:
            Number of synergies calculated
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Get all unique player GUIDs
                cursor = await db.execute("""
                    SELECT DISTINCT player_guid
                    FROM player_comprehensive_stats
                    ORDER BY player_guid
                """)
                
                players = [row[0] for row in await cursor.fetchall()]
                
                logger.info(f"Found {len(players)} unique players")
                
                # Generate all pairs
                pairs = []
                for i, player_a in enumerate(players):
                    for player_b in players[i+1:]:
                        pairs.append((player_a, player_b))
                
                logger.info(f"Calculating {len(pairs)} player pair synergies...")
                
                calculated = 0
                for idx, (player_a, player_b) in enumerate(pairs):
                    if progress_callback:
                        progress_callback(idx + 1, len(pairs), player_a, player_b)
                    
                    synergy = await self.calculate_synergy(player_a, player_b)
                    
                    if synergy:
                        await self.save_synergy(synergy)
                        calculated += 1
                
                logger.info(f"Successfully calculated {calculated} synergies")
                return calculated
                
        except Exception as e:
            logger.error(f"Error in calculate_all_synergies: {e}", exc_info=True)
            return 0
    
    async def get_best_duos(self, limit: int = 10) -> List[SynergyMetrics]:
        """Get top player duos by synergy score"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT 
                        player_a_guid, player_b_guid,
                        games_together, games_same_team,
                        wins_together, losses_together,
                        win_rate_together,
                        player_a_solo_win_rate, player_b_solo_win_rate,
                        expected_win_rate, win_rate_boost,
                        performance_boost_a, performance_boost_b, performance_boost_avg,
                        synergy_score, confidence_level,
                        last_played_together
                    FROM player_synergies
                    WHERE games_same_team >= ?
                    ORDER BY synergy_score DESC
                    LIMIT ?
                """, (self.min_games_threshold, limit))
                
                rows = await cursor.fetchall()
                
                duos = []
                for row in rows:
                    # Get player names
                    player_a_name = await self._get_player_name(db, row[0])
                    player_b_name = await self._get_player_name(db, row[1])
                    
                    duos.append(SynergyMetrics(
                        player_a_guid=row[0],
                        player_b_guid=row[1],
                        player_a_name=player_a_name or "Unknown",
                        player_b_name=player_b_name or "Unknown",
                        games_together=row[2],
                        games_same_team=row[3],
                        wins_together=row[4],
                        losses_together=row[5],
                        win_rate_together=row[6],
                        player_a_solo_win_rate=row[7],
                        player_b_solo_win_rate=row[8],
                        expected_win_rate=row[9],
                        win_rate_boost=row[10],
                        performance_boost_a=row[11],
                        performance_boost_b=row[12],
                        performance_boost_avg=row[13],
                        synergy_score=row[14],
                        confidence=row[15],
                        last_played_together=datetime.fromisoformat(row[16]) if row[16] else None
                    ))
                
                return duos
                
        except Exception as e:
            logger.error(f"Error getting best duos: {e}", exc_info=True)
            return []


# CLI for testing
if __name__ == '__main__':
    import sys
    
    async def main():
        detector = SynergyDetector()
        
        if len(sys.argv) > 1 and sys.argv[1] == 'calculate_all':
            print("Calculating all player synergies...")
            
            def progress(current, total, player_a, player_b):
                print(f"   [{current}/{total}] Processing pair: {player_a[:8]}... + {player_b[:8]}...")
            
            count = await detector.calculate_all_synergies(progress_callback=progress)
            print(f"\nCalculated {count} synergies successfully!")
            
        elif len(sys.argv) > 1 and sys.argv[1] == 'best_duos':
            print("Top 10 Player Duos:\n")
            duos = await detector.get_best_duos(10)
            
            for idx, duo in enumerate(duos, 1):
                print(f"{idx}. {duo.player_a_name} + {duo.player_b_name}")
                print(f"   Synergy: {duo.synergy_score:.3f}")
                print(f"   Games: {duo.games_same_team} | Win Rate: {duo.win_rate_together:.1%}")
                print(f"   Win Boost: {duo.win_rate_boost:+.1%} | Perf Boost: {duo.performance_boost_avg:+.1f}%")
                print()
        
        else:
            print("Usage:")
            print("  python synergy_detector.py calculate_all   # Calculate all synergies")
            print("  python synergy_detector.py best_duos       # Show top 10 duos")
    
    asyncio.run(main())
