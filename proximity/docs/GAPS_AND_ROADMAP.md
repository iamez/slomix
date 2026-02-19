# Gaps and Roadmap

Known limitations and planned improvements for the proximity tracking system.

Status note (2026-02-19): objective focus export and reaction telemetry are now implemented in v4.2. Remaining gaps below are post-v4.2 items.

---

## The Goal

Transform the proximity tracker from a "player position logger" into a "team chemistry data collector" that enables:

1. **Crossfire effectiveness analysis** - Which player pairs consistently create crossfires together
2. **Movement cohesion metrics** - Who moves in complementary patterns
3. **Objective focus tracking** - Who plays to win vs who pads stats
4. **Team composition analysis** - Which combinations of players work best together

---

## Current Gaps

### Proximity Tracker (Lua Module)

| Gap | Impact | Difficulty |
|-----|--------|------------|
| No round/match outcomes | Can't track wins/losses | Medium |
| Partial objective coverage | Objective focus works only for maps with configured coordinates | Medium |
| No "team" identity | Only knows Axis/Allies, not persistent team | Low (needs bot integration) |
| Crossfire lacks pair structure | Have participants list, but not optimized for pair queries | Low |
| Incomplete objective positions | Some maps still missing objective coordinate blocks | Medium (needs map configs) |
| No game phase detection | Can't distinguish early round vs objective push | Medium |
| No damage direction | Can't analyze flanking patterns | Low priority |
| No full MOD taxonomy | Tracker has `death_type`, but not fine-grained hit-location or full MOD analytics | Low priority |
| No class-switch timeline | Class is captured per life/engagement, but mid-life class switch history is not modeled | Low |

### Upstream Systems (Bot/Database)

| Gap | Severity | Location | Problem |
|-----|----------|----------|---------|
| `session_results` never populated | CRITICAL | No INSERT code | Team W/L impossible |
| Team detector uses SQLite | CRITICAL | `team_detector_integration.py` | Bot uses PostgreSQL |
| `get_team_record()` empty | HIGH | `team_manager.py:374` | Just `pass` |
| `get_map_performance()` empty | HIGH | `team_manager.py:437` | Just `pass` |
| Async/sync mismatch | HIGH | `advanced_team_detector.py:289` | `_analyze_multi_round_consensus()` not async |
| No automatic team storage | MEDIUM | `team_manager.py` | Only stored if cog called |

---

## Roadmap

### Phase 1: Fix Team Tracking (Bot)

**Goal:** Get team assignment and score tracking working end-to-end.

| Task | Priority | Description |
|------|----------|-------------|
| Fix async/sync mismatch | P0 | Make `_analyze_multi_round_consensus()` async |
| Populate session_results | P0 | Add INSERT code after scoring calculation |
| Fix team_detector_integration | P0 | Rewrite for async PostgreSQL |
| Implement `get_team_record()` | P1 | Query session_results for team W/L |
| Implement `get_map_performance()` | P1 | Aggregate scores per map |
| Add automatic team storage | P2 | Background task to detect and store teams |

### Phase 2: Enrich Proximity Data

**Goal:** Add data needed for team chemistry analysis.

| Task | Priority | Description |
|------|----------|-------------|
| Track round outcomes | P1 | Capture who won the round in Lua |
| Add map objective configs | P1 | Define objective positions per map |
| Expand objective map coverage | P1 | Fill remaining map coordinate blocks |
| Enrich crossfire pairs | P2 | Structure data for efficient pair queries |
| Add game phase detection | P2 | Detect early/mid/late round phases |
| Add class-switch timeline | P2 | Capture class transitions inside round/life windows |

### Phase 3: Team Chemistry Metrics

**Goal:** Build the analysis layer.

| Task | Priority | Description |
|------|----------|-------------|
| Crossfire pair success rate | P1 | Per-pair crossfire → kill conversion |
| Movement cohesion score | P2 | Measure how players move together |
| Objective focus rating | P2 | Score based on proximity to objectives |
| Attack vs defense split | P2 | Per-player performance by role |
| Team chemistry index | P3 | Composite score for player combinations |

### Phase 4: Analysis & Visualization

**Goal:** Surface insights to users.

| Task | Priority | Description |
|------|----------|-------------|
| Discord commands for pair stats | P1 | "Who do I synergize with?" |
| Web dashboard for chemistry | P2 | Visual pair performance matrix |
| Team builder suggestions | P2 | "For balanced 3v3, try..." |
| Historical trend analysis | P3 | How chemistry changes over time |

---

## Data Needed for Team Chemistry

### What We Need to Add (Lua)

```lua
-- Round outcome tracking
round_outcome = {
    winner_team = "AXIS" or "ALLIES",
    time_remaining = 120000,  -- ms
    objectives_completed = {"bankdoor", "goldcrates"}
}

-- Map objective configs (per-map)
local objectives = {
    supply = {
        tank = {x = 1234, y = 5678, z = 100, type = "escort"},
        depot_gate = {x = 2345, y = 6789, z = 100, type = "destroy"},
        depot_goods = {x = 3456, y = 7890, z = 100, type = "steal"}
    },
    goldrush = {
        bankdoor = {x = 1111, y = 2222, z = 100, type = "destroy"},
        goldcrates = {x = 3333, y = 4444, z = 100, type = "steal"}
    }
    -- etc.
}
```text

### What We Need to Fix (Bot/Database)

```sql
-- session_results needs to be populated
INSERT INTO session_results (
    session_date, map_name,
    team_1_guids, team_2_guids,
    team_1_score, team_2_score,
    winning_team, format
) VALUES (...);

-- Then we can query team chemistry
SELECT
    player1_guid, player2_guid,
    SUM(CASE WHEN won THEN 1 ELSE 0 END) as wins_together,
    COUNT(*) as games_together,
    AVG(crossfire_kills) as avg_crossfire_kills
FROM session_results sr
JOIN crossfire_pairs cp ON ...
GROUP BY player1_guid, player2_guid;
```

---

## Key Questions to Answer

Once the gaps are filled, we want to answer:

### Team Building

- "Which 3-player combination has the highest crossfire rate?"
- "Who should I pair with Player X for best movement synergy?"
- "We need a strong defender — who performs best on Axis side?"

### Individual Insights

- "What's my playstyle? Am I a fragger, anchor, or objective player?"
- "Who do I synergize best with?"
- "What's my weakness?"

### Team Balance

- "Given these 10 players, what's the fairest 5v5 split?"
- "Team A has better fraggers, Team B has better coordination — is this balanced?"

### Opponent Context

- "How does Team X perform against strong opponents vs weak ones?"
- "Which teams crumble under pressure?"

---

## Success Criteria

The system is "complete" when we can:

1. ✅ Track all player movement and combat (DONE)
2. ⏳ Assign players to persistent teams across rounds
3. ⏳ Track team win/loss records
4. ⏳ Calculate crossfire pair effectiveness
5. ⏳ Measure player objective focus
6. ⏳ Suggest balanced team compositions
7. ⏳ Factor in opponent strength

---

## Notes

- **Prototype phase** - Get basics working before adding complexity
- **Data first** - Capture more than we need now; analysis comes later
- **Storage is cheap** - Don't optimize for storage, optimize for queryability
- **Retroactive impossible** - Can't add data we didn't capture, so err on the side of capturing more
