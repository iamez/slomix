# ⚖️ Phase 2: Role Normalization System

**Duration:** Weeks 4-5  
**Complexity:** ⭐⭐ Medium  
**Risk Level:** 🟡 Medium (requires community validation)  
**Dependencies:** Phase 1 complete

---

## 🎯 Goal

Create a fair performance scoring system that recognizes engineers and support players by normalizing metrics across different roles/classes.

### The Problem

Current leaderboards favor aggressive medics:
- **Medics** get high K/D + can self-heal
- **Engineers** have low K/D but complete critical objectives
- **Field Ops** provide support (ammo, airstrikes) but don't get credit
- **Soldiers** spam damage but may not contribute to objectives

### The Solution

**Role-weighted performance scoring** that values each class's primary contributions:
- Engineers rated by objectives, plants, constructions
- Medics rated by revives, survival time, combat
- Field Ops rated by support actions + damage output
- Soldiers rated by damage efficiency
- Covert Ops rated by reconnaissance and assassinations

---

## 📋 Week-by-Week Breakdown

### **Week 4: Role Weight System**

#### Day 1-2: Define Role Weights

Create `analytics/performance_normalizer.py`:

```python
"""
Role-Normalized Performance Scoring
Weights stats based on class expectations
"""

from dataclasses import dataclass
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

@dataclass
class RoleWeights:
    """Stat weights for a specific role"""
    kills: float = 1.0
    deaths: float = 1.0
    damage: float = 1.0
    objectives: float = 1.0
    revives: float = 1.0
    constructions: float = 1.0
    destructions: float = 1.0
    dynamites: float = 1.0
    ammo_given: float = 1.0
    health_given: float = 1.0
    headshots: float = 1.0
    survival_time: float = 1.0

# Define weights for each class (based on 3v3 competitive play)
ROLE_WEIGHTS = {
    'medic': RoleWeights(
        kills=1.0,              # Medics expected to frag
        deaths=1.5,             # Staying alive is CRITICAL
        damage=0.8,             # Less important than kills
        objectives=1.2,         # Still important
        revives=2.5,            # PRIMARY ROLE - most important
        constructions=0.5,      # Rarely build
        destructions=0.5,
        dynamites=0.5,
        survival_time=2.0,      # Must stay alive to revive
        health_given=1.5        # Self-healing counted here
    ),
    
    'engineer': RoleWeights(
        kills=0.7,              # Low kill expectations
        deaths=1.0,             # Deaths acceptable if objective done
        damage=0.6,             # Not primary concern
        objectives=3.0,         # PRIMARY ROLE - completing objectives
        revives=0.0,            # Can't revive
        constructions=2.5,      # Building is critical
        destructions=2.5,       # Destroying enemy builds
        dynamites=2.5,          # Planting/defusing PRIMARY
        survival_time=1.5,      # Need to stay alive for plants
        ammo_given=0.5          # Can give ammo but not primary
    ),
    
    'fieldops': RoleWeights(
        kills=1.2,              # Expected to get kills
        deaths=0.8,             # Deaths less critical (can respawn fast)
        damage=1.5,             # PRIMARY ROLE - spam damage
        objectives=1.0,         # Standard
        revives=0.0,            # Can't revive
        constructions=0.5,
        destructions=1.0,       # Arty can destroy
        ammo_given=2.0,         # Support role - keep team supplied
        survival_time=0.8       # Less critical than medic
    ),
    
    'soldier': RoleWeights(
        kills=1.3,              # PRIMARY ROLE - fragging
        deaths=0.7,             # Acceptable to trade
        damage=1.5,             # HIGH - panzers/flamers
        objectives=0.8,         # Less important
        revives=0.0,
        constructions=0.5,
        destructions=1.2,       # Panzers destroy
        headshots=1.5,          # Skill indicator
        survival_time=0.5       # Aggressive play expected
    ),
    
    'covert': RoleWeights(
        kills=1.1,              # Sniping/backstabs
        deaths=1.2,             # Should avoid dying (long respawn)
        damage=0.9,             # Less than soldier
        objectives=1.5,         # Can steal/return
        revives=0.0,
        constructions=0.5,
        destructions=1.0,
        headshots=2.0,          # PRIMARY - sniper headshots
        survival_time=1.3       # Stay hidden, stay alive
    )
}

class PerformanceNormalizer:
    """Calculates role-normalized performance scores"""
    
    def __init__(self):
        self.weights = ROLE_WEIGHTS
    
    def calculate_performance_score(
        self, 
        stats: Dict, 
        player_class: str
    ) -> float:
        """
        Calculate normalized performance score for a player
        
        Args:
            stats: Dict with player stats (kills, deaths, damage, etc.)
            player_class: 'medic', 'engineer', 'fieldops', 'soldier', 'covert'
        
        Returns:
            Normalized score (higher = better, accounts for role)
        """
        
        if player_class not in self.weights:
            logger.warning(f"Unknown class: {player_class}, using default weights")
            player_class = 'medic'  # Default fallback
        
        weights = self.weights[player_class]
        
        # Get stats with defaults
        kills = stats.get('kills', 0)
        deaths = max(stats.get('deaths', 1), 1)  # Avoid division by 0
        damage = stats.get('damage_given', 0)
        objectives = stats.get('objectives_completed', 0)
        revives = stats.get('revives_given', 0)
        constructions = stats.get('constructions', 0)
        destructions = stats.get('destructions', 0)
        dynamites = stats.get('dynamites_planted', 0) + stats.get('dynamites_defused', 0)
        time_played = max(stats.get('time_played_seconds', 1), 1)
        
        # Calculate component scores
        kill_score = (kills / deaths) * weights.kills
        damage_score = (damage / time_played * 60) * weights.damage  # DPM
        objective_score = objectives * weights.objectives
        revive_score = revives * weights.revives
        construction_score = constructions * weights.constructions
        destruction_score = destructions * weights.destructions
        dynamite_score = dynamites * weights.dynamites
        
        # Survival bonus (staying alive matters for some classes)
        deaths_per_minute = deaths / (time_played / 60)
        survival_score = (1 / max(deaths_per_minute, 0.1)) * weights.survival_time
        
        # Sum weighted scores
        total_score = (
            kill_score +
            damage_score / 100 +  # Scale DPM to comparable range
            objective_score * 10 +  # Objectives worth a lot
            revive_score * 5 +
            construction_score * 10 +
            destruction_score * 10 +
            dynamite_score * 15 +  # Dynamites VERY valuable
            survival_score
        )
        
        # Normalize by time played (per-minute score)
        normalized_score = total_score / (time_played / 60)
        
        return normalized_score
    
    def get_class_rankings(
        self, 
        player_guid: str, 
        db_path: str = 'etlegacy_production.db'
    ) -> Dict[str, float]:
        """
        Get player's normalized score for each class they've played
        
        Returns: {'medic': 45.2, 'engineer': 38.7, ...}
        """
        import sqlite3
        
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Query stats by class (you'd need to track class per session)
        # For now, assume we have a 'player_class' column
        # This would require updating your stats tracking
        
        query = '''
            SELECT 
                player_class,
                AVG(kills) as avg_kills,
                AVG(deaths) as avg_deaths,
                AVG(damage_given) as avg_damage,
                AVG(objectives_completed) as avg_objectives,
                AVG(revives_given) as avg_revives,
                AVG(constructions) as avg_constructions,
                AVG(destructions) as avg_destructions,
                AVG(dynamites_planted + dynamites_defused) as avg_dynamites,
                AVG(time_played_seconds) as avg_time
            FROM player_comprehensive_stats
            WHERE player_guid = ?
            GROUP BY player_class
        '''
        
        cursor.execute(query, (player_guid,))
        rows = cursor.fetchall()
        conn.close()
        
        rankings = {}
        for row in rows:
            stats = {
                'kills': row['avg_kills'],
                'deaths': row['avg_deaths'],
                'damage_given': row['avg_damage'],
                'objectives_completed': row['avg_objectives'],
                'revives_given': row['avg_revives'],
                'constructions': row['avg_constructions'],
                'destructions': row['avg_destructions'],
                'dynamites_planted': row['avg_dynamites'],
                'time_played_seconds': row['avg_time']
            }
            
            score = self.calculate_performance_score(stats, row['player_class'])
            rankings[row['player_class']] = score
        
        return rankings
    
    def compare_players_fairly(
        self, 
        player_a_stats: Dict,
        player_a_class: str,
        player_b_stats: Dict,
        player_b_class: str
    ) -> str:
        """
        Compare two players on different classes fairly
        
        Returns: "Player A", "Player B", or "Tied"
        """
        
        score_a = self.calculate_performance_score(player_a_stats, player_a_class)
        score_b = self.calculate_performance_score(player_b_stats, player_b_class)
        
        if abs(score_a - score_b) < 0.5:  # Within 0.5 points = tied
            return "Tied"
        elif score_a > score_b:
            return "Player A"
        else:
            return "Player B"
```

#### Day 3-4: Test Role Weights with Community

Create `tests/test_role_weights.py`:

```python
"""
Test role weights with known player data
Validate with community feedback
"""

from analytics.performance_normalizer import PerformanceNormalizer

def test_engineer_vs_medic():
    """
    Test case: Engineer with low K/D but high objectives
    vs Medic with high K/D but low objectives
    
    Expected: Engineer should score competitively
    """
    
    normalizer = PerformanceNormalizer()
    
    # Engineer stats (low K/D, high objectives)
    engineer_stats = {
        'kills': 10,
        'deaths': 15,
        'damage_given': 3000,
        'objectives_completed': 5,
        'constructions': 3,
        'dynamites_planted': 4,
        'dynamites_defused': 2,
        'time_played_seconds': 900  # 15 minutes
    }
    
    # Medic stats (high K/D, low objectives)
    medic_stats = {
        'kills': 25,
        'deaths': 10,
        'damage_given': 7000,
        'objectives_completed': 1,
        'revives_given': 8,
        'time_played_seconds': 900
    }
    
    engineer_score = normalizer.calculate_performance_score(
        engineer_stats, 'engineer'
    )
    medic_score = normalizer.calculate_performance_score(
        medic_stats, 'medic'
    )
    
    print(f"Engineer score: {engineer_score:.2f}")
    print(f"Medic score: {medic_score:.2f}")
    
    # Both should be competitive (within 20% of each other)
    ratio = engineer_score / medic_score
    assert 0.8 <= ratio <= 1.2, "Engineer and Medic should be competitive!"
    
    print("✅ Test passed: Engineer fairly rated vs Medic")

if __name__ == '__main__':
    test_engineer_vs_medic()
```

#### Day 5: Database Schema Updates

**Option A: Track class per session (recommended)**

```python
# Migration: tools/migrations/002_add_player_class.py

import sqlite3

def add_player_class_column():
    """Add player_class column to track class played"""
    
    conn = sqlite3.connect('etlegacy_production.db')
    cursor = conn.cursor()
    
    # Check if column exists
    cursor.execute("PRAGMA table_info(player_comprehensive_stats)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'player_class' not in columns:
        cursor.execute('''
            ALTER TABLE player_comprehensive_stats
            ADD COLUMN player_class TEXT DEFAULT 'unknown'
        ''')
        print("✅ Added player_class column")
    else:
        print("⏭️  player_class column already exists")
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    add_player_class_column()
```

**Update parser to extract class:**

```python
# In bot/community_stats_parser.py

# Add to parse_player_stats() method:
def parse_player_stats(self, content: str) -> List[Dict]:
    # ... existing code ...
    
    # Extract player class (from XP section or class-specific stats)
    # c0rnp0rn3.lua should log class played
    player_data['player_class'] = self._extract_player_class(player_block)
    
    return players

def _extract_player_class(self, player_block: str) -> str:
    """Extract class from player data"""
    # Look for class indicators in XP or skill sections
    # This depends on your Lua script output
    # Example: "Battle Sense: 20" indicates soldier
    
    if 'Light Weapons' in player_block:
        return 'medic'
    elif 'Engineering' in player_block:
        return 'engineer'
    elif 'Signals' in player_block:
        return 'fieldops'
    elif 'Heavy Weapons' in player_block:
        return 'soldier'
    elif 'Covert Ops' in player_block:
        return 'covert'
    else:
        return 'unknown'
```

---

### **Week 5: Bot Integration & Leaderboards**

#### Day 6-7: Update !leaderboard Command

```python
# Update ETLegacyCommands Cog in bot/ultimate_bot.py

@commands.command(name='leaderboard', aliases=['lb', 'top'])
async def leaderboard_command(
    self, 
    ctx, 
    stat: str = 'normalized',  # NEW: default to normalized
    limit: int = 10
):
    """
    Show leaderboards
    
    Usage:
        !leaderboard                    # Top 10 by normalized score
        !leaderboard engineers          # Top engineers
        !leaderboard medics             # Top medics
        !leaderboard kd                 # Traditional K/D leaderboard
    """
    
    from analytics.performance_normalizer import PerformanceNormalizer
    
    normalizer = PerformanceNormalizer()
    
    if stat == 'normalized' or stat == 'overall':
        # Normalized leaderboard (all classes fairly compared)
        await self._show_normalized_leaderboard(ctx, limit, normalizer)
    
    elif stat in ['engineer', 'engineers']:
        await self._show_class_leaderboard(ctx, 'engineer', limit, normalizer)
    
    elif stat in ['medic', 'medics']:
        await self._show_class_leaderboard(ctx, 'medic', limit, normalizer)
    
    elif stat in ['fieldops', 'fo']:
        await self._show_class_leaderboard(ctx, 'fieldops', limit, normalizer)
    
    elif stat in ['soldier', 'soldiers']:
        await self._show_class_leaderboard(ctx, 'soldier', limit, normalizer)
    
    elif stat in ['kd', 'kills']:
        # Traditional leaderboard (for comparison)
        await self._show_traditional_leaderboard(ctx, 'kd', limit)
    
    else:
        await ctx.send(f"❌ Unknown leaderboard: {stat}")

async def _show_normalized_leaderboard(
    self, 
    ctx, 
    limit: int, 
    normalizer: PerformanceNormalizer
):
    """Show overall leaderboard with normalized scores"""
    
    async with aiosqlite.connect(self.bot.db_path) as db:
        # Get all players with stats
        cursor = await db.execute('''
            SELECT 
                player_guid,
                clean_name,
                player_class,
                AVG(kills) as avg_kills,
                AVG(deaths) as avg_deaths,
                AVG(damage_given) as avg_damage,
                AVG(objectives_completed) as avg_objectives,
                AVG(revives_given) as avg_revives,
                AVG(constructions) as avg_constructions,
                AVG(destructions) as avg_destructions,
                AVG(dynamites_planted + dynamites_defused) as avg_dynamites,
                AVG(time_played_seconds) as avg_time,
                COUNT(*) as games_played
            FROM player_comprehensive_stats
            WHERE player_class != 'unknown'
            GROUP BY player_guid, player_class
            HAVING games_played >= 5
        ''')
        
        rows = await cursor.fetchall()
    
    # Calculate normalized scores
    player_scores = []
    
    for row in rows:
        stats = {
            'kills': row[3],
            'deaths': row[4],
            'damage_given': row[5],
            'objectives_completed': row[6],
            'revives_given': row[7],
            'constructions': row[8],
            'destructions': row[9],
            'dynamites_planted': row[10],
            'time_played_seconds': row[11]
        }
        
        score = normalizer.calculate_performance_score(stats, row[2])
        
        player_scores.append({
            'guid': row[0],
            'name': row[1],
            'class': row[2],
            'score': score,
            'games': row[12]
        })
    
    # Sort by score
    player_scores.sort(key=lambda x: x['score'], reverse=True)
    top_players = player_scores[:limit]
    
    # Create embed
    embed = discord.Embed(
        title="🏆 Overall Leaderboard (Role-Normalized)",
        description="Fair comparison across all classes",
        color=0xFFD700
    )
    
    for i, player in enumerate(top_players, 1):
        class_emoji = {
            'medic': '💉',
            'engineer': '🔧',
            'fieldops': '📡',
            'soldier': '💣',
            'covert': '🔍'
        }.get(player['class'], '❓')
        
        embed.add_field(
            name=f"{i}. {player['name']} {class_emoji}",
            value=f"Score: {player['score']:.1f} | Games: {player['games']}",
            inline=False
        )
    
    embed.set_footer(text="Scores account for class roles and expectations")
    await ctx.send(embed=embed)

async def _show_class_leaderboard(
    self,
    ctx,
    player_class: str,
    limit: int,
    normalizer: PerformanceNormalizer
):
    """Show leaderboard for specific class"""
    
    # Similar to above but filter by player_class
    # ... implementation ...
```

#### Day 8-9: Add New Commands

```python
# Add to ETLegacyCommands Cog

@commands.command(name='class_stats', aliases=['classes', 'my_classes'])
async def class_stats_command(self, ctx, player: str = None):
    """
    Show player's performance across all classes
    
    Usage:
        !class_stats            # Your stats
        !class_stats @Player    # Someone else's stats
    """
    
    from analytics.performance_normalizer import PerformanceNormalizer
    
    # Get player GUID (from mention or self)
    player_guid = await self._resolve_player(ctx, player)
    
    if not player_guid:
        await ctx.send("❌ Player not found")
        return
    
    normalizer = PerformanceNormalizer()
    rankings = normalizer.get_class_rankings(player_guid, self.bot.db_path)
    
    if not rankings:
        await ctx.send("❌ No class data found")
        return
    
    # Create embed
    player_name = await self._get_player_name(player_guid)
    
    embed = discord.Embed(
        title=f"📊 Class Performance: {player_name}",
        color=0x00FF00
    )
    
    # Sort classes by score
    sorted_classes = sorted(rankings.items(), key=lambda x: x[1], reverse=True)
    
    for player_class, score in sorted_classes:
        class_emoji = {
            'medic': '💉',
            'engineer': '🔧',
            'fieldops': '📡',
            'soldier': '💣',
            'covert': '🔍'
        }.get(player_class, '❓')
        
        embed.add_field(
            name=f"{class_emoji} {player_class.capitalize()}",
            value=f"Score: {score:.1f}",
            inline=True
        )
    
    # Show best class
    best_class = sorted_classes[0][0]
    embed.set_footer(text=f"Best class: {best_class.capitalize()}")
    
    await ctx.send(embed=embed)

@commands.command(name='compare', aliases=['vs'])
async def compare_players_command(
    self, 
    ctx, 
    player1: str = None, 
    player2: str = None
):
    """
    Fairly compare two players (even on different classes)
    
    Usage:
        !compare @Player1 @Player2
    """
    
    from analytics.performance_normalizer import PerformanceNormalizer
    
    # Get player GUIDs
    guid1 = await self._resolve_player(ctx, player1)
    guid2 = await self._resolve_player(ctx, player2)
    
    if not guid1 or not guid2:
        await ctx.send("❌ Could not find players")
        return
    
    # Get stats for both players
    stats1, class1 = await self._get_player_avg_stats(guid1)
    stats2, class2 = await self._get_player_avg_stats(guid2)
    
    normalizer = PerformanceNormalizer()
    
    score1 = normalizer.calculate_performance_score(stats1, class1)
    score2 = normalizer.calculate_performance_score(stats2, class2)
    
    # Create comparison embed
    name1 = await self._get_player_name(guid1)
    name2 = await self._get_player_name(guid2)
    
    embed = discord.Embed(
        title=f"⚔️ Player Comparison",
        description=f"{name1} ({class1}) vs {name2} ({class2})",
        color=0x00BFFF
    )
    
    embed.add_field(
        name=f"{name1}",
        value=f"Score: {score1:.1f}",
        inline=True
    )
    
    embed.add_field(
        name=f"{name2}",
        value=f"Score: {score2:.1f}",
        inline=True
    )
    
    # Determine winner
    if abs(score1 - score2) < 0.5:
        winner = "Tied! 🤝"
    elif score1 > score2:
        winner = f"{name1} wins! 🏆"
    else:
        winner = f"{name2} wins! 🏆"
    
    embed.add_field(
        name="Result",
        value=winner,
        inline=False
    )
    
    await ctx.send(embed=embed)
```

#### Day 10: Community Feedback & Tuning

```python
# Create admin command to adjust weights on-the-fly

@commands.command(name='tune_weights')
@commands.has_role('Admin')  # Only admins
async def tune_weights_command(
    self,
    ctx,
    player_class: str,
    stat: str,
    new_weight: float
):
    """
    Adjust role weights based on community feedback
    
    Usage:
        !tune_weights engineer objectives 3.5
    """
    
    from analytics.performance_normalizer import ROLE_WEIGHTS
    
    if player_class not in ROLE_WEIGHTS:
        await ctx.send(f"❌ Unknown class: {player_class}")
        return
    
    if not hasattr(ROLE_WEIGHTS[player_class], stat):
        await ctx.send(f"❌ Unknown stat: {stat}")
        return
    
    # Update weight
    setattr(ROLE_WEIGHTS[player_class], stat, new_weight)
    
    await ctx.send(
        f"✅ Updated {player_class}.{stat} weight to {new_weight}\n"
        f"🔄 Recalculating all scores..."
    )
    
    # Trigger recalculation
    # (This would save to config file and reload)
```

---

## 📊 Testing Checklist

### Validation Tests

- [ ] Engineer with high objectives beats medic with high K/D
- [ ] Support fieldops gets credit for ammo/arty
- [ ] Aggressive medics still valued (not nerfed too much)
- [ ] Covert ops snipers ranked fairly

### Community Acceptance

- [ ] Poll community: "Do these scores feel fair?"
- [ ] Compare normalized leaderboard to community's subjective opinions
- [ ] Adjust weights based on feedback
- [ ] Re-test and validate

### Performance Tests

- [ ] `!leaderboard normalized` responds in <2 seconds
- [ ] `!class_stats` responds in <1 second
- [ ] Score calculations accurate

---

## 🎯 Success Criteria

✅ **Phase 2 Complete When:**

1. Normalized leaderboard shows engineers in top 10
2. Community agrees scores are "fair" (>70% approval)
3. All new commands working
4. Weights tuned and stable

---

## 📈 Expected Outcomes

After Week 5:

- ✅ Engineers and support players recognized in leaderboards
- ✅ Fair comparison across classes
- ✅ Community uses normalized scores as standard
- ✅ Foundation for advanced analytics (Phase 3)

---

## 🔄 Iteration Process

1. **Deploy initial weights** (Week 4)
2. **Gather community feedback** (Week 5)
3. **Tune weights** based on feedback
4. **Re-validate** with community
5. **Lock weights** when consensus reached

---

## 🚀 Next Steps

After Phase 2:

1. **Decide on Phase 3** - Is proximity tracking needed?
2. **Integrate with Phase 1** - Update synergy scores with normalized performance
3. **Advanced analytics** - Predict match outcomes, suggest optimal class compositions

---

**Status:** Ready to implement after Phase 1  
**Start Date:** October 27, 2025 (after Phase 1)  
**Target Completion:** November 10, 2025
