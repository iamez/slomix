# 🎮 COMPETITIVE ANALYTICS IMPLEMENTATION GUIDE
## For Claude Code (Sonnet 4.5) - Step-by-Step Instructions

**Project:** slomix ET:Legacy Discord Bot  
**Feature:** Automated Team Detection, Predictions & Match Analytics  
**Total Effort:** ~55-70 hours across 5 phases  
**Created:** November 28, 2025

---

## 📋 EXECUTIVE SUMMARY

### What We're Building
An automated competitive analytics system that:
1. **Detects** when players split into teams (voice channels)
2. **Predicts** match outcomes using historical data
3. **Tracks** live scores during gameplay
4. **Analyzes** results and improves over time

### Current State
- ✅ Voice session detection works (counts players)
- ✅ SSH file monitoring works (imports stats)
- ✅ Database adapter exists (PostgreSQL ready)
- ❌ Team SPLIT detection missing (Phase 2 foundation exists but broken)
- ❌ Prediction engine missing (needs to be built)
- ❌ Live scoring incomplete

### The Problem with "Dead Code"
The modules in `bot/core/` (advanced_team_detector.py, substitution_detector.py, etc.) are NOT dead - they're **80% complete but use wrong database patterns**. They were written before the PostgreSQL migration.

---

## 🛠️ PHASE 1: DATABASE ADAPTER REFACTORING (12 hours)

### Goal
Convert all sqlite3 patterns to async DatabaseAdapter patterns.

### Files to Refactor

#### 1. `bot/core/team_manager.py` (PRIORITY - in production!)

**Current (BROKEN):**
```python
# Line 28
def __init__(self, db_path: str = "bot/etlegacy_production.db"):
    self.db_path = db_path

# Line 33
def detect_session_teams(
    self,
    db: sqlite3.Connection,  # ❌ WRONG
    session_date: str
) -> Dict[str, Dict]:
    cursor = db.cursor()  # ❌ WRONG
    cursor.execute(query, (f"{session_date}%",))  # ❌ WRONG
    rows = cursor.fetchall()  # ❌ WRONG
```

**Convert to (CORRECT):**
```python
from typing import TYPE_CHECKING, Dict, List, Optional
import logging

if TYPE_CHECKING:
    from bot.core.database_adapter import DatabaseAdapter

logger = logging.getLogger(__name__)


class TeamManager:
    """Manages team detection, tracking, and statistics"""
    
    def __init__(self, db_adapter: 'DatabaseAdapter'):
        """
        Initialize TeamManager with database adapter.
        
        Args:
            db_adapter: DatabaseAdapter instance for PostgreSQL/SQLite
        """
        self.db = db_adapter
    
    async def detect_session_teams(
        self, 
        session_date: str
    ) -> Dict[str, Dict]:
        """
        Automatically detect persistent teams for a session.
        
        Args:
            session_date: Session date (YYYY-MM-DD format)
            
        Returns:
            {
                'Team A': {'guids': [...], 'names': [...], 'count': 5},
                'Team B': {'guids': [...], 'names': [...], 'count': 5}
            }
        """
        # Get all players from session grouped by round and game-team
        query = """
            SELECT round_number, team, player_guid, player_name
            FROM player_comprehensive_stats
            WHERE round_date LIKE $1
            ORDER BY round_number, team
        """
        rows = await self.db.fetch_all(query, (f"{session_date}%",))
        
        if not rows:
            logger.warning(f"No player data found for session {session_date}")
            return {}
        
        # Rest of logic stays the same, just uses rows directly
        # ... (process rows as before)
```

**Key Changes:**
1. `__init__` accepts `db_adapter` instead of `db_path`
2. All methods become `async def`
3. Replace `cursor.execute()` + `fetchall()` → `await self.db.fetch_all()`
4. Replace `?` placeholders → `$1, $2, $3` (PostgreSQL style)
5. Remove `db: sqlite3.Connection` parameters

**All Methods to Convert in team_manager.py:**
- [ ] `__init__()` - Accept db_adapter
- [ ] `detect_session_teams()` - async + adapter
- [ ] `store_session_teams()` - async + adapter
- [ ] `get_session_teams()` - async + adapter
- [ ] `detect_lineup_changes()` - async + adapter
- [ ] `get_team_record()` - async + adapter (if implemented)
- [ ] `set_custom_team_names()` - async + adapter
- [ ] `get_map_performance()` - async + adapter (if implemented)

---

#### 2. `bot/core/advanced_team_detector.py`

**Same refactoring pattern. Key methods:**
- [ ] `__init__()` - Accept db_adapter
- [ ] `detect_session_teams()` - async
- [ ] `_get_session_player_data()` - async
- [ ] `_analyze_historical_patterns()` - async
- [ ] `_analyze_multi_round_consensus()` - async
- [ ] `_analyze_cooccurrence()` - async
- [ ] `_combine_strategies()` - stays sync (no DB calls)
- [ ] `_cluster_into_teams()` - stays sync (no DB calls)

**Example conversion for `_get_session_player_data`:**

```python
# OLD (line ~144)
def _get_session_player_data(
    self,
    db: sqlite3.Connection,
    session_date: str
) -> Dict[str, Dict]:
    cursor = db.cursor()
    query = """..."""
    cursor.execute(query, (f"{session_date}%",))
    rows = cursor.fetchall()

# NEW
async def _get_session_player_data(
    self,
    session_date: str
) -> Dict[str, Dict]:
    query = """
        SELECT 
            player_guid,
            player_name,
            round_number,
            team,
            kills,
            deaths,
            time_played_seconds
        FROM player_comprehensive_stats
        WHERE round_date LIKE $1
        ORDER BY round_number, player_guid
    """
    rows = await self.db.fetch_all(query, (f"{session_date}%",))
    
    # Process rows (same logic as before)
    players = {}
    for row in rows:
        guid, name, round_num, game_team, kills, deaths, time_played = row
        # ... rest of logic
    return players
```

---

#### 3. `bot/core/substitution_detector.py`

**Same pattern. Key methods:**
- [ ] `__init__()` - Accept db_adapter
- [ ] `analyze_session_roster_changes()` - async
- [ ] `_get_player_activity()` - async
- [ ] `_get_round_rosters()` - async
- [ ] `_detect_roster_changes()` - stays sync (processes data, no DB)
- [ ] `_detect_substitutions()` - stays sync
- [ ] `_generate_summary()` - stays sync
- [ ] `adjust_team_detection_for_substitutions()` - stays sync

**REMOVE the standalone demo function** at the bottom (uses direct sqlite3.connect).

---

#### 4. `bot/core/team_history.py`

**Key methods:**
- [ ] `__init__()` - Accept db_adapter
- [ ] `get_lineup_stats()` - async
- [ ] `get_lineup_sessions()` - async
- [ ] `find_similar_lineups()` - async
- [ ] `get_head_to_head()` - async
- [ ] `get_recent_lineups()` - async
- [ ] `get_best_lineups()` - async

**REMOVE the `if __name__ == "__main__":` block** (uses direct sqlite3.connect).

---

#### 5. `bot/core/team_detector_integration.py`

This is the GLUE layer. Convert to use the refactored modules:

```python
class TeamDetectorIntegration:
    def __init__(self, db_adapter: 'DatabaseAdapter'):
        self.db = db_adapter
        self.advanced_detector = AdvancedTeamDetector(db_adapter)
    
    async def detect_and_validate(
        self,
        session_date: str,
        require_high_confidence: bool = False
    ) -> Tuple[Dict, bool]:
        # Use self.advanced_detector (already has db reference)
        result = await self.advanced_detector.detect_session_teams(
            session_date, use_historical=True
        )
        # ... rest of validation logic
```

---

#### 6. `bot/core/achievement_system.py`

**Current (uses aiosqlite - wrong library):**
```python
async with aiosqlite.connect(self.bot.db_path) as db:
    async with db.execute(query, params) as cursor:
        stats = await cursor.fetchone()
```

**Convert to (use bot's DatabaseAdapter):**
```python
# Use self.bot.db (the bot's DatabaseAdapter instance)
stats = await self.bot.db.fetch_one(query, params)
```

**Remove:**
- Any `import aiosqlite` statements
- The `_ensure_player_name_alias()` method (SQLite compatibility hack)

---

### Phase 1 Testing Checklist

```bash
# After refactoring, test each module:

# 1. Syntax check
python -m py_compile bot/core/team_manager.py
python -m py_compile bot/core/advanced_team_detector.py
python -m py_compile bot/core/substitution_detector.py
python -m py_compile bot/core/team_history.py
python -m py_compile bot/core/team_detector_integration.py
python -m py_compile bot/core/achievement_system.py

# 2. Import check
python -c "
from bot.core.team_manager import TeamManager
from bot.core.advanced_team_detector import AdvancedTeamDetector
from bot.core.substitution_detector import SubstitutionDetector
from bot.core.team_history import TeamHistoryManager
from bot.core.team_detector_integration import TeamDetectorIntegration
from bot.core.achievement_system import AchievementSystem
print('All team modules import OK')
"

# 3. Full bot startup test
python -c "from bot.ultimate_bot import UltimateBot; print('Bot imports OK')"
```

---

### Phase 1 Cog Updates

After refactoring the core modules, update the cogs that use them:

#### `bot/cogs/team_cog.py`

```python
# Find where TeamManager is instantiated and update:

# OLD
self.team_manager = TeamManager(self.bot.db_path)

# NEW
self.team_manager = TeamManager(self.bot.db)

# And update method calls to await:
# OLD
teams = self.team_manager.detect_session_teams(db, session_date)

# NEW
teams = await self.team_manager.detect_session_teams(session_date)
```

---

## 🛠️ PHASE 2: VOICE CHANNEL ENHANCEMENT (6-8 hours)

### Goal
Detect when players split into 2 team channels (trigger for predictions).

### File: `bot/services/voice_session_service.py`

### New Data Structures

Add to class `__init__`:

```python
def __init__(self, bot, config, db_adapter):
    # ... existing code ...
    
    # NEW: Team split detection
    self.channel_distribution: Dict[int, Set[int]] = {}  # {channel_id: {user_ids}}
    self.team_split_detected: bool = False
    self.team_a_channel_id: Optional[int] = None
    self.team_b_channel_id: Optional[int] = None
    self.team_a_guids: List[str] = []
    self.team_b_guids: List[str] = []
    self.last_split_time: Optional[datetime] = None
    
    # Cooldown to prevent spam (min 5 minutes between predictions)
    self.prediction_cooldown_minutes: int = 5
```

### New Method: `_detect_team_split()`

```python
async def _detect_team_split(self) -> Optional[Dict]:
    """
    Detect when players split into two roughly equal team channels.
    
    Returns:
        {
            'team_a_discord_ids': [user_id1, user_id2, ...],
            'team_b_discord_ids': [user_id3, user_id4, ...],
            'team_a_guids': ['GUID1', 'GUID2', ...],
            'team_b_guids': ['GUID3', 'GUID4', ...],
            'format': '4v4',
            'confidence': 'high'
        }
        OR None if no valid team split detected
    """
    # 1. Count players in each gaming voice channel
    distribution = {}
    for channel_id in self.config.gaming_voice_channels:
        channel = self.bot.get_channel(channel_id)
        if channel and hasattr(channel, 'members'):
            member_ids = {m.id for m in channel.members if not m.bot}
            if member_ids:
                distribution[channel_id] = member_ids
    
    # 2. Need exactly 2 active channels for team split
    if len(distribution) != 2:
        return None
    
    # 3. Get the two channels
    channels = list(distribution.items())
    channel_a_id, users_a = channels[0]
    channel_b_id, users_b = channels[1]
    
    count_a = len(users_a)
    count_b = len(users_b)
    total = count_a + count_b
    
    # 4. Minimum 6 players for competitive match
    if total < 6:
        return None
    
    # 5. Teams must be roughly equal (max 1 player difference)
    if abs(count_a - count_b) > 1:
        return None
    
    # 6. Determine format
    format_map = {6: "3v3", 8: "4v4", 10: "5v5", 12: "6v6"}
    format_str = format_map.get(total, f"{count_a}v{count_b}")
    
    # 7. Resolve Discord IDs to Player GUIDs
    team_a_guids = await self._resolve_discord_ids_to_guids(list(users_a))
    team_b_guids = await self._resolve_discord_ids_to_guids(list(users_b))
    
    # 8. Check if we have enough GUIDs mapped
    guid_coverage = (len(team_a_guids) + len(team_b_guids)) / total
    if guid_coverage < 0.5:  # Need at least 50% mapped
        logger.warning(f"Low GUID coverage ({guid_coverage:.0%}), skipping prediction")
        return None
    
    # 9. Confidence based on balance and GUID coverage
    confidence = "high" if (count_a == count_b and guid_coverage > 0.8) else "medium"
    
    return {
        'team_a_discord_ids': list(users_a),
        'team_b_discord_ids': list(users_b),
        'team_a_channel_id': channel_a_id,
        'team_b_channel_id': channel_b_id,
        'team_a_guids': team_a_guids,
        'team_b_guids': team_b_guids,
        'format': format_str,
        'confidence': confidence,
        'guid_coverage': guid_coverage
    }
```

### New Method: `_resolve_discord_ids_to_guids()`

```python
async def _resolve_discord_ids_to_guids(
    self, 
    discord_ids: List[int]
) -> List[str]:
    """
    Convert Discord user IDs to ET:Legacy player GUIDs.
    
    Uses the player_links table for mapping.
    """
    if not discord_ids:
        return []
    
    # Build query with correct number of placeholders
    placeholders = ', '.join([f'${i+1}' for i in range(len(discord_ids))])
    query = f"""
        SELECT discord_id, et_guid
        FROM player_links
        WHERE discord_id IN ({placeholders})
    """
    
    rows = await self.db_adapter.fetch_all(query, tuple(discord_ids))
    
    # Build mapping
    id_to_guid = {row[0]: row[1] for row in rows}
    
    # Return GUIDs in order (skip unmapped)
    guids = []
    for discord_id in discord_ids:
        if discord_id in id_to_guid:
            guids.append(id_to_guid[discord_id])
    
    return guids
```

### Update `_handle_voice_state_update()` method

Add team split detection to existing voice state handler:

```python
async def _handle_voice_state_update(self, member, before, after):
    # ... existing session detection logic ...
    
    # NEW: Check for team split (only during active session)
    if self.session_active and self.config.ENABLE_TEAM_SPLIT_DETECTION:
        await self._check_for_team_split()

async def _check_for_team_split(self):
    """Check if players have split into teams and trigger prediction."""
    # Cooldown check
    if self.last_split_time:
        elapsed = (datetime.now() - self.last_split_time).total_seconds() / 60
        if elapsed < self.prediction_cooldown_minutes:
            return  # Still in cooldown
    
    # Detect split
    split_data = await self._detect_team_split()
    
    if split_data and not self.team_split_detected:
        logger.info(f"🎯 Team split detected! {split_data['format']} format")
        self.team_split_detected = True
        self.last_split_time = datetime.now()
        self.team_a_guids = split_data['team_a_guids']
        self.team_b_guids = split_data['team_b_guids']
        
        # Trigger prediction (if enabled)
        if self.config.ENABLE_MATCH_PREDICTIONS:
            await self._trigger_match_prediction(split_data)
    
    elif not split_data and self.team_split_detected:
        # Teams merged back - reset
        logger.info("Teams merged back, resetting split detection")
        self.team_split_detected = False
```

---

## 🛠️ PHASE 3: PREDICTION ENGINE (16-20 hours)

### Goal
Build the brain that predicts match outcomes.

### New File: `bot/services/prediction_engine.py`

```python
"""
Match Prediction Engine
=======================
Predicts match outcomes based on:
- Head-to-head history (40% weight)
- Recent form (25% weight)
- Map performance (20% weight)
- Substitution impact (15% weight)
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class PredictionEngine:
    """
    Weighted prediction engine for ET:Legacy matches.
    
    Weights (configurable):
    - H2H_WEIGHT: 0.40 (head-to-head history)
    - FORM_WEIGHT: 0.25 (recent performance)
    - MAP_WEIGHT: 0.20 (map-specific performance)
    - SUB_WEIGHT: 0.15 (substitution impact)
    """
    
    # Configurable weights
    H2H_WEIGHT = 0.40
    FORM_WEIGHT = 0.25
    MAP_WEIGHT = 0.20
    SUB_WEIGHT = 0.15
    
    # Minimum data thresholds
    MIN_H2H_MATCHES = 3  # Need 3+ matches for H2H to count
    MIN_FORM_MATCHES = 5  # Need 5+ recent matches for form
    
    def __init__(self, db_adapter):
        self.db = db_adapter
    
    async def predict_match(
        self,
        team_a_guids: List[str],
        team_b_guids: List[str],
        map_name: Optional[str] = None
    ) -> Dict:
        """
        Generate match prediction with confidence scoring.
        
        Args:
            team_a_guids: List of player GUIDs for Team A
            team_b_guids: List of player GUIDs for Team B
            map_name: Optional map name for map-specific analysis
        
        Returns:
            {
                'team_a_win_probability': 0.65,
                'team_b_win_probability': 0.35,
                'confidence': 'high',  # high/medium/low
                'confidence_score': 0.85,
                'factors': {
                    'h2h': {'score': 0.7, 'details': '...', 'matches': 5},
                    'form': {'score': 0.6, 'details': '...'},
                    'map': {'score': 0.5, 'details': '...'},
                    'subs': {'score': 0.5, 'details': '...'}
                },
                'key_insight': 'Team A has won 4 of last 5 head-to-head matches'
            }
        """
        logger.info(f"Generating prediction: {len(team_a_guids)}v{len(team_b_guids)}")
        
        # Analyze each factor
        h2h = await self._analyze_head_to_head(team_a_guids, team_b_guids)
        form = await self._analyze_recent_form(team_a_guids, team_b_guids)
        map_perf = await self._analyze_map_performance(team_a_guids, team_b_guids, map_name)
        subs = await self._analyze_substitution_impact(team_a_guids, team_b_guids)
        
        # Calculate weighted score
        # Score > 0.5 means Team A favored, < 0.5 means Team B favored
        weighted_score = (
            h2h['score'] * self.H2H_WEIGHT +
            form['score'] * self.FORM_WEIGHT +
            map_perf['score'] * self.MAP_WEIGHT +
            subs['score'] * self.SUB_WEIGHT
        )
        
        # Convert to win probabilities
        # Apply sigmoid-like scaling to keep probabilities reasonable (30-70% range)
        team_a_prob = 0.3 + (weighted_score * 0.4)  # Maps 0-1 to 0.3-0.7
        team_b_prob = 1.0 - team_a_prob
        
        # Calculate confidence based on data availability
        confidence_score = self._calculate_confidence(h2h, form, map_perf, subs)
        confidence = self._score_to_confidence_label(confidence_score)
        
        # Generate key insight
        key_insight = self._generate_key_insight(h2h, form, map_perf, subs)
        
        return {
            'team_a_win_probability': round(team_a_prob, 2),
            'team_b_win_probability': round(team_b_prob, 2),
            'confidence': confidence,
            'confidence_score': round(confidence_score, 2),
            'factors': {
                'h2h': h2h,
                'form': form,
                'map': map_perf,
                'subs': subs
            },
            'key_insight': key_insight,
            'weighted_score': round(weighted_score, 3)
        }
    
    async def _analyze_head_to_head(
        self,
        team_a_guids: List[str],
        team_b_guids: List[str]
    ) -> Dict:
        """
        Analyze historical head-to-head matchups between these lineups.
        
        Returns score: >0.5 = Team A favored, <0.5 = Team B favored
        """
        # Find sessions where these teams (or similar) played each other
        # Use overlap percentage to find matches
        
        query = """
            WITH team_sessions AS (
                SELECT DISTINCT 
                    DATE(round_date) as session_date,
                    player_guid,
                    team
                FROM player_comprehensive_stats
                WHERE round_number IN (1, 2)
                  AND round_date > $1
            )
            SELECT session_date, team, array_agg(DISTINCT player_guid) as guids
            FROM team_sessions
            GROUP BY session_date, team
            ORDER BY session_date DESC
        """
        
        # Look back 90 days
        cutoff = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
        
        try:
            rows = await self.db.fetch_all(query, (cutoff,))
            
            # Find sessions with significant overlap
            team_a_wins = 0
            team_b_wins = 0
            total_matches = 0
            
            # Group by session
            sessions = {}
            for row in rows:
                session_date, team, guids = row
                if session_date not in sessions:
                    sessions[session_date] = {}
                sessions[session_date][team] = set(guids) if guids else set()
            
            # Check each session for overlap
            for session_date, teams in sessions.items():
                if 1 not in teams or 2 not in teams:
                    continue
                
                team1_guids = teams[1]
                team2_guids = teams[2]
                
                # Check overlap with current teams
                overlap_a_1 = len(set(team_a_guids) & team1_guids) / max(len(team_a_guids), 1)
                overlap_a_2 = len(set(team_a_guids) & team2_guids) / max(len(team_a_guids), 1)
                overlap_b_1 = len(set(team_b_guids) & team1_guids) / max(len(team_b_guids), 1)
                overlap_b_2 = len(set(team_b_guids) & team2_guids) / max(len(team_b_guids), 1)
                
                # Need >50% overlap to count as same team
                if overlap_a_1 > 0.5 and overlap_b_2 > 0.5:
                    # Team A was team 1, Team B was team 2
                    # TODO: Get winner from rounds table
                    total_matches += 1
                elif overlap_a_2 > 0.5 and overlap_b_1 > 0.5:
                    # Team A was team 2, Team B was team 1
                    total_matches += 1
            
            if total_matches < self.MIN_H2H_MATCHES:
                return {
                    'score': 0.5,
                    'details': f'Insufficient H2H data ({total_matches} matches)',
                    'matches': total_matches,
                    'team_a_wins': 0,
                    'team_b_wins': 0,
                    'confidence': 'low'
                }
            
            # Calculate score
            if team_a_wins + team_b_wins > 0:
                score = team_a_wins / (team_a_wins + team_b_wins)
            else:
                score = 0.5
            
            return {
                'score': score,
                'details': f'Team A leads {team_a_wins}-{team_b_wins} in H2H',
                'matches': total_matches,
                'team_a_wins': team_a_wins,
                'team_b_wins': team_b_wins,
                'confidence': 'high' if total_matches >= 5 else 'medium'
            }
            
        except Exception as e:
            logger.error(f"H2H analysis failed: {e}")
            return {
                'score': 0.5,
                'details': 'H2H analysis unavailable',
                'matches': 0,
                'confidence': 'low'
            }
    
    async def _analyze_recent_form(
        self,
        team_a_guids: List[str],
        team_b_guids: List[str]
    ) -> Dict:
        """
        Analyze recent form (last 5 sessions, regardless of opponent).
        """
        # Placeholder - implement similar to H2H
        return {
            'score': 0.5,
            'details': 'Form analysis not yet implemented',
            'team_a_form': '?-?',
            'team_b_form': '?-?',
            'confidence': 'low'
        }
    
    async def _analyze_map_performance(
        self,
        team_a_guids: List[str],
        team_b_guids: List[str],
        map_name: Optional[str]
    ) -> Dict:
        """
        Analyze map-specific performance.
        """
        if not map_name:
            return {
                'score': 0.5,
                'details': 'Map not specified',
                'confidence': 'low'
            }
        
        # Placeholder - implement map-specific analysis
        return {
            'score': 0.5,
            'details': f'Map performance on {map_name} not yet tracked',
            'confidence': 'low'
        }
    
    async def _analyze_substitution_impact(
        self,
        team_a_guids: List[str],
        team_b_guids: List[str]
    ) -> Dict:
        """
        Analyze impact of roster changes compared to typical lineups.
        """
        # Placeholder - check if teams have their regular players
        return {
            'score': 0.5,
            'details': 'Substitution analysis not yet implemented',
            'team_a_subs': 0,
            'team_b_subs': 0,
            'confidence': 'low'
        }
    
    def _calculate_confidence(
        self,
        h2h: Dict,
        form: Dict,
        map_perf: Dict,
        subs: Dict
    ) -> float:
        """Calculate overall prediction confidence (0-1)."""
        # Weight confidence by factor importance
        conf_scores = [
            (h2h.get('confidence', 'low'), self.H2H_WEIGHT),
            (form.get('confidence', 'low'), self.FORM_WEIGHT),
            (map_perf.get('confidence', 'low'), self.MAP_WEIGHT),
            (subs.get('confidence', 'low'), self.SUB_WEIGHT)
        ]
        
        conf_map = {'high': 1.0, 'medium': 0.6, 'low': 0.3}
        
        total = sum(conf_map.get(c, 0.3) * w for c, w in conf_scores)
        return total
    
    def _score_to_confidence_label(self, score: float) -> str:
        """Convert confidence score to label."""
        if score >= 0.7:
            return 'high'
        elif score >= 0.5:
            return 'medium'
        else:
            return 'low'
    
    def _generate_key_insight(
        self,
        h2h: Dict,
        form: Dict,
        map_perf: Dict,
        subs: Dict
    ) -> str:
        """Generate the most important insight for display."""
        insights = []
        
        if h2h.get('matches', 0) >= 3:
            insights.append(h2h.get('details', ''))
        
        if form.get('confidence') == 'high':
            insights.append(form.get('details', ''))
        
        if not insights:
            return "Limited historical data - prediction may be less accurate"
        
        return insights[0]
```

---

## 🛠️ PHASE 4: DATABASE TABLES (2 hours)

### New Tables for Competitive Analytics

Run this SQL on PostgreSQL:

```sql
-- 1. Lineup Performance (track team compositions)
CREATE TABLE IF NOT EXISTS lineup_performance (
    id SERIAL PRIMARY KEY,
    lineup_hash VARCHAR(64) UNIQUE NOT NULL,  -- Hash of sorted GUIDs
    player_guids JSONB NOT NULL,
    player_count INTEGER NOT NULL,
    total_sessions INTEGER DEFAULT 0,
    total_wins INTEGER DEFAULT 0,
    total_losses INTEGER DEFAULT 0,
    total_ties INTEGER DEFAULT 0,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Head-to-Head Matchups
CREATE TABLE IF NOT EXISTS head_to_head_matchups (
    id SERIAL PRIMARY KEY,
    team_a_hash VARCHAR(64) NOT NULL,
    team_b_hash VARCHAR(64) NOT NULL,
    session_date DATE NOT NULL,
    winner VARCHAR(10),  -- 'team_a', 'team_b', 'tie'
    score_a INTEGER,
    score_b INTEGER,
    maps_played INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(team_a_hash, team_b_hash, session_date)
);

-- 3. Map Performance
CREATE TABLE IF NOT EXISTS map_performance (
    id SERIAL PRIMARY KEY,
    lineup_hash VARCHAR(64) NOT NULL,
    map_name VARCHAR(100) NOT NULL,
    times_played INTEGER DEFAULT 0,
    times_won INTEGER DEFAULT 0,
    avg_completion_time REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(lineup_hash, map_name)
);

-- 4. Match Predictions
CREATE TABLE IF NOT EXISTS match_predictions (
    id SERIAL PRIMARY KEY,
    session_date DATE NOT NULL,
    prediction_time TIMESTAMP NOT NULL,
    team_a_guids JSONB NOT NULL,
    team_b_guids JSONB NOT NULL,
    team_a_probability REAL NOT NULL,
    team_b_probability REAL NOT NULL,
    confidence VARCHAR(20) NOT NULL,
    confidence_score REAL,
    factors JSONB,
    predicted_winner VARCHAR(10),  -- 'team_a' or 'team_b'
    actual_winner VARCHAR(10),  -- Filled after match
    prediction_correct BOOLEAN,  -- Filled after match
    final_score_a INTEGER,
    final_score_b INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_h2h_teams ON head_to_head_matchups(team_a_hash, team_b_hash);
CREATE INDEX idx_map_perf_lineup ON map_performance(lineup_hash);
CREATE INDEX idx_predictions_date ON match_predictions(session_date);
CREATE INDEX idx_predictions_accuracy ON match_predictions(prediction_correct) WHERE actual_winner IS NOT NULL;
```

---

## 🛠️ PHASE 5: FEATURE FLAGS (Add to config)

### File: `bot/config.py`

Add these configuration options:

```python
# ============================================================
# COMPETITIVE ANALYTICS FEATURE FLAGS
# ============================================================
# Enable/disable features without code changes

# Phase 2: Voice team split detection
ENABLE_TEAM_SPLIT_DETECTION: bool = False  # Set True after Phase 2 tested

# Phase 3: Match predictions
ENABLE_MATCH_PREDICTIONS: bool = False  # Set True after Phase 3 tested

# Phase 4: Live score updates
ENABLE_LIVE_SCORING: bool = False  # Set True after Phase 4 tested

# Always on for debugging
ENABLE_PREDICTION_LOGGING: bool = True

# Thresholds
PREDICTION_COOLDOWN_MINUTES: int = 5  # Min time between predictions
MIN_PLAYERS_FOR_PREDICTION: int = 6  # Minimum players for prediction
MIN_GUID_COVERAGE: float = 0.5  # 50% of players must have linked GUIDs
```

---

## 📋 IMPLEMENTATION CHECKLIST

### Phase 1: Database Adapter Refactoring (Week 1-2)
- [ ] Refactor `team_manager.py` - async + DatabaseAdapter
- [ ] Refactor `advanced_team_detector.py` - async + DatabaseAdapter  
- [ ] Refactor `substitution_detector.py` - async + DatabaseAdapter
- [ ] Refactor `team_history.py` - async + DatabaseAdapter
- [ ] Refactor `team_detector_integration.py` - async + DatabaseAdapter
- [ ] Refactor `achievement_system.py` - remove aiosqlite
- [ ] Update `team_cog.py` to await async methods
- [ ] Test all !team commands work
- [ ] Deploy to production

### Phase 2: Voice Enhancement (Week 3-4)
- [ ] Add feature flags to config
- [ ] Add `_detect_team_split()` to voice service
- [ ] Add `_resolve_discord_ids_to_guids()` method
- [ ] Update voice state handler to check for splits
- [ ] Test with live voice channels (flag ON)
- [ ] Deploy with flag OFF, then enable

### Phase 3: Prediction Engine (Week 5-8)
- [ ] Create `bot/services/prediction_engine.py`
- [ ] Implement H2H analysis
- [ ] Implement form analysis
- [ ] Implement map performance analysis
- [ ] Implement substitution impact analysis
- [ ] Create prediction Discord embed
- [ ] Connect to voice service trigger
- [ ] Test with historical data (>50% accuracy)
- [ ] Deploy with flag OFF, then enable

### Phase 4: Database Tables & Live Scoring (Week 9-10)
- [ ] Create new PostgreSQL tables
- [ ] Store predictions in database
- [ ] Connect SSH monitor to score updates
- [ ] Post live score updates to Discord
- [ ] Post final results with accuracy

### Phase 5: Refinement (Week 11-12)
- [ ] Track prediction accuracy over time
- [ ] Tune prediction weights based on results
- [ ] Add accuracy dashboard command
- [ ] Documentation and cleanup

---

## 🚨 ROLLBACK PROCEDURES

### Level 1: Feature Flag Disable (2 minutes)
```python
# In config.py or environment:
ENABLE_TEAM_SPLIT_DETECTION = False
ENABLE_MATCH_PREDICTIONS = False
ENABLE_LIVE_SCORING = False
# Restart bot
```

### Level 2: Git Revert (10 minutes)
```bash
git log --oneline -5  # Find last good commit
git revert HEAD  # Or specific commit
git push
# Restart bot
```

### Level 3: Database Rollback (30 minutes)
```sql
-- Drop new tables (doesn't affect existing data)
DROP TABLE IF EXISTS match_predictions;
DROP TABLE IF EXISTS lineup_performance;
DROP TABLE IF EXISTS head_to_head_matchups;
DROP TABLE IF EXISTS map_performance;
```

---

## ✅ SUCCESS CRITERIA

- [ ] **Phase 1:** All !team commands work with PostgreSQL
- [ ] **Phase 2:** Team splits detected accurately (no false positives)
- [ ] **Phase 3:** Predictions posted automatically, >50% accuracy
- [ ] **Phase 4:** Live scores update correctly
- [ ] **Phase 5:** >60% prediction accuracy over 20+ matches

---

**Document End**

*For Claude Code (Sonnet 4.5) - Follow phases in order, test thoroughly, use feature flags!*
