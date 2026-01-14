# Fix Team Tracking System

**Purpose:** This document contains everything needed to fix the broken team tracking system in the Discord bot.

**Context:** The team tracking system was built in phases but never fully integrated. Teams are detected but results are never saved, making team chemistry analysis impossible.

---

## Problem Summary

The system can detect which players are on which team, but:
1. **Results never saved** - `session_results` table is never populated
2. **Team records impossible** - Can't query team win/loss history
3. **Integration broken** - Team detector uses SQLite but bot uses PostgreSQL

---

## Files That Need Fixing

| File | Issue | Priority |
|------|-------|----------|
| `bot/core/advanced_team_detector.py` | Async/sync mismatch | P0 |
| `bot/core/team_detector_integration.py` | Uses SQLite, needs PostgreSQL | P0 |
| `bot/services/stopwatch_scoring_service.py` | Needs to save results | P0 |
| `bot/core/team_manager.py` | Empty implementations | P1 |

---

## Fix #1: Async/Sync Mismatch in advanced_team_detector.py

### Location
`bot/core/advanced_team_detector.py`, line 289

### Problem
The method `_analyze_multi_round_consensus` is synchronous but called from async context:

```python
# Line 289 - CURRENT (broken):
def _analyze_multi_round_consensus(
    self,
    session_date: str,
    players_data: Dict[str, Dict]
) -> Dict[str, PlayerTeamScore]:
```

### Fix
Make it async or ensure it's called properly. Since it doesn't do any I/O, it can remain sync but the caller must not await it:

**Option A:** Keep sync, fix caller (simpler):
```python
# In the caller, don't await:
result = self._analyze_multi_round_consensus(session_date, players_data)
# NOT: result = await self._analyze_multi_round_consensus(...)
```

**Option B:** Make async (more consistent):
```python
async def _analyze_multi_round_consensus(
    self,
    session_date: str,
    players_data: Dict[str, Dict]
) -> Dict[str, PlayerTeamScore]:
    # ... same implementation, just add async keyword
```

### Verification
Search for all calls to `_analyze_multi_round_consensus` and ensure they match the method's sync/async nature.

---

## Fix #2: Rewrite team_detector_integration.py for PostgreSQL

### Location
`bot/core/team_detector_integration.py`

### Problem
The entire file uses SQLite patterns:

```python
# Line 25 - CURRENT (broken):
def __init__(self, db_path: str = "bot/etlegacy_production.db"):
    self.db_path = db_path
    self.advanced_detector = AdvancedTeamDetector(db_path)

# Line 31 - CURRENT (broken):
def detect_and_validate(
    self,
    db: sqlite3.Connection,  # <-- SQLite connection!
    session_date: str,
    ...
```

### Fix
Rewrite to use async PostgreSQL adapter:

```python
"""
Team Detector Integration Layer (Async PostgreSQL Version)

Provides a unified interface for team detection that:
1. Uses the advanced detector by default
2. Falls back to simple detection if needed
3. Provides validation and confidence reporting
4. Handles edge cases gracefully
"""

import json
import logging
from typing import Dict, Tuple, Optional

logger = logging.getLogger(__name__)


class TeamDetectorIntegration:
    """
    Unified team detection interface with automatic fallback
    """

    def __init__(self, db_adapter):
        """
        Initialize with async database adapter.

        Args:
            db_adapter: Async DatabaseAdapter instance (PostgreSQL)
        """
        self.db = db_adapter
        # Note: AdvancedTeamDetector also needs to be updated for async

    async def detect_and_validate(
        self,
        session_date: str,
        require_high_confidence: bool = False
    ) -> Tuple[Dict, bool]:
        """
        Detect teams with automatic validation.

        Args:
            session_date: Session date (YYYY-MM-DD)
            require_high_confidence: If True, reject low-confidence detections

        Returns:
            (teams_dict, is_reliable)
        """
        try:
            # Get player data for the session
            players_data = await self._get_session_players(session_date)

            if not players_data or len(players_data) < 4:
                logger.warning(f"Not enough players for {session_date}")
                return {}, False

            # Detect teams using round-by-round analysis
            teams = await self._detect_teams_from_rounds(session_date, players_data)

            if not teams or 'Team A' not in teams or 'Team B' not in teams:
                logger.warning(f"Team detection failed for {session_date}")
                return {}, False

            # Validate team sizes
            team_a_size = len(teams['Team A']['guids'])
            team_b_size = len(teams['Team B']['guids'])

            if team_a_size == 0 or team_b_size == 0:
                logger.error("One team has no players!")
                return {}, False

            # Check team balance
            size_diff = abs(team_a_size - team_b_size)
            is_balanced = size_diff <= 1

            confidence = teams.get('metadata', {}).get('avg_confidence', 0.7)
            is_reliable = is_balanced and confidence >= 0.7

            if require_high_confidence and confidence < 0.8:
                logger.info(f"Low confidence {confidence:.2f} - rejecting")
                return {}, False

            return teams, is_reliable

        except Exception as e:
            logger.error(f"Team detection error: {e}", exc_info=True)
            return {}, False

    async def _get_session_players(self, session_date: str) -> Dict:
        """Get all players and their round data for a session."""
        query = """
            SELECT player_guid, player_name, team, round_number
            FROM player_comprehensive_stats
            WHERE SUBSTRING(round_date, 1, 10) = $1
            ORDER BY round_number, player_guid
        """
        rows = await self.db.fetch_all(query, (session_date,))

        players = {}
        for guid, name, team, round_num in rows:
            if guid not in players:
                players[guid] = {
                    'name': name,
                    'rounds': []
                }
            players[guid]['rounds'].append({
                'round': round_num,
                'game_team': team
            })

        return players

    async def _detect_teams_from_rounds(
        self,
        session_date: str,
        players_data: Dict
    ) -> Dict:
        """
        Detect persistent teams from round data.

        Strategy: Players consistently on same game-team across rounds
        are on the same persistent team.
        """
        from collections import defaultdict
        from itertools import combinations

        # Count how often each pair of players are on same/different game teams
        same_side_count = defaultdict(int)
        diff_side_count = defaultdict(int)

        guids = list(players_data.keys())

        # Analyze each round
        for round_num in range(1, 10):
            round_teams = {}
            for guid, data in players_data.items():
                for r in data['rounds']:
                    if r['round'] == round_num:
                        round_teams[guid] = r['game_team']

            if len(round_teams) < 4:
                continue

            # Compare all pairs in this round
            for g1, g2 in combinations(round_teams.keys(), 2):
                pair = tuple(sorted([g1, g2]))
                if round_teams[g1] == round_teams[g2]:
                    same_side_count[pair] += 1
                else:
                    diff_side_count[pair] += 1

        # Cluster players into two teams
        # Start with first two players who are consistently on different sides
        team_a_guids = set()
        team_b_guids = set()

        # Find anchor pair (most consistently on different sides)
        best_pair = None
        best_diff = 0
        for pair, count in diff_side_count.items():
            if count > best_diff:
                best_diff = count
                best_pair = pair

        if not best_pair:
            # Fallback: use first two players
            if len(guids) >= 2:
                best_pair = (guids[0], guids[1])
            else:
                return {}

        team_a_guids.add(best_pair[0])
        team_b_guids.add(best_pair[1])

        # Assign remaining players based on co-occurrence
        for guid in guids:
            if guid in team_a_guids or guid in team_b_guids:
                continue

            # Score: positive = same as team A anchor, negative = same as team B
            score = 0
            for a_guid in team_a_guids:
                pair = tuple(sorted([guid, a_guid]))
                score += same_side_count.get(pair, 0)
                score -= diff_side_count.get(pair, 0)

            for b_guid in team_b_guids:
                pair = tuple(sorted([guid, b_guid]))
                score -= same_side_count.get(pair, 0)
                score += diff_side_count.get(pair, 0)

            if score >= 0:
                team_a_guids.add(guid)
            else:
                team_b_guids.add(guid)

        # Build result
        return {
            'Team A': {
                'guids': list(team_a_guids),
                'names': [players_data[g]['name'] for g in team_a_guids],
                'confidence': 0.8
            },
            'Team B': {
                'guids': list(team_b_guids),
                'names': [players_data[g]['name'] for g in team_b_guids],
                'confidence': 0.8
            },
            'metadata': {
                'strategy_used': 'round_consensus',
                'avg_confidence': 0.8,
                'detection_quality': 'medium'
            }
        }
```

---

## Fix #3: Populate session_results After Scoring

### Location
`bot/services/stopwatch_scoring_service.py`

### Problem
The `calculate_session_scores` method calculates scores but never saves them to `session_results`.

### Current Code (line ~316)
```python
# Return team scores with names
return {
    teams[1]['name']: teams[1]['score'],
    teams[2]['name']: teams[2]['score'],
    'maps': map_results,
    'total_maps': len(map_results)
}
```

### Fix
Add a method to save results and call it:

```python
async def save_session_results(
    self,
    session_date: str,
    team_a_name: str,
    team_a_guids: List[str],
    team_a_names: List[str],
    team_b_name: str,
    team_b_guids: List[str],
    team_b_names: List[str],
    team_a_score: int,
    team_b_score: int,
    map_results: List[Dict],
    gaming_session_id: Optional[int] = None
) -> bool:
    """
    Save session results to database.

    This is the critical missing piece - without this, team records
    can never be queried.
    """
    try:
        # Determine winner (0 = tie, 1 = team_a, 2 = team_b)
        if team_a_score > team_b_score:
            winning_team = 1
        elif team_b_score > team_a_score:
            winning_team = 2
        else:
            winning_team = 0

        # Format for storage
        format_str = f"{len(team_a_guids)}v{len(team_b_guids)}"
        round_details = json.dumps(map_results)
        round_numbers = json.dumps([1, 2] * len(map_results))

        query = """
            INSERT INTO session_results (
                session_date,
                map_name,
                gaming_session_id,
                team_1_guids,
                team_2_guids,
                team_1_names,
                team_2_names,
                format,
                total_rounds,
                team_1_score,
                team_2_score,
                winning_team,
                round_details,
                round_numbers,
                session_start
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, NOW()
            )
            ON CONFLICT (session_date, map_name) DO UPDATE SET
                team_1_score = EXCLUDED.team_1_score,
                team_2_score = EXCLUDED.team_2_score,
                winning_team = EXCLUDED.winning_team,
                round_details = EXCLUDED.round_details
        """

        # For multi-map sessions, save overall result with map_name='ALL'
        await self.db.execute(query, (
            session_date,
            'ALL',  # Overall session result
            gaming_session_id,
            json.dumps(team_a_guids),
            json.dumps(team_b_guids),
            json.dumps(team_a_names),
            json.dumps(team_b_names),
            format_str,
            len(map_results) * 2,
            team_a_score,
            team_b_score,
            winning_team,
            round_details,
            round_numbers
        ))

        logger.info(f"Saved session results: {session_date} - "
                   f"{team_a_name} {team_a_score} vs {team_b_score} {team_b_name}")
        return True

    except Exception as e:
        logger.error(f"Failed to save session results: {e}", exc_info=True)
        return False
```

### Integration
Call this from `calculate_session_scores` or from the cog that calls it:

```python
# In team_cog.py after calculating scores:
scores = await self.scorer.calculate_session_scores(session_date=date)
if scores:
    teams = await self.team_manager.get_session_teams(date)
    if teams:
        await self.scorer.save_session_results(
            session_date=date,
            team_a_name=teams['Team A']['name'],
            team_a_guids=teams['Team A']['guids'],
            team_a_names=teams['Team A']['names'],
            team_b_name=teams['Team B']['name'],
            team_b_guids=teams['Team B']['guids'],
            team_b_names=teams['Team B']['names'],
            team_a_score=scores.get(teams['Team A']['name'], 0),
            team_b_score=scores.get(teams['Team B']['name'], 0),
            map_results=scores.get('maps', [])
        )
```

---

## Fix #4: Implement get_team_record in team_manager.py

### Location
`bot/core/team_manager.py`, line 374

### Current Code
```python
async def get_team_record(
    self,
    session_date: str
) -> Dict:
    # TODO: Implement once we have session results stored
    # This will query the stopwatch scores and match them to team rosters
    pass
```

### Fix
```python
async def get_team_record(
    self,
    team_guids: List[str],
    days_back: int = 90
) -> Dict:
    """
    Get win/loss record for a team lineup.

    Args:
        team_guids: List of player GUIDs on the team
        days_back: How far back to look (default 90 days)

    Returns:
        {
            'wins': 5,
            'losses': 3,
            'ties': 1,
            'total': 9,
            'win_rate': 0.556,
            'recent_matches': [...]
        }
    """
    try:
        # Normalize GUID list for comparison
        team_guids_set = set(team_guids)
        team_guids_json = json.dumps(sorted(team_guids))

        query = """
            SELECT
                session_date,
                team_1_guids,
                team_2_guids,
                team_1_score,
                team_2_score,
                winning_team
            FROM session_results
            WHERE session_date >= (CURRENT_DATE - INTERVAL '%s days')::text
            ORDER BY session_date DESC
        """

        rows = await self.db.fetch_all(query, (days_back,))

        wins = 0
        losses = 0
        ties = 0
        matches = []

        for row in rows:
            date, t1_guids, t2_guids, t1_score, t2_score, winner = row
            t1_set = set(json.loads(t1_guids))
            t2_set = set(json.loads(t2_guids))

            # Check if this team matches team 1 or team 2
            # Using subset match (team might have subs)
            is_team_1 = len(team_guids_set & t1_set) >= len(team_guids_set) * 0.6
            is_team_2 = len(team_guids_set & t2_set) >= len(team_guids_set) * 0.6

            if not is_team_1 and not is_team_2:
                continue

            our_team = 1 if is_team_1 else 2
            our_score = t1_score if our_team == 1 else t2_score
            their_score = t2_score if our_team == 1 else t1_score

            if winner == our_team:
                wins += 1
                result = 'W'
            elif winner == 0:
                ties += 1
                result = 'T'
            else:
                losses += 1
                result = 'L'

            matches.append({
                'date': date,
                'our_score': our_score,
                'their_score': their_score,
                'result': result
            })

        total = wins + losses + ties
        win_rate = wins / total if total > 0 else 0.0

        return {
            'wins': wins,
            'losses': losses,
            'ties': ties,
            'total': total,
            'win_rate': win_rate,
            'recent_matches': matches[:10]  # Last 10
        }

    except Exception as e:
        logger.error(f"Error getting team record: {e}", exc_info=True)
        return {'wins': 0, 'losses': 0, 'ties': 0, 'total': 0, 'win_rate': 0.0}
```

---

## Fix #5: Implement get_map_performance in team_manager.py

### Location
`bot/core/team_manager.py`, line 437

### Current Code
```python
async def get_map_performance(
    self,
    session_date: str
) -> Dict[str, Dict]:
    # This will integrate with StopwatchScoring
    # TODO: Implement
    pass
```

### Fix
```python
async def get_map_performance(
    self,
    session_date: str
) -> Dict[str, Dict]:
    """
    Get team performance per map for a session.

    Returns:
        {
            'supply': {
                'Team A': {'rounds_won': 1, 'rounds_lost': 1, 'points': 1},
                'Team B': {'rounds_won': 1, 'rounds_lost': 1, 'points': 1}
            },
            ...
        }
    """
    try:
        # Get session scores which includes per-map breakdown
        scores = await StopwatchScoringService(self.db).calculate_session_scores(
            session_date=session_date
        )

        if not scores or 'maps' not in scores:
            return {}

        # Get team names
        teams = await self.get_session_teams(session_date)
        if not teams:
            return {}

        team_a_name = teams.get('Team A', {}).get('name', 'Team A')
        team_b_name = teams.get('Team B', {}).get('name', 'Team B')

        result = {}
        for map_data in scores['maps']:
            map_name = map_data['map']
            t1_pts = map_data['team1_points']
            t2_pts = map_data['team2_points']

            result[map_name] = {
                team_a_name: {
                    'rounds_won': t1_pts,
                    'rounds_lost': t2_pts,
                    'points': t1_pts
                },
                team_b_name: {
                    'rounds_won': t2_pts,
                    'rounds_lost': t1_pts,
                    'points': t2_pts
                }
            }

        return result

    except Exception as e:
        logger.error(f"Error getting map performance: {e}", exc_info=True)
        return {}
```

---

## Database Schema Reference

The `session_results` table (from PostgreSQL backup):

```sql
CREATE TABLE session_results (
    id SERIAL PRIMARY KEY,
    session_date TEXT NOT NULL,
    map_name TEXT NOT NULL,
    gaming_session_id INTEGER,
    team_1_guids TEXT NOT NULL,      -- JSON array of GUIDs
    team_2_guids TEXT NOT NULL,      -- JSON array of GUIDs
    team_1_names TEXT NOT NULL,      -- JSON array of names
    team_2_names TEXT NOT NULL,      -- JSON array of names
    format TEXT NOT NULL,            -- "3v3", "5v5", etc.
    total_rounds INTEGER NOT NULL,
    team_1_score INTEGER DEFAULT 0 NOT NULL,
    team_2_score INTEGER DEFAULT 0 NOT NULL,
    winning_team INTEGER NOT NULL,   -- 0=tie, 1=team1, 2=team2
    round_details TEXT,              -- JSON with per-round data
    round_numbers TEXT NOT NULL,     -- JSON array of round numbers
    session_start TIMESTAMP NOT NULL,
    session_end TIMESTAMP,
    duration_minutes INTEGER,
    total_kills INTEGER,
    total_deaths INTEGER,
    total_damage INTEGER,
    had_substitutions BOOLEAN DEFAULT FALSE,
    substitution_details TEXT,
    notes TEXT,
    UNIQUE(session_date, map_name)
);
```

---

## Testing Steps

After making fixes:

1. **Run a test session** or use existing data:
   ```bash
   # Check if session_teams has data
   psql -d etlegacy_production -c "SELECT * FROM session_teams LIMIT 5;"
   ```

2. **Trigger score calculation via Discord:**
   ```
   !scores 2026-01-09
   ```

3. **Verify session_results is populated:**
   ```bash
   psql -d etlegacy_production -c "SELECT * FROM session_results ORDER BY session_date DESC LIMIT 5;"
   ```

4. **Test team record query:**
   ```
   !team_record
   ```

---

## Implementation Order

1. **First:** Fix async/sync mismatch (quick fix)
2. **Second:** Add `save_session_results` method
3. **Third:** Call save method from scoring flow
4. **Fourth:** Implement `get_team_record`
5. **Fifth:** Implement `get_map_performance`
6. **Last:** Rewrite `team_detector_integration.py` if needed

---

## Why This Matters

Without these fixes:
- Team chemistry analysis is blocked (can't know who played together and won)
- Prediction engine has no historical data
- Team records show "no data"
- The whole SLOMIX vision of "team chemistry" can't work

With these fixes:
- Every session's results are stored
- Team win/loss records can be queried
- Crossfire data can be correlated with team outcomes
- Can finally answer: "Does Team A's crossfire rate correlate with wins?"
