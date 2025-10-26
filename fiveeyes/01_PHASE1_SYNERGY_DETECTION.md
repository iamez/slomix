# 📊 Phase 1: Synergy Detection System

**Duration:** Weeks 1-3  
**Complexity:** ⭐⭐ Medium  
**Risk Level:** 🟢 Low  
**Dependencies:** None (uses existing data)

---

## 🎯 Goal

Build a system that identifies which players perform better together by analyzing 2 years of historical match data.

---

## 📋 Week-by-Week Breakdown

### **Week 1: Database Setup & Core Algorithm**

#### Day 1-2: Database Schema
Create `player_synergies` table:

```sql
-- Migration script: tools/migrations/001_create_player_synergies.py

import sqlite3

def create_synergies_table():
    conn = sqlite3.connect('etlegacy_production.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_synergies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_a_guid TEXT NOT NULL,
            player_b_guid TEXT NOT NULL,
            games_together INTEGER DEFAULT 0,
            games_same_team INTEGER DEFAULT 0,
            games_opposite_team INTEGER DEFAULT 0,
            wins_together INTEGER DEFAULT 0,
            losses_together INTEGER DEFAULT 0,
            win_rate_together REAL DEFAULT 0,
            win_rate_a_solo REAL DEFAULT 0,
            win_rate_b_solo REAL DEFAULT 0,
            win_rate_boost REAL DEFAULT 0,
            avg_kills_together REAL DEFAULT 0,
            avg_deaths_together REAL DEFAULT 0,
            avg_damage_together REAL DEFAULT 0,
            avg_kills_apart REAL DEFAULT 0,
            avg_deaths_apart REAL DEFAULT 0,
            avg_damage_apart REAL DEFAULT 0,
            performance_boost REAL DEFAULT 0,
            synergy_score REAL DEFAULT 0,
            confidence_level REAL DEFAULT 0,
            last_played_together TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(player_a_guid, player_b_guid)
        )
    ''')
    
    # Create indexes for fast queries
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_synergies_player_a 
        ON player_synergies(player_a_guid)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_synergies_player_b 
        ON player_synergies(player_b_guid)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_synergies_score 
        ON player_synergies(synergy_score DESC)
    ''')
    
    conn.commit()
    conn.close()
    print("✅ player_synergies table created successfully")

if __name__ == '__main__':
    create_synergies_table()
```

#### Day 3-4: Core Synergy Algorithm

Create `analytics/synergy_detector.py`:

```python
"""
Synergy Detection Algorithm
Calculates how well two players perform together vs apart
"""

import sqlite3
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class PlayerPerformance:
    """Individual player performance metrics"""
    kills: float
    deaths: float
    damage: float
    objectives: int
    revives: int
    kd_ratio: float
    dpm: float
    games_played: int

@dataclass
class SynergyMetrics:
    """Synergy metrics between two players"""
    games_together: int
    games_same_team: int
    wins_together: int
    win_rate_together: float
    win_rate_boost: float
    performance_boost: float
    synergy_score: float
    confidence: float

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
        
        Algorithm:
        1. Get all sessions where both played
        2. Split: same team vs opposite teams
        3. Calculate average performance together
        4. Calculate average performance apart (solo)
        5. Compare: boost = (together - apart) / apart
        """
        
        # Get sessions where both players participated
        sessions_together = await self._get_sessions_with_both(
            player_a_guid, player_b_guid
        )
        
        if len(sessions_together) < self.min_games_threshold:
            logger.info(
                f"Insufficient data for {player_a_guid[:8]} + {player_b_guid[:8]}: "
                f"{len(sessions_together)} games (need {self.min_games_threshold})"
            )
            return None
        
        # Split sessions by team alignment
        same_team_sessions = [s for s in sessions_together if s['same_team']]
        opposite_team_sessions = [s for s in sessions_together if not s['same_team']]
        
        if len(same_team_sessions) < 5:
            logger.info(f"Not enough same-team games: {len(same_team_sessions)}")
            return None
        
        # Calculate performance when together on same team
        perf_together_a = await self._calculate_avg_performance(
            player_a_guid, same_team_sessions
        )
        perf_together_b = await self._calculate_avg_performance(
            player_b_guid, same_team_sessions
        )
        
        # Calculate performance when apart (not in same session)
        perf_apart_a = await self._calculate_solo_performance(
            player_a_guid, player_b_guid
        )
        perf_apart_b = await self._calculate_solo_performance(
            player_b_guid, player_a_guid
        )
        
        # Calculate win rates
        wins_together = sum(1 for s in same_team_sessions if s['won'])
        win_rate_together = wins_together / len(same_team_sessions)
        
        # Calculate synergy scores
        performance_boost_a = self._calculate_boost(perf_together_a, perf_apart_a)
        performance_boost_b = self._calculate_boost(perf_together_b, perf_apart_b)
        performance_boost = (performance_boost_a + performance_boost_b) / 2
        
        win_rate_expected = (perf_apart_a.kd_ratio + perf_apart_b.kd_ratio) / 2
        win_rate_boost = win_rate_together - (win_rate_expected * 0.5)  # Normalize
        
        # Overall synergy score (weighted combination)
        synergy_score = (
            performance_boost * 0.6 +  # 60% performance
            win_rate_boost * 0.4       # 40% win rate
        )
        
        # Confidence based on sample size
        confidence = min(len(same_team_sessions) / 50, 1.0)  # Max confidence at 50 games
        
        return SynergyMetrics(
            games_together=len(sessions_together),
            games_same_team=len(same_team_sessions),
            wins_together=wins_together,
            win_rate_together=win_rate_together,
            win_rate_boost=win_rate_boost,
            performance_boost=performance_boost,
            synergy_score=synergy_score,
            confidence=confidence
        )
    
    async def _get_sessions_with_both(
        self, 
        player_a_guid: str, 
        player_b_guid: str
    ) -> List[Dict]:
        """Get all sessions where both players participated"""
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = '''
            SELECT DISTINCT
                s.id as session_id,
                s.session_date,
                s.map_name,
                pa.team as team_a,
                pb.team as team_b,
                CASE WHEN pa.team = pb.team THEN 1 ELSE 0 END as same_team
            FROM sessions s
            JOIN player_comprehensive_stats pa ON s.id = pa.session_id
            JOIN player_comprehensive_stats pb ON s.id = pb.session_id
            WHERE pa.player_guid = ? AND pb.player_guid = ?
            ORDER BY s.session_date DESC
        '''
        
        cursor.execute(query, (player_a_guid, player_b_guid))
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    async def _calculate_avg_performance(
        self, 
        player_guid: str, 
        sessions: List[Dict]
    ) -> PlayerPerformance:
        """Calculate average performance across given sessions"""
        
        if not sessions:
            return PlayerPerformance(0, 0, 0, 0, 0, 0, 0, 0)
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        session_ids = [s['session_id'] for s in sessions]
        placeholders = ','.join('?' * len(session_ids))
        
        query = f'''
            SELECT 
                AVG(kills) as avg_kills,
                AVG(deaths) as avg_deaths,
                AVG(damage_given) as avg_damage,
                AVG(objectives_completed) as avg_objectives,
                AVG(revives_given) as avg_revives,
                AVG(CAST(kills AS REAL) / NULLIF(deaths, 0)) as avg_kd,
                AVG(damage_per_minute) as avg_dpm,
                COUNT(*) as games
            FROM player_comprehensive_stats
            WHERE player_guid = ? AND session_id IN ({placeholders})
        '''
        
        cursor.execute(query, [player_guid] + session_ids)
        row = cursor.fetchone()
        conn.close()
        
        return PlayerPerformance(
            kills=row['avg_kills'] or 0,
            deaths=row['avg_deaths'] or 1,
            damage=row['avg_damage'] or 0,
            objectives=row['avg_objectives'] or 0,
            revives=row['avg_revives'] or 0,
            kd_ratio=row['avg_kd'] or 0,
            dpm=row['avg_dpm'] or 0,
            games_played=row['games'] or 0
        )
    
    async def _calculate_solo_performance(
        self, 
        player_guid: str, 
        exclude_with_guid: str
    ) -> PlayerPerformance:
        """Calculate performance when NOT playing with specific player"""
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = '''
            SELECT 
                AVG(pcs.kills) as avg_kills,
                AVG(pcs.deaths) as avg_deaths,
                AVG(pcs.damage_given) as avg_damage,
                AVG(pcs.objectives_completed) as avg_objectives,
                AVG(pcs.revives_given) as avg_revives,
                AVG(CAST(pcs.kills AS REAL) / NULLIF(pcs.deaths, 0)) as avg_kd,
                AVG(pcs.damage_per_minute) as avg_dpm,
                COUNT(*) as games
            FROM player_comprehensive_stats pcs
            WHERE pcs.player_guid = ?
            AND pcs.session_id NOT IN (
                SELECT DISTINCT session_id 
                FROM player_comprehensive_stats 
                WHERE player_guid = ?
            )
        '''
        
        cursor.execute(query, (player_guid, exclude_with_guid))
        row = cursor.fetchone()
        conn.close()
        
        return PlayerPerformance(
            kills=row['avg_kills'] or 0,
            deaths=row['avg_deaths'] or 1,
            damage=row['avg_damage'] or 0,
            objectives=row['avg_objectives'] or 0,
            revives=row['avg_revives'] or 0,
            kd_ratio=row['avg_kd'] or 0,
            dpm=row['avg_dpm'] or 0,
            games_played=row['games'] or 0
        )
    
    def _calculate_boost(
        self, 
        together: PlayerPerformance, 
        apart: PlayerPerformance
    ) -> float:
        """Calculate performance boost percentage"""
        
        if apart.dpm == 0 or apart.kd_ratio == 0:
            return 0.0
        
        # Weighted boost calculation
        dpm_boost = (together.dpm - apart.dpm) / apart.dpm
        kd_boost = (together.kd_ratio - apart.kd_ratio) / apart.kd_ratio
        
        # Average the boosts
        return (dpm_boost + kd_boost) / 2
    
    async def calculate_all_synergies(self) -> int:
        """
        Calculate synergies for all player pairs
        Returns: number of synergies calculated
        """
        
        # Get all unique players
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT DISTINCT player_guid 
            FROM player_comprehensive_stats
        ''')
        
        players = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        logger.info(f"Calculating synergies for {len(players)} players...")
        
        synergies_calculated = 0
        
        # Calculate for all pairs
        for i, player_a in enumerate(players):
            for player_b in players[i+1:]:  # Only calculate each pair once
                
                synergy = await self.calculate_synergy(player_a, player_b)
                
                if synergy:
                    await self._save_synergy(player_a, player_b, synergy)
                    synergies_calculated += 1
                    
                    if synergies_calculated % 10 == 0:
                        logger.info(f"Calculated {synergies_calculated} synergies...")
        
        logger.info(f"✅ Calculated {synergies_calculated} total synergies")
        return synergies_calculated
    
    async def _save_synergy(
        self, 
        player_a_guid: str, 
        player_b_guid: str, 
        metrics: SynergyMetrics
    ):
        """Save synergy metrics to database"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO player_synergies (
                player_a_guid, player_b_guid,
                games_together, games_same_team, wins_together,
                win_rate_together, win_rate_boost,
                performance_boost, synergy_score, confidence_level,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (
            player_a_guid, player_b_guid,
            metrics.games_together, metrics.games_same_team, metrics.wins_together,
            metrics.win_rate_together, metrics.win_rate_boost,
            metrics.performance_boost, metrics.synergy_score, metrics.confidence
        ))
        
        conn.commit()
        conn.close()
```

#### Day 5: Test Algorithm

Create `tests/test_synergy_detector.py`:

```python
"""Test synergy detection with known player pairs"""

import asyncio
from analytics.synergy_detector import SynergyDetector

async def test_synergy():
    detector = SynergyDetector()
    
    # Test with two known active players (replace with real GUIDs)
    player_a = "YOUR_PLAYER_GUID_1"
    player_b = "YOUR_PLAYER_GUID_2"
    
    synergy = await detector.calculate_synergy(player_a, player_b)
    
    if synergy:
        print(f"✅ Synergy calculated successfully!")
        print(f"   Games together: {synergy.games_together}")
        print(f"   Win rate: {synergy.win_rate_together:.1%}")
        print(f"   Performance boost: {synergy.performance_boost:+.1%}")
        print(f"   Synergy score: {synergy.synergy_score:.3f}")
        print(f"   Confidence: {synergy.confidence:.1%}")
    else:
        print("❌ Not enough data for synergy calculation")

if __name__ == '__main__':
    asyncio.run(test_synergy())
```

---

### **Week 2: Discord Bot Integration**

#### Day 6-7: Add SynergyAnalytics Cog

Update `bot/ultimate_bot.py`:

```python
# Add new Cog (around line 3800, before UltimateETLegacyBot class)

class SynergyAnalytics(commands.Cog):
    """Player chemistry and team synergy analysis"""
    
    def __init__(self, bot):
        self.bot = bot
        self.detector = SynergyDetector(bot.db_path)
    
    @commands.command(name='synergy', aliases=['chemistry', 'duo'])
    async def synergy_command(
        self, 
        ctx, 
        player1: str = None, 
        player2: str = None
    ):
        """
        Show synergy between two players
        
        Usage:
            !synergy @Player1 @Player2
            !synergy PlayerName1 PlayerName2
            !synergy (shows your synergy with most recent partner)
        """
        
        try:
            # Handle Discord mentions
            if ctx.message.mentions:
                if len(ctx.message.mentions) >= 2:
                    player1_guid = await self._get_guid_from_mention(
                        ctx.message.mentions[0].id
                    )
                    player2_guid = await self._get_guid_from_mention(
                        ctx.message.mentions[1].id
                    )
                else:
                    await ctx.send("❌ Please mention two players")
                    return
            
            # Handle player names
            elif player1 and player2:
                player1_guid = await self._get_guid_from_name(player1)
                player2_guid = await self._get_guid_from_name(player2)
            
            else:
                await ctx.send("❌ Usage: `!synergy @Player1 @Player2`")
                return
            
            if not player1_guid or not player2_guid:
                await ctx.send("❌ Could not find one or both players")
                return
            
            # Calculate synergy
            await ctx.send("🔄 Calculating synergy...")
            
            synergy = await self.detector.calculate_synergy(
                player1_guid, player2_guid
            )
            
            if not synergy:
                await ctx.send(
                    "❌ Not enough data. Players need to play at least "
                    f"{self.detector.min_games_threshold} games together."
                )
                return
            
            # Create embed
            embed = await self._create_synergy_embed(
                player1_guid, player2_guid, synergy
            )
            
            await ctx.send(embed=embed)
        
        except Exception as e:
            logger.error(f"Error in synergy command: {e}", exc_info=True)
            await ctx.send(f"❌ Error calculating synergy: {e}")
    
    async def _create_synergy_embed(
        self, 
        player1_guid: str, 
        player2_guid: str, 
        synergy: SynergyMetrics
    ) -> discord.Embed:
        """Create pretty embed for synergy display"""
        
        # Get player names
        name1 = await self._get_player_name(player1_guid)
        name2 = await self._get_player_name(player2_guid)
        
        # Determine synergy rating
        if synergy.synergy_score > 0.15:
            rating = "🔥 Excellent"
            color = 0x00FF00
        elif synergy.synergy_score > 0.05:
            rating = "✅ Good"
            color = 0x00FF00
        elif synergy.synergy_score > -0.05:
            rating = "➖ Neutral"
            color = 0xFFFF00
        else:
            rating = "⚠️ Poor"
            color = 0xFF0000
        
        embed = discord.Embed(
            title=f"⚔️ Player Synergy: {name1} + {name2}",
            description=f"**Overall Rating:** {rating}",
            color=color
        )
        
        # Stats
        embed.add_field(
            name="📊 Games Together",
            value=f"{synergy.games_same_team} games on same team\n"
                  f"{synergy.games_together} total games",
            inline=True
        )
        
        embed.add_field(
            name="🏆 Win Rate",
            value=f"{synergy.win_rate_together:.1%}\n"
                  f"({synergy.wins_together}W-{synergy.games_same_team - synergy.wins_together}L)",
            inline=True
        )
        
        boost_emoji = "📈" if synergy.performance_boost > 0 else "📉"
        embed.add_field(
            name=f"{boost_emoji} Performance Boost",
            value=f"{synergy.performance_boost:+.1%}",
            inline=True
        )
        
        embed.add_field(
            name="💯 Synergy Score",
            value=f"{synergy.synergy_score:.3f}",
            inline=True
        )
        
        embed.add_field(
            name="🎯 Confidence",
            value=f"{synergy.confidence:.0%}",
            inline=True
        )
        
        # Interpretation
        if synergy.performance_boost > 0.1:
            interpretation = "These players perform significantly better together!"
        elif synergy.performance_boost > 0:
            interpretation = "These players have slight positive synergy."
        else:
            interpretation = "These players may work better with different teammates."
        
        embed.add_field(
            name="📝 Analysis",
            value=interpretation,
            inline=False
        )
        
        embed.set_footer(
            text=f"Based on {synergy.games_same_team} games • "
                 f"{synergy.confidence:.0%} confidence"
        )
        
        return embed
    
    async def _get_guid_from_mention(self, discord_id: int) -> Optional[str]:
        """Get player GUID from Discord mention"""
        async with aiosqlite.connect(self.bot.db_path) as db:
            cursor = await db.execute(
                'SELECT player_guid FROM player_links WHERE discord_id = ?',
                (str(discord_id),)
            )
            row = await cursor.fetchone()
            return row[0] if row else None
    
    async def _get_guid_from_name(self, player_name: str) -> Optional[str]:
        """Get player GUID from player name (fuzzy match)"""
        async with aiosqlite.connect(self.bot.db_path) as db:
            cursor = await db.execute('''
                SELECT player_guid 
                FROM player_comprehensive_stats 
                WHERE LOWER(clean_name) LIKE LOWER(?) 
                   OR LOWER(player_name) LIKE LOWER(?)
                LIMIT 1
            ''', (f'%{player_name}%', f'%{player_name}%'))
            row = await cursor.fetchone()
            return row[0] if row else None
    
    async def _get_player_name(self, player_guid: str) -> str:
        """Get most recent player name"""
        async with aiosqlite.connect(self.bot.db_path) as db:
            cursor = await db.execute('''
                SELECT clean_name 
                FROM player_comprehensive_stats 
                WHERE player_guid = ? 
                ORDER BY id DESC 
                LIMIT 1
            ''', (player_guid,))
            row = await cursor.fetchone()
            return row[0] if row else player_guid[:8]
```

#### Day 8-9: Add !best_duos Command

```python
# Add to SynergyAnalytics class

@commands.command(name='best_duos', aliases=['top_duos', 'best_pairs'])
async def best_duos_command(self, ctx, limit: int = 10):
    """
    Show the best player duos by synergy score
    
    Usage:
        !best_duos          # Top 10 duos
        !best_duos 20       # Top 20 duos
    """
    
    try:
        async with aiosqlite.connect(self.bot.db_path) as db:
            cursor = await db.execute('''
                SELECT 
                    player_a_guid,
                    player_b_guid,
                    synergy_score,
                    games_same_team,
                    win_rate_together,
                    performance_boost,
                    confidence_level
                FROM player_synergies
                WHERE games_same_team >= 10
                  AND confidence_level >= 0.2
                ORDER BY synergy_score DESC
                LIMIT ?
            ''', (limit,))
            
            rows = await cursor.fetchall()
        
        if not rows:
            await ctx.send("❌ No synergy data available yet. Play some games!")
            return
        
        # Create embed
        embed = discord.Embed(
            title=f"🏆 Top {len(rows)} Player Duos",
            description="Ranked by synergy score",
            color=0xFFD700
        )
        
        for i, row in enumerate(rows, 1):
            name1 = await self._get_player_name(row[0])
            name2 = await self._get_player_name(row[1])
            
            embed.add_field(
                name=f"{i}. {name1} + {name2}",
                value=f"Score: {row[2]:.3f} | "
                      f"Win Rate: {row[4]:.1%} | "
                      f"Boost: {row[5]:+.1%} | "
                      f"Games: {row[3]}",
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    except Exception as e:
        logger.error(f"Error in best_duos: {e}", exc_info=True)
        await ctx.send(f"❌ Error: {e}")
```

---

### **Week 3: Advanced Commands & Optimization**

#### Day 10-11: Add !team_builder Command

```python
# Add to SynergyAnalytics class

@commands.command(name='team_builder', aliases=['balance_teams', 'suggest_teams'])
async def team_builder_command(self, ctx):
    """
    Suggest balanced teams based on player synergies
    
    Usage:
        !team_builder @P1 @P2 @P3 @P4 @P5 @P6
    """
    
    try:
        mentions = ctx.message.mentions
        
        if len(mentions) < 6:
            await ctx.send("❌ Please mention at least 6 players to balance teams")
            return
        
        # Get GUIDs
        player_guids = []
        for mention in mentions:
            guid = await self._get_guid_from_mention(mention.id)
            if guid:
                player_guids.append(guid)
        
        if len(player_guids) < 6:
            await ctx.send("❌ Could not find all players in database")
            return
        
        # Calculate best team split
        await ctx.send("🔄 Calculating optimal teams...")
        
        best_split = await self._optimize_teams(player_guids)
        
        # Create embed
        embed = await self._create_team_builder_embed(best_split)
        await ctx.send(embed=embed)
    
    except Exception as e:
        logger.error(f"Error in team_builder: {e}", exc_info=True)
        await ctx.send(f"❌ Error: {e}")

async def _optimize_teams(self, player_guids: List[str]) -> Dict:
    """
    Find optimal team split to maximize balance
    Uses greedy algorithm to balance synergies
    """
    from itertools import combinations
    
    n = len(player_guids)
    team_size = n // 2
    
    best_balance = float('inf')
    best_split = None
    
    # Try all possible team combinations
    for team_a_combo in combinations(range(n), team_size):
        team_a_indices = set(team_a_combo)
        team_b_indices = set(range(n)) - team_a_indices
        
        team_a = [player_guids[i] for i in team_a_indices]
        team_b = [player_guids[i] for i in team_b_indices]
        
        # Calculate team synergies
        synergy_a = await self._calculate_team_synergy(team_a)
        synergy_b = await self._calculate_team_synergy(team_b)
        
        # Balance = difference (want close to 0)
        balance = abs(synergy_a - synergy_b)
        
        if balance < best_balance:
            best_balance = balance
            best_split = {
                'team_a': team_a,
                'team_b': team_b,
                'synergy_a': synergy_a,
                'synergy_b': synergy_b,
                'balance': balance
            }
    
    return best_split

async def _calculate_team_synergy(self, team: List[str]) -> float:
    """Calculate average synergy within a team"""
    from itertools import combinations
    
    synergies = []
    
    for player_a, player_b in combinations(team, 2):
        async with aiosqlite.connect(self.bot.db_path) as db:
            cursor = await db.execute('''
                SELECT synergy_score 
                FROM player_synergies
                WHERE (player_a_guid = ? AND player_b_guid = ?)
                   OR (player_a_guid = ? AND player_b_guid = ?)
            ''', (player_a, player_b, player_b, player_a))
            row = await cursor.fetchone()
            
            if row:
                synergies.append(row[0])
    
    return sum(synergies) / len(synergies) if synergies else 0
```

#### Day 12-14: Optimization & Testing

```python
# Create background task to recalculate synergies daily

# Add to UltimateETLegacyBot class

@tasks.loop(hours=24)
async def recalculate_synergies(self):
    """Recalculate all synergies once per day"""
    logger.info("🔄 Starting daily synergy recalculation...")
    
    try:
        detector = SynergyDetector(self.db_path)
        count = await detector.calculate_all_synergies()
        logger.info(f"✅ Recalculated {count} synergies")
    except Exception as e:
        logger.error(f"Error recalculating synergies: {e}", exc_info=True)
```

---

## 📊 Testing Checklist

### Unit Tests
- [ ] `test_synergy_detector.py` passes
- [ ] `test_performance_calculation.py` passes
- [ ] Edge cases handled (0 games, 1 game, equal performance)

### Integration Tests
- [ ] `!synergy @Player1 @Player2` returns valid data
- [ ] `!best_duos` shows top 10 pairs
- [ ] `!team_builder` balances 6 players correctly

### Performance Tests
- [ ] `!synergy` responds in <1 second
- [ ] `!best_duos` responds in <2 seconds
- [ ] Background recalculation completes in <5 minutes

---

## 🎯 Success Criteria

✅ **Phase 1 Complete When:**

1. `player_synergies` table populated with all player pairs
2. All 3 commands working (`!synergy`, `!best_duos`, `!team_builder`)
3. Community uses commands regularly (5+ times per week)
4. Synergy scores match subjective player opinions (validate with community)

---

## 📈 Expected Outcomes

After Week 3, you will have:

- ✅ Synergy scores for ~400-900 player pairs (30 players × 29 / 2)
- ✅ Ability to identify "dream teams" and problematic pairings
- ✅ Data-driven team balancing (better than manual)
- ✅ Foundation for Phase 2 (role normalization)

---

## 🚀 Next Steps

After Phase 1 completion:

1. **Gather community feedback** - Do synergy scores feel accurate?
2. **Validate predictions** - Do recommended teams actually perform better?
3. **Tune thresholds** - Adjust minimum games, confidence levels
4. **Proceed to Phase 2** - Role normalization for fairer comparisons

---

**Status:** Ready to implement  
**Start Date:** October 6, 2025  
**Target Completion:** October 27, 2025
