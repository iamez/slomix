# 🎯 Competitive Analytics Master Plan

**Project:** Automated Team Detection, Performance Tracking & Match Prediction
**Status:** Research & Planning Phase
**Created:** November 28, 2025
**Estimated Total Effort:** 80-120 hours

---

## 📋 Executive Summary

Transform the slomix Discord bot into a competitive esports analytics platform that automatically:

1. **Detects team formations** when players split into voice channels
2. **Predicts match outcomes** based on historical performance
3. **Tracks live scores** during gameplay
4. **Analyzes team chemistry** and substitution impact
5. **Provides post-match analytics** comparing predictions to results

**Key Design Principle:** Everything is automated - no manual commands. The bot observes, predicts, and reports automatically.

---

## 🏗️ System Architecture Overview

```sql
┌─────────────────────────────────────────────────────────────────┐
│                     DISCORD VOICE CHANNELS                       │
│  Gaming Channel (8 players) → Team A (4) + Team B (4)          │
└────────────────────┬────────────────────────────────────────────┘
                     │ Voice State Update Event
                     ↓
┌─────────────────────────────────────────────────────────────────┐
│              🎙️ VOICE CHANNEL MONITOR                          │
│  - Detects when players split into team channels                │
│  - Identifies player GUIDs for each team                        │
│  - Triggers prediction system                                   │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────────────┐
│          🔍 ADVANCED TEAM DETECTOR (Refactored)                 │
│  - Historical pattern analysis (past 10 sessions)               │
│  - Identifies regular lineups vs substitutes                    │
│  - Confidence scoring for team composition                      │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────────────┐
│          📊 TEAM PERFORMANCE ANALYZER                           │
│  - Win/loss records for specific lineups                       │
│  - Head-to-head matchup history                                │
│  - Map-specific performance                                     │
│  - Role effectiveness (not just fragging)                       │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────────────┐
│          🎯 MATCH PREDICTION ENGINE                             │
│  - Calculates win probability (0-100%)                         │
│  - Identifies key factors (lineup strength, matchups, etc.)    │
│  - Posts automated prediction to Discord                        │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────────────┐
│          📈 LIVE SCORE TRACKER                                  │
│  - Monitors database for new rounds                             │
│  - Updates scores after each map                                │
│  - Tracks prediction accuracy in real-time                      │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────────────┐
│          🏆 POST-MATCH ANALYSIS                                 │
│  - Final score vs prediction                                    │
│  - Lineup performance analysis                                  │
│  - Substitution impact report                                   │
│  - Updates historical database                                  │
└─────────────────────────────────────────────────────────────────┘
```sql

---

## 🎯 Core Design Principles

### 1. **Team-Based Metrics Over Individual Stats**

ET:Legacy stopwatch is about **coordination, timing, and objective play** - not just fragging.

**Traditional FPS Metrics (Less Important):**

- K/D ratio
- Damage per minute
- Headshot percentage

**Team Coordination Metrics (More Important):**

- **Objective completion rate** - How often do they complete map objectives?
- **Stopwatch efficiency** - Do they win rounds quickly or barely?
- **Defensive holds** - How often do they successfully defend?
- **Comeback ability** - Do they recover from losing first rounds?
- **Map pool strength** - Which maps do they dominate vs struggle?
- **Role fulfillment** - Engineers planting, medics reviving, etc.

**Lineup Synergy Metrics:**

- **Player combination win rate** - These 5 players together
- **Substitution impact** - Performance with sub vs without
- **Head-to-head record** - Team A vs Team B historically
- **Recent form** - Last 5 sessions performance trend

### 2. **Zero Manual Commands**

Everything happens automatically:

- ✅ Teams detected when voice channels split
- ✅ Prediction posted immediately
- ✅ Score updates after each map
- ✅ Final analysis when session ends
- ❌ NO `!predict` commands
- ❌ NO manual team registration

### 3. **Confidence Scoring**

Never make blind predictions:

- **High Confidence (>80%):** 20+ historical matchups, regular lineups
- **Medium Confidence (50-80%):** 10-20 matchups, some substitutes
- **Low Confidence (<50%):** <10 matchups, many new players

Display confidence to users:

```text
🎯 Match Prediction (High Confidence - 85%)
Team A: 68% win probability
Team B: 32% win probability

📊 Based on 23 historical matchups
🔑 Key Factors:
  • Team A won 15 of last 23 meetings
  • Team A dominates on these maps (8-2 record)
  • Team B has 1 substitute (Player X → Player Y)
```python

---

## 🔧 Technical Implementation Plan

---

## Phase 1: Voice Channel Team Detection (NEW SYSTEM)

**Estimated Effort:** 15-20 hours
**Risk Level:** Medium (new functionality)
**Dependencies:** None

### Current State

- ✅ Voice session detection working (6+ players = session start)
- ✅ Monitors `gaming_voice_channels` for total player count
- ❌ Does NOT track which specific channels players are in
- ❌ Does NOT detect team splits

### What Needs to Be Built

#### 1.1: Enhanced Voice State Tracking

**File:** `bot/services/voice_session_service.py`

**New Data Structure:**

```python
class VoiceSessionService:
    def __init__(self, ...):
        # Existing
        self.session_participants: Set[int] = set()

        # NEW: Track which channel each player is in
        self.channel_distribution: Dict[int, Set[int]] = {}  # {channel_id: {user_ids}}
        self.team_channels_detected: bool = False
        self.team_a_channel_id: Optional[int] = None
        self.team_b_channel_id: Optional[int] = None
```text

#### 1.2: Team Split Detection Algorithm

**New Method:** `detect_team_formation()`

**Logic:**

```python
async def detect_team_formation(self) -> Optional[Dict[str, List[int]]]:
    """
    Detect when players split into two roughly equal team channels.

    Returns:
        {
            'team_a': [user_id1, user_id2, user_id3, user_id4],
            'team_b': [user_id5, user_id6, user_id7, user_id8],
            'format': '4v4',  # or '3v3', '5v5', '6v6'
            'confidence': 'high'  # high if exact split, medium if uneven
        }
        None if no clear team split detected
    """

    # 1. Count players in each gaming voice channel
    distribution = {}
    for channel_id in self.config.gaming_voice_channels:
        channel = self.bot.get_channel(channel_id)
        if channel:
            distribution[channel_id] = set(m.id for m in channel.members)

    # 2. Find channels with players
    active_channels = {cid: users for cid, users in distribution.items() if users}

    # 3. Detect if split into exactly 2 channels
    if len(active_channels) != 2:
        return None  # Not a team split (still gathering, or 3+ way split)

    # 4. Check if roughly equal teams
    channels = list(active_channels.items())
    channel_a_id, users_a = channels[0]
    channel_b_id, users_b = channels[1]

    count_a = len(users_a)
    count_b = len(users_b)

    # 5. Determine if this is a valid team format
    total = count_a + count_b
    diff = abs(count_a - count_b)

    # Allow max difference of 1 player (e.g., 4v3 is OK, 5v3 is not)
    if diff > 1:
        return None  # Too uneven

    # 6. Determine format
    if total == 6:
        format_str = "3v3"
    elif total == 8:
        format_str = "4v4"
    elif total == 10:
        format_str = "5v5"
    elif total == 12:
        format_str = "6v6"
    else:
        format_str = f"{count_a}v{count_b}"

    # 7. Confidence based on balance
    confidence = "high" if diff == 0 else "medium"

    return {
        'team_a': list(users_a),
        'team_b': list(users_b),
        'team_a_channel_id': channel_a_id,
        'team_b_channel_id': channel_b_id,
        'format': format_str,
        'confidence': confidence,
        'total_players': total
    }
```text

#### 1.3: Integration with Voice State Updates

**Modified Method:** `handle_voice_state_change()`

```python
async def handle_voice_state_change(self, member, before, after):
    # ... existing session start/end logic ...

    # NEW: Check for team formation AFTER session starts
    if self.session_active and not self.team_channels_detected:
        teams = await self.detect_team_formation()

        if teams:
            self.team_channels_detected = True
            self.team_a_channel_id = teams['team_a_channel_id']
            self.team_b_channel_id = teams['team_b_channel_id']

            logger.info(f"🎮 TEAMS FORMED! {teams['format']} detected")
            logger.info(f"   Team A: {len(teams['team_a'])} players in channel {teams['team_a_channel_id']}")
            logger.info(f"   Team B: {len(teams['team_b'])} players in channel {teams['team_b_channel_id']}")

            # TRIGGER PREDICTION SYSTEM
            await self.trigger_match_prediction(teams)
```text

#### 1.4: Map Discord User IDs to Player GUIDs

**New Method:** `map_users_to_guids()`

```python
async def map_users_to_guids(self, user_ids: List[int]) -> List[str]:
    """
    Map Discord user IDs to ET:Legacy player GUIDs.

    Uses linked_accounts table to find GUIDs.
    Falls back to recent session history if no link exists.
    """
    guids = []

    for user_id in user_ids:
        # Query linked_accounts table
        query = "SELECT player_guid FROM linked_accounts WHERE discord_id = $1"
        result = await self.db_adapter.fetch_one(query, (user_id,))

        if result:
            guids.append(result[0])
        else:
            # Fallback: Check recent sessions for this Discord user
            # (This assumes player_comprehensive_stats has discord_id field)
            logger.warning(f"No linked GUID for Discord user {user_id}, using fallback")
            # TODO: Implement fallback logic

    return guids
```text

**Database Schema Needed:**

```sql
-- New table to link Discord users to player GUIDs
CREATE TABLE IF NOT EXISTS linked_accounts (
    discord_id BIGINT PRIMARY KEY,
    player_guid TEXT NOT NULL,
    player_name TEXT,
    linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    verified BOOLEAN DEFAULT FALSE
);

-- Index for fast lookups
CREATE INDEX idx_linked_accounts_guid ON linked_accounts(player_guid);
```python

---

## Phase 2: Refactor Advanced Team Detection

**Estimated Effort:** 20-30 hours
**Risk Level:** High (major refactoring)
**Dependencies:** Phase 1

### Current Issues

- ❌ Uses `sqlite3.Connection` instead of DatabaseAdapter
- ❌ Not imported anywhere in production code
- ❌ Incompatible with current architecture

### Refactoring Tasks

#### 2.1: Database Adapter Migration

**Files to Refactor:**

- `bot/core/advanced_team_detector.py`
- `bot/core/team_detector_integration.py`
- `bot/core/substitution_detector.py`
- `bot/core/team_history.py`

**Changes:**

```python
# OLD (sqlite3)
def detect_teams(self, db: sqlite3.Connection, session_date: str):
    cursor = db.cursor()
    cursor.execute("SELECT ...")

# NEW (DatabaseAdapter)
async def detect_teams(self, session_date: str) -> Dict:
    query = "SELECT ..."
    if self.db_adapter.db_type == 'postgresql':
        query = query.replace('?', '$1')  # PostgreSQL uses $1, $2 instead of ?

    results = await self.db_adapter.fetch_all(query, (session_date,))
```python

#### 2.2: Async/Await Conversion

All methods must be converted to `async def`:

```python
# OLD (sync)
def analyze_historical_patterns(self, player_guids: List[str]) -> Dict:
    # Blocking database calls

# NEW (async)
async def analyze_historical_patterns(self, player_guids: List[str]) -> Dict:
    # Non-blocking async database calls
    results = await self.db_adapter.fetch_all(...)
```text

#### 2.3: Remove Direct Database Dependencies

**Current:** Modules create their own database connections
**New:** Use DatabaseAdapter injected via constructor

```python
class AdvancedTeamDetector:
    def __init__(self, db_adapter: DatabaseAdapter):
        self.db_adapter = db_adapter
        # NO self.db_path or sqlite3.connect()
```python

#### 2.4: Update Integration Layer

**File:** `bot/core/team_detector_integration.py`

Make it compatible with current bot architecture:

```python
class TeamDetectorIntegration:
    def __init__(self, db_adapter: DatabaseAdapter, config: BotConfig):
        self.db_adapter = db_adapter
        self.config = config
        self.advanced_detector = AdvancedTeamDetector(db_adapter)
        self.substitution_detector = SubstitutionDetector(db_adapter)

    async def analyze_and_predict(
        self,
        team_a_guids: List[str],
        team_b_guids: List[str]
    ) -> Dict:
        """
        Full analysis: detection + substitution + performance
        Returns comprehensive team intelligence for prediction.
        """
        # Detection confidence
        detection = await self.advanced_detector.detect_with_confidence(
            team_a_guids, team_b_guids
        )

        # Substitution analysis
        subs = await self.substitution_detector.detect_substitutions(
            team_a_guids, team_b_guids
        )

        # Historical performance
        performance = await self.analyze_team_performance(
            team_a_guids, team_b_guids
        )

        return {
            'detection': detection,
            'substitutions': subs,
            'performance': performance
        }
```yaml

---

## Phase 3: Team Performance & Historical Analysis

**Estimated Effort:** 15-20 hours
**Risk Level:** Medium
**Dependencies:** Phase 2

### Database Schema

#### 3.1: New Tables

**Table: `lineup_performance`**

```sql
CREATE TABLE lineup_performance (
    id SERIAL PRIMARY KEY,
    lineup_hash TEXT NOT NULL,  -- MD5 of sorted player GUIDs
    player_guids JSONB NOT NULL,  -- ["guid1", "guid2", ...]
    player_names JSONB NOT NULL,  -- ["Player1", "Player2", ...]
    total_matches INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    ties INTEGER DEFAULT 0,
    total_maps_won INTEGER DEFAULT 0,
    total_maps_lost INTEGER DEFAULT 0,
    last_played TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(lineup_hash)
);

CREATE INDEX idx_lineup_hash ON lineup_performance(lineup_hash);
CREATE INDEX idx_last_played ON lineup_performance(last_played DESC);
```text

**Table: `head_to_head_matchups`**

```sql
CREATE TABLE head_to_head_matchups (
    id SERIAL PRIMARY KEY,
    team_a_lineup_hash TEXT NOT NULL,
    team_b_lineup_hash TEXT NOT NULL,
    session_date TEXT NOT NULL,
    team_a_score INTEGER NOT NULL,  -- Maps won
    team_b_score INTEGER NOT NULL,
    total_maps INTEGER NOT NULL,
    winner TEXT,  -- 'team_a', 'team_b', 'tie'
    played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_h2h_matchups ON head_to_head_matchups(team_a_lineup_hash, team_b_lineup_hash);
CREATE INDEX idx_h2h_date ON head_to_head_matchups(session_date DESC);
```text

**Table: `map_performance`**

```sql
CREATE TABLE map_performance (
    id SERIAL PRIMARY KEY,
    lineup_hash TEXT NOT NULL,
    map_name TEXT NOT NULL,
    times_played INTEGER DEFAULT 0,
    times_won INTEGER DEFAULT 0,
    avg_completion_time REAL,  -- Average time to complete objective
    avg_defense_time REAL,  -- Average time held when defending
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(lineup_hash, map_name)
);

CREATE INDEX idx_map_perf_lineup ON map_performance(lineup_hash);
CREATE INDEX idx_map_perf_map ON map_performance(map_name);
```python

#### 3.2: Performance Analyzer Class

**File:** `bot/services/team_performance_analyzer.py` (NEW)

```python
class TeamPerformanceAnalyzer:
    """
    Analyzes team performance for predictions.
    Focuses on team metrics, not individual stats.
    """

    def __init__(self, db_adapter: DatabaseAdapter):
        self.db_adapter = db_adapter

    def calculate_lineup_hash(self, guids: List[str]) -> str:
        """Generate consistent hash for lineup (sorted)"""
        import hashlib
        sorted_guids = sorted(guids)
        return hashlib.md5(''.join(sorted_guids).encode()).hexdigest()

    async def get_lineup_stats(self, guids: List[str]) -> Dict:
        """
        Get historical performance for this exact lineup.

        Returns:
            {
                'matches_played': 15,
                'wins': 10,
                'losses': 4,
                'ties': 1,
                'win_rate': 66.7,
                'recent_form': [1, 1, 0, 1, 1],  # Last 5: 1=win, 0=loss
                'maps_won': 28,
                'maps_lost': 12,
                'maps_win_rate': 70.0
            }
        """
        lineup_hash = self.calculate_lineup_hash(guids)

        query = """
            SELECT total_matches, wins, losses, ties,
                   total_maps_won, total_maps_lost, last_played
            FROM lineup_performance
            WHERE lineup_hash = $1
        """

        result = await self.db_adapter.fetch_one(query, (lineup_hash,))

        if not result:
            return self._empty_stats()

        matches, wins, losses, ties, maps_won, maps_lost, last_played = result

        # Calculate win rate
        win_rate = (wins / matches * 100) if matches > 0 else 0.0
        maps_win_rate = (maps_won / (maps_won + maps_lost) * 100) if (maps_won + maps_lost) > 0 else 0.0

        # Get recent form (last 5 matches)
        recent_form = await self._get_recent_form(lineup_hash, limit=5)

        return {
            'matches_played': matches,
            'wins': wins,
            'losses': losses,
            'ties': ties,
            'win_rate': round(win_rate, 1),
            'recent_form': recent_form,
            'maps_won': maps_won,
            'maps_lost': maps_lost,
            'maps_win_rate': round(maps_win_rate, 1),
            'last_played': last_played
        }

    async def get_head_to_head(
        self,
        team_a_guids: List[str],
        team_b_guids: List[str]
    ) -> Dict:
        """
        Get head-to-head record between these two specific lineups.

        Returns:
            {
                'total_matchups': 10,
                'team_a_wins': 6,
                'team_b_wins': 3,
                'ties': 1,
                'team_a_maps_won': 52,
                'team_b_maps_won': 28,
                'recent_results': ['team_a', 'team_a', 'team_b', 'team_a', 'tie']
            }
        """
        hash_a = self.calculate_lineup_hash(team_a_guids)
        hash_b = self.calculate_lineup_hash(team_b_guids)

        query = """
            SELECT session_date, team_a_score, team_b_score, winner, played_at
            FROM head_to_head_matchups
            WHERE (team_a_lineup_hash = $1 AND team_b_lineup_hash = $2)
               OR (team_a_lineup_hash = $2 AND team_b_lineup_hash = $1)
            ORDER BY played_at DESC
        """

        results = await self.db_adapter.fetch_all(query, (hash_a, hash_b))

        if not results:
            return self._empty_h2h()

        # Analyze results
        team_a_wins = 0
        team_b_wins = 0
        ties = 0
        team_a_maps = 0
        team_b_maps = 0
        recent_results = []

        for row in results:
            session_date, a_score, b_score, winner, played_at = row

            # Normalize: ensure we're counting from team_a's perspective
            if row[0] == hash_a:  # team_a was listed first in this record
                team_a_maps += a_score
                team_b_maps += b_score
                if winner == 'team_a':
                    team_a_wins += 1
                    recent_results.append('team_a')
                elif winner == 'team_b':
                    team_b_wins += 1
                    recent_results.append('team_b')
                else:
                    ties += 1
                    recent_results.append('tie')
            else:  # team_a was listed second, swap
                team_a_maps += b_score
                team_b_maps += a_score
                if winner == 'team_b':
                    team_a_wins += 1
                    recent_results.append('team_a')
                elif winner == 'team_a':
                    team_b_wins += 1
                    recent_results.append('team_b')
                else:
                    ties += 1
                    recent_results.append('tie')

        return {
            'total_matchups': len(results),
            'team_a_wins': team_a_wins,
            'team_b_wins': team_b_wins,
            'ties': ties,
            'team_a_maps_won': team_a_maps,
            'team_b_maps_won': team_b_maps,
            'recent_results': recent_results[:5]  # Last 5 only
        }

    async def get_map_pool_analysis(
        self,
        team_a_guids: List[str],
        team_b_guids: List[str],
        maps_to_play: List[str]
    ) -> Dict:
        """
        Analyze how each team performs on the maps to be played.

        Returns which team has advantage on which maps.
        """
        hash_a = self.calculate_lineup_hash(team_a_guids)
        hash_b = self.calculate_lineup_hash(team_b_guids)

        map_advantages = []

        for map_name in maps_to_play:
            # Get both teams' performance on this map
            query = """
                SELECT times_played, times_won, avg_completion_time, avg_defense_time
                FROM map_performance
                WHERE lineup_hash = $1 AND map_name = $2
            """

            team_a_perf = await self.db_adapter.fetch_one(query, (hash_a, map_name))
            team_b_perf = await self.db_adapter.fetch_one(query, (hash_b, map_name))

            # Calculate win rates
            a_win_rate = (team_a_perf[1] / team_a_perf[0] * 100) if team_a_perf and team_a_perf[0] > 0 else None
            b_win_rate = (team_b_perf[1] / team_b_perf[0] * 100) if team_b_perf and team_b_perf[0] > 0 else None

            # Determine advantage
            if a_win_rate and b_win_rate:
                diff = a_win_rate - b_win_rate
                if diff > 10:
                    advantage = 'team_a'
                elif diff < -10:
                    advantage = 'team_b'
                else:
                    advantage = 'neutral'
            else:
                advantage = 'unknown'

            map_advantages.append({
                'map_name': map_name,
                'team_a_win_rate': a_win_rate,
                'team_b_win_rate': b_win_rate,
                'advantage': advantage
            })

        return {
            'maps': map_advantages,
            'team_a_favored_maps': len([m for m in map_advantages if m['advantage'] == 'team_a']),
            'team_b_favored_maps': len([m for m in map_advantages if m['advantage'] == 'team_b']),
            'neutral_maps': len([m for m in map_advantages if m['advantage'] == 'neutral'])
        }
```python

---

## Phase 4: Match Prediction Engine

**Estimated Effort:** 25-35 hours
**Risk Level:** High (complex algorithm)
**Dependencies:** Phase 3

### Prediction Algorithm

#### 4.1: Prediction Engine Class

**File:** `bot/services/match_predictor.py` (NEW)

```python
class MatchPredictor:
    """
    Predicts match outcomes based on team composition and historical data.

    Uses weighted factors:
    - Head-to-head record (40%)
    - Recent form (25%)
    - Map pool strength (20%)
    - Substitution impact (15%)
    """

    def __init__(self, db_adapter: DatabaseAdapter, performance_analyzer: TeamPerformanceAnalyzer):
        self.db_adapter = db_adapter
        self.analyzer = performance_analyzer

        # Weights for prediction factors
        self.WEIGHTS = {
            'head_to_head': 0.40,
            'recent_form': 0.25,
            'map_pool': 0.20,
            'substitutions': 0.15
        }

    async def predict_match(
        self,
        team_a_guids: List[str],
        team_b_guids: List[str],
        maps_to_play: Optional[List[str]] = None
    ) -> Dict:
        """
        Generate match prediction.

        Returns:
            {
                'team_a_win_probability': 0.68,  # 68%
                'team_b_win_probability': 0.32,  # 32%
                'confidence': 0.85,  # 85% confident in this prediction
                'confidence_level': 'high',  # 'high', 'medium', 'low'
                'factors': {
                    'head_to_head': {...},
                    'recent_form': {...},
                    'map_pool': {...},
                    'substitutions': {...}
                },
                'key_insights': [
                    "Team A won 15 of last 23 matchups",
                    "Team A dominates on 3 of 5 maps",
                    "Team B has 1 substitute"
                ],
                'prediction_basis': 'Based on 23 historical matchups'
            }
        """

        # 1. Gather all analysis data
        h2h = await self.analyzer.get_head_to_head(team_a_guids, team_b_guids)
        team_a_stats = await self.analyzer.get_lineup_stats(team_a_guids)
        team_b_stats = await self.analyzer.get_lineup_stats(team_b_guids)

        map_analysis = None
        if maps_to_play:
            map_analysis = await self.analyzer.get_map_pool_analysis(
                team_a_guids, team_b_guids, maps_to_play
            )

        # TODO: Substitution analysis (Phase 5)
        sub_impact = {'team_a_subs': 0, 'team_b_subs': 0}

        # 2. Calculate prediction scores for each factor
        factors = {}

        # Factor 1: Head-to-Head (40% weight)
        factors['head_to_head'] = self._analyze_h2h_factor(h2h)

        # Factor 2: Recent Form (25% weight)
        factors['recent_form'] = self._analyze_form_factor(team_a_stats, team_b_stats)

        # Factor 3: Map Pool (20% weight)
        factors['map_pool'] = self._analyze_map_factor(map_analysis) if map_analysis else {'score_a': 0.5, 'score_b': 0.5}

        # Factor 4: Substitutions (15% weight)
        factors['substitutions'] = self._analyze_sub_factor(sub_impact)

        # 3. Weighted probability calculation
        team_a_prob = (
            factors['head_to_head']['score_a'] * self.WEIGHTS['head_to_head'] +
            factors['recent_form']['score_a'] * self.WEIGHTS['recent_form'] +
            factors['map_pool']['score_a'] * self.WEIGHTS['map_pool'] +
            factors['substitutions']['score_a'] * self.WEIGHTS['substitutions']
        )

        team_b_prob = 1.0 - team_a_prob

        # 4. Calculate confidence
        confidence, confidence_level = self._calculate_confidence(
            h2h, team_a_stats, team_b_stats
        )

        # 5. Generate key insights
        insights = self._generate_insights(
            h2h, team_a_stats, team_b_stats, map_analysis, factors
        )

        # 6. Prediction basis
        basis = self._generate_basis(h2h, team_a_stats, team_b_stats)

        return {
            'team_a_win_probability': round(team_a_prob, 2),
            'team_b_win_probability': round(team_b_prob, 2),
            'confidence': round(confidence, 2),
            'confidence_level': confidence_level,
            'factors': factors,
            'key_insights': insights,
            'prediction_basis': basis
        }

    def _analyze_h2h_factor(self, h2h: Dict) -> Dict:
        """
        Analyze head-to-head record.
        Returns score between 0.0 (Team B dominated) and 1.0 (Team A dominated)
        """
        total = h2h['total_matchups']

        if total == 0:
            # No history - neutral
            return {
                'score_a': 0.5,
                'score_b': 0.5,
                'description': "No historical matchups"
            }

        # Calculate win rates
        a_wins = h2h['team_a_wins']
        b_wins = h2h['team_b_wins']
        ties = h2h['ties']

        # Convert to score (0.0-1.0 for Team A)
        # Ties count as 0.5 wins for each team
        effective_a_wins = a_wins + (ties * 0.5)
        score_a = effective_a_wins / total

        # Weight recent results more heavily (last 5 matches)
        recent = h2h['recent_results'][:5]
        if len(recent) >= 3:
            recent_a_wins = recent.count('team_a') + (recent.count('tie') * 0.5)
            recent_score_a = recent_a_wins / len(recent)

            # Blend: 60% all-time, 40% recent
            score_a = (score_a * 0.6) + (recent_score_a * 0.4)

        return {
            'score_a': score_a,
            'score_b': 1.0 - score_a,
            'description': f"Team A won {a_wins} of {total} matchups ({a_wins/total*100:.0f}%)"
        }

    def _analyze_form_factor(self, team_a_stats: Dict, team_b_stats: Dict) -> Dict:
        """
        Analyze recent form (last 5 matches).
        """
        a_form = team_a_stats['recent_form']
        b_form = team_b_stats['recent_form']

        if not a_form or not b_form:
            return {
                'score_a': 0.5,
                'score_b': 0.5,
                'description': "Insufficient recent form data"
            }

        # Calculate win rate from recent form
        a_recent_wins = a_form.count(1)
        b_recent_wins = b_form.count(1)

        a_rate = a_recent_wins / len(a_form)
        b_rate = b_recent_wins / len(b_form)

        # Normalize to 0.0-1.0
        if a_rate + b_rate == 0:
            score_a = 0.5
        else:
            score_a = a_rate / (a_rate + b_rate)

        return {
            'score_a': score_a,
            'score_b': 1.0 - score_a,
            'description': f"Recent form: Team A {a_recent_wins}/5, Team B {b_recent_wins}/5"
        }

    def _analyze_map_factor(self, map_analysis: Dict) -> Dict:
        """
        Analyze map pool advantage.
        """
        if not map_analysis:
            return {'score_a': 0.5, 'score_b': 0.5, 'description': "No map data"}

        a_favored = map_analysis['team_a_favored_maps']
        b_favored = map_analysis['team_b_favored_maps']
        neutral = map_analysis['neutral_maps']

        total_maps = a_favored + b_favored + neutral

        if total_maps == 0:
            return {'score_a': 0.5, 'score_b': 0.5, 'description': "No map data"}

        # Score based on map advantage
        # Neutral maps count as 0.5 for each team
        score_a = (a_favored + neutral * 0.5) / total_maps

        return {
            'score_a': score_a,
            'score_b': 1.0 - score_a,
            'description': f"Team A favored on {a_favored}/{total_maps} maps"
        }

    def _analyze_sub_factor(self, sub_impact: Dict) -> Dict:
        """
        Analyze substitution impact.

        Substitutes generally hurt performance slightly.
        """
        a_subs = sub_impact['team_a_subs']
        b_subs = sub_impact['team_b_subs']

        # Each sub reduces score by ~5%
        a_penalty = a_subs * 0.05
        b_penalty = b_subs * 0.05

        # Start at neutral (0.5) and apply penalties
        score_a = 0.5 - a_penalty + b_penalty

        # Clamp to 0.2-0.8 range
        score_a = max(0.2, min(0.8, score_a))

        if a_subs == 0 and b_subs == 0:
            desc = "No substitutes on either team"
        elif a_subs > 0 and b_subs == 0:
            desc = f"Team A has {a_subs} substitute(s)"
        elif b_subs > 0 and a_subs == 0:
            desc = f"Team B has {b_subs} substitute(s)"
        else:
            desc = f"Team A: {a_subs} subs, Team B: {b_subs} subs"

        return {
            'score_a': score_a,
            'score_b': 1.0 - score_a,
            'description': desc
        }

    def _calculate_confidence(
        self,
        h2h: Dict,
        team_a_stats: Dict,
        team_b_stats: Dict
    ) -> Tuple[float, str]:
        """
        Calculate confidence in prediction.

        High confidence requires:
        - Many historical matchups (20+)
        - Regular lineups (not many subs)
        - Recent data (played within last month)
        """

        confidence_score = 0.0

        # Factor 1: Number of matchups (max 50 points)
        matchups = h2h['total_matchups']
        if matchups >= 20:
            confidence_score += 50
        elif matchups >= 10:
            confidence_score += 35
        elif matchups >= 5:
            confidence_score += 20
        elif matchups >= 2:
            confidence_score += 10

        # Factor 2: Team familiarity (max 30 points)
        a_matches = team_a_stats['matches_played']
        b_matches = team_b_stats['matches_played']

        if a_matches >= 10 and b_matches >= 10:
            confidence_score += 30
        elif a_matches >= 5 and b_matches >= 5:
            confidence_score += 20
        elif a_matches >= 2 and b_matches >= 2:
            confidence_score += 10

        # Factor 3: Data recency (max 20 points)
        # TODO: Check if last_played is recent
        confidence_score += 10  # Placeholder

        # Convert to 0.0-1.0 scale
        confidence = confidence_score / 100.0

        # Determine level
        if confidence >= 0.80:
            level = 'high'
        elif confidence >= 0.50:
            level = 'medium'
        else:
            level = 'low'

        return confidence, level

    def _generate_insights(
        self,
        h2h: Dict,
        team_a_stats: Dict,
        team_b_stats: Dict,
        map_analysis: Optional[Dict],
        factors: Dict
    ) -> List[str]:
        """
        Generate human-readable insights.
        """
        insights = []

        # H2H insight
        if h2h['total_matchups'] > 0:
            a_wins = h2h['team_a_wins']
            total = h2h['total_matchups']
            insights.append(f"Team A won {a_wins} of last {total} meetings")

        # Recent form
        if team_a_stats['recent_form'] and team_b_stats['recent_form']:
            a_wins = team_a_stats['recent_form'].count(1)
            b_wins = team_b_stats['recent_form'].count(1)

            if a_wins >= 4:
                insights.append("Team A on a hot streak (4+ recent wins)")
            elif b_wins >= 4:
                insights.append("Team B on a hot streak (4+ recent wins)")

        # Map pool
        if map_analysis:
            a_favored = map_analysis['team_a_favored_maps']
            b_favored = map_analysis['team_b_favored_maps']

            if a_favored > b_favored:
                insights.append(f"Team A favored on {a_favored} maps")
            elif b_favored > a_favored:
                insights.append(f"Team B favored on {b_favored} maps")

        # Substitutions
        sub_desc = factors['substitutions']['description']
        if 'substitute' in sub_desc.lower():
            insights.append(sub_desc)

        return insights[:5]  # Max 5 insights

    def _generate_basis(
        self,
        h2h: Dict,
        team_a_stats: Dict,
        team_b_stats: Dict
    ) -> str:
        """
        Generate description of prediction basis.
        """
        matchups = h2h['total_matchups']
        a_matches = team_a_stats['matches_played']
        b_matches = team_b_stats['matches_played']

        if matchups >= 10:
            return f"Based on {matchups} historical matchups"
        elif matchups >= 5:
            return f"Based on {matchups} matchups and team history"
        elif matchups > 0:
            return f"Limited data: {matchups} matchups, prediction less reliable"
        else:
            return f"No direct matchups, based on team records ({a_matches} vs {b_matches} matches)"
```python

#### 4.2: Integration with Voice Service

**File:** `bot/services/voice_session_service.py`

Add method to trigger prediction:

```python
async def trigger_match_prediction(self, teams: Dict):
    """
    Called when teams are formed in voice channels.
    Generates and posts match prediction.
    """
    logger.info("🎯 Generating match prediction...")

    # 1. Map Discord user IDs to player GUIDs
    team_a_users = teams['team_a']
    team_b_users = teams['team_b']

    team_a_guids = await self.map_users_to_guids(team_a_users)
    team_b_guids = await self.map_users_to_guids(team_b_users)

    # 2. Get player names for display
    team_a_names = await self._get_player_names(team_a_guids)
    team_b_names = await self._get_player_names(team_b_guids)

    # 3. Create predictor
    from bot.services.team_performance_analyzer import TeamPerformanceAnalyzer
    from bot.services.match_predictor import MatchPredictor

    analyzer = TeamPerformanceAnalyzer(self.db_adapter)
    predictor = MatchPredictor(self.db_adapter, analyzer)

    # 4. Generate prediction
    prediction = await predictor.predict_match(team_a_guids, team_b_guids)

    # 5. Post to Discord
    await self._post_prediction_embed(
        teams, team_a_names, team_b_names, prediction
    )

    # 6. Store prediction for later comparison
    await self._store_prediction(
        team_a_guids, team_b_guids, prediction, datetime.utcnow()
    )

async def _post_prediction_embed(
    self,
    teams: Dict,
    team_a_names: List[str],
    team_b_names: List[str],
    prediction: Dict
):
    """
    Post prediction embed to Discord.
    """
    channel = self.bot.get_channel(self.config.production_channel_id)
    if not channel:
        return

    # Determine emoji based on confidence
    if prediction['confidence_level'] == 'high':
        conf_emoji = '🎯'
    elif prediction['confidence_level'] == 'medium':
        conf_emoji = '🎲'
    else:
        conf_emoji = '❓'

    # Build embed
    embed = discord.Embed(
        title=f"{conf_emoji} Match Prediction ({teams['format']})",
        description=prediction['prediction_basis'],
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow()
    )

    # Team A
    team_a_prob = int(prediction['team_a_win_probability'] * 100)
    embed.add_field(
        name="🔴 Team A",
        value=f"**{team_a_prob}% win probability**\n" + "\n".join(team_a_names),
        inline=True
    )

    # Team B
    team_b_prob = int(prediction['team_b_win_probability'] * 100)
    embed.add_field(
        name="🔵 Team B",
        value=f"**{team_b_prob}% win probability**\n" + "\n".join(team_b_names),
        inline=True
    )

    # Key Insights
    if prediction['key_insights']:
        insights_text = "\n".join([f"• {insight}" for insight in prediction['key_insights']])
        embed.add_field(
            name="🔑 Key Factors",
            value=insights_text,
            inline=False
        )

    # Confidence
    conf_text = f"{int(prediction['confidence'] * 100)}% - {prediction['confidence_level'].upper()}"
    embed.add_field(
        name="📊 Prediction Confidence",
        value=conf_text,
        inline=False
    )

    embed.set_footer(text="Prediction will be tracked for accuracy")

    await channel.send(embed=embed)
    logger.info("✅ Prediction posted to Discord")
```python

---

## Phase 5: Live Score Tracking & Post-Match Analysis

**Estimated Effort:** 10-15 hours
**Risk Level:** Low
**Dependencies:** Phase 4

### Implementation

#### 5.1: Score Monitor Service

**File:** `bot/services/live_score_monitor.py` (NEW)

```python
class LiveScoreMonitor:
    """
    Monitors database for new rounds and updates scores live.
    """

    def __init__(self, bot, db_adapter, config):
        self.bot = bot
        self.db_adapter = db_adapter
        self.config = config

        self.active_match = None  # {session_date, team_a, team_b, prediction, score_a, score_b}

    async def start_monitoring(
        self,
        session_date: str,
        team_a_guids: List[str],
        team_b_guids: List[str],
        prediction: Dict
    ):
        """
        Begin monitoring this session for live score updates.
        """
        self.active_match = {
            'session_date': session_date,
            'team_a_guids': team_a_guids,
            'team_b_guids': team_b_guids,
            'prediction': prediction,
            'score_a': 0,
            'score_b': 0,
            'maps_completed': 0,
            'last_check': datetime.utcnow()
        }

        logger.info(f"📊 Live score monitoring started for {session_date}")

    async def check_for_updates(self):
        """
        Check database for new completed maps.
        Called periodically (every 30 seconds during active match).
        """
        if not self.active_match:
            return

        # Query for completed maps since last check
        query = """
            SELECT map_name, winner_team, round_number
            FROM rounds
            WHERE session_date = $1
              AND round_number > 0  -- Exclude R0
              AND created_at > $2
            ORDER BY created_at ASC
        """

        new_rounds = await self.db_adapter.fetch_all(
            query,
            (self.active_match['session_date'], self.active_match['last_check'])
        )

        if not new_rounds:
            return

        # Group rounds into maps (R1 + R2 pairs)
        maps_completed = self._group_into_maps(new_rounds)

        for map_data in maps_completed:
            await self._process_completed_map(map_data)

        self.active_match['last_check'] = datetime.utcnow()

    async def _process_completed_map(self, map_data: Dict):
        """
        Process a completed map and post score update.
        """
        # Calculate map score using StopwatchScoring
        from tools.stopwatch_scoring import StopwatchScoring
        scorer = StopwatchScoring()

        # TODO: Extract times from database
        # score_a, score_b, description = scorer.calculate_map_score(...)

        # Update match score
        self.active_match['score_a'] += score_a
        self.active_match['score_b'] += score_b
        self.active_match['maps_completed'] += 1

        # Post update to Discord
        await self._post_score_update(map_data, score_a, score_b)

    async def _post_score_update(self, map_data: Dict, score_a: int, score_b: int):
        """
        Post live score update to Discord.
        """
        channel = self.bot.get_channel(self.config.production_channel_id)
        if not channel:
            return

        match = self.active_match

        # Build simple message
        message = (
            f"📊 **SCORE UPDATE** - Map {match['maps_completed']}\n"
            f"🗺️ {map_data['map_name']}\n"
            f"🔴 Team A: **{match['score_a']}** - **{match['score_b']}** Team B 🔵\n"
            f"Prediction tracking: Team A {int(match['prediction']['team_a_win_probability']*100)}%"
        )

        await channel.send(message)
        logger.info(f"✅ Score update posted: {match['score_a']}-{match['score_b']}")

    async def end_match(self):
        """
        Called when match ends - post final analysis.
        """
        if not self.active_match:
            return

        match = self.active_match

        # Determine winner
        if match['score_a'] > match['score_b']:
            winner = 'team_a'
            winner_text = "Team A"
        elif match['score_b'] > match['score_a']:
            winner = 'team_b'
            winner_text = "Team B"
        else:
            winner = 'tie'
            winner_text = "TIE"

        # Compare to prediction
        predicted_winner = 'team_a' if match['prediction']['team_a_win_probability'] > 0.5 else 'team_b'
        prediction_correct = (winner == predicted_winner) or (winner == 'tie' and abs(match['prediction']['team_a_win_probability'] - 0.5) < 0.1)

        # Build final embed
        await self._post_final_analysis(match, winner, winner_text, prediction_correct)

        # Store results in database
        await self._store_match_result(match, winner)

        # Clear active match
        self.active_match = None
        logger.info("✅ Match monitoring ended")

    async def _post_final_analysis(
        self,
        match: Dict,
        winner: str,
        winner_text: str,
        prediction_correct: bool
    ):
        """
        Post final match analysis to Discord.
        """
        channel = self.bot.get_channel(self.config.production_channel_id)
        if not channel:
            return

        embed = discord.Embed(
            title="🏆 MATCH COMPLETE - Final Analysis",
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow()
        )

        # Final Score
        embed.add_field(
            name="📊 Final Score",
            value=f"🔴 Team A: **{match['score_a']}**\n🔵 Team B: **{match['score_b']}**",
            inline=False
        )

        # Winner
        if winner == 'tie':
            winner_emoji = '🤝'
        else:
            winner_emoji = '🏆'

        embed.add_field(
            name=f"{winner_emoji} Result",
            value=f"**{winner_text} WINS**" if winner != 'tie' else "**PERFECT TIE**",
            inline=False
        )

        # Prediction Accuracy
        pred = match['prediction']
        team_a_prob = int(pred['team_a_win_probability'] * 100)
        team_b_prob = int(pred['team_b_win_probability'] * 100)

        if prediction_correct:
            accuracy_emoji = '✅'
            accuracy_text = "ACCURATE"
        else:
            accuracy_emoji = '❌'
            accuracy_text = "INCORRECT"

        embed.add_field(
            name=f"{accuracy_emoji} Prediction Accuracy",
            value=(
                f"Predicted: Team A {team_a_prob}% | Team B {team_b_prob}%\n"
                f"Result: {accuracy_text}"
            ),
            inline=False
        )

        # Total maps
        embed.add_field(
            name="🗺️ Maps Played",
            value=f"{match['maps_completed']} maps",
            inline=True
        )

        embed.set_footer(text="Historical data updated • Thanks for playing!")

        await channel.send(embed=embed)
        logger.info("✅ Final analysis posted")
```

---

## 📊 Success Metrics & Testing

### Testing Plan

1. **Historical Data Validation**
   - Run predictions on past 20 sessions
   - Compare predictions to actual results
   - Target: >60% prediction accuracy

2. **Confidence Calibration**
   - High confidence predictions should be >75% accurate
   - Medium confidence: 55-75% accurate
   - Low confidence: Expected to be unreliable

3. **Team Detection Accuracy**
   - Test on various session formats (3v3, 4v4, 5v5, 6v6)
   - Handle edge cases (uneven teams, late joiners)
   - Substitution detection accuracy

### Performance Targets

- **Prediction Generation:** <2 seconds
- **Database Queries:** <500ms per query
- **Discord Embed Posting:** <1 second
- **Live Score Check Interval:** 30 seconds

---

## 🚀 Deployment Strategy

### Phase Rollout

1. **Phase 1-2:** Development & Testing (offline)
   - Build on test bot instance
   - Test with historical data

2. **Phase 3-4:** Beta Testing (production, manual trigger)
   - Add hidden admin command: `!predict_test`
   - Monitor accuracy for 2 weeks

3. **Phase 5:** Full Automation
   - Enable automatic predictions
   - Monitor for 1 week with alerts
   - Gather user feedback

4. **Phase 6:** Refinement
   - Tune weights based on accuracy
   - Add more sophisticated metrics
   - Improve insights generation

---

## 📝 Documentation Requirements

1. **Architecture Diagram** - Visual system flow
2. **Database Schema Documentation** - All new tables
3. **API Reference** - All public methods
4. **Troubleshooting Guide** - Common issues
5. **Metrics Dashboard** - Prediction accuracy tracking

---

## ⚠️ Known Challenges & Risks

### Technical Challenges

1. **Discord User → Player GUID Mapping**
   - Requires `linked_accounts` table
   - Manual linking process needed
   - Fallback logic for unlinked users

2. **Real-Time Score Detection**
   - Database polling every 30s
   - Race conditions possible
   - Network latency issues

3. **Prediction Accuracy**
   - Limited historical data initially
   - Team comp changes over time
   - Player skill variance

### Mitigation Strategies

1. **Gradual Confidence Building**
   - Start with "experimental" label
   - Show confidence levels prominently
   - Collect feedback

2. **Fallback Mechanisms**
   - If prediction fails, skip silently
   - If score tracking breaks, continue session
   - Never crash bot due to prediction errors

3. **User Communication**
   - "This is an experimental feature"
   - "Predictions improve with more data"
   - "Report issues to help us improve"

---

## 🎯 Future Enhancements (Beyond Initial Release)

1. **Machine Learning Integration**
   - Train on more factors
   - Player role analysis
   - Map-specific strategies

2. **Live Betting Odds**
   - Dynamic odds during match
   - "Team A now 80% after crushing first map"

3. **Player Impact Scores**
   - Quantify individual contribution
   - "Player X adds +15% win probability"

4. **Custom Team Names & Logos**
   - User-submitted team identities
   - Discord role integration

5. **Tournament Mode**
   - Bracket predictions
   - Cumulative accuracy tracking
   - Leaderboard for prediction accuracy

---

## ✅ Definition of Done

This system is complete when:

- [x] Teams auto-detected from voice channel splits
- [x] Prediction auto-posted when teams form
- [x] Live scores update after each map
- [x] Final analysis compares prediction to result
- [x] Historical database updated automatically
- [x] Prediction accuracy >60% on test data
- [x] Zero manual commands required
- [x] Comprehensive documentation written
- [x] User feedback gathered and positive

---

## 📅 Estimated Timeline

**Conservative Estimate:** 80-120 hours total development

| Phase | Hours | Weeks (10h/week) |
|-------|-------|------------------|
| Phase 1: Voice Team Detection | 15-20 | 2 weeks |
| Phase 2: Refactor Advanced Detection | 20-30 | 3 weeks |
| Phase 3: Performance Analysis | 15-20 | 2 weeks |
| Phase 4: Prediction Engine | 25-35 | 3 weeks |
| Phase 5: Live Score Tracking | 10-15 | 2 weeks |
| **Testing & Polish** | 10-15 | 2 weeks |
| **TOTAL** | **95-135** | **14 weeks** |

**Aggressive Estimate (20h/week):** 7-8 weeks
**Realistic Estimate (10h/week):** 14-16 weeks

---

## 🎬 Next Steps

When you're ready to start:

1. **Read this document thoroughly**
2. **Create feature branch:** `git checkout -b feature/competitive-analytics`
3. **Start with Phase 1:** Voice team detection (lowest risk)
4. **Test incrementally:** Each phase must work before moving on
5. **Document as you go:** Update this doc with actual findings

---

**Remember:** This is NOT dead code - it's the foundation of an amazing competitive analytics system. Take your time, build it right, and it will transform your bot into something truly special.

Good luck! 🚀
