# Team Tracking Algorithm Design - Stopwatch Mode Fix

**Problem:** In stopwatch mode, the `team` column (1/2) represents SIDE (Axis/Allies), not actual team.
**Impact:** Team stats show "Attackers vs Defenders" instead of "Team A vs Team B"

---

## Current System Issues

### Database Schema
```sql
CREATE TABLE player_comprehensive_stats (
    ...
    team INTEGER DEFAULT 0,  -- 1=Axis, 2=Allies (GAME SIDE, not actual team!)
    ...
);
```

### Stopwatch Mode Behavior
```
R1: Team A plays Axis (team=1), Team B plays Allies (team=2)
R2: Teams SWAP → Team A plays Allies (team=2), Team B plays Axis (team=1)
```

### Current Query Problem
```sql
SELECT team, SUM(kills)
FROM player_comprehensive_stats
WHERE round_id IN (session_rounds)
GROUP BY team  -- ❌ Groups by SIDE, not actual team!
```

Result: "Team 1" shows Team A R1 + Team B R2 stats = meaningless!

---

## Solution Architecture

### Phase 1: Schema Migration

#### Add `actual_team` Column
```sql
ALTER TABLE player_comprehensive_stats
ADD COLUMN actual_team_id INTEGER;  -- References team_assignments.id

-- Keep existing 'team' column for backwards compatibility
-- Rename it for clarity
ALTER TABLE player_comprehensive_stats
RENAME COLUMN team TO game_side;  -- 1=Axis, 2=Allies

COMMENT ON COLUMN player_comprehensive_stats.game_side IS
    'Game side (1=Axis, 2=Allies). In stopwatch, this switches R1→R2. Use actual_team_id for real team.';
COMMENT ON COLUMN player_comprehensive_stats.actual_team_id IS
    'Actual team ID (constant across rounds). NULL if no team assignment known.';
```

#### Create Team Assignments Table
```sql
CREATE TABLE team_assignments (
    id SERIAL PRIMARY KEY,
    gaming_session_id INTEGER REFERENCES rounds(gaming_session_id),
    team_name VARCHAR(50) NOT NULL,  -- 'Team A', 'Team B', etc.
    player_guid TEXT NOT NULL,
    player_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(gaming_session_id, player_guid)
);

CREATE INDEX idx_team_assignments_session ON team_assignments(gaming_session_id);
CREATE INDEX idx_team_assignments_guid ON team_assignments(player_guid);
```

---

## Phase 2: Team Detection Algorithm

### Input Sources (Priority Order)

1. **Voice Channel Detection** (HIGHEST PRIORITY)
   - Discord voice channels represent actual teams
   - Channel 1 = Team A, Channel 2 = Team B
   - Snapshot taken at session start
   - Maps Discord user ID → player GUID

2. **Hardcoded Teams** (session_teams table)
   - Manual team rosters from database
   - Used when voice detection unavailable
   - Current system uses this

3. **Co-occurrence Analysis** (FALLBACK)
   - Detects teammates by "always on same side"
   - Current algorithm has 50% threshold (too low!)
   - Improved algorithm:
     - Require 75% co-occurrence (not 50%)
     - Minimum 5 rounds together
     - Use graph clustering for team assignment

4. **No Detection** (NULL)
   - If no method works, actual_team_id = NULL
   - Stats queries must handle this gracefully
   - Warn user "Team stats unavailable for this session"

### Algorithm Flowchart

```
Session Import Start
    ↓
Check: Voice snapshots exist for this session?
    ├─ YES → Extract team rosters from voice channels
    │         Map Discord ID → player GUID
    │         Assign team_name based on voice channel
    │         Write to team_assignments table
    │         ↓
    └─ NO → Check: Hardcoded teams in session_teams?
            ├─ YES → Load hardcoded rosters
            │         Write to team_assignments table
            │         ↓
            └─ NO → Run co-occurrence analysis
                    ├─ Valid clusters found? (75%+ threshold, 5+ rounds)
                    │   ├─ YES → Assign team_name = "Team A", "Team B"
                    │   │         Write to team_assignments table
                    │   │         ↓
                    │   └─ NO → Set actual_team_id = NULL
                    │             Log warning: "No team detection possible"
                    │             ↓
                    └─────────────┘
                                  ↓
    For each player stat row:
        Look up team_assignment for (gaming_session_id, player_guid)
        Set actual_team_id = team_assignment.id
        ↓
    Import complete
```

---

## Phase 3: Query Updates

### Team Stats Aggregation (Fixed)
```sql
-- OLD (BROKEN):
SELECT team, SUM(kills) as total_kills
FROM player_comprehensive_stats
WHERE round_id IN (...)
GROUP BY team  -- ❌ Groups by SIDE

-- NEW (CORRECT):
SELECT ta.team_name, SUM(p.kills) as total_kills
FROM player_comprehensive_stats p
JOIN team_assignments ta ON p.actual_team_id = ta.id
WHERE p.round_id IN (...)
GROUP BY ta.team_name  -- ✓ Groups by ACTUAL TEAM

-- FALLBACK (when no team assignment):
SELECT
    CASE
        WHEN p.actual_team_id IS NOT NULL THEN ta.team_name
        ELSE 'Side ' || p.game_side  -- Show "Side 1", "Side 2"
    END as team_display,
    SUM(p.kills) as total_kills
FROM player_comprehensive_stats p
LEFT JOIN team_assignments ta ON p.actual_team_id = ta.id
WHERE p.round_id IN (...)
GROUP BY team_display
```

### Session Summary Updates
```python
# In session_stats_aggregator.py
async def aggregate_team_stats(self, session_ids, gaming_session_id):
    # Check if team assignments exist
    team_check = await self.db_adapter.fetch_one("""
        SELECT COUNT(*) FROM team_assignments
        WHERE gaming_session_id = ?
    """, (gaming_session_id,))

    if team_check[0] > 0:
        # Use actual team assignments
        query = """
            SELECT ta.team_name,
                SUM(p.kills) as total_kills,
                ...
            FROM player_comprehensive_stats p
            JOIN team_assignments ta ON p.actual_team_id = ta.id
            WHERE p.round_id IN (...)
            GROUP BY ta.team_name
        """
    else:
        # Fallback to side-based with warning
        logger.warning(f"⚠️ No team assignments for session {gaming_session_id} - using game sides")
        query = """
            SELECT
                'Side ' || p.game_side as team_display,
                SUM(p.kills) as total_kills,
                ...
            FROM player_comprehensive_stats p
            WHERE p.round_id IN (...)
            GROUP BY p.game_side
        """
```

---

## Phase 4: Voice Detection Integration

### Voice Snapshot Schema
```sql
CREATE TABLE voice_snapshots (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    discord_id BIGINT NOT NULL,
    discord_username TEXT,
    voice_channel_id BIGINT NOT NULL,
    voice_channel_name TEXT,
    action VARCHAR(20),  -- 'joined', 'left', 'switched'
    gaming_session_id INTEGER,
    FOREIGN KEY (gaming_session_id) REFERENCES rounds(gaming_session_id)
);

CREATE INDEX idx_voice_snapshots_session ON voice_snapshots(gaming_session_id);
CREATE INDEX idx_voice_snapshots_timestamp ON voice_snapshots(timestamp DESC);
```

### Voice Event Handler
```python
@bot.event
async def on_voice_state_update(member, before, after):
    # Skip bots
    if member.bot:
        return

    # Check if gaming voice channel
    if after.channel and after.channel.id in GAMING_VOICE_CHANNELS:
        # Record snapshot
        await db.execute("""
            INSERT INTO voice_snapshots (
                timestamp, discord_id, discord_username,
                voice_channel_id, voice_channel_name,
                action, gaming_session_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now(),
            member.id,
            str(member),
            after.channel.id,
            after.channel.name,
            'joined' if not before.channel else 'switched',
            current_gaming_session_id
        ))

        # Check for session start (2+ players in voice)
        player_count = len([m for m in after.channel.members if not m.bot])
        if player_count >= 2 and not gaming_session_active:
            await start_gaming_session()
```

### Discord User → Player GUID Mapping
```python
async def map_voice_to_teams(gaming_session_id):
    """
    Map voice channel presence to team assignments.

    Returns dict: {player_guid: team_name}
    """
    # Get voice snapshots for this session
    snapshots = await db.fetch_all("""
        SELECT DISTINCT discord_id, voice_channel_id, voice_channel_name
        FROM voice_snapshots
        WHERE gaming_session_id = ?
        AND action IN ('joined', 'switched')
    """, (gaming_session_id,))

    # Get player links (Discord ID → player GUID)
    links = await db.fetch_all("""
        SELECT discord_id, player_guid
        FROM player_links
    """)

    discord_to_guid = {row[0]: row[1] for row in links}

    # Assign teams based on voice channel
    team_assignments = {}
    for discord_id, channel_id, channel_name in snapshots:
        if discord_id in discord_to_guid:
            player_guid = discord_to_guid[discord_id]
            # Simple mapping: Channel 1 = Team A, Channel 2 = Team B
            team_name = "Team A" if channel_id == VOICE_CHANNEL_1 else "Team B"
            team_assignments[player_guid] = team_name

    return team_assignments
```

---

## Phase 5: Improved Co-occurrence Algorithm

```python
async def detect_teams_by_cooccurrence(session_ids: List[int]) -> Dict[str, List[str]]:
    """
    Detect teams using improved co-occurrence analysis.

    Returns: {'Team A': [guid1, guid2, ...], 'Team B': [guid3, guid4, ...]}
    """
    # Fetch all player-round combinations
    rows = await db.fetch_all("""
        SELECT player_guid, round_id, game_side
        FROM player_comprehensive_stats
        WHERE round_id IN (...)
    """, tuple(session_ids))

    # Build co-occurrence matrix
    from collections import defaultdict
    cooccurrence = defaultdict(int)
    total_rounds = defaultdict(int)

    # Group by round
    rounds = defaultdict(lambda: defaultdict(int))  # {round_id: {player_guid: side}}
    for guid, round_id, side in rows:
        rounds[round_id][guid] = side

    # Calculate co-occurrence (same side count)
    for round_id, players in rounds.items():
        guids = list(players.keys())
        for i, guid1 in enumerate(guids):
            for guid2 in guids[i+1:]:
                total_rounds[(guid1, guid2)] += 1
                if players[guid1] == players[guid2]:
                    cooccurrence[(guid1, guid2)] += 1

    # Build teammate graph (75% threshold, min 5 rounds)
    teammates = defaultdict(set)
    for (guid1, guid2), same_side_count in cooccurrence.items():
        total = total_rounds[(guid1, guid2)]
        if total >= 5 and (same_side_count / total) >= 0.75:
            teammates[guid1].add(guid2)
            teammates[guid2].add(guid1)

    # Find connected components (graph clustering)
    visited = set()
    teams = []

    def dfs(guid, team):
        visited.add(guid)
        team.append(guid)
        for neighbor in teammates[guid]:
            if neighbor not in visited:
                dfs(neighbor, team)

    for guid in teammates:
        if guid not in visited:
            team = []
            dfs(guid, team)
            if len(team) >= 2:  # Only valid teams with 2+ players
                teams.append(team)

    # Assign team names
    if len(teams) == 2:
        return {
            'Team A': teams[0],
            'Team B': teams[1]
        }
    else:
        return {}  # Invalid team detection
```

---

## Migration Strategy

### Step 1: Schema Changes (Safe)
```sql
-- Add new columns (non-breaking)
ALTER TABLE player_comprehensive_stats
ADD COLUMN actual_team_id INTEGER;

-- Create new tables
CREATE TABLE team_assignments (...);
CREATE TABLE voice_snapshots (...);
```

### Step 2: Backfill Existing Data (Optional)
```python
# For each gaming session in database:
for session_id in all_sessions:
    # Try to detect teams using co-occurrence
    teams = detect_teams_by_cooccurrence(session_id)

    if teams:
        # Create team assignments
        for team_name, guids in teams.items():
            for guid in guids:
                await create_team_assignment(session_id, team_name, guid)

        # Update player stats with team IDs
        for team_name, guids in teams.items():
            await update_actual_team_ids(session_id, team_name, guids)
```

### Step 3: Forward-going (New Sessions)
- All new sessions use team detection algorithm
- Voice detection takes priority when available
- Fallback to co-occurrence if needed

---

## Benefits

1. **Accurate Team Stats:** Team A vs Team B (not Side 1 vs Side 2)
2. **Stopwatch Compatible:** Handles side-switching correctly
3. **Multiple Detection Methods:** Voice → Hardcoded → Co-occurrence → NULL
4. **Backwards Compatible:** Existing `game_side` column preserved
5. **Auditable:** Team assignments tracked in dedicated table
6. **Voice Integration:** Ready for automatic session detection

---

## Testing Checklist

- [ ] Schema migration runs without errors
- [ ] Existing sessions don't break
- [ ] New sessions assign teams correctly
- [ ] Voice detection maps Discord → GUID
- [ ] Co-occurrence detects teams in 6v6
- [ ] Team stats show actual teams
- [ ] Session summary shows Team A vs Team B
- [ ] Handles NULL actual_team_id gracefully

---

## Implementation Priority

**CRITICAL (Do Now):**
1. Schema migration (team_assignments table)
2. Update aggregate_team_stats() to use actual_team_id
3. Update session queries

**HIGH (This Week):**
1. Voice snapshot table + event handler
2. Discord → GUID mapping in team detection
3. Improved co-occurrence algorithm (75% threshold)

**MEDIUM (Next Week):**
1. Backfill existing sessions with team detection
2. Add team assignment UI commands (!assign_team)
3. Team validation and conflict resolution

