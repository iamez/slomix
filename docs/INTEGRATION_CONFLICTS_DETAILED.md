# Integration Conflicts - Detailed Analysis

**Competitive Analytics System Integration**
*Generated: 2025-11-28*

---

## Executive Summary

After examining the unfinished competitive analytics modules alongside the current production system, I've identified **5 CRITICAL conflicts** that must be resolved before integration. This document provides line-by-line analysis of each conflict with specific remediation strategies.

**Overall Risk Level:** MEDIUM-HIGH
**Primary Blocker:** Database adapter incompatibility across ALL unfinished modules

---

## Conflict Matrix

| # | Conflict | Severity | Files Affected | Estimated Fix Time |
|---|----------|----------|----------------|-------------------|
| 1 | Database Adapter Incompatibility | CRITICAL | 3 files | 8-12 hours |
| 2 | Voice Channel Detection Gap | HIGH | 1 file | 6-8 hours |
| 3 | GUID Mapping Not Utilized | MEDIUM | 1 file | 3-4 hours |
| 4 | TeamManager Duplication Risk | MEDIUM | 2 files | 4-6 hours |
| 5 | Missing Prediction Engine | HIGH | New code | 16-20 hours |

---

## CONFLICT 1: Database Adapter Incompatibility

### Severity: CRITICAL 🔴

This is the PRIMARY BLOCKER for integration.

### Problem Description

All unfinished competitive analytics modules use direct `sqlite3.Connection` objects, while the production system has migrated to a `DatabaseAdapter` abstraction that supports both PostgreSQL and SQLite.

### Affected Files

#### 1. `bot/core/advanced_team_detector.py`

```python
# Line 55: Class initialization
def __init__(self, db_path: str = "bot/etlegacy_production.db"):
    self.db_path = db_path

# Line 64: Method signature
def detect_session_teams(
    self,
    db: sqlite3.Connection,  # ❌ HARDCODED sqlite3
    session_date: str,
    use_historical: bool = True
) -> Dict[str, Dict]:

# Line 144: Direct cursor usage
cursor = db.cursor()  # ❌ sqlite3-specific
cursor.execute(query, (f"{session_date}%",))
rows = cursor.fetchall()  # ❌ sqlite3-specific

# Lines 183-235: Historical pattern analysis
# Uses direct sqlite3 cursor operations throughout
```python

**Issue:** The entire class assumes `sqlite3.Connection` and uses cursor-based operations.

#### 2. `bot/core/substitution_detector.py`

```python
# Line 80: Method signature
def analyze_session_roster_changes(
    self,
    db: sqlite3.Connection,  # ❌ HARDCODED sqlite3
    session_date: str
) -> Dict:

# Line 160: Direct cursor usage
cursor = db.cursor()  # ❌ sqlite3-specific

# Line 388-390: Standalone function
def demonstrate_substitution_detection(session_date: str, db_path: str = "bot/etlegacy_production.db"):
    import sqlite3
    db = sqlite3.connect(db_path)  # ❌ Direct connection
```python

**Issue:** All database operations use sqlite3-specific cursor API.

#### 3. `bot/core/team_manager.py` (CURRENTLY IN PRODUCTION!)

```python
# Line 28: Class initialization
def __init__(self, db_path: str = "bot/etlegacy_production.db"):
    self.db_path = db_path  # ❌ Still using direct connection

# Line 33: Method signature
def detect_session_teams(
    self,
    db: sqlite3.Connection,  # ❌ HARDCODED sqlite3
    session_date: str
) -> Dict[str, Dict]:

# Line 58: Direct cursor usage
cursor = db.cursor()  # ❌ sqlite3-specific
cursor.execute(query, (f"{session_date}%",))
```python

**Issue:** Even the CURRENT production code uses sqlite3 directly. This is a legacy issue that affects both old and new systems.

### Current Production System

For comparison, here's how the production bot uses DatabaseAdapter:

**bot/services/voice_session_service.py** (Lines 362-370):

```python
recent_round = await self.db_adapter.fetch_one(
    """
    SELECT id FROM rounds
    WHERE (round_date > ? OR (round_date = ? AND round_time >= ?))
    ORDER BY round_date DESC, round_time DESC
    LIMIT 1
    """,
    (cutoff_date, cutoff_date, cutoff_time_str)
)
```python

**Key Difference:**

- ✅ Uses `db_adapter.fetch_one()` (async, adapter-based)
- ❌ NOT `cursor.execute()` / `cursor.fetchone()` (sync, sqlite3-specific)

### Root Cause Analysis

The unfinished modules were developed during Week 11-12 (November 2, 2025 commit: "Team Detection System - Complete Implementation") **BEFORE** the DatabaseAdapter refactoring was completed in Week 13-14.

### Impact Assessment

**If we try to integrate as-is:**

1. ❌ Code won't run on PostgreSQL (production database)
2. ❌ Type errors at runtime (passing sqlite3.Connection where DatabaseAdapter expected)
3. ❌ Can't be called from async contexts (team_manager uses sync sqlite3)
4. ❌ No connection pooling (performance degradation)

**Production Evidence:**

- Current bot uses PostgreSQL: `database_type = "postgresql"` (bot/config.py)
- Current connection string: `postgresql://etlegacy_user:etlegacy_secure_2025@localhost/etlegacy`
- NONE of the unfinished modules would work with this setup

### Solution Strategy

#### Option A: Refactor All Modules to DatabaseAdapter (RECOMMENDED)

**Time:** 8-12 hours
**Risk:** LOW (controlled refactor)

**Changes Required:**

1. **Class Constructor Changes**

```python
# OLD (sqlite3-based)
class AdvancedTeamDetector:
    def __init__(self, db_path: str = "bot/etlegacy_production.db"):
        self.db_path = db_path

# NEW (adapter-based)
class AdvancedTeamDetector:
    def __init__(self, db_adapter):
        self.db_adapter = db_adapter
        self.config = db_adapter.config  # Access to bot config
```text

1. **Method Signature Changes**

```python
# OLD
def detect_session_teams(
    self,
    db: sqlite3.Connection,
    session_date: str
) -> Dict[str, Dict]:

# NEW (make async)
async def detect_session_teams(
    self,
    session_date: str
) -> Dict[str, Dict]:
    # Use self.db_adapter instead of db parameter
```text

1. **Query Execution Changes**

```python
# OLD (sqlite3 cursor)
cursor = db.cursor()
cursor.execute(query, (f"{session_date}%",))
rows = cursor.fetchall()

# NEW (DatabaseAdapter - handles both PostgreSQL and SQLite)
rows = await self.db_adapter.fetch_all(
    query,
    (f"{session_date}%",)
)
```text

1. **Parameterized Query Syntax**

```python
# OLD (SQLite ? placeholders)
query = "SELECT * FROM rounds WHERE round_date = ?"

# NEW (adapter handles both ? and $1 automatically)
# PostgreSQL uses $1, $2, $3...
# SQLite uses ?, ?, ?...
# DatabaseAdapter converts internally based on config.database_type
query = "SELECT * FROM rounds WHERE round_date = ?"
# OR
query = "SELECT * FROM rounds WHERE round_date = $1"
# Adapter handles conversion!
```python

**File-by-File Refactor Plan:**

| File | Methods to Refactor | Estimated Time |
|------|---------------------|----------------|
| advanced_team_detector.py | 7 methods (detect_session_teams, _get_session_player_data, _analyze_historical_patterns,_analyze_multi_round_consensus,_analyze_cooccurrence,_combine_strategies,_cluster_into_teams) | 4 hours |
| substitution_detector.py | 5 methods (analyze_session_roster_changes,_get_player_activity, _get_round_rosters,_detect_roster_changes, adjust_team_detection_for_substitutions) | 3 hours |
| team_manager.py | 4 methods (detect_session_teams, store_session_teams, get_session_teams, detect_lineup_changes) | 2 hours |
| **Testing & Integration** | | 3 hours |
| **TOTAL** | | **12 hours** |

#### Option B: Create Adapter Wrapper (NOT RECOMMENDED)

**Time:** 4 hours
**Risk:** HIGH (abstraction leak, maintenance burden)

Create a `LegacyDatabaseBridge` that wraps DatabaseAdapter to look like sqlite3.Connection. This is a **band-aid solution** that will cause technical debt.

### Recommendation

**PROCEED WITH OPTION A:** Full refactor to DatabaseAdapter.

**Reasoning:**

1. team_manager.py is ALSO using sqlite3 (it's affected too!)
2. One-time fix resolves the issue permanently
3. Enables async/await throughout (better performance)
4. Future-proof for other database backends

**Rollout Strategy:**

1. ✅ Refactor team_manager.py FIRST (it's in production, low risk, high value)
2. ✅ Test team_manager.py with existing !team commands
3. ✅ Refactor advanced_team_detector.py (uses same patterns)
4. ✅ Refactor substitution_detector.py
5. ✅ Integration testing

---

## CONFLICT 2: Voice Channel Detection Gap

### Severity: HIGH 🟡

### Problem Description

The current `voice_session_service.py` only counts TOTAL players across all voice channels. It **CANNOT** detect team splits (e.g., 6 players → 3 in Channel A + 3 in Channel B).

This is the trigger mechanism for the competitive analytics system.

### Current Implementation

**bot/services/voice_session_service.py (Lines 74-82):**

```python
# Count players in gaming voice channels
total_players = 0
current_participants = set()

for channel_id in self.config.gaming_voice_channels:
    channel = self.bot.get_channel(channel_id)
    if channel and isinstance(channel, discord.VoiceChannel):
        total_players += len(channel.members)  # ❌ Just counting total!
        current_participants.update([m.id for m in channel.members])

logger.debug(f"🎙️ Voice update: {total_players} players in gaming channels")
```text

**What This Does:**

- ✅ Counts total players across all channels
- ✅ Tracks Discord user IDs
- ❌ Does NOT track which channel each player is in
- ❌ Does NOT detect team formation (channel split events)

### Required Functionality

To trigger competitive analytics, we need to detect:

```text

BEFORE (Group Channel):
Channel A: [Player1, Player2, Player3, Player4, Player5, Player6]
Channel B: []

AFTER (Teams Formed):
Channel A: [Player1, Player2, Player3]  ← Team 1
Channel B: [Player4, Player5, Player6]  ← Team 2

🎯 TRIGGER: Team split detected! → Generate prediction

```sql

### User's Vision (from conversation)

> "we know when the teams are made, when the group of players in one channel, is split into even numbers in two channels... if they go from 6 players in one channel to 3 players in one and 3 in other we know they're playing 3v3 against each other.. if its 4 in one 4 in other and 8 started in group channel we know its 4v4.."

### Solution Design

**Enhanced Voice State Tracking:**

```python
# NEW data structure needed
self.channel_distribution = {
    channel_id_1: {user_id_1, user_id_2, user_id_3},  # Team 1
    channel_id_2: {user_id_4, user_id_5, user_id_6}   # Team 2
}
self.previous_distribution = {}  # Track changes

async def handle_voice_state_change(self, member, before, after):
    # ... existing code ...

    # NEW: Build channel distribution
    channel_distribution = {}
    for channel_id in self.config.gaming_voice_channels:
        channel = self.bot.get_channel(channel_id)
        if channel and isinstance(channel, discord.VoiceChannel):
            channel_distribution[channel_id] = set([m.id for m in channel.members])

    # NEW: Detect team split
    split_event = self._detect_team_split(
        previous=self.previous_distribution,
        current=channel_distribution
    )

    if split_event:
        await self._trigger_match_prediction(split_event)

    self.previous_distribution = channel_distribution

def _detect_team_split(self, previous: Dict, current: Dict) -> Optional[Dict]:
    """
    Detect when players split from one channel into multiple.

    Example scenario:
    Previous: Channel A = 8 players, Channel B = 0
    Current:  Channel A = 4 players, Channel B = 4 players

    Returns:
        {
            'team1_channel': channel_id_1,
            'team1_members': {user_id_1, user_id_2, user_id_3, user_id_4},
            'team2_channel': channel_id_2,
            'team2_members': {user_id_5, user_id_6, user_id_7, user_id_8},
            'format': '4v4',
            'timestamp': datetime.now()
        }
    """
    # Find channels with balanced player counts
    populated_channels = [
        (ch_id, members)
        for ch_id, members in current.items()
        if len(members) >= 2
    ]

    if len(populated_channels) != 2:
        return None  # Not a two-team scenario

    ch1_id, team1 = populated_channels[0]
    ch2_id, team2 = populated_channels[1]

    # Check if teams are roughly balanced (within 1 player difference)
    if abs(len(team1) - len(team2)) > 1:
        return None  # Unbalanced teams

    # Check if this is a NEW split (not just players returning)
    prev_total = sum(len(members) for members in previous.values())
    curr_total = len(team1) + len(team2)

    # Must be a split event (not players leaving/joining)
    if curr_total < prev_total - 1:
        return None  # Players left, not a split

    return {
        'team1_channel': ch1_id,
        'team1_members': team1,
        'team2_channel': ch2_id,
        'team2_members': team2,
        'format': f"{len(team1)}v{len(team2)}",
        'timestamp': discord.utils.utcnow()
    }
```python

### Integration Points

Once team split is detected:

1. Map Discord IDs → Player GUIDs (using player_links table)
2. Query historical performance data
3. Generate match prediction
4. Post prediction to Discord channel

### Implementation Estimate

- **Code Changes:** 120-150 lines
- **Testing:** Need to test with live voice channel events
- **Time:** 6-8 hours (including edge case handling)

### Edge Cases to Handle

1. **Unbalanced splits:** 5v3 (one team short a player)
2. **Multiple channels:** More than 2 active channels
3. **Partial teams:** Not all Discord users have linked GUIDs
4. **Quick rejoins:** Player leaves voice for 5 seconds then returns
5. **Bot restart:** Resume monitoring without false triggers

---

## CONFLICT 3: GUID Mapping Not Utilized

### Severity: MEDIUM 🟡

### Problem Description

The infrastructure for Discord ID → Player GUID mapping **ALREADY EXISTS** in the `player_links` table, but `voice_session_service.py` doesn't use it.

### Database Evidence

**player_links table schema:**

```sql
CREATE TABLE player_links (
    id SERIAL PRIMARY KEY,
    player_guid TEXT UNIQUE NOT NULL,
    discord_id BIGINT UNIQUE NOT NULL,
    discord_username TEXT,
    player_name TEXT,
    linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    display_name TEXT,
    display_name_source TEXT DEFAULT 'auto',
    display_name_updated_at TIMESTAMP
);
```text

**Sample Data:**

```bash
$ psql -c "SELECT discord_id, player_guid, player_name FROM player_links LIMIT 3;"
  discord_id   |         player_guid          | player_name
---------------+------------------------------+-------------
 123456789012  | 550e8400-e29b-41d4-a716-... | SloMix
 234567890123  | 660e8400-e29b-41d4-a716-... | AnotherPlayer
 345678901234  | 770e8400-e29b-41d4-a716-... | ThirdPlayer
```python

### Current Gap

**voice_session_service.py** tracks:

```python
self.session_participants: Set[int] = set()  # Discord user IDs only
```text

But to generate predictions, we need:

```python
# Map Discord IDs → Player GUIDs → Historical stats
discord_id_123456789012 → "550e8400-e29b..." → Query player_comprehensive_stats
```text

### Solution Implementation

**Add GUID resolution to voice session service:**

```python
class VoiceSessionService:
    def __init__(self, bot, config, db_adapter):
        self.bot = bot
        self.config = config
        self.db_adapter = db_adapter

        # NEW: GUID mapping cache
        self.discord_to_guid_cache = {}  # {discord_id: player_guid}

    async def resolve_discord_ids_to_guids(
        self,
        discord_ids: Set[int]
    ) -> Dict[int, str]:
        """
        Map Discord user IDs to player GUIDs using player_links table.

        Args:
            discord_ids: Set of Discord user IDs from voice channels

        Returns:
            {discord_id: player_guid} for users with linked accounts
        """
        # Check cache first
        cached_guids = {}
        uncached_ids = []

        for discord_id in discord_ids:
            if discord_id in self.discord_to_guid_cache:
                cached_guids[discord_id] = self.discord_to_guid_cache[discord_id]
            else:
                uncached_ids.append(discord_id)

        # Query database for uncached IDs
        if uncached_ids:
            query = """
                SELECT discord_id, player_guid
                FROM player_links
                WHERE discord_id = ANY($1)
            """
            rows = await self.db_adapter.fetch_all(query, (uncached_ids,))

            for discord_id, player_guid in rows:
                self.discord_to_guid_cache[discord_id] = player_guid
                cached_guids[discord_id] = player_guid

        return cached_guids

    async def _trigger_match_prediction(self, split_event: Dict):
        """
        Trigger match prediction when team split detected.

        Args:
            split_event: Output from _detect_team_split()
        """
        team1_discord_ids = split_event['team1_members']
        team2_discord_ids = split_event['team2_members']

        # Resolve to GUIDs
        all_discord_ids = team1_discord_ids | team2_discord_ids
        guid_mapping = await self.resolve_discord_ids_to_guids(all_discord_ids)

        # Extract team GUIDs
        team1_guids = [
            guid_mapping[did]
            for did in team1_discord_ids
            if did in guid_mapping
        ]
        team2_guids = [
            guid_mapping[did]
            for did in team2_discord_ids
            if did in guid_mapping
        ]

        # Check if we have enough linked players
        link_rate = len(guid_mapping) / len(all_discord_ids)
        if link_rate < 0.8:  # Require 80% of players linked
            logger.warning(
                f"⚠️ Team split detected but only {link_rate:.0%} of players "
                f"have linked accounts. Skipping prediction."
            )
            return

        # Generate prediction
        from bot.services.prediction_engine import PredictionEngine
        prediction_engine = PredictionEngine(self.db_adapter)

        prediction = await prediction_engine.predict_match(
            team1_guids=team1_guids,
            team2_guids=team2_guids
        )

        # Post to Discord
        await self._post_prediction_embed(prediction)
```python

### Implementation Estimate

- **Code Changes:** 80-100 lines
- **Testing:** Need test data in player_links table
- **Time:** 3-4 hours

---

## CONFLICT 4: TeamManager Duplication Risk

### Severity: MEDIUM 🟡

### Problem Description

We have TWO team detection implementations:

1. **bot/core/team_manager.py** (ACTIVE, 460 lines)
   - Simple Round 1 seeding + late joiner voting
   - Used by `team_cog.py` (!team commands)
   - Works but limited

2. **bot/core/advanced_team_detector.py** (UNFINISHED, 618 lines)
   - Sophisticated multi-strategy detection
   - Historical patterns + multi-round consensus + co-occurrence
   - Not integrated anywhere

### Risk Analysis

**If we integrate advanced_team_detector.py WITHOUT a plan:**

- ❌ Code duplication (two classes doing similar things)
- ❌ Maintenance burden (which one to update?)
- ❌ Confusion (which one should be used where?)
- ❌ Potential data inconsistency (different algorithms, different results)

### Current TeamManager Usage

**bot/cogs/team_cog.py imports and uses TeamManager:**

```python
from bot.core.team_manager import TeamManager

class TeamCog(commands.Cog):
    async def teams(self, ctx, session_date: str = None):
        manager = TeamManager(self.config.db_path)
        # Uses detect_session_teams(), store_session_teams(), etc.
```yaml

### Comparison Matrix

| Feature | TeamManager (Current) | AdvancedTeamDetector (Unfinished) |
|---------|----------------------|-----------------------------------|
| **Algorithm** | Round 1 seed + voting | Multi-strategy (historical/consensus/cooccurrence) |
| **Confidence Scoring** | ❌ No | ✅ Yes (per-player confidence) |
| **Historical Learning** | ❌ No | ✅ Yes (last 10 sessions) |
| **Late Joiner Handling** | ✅ Yes (voting) | ✅ Yes (multiple strategies) |
| **Detection Quality** | Basic | Advanced |
| **Database Adapter** | ❌ sqlite3 only | ❌ sqlite3 only (needs refactor) |
| **Integration Status** | ✅ Production | ❌ Not integrated |
| **Lines of Code** | 460 | 618 |

### Solution Options

#### Option A: Coexistence Strategy (RECOMMENDED)

**Keep both, use each for different purposes**

```text

TeamManager (Simple)
├── Used by: !team commands (manual team management)
├── Purpose: Quick team detection for Discord commands
└── Algorithm: Fast Round 1 seeding

AdvancedTeamDetector (Sophisticated)
├── Used by: Automated competitive analytics
├── Purpose: High-confidence team detection for predictions
└── Algorithm: Multi-strategy with confidence scoring

```text

**Integration:**

```python
# In prediction engine
if prediction_needed:
    # Use advanced detector for high-confidence results
    detector = AdvancedTeamDetector(db_adapter)
    teams = await detector.detect_session_teams(session_date)

    if teams['metadata']['avg_confidence'] < 0.7:
        logger.warning("Low confidence team detection, skipping prediction")
        return None

# In team commands
if user_command:
    # Use simple TeamManager for quick results
    manager = TeamManager(db_adapter)
    teams = await manager.detect_session_teams(session_date)
```python

**Pros:**

- ✅ No breaking changes to existing !team commands
- ✅ Advanced detection used only where needed
- ✅ Gradual rollout possible

**Cons:**

- ⚠️ Two implementations to maintain
- ⚠️ Must keep APIs compatible

#### Option B: Migration Strategy

**Replace TeamManager with AdvancedTeamDetector**

**Pros:**

- ✅ Single implementation
- ✅ Best algorithm everywhere

**Cons:**

- ❌ Riskier (breaking changes)
- ❌ More testing needed
- ❌ Performance impact on simple commands

### Recommendation

**PROCEED WITH OPTION A:** Coexistence strategy.

**Reasoning:**

1. Existing !team commands work fine with simple detector
2. Competitive analytics needs advanced detector
3. Low risk (no changes to production code initially)
4. Can migrate to advanced later if desired

**Action Items:**

1. Refactor both to use DatabaseAdapter
2. Keep TeamManager for manual commands
3. Use AdvancedTeamDetector for automated predictions
4. Monitor quality difference in production

---

## CONFLICT 5: Missing Prediction Engine

### Severity: HIGH 🟡

### Problem Description

The unfinished modules provide **team detection** infrastructure, but there's NO **prediction engine**. To implement the user's vision, we need to build:

1. Match outcome prediction algorithm
2. Historical matchup tracking
3. Win/loss record by lineup
4. Map-specific performance analysis
5. Weighted scoring system

### What Exists vs. What's Needed

**Exists:**

- ✅ Team detection (advanced_team_detector.py)
- ✅ Substitution tracking (substitution_detector.py)
- ✅ Match pairing logic (match_tracker.py)
- ✅ Voice session detection (voice_session_service.py)

**Missing:**

- ❌ Prediction engine (calculate win probability)
- ❌ Head-to-head tracking (Team A vs Team B history)
- ❌ Lineup performance database (win/loss by roster)
- ❌ Map performance analysis (team stats per map)
- ❌ Weighted factor system (H2H 40%, Form 25%, Maps 20%, Subs 15%)

### User's Vision (from conversation)

> "we want it automated.. as soon as the teams are in their channels it means games started and we can start our prediction because we know who plays together... and we know one more important thing. we know exactly who they play against... we can predict... its a teamgame... so being the most aggressive and hardcore frager with top dpm and top dmg is not necessarily the biggest skillset needed to win competitive games of stopwatch in et:legacy, tailor predictions accordingly"

**Key Requirements:**

- ✅ Team-based predictions (not individual player stats)
- ✅ Automated (triggered by voice channel split)
- ✅ Matchup-aware (Team A vs Team B specifically)
- ✅ Teamwork focus (objective completion, not K/D)

### Required New Components

#### 1. Database Tables

**lineup_performance** - Track team win/loss records

```sql
CREATE TABLE lineup_performance (
    id SERIAL PRIMARY KEY,
    lineup_guids JSONB NOT NULL,  -- Sorted list of player GUIDs
    matches_played INT DEFAULT 0,
    matches_won INT DEFAULT 0,
    matches_lost INT DEFAULT 0,
    matches_tied INT DEFAULT 0,
    win_rate DECIMAL(5,2),
    last_played TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Index for fast lineup lookup
    CONSTRAINT lineup_performance_guids_unique UNIQUE (lineup_guids)
);

CREATE INDEX idx_lineup_performance_guids ON lineup_performance
USING gin (lineup_guids jsonb_path_ops);
```text

**head_to_head_matchups** - Track specific Team A vs Team B history

```sql
CREATE TABLE head_to_head_matchups (
    id SERIAL PRIMARY KEY,
    team_a_guids JSONB NOT NULL,
    team_b_guids JSONB NOT NULL,
    match_date DATE NOT NULL,
    team_a_score INT,
    team_b_score INT,
    winner TEXT,  -- 'team_a', 'team_b', 'tie'
    match_id TEXT,
    session_start_date TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_h2h_team_a ON head_to_head_matchups
USING gin (team_a_guids jsonb_path_ops);
CREATE INDEX idx_h2h_team_b ON head_to_head_matchups
USING gin (team_b_guids jsonb_path_ops);
```text

**map_performance** - Map-specific team stats

```sql
CREATE TABLE map_performance (
    id SERIAL PRIMARY KEY,
    lineup_guids JSONB NOT NULL,
    map_name TEXT NOT NULL,
    matches_played INT DEFAULT 0,
    matches_won INT DEFAULT 0,
    win_rate DECIMAL(5,2),
    avg_completion_time DECIMAL(10,2),  -- Seconds

    UNIQUE (lineup_guids, map_name)
);
```text

**match_predictions** - Store predictions for accuracy tracking

```sql
CREATE TABLE match_predictions (
    id SERIAL PRIMARY KEY,
    prediction_time TIMESTAMP NOT NULL,
    team_a_guids JSONB NOT NULL,
    team_b_guids JSONB NOT NULL,
    predicted_winner TEXT,  -- 'team_a', 'team_b'
    confidence DECIMAL(5,2),  -- 0.00 to 1.00
    factors JSONB,  -- Breakdown of prediction factors
    actual_winner TEXT,  -- Filled in after match
    prediction_correct BOOLEAN,  -- Filled in after match
    session_start_date TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```python

#### 2. PredictionEngine Service

**bot/services/prediction_engine.py** (NEW FILE)

```python
"""
Prediction Engine - Match Outcome Prediction

Weighted factors:
- 40% Head-to-head history
- 25% Recent form (last 5 sessions)
- 20% Map-specific performance
- 15% Roster changes (substitutions impact)
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger('PredictionEngine')


class PredictionEngine:
    """
    Predicts match outcomes based on historical data and weighted factors.

    Focus: TEAM performance, not individual stats.
    Metrics: Objective completion, defensive holds, lineup synergy.
    """

    def __init__(self, db_adapter):
        self.db_adapter = db_adapter

        # Weights (must sum to 1.0)
        self.weight_h2h = 0.40
        self.weight_form = 0.25
        self.weight_maps = 0.20
        self.weight_subs = 0.15

        # Thresholds
        self.min_matches_for_prediction = 3  # Need at least 3 historical matches
        self.min_confidence_to_post = 0.60  # Only post if >60% confidence

    async def predict_match(
        self,
        team1_guids: List[str],
        team2_guids: List[str],
        current_map: Optional[str] = None
    ) -> Dict:
        """
        Generate match prediction.

        Returns:
            {
                'predicted_winner': 'team_a' or 'team_b',
                'confidence': 0.72,
                'win_probability_a': 0.65,
                'win_probability_b': 0.35,
                'factors': {
                    'h2h': {'score': 0.80, 'weight': 0.40, 'details': '...'},
                    'form': {'score': 0.60, 'weight': 0.25, 'details': '...'},
                    'maps': {'score': 0.70, 'weight': 0.20, 'details': '...'},
                    'subs': {'score': 0.50, 'weight': 0.15, 'details': '...'}
                },
                'metadata': {
                    'team_a_guids': [...],
                    'team_b_guids': [...],
                    'matches_analyzed': 12,
                    'prediction_quality': 'high'
                }
            }
        """
        # Normalize team rosters (sort for consistency)
        team1_guids = sorted(team1_guids)
        team2_guids = sorted(team2_guids)

        # Calculate factor scores
        h2h_score = await self._analyze_head_to_head(team1_guids, team2_guids)
        form_score = await self._analyze_recent_form(team1_guids, team2_guids)
        maps_score = await self._analyze_map_performance(team1_guids, team2_guids, current_map)
        subs_score = await self._analyze_substitution_impact(team1_guids, team2_guids)

        # Weighted combination
        # Score > 0.5 = Team A favored, < 0.5 = Team B favored
        combined_score = (
            h2h_score['score'] * self.weight_h2h +
            form_score['score'] * self.weight_form +
            maps_score['score'] * self.weight_maps +
            subs_score['score'] * self.weight_subs
        )

        # Determine winner and confidence
        predicted_winner = 'team_a' if combined_score >= 0.5 else 'team_b'
        confidence = abs(combined_score - 0.5) * 2  # Convert to 0-1 scale

        win_prob_a = combined_score
        win_prob_b = 1.0 - combined_score

        # Determine prediction quality
        if confidence >= 0.75:
            quality = 'high'
        elif confidence >= 0.60:
            quality = 'medium'
        else:
            quality = 'low'

        return {
            'predicted_winner': predicted_winner,
            'confidence': confidence,
            'win_probability_a': win_prob_a,
            'win_probability_b': win_prob_b,
            'factors': {
                'h2h': {**h2h_score, 'weight': self.weight_h2h},
                'form': {**form_score, 'weight': self.weight_form},
                'maps': {**maps_score, 'weight': self.weight_maps},
                'subs': {**subs_score, 'weight': self.weight_subs}
            },
            'metadata': {
                'team_a_guids': team1_guids,
                'team_b_guids': team2_guids,
                'prediction_quality': quality,
                'timestamp': datetime.now().isoformat()
            }
        }

    async def _analyze_head_to_head(
        self,
        team1_guids: List[str],
        team2_guids: List[str]
    ) -> Dict:
        """
        Analyze head-to-head matchup history.

        Returns score: 1.0 = Team A always wins, 0.0 = Team B always wins, 0.5 = even
        """
        query = """
            SELECT winner, COUNT(*) as count
            FROM head_to_head_matchups
            WHERE team_a_guids = $1::jsonb AND team_b_guids = $2::jsonb
               OR team_a_guids = $2::jsonb AND team_b_guids = $1::jsonb
            GROUP BY winner
        """

        rows = await self.db_adapter.fetch_all(
            query,
            (json.dumps(team1_guids), json.dumps(team2_guids))
        )

        if not rows:
            return {
                'score': 0.5,  # No history = even odds
                'details': 'No head-to-head history',
                'matches': 0
            }

        wins_a = sum(count for winner, count in rows if winner == 'team_a')
        wins_b = sum(count for winner, count in rows if winner == 'team_b')
        total = wins_a + wins_b

        score = wins_a / total if total > 0 else 0.5

        return {
            'score': score,
            'details': f"{wins_a}-{wins_b} H2H record",
            'matches': total
        }

    async def _analyze_recent_form(
        self,
        team1_guids: List[str],
        team2_guids: List[str]
    ) -> Dict:
        """
        Analyze recent form (last 5 sessions, regardless of opponent).

        Returns score: >0.5 = Team A has better form, <0.5 = Team B better
        """
        # Query last 5 matches for each team
        # Calculate win rate
        # Compare and return score

        # STUB implementation
        return {
            'score': 0.5,
            'details': 'Form analysis not yet implemented',
            'team_a_form': '0-0',
            'team_b_form': '0-0'
        }

    async def _analyze_map_performance(
        self,
        team1_guids: List[str],
        team2_guids: List[str],
        map_name: Optional[str]
    ) -> Dict:
        """
        Analyze map-specific performance.

        If map_name provided, compare teams' win rates on that specific map.
        Otherwise, use overall map performance.
        """
        if not map_name:
            return {
                'score': 0.5,
                'details': 'Map not known yet',
                'team_a_map_winrate': None,
                'team_b_map_winrate': None
            }

        # Query map_performance table
        # STUB implementation
        return {
            'score': 0.5,
            'details': f'Map performance on {map_name} not yet tracked',
            'team_a_map_winrate': None,
            'team_b_map_winrate': None
        }

    async def _analyze_substitution_impact(
        self,
        team1_guids: List[str],
        team2_guids: List[str]
    ) -> Dict:
        """
        Analyze impact of roster changes.

        If a team has new players (compared to their typical lineup),
        reduce their score slightly.
        """
        # STUB implementation
        return {
            'score': 0.5,
            'details': 'Substitution analysis not yet implemented',
            'team_a_subs': 0,
            'team_b_subs': 0
        }
```

### Implementation Estimate

**PredictionEngine Development:**

- Core prediction logic: 6 hours
- Head-to-head analysis: 3 hours
- Recent form analysis: 3 hours
- Map performance analysis: 2 hours
- Substitution impact: 2 hours
- Database tables: 2 hours
- Testing: 3 hours
- **TOTAL: 21 hours**

This is the LARGEST piece of missing functionality.

---

## Integration Sequence

Based on the conflict analysis, here's the recommended integration sequence:

### Phase 1: Foundation (Weeks 1-2)

**Goal:** Fix database adapter compatibility

1. ✅ **Refactor team_manager.py** to DatabaseAdapter (2 hours)
   - Convert sqlite3 → adapter
   - Test with existing !team commands
   - Deploy to production

2. ✅ **Refactor advanced_team_detector.py** to DatabaseAdapter (4 hours)
   - Convert all queries
   - Make methods async
   - Unit testing

3. ✅ **Refactor substitution_detector.py** to DatabaseAdapter (3 hours)
   - Convert queries
   - Integration testing

4. ✅ **Create database tables** (2 hours)
   - lineup_performance
   - head_to_head_matchups
   - map_performance
   - match_predictions

**Deliverable:** All modules use DatabaseAdapter, tables created, no conflicts

---

### Phase 2: Voice Enhancement (Weeks 3-4)

**Goal:** Detect team splits and trigger events

1. ✅ **Enhance voice_session_service.py** (6 hours)
   - Add channel distribution tracking
   - Implement _detect_team_split()
   - Add GUID resolution
   - Test with live voice events

2. ✅ **Create MatchEvent system** (2 hours)
   - Event bus for team split events
   - Decouple voice service from prediction logic

**Deliverable:** Bot can detect when teams form in voice channels

---

### Phase 3: Prediction Engine (Weeks 5-8)

**Goal:** Build prediction capabilities

1. ✅ **Create PredictionEngine service** (16 hours)
   - Head-to-head analysis
   - Recent form tracking
   - Map performance
   - Substitution impact
   - Weighted scoring

2. ✅ **Discord embed formatting** (2 hours)
   - Prediction announcement embed
   - Factor breakdown display

3. ✅ **Integration testing** (3 hours)
   - End-to-end: voice split → prediction → post
   - Edge cases

**Deliverable:** Functional prediction system

---

### Phase 4: Live Scoring (Weeks 9-10)

**Goal:** Track match results in real-time

1. ✅ **Connect to SSH monitor** (4 hours)
   - Detect when R1/R2 files arrive
   - Parse stopwatch scores
   - Update match_predictions table

2. ✅ **Post live updates** (2 hours)
   - Score updates to Discord
   - Final result announcement

**Deliverable:** Live score tracking

---

### Phase 5: Refinement (Weeks 11-12)

**Goal:** Polish and optimize

1. ✅ **Accuracy tracking** (3 hours)
   - Calculate prediction accuracy over time
   - Tune weights based on results

2. ✅ **Performance optimization** (2 hours)
   - Query optimization
   - Caching strategies

3. ✅ **Documentation** (2 hours)
   - User guide
   - Admin commands

**Deliverable:** Production-ready system

---

## Risk Mitigation

### Testing Strategy

1. **Unit Tests**
   - Each component tested in isolation
   - Mock database responses

2. **Integration Tests**
   - Full flow: voice → detection → prediction → post
   - Test with historical data

3. **Canary Deployment**
   - Deploy to test server first
   - Run alongside production (parallel mode)
   - Compare results before full rollout

### Rollback Plan

1. **Feature Flags**
   - `ENABLE_TEAM_DETECTION = False` (default)
   - `ENABLE_PREDICTIONS = False` (default)
   - Can disable without code changes

2. **Database Isolation**
   - All new tables are ADDITIONS (no schema changes to existing tables)
   - Can drop new tables without affecting existing data

3. **Git Strategy**
   - Feature branch: `feature/competitive-analytics`
   - Merge only after full testing
   - Tag releases for easy rollback

---

## Success Metrics

### Prediction Accuracy

- **Target:** >60% correct predictions after 20 matches
- **Measure:** `match_predictions.prediction_correct` ratio
- **Threshold:** If accuracy <50% after 30 matches, revisit weights

### Performance Impact

- **Target:** Prediction generation <2 seconds
- **Measure:** Log timestamps
- **Threshold:** If >5 seconds, optimize queries

### User Engagement

- **Target:** Predictions posted automatically for >80% of sessions
- **Measure:** Count predictions vs sessions
- **Threshold:** If <60%, investigate why splits not detected

---

## Conclusion

**Overall Assessment:** Integration is FEASIBLE but requires significant work.

**Primary Blocker:** Database adapter incompatibility (12 hours to fix)

**Largest Gap:** Prediction engine (21 hours to build)

**Total Effort:** ~45-55 hours of development + 10-15 hours testing = **55-70 hours**

**Timeline:** 12-14 weeks at 5 hours/week, or 7-9 weeks at 8 hours/week

**Recommendation:** Proceed with phased approach, starting with Phase 1 (database adapter refactoring) as it provides value immediately by modernizing existing code.

---

**Document End**
