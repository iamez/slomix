# Skill Rating Implementation Plan for ET:Legacy

**Created**: 2026-02-24
**Status**: Design — not yet implemented
**Related**: `docs/reports/DEEP_RESEARCH_ALGORITHMS_AND_QUALITY.md`, `docs/STATS_FORMULA_RESEARCH.md`

---

## The Problem

ET:Legacy pub stopwatch has characteristics that make standard skill ratings difficult:

1. **Shuffled teams** — No persistent teams. Same players end up on opposite sides next match.
2. **Classes matter** — Medic with 5 kills but 20 revives carried. Soldier with 30 kills but 0 objectives didn't. Pure win/loss doesn't capture this.
3. **Varying player counts** — 3v3 grows to 6v6 mid-game. Late joiners get unfair ratings.
4. **No matchmaking** — Pub server, not ranked queue. Massive skill range.
5. **Win condition ambiguity** — Fastest objective completion in stopwatch? Surrenders? Partial rounds? Defensive holds?
6. **No premade teams** — No captains, no strategy. Organized cups are the exception, not the norm.

---

## Three Options (Easiest → Hardest)

### Option C: Individual Performance Rating (RECOMMENDED FIRST)

**Why start here**: No win/loss needed. Respects class differences. Team shuffling doesn't matter. Uses data we already have (56 fields per player per round).

**Concept**: Build a composite "ET Rating" similar to HLTV 2.0 but adapted for ET:Legacy.

**Proposed formula**:
```
ET_Rating = w1 * norm(DPM_alive)
          + w2 * norm(KPR)
          - w3 * norm(DPR)
          + w4 * norm(revive_rate)
          + w5 * norm(objective_rate)
          + w6 * norm(survival_rate)
          + w7 * norm(useful_kill_rate)
          + w8 * norm(denied_playtime_per_min)
          + constant
```

Where `norm()` normalizes each metric to 0-1 range based on the player population distribution (percentiles).

**Weight calibration approach**:
1. Query all player stats from the database
2. Calculate percentile distributions for each metric
3. Start with equal weights, then tune based on:
   - Which metrics correlate most with being on winning teams
   - Community feedback on "who's actually good"
   - Class balance: ensure medics/engineers aren't systematically underrated

**Class-specific adjustments** (optional):
- Detect dominant class from weapon usage (SMG = medic, rifle = soldier, etc.)
- Apply class-specific weight profiles:
  - Medic: revive_rate weight increased 2x
  - Engineer: objective_rate weight increased 2x
  - Soldier: DPM/KPR weight stays high
  - Covert Ops: headshot_accuracy weight increased

**Implementation steps**:
1. Add `calculate_et_rating()` to `bot/stats/calculator.py`
2. Query population percentiles on bot startup (cache them)
3. Compute per-player rating in leaderboard/stats commands
4. Store historical ratings in a new `player_skill_history` table
5. Add `!rating` and `!rating history` commands

**New table**:
```sql
CREATE TABLE player_skill_history (
    id SERIAL PRIMARY KEY,
    player_guid VARCHAR(32) NOT NULL,
    rating FLOAT NOT NULL,
    rating_components JSONB,  -- breakdown of each component
    round_id INTEGER REFERENCES rounds(id),
    calculated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_skill_history_guid ON player_skill_history(player_guid);
CREATE INDEX idx_skill_history_date ON player_skill_history(calculated_at);
```

**Estimated effort**: Medium (2-3 sessions)

---

### Option A: Pure Win/Loss OpenSkill (Add Later)

**Concept**: Standard OpenSkill team rating using match outcomes.

**How it works**:
- Each R1+R2 match = one OpenSkill rating event
- Players on winning team = winners, losing team = losers
- Weight each player by `time_played_minutes / round_duration` to handle late joiners
- OpenSkill handles ad-hoc teams natively — shuffling is fine

**Prerequisites**:
- Clean `match_winner` data in the database (from round correlation service)
- `pip install openskill`
- Need to define "win" clearly for ET:Legacy stopwatch:
  - Option 1: Team that completes objectives faster wins
  - Option 2: Use the `winner` field from rounds table if populated
  - Option 3: Use score differential

**OpenSkill code pattern**:
```python
from openskill.models import PlackettLuce

model = PlackettLuce()

# Each match: list of teams, each team is list of player ratings
# team1 won (listed first), team2 lost
[[team1_ratings], [team2_ratings]] = model.rate(
    [[p1_rating, p2_rating], [p3_rating, p4_rating]],
    ranks=[1, 2]  # 1st place, 2nd place
)
```

**Challenges**:
- Win/loss only — doesn't reward good play on losing team
- Class-blind
- Sensitive to team balance (if teams are always unbalanced, ratings oscillate)

**Estimated effort**: Low (1 session) once match winner data is reliable

---

### Option B: Performance-Weighted OpenSkill (Most Sophisticated)

**Concept**: Combine Option A and C. Use OpenSkill for team-based rating, but weight each player's contribution by their individual performance score.

**How it works**:
- Run OpenSkill as in Option A
- But set each player's "partial play" weight based on their performance score from Option C
- A medic who hard-carried (high revives, good survival) gets MORE rating change than a passenger on the winning team
- A soldier who fragged well on the losing team loses LESS rating

**OpenSkill partial play**:
```python
# weights: 0.0 (no contribution) to 1.0 (full contribution)
model.rate(teams, ranks=[1, 2], weights=[[0.8, 0.6], [0.9, 0.3]])
```

**Implementation**:
1. Implement Option C first (individual performance score)
2. Implement Option A (basic OpenSkill)
3. Feed Option C scores as weights into Option A
4. Store both ratings: "Performance Rating" (C) and "Competitive Rating" (B)

**Estimated effort**: Medium-High (3-4 sessions, after A and C are done)

---

## Data Requirements

### Already Available
- [x] Kills, deaths, damage_given, damage_received per player per round
- [x] Headshot hits, weapon accuracy
- [x] Revives_given, objectives_stolen/returned, constructions
- [x] Time_played, time_dead, denied_playtime
- [x] Useful_kills, useless_kills
- [x] Per-weapon breakdowns
- [x] Round/match/session grouping
- [x] Player GUID tracking across name changes

### Needed for Option A/B
- [ ] Reliable `match_winner` field (which team won each R1+R2 match)
- [ ] Player-to-team mapping per match (from team detection system)

### Needed for Weight Calibration
- [ ] Population percentile distributions (query once, cache)
- [ ] Historical data analysis: which metrics correlate with winning

---

## Recommended Execution Order

1. **Option C first** — Individual ET Rating
   - No dependencies on win/loss data
   - Immediately useful for leaderboards
   - Provides the performance weights needed for Option B later

2. **Option A second** — Pure OpenSkill
   - Once round_correlation_service is out of DRY-RUN mode
   - Once match_winner data is reliable
   - Simple to implement with `pip install openskill`

3. **Option B last** — Combined rating
   - Merges A + C
   - Most accurate but most complex
   - Only worth it if the community cares about competitive rankings

---

## Reference: Industry Ratings

| Rating | Game | Key Insight for ET |
|--------|------|--------------------|
| HLTV 2.0 | CS2 | Deaths weighted MORE than kills (survival matters) |
| HLTV 3.0 | CS2 | Eco-adjusted — accounts for equipment advantage |
| ADR | CS2 | Average damage per round — simple, universal |
| KAST | CS2 | Kill/Assist/Survive/Trade per round — consistency metric |
| RWS | ESEA | Round Win Share — only counts damage in won rounds |
| ACS | Valorant | Combat score with ability usage weighting |
| TrueSkill | Xbox | Bayesian, but Microsoft-licensed (non-free) |
| OpenSkill | Open source | MIT license, handles asymmetric teams, faster than TrueSkill |

See `docs/reports/DEEP_RESEARCH_ALGORITHMS_AND_QUALITY.md` for full details on each.

---

## Files That Would Need Changes

| File | Change |
|------|--------|
| `bot/stats/calculator.py` | Add `calculate_et_rating()`, `calculate_kast()` |
| `bot/core/frag_potential.py` | Add rating fields to `PlayerMetrics` |
| `bot/cogs/leaderboard_cog.py` | Add `!rating` leaderboard variant |
| `bot/cogs/stats_cog.py` | Show rating in `!stats` output |
| `tools/schema_postgresql.sql` | Add `player_skill_history` table |
| `migrations/` | New migration for skill history table |
| `requirements.txt` | Add `openskill` (for Options A/B) |

---

*This plan was designed around the specific constraints of ET:Legacy pub stopwatch mode — shuffled teams, mixed classes, no matchmaking, varying player counts.*
